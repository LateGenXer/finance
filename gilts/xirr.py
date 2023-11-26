#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import math
import datetime

import numpy as np

import scipy.optimize


__all__ = [
    'xnpv',
    'xirr',
]


def _periods(dates):
    d0 = dates[0]
    assert isinstance(d0, datetime.date)
    dm = min(dates)
    if d0 != dm:
        raise ValueError(f'First date ({d0}) is not earliest date ({dm}).')
    return np.array([(d0 - di).days / 365.0 for di in dates], dtype=np.float64)


def _npv(discount_factor, values, periods):
    if discount_factor <= 0.0:
        return math.inf
    return np.sum(values * discount_factor ** periods)


def _npv_prime(discount_factor, values, periods):
    '''Derivative of _npv in respect to the discount_factor.'''
    if discount_factor <= 0.0:
        return math.inf
    return np.sum(values * periods * discount_factor ** (periods - 1))


def xnpv(rate, values, dates):
    '''Equivalent of Excel's XNPV function.'''
    values = np.asarray(values, dtype=np.float64)
    periods = _periods(dates)
    return _npv(1.0 + rate, values, periods)


def xirr(values, dates, guess=0.1, secant=False):
    '''Equivalent of Excel's XIRR function.'''

    assert min(values) <= 0.0
    assert max(values) >= 0.0

    values = np.asarray(values, dtype=np.float64)
    periods = _periods(dates)

    fn       = lambda r: _npv      (1.0 + r, values, periods)

    if secant:
        fn_prime = None
    else:
        fn_prime = lambda r: _npv_prime(1.0 + r, values, periods)

    try:
        return scipy.optimize.newton(fn, guess, fn_prime)
    except RuntimeError:
        # https://stackoverflow.com/a/33260133 suggests using brentq but it
        # seems errors can be avoided by passing the exact derivative to the
        # newton method.
        raise
