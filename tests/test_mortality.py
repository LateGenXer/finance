#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import pytest

from pytest import approx

from data import mortality


@pytest.mark.parametrize('gender', ['male', 'female'])
@pytest.mark.parametrize('basis', ['period', 'cohort'])
def test_get_ons_table(basis, gender):
    table = mortality.get_ons_table(basis, gender)
    assert isinstance(table, mortality.Table)


def test_get_cmi_table():
    table = mortality.get_cmi_table()
    assert isinstance(table, mortality.Table)


@pytest.fixture(scope='module')
def cmi_table():
    return mortality.get_cmi_table()


def test_mortality_max_age(cmi_table):
    assert cmi_table.mortality(2024, 999) == 1.0


def test_life_expectancy(cmi_table):
    mp = mortality.get_ons_table('period', 'male')
    fp = mortality.get_ons_table('period', 'female')

    mc = mortality.get_ons_table('cohort', 'male')
    fc = mortality.get_ons_table('cohort', 'female')
    uc = cmi_table

    year = 2024
    age = 65

    le_mp = mp.life_expectancy(year, 65)
    assert age + le_mp == approx(85, abs=2)

    le_fp = fp.life_expectancy(year, 65)
    assert le_mp < le_fp

    le_mc = mc.life_expectancy(year, 65)
    le_fc = fc.life_expectancy(year, 65)
    le_uc = uc.life_expectancy(year, 65)

    assert le_mc > le_mp
    assert le_fc > le_fp

    assert le_mc < le_fc

    assert le_mc < le_uc
    assert le_fc < le_uc
