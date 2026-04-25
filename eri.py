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
import contextlib
import csv
import dataclasses
import datetime
import sys

from collections.abc import Callable, Iterable
from decimal import Decimal
from typing import TextIO

from cgtcalc import Calculator, PoolUpdate
from data.hmrc import exchange_rates
from report import TextReport
from tax.uk import TaxYear


def shares_held_at(pool_updates: list[PoolUpdate], date: datetime.date) -> Decimal:
    '''Return Section 104 pool shares at the end of a given date (last update on or before date).'''
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


RateLookup = Callable[[str, datetime.date], Decimal]


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


def calculate(trades_streams: Iterable[TextIO], eri_stream: TextIO, rate_lookup: RateLookup = lookup_rate) -> list[ERI]:
    '''Return ERI entries for the securities held on each reporting period end date.'''

    calculator = Calculator(rounding=False)
    for trades_stream in trades_streams:
        calculator.parse(trades_stream)
    result = calculator.calculate()

    # Map bare TIDM/ISIN (without exchange prefix) to the CGT calculator security
    security_map: dict[str, str] = {}
    for key in result.section104_tables:
        _, _, name = key.rpartition(':')
        security_map[name] = key

    entries:list[ERI] = []

    reader = csv.DictReader(eri_stream)
    for row in reader:
        entry = ERI()

        tidm = row['TIDM']
        isin = row['ISIN']

        entry.report_end_date = datetime.datetime.strptime(row['ReportEndDate'], '%d/%m/%Y').date()
        entry.currency = row['Currency']
        entry.eri_per_share = Decimal(row['ERI'])
        entry.distribution_date = datetime.datetime.strptime(row['DistributionDate'], '%d/%m/%Y').date()
        security = security_map.get(tidm) or security_map.get(isin)
        if security is None:
            continue

        # Use the CGT calculator security, so that DIVIDEND lines match the trades
        entry.security = security
        pool_updates = result.section104_tables[security]

        # ERI is due on the holding at the end of the reporting period
        # (Offshore Funds (Tax) Regulations 2009, reg. 94(3)), i.e., including
        # any trades on its last day.
        #
        # A disposal identified under the 30-day rule (TCGA 1992, s.106A) with
        # an acquisition in the next reporting period is ignored, and the
        # interest treated as still held at the end of the period (reg. 94(3A)).
        # The Section 104 pool already reflects this, since such disposals are
        # matched against the later acquisition rather than the pool.
        entry.shares = shares_held_at(pool_updates, entry.report_end_date)
        if not entry.shares:
            continue

        entry.rate = rate_lookup(entry.currency, entry.distribution_date)
        entry.eri_gbp = round(entry.shares * entry.eri_per_share / entry.rate, 2)

        entries.append(entry)

    entries.sort(key=lambda entry: (entry.distribution_date, entry.report_end_date, entry.security))

    return entries


def write_report(entries: list[ERI], stream: TextIO, dividends: bool = False) -> None:
    # ERI is treated as income on the distribution date
    yearly_entries: dict[TaxYear, list[ERI]] = {}
    for entry in entries:
        tax_year = TaxYear.from_date(entry.distribution_date)
        yearly_entries.setdefault(tax_year, []).append(entry)

    report = TextReport(stream)
    report.start('Excess Reportable Income')

    if not entries:
        report.write_paragraph('No matching securities found.')
    for tax_year in sorted(yearly_entries):
        report.write_heading(f'Tax year {tax_year}')

        year_entries = yearly_entries[tax_year]
        total_eri = sum((entry.eri_gbp for entry in year_entries), Decimal(0))
        header = ['Security', 'Report End', 'Distribution', 'Shares', 'ERI/share', 'CCY', 'Rate', 'ERI (GBP)']
        footer = ['Total', '', '', '', '', '', '', total_eri]
        rows:list[list] = [list(dataclasses.astuple(entry)) for entry in year_entries]
        report.write_table(rows, header=header, footer=footer, just='lccrrrrr', indent='  ')

    report.end()

    if dividends and entries:
        for entry in entries:
            # cgtcalc checks a DIVIDEND against the holding at the start of its
            # date (i.e., the ex-dividend date semantics), before any same-day
            # trades, whereas ERI is due on the holding at the end of the
            # reporting period (Offshore Funds (Tax) Regulations 2009, reg. 94(3)),
            # after any trades on its last day.  Therefore date the DIVIDEND on
            # the day after the reporting period end, which is effectively the
            # ex-dividend date, so both agree on the holding.
            ex_date = entry.report_end_date + datetime.timedelta(days=1)
            stream.write(f'DIVIDEND\t{ex_date:%d/%m/%Y}\t{entry.security}\t{entry.shares}\t{entry.eri_gbp}\n')


def main() -> None:
    argparser = argparse.ArgumentParser(
        description='Calculate Excess Reportable Income (ERI) from CGT trades and an ERI data CSV.'
    )
    argparser.add_argument('trades', metavar='TRADES', nargs='+', help='CGT calculator input file(s)')
    argparser.add_argument('eri_csv', metavar='ERI_CSV', help='ERI data CSV file (TIDM,ISIN,ReportEndDate,Currency,ERI,DistributionDate)')
    argparser.add_argument('--dividends', action='store_true', default=False, help='print DIVIDEND trade lines for use with cgtcalc.py')
    args = argparser.parse_args()

    with contextlib.ExitStack() as stack:
        trades_streams = [stack.enter_context(open(trades_file, 'rt')) for trades_file in args.trades]
        eri_stream = stack.enter_context(open(args.eri_csv, newline=''))
        entries = calculate(trades_streams, eri_stream)

    write_report(entries, sys.stdout, dividends=args.dividends)


if __name__ == '__main__':
    main()
