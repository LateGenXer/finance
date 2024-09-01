#!/usr/bin/env python3
#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#

#
# Python CGT calculator, inspired by http://cgtcalculator.com/ and
# https://github.com/mattjgalloway/cgtcalc
#
# Usage:
#
#   python cgtcalc.py input.tsv
#
# Accepts input in both formats:
# - http://cgtcalculator.com/instructions.htm#tradeformat
# - https://github.com/mattjgalloway/cgtcalc?tab=readme-ov-file#input-data
#


import dataclasses
import datetime
import logging
import math
import operator
import sys
import typing

from collections import namedtuple
from enum import IntEnum, Enum
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_CEILING, ROUND_FLOOR


logger = logging.getLogger('cgtcalc')


Kind = IntEnum('Kind', ['DIVIDEND', 'CAPRETURN', 'BUY', 'SELL'])


assert Kind.CAPRETURN < Kind.BUY

Trade = namedtuple('Trade', ['date', 'kind', 'params'])

# https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg51560
Identification = Enum('Identification', ['SAME_DAY', 'BED_AND_BREAKFAST', 'POOL'])

@dataclasses.dataclass
class Acquisition:
    cost: Decimal
    shares: Decimal

    unidentified: Decimal


@dataclasses.dataclass
class Disposal:
    proceeds: Decimal
    cost: Decimal
    shares: Decimal
    unidentified: Decimal
    identifications: list[tuple] = dataclasses.field(default_factory=list)


def identify(disposal, acquisition, kind, acquisition_date):
    assert disposal.unidentified > 0.0
    assert acquisition.unidentified > 0.0
    identified = min(disposal.unidentified, acquisition.unidentified)
    acquisition.unidentified -= identified
    assert acquisition.unidentified >= 0.0
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
    charges: Decimal
    costs: Decimal
    table: list


def date_to_tax_year(date: datetime.date):
    if date < date.replace(date.year, 4, 6):
        return date.year - 1, date.year
    else:
        return date.year, date.year + 1




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
allowance_latest = allowances[next(reversed(allowances))]


def dround(d, places=0, rounding=None):
    assert isinstance(d, Decimal)
    _, _, exponent = d.as_tuple()
    if exponent == 'n':
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
    disposals: int = 0
    proceeds: Decimal = Decimal(0)
    costs: Decimal = Decimal(0)
    gains: Decimal = Decimal(0)
    losses: Decimal = Decimal(0)
    allowance: int = 0
    taxable_gain: Decimal = Decimal(0)
    carried_losses: Decimal = Decimal(0)


@dataclasses.dataclass
class Result:
    warnings: list[str] = dataclasses.field(default_factory=list)
    disposals: list[tuple] = dataclasses.field(default_factory=list)
    section104_tables: dict[str, list] = dataclasses.field(default_factory=dict)
    tax_years: dict[tuple[int, int], TaxYearResult] = dataclasses.field(default_factory=dict)

    def add_disposal(self, disposal):
        self.disposals.append(disposal)

        tax_year = date_to_tax_year(disposal.date)

        try:
            tax_year_result = self.tax_years[tax_year]
        except KeyError:
            try:
                allowance = allowances[tax_year]
            except KeyError:
                allowance = allowance_latest
                self.warnings.append(f'warning: capital gains allowance for {tax_year[0]}/{tax_year[1]} tax year unknown, presuming £{allowance}')

            tax_year_result = TaxYearResult(f'{tax_year[0]}/{tax_year[1]}', allowance=allowance)
            self.tax_years[tax_year] = tax_year_result

        tax_year_result.disposals += 1
        tax_year_result.proceeds += disposal.proceeds
        tax_year_result.costs += disposal.costs
        gain = disposal.proceeds - disposal.costs
        if gain < Decimal(0):
            tax_year_result.losses += -gain
        else:
            tax_year_result.gains += gain

    def sorted_tax_years(self):
        tax_years = list(self.tax_years.keys())
        tax_years.sort()
        return tax_years

    def finalize(self):
        self.disposals.sort(key=operator.attrgetter('date'))

        for tax_year in self.sorted_tax_years():
            tyr = self.tax_years[tax_year]

            tyr.taxable_gain = max(tyr.proceeds - tyr.costs - tyr.allowance, 0)
            tyr.carried_losses = max(tyr.costs - tyr.proceeds, 0)

    def write(self, stream):
        if self.tax_years:
            stream.write('SUMMARY\n\n')

            data = [self.tax_years[tax_year] for tax_year in self.sorted_tax_years()]
            self.write_table(stream, data)

            stream.write('\n\n')

        if self.disposals:
            disposals_by_tax_year = {}
            for disposal in self.disposals:
                tax_year = date_to_tax_year(disposal.date)
                disposals_by_tax_year.setdefault(tax_year, []).append(disposal)

            tax_years = list(disposals_by_tax_year.keys())
            tax_years.sort()

            for tax_year in tax_years:
                tax_year1, tax_year2 = tax_year

                stream.write(f'TAX YEAR {tax_year1}/{tax_year2}\n')
                stream.write('\n')

                disposals = disposals_by_tax_year[tax_year]

                for no, disposal in enumerate(disposals, start=1):
                    gain = disposal.proceeds - disposal.costs
                    if gain < Decimal(0):
                        sign = 'LOSS'
                        gain = -gain
                    else:
                        sign = 'GAIN'
                    stream.write(f'{no}. SOLD {disposal.shares} {disposal.security} on {disposal.date:%d/%m/%Y} for £{disposal.proceeds} giving {sign} of £{gain}\n\n')

                    footer = ('Gain', str(disposal.proceeds - disposal.costs), '')
                    self._write_table(stream, disposal.table, footer=footer, indent='  ')
                    stream.write('\n')

                stream.write('\n')

        if self.section104_tables:
            stream.write('SECTION 104 HOLDINGS\n')

            securities = list(self.section104_tables.keys())
            securities.sort()

            for security in securities:
                data = self.section104_tables[security]

                stream.write('\n')
                stream.write(f'{security}\n\n')

                self.write_table(stream, data, indent='  ')

    def write_table(self, stream, data, indent=''):
        assert data
        # TODO: Avoid Pandas
        obj0 = data[0]
        header = [field.name.replace('_', ' ').title().replace('Delta ', 'Δ') for field in dataclasses.fields(obj0)]
        rows = [dataclasses.astuple(obj) for obj in data]
        self._write_table(stream, rows, header=header, indent=indent)

    def _write_table(self, stream, rows, header=None, footer=None, indent=''):
        columns = [list(col) for col in zip(*rows)]
        if header is not None:
            header = list(header)
            assert len(header) == len(columns)
        if footer is not None:
            footer = list(footer)
            assert len(footer) == len(columns)

        widths = []
        for c in range(len(columns)):
            width = 0
            if header is not None:
                width = max(width, len(header[c]))
            if footer is not None:
                width = max(width, len(footer[c]))
            column = columns[c]
            header_just = str.center
            cell_just = str.rjust
            for r in range(len(column)):
                cell = column[r]
                if isinstance(cell, str):
                    header_just = str.ljust
                    cell_just = str.ljust
                else:
                    if cell != cell:
                        # NaN
                        cell = ''
                    cell = str(cell)
                    column[r] = cell
                width = max(width, len(cell))
            if header is not None:
                header[c] = header_just(header[c], width)
            for r in range(len(column)):
                column[r] = cell_just(column[r], width)
            if footer is not None:
                footer[c] = cell_just(str(footer[c]), width)
            widths.append(width)

        sep = '  '

        line_width = len(sep.join([' '*width for width in widths]))
        rule = '─' * line_width

        if header is not None:
            stream.write(indent + sep.join(header).rstrip() + '\n')
            stream.write(indent + rule + '\n')
        for row in zip(*columns):
            stream.write(indent + sep.join(row).rstrip() + '\n')
        if footer is not None:
            stream.write(indent + rule + '\n')
            stream.write(indent + sep.join(footer).rstrip() + '\n')


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


def calculate(stream):

    # Parse
    securities = {}

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
                raise NotImplementedError('line {line_no}: disposals before 6/4/2088 unsupported; replace earlier trades with BUY for Section 104 holding.\n')
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
        logger.debug('~~~~~~~~ %s ~~~~~~~~~', security)

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
                params = (shares, price, charges)
                trades[i] = Trade(tr0.date, tr0.kind, params)
                trades.pop(i + 1)
            else:
                i += 1

        if logger.isEnabledFor(logging.DEBUG):
            for tr in trades:
                logger.debug('%s %s\t%s', tr.date, tr.kind.name, '\t'.join([str(param) for param in tr.params]))

        acquisitions = {}
        disposals = {}

        for tr in trades:
            if tr.kind == Kind.BUY:
                shares, price, charges = tr.params
                cost = shares*price
                cost = dround(cost, 2, ROUND_HALF_EVEN) # Compensate rounding in unit price
                cost = dround(cost, 0, ROUND_CEILING)
                cost += dround(charges, 0, ROUND_CEILING)
                acquisition = Acquisition(cost, shares, shares)
                assert tr.date not in acquisitions
                acquisitions[tr.date] = acquisition
            if tr.kind == Kind.SELL:
                shares, price, charges = tr.params
                proceeds = shares*price
                proceeds = dround(proceeds, 2, ROUND_HALF_EVEN) # Compensate rounding in unit price
                proceeds = dround(proceeds, 0, ROUND_FLOOR)
                charges = dround(charges, 0, ROUND_CEILING)
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

        pool_updates = []

        # Walk trades chronologically:
        # - pooling unidentified shares into a Secion 104 pool
        # - tracking equalisation group 1 and group 2 shares and acquisitions
        pool = Acquisition(0, 0, 0)
        group1_holding = Decimal(0)
        group2_holding = Decimal(0)
        for tr in trades:

            if tr.kind == Kind.BUY:
                acquisition = acquisitions[tr.date]
                if acquisition.unidentified:
                    if acquisition.unidentified == acquisition.shares:
                        delta_cost = acquisition.cost
                    else:
                        delta_cost = dround(acquisition.cost * acquisition.unidentified / acquisition.shares, 0, ROUND_CEILING)
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
                        cost = dround(acquisition.cost * identified / acquisition.shares, 0, ROUND_CEILING)
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
                        cost = dround(pool.cost * identified / pool.shares, 0, ROUND_CEILING)
                        table.append((description, -cost, f'({-pool.cost} × {identified} / {pool.shares})'))
                    update_pool(pool_updates, pool, tr,
                        description=f'Sold {disposal.shares} shares',
                        delta_shares = -identified,
                        delta_cost = -cost
                    )

                # Assume FIFO for notional income and equalisation payments
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
                    charges=disposal.cost,
                    costs=allowable_costs,
                    table=table
                ))

            elif tr.kind == Kind.DIVIDEND:

                reference_holding, income = tr.params
                holding = group1_holding + group2_holding
                if not (is_close_decimal(reference_holding, holding) or is_close_decimal(reference_holding, pool.shares)):
                    result.warnings.append(f'DIVIDEND {tr.date:%d/%m/%Y}: expected holding of {holding} {security} but {reference_holding} were specified')
                assert pool.shares >= holding

                # https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg57707
                # Add notional income to the Section 104 pool cost
                assert pool.shares
                income = dround(income, 0, ROUND_CEILING)

                update_pool(pool_updates, pool, tr,
                    description="Notional distribution",
                    delta_cost=income,
                )

            elif tr.kind == Kind.CAPRETURN:
                reference_holding, equalisation = tr.params
                if not is_close_decimal(reference_holding, group2_holding):
                    result.warning(f'CAPRETURN {tr.date:%d/%m/%Y}: expected Group 2 holding of {group2_holding} {security} but {reference_holding} was specified')

                # https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg57705
                # Allocate equalisation payments to Group 2 acquisitions in proportion to the remaining holdings
                assert pool.shares
                assert pool.cost >= equalisation

                equalisation = dround(equalisation, 0, ROUND_FLOOR)

                update_pool(pool_updates, pool, tr,
                    description="Equalisation payment",
                    delta_cost = -equalisation,
                )

                # Move Group 2 shares into Group 1
                group1_holding += group2_holding
                group2_holding = Decimal(0)

            else:
                raise NotImplementedError(tr.kind)


        if pool_updates:
            result.section104_tables[security] = pool_updates

    result.finalize()

    return result


def main():
    logging.basicConfig(format='%(levelname)s %(message)s', level=logging.INFO)
    for arg in sys.argv[1:]:
        result = calculate(open(arg, 'rt'))
        if result.warnings:
            for warning in result.warnings:
                sys.stderr.write(warning + '\n')
            sys.stderr.write('\n')
        result.write(sys.stdout)


if __name__ == '__main__':
    main()
