#
# Copyright (c) 2023-2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import io
import os.path

import pytest

from cgtcalc import calculate, TaxYear
from report import TextReport

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    pytest.skip("No Streamlit; skipping.", allow_module_level=True)


data_dir = os.path.join(os.path.dirname(__file__), 'data')

default_timeout = 10


@pytest.fixture(scope="function")
def at():
    at = AppTest.from_file("Home.py", default_timeout=default_timeout)
    at.switch_page('pages/3_CGT_Calculator.py')
    at.run()
    assert not at.exception
    return at


def test_run(at):
    # Ensure no state corruption
    at.run()
    assert not at.exception
    print(at.main)


def check_text_report(at, filename, rounding, tax_year=None):
    text = None
    for md in at.markdown:
        assert isinstance(md.value, str)
        # Trailing '\n' is striped
        if md.value.startswith('```\n') and md.value.endswith('```'):
            text = md.value[4: -3]
    assert text

    result = calculate(open(filename, 'rt'), rounding=rounding)

    if tax_year is not None:
        result.filter_tax_year(tax_year)

    expected_text = io.StringIO()
    report = TextReport(expected_text)
    result.write(report)

    assert text == expected_text.getvalue()


def test_calculation(at):
    filename = os.path.join(data_dir, 'cgtcalc', 'quilter-qrg1-example.tsv')

    # Input transactions
    transactions = at.text_area(key='transactions')
    transactions.set_value(open(filename, 'rt').read())
    at.run()
    assert not at.exception

    # Switch to text format
    format_ = at.selectbox(key='format')
    format_.select('Text')
    at.run()
    assert not at.exception
    check_text_report(at, filename, True)

    rounding = at.checkbox(key="rounding")
    assert rounding
    rounding.set_value(not rounding.value)
    at.run()
    assert not at.exception
    check_text_report(at, filename, False)

    # Select a single tax_year
    tax_year = at.selectbox(key='tax_year')
    tax_year.select('2021/2022')
    at.run()
    assert not at.exception
    check_text_report(at, filename, False, TaxYear(2021, 2022))
