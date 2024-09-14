#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


from pytest import approx

from data import mortality


def test_load_ons_tables():
    mortality._load_ons_tables()


def test_load_cmi_table():
    mortality._load_cmi_table()


def test_mortality_max_age():
    assert mortality.mortality(2024, 999) == 1.0


def test_life_expectancy():
    year = 2024
    age = 65

    le_mp = mortality.life_expectancy(year, 65, 'male', 'period')
    assert age + le_mp == approx(85, abs=2)

    le_fp = mortality.life_expectancy(year, 65, 'female', 'period')
    assert le_mp < le_fp

    le_mc = mortality.life_expectancy(year, 65, 'male',   'cohort')
    le_fc = mortality.life_expectancy(year, 65, 'female', 'cohort')
    le_uc = mortality.life_expectancy(year, 65, 'unisex', 'cohort')

    assert le_mc > le_mp
    assert le_fc > le_fp

    assert le_mc < le_fc

    assert le_mc < le_uc
    assert le_fc < le_uc
