import pytest

from uk import *


basic_rate_allowance  = income_tax_threshold_40 - income_tax_threshold_20
higher_rate_allowance = income_tax_threshold_45 - income_tax_threshold_40


# income, income_tax, cg, cgt
combined_test_cases = [
    (0, 0, 0, 0),
    (0, 0, cgt_allowance, 0),
    (0, 0, cgt_allowance + 1, 0.10),
    (0, 0, cgt_allowance + income_tax_threshold_40, income_tax_threshold_40*0.10),
    (0, 0, cgt_allowance + income_tax_threshold_40 + 1, income_tax_threshold_40*0.10 + 0.20),
    (1, 0, 0, 0),
    (income_tax_threshold_20, 0, 0, 0),
    (income_tax_threshold_20, 0, cgt_allowance, 0),
    (income_tax_threshold_20, 0, cgt_allowance + basic_rate_allowance, basic_rate_allowance*0.10),
    (income_tax_threshold_20, 0, cgt_allowance + basic_rate_allowance + 1, basic_rate_allowance*0.10 + 0.20),
    (income_tax_threshold_20 + 1, 0.20, 0, 0),
    (income_tax_threshold_40, basic_rate_allowance*0.20, 0, 0),
    (income_tax_threshold_40, basic_rate_allowance*0.20, cgt_allowance, 0),
    (income_tax_threshold_40, basic_rate_allowance*0.20, cgt_allowance + 1, 0.20),
    (income_tax_threshold_40 + 1, basic_rate_allowance*0.20 + 0.40, 0, 0),
    (pa_limit, basic_rate_allowance*0.20 + (pa_limit - income_tax_threshold_40) * 0.40, 0, 0),
    (pa_limit, basic_rate_allowance*0.20 + (pa_limit - income_tax_threshold_40) * 0.40, cgt_allowance, 0),
    (pa_limit, basic_rate_allowance*0.20 + (pa_limit - income_tax_threshold_40) * 0.40, cgt_allowance + 1, 0.20),
    (pa_limit + 1, basic_rate_allowance*0.20 + (pa_limit - income_tax_threshold_40) * 0.40 + 0.40*1.5, 0, 0),
    (income_tax_threshold_45, basic_rate_allowance*0.20 + (income_tax_threshold_45 - basic_rate_allowance) * 0.40, 0, 0),
    (income_tax_threshold_45, basic_rate_allowance*0.20 + (income_tax_threshold_45 - basic_rate_allowance) * 0.40, cgt_allowance, 0),
    (income_tax_threshold_45, basic_rate_allowance*0.20 + (income_tax_threshold_45 - basic_rate_allowance) * 0.40, cgt_allowance + 1, 0.20),
    (income_tax_threshold_45 + 1, basic_rate_allowance*0.20 + (income_tax_threshold_45 - basic_rate_allowance) * 0.40 + 0.45, 0, 0),
]


@pytest.mark.parametrize("income,income_tax,cg,cgt", combined_test_cases)
def test_tax(income, cg, income_tax, cgt):
    income_tax_, cgt_ = tax(income, cg)
    assert income_tax_ == pytest.approx(income_tax, abs=1e-2)
    assert cgt_ == pytest.approx(cgt, abs=1e-2)
