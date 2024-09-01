#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import io
import os.path


import streamlit as st
import pandas as pd


# https://docs.streamlit.io/library/api-reference/utilities/st.set_page_config
st.set_page_config(
    page_title="CGT Calculator",
    page_icon=":pound banknote:",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        "Get help": "https://github.com/LateGenXer/finance/discussions",
        "Report a Bug": "https://github.com/LateGenXer/finance/issues",
        "About": """Capital Gain Tax Calculator

https://github.com/LateGenXer/finance/blob/main/cgtcalc.md

Copyright (c) 2024 LateGenXer.

""",
    }
)


st.title('Capital Gain Tax Calculator')


st.markdown('''This is a UK Capital Gains Tax calculator.
Please read more [here](https://github.com/LateGenXer/finance/blob/main/cgtcalc.md).
''')

from cgtcalc import calculate


#
# Input
#

st.header('Input')

placeholder_filename = os.path.join(os.path.dirname(__file__), '..', 'tests', 'data', 'cgtcalc', 'hmrc-hs284-example3.tsv')
transactions = st.text_area(
    label="Transactions",
    height = 480,
    placeholder=open(placeholder_filename, 'rt').read(),
    help='[Format specification](https://github.com/LateGenXer/finance/blob/main/cgtcalc.md#format)'
)


#
# Calculation
#

st.header('Output')


if transactions:
    stream = io.StringIO(transactions)
else:
    stream = open(placeholder_filename, 'rt')

result = calculate(stream)
for warning in result.warnings:
    st.warning(warning, icon="⚠️")

calculation = io.StringIO()
calculation.write('```\n')
result.write(calculation)
calculation.write('```\n')

st.markdown(calculation.getvalue())


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
