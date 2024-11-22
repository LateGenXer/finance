#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import pytest

import pandas as pd

from data import boe


def test_load():
    boe.load()


@pytest.mark.parametrize('measure', ('Nominal', 'Real', 'Inflation'))
def test_yield_curves(measure):
    yield_curve = boe.YieldCurve(measure)

    ds = yield_curve.series
    assert isinstance(ds, pd.Series)

    for i in range(len(ds.index)):
        assert ds.index[i] == 0.5 * (i + 1)

    assert not ds.isna().any()
