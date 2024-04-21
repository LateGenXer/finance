import pytest

from uk import *


basic_rate_allowance  = income_tax_threshold_40 - income_tax_threshold_20
higher_rate_allowance = income_tax_threshold_45 - income_tax_threshold_40


test_cases = [
    (0, 0),
    (1, 0),
    (income_tax_threshold_20, 0),
    (income_tax_threshold_20 + 1, 0.20),
    (income_tax_threshold_40, basic_rate_allowance*0.20),
    (income_tax_threshold_40 + 1, basic_rate_allowance*0.20 + 0.40),
    (pa_limit, basic_rate_allowance*0.20 + (pa_limit - income_tax_threshold_40) * 0.40),
    (pa_limit + 1, basic_rate_allowance*0.20 + (pa_limit - income_tax_threshold_40) * 0.40 + 0.40*1.5),
    (income_tax_threshold_45, basic_rate_allowance*0.20 + (income_tax_threshold_45 - basic_rate_allowance) * 0.40),
    (income_tax_threshold_45 + 1, basic_rate_allowance*0.20 + (income_tax_threshold_45 - basic_rate_allowance) * 0.40 + 0.45),
]


@pytest.mark.parametrize("gr_income,tx", test_cases)
def test_income_tax(gr_income, tx):
    tax = income_tax(gr_income)
    assert tax == pytest.approx(tx, abs=1e-2)
