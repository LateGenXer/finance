#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import datetime
import sys

import pytest

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    pytest.skip("No Streamlit; skipping.", allow_module_level=True)


default_timeout = 10


@pytest.fixture(scope="function")
def at():
    at = AppTest.from_file("gilts/app.py", default_timeout=default_timeout)
    at.run()
    assert not at.exception
    return at


def test_run(at):
    # Ensure no state corruption
    at.run()
    assert not at.exception


def test_monthly(at):
    # Toggle Joint checkbox
    frequency = at.radio(key="frequency")
    assert frequency.value == "Yearly"
    frequency.set_value("Monthly")
    at.run()
    assert not at.exception


def test_start_date(at):
    start_date = at.date_input(key="start_date")
    assert start_date.value is None
    today = datetime.datetime.utcnow().date()
    start_date.set_value(today.replace(year=today.year + 10, month=4, day=6))
    at.run()
    assert not at.exception


def test_index_linked(at):
    # Toggle Joint checkbox
    index_linked = at.toggle(key="index_linked")
    index_linked.set_value(not index_linked.value)
    at.run()
    assert not at.exception


def test_experimental_window():
    at = AppTest.from_file("gilts/app.py", default_timeout=default_timeout)
    at.query_params['experimental'] = ''
    at.run()
    assert not at.exception

    window = at.slider(key="window")
    window.set_value(2)
    at.run()
    assert not at.exception
