"""UK tax constants and functions."""


# https://www.gov.uk/government/publications/rates-and-allowances-income-tax/income-tax-rates-and-allowances-current-and-past
income_tax_threshold_20 =  12570
income_tax_threshold_40 =  50270
pa_limit                = 100000
income_tax_threshold_45 = pa_limit + 2*income_tax_threshold_20 # 2023/2024
assert income_tax_threshold_45 == 125140

# https://www.gov.uk/government/publications/the-personal-allowance-and-basic-rate-limit-for-income-tax-and-certain-national-insurance-contributions-nics-thresholds-from-6-april-2026-to-5-apr/income-tax-personal-allowance-and-the-basic-rate-limit-and-certain-national-insurance-contributions-thresholds-from-6-april-2026-to-5-april-2028
_inflation_rate = .035
_inflation_adjustment = (1 + _inflation_rate) ** -3
income_tax_threshold_20 = int(income_tax_threshold_20 * _inflation_adjustment)
income_tax_threshold_40 = int(income_tax_threshold_40 * _inflation_adjustment)
pa_limit                = int(pa_limit * _inflation_adjustment)
income_tax_threshold_45 = pa_limit + 2*income_tax_threshold_20 # 2023/2024


# https://www.gov.uk/capital-gains-tax/allowances
# https://www.gov.uk/government/publications/reducing-the-annual-exempt-amount-for-capital-gains-tax
cgt_allowance = 3000 # 2024/2025
cgt_rates = [0.18, 0.24]


# https://www.gov.uk/marriage-allowance
marriage_allowance = 1260


# https://www.gov.uk/new-state-pension/what-youll-get
weeks_per_year = 365.25/7
state_pension_full = 230.05 * weeks_per_year


# https://www.gov.uk/government/publications/increasing-normal-minimum-pension-age/increasing-normal-minimum-pension-age
# https://adviser.royallondon.com/technical-central/pensions/benefit-options/increase-in-normal-minimum-pension-age-in-2028/
def nmpa(dob):
    if dob + 55 <= 2028:
        return 55
    elif dob + 57 < 2044:
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

# https://www.gov.uk/tax-on-your-private-pension/lump-sum-allowance
lsa = 268275

isa_allowance = 20000


def _split(allowance, income):
    used = min(allowance, income)
    allowance -= used
    income -= used
    return allowance, income, used


def tax(income, capital_gains = 0, marriage_allowance = 0):

    assert income_tax_threshold_45 >= pa_limit + 2*income_tax_threshold_20

    # https://www.gov.uk/income-tax-rates/income-over-100000
    personal_allowance    = max(income_tax_threshold_20 + marriage_allowance - max(income - pa_limit, 0)*0.5, 0)
    basic_rate_allowance  = income_tax_threshold_40 - income_tax_threshold_20
    higher_rate_allowance = income_tax_threshold_45 - personal_allowance - basic_rate_allowance

    personal_allowance,    income,                 _                  = _split(personal_allowance,    income)
    basic_rate_allowance,  income,                 basic_rate_income  = _split(basic_rate_allowance,  income)
    higher_rate_allowance, additional_rate_income, higher_rate_income = _split(higher_rate_allowance, income)

    income_tax  = basic_rate_income      * 0.20
    income_tax += higher_rate_income     * 0.40
    income_tax += additional_rate_income * 0.45

    if False:
        print("PA", personal_allowance)
        print("20", basic_rate_income      * 0.20)
        print("40", higher_rate_income     * 0.40)
        print("45", additional_rate_income * 0.45)

    _, capital_gains, _                                    = _split(cgt_allowance,                             capital_gains)
    _, higher_rate_capital_gains, basic_rate_capital_gains = _split(personal_allowance + basic_rate_allowance, capital_gains)

    capital_gains_tax  = basic_rate_capital_gains  * cgt_rates[0]
    capital_gains_tax += higher_rate_capital_gains * cgt_rates[1]

    return income_tax, capital_gains_tax
