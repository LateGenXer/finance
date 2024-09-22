#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import pytest

import annuities

from data import mortality


@pytest.fixture(scope='module', params=('unisex', 'male', 'female'))
def table(request):
    gender = request.param
    if gender == 'unisex':
        return mortality.get_cmi_table()
    else:
        return mortality.get_ons_table('cohort', gender)


@pytest.mark.parametrize('kind', ('Real', 'Nominal'))
def test_annuity_rate(kind, table):
    ar = annuities.annuity_rate(66, kind, table)
    assert 0.0 < ar < 1.0
