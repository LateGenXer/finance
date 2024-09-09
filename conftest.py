#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import os.path
import sys
import pytest


here = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(here, 'rtp'))
sys.path.insert(0, here)


pytest.register_assert_rewrite("gilts")


def pytest_addoption(parser):
    parser.addoption("--show-browser", action="store_true", default=False, help="Show browser")
    parser.addoption("--show-plots", action="store_true", default=False, help="Show plots")
    parser.addoption("--production", action="store_true")


@pytest.fixture(scope="session")
def show_browser(request):
    return request.config.getoption("--show-browser")


@pytest.fixture(scope="session")
def show_plots(request):
    return request.config.getoption("--show-plots")


@pytest.fixture(scope="session")
def production(request):
    return request.config.getoption("--production")
