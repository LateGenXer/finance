#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import math

import pytest

from data import boe


def test_load():
    boe.load()


@pytest.mark.parametrize('measure', ('Nominal', 'Real', 'Inflation'))
def test_yield_curves(measure):
    yield_curve = boe.YieldCurve(measure)
    assert isinstance(yield_curve, boe.Curve)

    assert not math.isnan(yield_curve(0.0))
    assert not math.isnan(yield_curve(100.0))
