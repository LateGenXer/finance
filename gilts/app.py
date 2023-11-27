#!/usr/bin/env python3
#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import datetime
import io
import json
import math
import os
import operator
import sys

import streamlit as st
import pandas as pd


experimental = '--experimental' in sys.argv[1:]


# https://docs.streamlit.io/library/api-reference/utilities/st.set_page_config
st.set_page_config(
    page_title="Gilt Ladder Builder",
    page_icon=":pound banknote:",
    layout="centered",
    initial_sidebar_state="expanded",
    menu_items={
        "Get help": "https://github.com/LateGenXer/finance/discussions",
        "Report a Bug": "https://github.com/LateGenXer/finance/issues",
        "About": """Gilt Ladder Builder

https://github.com/LateGenXer/finance/tree/main/gilts

Copyright (c) 2023 LateGenXer.

""",
    }
)


import caching
if "PYTEST_CURRENT_TEST" not in os.environ:
    assert caching.stub_use_count == 0
    caching.cache_data = st.cache_data

import lse
import rpi

from gilts import Issued, BondLadder, schedule, monthly, yearly, yield_curve


#
# Parameters
#

with st.sidebar:
    st.title('Gilt Ladder Builder')

    #st.info('Parameters are not stored permanently and will not persist across page reloads.', icon="ℹ️")

    # TODO
    if experimental:
        advanced = st.toggle("Advanced", value=False, key="advanced")
    else:
        advanced = False

    if not advanced:
        st.number_input('Withdrawal amount per year:', value=10000, min_value=1, step=1, key='year_amount')
        st.number_input('Number of years:', value=10, min_value=1, max_value=50, step=1, key='year_count')
        frequency = st.radio('Withdrawal frequency:', ['Yearly', 'Monthly'], horizontal=True, key='frequency')
    else:
        today = datetime.datetime.utcnow().date()
        default_date = today.replace(year=today.year + 1)
        edited_df = st.data_editor(
            data = pd.DataFrame([
                {'Date': default_date, 'Amount': 1000 },
            ]),
            column_config={
                "Date": st.column_config.DateColumn("Date", required=True, min_value=today),
                "Amount": st.column_config.NumberColumn("Amount", required=True, default=1000, min_value=1, step=1),
            },
            num_rows="dynamic",
            key="schedule",
        )

    index_linked = st.toggle("Index-linked", value=False, key="index_linked")

    st.select_slider("Marginal income tax rate:", value=0.00, options=(0.00, 0.20, 0.40, 0.45), format_func='{:.0%}'.format, key="marginal_income_tax")

    st.slider("Cash interest rate:", value=0.0, min_value=0.0, max_value=5.0, step=0.25, format='%.2f%%', key="interest_rate",
        help="See [BoE's overnight index swap (OIS) instantaneous nominal forward curve](https://www.bankofengland.co.uk/statistics/yield-curves) for expected long term cash interest rate."
    )

    if experimental:
        st.slider("Early sell window (years):", value=0, min_value=0, max_value=2, step=1, key="window")


#
# Calculation
#

# Withdrawal schedule
if not advanced:
    if frequency == 'Yearly':
        f = yearly
        amount = st.session_state.year_amount
        count = st.session_state.year_count
    else:
        assert st.session_state.frequency == 'Monthly'
        f = monthly
        amount = st.session_state.year_amount / 12
        count = st.session_state.year_count * 12
    s = schedule(count, amount, f)
else:
    s = []
    for index, row in edited_df.iterrows():
        date = row['Date']
        value = row['Amount']
        assert isinstance(date, datetime.date)
        assert value > 0
        s.append((date, value))
    if not s:
        st.error("No data")
        st.stop()
    s.sort(key=operator.itemgetter(0))


issued = Issued()
prices = lse.GiltPrices()
rpi_series = rpi.RPI() # XXX pass this to BondLadder
bl = BondLadder(issued, prices, s)
bl.index_linked = index_linked
bl.marginal_income_tax = st.session_state.marginal_income_tax
bl.interest_rate = st.session_state.interest_rate * .01
if experimental:
    bl.lag = st.session_state.window
try:
    with st.spinner():
        bl.solve()

except ValueError as ex:
    st.error(str(ex))
    st.stop()

with st.sidebar:
    st.divider()

    st.metric(label="Cost", value=f"£{bl.cost:,.2f}")
    if not index_linked:
        st.metric(label="Net Yield", value=f"{bl.yield_:.2%}", help='''IRR derived from total cost and withdrawals.

It considers the opportunity cost of cash balances and any income tax.''')
    else:
        inflation_rate = .03
        yield_ = (1.0 + bl.yield_)/(1 + inflation_rate) - 1
        st.metric(label="Net Real Yield", value=f"{yield_:.2%}", help=f'''IRR derived from total cost and withdrawals adjusted for a constant inflation rate of {inflation_rate:.1%}.

It considers the opportunity cost and depreciation of cash balances as well as any income tax.''')
        st.metric(label="Net Nominal Yield", value=f"{bl.yield_:.2%}",
            help=f'Assuming a constant inflation rate of {inflation_rate:.1%} from the last published RPI.'
        )

    if advanced:
        withdrawal_rate = bl.withdrawal_rate
    else:
        # Use the input figure as it's more accurate
        withdrawal_rate = st.session_state.year_amount / bl.cost

    st.metric(label="Withdrawal Rate", value=f"{withdrawal_rate:,.2%}",
        help='Percentage of the pot (total cost) withdrawn per year.'
    )


tab1, tab2, tab3, tab4 = st.tabs(["Implementation", "Cash Flow", "Export", "About"])

currency_format = '{:,.2f}'

with tab1:

    df = bl.buy_df

    st.warning("A bond ladder is not necessarily the best strategy. Read [here](https://www.fidelity.com/learning-center/investment-products/fixed-income-bonds/bond-investment-strategies) to know more.", icon="⚠️")

    st.info(f'Using prices obtained on {prices.get_prices_date().isoformat(sep=" ", timespec="minutes")}', icon="ℹ️")
    if index_linked:
        st.info(f'Using published RPI series untill {rpi_series.last_date().strftime("%B %Y")}', icon="ℹ️")

    # https://pandas.pydata.org/docs/user_guide/style.html#1.-Remove-UUID-and-cell_ids
    from pandas.io.formats.style import Styler
    s = Styler(df, uuid_len=0, cell_ids=False)
    s.hide(axis='index')
    formatters = {
        'Clean Price': currency_format,
        'Dirty Price': currency_format,
        'GRY':   '{:.2%}'.format,
        'Quantity':  '{:.2f}'.format,
        'Cost':  currency_format,
    }
    s.format(na_rep='')
    s.format(lambda tidm: f'<a href="https://www.londonstockexchange.com/stock/{tidm:}/united-kingdom">{tidm}</a>', subset=['TIDM'], na_rep='')
    s.format(formatters, subset=list(formatters.keys()), na_rep='')

    s.set_table_styles([
        {'selector': 'table', 'props': 'margin: 0px auto;'},
        {'selector': 'table, tr, th, td', 'props': 'border: 0;'},
        {'selector': 'td', 'props': 'text-align: right; padding: 0px 5px 0px 5px;'},
        {'selector': 'tbody tr:nth-child(even)', 'props': 'background-color: whitesmoke;'},
        {'selector': 'td.col0', 'props': 'text-align: left'},
        {'selector': 'td.col1', 'props': 'text-align: left'},
    ])

    df_ = df[df['Quantity'].lt(.005)]
    slice_ = pd.IndexSlice[df_.index, df_.columns]
    s.set_properties(**{'opacity': '0.25'}, subset=slice_)
    s.set_properties(**{'font-weight': 'bold'}, subset=df.index[-1])

    # https://github.com/streamlit/streamlit/issues/4830#issuecomment-1147878371
    st.write(s.to_html(table_uuid="buy_table"), unsafe_allow_html=True)

    df1 = df

    if True:
        st.divider()
        st.subheader('Yield Curve')
        import altair as alt

        df = yield_curve(issued, prices, index_linked=index_linked)

        xScale = alt.Scale(zero=True, domain=[0, 50])
        xAxis = alt.Axis(format=".2~f", values=[0, 1, 2, 3, 5, 10, 15, 30, 50], title="Maturity (years)")
        yDomainMax = int(math.ceil(df['Yield'].max() + 0.25))
        yScale = alt.Scale(zero=True, domain=[0, yDomainMax])
        yTitle = 'Nominal yield (%)' if index_linked else 'Yield (%)'
        yAxis = alt.Axis(format=".2~f", values=list(range(0, yDomainMax + 1)), title=yTitle)

        chart = (
            alt.Chart(df)
            .mark_point()
            .encode(
                alt.X("Maturity:Q", scale=xScale, axis=xAxis),
                alt.Y("Yield:Q", scale=yScale, axis=yAxis),
                alt.Color("TIDM:N", legend=None),
            )
        )
        st.altair_chart(chart, use_container_width=True)


with tab2:
    if st.session_state.index_linked:
        st.info("Figures are shown in today's money.", icon="ℹ️")

    df = bl.cash_flow_df

    s = Styler(df, uuid_len=0, cell_ids=False)

    s.hide(axis='index')

    s.format_index(formatter=str.title, axis=1)
    s.format(precision=2, thousands=',', decimal='.', na_rep='')

    s.set_table_styles([
        {'selector': 'table, tr, th, td', 'props': 'border: 0;'},
        {'selector': 'td', 'props': 'text-align: right; padding: 0px 5px 0px 5px;'},
        {'selector': 'tbody tr:nth-child(even)', 'props': 'background-color: whitesmoke;'},
        {'selector': 'td.col1', 'props': 'text-align: left'},
    ])
    s.set_properties(subset=['Description'], **{'text-align': 'left'})

    if True:
        st.write(s.to_html(table_uuid="cash_flow_table", border=0), unsafe_allow_html=True)
    else:
        # XXX st.dataframe
        df.fillna("", inplace=True)
        #s = s.highlight_null(props="color: transparent;")
        st.dataframe(s,
            column_config={
                "Date": st.column_config.DateColumn("Date"),
                "Description": "Description",
                "Incoming": st.column_config.NumberColumn("Incoming", format="%.2f"),
                "Outgoing": st.column_config.NumberColumn("Outgoing", format="%.2f"),
                "Balance":  st.column_config.NumberColumn("Balance",  format="%.2f"),
                "Income":   st.column_config.NumberColumn("Income",   format="%.2f"),
            },
            hide_index=True,
            use_container_width=True,
        )

    df2 = df


with tab3:
    # https://xlsxwriter.readthedocs.io/example_pandas_multiple.html
    @st.cache_data
    def to_excel(df1, df2):
        stream = io.BytesIO()
        engine = 'xlsxwriter'
        #engine = 'openpyxl'
        writer = pd.ExcelWriter(stream, engine=engine)
        df1.to_excel(writer, index=False, float_format='%.2f', sheet_name='Implementation')
        df2.to_excel(writer, index=False, float_format='%.2f', sheet_name='CashFlow')
        writer.close()
        return stream.getvalue()

    xlsx = to_excel(df1, df2)
    st.download_button(label='Export to Excel', data=xlsx, file_name= 'gilt_ladder.xlsx')


@st.cache_data(ttl=24*3600)
def about():
    return open(os.path.join(os.path.dirname(__file__), 'README.md'), 'rt').read()


with tab4:
    st.markdown(about())


#
# Disclaimer
#

st.divider()

st.subheader('Disclaimer')

# https://termly.io/resources/templates/disclaimer-template/
st.markdown('''
The information provided by LateGenXer ('we', 'us', or 'our') on https://lategenxer.streamlit.app/ (the 'Site') is for general informational purposes only. All information on the Site is provided in good faith, however we make no representation or warranty of any kind, express or implied, regarding the accuracy, adequacy, validity, reliability, availability, or completeness of any information on the Site. UNDER NO CIRCUMSTANCE SHALL WE HAVE ANY LIABILITY TO YOU FOR ANY LOSS OR DAMAGE OF ANY KIND INCURRED AS A RESULT OF THE USE OF THE SITE OR RELIANCE ON ANY INFORMATION PROVIDED ON THE SITE. YOUR USE OF THE SITE AND YOUR RELIANCE ON ANY INFORMATION ON THE SITE IS SOLELY AT YOUR OWN RISK.

The Site may contain (or you may be sent through the Site) links to other websites or content belonging to or originating from third parties or links to websites and features in banners or other advertising. Such external links are not investigated, monitored, or checked for accuracy, adequacy, validity, reliability, availability, or completeness by us. WE DO NOT WARRANT, ENDORSE, GUARANTEE, OR ASSUME RESPONSIBILITY FOR THE ACCURACY OR RELIABILITY OF ANY INFORMATION OFFERED BY THIRD-PARTY WEBSITES LINKED THROUGH THE SITE OR ANY WEBSITE OR FEATURE LINKED IN ANY BANNER OR OTHER ADVERTISING. WE WILL NOT BE A PARTY TO OR IN ANY WAY BE RESPONSIBLE FOR MONITORING ANY TRANSACTION BETWEEN YOU AND THIRD-PARTY PROVIDERS OF PRODUCTS OR SERVICES.

The Site cannot and does not contain financial advice. The financial information is provided for general informational and educational purposes only and is not a substitute for professional advice. Accordingly, before taking any actions based upon such information, we encourage you to consult with the appropriate professionals. We do not provide any kind of financial advice. THE USE OR RELIANCE OF ANY INFORMATION CONTAINED ON THE SITE IS SOLELY AT YOUR OWN RISK.
''')
