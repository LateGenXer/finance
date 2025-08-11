#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


from __future__ import annotations

import datetime
import io
import typing
import os

from zoneinfo import ZoneInfo

import streamlit as st
import pandas as pd

import xlsxwriter.workbook  # type: ignore[import-untyped]

import common

from gilts.gilts import IndexLinkedGilt, yield_curve
from gilts.ladder import BondLadder, schedule, schedule_from_csv
from ukcalendar import next_business_day, shift_year, shift_month


experimental = 'experimental' in st.query_params


common.set_page_config(
    page_title="Gilt Ladder Builder",
    layout="centered",
    initial_sidebar_state="expanded",
)


st.title('Gilt Ladder Builder')


#
# Parameters
#

with st.sidebar:
    st.header("Parameters")

    today = datetime.datetime.now(datetime.timezone.utc).date()
    tab1, tab2 = st.tabs(["Basic", "Advanced"])
    with tab1:
        st.number_input('Withdrawal amount per year:', value=10000, min_value=1, step=1, key='year_amount')
        st.number_input('Number of years:', value=10, min_value=1, max_value=50, step=1, key='year_count')
        frequency = st.radio('Withdrawal frequency:', ['Yearly', 'Monthly'], horizontal=True, key='frequency')
        min_start_date = next_business_day(today)
        max_start_date = shift_year(today, 30)
        start_date = st.date_input('Start date', value=None, min_value=min_start_date, max_value=max_start_date, key='start_date',
            help='Withdrawal start date.  Default is a year/month from today, as determined by the frequency.')
    with tab2:
        schedule_file = st.file_uploader("Upload withdrawal schedule as a CSV file.", type=['csv'], help='''
Create a spreadsheet with a `Date` and `Value` columns like:

| Date       | Value |
| :--------- | ----: |
| 2025-12-01 |  1000 |
| 2026-12-01 |  1000 |
| 2027-12-01 |  1000 |
| 2028-12-01 |  1000 |
| 2029-12-01 |  1000 |

Then export it as CSV, and upload it.  The CSV file should look like:
```
Date,Value
2025-12-01,1000
2026-12-01,1000
2027-12-01,1000
2028-12-01,1000
2029-12-01,1000
```
''')

    st.divider()

    index_linked = st.toggle("Index-linked", value=False, key="index_linked")

    st.select_slider("Marginal income tax rate:", value=0.00, options=(0.00, 0.20, 0.40, 0.45), format_func='{:.0%}'.format, key="marginal_income_tax")

    st.slider("Cash interest rate:", value=0.0, min_value=0.0, max_value=5.0, step=0.25, format='%.2f%%', key="interest_rate",
        help="""
It might be necessary to hold cash balances for long in several cases (e.g, when there are few gilts available, or when withdrawal starts far in the future.)
Normally one would hold these in a cash savings account or a Money Market Fund, yielding some interest, which can be modelled here.

The value entered here should be an _underestimation_ of the interest rate over the whole period gilts are held.

See [BoE's overnight index swap (OIS) instantaneous nominal forward curve](https://www.bankofengland.co.uk/statistics/yield-curves) for expected long term cash interest rate.
The value entered here should be well below the minimum estimated interest rate.

Overestimating the cash interest rate might adversely impact the realized return.
"""
    )

    if experimental:
        st.slider("Early sell window (years):", value=0, min_value=0, max_value=2, step=1, key="window")


#
# Calculation
#

# Withdrawal schedule
advanced = schedule_file is not None
if not advanced:
    shift:typing.Callable[[datetime.date], datetime.date]
    if frequency == 'Yearly':
        shift = shift_year
        amount = st.session_state.year_amount
        count = st.session_state.year_count
    else:
        assert st.session_state.frequency == 'Monthly'
        shift = shift_month
        amount = st.session_state.year_amount / 12
        count = st.session_state.year_count * 12
    s = schedule(count, amount, shift, start_date)
else:
    # To convert to a string based IO:
    assert schedule_file is not None
    buffer = io.TextIOWrapper(schedule_file, encoding="utf-8")

    schedule_df = schedule_from_csv(buffer)

    with st.expander("Uploaded data", expanded=False):
        st.dataframe(
            data = schedule_df,
            column_config={
                "Date": st.column_config.DateColumn("Date", required=True, min_value=today),
                "Value": st.column_config.NumberColumn("Value", required=True, default=1000, min_value=1, step=1),
            },
            hide_index = True,
        )
    assert len(schedule_df)
    assert schedule_df['Date'].min() >= min_start_date
    assert schedule_df['Value'].min() > 0

    s = list(schedule_df.itertuples(index=False))


rpi_series = common.get_latest_rpi()
issued = common.get_issued_gilts(rpi_series)
prices = common.get_latest_gilt_close_prices()
bl = BondLadder(issued, prices, s)
bl.index_linked = index_linked
bl.marginal_income_tax = st.session_state.marginal_income_tax
bl.interest_rate = st.session_state.interest_rate * .01
if experimental:
    bl.lag = st.session_state.window * 12
with st.spinner('Solving...'):
    bl.solve()

with st.sidebar:
    st.divider()

    st.header("Overview")

    st.metric(label="Cost", value=f"£{bl.cost:,.2f}")
    if not index_linked:
        st.metric(label="Net Yield", value=f"{bl.yield_:.2%}", help='''IRR derived from total cost and withdrawals.

It considers the opportunity cost of cash balances and any income tax.''')
    else:
        inflation_rate = IndexLinkedGilt.inflation_rate
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

# https://www.gov.uk/guidance/style-guide/a-to-z-of-gov-uk-style
def date_format(d):
    return f'{d.day} {d:%B} {d.year}'

with tab1:

    st.warning("A bond ladder is not necessarily the best strategy. Read more [here](https://github.com/LateGenXer/finance/tree/main/gilts#on-gilt-ladders).", icon="⚠️")

    if not advanced and start_date is not None:
        msg = f'Coupons received before {date_format(start_date)} will be accumulated as a cash balance and not reinvested.'
        if not st.session_state.interest_rate:
            msg += '\n\nYou might want to set a relatively modest cash interest rate for more meaningful results.'
        st.warning(msg, icon="⚠️")

    if st.session_state.interest_rate > 0.50:
        st.warning("Make sure you don't overestimate cash interest rate.  Check the (?) icon next to it for guidance.", icon="⚠️")

    msg  = 'Using:'
    msg += f'\n- gilts in issue on the close of {date_format(issued.close_date)}'

    prices_date = prices.get_prices_date()
    prices_date = prices_date.astimezone(ZoneInfo("Europe/London"))
    msg += f';\n- prices from {date_format(prices_date)}, {prices_date:%H:%M (%Z)}'

    if index_linked:
        msg += f';\n- RPI published on {date_format(rpi_series.release_date)}'
    msg += '.'

    st.info(msg, icon="ℹ️")

    df = bl.buy_df
    assert df is not None

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
        dict(selector='table', props='margin: 0px auto;'),
        dict(selector='table, tr, th, td', props='border: 0;'),
        dict(selector='td', props='text-align: right; padding: 0px 5px 0px 5px;'),
        dict(selector='tbody tr:nth-child(even)', props='background-color: whitesmoke;'),
        dict(selector='td.col0, td.col1', props='text-align: left'),
    ])

    df_ = df[df['Quantity'].lt(.005)]
    slice_ = pd.IndexSlice[df_.index, df_.columns]
    s.set_properties(**{'opacity': '0.25'}, subset=slice_)
    s.set_properties(**{'font-weight': 'bold'}, subset=df.index[-1])

    # https://github.com/streamlit/streamlit/issues/4830#issuecomment-1147878371
    st.write(s.to_html(table_uuid="buy_table"), unsafe_allow_html=True)

    st.text('')

    with st.expander('Definitions'):
        st.markdown('''
**Tradable Instrument Display Mnemonics (TIDM)**: London Stock Exchange ticker (previously referred to as EPIC codes).

**Clean Price**: market quoted price; excludes accrued interest, and inflation uplift (for 3-month lag index-linked gilts.)

**Dirty Price**: purchase price; includes accrued interest and inflation uplift (for index-linked gilts.)

**Quantity**: number of nominal £100 units to buy; however brokers might use different units (e.g., IWeb and Hargreaves Lansdown consider nominal £1 units.)

**Gross Redemption Yield (GRY)**: yield to maturity, gross of taxes, and in real terms for index-linked gilts.
''')

    df1 = df

    st.divider()
    st.subheader('Yield Curve')
    df = yield_curve(issued, prices, index_linked=index_linked)
    yTitle = 'Real yield (%)' if index_linked else 'Yield (%)'
    common.plot_yield_curve(df, yTitle=yTitle)


with tab2:
    if st.session_state.index_linked:
        st.info("Values shown below are in _today_'s money, i.e., discounted by assumed inflation.  Balances [depreciate with time](https://github.com/LateGenXer/finance/issues/5#issuecomment-2451693350), besides reflecting in/out-flows.", icon="ℹ️")

    df = bl.cash_flow_df

    s = Styler(df, uuid_len=0, cell_ids=False)

    s.hide(axis='index')

    s.format(precision=2, thousands=',', decimal='.', na_rep='')

    s.set_table_styles([
        dict(selector='th', props='text-align: center;'),
        dict(selector='th, td', props='font-family: monospace; font-size: 8pt;'),
        dict(selector='table, tr, th, td', props='border: 0;'),
        dict(selector='td', props='text-align: right; padding: 0px 5px 0px 5px;'),
        dict(selector='tbody tr:nth-child(even)', props='background-color: whitesmoke;'),
        dict(selector='th.col1, td.col1', props='text-align: left'),
    ])
    s.set_properties(subset=['Description'], **{'text-align': 'left'})

    st.write(s.to_html(table_uuid="cash_flow_table", border=0), unsafe_allow_html=True)

    st.text("")

    with st.expander('Definitions'):
        st.markdown('''
**Taxable Income (Tax. Inc.)**: cash inflows sujbect to income tax; this excludes accrued interest and redemptions,
''')
    df2 = df


with tab3:
    # https://xlsxwriter.readthedocs.io/example_pandas_multiple.html
    @st.cache_data
    def to_excel(df1, df2):
        stream = io.BytesIO()
        with pd.ExcelWriter(stream, engine='xlsxwriter') as writer:
            df1.to_excel(writer, index=False, float_format='%.4f', sheet_name='Implementation')
            df2.to_excel(writer, index=False, float_format='%.2f', sheet_name='CashFlow')

            workbook = writer.book
            assert isinstance(workbook, xlsxwriter.workbook.Workbook)
            sheet1 = writer.sheets["Implementation"]

            currency_format = workbook.add_format({"num_format": "0.00"})
            percent_format = workbook.add_format({"num_format": "0.00%"})

            def apply_format(df, sheet, columns, format):
                names = list(df1.columns)
                for name in columns:
                    col = names.index(name)
                    sheet1.set_column(col, col, None, format)

            apply_format(df1, sheet1, ["Clean Price", "Dirty Price", "Quantity", "Cost"], currency_format)
            apply_format(df1, sheet1, ["GRY"], percent_format)

        return stream.getvalue()

    xlsx = to_excel(df1, df2)
    st.download_button(label='Export to Excel', data=xlsx, file_name= 'gilt_ladder.xlsx')


@st.cache_data(ttl=24*3600)
def about():
    return open(os.path.join(os.path.dirname(__file__), '..', 'gilts', 'README.md'), 'rt').read()


with tab4:
    st.markdown(about())


common.analytics_html()
