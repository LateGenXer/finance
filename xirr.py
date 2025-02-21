#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import math

import numpy as np

import scipy.optimize  # type: ignore[import-untyped]


__all__ = [
    'xnpv',
    'xirr',
]


def _periods(dates, period):
    dates = np.array(dates, dtype=np.datetime64)
    assert (dates[:-1] <= dates[1:]).all()
    periods = (dates - dates[0]) / np.timedelta64(1, 'D')
    periods /= period
    return periods


def xnpv(rate, values, dates, period=365.25):
    '''Equivalent of Excel's XNPV function.'''
    values = np.asarray(values, dtype=np.float64)
    periods = _periods(dates, period)
    discount_factor = 1.0 / (1.0 + rate)
    return np.dot(values, discount_factor ** periods)


def xirr(values, dates, guess=0.1, secant=False, period=365.25):
    '''Equivalent of Excel's XIRR function.'''

    assert min(values) <= 0.0
    assert max(values) >= 0.0

    values = np.asarray(values, dtype=np.float64)
    periods = _periods(dates, period)

    def fn(df):
        if df <= 0.0:
            return -math.inf
        return np.dot(values, df ** periods)

    if secant:
        fn_prime = None
    else:
        values_periods = values * periods
        periods_minus_one = periods - 1.0
        def fn_prime(df):
            if df <= 0.0:
                return math.inf
            return np.dot(values_periods, df ** periods_minus_one)

    df_guess = 1.0 / (1.0 + guess)

    try:
        df = scipy.optimize.newton(fn, df_guess, fn_prime)
    except RuntimeError:
        # https://stackoverflow.com/a/33260133
        df = scipy.optimize.brentq(fn, 1e-6, 1e6)

    return 1.0 / df - 1.0
