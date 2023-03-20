import math


# https://www.gov.uk/government/publications/rates-and-allowances-income-tax/income-tax-rates-and-allowances-current-and-past
income_tax_threshold_20 =  12570
income_tax_threshold_40 =  50270
pa_limit                = 100000
if False:
    income_tax_threshold_45 = 150000           # 2022/2023
else:
    income_tax_threshold_45 = pa_limit + 2*income_tax_threshold_20 # 2023/2024
    assert income_tax_threshold_45 == 125140

cgt_allowance = 3000

weeks_per_year = 365.25/7
state_pension_full = 185.15 * weeks_per_year
state_pension_age = 68

# https://www.gov.uk/government/publications/increasing-normal-minimum-pension-age/increasing-normal-minimum-pension-age
nmpa = 57

# https://www.gov.uk/government/publications/rates-and-allowances-pension-schemes/pension-schemes-rates
uiaa     =  3600     # Unearned income annual allowance
aa       = 60000
aa_taper = 10000
mpaa     = 10000

lta = 1073100
tfca = 268275
assert tfca * 4 == lta

isa_allowance = 20000


def net_income(gross_income):
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

    net_income = gross_income - tax
    return net_income


def gross_income(net_income_):
    assert net_income_ >= 0

    abs_tol = 0.01

    income = net_income_
    income_tax_band_00 = min(income, income_tax_threshold_20)
    income -= income_tax_band_00
    income_tax_band_20 = min(income, (income_tax_threshold_40 - income_tax_threshold_20)*0.80)
    income -= income_tax_band_20
    income_tax_band_40 = min(income, (100000                  - income_tax_threshold_40)*0.60)
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


# Test
def test_income_tax(gross_income_):
    nt_income = net_income(gross_income_)
    gr_income = gross_income(nt_income)
    assert math.isclose(gross_income_, gr_income)

test_income_tax(income_tax_threshold_20*0.5)
test_income_tax(income_tax_threshold_20)
test_income_tax(income_tax_threshold_20*0.5 + income_tax_threshold_40*0.5)
test_income_tax(income_tax_threshold_40)
test_income_tax(100000)
test_income_tax(100000 + income_tax_threshold_20)
test_income_tax(100000 + 2*income_tax_threshold_20)
test_income_tax(income_tax_threshold_45)
test_income_tax(income_tax_threshold_45*2)
