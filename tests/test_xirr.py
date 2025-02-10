#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


from datetime import date

import pytest

from pytest import approx

from xirr import xnpv, xirr


def test_xnpv():
    # https://support.microsoft.com/en-us/office/xnpv-function-1b42bbf6-370f-4532-a0eb-d67c16b664b7
    transactions = [
        (-10000, date(2008,  1,  1)),
        (  2750, date(2008,  3,  1)),
        (  4250, date(2008, 10, 30)),
        (  3250, date(2009,  2, 15)),
        (  2750, date(2009,  4,  1)),
    ]

    values, dates = zip(*transactions)
    npv = xnpv(.09, values, dates, period=365.0)
    assert npv == approx(2086.65, abs=1e-02)


@pytest.mark.parametrize('secant', [False, True])
def test_xirr(secant):
    # https://support.microsoft.com/en-us/office/xirr-function-de1242ec-6477-445b-b11b-a303ad9adc9d
    transactions = [
        (-10000, date(2008,  1,  1)),
        (  2750, date(2008,  3,  1)),
        (  4250, date(2008, 10, 30)),
        (  3250, date(2009,  2, 15)),
        (  2750, date(2009,  4,  1)),
    ]

    values, dates = zip(*transactions)
    irr = xirr(values, dates, 0.1, period=365.0, secant=secant)
    assert irr == approx(0.373362535, abs=5e-09)


def test_xirr_maxiter():
    # This triggers RunTimeError with secant=False, and bad results with secant=True
    transactions = [
        (date(2024, 3, 19), -155.3170362032967),
        (date(2024, 3, 22), 0.098048),
        (date(2024, 3, 22), 156.876965)
    ]
    dates, values = zip(*transactions)
    irr = xirr(values, dates, guess=0.1)
    assert irr == approx(2.64285575, rel=1e-8)
