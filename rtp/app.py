#!/usr/bin/env python3
#
# Copyright (c) 2023 LateGenXer.  All rights reserved
#


import datetime
import os

import streamlit as st
import pandas as pd
import numpy as np

from model import model, column_headers, dataframe


st.set_page_config(layout="wide")

st.title('Retirement Tax Planner')

# Allow to override initial state on development enviroments
try:
    from devel import state as devel_state
except ImportError:
    devel = False
else:
    devel = True
    with st.expander("Devel..."):
        st.write(devel_state)
        if 'devel_state' not in st.session_state:
            st.session_state.update(devel_state)
            st.session_state.devel_state = True

# Default state
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
    "sipp_contrib_1": 0,
    "sipp_contrib_2": 3600,
    "sipp_extra_contrib": False,
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
}
for key, value in default_state.items():
    st.session_state.setdefault(key, value)

#
# About
#

@st.cache_data(ttl=24*3600)
def about():
    return open(os.path.join(os.path.dirname(__file__), 'README.md'), 'rt').read()

with st.expander("About..."):
    st.markdown(about())

#
# Parameters
#

st.header('Parameters')

st.warning('Inputs are not stored permanently and will not persist across page reloads!', icon="⚠️")

st.checkbox("Joint calculation", key="joint")
with st.form(key='my_form'):

    tab1, tab2 = st.tabs(["Basic", "Advanced"])

    with tab1:

        col1, col2, col3 = st.columns(3)

        state_pension_years_help = "If in doubt [check on your National Insurance record](https://www.gov.uk/check-state-pension) how many years of full contributions you have, and add how many more years you plan to work or do voluntary contributions."

        marginal_income_tax_help = "Used to estimate income tax from withdrawing more than the Tax Free Cash from a SIPP before retirement."

        with col1:
            st.subheader('You')
            st.number_input('Year of birth:', min_value=1920, max_value=2080, step=1, key='dob_1')
            st.number_input('State pension qualifying years at retirement:', min_value=0, max_value=35, step=1, key='state_pension_years_1', help=state_pension_years_help)
            st.number_input('SIPP value:', min_value=0, step=1, key='sipp_1')
            st.number_input('SIPP yearly _gross_ contribution:', min_value=0, max_value=40000, step=1, key='sipp_contrib_1', help="Until retirement")
            st.select_slider("Marginal income tax rate:", options=(0.00, 0.20, 0.40, 0.45), format_func='{:.0%}'.format, key="marginal_income_tax_1", help=marginal_income_tax_help)

        single = not st.session_state.joint
        with col2:
            st.subheader('Partner')
            st.number_input('Year of birth:', min_value=1920, max_value=2080, step=1, key='dob_2', disabled=single)
            st.number_input('State pension qualifying years at retirement:', min_value=0, max_value=35, step=1, key='state_pension_years_2', disabled=single, help=state_pension_years_help)
            st.number_input('SIPP value:', min_value=0, step=1, key='sipp_2', disabled=single)
            st.number_input('SIPP yearly _gross_ contribution:', min_value=0, max_value=40000, step=1, key='sipp_contrib_2', help="Until retirement", disabled=single)
            st.select_slider("Marginal income tax rate:", options=(0.00, 0.20, 0.40, 0.45), format_func='{:.0%}'.format, key="marginal_income_tax_2", disabled=single, help=marginal_income_tax_help)

        with col3:
            st.subheader('Shared')
            st.number_input('Retirement year:', min_value=2020, max_value=2080, step=1, key='retirement_year')
            st.number_input('Retirement income (0 for maximum):', min_value=0, step=1000, key='retirement_income_net', help='Go to https://www.retirementlivingstandards.org.uk/ for guidance.')
            st.number_input('ISAs value:', min_value=0, step=1, key='isa')
            st.number_input('GIAs value:', min_value=0, step=1, key='gia')
            st.number_input('ISAs/GIAs yearly savings:', min_value=0, step=1, key='misc_contrib', help="Until retirement.  The optimization will automatically maximize the ISA allowance.")

    with tab2:
        col1, col2 = st.columns(2)

        with col1:
            max_rate = 10.0
            growth_rate_format = '%.1f%%'
            st.slider("Inflation rate:", min_value=0.0, max_value=max_rate, step=0.5, format=growth_rate_format, key="inflation_rate")
            st.slider("Your SIPP nominal growth rate:", min_value=0.0, max_value=max_rate, step=0.5, format=growth_rate_format, key="sipp_growth_rate_1")
            st.slider("Partner's SIPP nominal growth rate:", min_value=0.0, max_value=max_rate, step=0.5, format=growth_rate_format, key="sipp_growth_rate_2")
            st.slider("ISAs nominal growth rate:", min_value=0.0, max_value=max_rate, step=0.5, format=growth_rate_format, key="isa_growth_rate")
            st.slider("GIAs nominal growth rate:", min_value=0.0, max_value=max_rate, step=0.5, format=growth_rate_format, key="gia_growth_rate")

        with col2:

            st.selectbox("Retirement country:", options=("UK", "PT"), index=0, key='retirement_country',
                help="Country to be tax resident from _retirement year_. " +
                "Values still always in pounds.  Differences in cost of life not considered."
            )

    submitted = st.form_submit_button(label='Update', type='primary')


#
# Results
#

st.header('Results')

params = dict(st.session_state)

perc_xform = lambda x: x*.01
state_xforms =  {
    'inflation_rate': perc_xform,
    'sipp_growth_rate_1': perc_xform,
    'sipp_growth_rate_2': perc_xform,
    'isa_growth_rate': perc_xform,
    'gia_growth_rate': perc_xform,
}
for key, xform in state_xforms.items():
    params[key] = xform(st.session_state[key])

params['present_year'] = datetime.date.today().year
params['pt'] = st.session_state.retirement_country == 'PT'

if devel:
    with st.expander("Parameters"):
        st.write(params)

# https://docs.streamlit.io/library/advanced-features/caching
@st.cache_data(ttl=3600, max_entries=1024)
def run(params):
    return model(**params)

result = run(params)
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
    'isa_delta': delta_format,
    'gia_delta': delta_format,
    'income_surplus': delta_format,
    'lta_ratio_1':  perc_format,
    'lta_ratio_2':  perc_format,
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
#s.set_properties(**{'font-size': '8pt'})
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
    s.background_gradient(cmap='magma', subset=['lta_ratio_1', 'lta_ratio_2'], vmin=0, vmax=1)

    # https://pandas.pydata.org/docs/user_guide/style.html#Bar-charts
    #s.bar(subset=['lta_ratio_1', 'lta_ratio_2'], align='left', color='#d65f5f', vmin=0, vmax=1)

# Charts
if True:
    import altair as alt

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
    if False:
        # https://docs.streamlit.io/library/api-reference/charts/st.altair_chart#annotating-charts
        adf = pd.DataFrame()
        adf['Year'] = pd.to_datetime(df['year'], format='%Y')
        adf['LAC'] = df['lac']
        adf['Event'] = 'LAC'
        adf = adf[adf['LAC'] > 80]
        adf['Y'] = 0
        annotation_layer = (
            alt.Chart(adf)
            .mark_text(size=20, text="⬇", dx=-8, dy=-10, align="left")
            .encode(
                x="Year:T",
                y=alt.Y("Y:Q"),
                tooltip=["Event"],
            )
        )
        chart = chart + annotation_layer
    st.altair_chart(chart, use_container_width=True)

    cdf = pd.DataFrame()

    # https://stackoverflow.com/questions/46658232/pandas-convert-column-with-year-integer-to-datetime
    cdf['Year'] = pd.to_datetime(df['year'], format='%Y')

    if st.session_state.joint:
        cdf['Income Tax 1'] = df['income_tax_1']
        cdf['Income Tax 2'] = df['income_tax_2']
    else:
        cdf['Income Tax'] = df['income_tax_1']
    cdf['Capital Gains Tax'] = df['cgt']
    cdf['Lifetime Allowance Charge'] = df['lac']

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
    st.altair_chart(chart2, use_container_width=True)

st.subheader("Plan")

with st.expander("Abbreviations..."):
    st.markdown('''
* **1**: You
* **2**: Your partner
* **SP**: State Pension
* **UF**: Uncrystalized Funds
* **DF**: Drawdown Funds (for example, _flexi-access drawdown_)
* **GIA**: General Investment Account
* **GI**: Gross Income
* **NI**: Net Income
* **Error**: Error relative to target income; should be zero, unless there are modelling errors.
* **LTA**: Lifetime Allowance
* **\u0394**: Cash flow, that is, cash going in or out of the pot; excluding growth and tax charges.
* **IT**: Income Tax
* **CGT**: Capital Gains Tax
* **LAC**: Lifetime Allowance Charge
''')

# https://github.com/streamlit/streamlit/issues/4830#issuecomment-1147878371
st.markdown(s.to_html(table_uuid="table_1"), unsafe_allow_html=True)
