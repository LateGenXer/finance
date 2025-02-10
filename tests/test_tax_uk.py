#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import pytest

from tax.uk import *


basic_rate_allowance  = income_tax_threshold_40 - income_tax_threshold_20
higher_rate_allowance = income_tax_threshold_45 - income_tax_threshold_40

cgt_rate_basic, cgt_rate_higher = cgt_rates


# income, income_tax, cg, cgt, ma
combined_test_cases = [
    (0, 0, 0, 0, 0),
    (0, 0, cgt_allowance, 0, 0),
    (0, 0, cgt_allowance + 1, cgt_rate_basic, 0),
    (0, 0, cgt_allowance + income_tax_threshold_40, income_tax_threshold_40*cgt_rate_basic, 0),
    (0, 0, cgt_allowance + income_tax_threshold_40 + 1, income_tax_threshold_40*cgt_rate_basic + cgt_rate_higher, 0),
    (1, 0, 0, 0, 0),
    (income_tax_threshold_20, 0, 0, 0, 0),
    (income_tax_threshold_20, marriage_allowance*0.20, 0, 0, -marriage_allowance),
    (income_tax_threshold_20, 0, cgt_allowance, 0, 0),
    (income_tax_threshold_20, 0, cgt_allowance + basic_rate_allowance, basic_rate_allowance*cgt_rate_basic, 0),
    (income_tax_threshold_20, 0, cgt_allowance + basic_rate_allowance + 1, basic_rate_allowance*cgt_rate_basic + cgt_rate_higher, 0),
    (income_tax_threshold_20 + 1, 0.20, 0, 0, 0),
    (income_tax_threshold_20 + marriage_allowance, 0, 0, 0, marriage_allowance),
    (income_tax_threshold_40, basic_rate_allowance*0.20, 0, 0, 0),
    (income_tax_threshold_40, (basic_rate_allowance - marriage_allowance)*0.20, 0, 0, marriage_allowance),
    (income_tax_threshold_40, basic_rate_allowance*0.20, cgt_allowance, 0, 0),
    (income_tax_threshold_40, basic_rate_allowance*0.20, cgt_allowance + 1, cgt_rate_higher, 0),
    (income_tax_threshold_40 + 1, basic_rate_allowance*0.20 + 0.40, 0, 0, 0),
    (pa_limit, basic_rate_allowance*0.20 + (pa_limit - income_tax_threshold_40) * 0.40, 0, 0, 0),
    (pa_limit, basic_rate_allowance*0.20 + (pa_limit - income_tax_threshold_40) * 0.40, cgt_allowance, 0, 0),
    (pa_limit, basic_rate_allowance*0.20 + (pa_limit - income_tax_threshold_40) * 0.40, cgt_allowance + 1, cgt_rate_higher, 0),
    (pa_limit + 1, basic_rate_allowance*0.20 + (pa_limit - income_tax_threshold_40) * 0.40 + 0.40*1.5, 0, 0, 0),
    (income_tax_threshold_45, basic_rate_allowance*0.20 + (income_tax_threshold_45 - basic_rate_allowance) * 0.40, 0, 0, 0),
    (income_tax_threshold_45, basic_rate_allowance*0.20 + (income_tax_threshold_45 - basic_rate_allowance) * 0.40, cgt_allowance, 0, 0),
    (income_tax_threshold_45, basic_rate_allowance*0.20 + (income_tax_threshold_45 - basic_rate_allowance) * 0.40, cgt_allowance + 1, cgt_rate_higher, 0),
    (income_tax_threshold_45 + 1, basic_rate_allowance*0.20 + (income_tax_threshold_45 - basic_rate_allowance) * 0.40 + 0.45, 0, 0, 0),
]


@pytest.mark.parametrize("income,income_tax,cg,cgt,ma", combined_test_cases)
def test_tax(income, cg, income_tax, cgt, ma):
    income_tax_, cgt_ = tax(income, cg, marriage_allowance=ma)
    assert income_tax_ == pytest.approx(income_tax, abs=1e-2)
    assert cgt_ == pytest.approx(cgt, abs=1e-2)
