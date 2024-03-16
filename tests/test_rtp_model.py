import datetime

import pytest

import uk
import model



@pytest.mark.parametrize('lump_sum', [0, 1000])
@pytest.mark.parametrize('retirement_income_net', [0, 10000])
@pytest.mark.parametrize('retirement_country', ['UK', 'PT'])
@pytest.mark.parametrize('lacs', [False, True])
@pytest.mark.parametrize('sipp_extra_contrib', [False, True])
@pytest.mark.parametrize('joint,marriage_allowance', [(False, False), (True, False), (True, True)])
def test_model(joint, sipp_extra_contrib, lacs, retirement_country, retirement_income_net, lump_sum, marriage_allowance):
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
        "sipp_contrib_1": 0,
        "sipp_contrib_2": uk.uiaa,
        "sipp_extra_contrib": sipp_extra_contrib,
        "isa": 250000,
        "gia": 0,
        "misc_contrib": 0,
        "inflation_rate": 2.5e-2,
        "isa_growth_rate": 5.5e-2,
        "gia_growth_rate": 5.5e-2,
        "sipp_growth_rate_1": 5.5e-2,
        "sipp_growth_rate_2": 5.5e-2,
        'present_year': datetime.date.today().year,
        "pt": retirement_country == "UK",
        "retirement_income_net": retirement_income_net,
        "retirement_year": 2045,
        "lacs": lacs,
        "lump_sum": lump_sum,
        "aa_1": uk.aa,
        "aa_2": uk.uiaa,
        "marriage_allowance": marriage_allowance,
    }

    model.run(params)
