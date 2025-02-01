#
# Copyright (c) 2024-2025 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import pytest

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    pytest.skip("No Streamlit; skipping.", allow_module_level=True)

import environ


default_timeout = 30


@pytest.fixture(scope="function")
def at():
    at = AppTest.from_file("Home.py", default_timeout=default_timeout)
    at.switch_page('pages/6_Net_Yields.py')
    at.run()
    assert not at.exception
    return at


def test_run(at):
    # Ensure no state corruption
    at.run()
    assert not at.exception


@pytest.mark.parametrize("value", ['Conventional', 'Index-linked', 'Both'])
def test_gilts_type(at, value):
    gilts_type = at.radio(key="gilts_type")
    gilts_type.set_value(value)
    at.run()
    assert not at.exception


def test_mortgage(at):
    mortgage_rate = at.number_input(key="mortgage_rate")
    mortgage_rate.set_value(5.0)
    at.run()
    assert not at.exception


@pytest.mark.skipif(environ.ci, reason="frequent timeouts")
def test_latest_gilt_prices(at):
    at.query_params['latest'] = '1'
    at.run(timeout=60)
    assert not at.exception
