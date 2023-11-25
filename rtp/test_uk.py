import pytest

from uk import *


@pytest.mark.parametrize("gross_income_", [
    income_tax_threshold_20 // 2,
    income_tax_threshold_20,
    income_tax_threshold_20 // 2 + income_tax_threshold_40 // 2,
    income_tax_threshold_40,
    pa_limit,
    pa_limit + income_tax_threshold_20,
    pa_limit + income_tax_threshold_20 * 2,
    income_tax_threshold_45,
    income_tax_threshold_45 * 2,
])
def test_income_tax(gross_income_):
    nt_income = gross_income_ - income_tax(gross_income_)
    gr_income = gross_income(nt_income)
    assert math.isclose(gross_income_, gr_income)
