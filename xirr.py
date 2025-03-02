#
# Copyright (c) 2023-2025 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import datetime
import math

from collections.abc import Callable, Sequence
from typing import SupportsFloat

import numpy as np

import scipy.optimize  # type: ignore[import-untyped]


__all__ = [
    'xnpv',
    'xirr',
]


def _periods(dates:Sequence[datetime.date], period:float) -> np.ndarray:
    dates_array = np.array(dates, dtype=np.datetime64)
    assert (dates_array[:-1] <= dates_array[1:]).all()
    periods = (dates_array - dates_array[0]) / np.timedelta64(1, 'D')
    periods /= period
    return periods


def xnpv(rate:float, values:Sequence[SupportsFloat], dates:Sequence[datetime.date], period:float=365.25) -> float:
    '''Equivalent of Excel's XNPV function.'''
    values_array = np.asarray(values, dtype=np.float64)
    periods = _periods(dates, period)
    discount_factor = 1.0 / (1.0 + rate)
    return np.dot(values_array, discount_factor ** periods)


def xirr(values:Sequence[SupportsFloat], dates:Sequence[datetime.date], guess:float=0.1, secant:bool=False, period:float=365.25) -> float:
    '''Equivalent of Excel's XIRR function.'''

    values_array = np.asarray(values, dtype=np.float64)
    assert values_array.min() <= 0.0
    assert values_array.max() >= 0.0

    periods = _periods(dates, period)

    def fn(df:float) -> float:
        if df <= 0.0:
            return -math.inf
        return np.dot(values_array, df ** periods)

    fn_prime:Callable[[float], float]|None
    if secant:
        fn_prime = None
    else:
        values_periods = values_array * periods
        periods_minus_one = periods - 1.0
        def fn_prime(df:float) -> float:
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
