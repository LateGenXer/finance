#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import io
import os.path
import warnings

import streamlit as st

import common

common.set_page_config(
    page_title="Accrued Income Calculator",
    layout="wide",
)

from accrued_income import Calculator
from cgtcalc import TextReport

st.title('Accrued Income Calculator')

st.markdown('''This is an _Accrued Income_ calculator for gilts.
Please read more [here](https://github.com/LateGenXer/finance/blob/main/accrued_income.md).
''')


#
# Inputs
#

st.html("<style>textarea { font-family: monospace !important; font-size: 14px !important; }</style>")

placeholder_filename = os.path.join(os.path.dirname(__file__), '..', 'tests', 'data', 'accrued_income', 'example.csv')
transactions = st.text_area(
    label="Transactions",
    key='transactions',
    height = 14*20,
    placeholder=open(placeholder_filename, 'rt').read(),
    help='[Format specification](https://github.com/LateGenXer/finance/blob/main/accrued_income.md#format)'
)


#
# Calculation
#

if transactions:
    stream = io.StringIO(transactions)
else:
    stream = open(placeholder_filename, 'rt')

calculator = Calculator()

with warnings.catch_warnings(record=True) as caught_warnings:
    warnings.simplefilter("always")
    calculator.parse(stream)
    calculator.process()
    for warning in caught_warnings:
        st.warning(warning.message, icon="⚠️")

text = io.StringIO()
report = TextReport(text)
calculator.report(report)
st.markdown('```\n' + text.getvalue() + '```\n')


common.analytics_html()
