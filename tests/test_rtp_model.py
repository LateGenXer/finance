import json
import os

from decimal import Decimal

import pytest

from tax import uk
from rtp import model

import data.hmrc

import test_tax_uk

import lp


# Fixed inputs, so that results don't depend on the current date or live data
present_year = 2026
exchange_rates = {'EUR': Decimal('1.15'), 'JPY': Decimal('190.0')}


@pytest.fixture(autouse=True)
def no_live_exchange_rates(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("unexpected live exchange rate fetch")
    monkeypatch.setattr(data.hmrc, 'exchange_rates', fail)
    monkeypatch.setattr(data.hmrc, 'current_exchange_rates', fail)
    monkeypatch.setattr(data.hmrc, 'exchange_rate', fail)


def model_params(joint, marriage_allowance, country, retirement_income_net, lump_sum, sipp_extra_contrib):
    return {
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
        "present_year": present_year,
        "country": country,
        "retirement_income_net": retirement_income_net,
        "retirement_year": 2045,
        "lump_sum": lump_sum,
        "aa_1": uk.aa,
        "aa_2": uk.uiaa,
        "marriage_allowance": marriage_allowance,
        "end_age": 100,
        "exchange_rates": exchange_rates,
    }


SINGLE = dict(joint=False, marriage_allowance=False)
JOINT = dict(joint=True, marriage_allowance=False)
MA = dict(joint=True, marriage_allowance=True)

MAX = 0       # maximize retirement income
FIX = 10000   # fixed retirement income, maximize end net worth


# Only figures that are the LP objective are pinned (retirement income when
# maximizing income, end net worth otherwise); other figures such as total tax
# are not unique among optimal solutions and differ between LP solvers.
#
# Latin-sampled combinations: each household type and country appears twice,
# each binary factor three times.
@pytest.mark.parametrize("household,country,retirement_income_net,lump_sum,sipp_extra_contrib,expected", [
    pytest.param(SINGLE, 'UK', MAX,    0, False, dict(retirement_income_net=85205.10, net_worth_end=0), id="single-UK-max"),
    pytest.param(JOINT,  'PT', MAX, 1000, True,  dict(retirement_income_net=89990.58, net_worth_end=0), id="joint-PT-max-ls-extra"),
    pytest.param(MA,     'JP', FIX,    0, True,  dict(net_worth_end=5853515), id="ma-JP-fix-extra"),
    pytest.param(SINGLE, 'JP', FIX, 1000, True,  dict(net_worth_end=5017391), id="single-JP-fix-ls-extra"),
    pytest.param(JOINT,  'UK', FIX,    0, False, dict(net_worth_end=6352109), id="joint-UK-fix"),
    pytest.param(MA,     'PT', MAX, 1000, False, dict(retirement_income_net=89990.57, net_worth_end=0), id="ma-PT-max-ls"),
])
def test_model(household, country, retirement_income_net, lump_sum, sipp_extra_contrib, expected):
    params = model_params(country=country, retirement_income_net=retirement_income_net, lump_sum=lump_sum, sipp_extra_contrib=sipp_extra_contrib, **household)
    result = model.model(**params)
    actual = {name: getattr(result, name) for name in expected}
    assert actual == pytest.approx(expected, rel=1e-6, abs=1)


@pytest.mark.parametrize("country,currency", [('UK', None), ('PT', 'EUR'), ('JP', 'JPY')])
def test_run(capsys, country, currency):
    params = model_params(country=country, retirement_income_net=MAX, lump_sum=1000, sipp_extra_contrib=False, **JOINT)
    if country == 'UK':
        params['exchange_rates'] = {}
    model.run(params)
    out = capsys.readouterr().out
    assert 'Retirement net income' in out
    if currency is not None:
        assert currency in out


def test_missing_exchange_rates():
    params = model_params(country='JP', retirement_income_net=MAX, lump_sum=0, sipp_extra_contrib=False, **SINGLE)
    del params['exchange_rates']
    with pytest.raises(KeyError):
        model.model(**params)


def test_default_params():
    # Default parameters presented by the Streamlit app
    with open(os.path.join(os.path.dirname(__file__), 'data', 'rtp-params-default.json'), 'rt') as f:
        params = json.load(f)
    del params['version']
    for key in ('inflation_rate', 'isa_growth_rate', 'gia_growth_rate', 'sipp_growth_rate_1', 'sipp_growth_rate_2', 'lsa_ratio_1', 'lsa_ratio_2'):
        params[key] = params[key] / 100.0
    for key in ('db_payments_1', 'db_payments_2', 'db_ages_1', 'db_ages_2'):
        assert params[key] == ''
        params[key] = []
    params['country'] = params.pop('retirement_country')
    params['present_year'] = present_year
    result = model.model(**params)
    assert result.retirement_income_net == pytest.approx(77656.13, rel=1e-6, abs=1)


def gia_params(**kwargs):
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
