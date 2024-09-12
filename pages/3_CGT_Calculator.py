#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import datetime
import io
import os.path

import streamlit as st

import analytics

from cgtcalc import calculate, date_to_tax_year, str_to_tax_year, HtmlReport, TextReport


# https://docs.streamlit.io/library/api-reference/utilities/st.set_page_config
st.set_page_config(
    page_title="CGT Calculator",
    page_icon=":pound banknote:",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        "Get help": "https://github.com/LateGenXer/finance/discussions",
        "Report a Bug": "https://github.com/LateGenXer/finance/issues",
        "About": """Capital Gains Tax Calculator

https://github.com/LateGenXer/finance/blob/main/cgtcalc.md

Copyright (c) 2024 LateGenXer.

""",
    }
)


st.title('Capital Gains Tax Calculator')


st.markdown('''This is a UK Capital Gains Tax calculator.
Please read more [here](https://github.com/LateGenXer/finance/blob/main/cgtcalc.md).
''')


#
# Parameters
#

with st.sidebar:
    st.header("Parameters")

    _, current_tax_year_end = date_to_tax_year(datetime.date.today())

    options = ['All']
    for y in range(current_tax_year_end, 2008, -1):
        options.append(f'{y - 1}/{y}')
    tax_year = st.selectbox('Tax year', options, key="tax_year")

    rounding = st.checkbox("Rounding", value=True, key="rounding", help="Round to whole pounds.")

    format_ = st.selectbox('Format', ['HTML', 'Text'], key='format')

#
# Inputs
#

st.html("<style>textarea { font-family: monospace !important; font-size: 14px !important; }</style>")

placeholder_filename = os.path.join(os.path.dirname(__file__), '..', 'tests', 'data', 'cgtcalc', 'hmrc-hs284-example3.tsv')
transactions = st.text_area(
    label="Transactions",
    key='transactions',
    height = 14*20,
    placeholder=open(placeholder_filename, 'rt').read(),
    help='[Format specification](https://github.com/LateGenXer/finance/blob/main/cgtcalc.md#format)'
)


#
# Calculation
#

if transactions:
    stream = io.StringIO(transactions)
else:
    stream = open(placeholder_filename, 'rt')

result = calculate(stream, rounding=rounding)
for warning in result.warnings:
    st.warning(warning, icon="⚠️")

if tax_year != 'All':
    result.filter_tax_year(str_to_tax_year(tax_year))

with st.container(border=True):
    if format_ == 'HTML':
        html = io.StringIO()
        report = HtmlReport(html)
        result.write(report)
        st.components.v1.html(html.getvalue(), height=768, scrolling=True)
    else:
        assert format_ == 'Text'
        text = io.StringIO()
        report = TextReport(text)
        result.write(report)
        st.markdown('```\n' + text.getvalue() + '```\n')


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

st.html(analytics.html)
