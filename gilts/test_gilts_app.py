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


# Avoid slider state corruption due to the formating.
def reset_slider(at, key):
    slider = at.select_slider(key=key)
    slider.set_value(f'{slider.value:.0%}')


def run(at):
    at.run()
    assert not at.exception
    reset_slider(at, 'marginal_income_tax')


def test_run():
    at = AppTest.from_file("app.py", default_timeout=default_timeout)
    run(at)

    # Ensure no state corruption
    run(at)


def test_monthly():
    at = AppTest.from_file("app.py", default_timeout=default_timeout)
    run(at)

    # Toggle Joint checkbox
    frequency = at.radio(key="frequency")
    assert frequency.value == "Yearly"
    frequency.set_value("Monthly")
    run(at)


def test_start_date():
    at = AppTest.from_file("app.py", default_timeout=default_timeout)
    run(at)

    start_date = at.date_input(key="start_date")
    assert start_date.value is None
    today = datetime.datetime.utcnow().date()
    start_date.set_value(today.replace(year=today.year + 10, month=4, day=6))
    run(at)


def test_index_linked():
    at = AppTest.from_file("app.py", default_timeout=default_timeout)
    run(at)

    # Toggle Joint checkbox
    index_linked = at.toggle(key="index_linked")
    index_linked.set_value(not index_linked.value)
    run(at)


def test_experimental_window():
    argv = sys.argv
    try:
        sys.argv = ['app.py', '--experimental']
        at = AppTest.from_file("app.py", default_timeout=default_timeout)
        run(at)

        window = at.slider(key="window")
        window.set_value(2)
        run(at)

    finally:
        sys.argv = argv
