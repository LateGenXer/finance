import datetime

import pytest

from tax import uk
from rtp import model

import test_tax_uk

import lp


@pytest.mark.parametrize('lump_sum', [pytest.param(0, id=""), pytest.param(1000, id="lump_sum")])
@pytest.mark.parametrize('retirement_income_net', [pytest.param(0, id="max_income"), pytest.param(10000, id="fix_income")])
@pytest.mark.parametrize('retirement_country', ['UK', 'PT', 'JP'])
@pytest.mark.parametrize('sipp_extra_contrib', [pytest.param(False, id=""), pytest.param(True, id="sipp_extra_contrib")])
@pytest.mark.parametrize('joint,marriage_allowance', [
    pytest.param(False, False, id="single"),
    pytest.param(True, False, id="joint"),
    pytest.param(True, True, id="marriage_allowance"),
])
def test_model(joint, sipp_extra_contrib, retirement_country, retirement_income_net, lump_sum, marriage_allowance):
    params = {
        "joint": joint,
        "dob_1": 1980,
        "dob_2": 1981,
        "state_pension_years_1": 35,
        "state_pension_years_2": 35,
        "marginal_income_tax_1": 0.4,
        "marginal_income_tax_2": 0.2,
        "sipp_1": 750000,
        "sipp_2": 000000,
        "sipp_df_1": 0,
        "sipp_df_2": 0,
        "lsa_ratio_1": 1.0,
        "lsa_ratio_2": 1.0,
        "sipp_contrib_1": 0,
        "sipp_contrib_2": uk.uiaa,
        "sipp_extra_contrib": sipp_extra_contrib,
        "db_payments_1": [],
        "db_ages_1": [],
        "db_payments_2": [],
        "db_ages_2": [],
        "isa": 250000,
        "gia": 100000,
        "gia_gains": 25000,
        "misc_contrib": 0,
        "inflation_rate": 2.5e-2,
        "isa_growth_rate": 5.5e-2,
        "gia_growth_rate": 5.5e-2,
        "sipp_growth_rate_1": 5.5e-2,
        "sipp_growth_rate_2": 5.5e-2,
        'present_year': datetime.date.today().year,
        "country": retirement_country,
        "retirement_income_net": retirement_income_net,
        "retirement_year": 2045,
        "lump_sum": lump_sum,
        "aa_1": uk.aa,
        "aa_2": uk.uiaa,
        "marriage_allowance": marriage_allowance,
        "end_age": 100,
    }

    model.run(params)


def gia_params(**kwargs):
    present_year = datetime.date.today().year
    params = {
        "joint": False,
        "dob_1": present_year - 70,
        "dob_2": present_year - 70,
        "state_pension_years_1": 0,
        "state_pension_years_2": 0,
        "marginal_income_tax_1": 0.2,
        "marginal_income_tax_2": 0.2,
        "sipp_1": 0,
        "sipp_2": 0,
        "sipp_df_1": 0,
        "sipp_df_2": 0,
        "lsa_ratio_1": 1.0,
        "lsa_ratio_2": 1.0,
        "sipp_contrib_1": 0,
        "sipp_contrib_2": 0,
        "sipp_extra_contrib": False,
        "db_payments_1": [],
        "db_ages_1": [],
        "db_payments_2": [],
        "db_ages_2": [],
        "isa": 0,
        "gia": 100000,
        "gia_gains": 0,
        "misc_contrib": 0,
        "inflation_rate": 2.5e-2,
        "isa_growth_rate": 5.5e-2,
        "gia_growth_rate": 5.5e-2,
        "sipp_growth_rate_1": 5.5e-2,
        "sipp_growth_rate_2": 5.5e-2,
        "present_year": present_year,
        "country": "UK",
        "retirement_income_net": 0,
        "retirement_year": present_year,
        "lump_sum": 0,
        "aa_1": 0,
        "aa_2": 0,
        "marriage_allowance": False,
        "end_age": 71,  # Single year
    }
    params.update(kwargs)
    return params


# Gain fraction realized when selling from the initial GIA lot in the first year
def initial_gain_ratio(gia, gia_gains, growth_rate=5.5e-2):
    return 1.0 - (1.0 - gia_gains / gia) / (1.0 + growth_rate)


def test_gia_no_gains():
    result = model.model(**gia_params())
    cg = 100000 * initial_gain_ratio(100000, 0)
    assert result.data[0].cg == pytest.approx(cg, abs=1e-2)
    assert result.data[0].cgt == pytest.approx((cg - uk.cgt_allowance) * uk.cgt_rates[0], abs=1e-2)


def test_gia_gains():
    result = model.model(**gia_params(gia_gains=40000))
    cg = 100000 * initial_gain_ratio(100000, 40000)
    assert result.data[0].cg == pytest.approx(cg, abs=1e-2)
    assert result.data[0].cgt == pytest.approx((cg - uk.cgt_allowance) * uk.cgt_rates[0], abs=1e-2)


def test_gia_gains_lump_sum():
    # Lump sum goes into a separate lot, with no gains of its own
    result = model.model(**gia_params(gia_gains=100000, lump_sum=50000))
    assert result.ls_gia > 0
    cg = 100000 + result.ls_gia * (1 - model.eps) * initial_gain_ratio(100000, 0)
    assert result.data[0].cg == pytest.approx(cg, abs=1e-2)


def test_gia_gains_excessive():
    with pytest.raises(ValueError):
        model.model(**gia_params(gia_gains=100001))


def test_gia_gains_reduce_income():
    low = model.model(**gia_params(end_age=75, gia=500000, gia_gains=100000))
    high = model.model(**gia_params(end_age=75, gia=500000, gia_gains=400000))
    assert high.retirement_income_net < low.retirement_income_net


@pytest.mark.parametrize("income,income_tax,cg,cgt,ma", [
    test_case for test_case in test_tax_uk.combined_test_cases if test_case[0] <= uk.IncomeTaxThresholds.income_tax_threshold_45
])
def test_uk_tax_lp(income:int, cg:int, income_tax, cgt:float, ma:int):
    prob = lp.LpProblem("test_uk_tax_lp")
    itt = uk.IncomeTaxThresholds()
    income_tax_, cgt_ = model.uk_tax_lp(prob, income, cg, itt, marriage_allowance=ma)
    prob.setObjective(income_tax_ + cgt_)
    model.solve(prob)
    assert lp.value(income_tax_) == pytest.approx(income_tax, abs=1e-2)
    assert lp.value(cgt_) == pytest.approx(cgt, abs=1e-2)
