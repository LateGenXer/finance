#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import pytest


pytest.register_assert_rewrite("gilts")


def pytest_addoption(parser):
    parser.addoption("--show-plots", action="store_true", default=False, help="Show plots")


@pytest.fixture
def show_plots(request):
    return request.config.getoption("--show-plots")
