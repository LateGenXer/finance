"""UK tax constants and functions."""


import math


# https://www.gov.uk/government/publications/rates-and-allowances-income-tax/income-tax-rates-and-allowances-current-and-past
income_tax_threshold_20 =  12570
income_tax_threshold_40 =  50270
pa_limit                = 100000
income_tax_threshold_45 = pa_limit + 2*income_tax_threshold_20 # 2023/2024
assert income_tax_threshold_45 == 125140

# https://www.gov.uk/government/publications/the-personal-allowance-and-basic-rate-limit-for-income-tax-and-certain-national-insurance-contributions-nics-thresholds-from-6-april-2026-to-5-apr/income-tax-personal-allowance-and-the-basic-rate-limit-and-certain-national-insurance-contributions-thresholds-from-6-april-2026-to-5-april-2028
_inflation_rate = .035
_inflation_adjustment = (1 + _inflation_rate) ** -4
income_tax_threshold_20 = int(income_tax_threshold_20 * _inflation_adjustment)
income_tax_threshold_40 = int(income_tax_threshold_40 * _inflation_adjustment)
pa_limit                = int(pa_limit * _inflation_adjustment)
income_tax_threshold_45 = pa_limit + 2*income_tax_threshold_20 # 2023/2024


# https://www.gov.uk/capital-gains-tax/allowances
# https://www.gov.uk/government/publications/reducing-the-annual-exempt-amount-for-capital-gains-tax
cgt_allowance = 3000 # 2024/2025


# https://www.gov.uk/new-state-pension/what-youll-get
weeks_per_year = 365.25/7
state_pension_full = 221.20 * weeks_per_year


# https://www.gov.uk/government/publications/increasing-normal-minimum-pension-age/increasing-normal-minimum-pension-age
# https://adviser.royallondon.com/technical-central/pensions/benefit-options/increase-in-normal-minimum-pension-age-in-2028/
def nmpa(dob):
    if dob + 55 <= 2028:
        return 55
    elif dob + 57 <= 2044:
        return 57
    else:
        # XXX: Not set in stone
        return 58


# https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/310231/spa-timetable.pdf
# XXX rough approximation
def state_pension_age(dob):
    if dob + 66 <= 2028:
        return 66
    elif dob + 67 < 2044:
        return 67
    else:
        return 68


# https://www.gov.uk/government/publications/rates-and-allowances-pension-schemes/pension-schemes-rates
uiaa     =  3600     # Unearned income annual allowance
aa       = 60000
aa_taper = 10000
mpaa     = 10000

lta = 1073100
tfca = 268275
assert tfca * 4 == lta

isa_allowance = 20000


def income_tax(gross_income):
    # https://www.gov.uk/income-tax-rates/income-over-100000
    personal_allowance = max(income_tax_threshold_20 - max(gross_income - pa_limit, 0)*0.5, 0)
    taxable_income = max(gross_income - personal_allowance, 0)

    assert income_tax_threshold_45 >= pa_limit + 2*income_tax_threshold_20
    taxable_income_45 = max(taxable_income - income_tax_threshold_45, 0)
    taxable_income -= taxable_income_45

    taxable_income_20 = min(taxable_income, income_tax_threshold_40 - income_tax_threshold_20)
    taxable_income   -= taxable_income_20
    taxable_income_40 = taxable_income

    tax  = taxable_income_20 * 0.20
    tax += taxable_income_40 * 0.40
    tax += taxable_income_45 * 0.45

    if False:
        print("PA", personal_allowance)
        print(20, taxable_income_20 * 0.20)
        print(40, taxable_income_40 * 0.40)
        print(45, taxable_income_45 * 0.45)

    return tax


def gross_income(net_income_):
    assert net_income_ >= 0

    abs_tol = 0.01

    income = net_income_
    income_tax_band_00 = min(income, income_tax_threshold_20)
    income -= income_tax_band_00
    income_tax_band_20 = min(income, (income_tax_threshold_40 - income_tax_threshold_20)*0.80)
    income -= income_tax_band_20
    income_tax_band_40 = min(income, (pa_limit                - income_tax_threshold_40)*0.60)
    income -= income_tax_band_40
    income_tax_band_60 = min(income, 2*income_tax_threshold_20*0.40)
    income -= income_tax_band_60

    assert income_tax_threshold_45 == pa_limit + 2*income_tax_threshold_20
    income_tax_band_45 = income

    gross_income  = income_tax_band_00
    assert gross_income <= income_tax_threshold_20 + abs_tol
    gross_income += income_tax_band_20 / 0.80
    assert gross_income <= income_tax_threshold_40 + abs_tol
    gross_income += income_tax_band_40 / 0.60
    assert gross_income <= pa_limit + abs_tol
    gross_income += income_tax_band_60 / 0.40
    assert gross_income <= pa_limit + 2*income_tax_threshold_20 + abs_tol
    assert gross_income <= income_tax_threshold_45 + abs_tol
    gross_income += income_tax_band_45 / 0.55

    return gross_income
