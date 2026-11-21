import json
import os
import sys
import types

from decimal import Decimal

import pytest

import data.hmrc

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    pytest.skip("No Streamlit; skipping.", allow_module_level=True)


@pytest.fixture(scope="function")
def at():
    at = AppTest.from_file("Home.py", default_timeout=30)
    at.switch_page('pages/2_Retirement_Tax_Planner.py')
    at.run()
    return at


def test_run(at):
    # Ensure no state corruption
    at.run()
    assert not at.exception


@pytest.fixture(scope="function")
def submit(at):
    assert len(at.button) == 1
    submit = at.button[0]
    return submit


def test_joint(at):
    # Toggle Joint checkbox
    joint = at.checkbox(key="joint")
    joint.set_value(not joint.value)
    at.run()
    assert not at.exception


def test_lump_sum(at, submit):
    joint = at.checkbox(key="joint")
    joint.set_value(True)

    # Set a lump sum
    lump_sum = at.number_input(key="lump_sum")
    assert lump_sum.value == 0
    lump_sum.set_value(1000)
    submit.click()
    at.run()
    assert not at.exception


def test_gia_gains_error(at, submit):
    assert len(at.error) == 0
    at.number_input(key="gia").set_value(1000)
    at.number_input(key="gia_gains").set_value(2000)
    submit.click()
    at.run()
    assert not at.exception
    assert len(at.error) == 1


def test_error(at, submit):
    assert len(at.error) == 0
    joint = at.checkbox(key="joint")
    joint.set_value(False)
    retirement_income_net = at.number_input(key="retirement_income_net")
    retirement_income_net.set_value(1000000)
    submit.click()
    at.run()
    assert not at.exception
    assert len(at.error) == 1



@pytest.mark.parametrize("country", ['PT', 'JP'])
def test_country(at, submit, monkeypatch, country):
    # Avoid live exchange rate fetches
    exchange_rates = {'EUR': Decimal('1.15'), 'JPY': Decimal('190.0')}
    def current_exchange_rates(currencies=None):
        return {currency: exchange_rates[currency] for currency in currencies or exchange_rates}
    monkeypatch.setattr(data.hmrc, 'current_exchange_rates', current_exchange_rates)
    at.selectbox(key="retirement_country").set_value(country)
    submit.click()
    at.run()
    assert not at.exception
    assert len(at.error) == 0


def warnings(at, text):
    return [w.value for w in at.warning if text in w.value]


def test_db_pension(at, submit):
    at.text_input(key="db_payments_1").set_value("10000")
    at.text_input(key="db_ages_1").set_value("67")
    submit.click()
    at.run()
    assert not at.exception
    assert len(at.error) == 0
    assert len(warnings(at, 'Defined Benefit')) == 1


params_path = os.path.join(os.path.dirname(__file__), 'data', 'rtp-params-default.json')


def load_params(**kwargs):
    with open(params_path, 'rt') as f:
        params = json.load(f)
    params.update(kwargs)
    return params


@pytest.mark.parametrize("overrides,warning", [
    pytest.param({}, None, id="ok"),
    pytest.param({'version': 0}, 'Expected parameter file version', id="version"),
    pytest.param({'unknown': 1}, 'Unexpected parameter', id="unexpected"),
])
def test_upload(at, overrides, warning):
    assert at.number_input(key="retirement_year").value == 2045
    params = load_params(retirement_year=2040, **overrides)
    at.file_uploader[0].upload('rtp.json', json.dumps(params).encode('utf-8'), 'application/json')
    at.run()
    assert not at.exception
    assert at.number_input(key="retirement_year").value == 2040
    for text in ('Expected parameter file version', 'Unexpected parameter'):
        assert len(warnings(at, text)) == (text == warning)


def test_upload_once(at, submit):
    # An uploaded file must not override subsequent edits on re-runs
    params = load_params(retirement_year=2040)
    at.file_uploader[0].upload('rtp.json', json.dumps(params).encode('utf-8'), 'application/json')
    at.run()
    assert at.number_input(key="retirement_year").value == 2040
    at.number_input(key="retirement_year").set_value(2050)
    submit.click()
    at.run()
    assert not at.exception
    assert at.number_input(key="retirement_year").value == 2050


def devel_apptest():
    at = AppTest.from_file("Home.py", default_timeout=30)
    at.switch_page('pages/2_Retirement_Tax_Planner.py')
    at.run()
    assert not at.exception
    return at


def test_devel_argv(monkeypatch):
    monkeypatch.delenv('PYTEST_CURRENT_TEST')
    monkeypatch.setattr(sys, 'argv', ['streamlit', params_path])
    at = devel_apptest()
    assert 'Parameters' in [e.label for e in at.expander]


def test_devel_module(monkeypatch):
    # Never import the developer's local (git-ignored) rtp/devel.py
    state = load_params(retirement_year=2040)
    del state['version']
    monkeypatch.delenv('PYTEST_CURRENT_TEST')
    monkeypatch.setattr(sys, 'argv', ['streamlit'])
    monkeypatch.setitem(sys.modules, 'rtp.devel', types.SimpleNamespace(state=state))
    at = devel_apptest()
    labels = [e.label for e in at.expander]
    assert 'Devel...' in labels
    assert 'Parameters' in labels
    assert at.number_input(key="retirement_year").value == 2040


def test_devel_no_module(monkeypatch):
    monkeypatch.delenv('PYTEST_CURRENT_TEST')
    monkeypatch.setattr(sys, 'argv', ['streamlit'])
    monkeypatch.setitem(sys.modules, 'rtp.devel', None)  # ImportError
    at = devel_apptest()
    labels = [e.label for e in at.expander]
    assert 'Devel...' not in labels
    assert 'Parameters' not in labels
