#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


from data import boe


def test_load():
    boe.load()


def test_yield_curves():
    df = boe.yield_curves()

    assert tuple(df.columns) == ('Nominal_Spot', 'Real_Spot', 'Inflation_Spot')

    for i in range(len(df.index)):
        assert df.index[i] == 0.5 * (i + 1)
