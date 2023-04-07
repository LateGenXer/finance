import pytest

from model import *
from uk import *
from uk_test import income_test_cases


@pytest.mark.parametrize("gross_income", income_test_cases)
def test_uk_income_tax_lp(gross_income):
    prob = lp.LpProblem()
    tax = income_tax_lp(prob, gross_income, uk_income_tax_bands)
    prob += tax
    status = prob.solve()
    assert status == lp.LpStatusOptimal
    expected_tax = income_tax(gross_income)
    if gross_income <= income_tax_threshold_45:
        assert lp.value(tax) == pytest.approx(expected_tax)
    else:
        assert lp.value(tax) >= expected_tax


@pytest.mark.parametrize("gross_income", income_test_cases)
def test_uk_income_tax_milp(gross_income):
    prob = lp.LpProblem()
    tax = uk_income_tax_milp(prob, gross_income)
    prob += tax
    status = prob.solve()
    assert status == lp.LpStatusOptimal
    expected_tax = income_tax(gross_income)
    assert lp.value(tax) == pytest.approx(expected_tax)
