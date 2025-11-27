#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import datetime
import os
import json
import sys

import streamlit as st
import pandas as pd

from tax import uk

from tax.uk import aa, uiaa
from rtp.model import model, column_headers, dataframe

import common


common.set_page_config(
    page_title="Retirement Tax Planner",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title('Retirement Tax Planner')


#
# State
#

version = 1

default_state = {
    "joint": False,
    "dob_1": 1980,
    "dob_2": 1980,
    "state_pension_years_1": 35,
    "state_pension_years_2": 35,
    "marginal_income_tax_1": 0.4,
    "marginal_income_tax_2": 0.2,
    "sipp_1": 750000,
    "sipp_2": 000000,
    "sipp_df_1": 0,
    "sipp_df_2": 0,
    "sipp_contrib_1": 0,
    "sipp_contrib_2": uiaa,
    "sipp_extra_contrib": False,
    "db_payments_1": "",
    "db_payments_2": "",
    "db_ages_1": "",
    "db_ages_2": "",
    "lsa_ratio_1": 100.0,
    "lsa_ratio_2": 100.0,
    "isa": 250000,
    "gia": 0,
    "misc_contrib": 0,
    "inflation_rate": 2.5,
    "isa_growth_rate": 5.5,
    "gia_growth_rate": 5.5,
    "sipp_growth_rate_1": 5.5,
    "sipp_growth_rate_2": 5.5,
    "retirement_country": "UK",
    "retirement_income_net": 0,
    "retirement_year": 2045,
    "lump_sum": 0,
    "aa_1": aa,
    "aa_2": uiaa,
    "marriage_allowance": False,
    "end_age": 100,
}


def load_state(data:bytes, override:bool) -> None:
    state = json.loads(data)
    uploaded_version = state.pop('version', 0)
    if uploaded_version != version:
        st.warning(f"Expected parameter file version {version} but got {uploaded_version}", icon="⚠️")
    for key, value in state.items():
        if key in default_state:
            if override:
                st.session_state[key] = value
            else:
                st.session_state.setdefault(key, value)
        else:
            st.warning(f"Unexpected parameter {key}={value!r}", icon="⚠️")


# Allow to override initial state on development enviroments

devel = False
if "PYTEST_CURRENT_TEST" not in os.environ:
    if len(sys.argv) == 2:
        devel = True
        data = open(sys.argv[1], 'rb').read()
        load_state(data, override=False)
    else:
        try:
            from rtp.devel import state as devel_state  # type: ignore[import-not-found]
        except ImportError:
            pass
        else:
            devel = True
            with st.expander("Devel..."):
                st.write(devel_state)
                for key, value in devel_state.items():
                    st.session_state.setdefault(key, value)
for key, value in default_state.items():
    st.session_state.setdefault(key, value)

#
# About
#

def about():
    return open(os.path.join(os.path.dirname(__file__), '..', 'rtp', 'README.md'), 'rt').read()

with st.expander("About..."):
    st.markdown(about())

#
# Parameters
#

st.header('Parameters')

st.info('Parameters are not stored permanently and will not persist across page reloads, but they can be downloaded/uploaded.', icon="ℹ️")

st.session_state.setdefault('uploaded_hashes', set())
with st.expander("Upload..."):
    uploaded_file = st.file_uploader("Upload parameters", type=['json'], help='Upload all parameters from JSON file.', label_visibility='collapsed')
    if uploaded_file is not None:
        data = uploaded_file.getvalue()
        # Avoid reprocessing the uploaded file on re-runs
        data_hash = hash(data)
        if data_hash not in st.session_state.uploaded_hashes:
            st.session_state.uploaded_hashes.add(data_hash)
            load_state(data, override=True)

st.checkbox("Joint calculation", key="joint")
with st.form(key='form'):

    tab1, tab2, tab3, tab4 = st.tabs(["Basic", "Advanced", "Post-retirement", "Experimental"])

    # Basic
    with tab1:

        col1, col2, col3 = st.columns(3)

        state_pension_years_help = "If in doubt [check on your National Insurance record](https://www.gov.uk/check-state-pension) how many years of full contributions you have, and add how many more years you plan to work or do voluntary contributions."

        marginal_income_tax_help = "Used to estimate income tax from withdrawing more than the Tax Free Cash from a pension before retirement."

        sipp_help = """_Uncrystalized_ funds held in Defined Contribution Pension schemes.

If pension funds have been accessed as tax-free-allowance or moved into flexi-access drawdown then the appropriate fields in the _Post-retirement_ tab should be filled in.
"""

        db_payments_help = """Yearly payment made by Defined Benefit pension schemes(s).  Payments from multiple pension schemes can be entered seperated by semi-colons (;).

Payments are assumed to increase in line with inflation.
"""
        db_ages_help = "Age(s) the DB pension scheme(s) start paying.  Ages of multiple pension schemes can be entered seperated by semi-colons (;)."

        with col1:
            st.subheader('You')
            st.number_input('Year of birth:', min_value=1920, max_value=2080, step=1, key='dob_1')
            st.number_input('State pension qualifying years at retirement:', min_value=0, max_value=35, step=1, key='state_pension_years_1', help=state_pension_years_help)
            st.number_input('DC pensions value:', min_value=0, step=1, key='sipp_1', help=sipp_help)
            st.number_input('DC pensions yearly _gross_ contribution:', min_value=0, max_value=aa, step=1, key='sipp_contrib_1', help="Until retirement")
            st.text_input('DB pension yearly benefit(s):', key='db_payments_1', help=db_payments_help)
            st.text_input('DB pension age(s):', key='db_ages_1', help=db_ages_help)
            st.select_slider("Marginal income tax rate:", options=(0.00, 0.20, 0.40, 0.45), format_func='{:.0%}'.format, key="marginal_income_tax_1", help=marginal_income_tax_help)

        single = not st.session_state.joint
        with col2:
            st.subheader('Partner')
            st.number_input('Year of birth:', min_value=1920, max_value=2080, step=1, key='dob_2', disabled=single)
            st.number_input('State pension qualifying years at retirement:', min_value=0, max_value=35, step=1, key='state_pension_years_2', disabled=single, help=state_pension_years_help)
            st.number_input('DC pensions value:', min_value=0, step=1, key='sipp_2', help=sipp_help, disabled=single)
            st.number_input('DC pensions yearly _gross_ contribution:', min_value=0, max_value=aa, step=1, key='sipp_contrib_2', help="Until retirement", disabled=single)
            st.text_input('DB pension yearly benefit(s):', key='db_payments_2', help=db_payments_help)
            st.text_input('DB pension age(s):', key='db_ages_2', help=db_ages_help)
            st.select_slider("Marginal income tax rate:", options=(0.00, 0.20, 0.40, 0.45), format_func='{:.0%}'.format, key="marginal_income_tax_2", disabled=single, help=marginal_income_tax_help)

        with col3:
            st.subheader('Shared')
            st.number_input('Retirement year:', min_value=2020, max_value=2080, step=1, key='retirement_year')
            st.number_input('Retirement income (0 for maximum):', min_value=0, step=1000, key='retirement_income_net', help='Go to https://www.retirementlivingstandards.org.uk/ for guidance.')
            st.number_input('ISAs value:', min_value=0, step=1, key='isa')
            st.number_input('GIAs value:', min_value=0, step=1, key='gia')
            st.number_input('ISAs/GIAs yearly savings:', min_value=0, step=1, key='misc_contrib', help="Until retirement.  The optimization will automatically maximize the ISA allowance.")

    # Advanced
    with tab2:
        col1, col2, col3 = st.columns(3)

        with col1:
            max_rate = 10.0
            growth_rate_format = '%.1f%%'
            st.slider("Inflation rate:", min_value=0.0, max_value=max_rate, step=0.5, format=growth_rate_format, key="inflation_rate")
            st.slider("Your SIPP nominal growth rate:", min_value=0.0, max_value=max_rate, step=0.5, format=growth_rate_format, key="sipp_growth_rate_1")
            st.slider("Partner's SIPP nominal growth rate:", min_value=0.0, max_value=max_rate, step=0.5, format=growth_rate_format, key="sipp_growth_rate_2")
            st.slider("ISAs nominal growth rate:", min_value=0.0, max_value=max_rate, step=0.5, format=growth_rate_format, key="isa_growth_rate")
            st.slider("GIAs nominal growth rate:", min_value=0.0, max_value=max_rate, step=0.5, format=growth_rate_format, key="gia_growth_rate")

        with col2:
            st.checkbox("Marriage Allowance", key="marriage_allowance", disabled=single, help='\n'.join([
                "Transfer the Marriage Allowance from your partner to you.",
                "",
                "This will enforce the [applicable rules](https://www.gov.uk/marriage-allowance#who-can-apply) and might end up constraining the retirement income to ensure income stays withing basic rate.",
            ]))

        with col3:
            st.selectbox("Retirement country:", options=("UK", "PT", "JP"), index=0, key='retirement_country',
                help="Country to be tax resident from _retirement year_. " +
                "Values still always in pounds.  Differences in cost of life not considered."
            )
            st.number_input('End age:', min_value=70, max_value=130, step=1, key='end_age')

    # Post-retirement
    with tab3:
        col1, col2, col3 = st.columns(3)

        lsa_ratio_help = '''Percentage of the Lump Sump Allowance left.

This is equivalent to the old Lifetime Allowance percentage.
'''
        sipp_df_help = '''Pension funds hold in flex-acces drawdown.'''

        with col1:
            st.subheader('You')
            st.number_input('Lum Sump Allowance (%):', min_value=0, max_value=100, step=1, key='lsa_ratio_1')
            st.number_input('DC pension flexi-access drawdown funds:', min_value=0, step=1, key='sipp_df_1', help=sipp_df_help)

        with col2:
            st.subheader('Partner')
            st.number_input('Lum Sump Allowance (%):', min_value=0, max_value=100, step=1, key='lsa_ratio_2', disabled=single)
            st.number_input('DC pensions flexi-access drawdown funds:', min_value=0, step=1, key='sipp_df_2', disabled=single)

        with col3:
            st.subheader('Shared')

    # Experimental
    with tab4:
        st.warning("These are experimental features which might lead to misleading results.  Carefully read the help before changing any of these parameters!", icon="⚠️")

        col1, col2 = st.columns(2)

        with col1:
            st.checkbox("Allow extra SIPP contributions", key="sipp_extra_contrib", help='\n'.join([
                "Allow additional SIPP contributions funded by unearned income, on top of regular contributions.",
                "",
                "Care is taken to follow the [pension tax-free cash recycling rules](https://www.gov.uk/hmrc-internal-manuals/pensions-tax-manual/ptm133800) by limiting total contributions to 130% of the regular contributions.",
                "This is not necessarily optimal, but is easy to model and it should be resonably safe.",
                "",
                "Still contributions should be checked with utmost care and advice taken before following such plan.",
            ]))

        with col2:
            st.number_input('Lump sum:', min_value=0, step=1, key='lump_sum', help='\n'.join([
                'Determine how to best allocate a lump sum.',
                '',
                'Results are crude because Annual Allowance is not accurately known, being inferred from the marginal income tax rates set in the _Basic_ tab.'
            ]))
            st.number_input('Your Annual Allowance:', min_value=0, max_value=aa, step=100, key='aa_1')
            st.number_input('Partner\'s Annual Allowance:', min_value=0, max_value=aa, step=100, key='aa_2', help="Until retirement", disabled=single)

    submitted = st.form_submit_button(label='Update', type='primary')


state = {key: value for key, value in st.session_state.items() if key in default_state}
state['version'] = version
data = json.dumps(state, sort_keys=True, indent=2).encode('utf-8')
timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat(sep='-', timespec='seconds')
st.download_button("Download", data, file_name=f"rtp-{timestamp}.json", mime="application/json", help="Download all parameters as a JSON file.", width='stretch')


#
# Results
#

st.header('Results')

params = {key: value for key, value in st.session_state.items() if key in default_state}

def perc_xform(x):
    return x*.01

def number_list_xform(s):
    if s:
        return [float(n) for n in s.split(';')]
    else:
        return []

state_xforms =  {
    'inflation_rate': perc_xform,
    'sipp_growth_rate_1': perc_xform,
    'sipp_growth_rate_2': perc_xform,
    'isa_growth_rate': perc_xform,
    'gia_growth_rate': perc_xform,
    'lsa_ratio_1': perc_xform,
    'lsa_ratio_2': perc_xform,
    'db_payments_1': number_list_xform,
    'db_payments_2': number_list_xform,
    'db_ages_1': number_list_xform,
    'db_ages_2': number_list_xform,
}
for key, xform in state_xforms.items():
    params[key] = xform(st.session_state[key])

params['present_year'] = datetime.date.today().year
params['country'] = params.pop('retirement_country')

if devel:
    with st.expander("Parameters"):
        st.write(params)

if params['db_payments_1'] or params['db_payments_2']:
    st.warning('Defined Benefit Pension Schemes support is work in progress.  Please analyze results carefully and report any issues.', icon="🚧")


# https://docs.streamlit.io/library/advanced-features/caching
#@st.cache_data(ttl=3600, max_entries=1024)
def run(params):
    return model(**params)

try:
    result = run(params)
except ValueError as ex:
    st.error(str(ex))
    st.stop()

df = dataframe(result.data)

st.info("All values presented are in _today_'s pounds.", icon="ℹ️")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(label="Start net worth", value=f"£{result.net_worth_start:,.0f}")
with col2:
    st.metric(label="Retirement net income", value=f"£{result.retirement_income_net:,.0f}")
with col3:
    st.metric(label="End net worth", value=f"£{result.net_worth_end:,.0f}")
with col4:
    st.metric(label="Total tax", value=f"£{result.total_tax:,.0f}")

float_format = '{:,.0f}'
perc_format = '{:.1%}'
delta_format = '{:+,.0f}'
formatters = {
    'year': '{:}'.format,
    'sipp_delta_1': delta_format,
    'sipp_delta_2': delta_format,
    'contrib_1': delta_format,
    'contrib_2': delta_format,
    'isa_delta': delta_format,
    'gia_delta': delta_format,
    'lsa_ratio_1':  perc_format,
    'lsa_ratio_2':  perc_format,
    'income_tax_rate_1': perc_format,
    'income_tax_rate_2': perc_format,
    'cgt_rate':     perc_format,
}

df = df[column_headers.keys()]

s = df.style

s.hide(axis='index')

s.format(float_format)
s.format(formatters, subset=list(formatters.keys()))

s.relabel_index(list(column_headers.values()), axis='columns')

hidden_columns = []
if not st.session_state.joint:
    hidden_columns += [name for name in column_headers.keys() if name.endswith('_2')]
if hidden_columns:
    s.hide(axis='columns', subset=hidden_columns)

s.set_properties(**{'font-size': '10pt'})
s.set_table_styles([
    {'selector': 'td', 'props': 'text-align: right; padding:0px 2px 0px 2px;'}
])

# Highlight retirement years in bold
s.highlight_between(subset=['year'], left=st.session_state.retirement_year, props='font-weight:bold')

# Additional bells & whistles
if True:
    # https://pandas.pydata.org/docs/user_guide/style.html#Background-Gradient-and-Text-Gradient
    # https://matplotlib.org/stable/tutorials/colors/colormaps.html
    s.background_gradient(cmap='Wistia', text_color_threshold=0, subset=['income_gross_1', 'income_gross_2'], vmin=0, vmax=100000)
    s.background_gradient(cmap='Oranges', subset=['income_tax_rate_1', 'income_tax_rate_2', 'cgt_rate'], vmin=0, vmax=1)
    s.background_gradient(cmap='magma', subset=['lsa_ratio_1', 'lsa_ratio_2'], vmin=0, vmax=1)

    # https://pandas.pydata.org/docs/user_guide/style.html#Bar-charts
    #s.bar(subset=['lsa_ratio_1', 'lsa_ratio_2'], align='left', color='#d65f5f', vmin=0, vmax=1)

# Charts
if True:
    import altair as alt

    if st.session_state.lump_sum:
        st.subheader("Lump Sum")
        st.warning("This might be a crude estimation because Annual Allowance limits are not precisely known/modelled.", icon="⚠️")
        col1, col2 = st.columns(2)
        with col1:
            st.metric(label="SIPP 1", value=f"£{result.ls_sipp_1:,.0f}")
            st.metric(label="SIPP 2", value=f"£{result.ls_sipp_2:,.0f}")
            st.metric(label="ISA",    value=f"£{result.ls_isa:,.0f}")
            st.metric(label="GIA",    value=f"£{result.ls_gia:,.0f}")
        with col2:
            # https://altair-viz.github.io/gallery/pie_chart.html
            source = pd.DataFrame({"Asset": ["SIPP1", "SIPP2", "ISA", "GIA"], "Value": [
                result.ls_sipp_1, result.ls_sipp_2, result.ls_isa, result.ls_gia
            ]})

            chart = alt.Chart(source).mark_arc().encode(
                theta=alt.Theta(field="Value", type="quantitative"),
                color=alt.Color(field="Asset", type="nominal"),
            )
            st.altair_chart(chart, width='stretch')

    st.subheader("Time series")

    cdf = pd.DataFrame()

    # https://stackoverflow.com/questions/46658232/pandas-convert-column-with-year-integer-to-datetime
    cdf['Year'] = pd.to_datetime(df['year'], format='%Y')

    if st.session_state.joint:
        cdf['SIPP1'] = df['sipp_uf_1'] + df['sipp_df_1']
        cdf['SIPP2'] = df['sipp_uf_2'] + df['sipp_df_2']
    else:
        cdf['SIPP '] = df['sipp_uf_1'] + df['sipp_df_1']
    cdf['ISA'] = df['isa']
    cdf['GIA'] = df['gia']

    # https://altair-viz.github.io/user_guide/data.html#converting-with-pandas
    cdf = cdf.melt('Year', var_name='Asset', value_name='Value')

    # https://altair-viz.github.io/user_guide/generated/core/altair.Legend.html
    # https://stackoverflow.com/questions/68624885/position-altair-legend-top-center
    legend = alt.Legend(
        orient='top-right',
        #legendX=130, legendY=-40,
        #direction='horizontal',
        #titleAnchor='middle'
    )

    yScale = alt.Scale(domainMin=0)
    yAxis = alt.Axis(format=',.0f', title=None)

    chart = (
        alt.Chart(cdf, title='Asset allocation')
        .mark_area()
        .encode(
            alt.X("Year:T", axis=alt.Axis(format="%Y", domain=False, tickSize=0)),
            alt.Y("Value:Q", stack="zero", scale=yScale, axis=yAxis),
            alt.Color("Asset:N", legend=legend),
        )
    )
    st.altair_chart(chart, width='stretch')

    cdf = pd.DataFrame()

    # https://stackoverflow.com/questions/46658232/pandas-convert-column-with-year-integer-to-datetime
    cdf['Year'] = pd.to_datetime(df['year'], format='%Y')

    if st.session_state.joint:
        cdf['Income Tax 1'] = df['income_tax_1']
        cdf['Income Tax 2'] = df['income_tax_2']
    else:
        cdf['Income Tax'] = df['income_tax_1']
    cdf['Capital Gains Tax'] = df['cgt']

    cdf = cdf.melt('Year', var_name='Tax', value_name='Value')

    chart2 = (
        alt.Chart(cdf, title='Taxes')
        .mark_area()
        .encode(
            alt.X("Year:T", axis=alt.Axis(format="%Y", tickSize=0)),
            alt.Y("Value:Q", stack="zero", scale=yScale, axis=yAxis),
            alt.Color("Tax:N", legend=legend),
        )
    )
    st.altair_chart(chart2, width='stretch')

st.subheader("Plan")

st.info(f"""- The _Personal Allowance_ and the _Higher Rate Threshold_ have been adjusted down to £{uk.income_tax_threshold_20:,.0f} and £{uk.income_tax_threshold_40:,.0f} respectively, to reflect the fact that these thresholds [will remain the same in nominal terms until 2031](https://www.gov.uk/government/publications/budget-2025-document/budget-2025-html#taxation-of-income-from-assets#asking-everyone-to-contribute), therefore shrinking in _real_ terms.
- The ISA allowance is progressively adjusted down until 2030 to reflect the fact that [this limit will be frozen in nominal terms until 2030](https://www.gov.uk/government/publications/autumn-budget-2024/autumn-budget-2024-html#:~:text=Individual%20Savings%20Accounts%2C%20Lifetime%20ISA%2C%20Junior%20ISA%20and%20Child%20Trust%20Fund%20Allowance%20%E2%80%93%20Annual%20subscription%20limits%20will%20remain%20at%20%C2%A320%2C000%20for%20ISAs%2C%20%C2%A34%2C000%20for%20Lifetime%20ISAs%20and%20%C2%A39%2C000%20for%20Junior%20ISAs%20and%20Child%20Trust%20Funds%20until%205%20April%202030).
""", icon="ℹ️")

with st.expander("Abbreviations..."):
    st.markdown('''
* **1**: You
* **2**: Your partner
* **A**: Annuities, including State Pension and Defined Benefit Pension Schemes.
* **UF**: Uncrystalized Funds
* **DF**: Drawdown Funds (for example, _flexi-access drawdown_)
* **LSA**: [Lump Sum Allowance](https://www.gov.uk/tax-on-your-private-pension/lump-sum-allowance) (25% of the old LTA)
* **GIA**: General Investment Account
* **GI**: Gross Income
* **NI**: Net Income
* **TFC**: Tax Free Cash
* **\u0394**: Cash flow, that is, cash going in or out of the pot; excluding internal growth.
* **IT**: Income Tax
* **CGT**: Capital Gains Tax
''')

# https://github.com/streamlit/streamlit/issues/4830#issuecomment-1147878371
st.markdown(s.to_html(table_uuid="table_1"), unsafe_allow_html=True)

common.analytics_html()
