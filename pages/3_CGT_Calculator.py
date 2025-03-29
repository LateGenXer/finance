#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import datetime
import io
import os.path

import streamlit as st

import common

from typing import TextIO
from tax.uk import TaxYear
from cgtcalc import calculate
from report import Report, HtmlReport, TextReport


common.set_page_config(
    page_title="CGT Calculator",
    layout="wide",
)


st.title('Capital Gains Calculator')


st.markdown('''This is a UK Capital Gains calculator.
Please read more [here](https://github.com/LateGenXer/finance/blob/main/cgtcalc.md).
''')


#
# Parameters
#

with st.sidebar:
    st.header("Parameters")

    _, current_tax_year_end = TaxYear.from_date(datetime.date.today())

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

stream:TextIO
if transactions:
    stream = io.StringIO(transactions)
else:
    stream = open(placeholder_filename, 'rt')

result = calculate(stream, rounding=rounding)
for warning in result.warnings:
    st.warning(warning, icon="⚠️")

if tax_year != 'All':
    result.filter_tax_year(TaxYear.from_string(tax_year))

report:Report
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


common.analytics_html()
