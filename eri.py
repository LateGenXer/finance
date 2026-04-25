#!/usr/bin/env python3
#
# Copyright (c) 2024-2026 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


#
# Excess Reportable Income (ERI) calculator.
#
# Reads a CGT calculator input file to determine share holdings over time, then
# applies per-share ERI figures from a CSV file to calculate the total ERI
# income due on each reporting period end date.
#
# ERI CSV columns: TIDM, ISIN, ReportEndDate, Currency, ERI, DistributionDate
#


import argparse
import csv
import dataclasses
import datetime
import sys

from decimal import Decimal

from cgtcalc import Calculator, PoolUpdate
from data.hmrc import exchange_rates
from report import TextReport


def shares_held_at(pool_updates: list[PoolUpdate], date: datetime.date) -> Decimal:
    '''Return Section 104 pool shares on a given date (last update on or before date).'''
    shares = Decimal(0)
    for update in pool_updates:
        if update.date > date:
            break
        shares = update.pool_shares
    return shares


def lookup_rate(currency: str, date: datetime.date) -> Decimal:
    '''Return HMRC monthly exchange rate (foreign currency units per GBP) for the given month.'''
    if currency == 'GBP':
        return Decimal(1)
    rates = exchange_rates(date.year, date.month)
    return rates[currency]


@dataclasses.dataclass
class ERI:
    security:str = ''
    report_end_date:datetime.date = datetime.date(datetime.MINYEAR, 1, 1)
    distribution_date:datetime.date = datetime.date(datetime.MINYEAR, 1, 1)
    shares:Decimal = Decimal(0)
    eri_per_share:Decimal = Decimal(0)
    currency: str = ''
    rate: Decimal = Decimal(0)
    eri_gbp: Decimal = Decimal(0)


def main() -> None:
    argparser = argparse.ArgumentParser(
        description='Calculate Excess Reportable Income (ERI) from CGT trades and an ERI data CSV.'
    )
    argparser.add_argument('trades', metavar='TRADES', nargs='+', help='CGT calculator input file(s)')
    argparser.add_argument('eri_csv', metavar='ERI_CSV', help='ERI data CSV file (TIDM,ISIN,ReportEndDate,Currency,ERI,DistributionDate)')
    argparser.add_argument('--dividends', action='store_true', default=False, help='print DIVIDEND trade lines for use with cgtcalc.py')
    args = argparser.parse_args()

    calculator = Calculator(rounding=False)
    for trades_file in args.trades:
        with open(trades_file, 'rt') as f:
            calculator.parse(f)
    result = calculator.calculate()

    pool_updates: list[PoolUpdate] | None
    security_map: dict[str, list[PoolUpdate]] = {}
    for security, pool_updates in result.section104_tables.items():
        try:
            _, security = security.split(':')
        except ValueError:
            pass
        security_map[security] = pool_updates

    total_eri = Decimal(0)
    entries:list[ERI] = []

    with open(args.eri_csv, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            entry = ERI()

            tidm = row['TIDM']
            isin = row['ISIN']
            entry.security = tidm or isin

            entry.report_end_date = datetime.datetime.strptime(row['ReportEndDate'], '%d/%m/%Y').date()
            entry.currency = row['Currency']
            entry.eri_per_share = Decimal(row['ERI'])
            entry.distribution_date = datetime.datetime.strptime(row['DistributionDate'], '%d/%m/%Y').date()
            pool_updates = security_map.get(tidm) or security_map.get(isin)
            if pool_updates is None:
                continue

            entry.shares = shares_held_at(pool_updates, entry.report_end_date)
            if not entry.shares:
                continue

            entry.rate = lookup_rate(entry.currency, entry.distribution_date)
            entry.eri_gbp = round(entry.shares * entry.eri_per_share / entry.rate, 2)

            entries.append(entry)
            total_eri += entry.eri_gbp

    report = TextReport(sys.stdout)
    report.start('Excess Reportable Income')

    if not entries:
        report.write_paragraph('No matching securities found.')
    else:
        header = ['Security', 'Report End', 'Distribution', 'Shares', 'ERI/share', 'CCY', 'Rate', 'ERI (GBP)']
        footer = ['Total', '', '', '', '', '', '', total_eri]
        rows:list[list] = [list(dataclasses.astuple(entry)) for entry in entries]
        report.write_table(rows, header=header, footer=footer, just='lccrrrrr')

    report.end()

    if args.dividends and entries:
        for entry in entries:
            print(f'DIVIDEND\t{entry.report_end_date:%d/%m/%Y}\t{entry.security}\t{entry.shares}\t{entry.eri_gbp}')


if __name__ == '__main__':
    main()
