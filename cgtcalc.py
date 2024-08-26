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
from decimal import Decimal

import pandas as pd


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
    trade: str
    shares: str
    amount: Decimal
    holding: Decimal
    cost: Decimal


@dataclasses.dataclass
class DisposalResult:
    date: datetime.date
    security: str
    shares: Decimal
    proceeds: Decimal
    costs: Decimal
    identifications: list
    calculation: str


def date_to_tax_year(date: datetime.date):
    if date < date.replace(date.year, 4, 6):
        return date.year - 1, date.year
    else:
        return date.year, date.year + 1


@dataclasses.dataclass
class Result:
    disposals: list[tuple] = dataclasses.field(default_factory=list)
    section104_tables: dict[str, list] = dataclasses.field(default_factory=dict)

    def write(self, stream):

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

                proceeds = Decimal(0)
                costs = Decimal(0)
                gains = Decimal(0)
                losses = Decimal(0)

                for no, disposal in enumerate(disposals, start=1):
                    proceeds += disposal.proceeds
                    costs += disposal.costs
                    gain = disposal.proceeds - disposal.costs
                    if gain < Decimal(0):
                        sign = 'LOSS'
                        gain = -gain
                        losses += gain
                    else:
                        sign = 'GAIN'
                        gains += gain
                    stream.write(f'{no}. SOLD {disposal.shares} {disposal.security} on {disposal.date:%d/%m/%Y} for {sign} of £{gain}\n')
                    stream.write('Matches with:\n')
                    for identification in disposal.identifications:
                        stream.write(f'- {identification}\n')
                    stream.write(f'Calculation: {disposal.calculation}\n')
                    stream.write('\n')

                tax_year_short = f'{tax_year1 % 100:02d}-{tax_year2 % 100:02d}'

                stream.write(f'{tax_year_short}: Disposal Proceeds = £{proceeds} , Allowable Costs = £{costs} , Disposals = {len(disposals)}\n')
                stream.write(f'{tax_year_short}: Year Gains = £{gains}  Year Losses = £{losses}\n')
                stream.write('\n')
                stream.write('\n')

        if self.section104_tables:
            stream.write('SECTION 104\n')

            securities = list(self.section104_tables.keys())
            securities.sort()

            for security in securities:
                data = self.section104_tables[security]

                stream.write('\n')
                stream.write(f'{security}:\n')

                # TODO: Avoid Pandas
                df = pd.DataFrame(data)
                header = [name.title() for name in df.columns.to_list()]
                stream.write(df.to_string(index=False, na_rep='', header=header) + '\n')


def is_close_decimal(a, b, abs_tol=Decimal('.01')):
    return abs(a - b) <= abs_tol


def add_pool_update(pool_updates, pool, trade, shares, amount):
    pool_updates.append(PoolUpdate(
        date=trade.date,
        trade=trade.kind.name,
        shares=shares,
        amount=round(amount, 2),
        holding=pool.shares,
        cost=round(pool.cost, 2),
    ))


def calculate(filename):

    # Parse
    securities = {}

    line_no = 0
    for line in open(filename, 'rt'):
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
                sys.stderr.write(f'error: {line_no}: disposals before 6/4/2088 unsupported; replace earlier trades with BUY for Section 104 holding.\n')
                sys.exit(1)
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
            sys.stderr.write(f'error: {line_no}: restructurings not yet implemented.\n')
            sys.exit(1)
        else:
            raise NotImplementedError(trade)

        tr = Trade(date, kind, params)

        trades = securities.setdefault(security, [])
        trades.append(tr)

    result = Result()

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
                acquisition = Acquisition(shares*price + charges, shares, shares)
                assert tr.date not in acquisitions
                acquisitions[tr.date] = acquisition
            if tr.kind == Kind.SELL:
                shares, price, charges = tr.params
                disposal = Disposal(shares*price, charges, shares, shares)
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
                    pool.cost += acquisition.cost * acquisition.unidentified / acquisition.shares
                    pool.shares += acquisition.unidentified
                    add_pool_update(pool_updates, pool, tr,
                        shares=f'{acquisition.unidentified} of {acquisition.shares}',
                        amount=acquisition.cost,
                    )
                group2_holding += acquisition.shares

            elif tr.kind == Kind.SELL:
                disposal = disposals[tr.date]

                costs = []
                if disposal.cost:
                    costs.append(disposal.cost)
                identifications = []
                for identification in disposal.identifications:
                    identified, kind, acquisition_date = identification
                    acquisition = acquisitions[acquisition_date]
                    identifications.append(f'{kind.name}: {acquisition_date:%d/%m/%Y} {identified} shares of {acquisition.shares} at average cost of {round(acquisition.cost / acquisition.shares, 6)}')
                    cost = acquisition.cost * identified / acquisition.shares
                    costs.append(cost)
                if disposal.unidentified:
                    assert pool.cost > 0
                    assert pool.shares >= disposal.unidentified
                    identified = disposal.unidentified
                    cost = pool.cost * identified / pool.shares
                    costs.append(cost)
                    identifications.append(f'SECTION_104: {identified} shares of {pool.shares} at average cost of {round(pool.cost / pool.shares, 6)}')
                    pool.cost -= cost
                    pool.shares -= identified
                    add_pool_update(pool_updates, pool, tr,
                        shares=f'{disposal.unidentified} of {disposal.shares}',
                        amount=Decimal('NaN'),
                    )

                # Assume FIFO for notional income and equalisation payments
                if group1_holding >= disposal.shares:
                    group1_holding -= disposal.shares
                else:
                    group2_holding -= disposal.shares - group1_holding
                    group1_holding = Decimal(0)

                total_costs = round(sum(costs), 2)

                costs_calculation = " + ".join([str(round(cost, 2)) for cost in costs])
                if len(costs) > 1:
                    costs_calculation = f'({costs_calculation})'

                calculation = f'{disposal.proceeds} - {costs_calculation}'
                calculation += f' = {disposal.proceeds - total_costs}'

                result.disposals.append(DisposalResult(
                    date=tr.date,
                    security=security,
                    shares=disposal.shares,
                    proceeds=round(disposal.proceeds, 2),
                    costs=total_costs,
                    identifications=identifications,
                    calculation=calculation
                ))

            elif tr.kind == Kind.DIVIDEND:

                reference_holding, income = tr.params
                holding = group1_holding + group2_holding
                if not is_close_decimal(holding, reference_holding):
                    sys.stderr.write(f'warning: CAPRETURN {tr.date:%d/%m/%Y}: expected holding of {holding} {security} but {reference_holding} were specified\n')
                assert pool.shares <= holding

                # https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg57707
                # Add notional income to the Section 104 pool cost
                assert pool.shares
                pool.cost += income

                add_pool_update(pool_updates, pool, tr,
                    shares=Decimal('NaN'),
                    amount=income,
                )

            elif tr.kind == Kind.CAPRETURN:
                reference_holding, equalisation = tr.params
                if not is_close_decimal(group2_holding, reference_holding):
                    sys.stderr.write(f'warning: CAPRETURN {tr.date:%d/%m/%Y}: expected Group 2 holding of {group2_holding} {security} but {reference_holding} was specified\n')

                # https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg57705
                # Allocate equalisation payments to Group 2 acquisitions in proportion to the remaining holdings
                assert pool.shares
                assert pool.cost >= equalisation
                pool.cost -= equalisation

                add_pool_update(pool_updates, pool, tr,
                    shares=Decimal('NaN'),
                    amount=equalisation,
                )

                # Move Group 2 shares into Group 1
                group1_holding += group2_holding
                group2_holding = Decimal(0)

            else:
                raise NotImplementedError(tr.kind)


        if pool_updates:
            result.section104_tables[security] = pool_updates

    result.disposals.sort(key=operator.attrgetter('date'))

    return result


def main():
    sys.stderr.write('warning: cgtcal.py is still work in progress!\n')

    logging.basicConfig(format='%(levelname)s %(message)s', level=logging.INFO)
    for arg in sys.argv[1:]:
        result = calculate(arg)
        result.write(sys.stdout)


if __name__ == '__main__':
    main()
