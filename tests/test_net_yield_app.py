#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import datetime

import pytest

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    pytest.skip("No Streamlit; skipping.", allow_module_level=True)


default_timeout = 10


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


def test_index_linked(at):
    gilts_type = at.radio(key="gilts_type")
    gilts_type.set_value('Index-linked')
    at.run()
    assert not at.exception

    gilts_type.set_value('Both')
    at.run()
    assert not at.exception
