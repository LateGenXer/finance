#!/usr/bin/env python3
#
# Copyright (c) 2024-2025 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#

#
# Python capital gains calculator, inspired by http://cgtcalculator.com/ and
# https://github.com/mattjgalloway/cgtcalc
#
# See cgtcalc.md for usage instructions.
#


import argparse
import dataclasses
import datetime
import math
import operator
import sys
import typing

from enum import IntEnum, Enum
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_CEILING, ROUND_FLOOR

from environ import get_version
from report import Report, TextReport, HtmlReport


Kind = IntEnum('Kind', ['DIVIDEND', 'CAPRETURN', 'BUY', 'SELL'])


# Holding and matching relies upon this ordering
assert Kind.DIVIDEND < Kind.BUY
assert Kind.CAPRETURN < Kind.BUY
assert Kind.BUY < Kind.SELL


@dataclasses.dataclass
class Trade:
    date: datetime.date
    kind: Kind
    params: list[typing.Any]


# https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg51560
Identification = Enum('Identification', ['SAME_DAY', 'BED_AND_BREAKFAST', 'POOL'])


@dataclasses.dataclass
class Acquisition:
    cost: Decimal
    shares: Decimal

    # How many shares are yet to to be identified
    unidentified: Decimal


@dataclasses.dataclass
class Disposal:
    proceeds: Decimal
    cost: Decimal
    shares: Decimal
    unidentified: Decimal
    identifications: list[tuple] = dataclasses.field(default_factory=list)


def identify(disposal, acquisition, kind, acquisition_date):
    assert disposal.unidentified > Decimal(0)
    assert acquisition.unidentified > Decimal(0)
    identified = min(disposal.unidentified, acquisition.unidentified)
    acquisition.unidentified -= identified
    assert acquisition.unidentified >= Decimal(0)
    identification = (identified, kind, acquisition_date)
    disposal.identifications.append(identification)
    disposal.unidentified -= identified


@dataclasses.dataclass
class PoolUpdate:
    date: datetime.date
    description: str
    identified: Decimal
    delta_cost: Decimal
    pool_shares: Decimal
    pool_cost: Decimal


@dataclasses.dataclass
class DisposalResult:
    date: datetime.date
    security: str
    shares: Decimal
    proceeds: Decimal
    costs: Decimal
    table: list


class TaxYear(typing.NamedTuple):

    year1: int
    year2: int

    def __str__(self):
        return f'{self.year1}/{self.year2}'

    def start_date(self):
        return datetime.date(self.year1, 4, 6)

    def end_date(self):
        return datetime.date(self.year2, 4, 5)

    @classmethod
    def from_date(cls, date:datetime.date):
        if date < date.replace(date.year, 4, 6):
            year1, year2 = date.year - 1, date.year
        else:
            year1, year2 = date.year, date.year + 1
        return cls(year1, year2)

    @staticmethod
    def _str_to_year(s:str):
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
    def from_string(cls, s:str):
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


# https://www.gov.uk/guidance/capital-gains-tax-rates-and-allowances
# https://www.rossmartin.co.uk/capital-gains-tax/110-capital-gains-tax-rates-a-allowances
allowances = {
    (2008, 2009):  9600,
    (2009, 2010): 10100,
    (2010, 2011): 10100,
    (2011, 2012): 10600,
    (2012, 2013): 10600,
    (2013, 2014): 10900,
    (2014, 2015): 11000,
    (2015, 2016): 11100,
    (2016, 2017): 11100,
    (2017, 2018): 11300,
    (2018, 2019): 11700,
    (2019, 2020): 12000,
    (2020, 2021): 12300,
    (2021, 2022): 12300,
    (2022, 2023): 12300,
    (2023, 2024):  6000,
    (2024, 2025):  3000,
}


# Round if necessary, but don't quantitize if not
def dround(d:Decimal, places:int=0, rounding=None):
    assert isinstance(d, Decimal)
    _, _, exponent = d.as_tuple()
    assert isinstance(exponent, (int, str))
    if isinstance(exponent, str):
        return d
    elif exponent >= -places:
        assert exponent <= 0
        return d
    else:
        q = Decimal((0, (1,), -places))
        return d.quantize(q, rounding=rounding)


@dataclasses.dataclass
class TaxYearResult:
    tax_year: str
    disposals: list[DisposalResult] = dataclasses.field(default_factory=list)
    proceeds: Decimal = Decimal(0)
    costs: Decimal = Decimal(0)
    gains: Decimal = Decimal(0)
    losses: Decimal = Decimal(0)
    allowance: int = 0
    taxable_gain: Decimal = Decimal(0)
    carried_losses: Decimal = Decimal(0)


version = get_version()


@dataclasses.dataclass
class Result:
    warnings: list[str] = dataclasses.field(default_factory=list)
    section104_tables: dict[str, list] = dataclasses.field(default_factory=dict)
    tax_years: dict[TaxYear, TaxYearResult] = dataclasses.field(default_factory=dict)

    def add_disposal(self, disposal):

        tax_year = TaxYear.from_date(disposal.date)

        try:
            tax_year_result = self.tax_years[tax_year]
        except KeyError:
            try:
                allowance = allowances[tax_year]
            except KeyError:
                allowance = 0
                self.warnings.append(f'capital gains allowance for {tax_year} tax year unknown')

            tax_year_result = TaxYearResult(str(tax_year), allowance=allowance)
            self.tax_years[tax_year] = tax_year_result

        tax_year_result.disposals.append(disposal)
        tax_year_result.proceeds += disposal.proceeds
        tax_year_result.costs += disposal.costs
        gain = disposal.proceeds - disposal.costs
        if gain >= Decimal(0):
            tax_year_result.gains += gain
        else:
            tax_year_result.losses -= gain

        assert tax_year_result.proceeds - tax_year_result.costs == tax_year_result.gains - tax_year_result.losses

    def finalize(self):

        # https://realpython.com/sort-python-dictionary/
        self.tax_years = dict(sorted(self.tax_years.items(), key=operator.itemgetter(0)))
        assert sorted(self.tax_years) == list(self.tax_years)

        for tax_year, tyr in self.tax_years.items():
            tyr.disposals.sort(key=operator.attrgetter('date'))

            tyr.taxable_gain = max(tyr.proceeds - tyr.costs - tyr.allowance, Decimal(0))
            tyr.carried_losses = max(tyr.costs - tyr.proceeds, Decimal(0))

    def write(self, report):
        report.start()

        report.write_heading('Summary')

        if self.tax_years:
            header = self.dataclass_to_header(TaxYearResult)
            just = self.dataclass_to_just(TaxYearResult)
            just[1] = 'r' # disposals
            rows = []
            for tyr in self.tax_years.values():
                row = dataclasses.astuple(tyr, tuple_factory=list)
                row[1] = len(row[1]) # disposals
                rows.append(row)
            report.write_table(rows, header=header, just=just)
        else:
            report.write_paragraph('No disposals in range.')

        for tax_year, tyr in self.tax_years.items():
            assert tyr.disposals

            report.write_heading(f'Tax year {tax_year}')

            for no, disposal in enumerate(tyr.disposals, start=1):
                gain = disposal.proceeds - disposal.costs
                if gain < Decimal(0):
                    sign = 'LOSS'
                    gain = -gain
                else:
                    sign = 'GAIN'

                report.write_heading(f'{no}. SOLD {disposal.shares} {disposal.security} on {disposal.date} for £{disposal.proceeds} giving {sign} of £{gain}', level=3)

                footer = ('Gain', str(disposal.proceeds - disposal.costs), '')
                report.write_table(disposal.table, footer=footer, just='lrl', indent='  ')

        if self.section104_tables:
            report.write_heading('Section 104 Holdings')

            securities = list(self.section104_tables.keys())
            securities.sort()

            for security in securities:
                data = self.section104_tables[security]

                report.write_heading(security, level=2)

                self.write_table(report, data, indent='  ')

        report.write_heading('About')

        report.write_paragraph(f'Generated by cgtcalc.py version {version}.')

        report.end()

    def filter_tax_year(self, tax_year):
        try:
            tyr = self.tax_years[tax_year]
        except KeyError:
            self.tax_years = {}
        else:
            self.tax_years = {tax_year: tyr}

        assert tax_year.year1 + 1 == tax_year.year2
        start_date = tax_year.start_date()
        end_date = tax_year.end_date()

        for security, table in list(self.section104_tables.items()):
            filtered = []
            for update in table:
                if update.date <= end_date:
                    filtered.append(update)
                if update.date < start_date and not update.pool_shares and not update.pool_cost:
                    filtered = []
            if filtered:
                self.section104_tables[security] = filtered
            else:
                del self.section104_tables[security]

    @staticmethod
    def dataclass_to_header(class_or_instance):
        header = [field.name.replace('_', ' ').title().replace('Delta ', 'Δ') for field in dataclasses.fields(class_or_instance)]
        return header

    @staticmethod
    def dataclass_to_just(class_or_instance):
        just = []
        for field in dataclasses.fields(class_or_instance):
            j = 'l'
            t = field.type
            if t in (int, float, Decimal):
                j = 'r'
            if t in (datetime.date, datetime.datetime):
                j = 'c'
            just.append(j)
        return just

    def write_table(self, report, data, indent=''):
        assert data
        obj0 = data[0]
        header = self.dataclass_to_header(obj0)
        just = self.dataclass_to_just(obj0)
        rows = [dataclasses.astuple(obj) for obj in data]
        report.write_table(rows, header=header, indent=indent, just=just)


def is_close_decimal(a, b, abs_tol=Decimal('.01')):
    return abs(a - b) <= abs_tol


def update_pool(pool_updates, pool, trade, description, delta_cost=Decimal('NaN'), delta_shares=Decimal('NaN')):
    if not delta_cost.is_nan():
        pool.cost += delta_cost
        if not pool.cost:
            pool.cost = Decimal(0)
    if not delta_shares.is_nan():
        pool.shares += delta_shares

    pool_updates.append(PoolUpdate(
        date=trade.date,
        description=description.ljust(32),
        identified=abs(delta_shares),
        delta_cost=delta_cost,
        pool_shares=pool.shares,
        pool_cost=dround(pool.cost, 2),
    ))


def calculate(stream, rounding=True):

    places = 0 if rounding else 2

    # Parse
    securities: dict[str, list[Trade]] = {}

    line_no = 0
    for line in stream:
        line_no += 1
        line = line.rstrip('\n')
        if line.startswith('#'):
            continue
        row = line.split()
        if not row:
            continue

        trade, date, security = row[:3]
        params = [Decimal(field) for field in row[3:]]

        date = datetime.datetime.strptime(date, "%d/%m/%Y").date()

        # Case-insensitive
        trade = trade.upper()

        if trade in ('B', 'BUY'):
            kind = Kind.BUY
            if len(params) == 4:
                tax = params.pop(3)
                params[2] += tax
            else:
                assert len(params) == 3
        elif trade in ('S', 'SELL'):
            kind = Kind.SELL
            # Section 104 rules
            if date < datetime.date(2008, 4, 6):
                raise NotImplementedError(f'line {line_no}: {trade} {date:%d/%m/%Y} {security}: disposals before 4 April 2008 unsupported; replace earlier trades with BUY for Section 104 holding.\n')
            if len(params) == 4:
                tax = params.pop(3)
                assert not tax
            else:
                assert len(params) == 3
        elif trade == 'CAPRETURN':
            kind = Kind.CAPRETURN
        elif trade == 'DIVIDEND':
            kind = Kind.DIVIDEND
        elif trade in ('R', 'SPLIT', 'UNSPLIT'):
            raise NotImplementedError(f'line {line_no}: restructurings not yet implemented.\n')
        else:
            raise NotImplementedError(trade)

        tr = Trade(date, kind, params)

        trades = securities.setdefault(security, [])
        trades.append(tr)

    result = Result()
    result.warnings.append('cgtcalc.py is still work in progress!')

    for security, trades in securities.items():
        # Sort
        trades.sort(key=operator.attrgetter("date", "kind"))

        # Merge same-day buys/sells, as per
        # https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg51560#IDATX33F
        i = 0
        while i + 1 < len(trades):
            tr0 = trades[i + 0]
            tr1 = trades[i + 1]
            if tr0.date == tr1.date and tr0.kind == tr1.kind and tr0.kind in (Kind.BUY, Kind.SELL):
                shares0, price0, charges0 = tr0.params
                shares1, price1, charges1 = tr1.params
                shares = shares0 + shares1
                price = (shares0*price0 + shares1*price1) / shares
                charges = charges0 + charges1
                params0 = [shares, price, charges]
                trades[i] = Trade(tr0.date, tr0.kind, params0)
                trades.pop(i + 1)
            else:
                i += 1

        acquisitions = {}
        disposals = {}

        for tr in trades:
            if tr.kind == Kind.BUY:
                shares, price, charges = tr.params
                # XXX: We could track acquisition charges sepearately (and
                # round it separately) but coalescing into a single figure
                # greatly simplifies things
                cost = shares*price + charges
                cost = dround(cost, 2, ROUND_HALF_EVEN) # Compensate rounding in unit price
                cost = dround(cost, places, ROUND_CEILING)
                acquisition = Acquisition(cost, shares, shares)
                assert tr.date not in acquisitions
                acquisitions[tr.date] = acquisition
            if tr.kind == Kind.SELL:
                shares, price, charges = tr.params
                proceeds = shares*price
                proceeds = dround(proceeds, 2, ROUND_HALF_EVEN) # Compensate rounding in unit price
                proceeds = dround(proceeds, places, ROUND_FLOOR)
                charges = dround(charges, places, ROUND_CEILING)
                disposal = Disposal(proceeds, charges, shares, shares)
                assert tr.date not in disposals
                disposals[tr.date] = disposal

        # Same day rule
        for date, disposal in disposals.items():
            try:
                acquisition = acquisitions[date]
            except KeyError:
                continue
            identify(disposal, acquisition, Identification.SAME_DAY, date)

        # Bed and Breakfast rule
        for i in range(len(trades)):
            tr = trades[i]
            if tr.kind != Kind.SELL:
                continue
            disposal = disposals[tr.date]
            if not disposal.unidentified:
                continue
            j = i + 1
            for j in range(i, len(trades)):
                tr2 = trades[j]
                if (tr2.date - tr.date).days > 30:
                    break
                if tr2.kind != Kind.BUY:
                    continue
                acquisition = acquisitions[tr2.date]
                if not acquisition.unidentified:
                    continue
                identify(disposal, acquisition, Identification.BED_AND_BREAKFAST, tr2.date)

        pool_updates: list[PoolUpdate] = []

        # Walk trades chronologically:
        # - pooling unidentified shares into a Section 104 pool
        # - tracking equalisation group 1 and group 2 shares and acquisitions
        pool = Acquisition(Decimal(0), Decimal(0), Decimal(0))
        group1_holding = Decimal(0)
        group2_holding = Decimal(0)
        for tr in trades:

            if tr.kind == Kind.BUY:
                acquisition = acquisitions[tr.date]
                if acquisition.unidentified:
                    if acquisition.unidentified == acquisition.shares:
                        delta_cost = acquisition.cost
                    else:
                        delta_cost = dround(acquisition.cost * acquisition.unidentified / acquisition.shares, places, ROUND_CEILING)
                    update_pool(pool_updates, pool, tr,
                        description=f'Bought {acquisition.shares} shares for £{acquisition.cost}',
                        delta_cost=delta_cost,
                        delta_shares=acquisition.unidentified
                    )
                group2_holding += acquisition.shares

            elif tr.kind == Kind.SELL:
                disposal = disposals[tr.date]

                table = []
                table.append(('Disposal proceeds', disposal.proceeds, ''))
                if disposal.cost:
                    table.append(('Disposal costs', -disposal.cost, ''))
                for identification in disposal.identifications:
                    identified, kind, acquisition_date = identification
                    acquisition = acquisitions[acquisition_date]
                    if kind == Identification.SAME_DAY:
                        acquisition_date_desc = 'same day'
                    else:
                        assert kind == Identification.BED_AND_BREAKFAST
                        acquisition_date_desc = f'{acquisition_date} (B&B)'
                    if identified == acquisition.shares:
                        description = f'Cost of {acquisition.shares} shares acquired on {acquisition_date_desc} for £{acquisition.cost}'
                        table.append((description, -acquisition.cost, ''))
                    else:
                        description = f'Cost of {identified} shares of {acquisition.shares} acquired on {acquisition_date_desc} for £{acquisition.cost}'
                        cost = dround(acquisition.cost * identified / acquisition.shares, places, ROUND_CEILING)
                        table.append((description, -cost, f'(-{acquisition.cost} × {identified} / {acquisition.shares})'))
                if disposal.unidentified:
                    assert pool.cost > 0
                    assert pool.shares >= disposal.unidentified
                    identified = disposal.unidentified
                    if identified == pool.shares:
                        description = f'Cost of {pool.shares} shares in S.104 holding for £{pool.cost}'
                        cost = pool.cost
                        table.append((description, -cost, ''))
                    else:
                        description = f'Cost of {identified} shares of {pool.shares} in S.104 holding for £{pool.cost}'
                        cost = dround(pool.cost * identified / pool.shares, places, ROUND_CEILING)
                        table.append((description, -cost, f'({-pool.cost} × {identified} / {pool.shares})'))
                    update_pool(pool_updates, pool, tr,
                        description=f'Sold {disposal.shares} shares',
                        delta_shares = -identified,
                        delta_cost = -cost
                    )

                # Assume FIFO for notional distributions and equalisation payments
                if group1_holding >= disposal.shares:
                    group1_holding -= disposal.shares
                else:
                    group2_holding -= disposal.shares - group1_holding
                    group1_holding = Decimal(0)

                gain = Decimal(0)
                allowable_costs = Decimal(0)
                for description, cost, calculation in table:
                    if calculation:
                        assert math.isclose(eval(calculation.replace('×', '*')), cost, abs_tol=1.0)
                    gain += cost
                    if cost < Decimal(0):
                        allowable_costs -= cost

                assert gain == disposal.proceeds - allowable_costs

                result.add_disposal(DisposalResult(
                    date=tr.date,
                    security=security,
                    shares=disposal.shares,
                    proceeds=disposal.proceeds,
                    costs=allowable_costs,
                    table=table
                ))

            elif tr.kind == Kind.DIVIDEND:

                reference_holding, income = tr.params
                holding = group1_holding + group2_holding
                if not (is_close_decimal(reference_holding, holding) or is_close_decimal(reference_holding, pool.shares)):
                    result.warnings.append(f'DIVIDEND {tr.date:%d/%m/%Y} {security}: expected holding of {holding} {security} but {reference_holding} were specified')
                assert pool.shares >= holding

                # https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg57707
                # Add notional distribution to the Section 104 pool cost
                if not pool.shares:
                    raise ValueError(f'DIVIDEND {tr.date:%d/%m/%Y} {security}: no shares held on-ex-dividend date')
                income = dround(income, places, ROUND_CEILING)

                update_pool(pool_updates, pool, tr,
                    description="Notional distribution",
                    delta_cost=income,
                )

            elif tr.kind == Kind.CAPRETURN:
                reference_holding, equalisation = tr.params
                if not is_close_decimal(reference_holding, group2_holding):
                    result.warnings.append(f'CAPRETURN {tr.date:%d/%m/%Y} {security}: expected Group 2 holding of {group2_holding} {security} but {reference_holding} was specified')

                # https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg57705
                # Allocate equalisation payments to Group 2 acquisitions in proportion to the remaining holdings
                if not pool.shares:
                    raise ValueError(f'CAPRETURN {tr.date:%d/%m/%Y} {security}: no shares held on-ex-dividend date')
                assert pool.cost >= equalisation

                equalisation = dround(equalisation, places, ROUND_FLOOR)

                update_pool(pool_updates, pool, tr,
                    description="Equalisation payment",
                    delta_cost = -equalisation,
                )

                # Move Group 2 shares into Group 1
                group1_holding += group2_holding
                group2_holding = Decimal(0)

            else:  # pragma: no cover
                raise NotImplementedError(tr.kind)

        if pool_updates:
            result.section104_tables[security] = pool_updates

    result.finalize()

    return result


def main():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-y', '--tax-year', metavar='TAX_YEAR', default=None, help='tax year in XXXX/YYYY, XX/YY, YYYY, or YY format')
    argparser.add_argument('--rounding', action=argparse.BooleanOptionalAction, default=True, help='(dis)enable rounding to whole pounds')
    argparser.add_argument('--format', choices=['text', 'html'], default='text')
    argparser.add_argument('filename', metavar='FILENAME', help='file with input trades')
    args = argparser.parse_args()

    result = calculate(open(args.filename, 'rt'), rounding=args.rounding)
    if result.warnings:
        for warning in result.warnings:
            sys.stderr.write(f'warning: {warning}\n')
        sys.stderr.write('\n')

    if args.tax_year is not None:
        try:
            tax_year = TaxYear.from_string(args.tax_year)
        except ValueError as e:
            argparser.error(f'invalid tax year {args.tax_year!r}: {e}')
        result.filter_tax_year(tax_year)

    stream = sys.stdout
    report: Report
    if args.format == 'text':
        report = TextReport(stream)
    else:
        assert args.format == 'html'
        report = HtmlReport(stream)
    result.write(report)


if __name__ == '__main__':
    main()
