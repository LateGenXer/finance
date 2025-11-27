"""UK tax constants and functions."""


import datetime
import typing


# https://www.gov.uk/government/publications/rates-and-allowances-income-tax/income-tax-rates-and-allowances-current-and-past
income_tax_threshold_20 =  12570
income_tax_threshold_40 =  50270
pa_limit                = 100000
income_tax_threshold_45 = pa_limit + 2*income_tax_threshold_20 # 2023/2024
assert income_tax_threshold_45 == 125140

# https://www.gov.uk/government/publications/the-personal-allowance-and-basic-rate-limit-for-income-tax-and-certain-national-insurance-contributions-nics-thresholds-from-6-april-2026-to-5-apr/income-tax-personal-allowance-and-the-basic-rate-limit-and-certain-national-insurance-contributions-thresholds-from-6-april-2026-to-5-april-2028
# https://www.gov.uk/government/publications/budget-2025-document/budget-2025-html#taxation-of-income-from-assets#asking-everyone-to-contribute
_today = datetime.datetime.now(datetime.timezone.utc).date()
_years = max(2031 - _today.year, 0)
_inflation_rate = .035
_inflation_adjustment = (1 + _inflation_rate) ** -_years
income_tax_threshold_20 = int(income_tax_threshold_20 * _inflation_adjustment)
income_tax_threshold_40 = int(income_tax_threshold_40 * _inflation_adjustment)
pa_limit                = int(pa_limit * _inflation_adjustment)
income_tax_threshold_45 = pa_limit + 2*income_tax_threshold_20 # 2023/2024


# https://www.gov.uk/capital-gains-tax/allowances
# https://www.gov.uk/government/publications/reducing-the-annual-exempt-amount-for-capital-gains-tax
cgt_allowance = 3000 # 2025/2026
cgt_rates = [0.18, 0.24]


# https://www.gov.uk/marriage-allowance
marriage_allowance = 1260


# https://www.gov.uk/new-state-pension/what-youll-get
# https://www.gov.uk/government/publications/benefit-and-pension-rates-2025-to-2026/benefit-and-pension-rates-2025-to-2026#state-pension
weeks_per_year = 365.25/7
state_pension_full = 230.25 * weeks_per_year


# https://www.gov.uk/government/publications/increasing-normal-minimum-pension-age/increasing-normal-minimum-pension-age
# https://adviser.royallondon.com/technical-central/pensions/benefit-options/increase-in-normal-minimum-pension-age-in-2028/
def nmpa(dob:int) -> int:
    if dob + 55 <= 2028:
        return 55
    elif dob + 57 < 2044:
        return 57
    else:
        # XXX: Not set in stone
        return 58


# https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/310231/spa-timetable.pdf
# XXX rough approximation
def state_pension_age(dob:int) -> int:
    if dob + 66 <= 2028:
        return 66
    elif dob + 67 < 2044:
        return 67
    else:
        return 68


# https://www.gov.uk/government/publications/rates-and-allowances-pension-schemes/pension-schemes-rates
uiaa     =  3600     # Unearned income annual allowance
aa       = 60000
mpaa     = 10000

# https://www.gov.uk/tax-on-your-private-pension/lump-sum-allowance
lsa = 268275

isa_allowance = 20000


def _split(allowance:float|int, income:float|int) -> tuple[float|int, float|int, float|int]:
    used = min(allowance, income)
    allowance -= used
    income -= used
    return allowance, income, used


def tax(income:float|int, capital_gains:float|int = 0, marriage_allowance:float|int = 0) -> tuple[float, float]:

    assert income_tax_threshold_45 >= pa_limit + 2*income_tax_threshold_20

    # https://www.gov.uk/income-tax-rates/income-over-100000
    personal_allowance   :float = max(income_tax_threshold_20 + marriage_allowance - max(income - pa_limit, 0)*0.5, 0)
    basic_rate_allowance :float = income_tax_threshold_40 - income_tax_threshold_20
    higher_rate_allowance:float = income_tax_threshold_45 - personal_allowance - basic_rate_allowance

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


class TaxYear(typing.NamedTuple):

    year1: int
    year2: int

    def __str__(self) -> str:
        return f'{self.year1}/{self.year2}'

    def start_date(self) -> datetime.date:
        return datetime.date(self.year1, 4, 6)

    def end_date(self) -> datetime.date:
        return datetime.date(self.year2, 4, 5)

    @classmethod
    def from_date(cls, date:datetime.date) -> 'TaxYear':
        if date < date.replace(date.year, 4, 6):
            year1, year2 = date.year - 1, date.year
        else:
            year1, year2 = date.year, date.year + 1
        return cls(year1, year2)

    @staticmethod
    def _str_to_year(s:str) -> int:
        assert isinstance(s, str)
        if not s.isdigit():
            raise ValueError(s)
        y = int(s)
        if len(s) == 2 and s.isdigit():
            y += 2000
        if y < datetime.MINYEAR or y > datetime.MAXYEAR:
            raise ValueError(f'{s} out of range')
        return y

    @classmethod
    def from_string(cls, s:str) -> 'TaxYear':
        try:
            s1, s2 = s.split('/', maxsplit=1)
        except ValueError:
            y2 = cls._str_to_year(s)
            y1 = y2 - 1
        else:
            y1 = cls._str_to_year(s1)
            y2 = cls._str_to_year(s2)
            if y1 + 1 != y2:
                raise ValueError(f'{s1} and {s2} are not consecutive years')
        return cls(y1, y2)


