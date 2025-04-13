#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import base64
import datetime
import io
import os.path

import streamlit as st

import common

from typing import TextIO
from tax.uk import TaxYear
from cgtcalc import Calculator
from report import Report, HtmlReport, TextReport, PdfReport


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

    format_ = st.selectbox('Format', ['HTML', 'Text', 'PDF'], key='format')

#
# Inputs
#

st.html("<style>textarea { font-family: monospace !important; font-size: 14px !important; }</style>")

placeholder_filename = os.path.join(os.path.dirname(__file__), '..', 'tests', 'data', 'cgtcalc', '2024-2025.tsv')
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

calculator = Calculator(rounding=rounding)
calculator.parse(stream)
result = calculator.calculate()
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
    elif format_ == 'Text':
        text = io.StringIO()
        report = TextReport(text)
        result.write(report)
        st.markdown('```\n' + text.getvalue() + '```\n')
    else:
        assert format_ == 'PDF'
        buffer = io.BytesIO()
        report = PdfReport(buffer)
        result.write(report)
        b64 = base64.b64encode(buffer.getvalue()).decode('ASCII')
        # https://discuss.streamlit.io/t/rendering-pdf-on-ui/13505
        h = f'<embed src="data:application/pdf;base64,{b64}" width="100%" height="768" type="application/pdf" />'
        #h = f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="768" type="application/pdf" />'
        st.markdown(h, unsafe_allow_html=True)


common.analytics_html()
