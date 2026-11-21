#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import pytest

import annuities

from data import mortality, boe


@pytest.fixture(scope='module', params=('unisex', 'male', 'female'))
def table(request):
    gender = request.param
    if gender == 'unisex':
        return mortality.get_cmi_table()
    else:
        return mortality.get_ons_table('cohort', gender)


@pytest.fixture(scope='module', params=('Real', 'Nominal'))
def yield_curve(request):
    measure = request.param
    return boe.YieldCurve(measure)


def test_annuity_rate(yield_curve, table):
    ar = annuities.annuity_rate(66, yield_curve, table)
    assert 0.0 < ar < 1.0


def test_escalation_level() -> None:
    assert annuities.escalation_level(0) == 1.0
    assert annuities.escalation_level(10) == 1.0


def test_escalation_fixed() -> None:
    escalation = annuities.escalation_fixed(.03)
    assert escalation(0) == 1.0
    assert escalation(1) == pytest.approx(1.03)
    assert escalation(10) == pytest.approx(1.03**10)


def test_escalation_deferred() -> None:
    escalation = annuities.escalation_deferred(5)(annuities.escalation_fixed(.03))
    assert escalation(0) == 0.0
    assert escalation(4) == 0.0
    assert escalation(5) == 1.0
    assert escalation(6) == pytest.approx(1.03)
    assert escalation(15) == pytest.approx(1.03**10)


def test_present_value_escalation(yield_curve, table):
    pv_level = annuities.present_value(66, yield_curve, table)
    pv_fixed = annuities.present_value(66, yield_curve, table, escalation=annuities.escalation_fixed(.03))
    assert 0.0 < pv_level < pv_fixed
