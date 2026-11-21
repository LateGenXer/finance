#
# Copyright (c) 2026 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import os.path

import pytest

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    pytest.skip("No Streamlit; skipping.", allow_module_level=True)


default_timeout = 30

data_dir = os.path.join(os.path.dirname(__file__), 'data')


def run_page(page:str|None=None) -> AppTest:
    at = AppTest.from_file("Home.py", default_timeout=default_timeout)
    if page is not None:
        at.switch_page(page)
    at.run()
    assert not at.exception
    return at


def test_home() -> None:
    at = run_page()
    assert at.title[0].value == "LateGenXer's financial tools."


def test_disclaimer() -> None:
    at = run_page('pages/9_Disclaimer.py')
    assert at.title[0].value == 'Disclaimer'


def test_accrued_income_default() -> None:
    at = run_page('pages/4_Accrued_Income_Calculator.py')
    assert 'TG24' in at.markdown[-1].value


def test_accrued_income_transactions() -> None:
    at = run_page('pages/4_Accrued_Income_Calculator.py')
    transactions = open(os.path.join(data_dir, 'accrued_income', 'saim4130-example1.csv'), 'rt').read()
    at.text_area(key='transactions').set_value(transactions)
    at.run()
    assert not at.exception


@pytest.mark.parametrize('escalation', ['Level', '3%', 'Inflation-linked'])
def test_annuity_valuator(escalation:str) -> None:
    at = run_page('pages/5_Annuity_Valuator.py')
    at.radio(key='escalation').set_value(escalation)
    at.number_input(key='age').set_value(70)
    at.run()
    assert not at.exception
    assert len(at.metric) == 2
