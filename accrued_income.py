#!/usr/bin/env python3
#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import csv
import dataclasses
import datetime
import operator
import os.path
import sys
import typing
import warnings

from decimal import Decimal
from enum import IntEnum

import ukcalendar

from data.lse import is_tidm, is_isin
from gilts import gilts
from cgtcalc import TaxYear, TextReport


data_dir = os.path.join(os.path.dirname(__file__), 'data')
issued = gilts.Issued(csv_filename=os.path.join(data_dir, 'dmo_issued.csv'))
tidm_to_isin = {}
for isin, tidm in csv.reader(open(os.path.join(data_dir, 'tidm.csv'), 'rt')):
    tidm_to_isin[tidm] = isin


@dataclasses.dataclass
class GiltState:
    gilt: gilts.Gilt
    first_acquisition_date: datetime.date = datetime.date.max
    holding: Decimal = Decimal(0)


Kind = IntEnum('Kind', ['TRADE', 'ACCRUED_INTEREST', 'INTEREST', 'REDEMPTION'])


class Event(typing.NamedTuple):
    date: datetime.date
    isin: str
    kind: Kind

    # TRADE
    units: Decimal = Decimal('NaN')
    accrued_interest: Decimal = Decimal('NaN')

    # INTEREST
    interest: Decimal = Decimal('NaN')


footnote_mark = '†'


class Calculator:

    def __init__(self):
        self.gilt_states: dict[str, GiltState] = {}
        self.events: list[Event] = []

        today = datetime.datetime.now(datetime.timezone.utc).date()
        if today < today.replace(today.year, 4, 6):
            self.tax_year_end = today.replace(today.year, 4, 5)
        else:
            self.tax_year_end = today.replace(today.year + 1, 4, 5)

        self.provisional = False

    def parse(self, stream):
        for entry in csv.DictReader(stream):
            settlement_date = datetime.datetime.fromisoformat(entry['SettlementDate']).date()
            if not ukcalendar.is_business_day(settlement_date):
                warnings.warn("{settlement_date} is not a business day")

            security = entry['Security']

            if is_isin(security):
                isin = security
            else:
                assert is_tidm(security)
                isin = tidm_to_isin[security]

            units = Decimal(entry['Units'])
            accrued_interest = round(Decimal(entry['AccruedInterest']), 2)

            try:
                gilt_state = self.gilt_states[isin]
            except KeyError:
                gilt = issued.isin[isin]
                gilt_state = GiltState(gilt)
                self.gilt_states[isin] = gilt_state

            if units > 0:
                gilt_state.first_acquisition_date = min(gilt_state.first_acquisition_date, settlement_date)

            expected_accrued_interest = round(abs(units) * Decimal(gilt.accrued_interest(settlement_date)) * Decimal('.01'), 2)

            _, next_coupon_date = gilt.prev_next_coupon_date(settlement_date)
            #print(settlement_date.strftime('%a %d %b %Y'), isin, gilt.short_name(), units, accrued_interest, expected_accrued_interest)
            if abs(accrued_interest - expected_accrued_interest) > Decimal(.01):
                xd_date = gilt.ex_dividend_date(next_coupon_date)
                div = 'cum div' if settlement_date <= xd_date else 'ex div'
                warnings.warn(f'{settlement_date}, {units} x {gilt.short_name()}, {div}: expected accrued interest of {expected_accrued_interest}, got {accrued_interest}\n')

            # Shuft holding adjustments by 7 business days to account for ex-dividend period
            cum_div_date = settlement_date
            for i in range(7):
                cum_div_date = ukcalendar.next_business_day(cum_div_date)

            self.events.append(Event(cum_div_date, isin, Kind.TRADE, units=units))
            self.events.append(Event(settlement_date, isin, Kind.ACCRUED_INTEREST, units=units, accrued_interest=accrued_interest))

    def process(self):
        self.process_gilts()
        self.process_events()

    def process_gilts(self):
        for isin, gilt_state in self.gilt_states.items():
            settlement_date = gilt_state.first_acquisition_date
            gilt = gilt_state.gilt
            cash_flows = list(gilt.cash_flows(settlement_date))
            for date, cash in cash_flows[:-1]:
                interest = Decimal(cash) * Decimal('.01')
                self.events.append(Event(date, isin, Kind.INTEREST, interest=interest))

            self.events.append(Event(gilt.maturity, gilt.isin, Kind.REDEMPTION))

        self.events.sort(key=operator.attrgetter('date', 'isin', 'kind'))

    def process_events(self):
        accrued_incomes = []
        for ev in self.events:
            if ev.date >= self.tax_year_end:
                continue

            gilt_state = self.gilt_states[ev.isin]
            gilt = gilt_state.gilt
            if ev.kind == Kind.TRADE:
                gilt_state.holding += ev.units
                assert gilt_state.holding >= Decimal(0)
            elif ev.kind == Kind.ACCRUED_INTEREST:
                if ev.units >= Decimal(0):
                    # Buy
                    accrued_income = -ev.accrued_interest
                    verb = 'Bought'
                else:
                    # Sell
                    accrued_income = ev.accrued_interest
                    verb = 'Sold'
                description = f'{verb} nominal £{abs(ev.units)}'

                _, next_coupon_date = gilt.prev_next_coupon_date(ev.date)
                accrued_incomes.append((next_coupon_date, ev.date, gilt, description, accrued_income))
            elif ev.kind == Kind.INTEREST:
                if gilt_state.holding > Decimal(0):
                    interest = round(gilt_state.holding * Decimal(ev.interest), 2)
                    description = f'Interest of nominal £{gilt_state.holding}'
                    if isinstance(gilt, gilts.IndexLinkedGilt):
                        if not gilt.is_fixed(ev.date):
                            self.provisional = True
                            description += footnote_mark
                    accrued_incomes.append((ev.date, ev.date, gilt, description, interest))
            else:
                assert ev.kind == Kind.REDEMPTION
                gilt_state.holding = Decimal(0)

        accrued_incomes.sort(key=operator.itemgetter(0, 1))

        self.yearly_acrued_income: dict[TaxYear, list[tuple[datetime.date, datetime.date, gilts.Gilt, str, Decimal]]] = {}
        for interest_date, date, gilt, description, income in accrued_incomes:
            tax_year = TaxYear.from_date(interest_date)
            year_acrued_income = self.yearly_acrued_income.setdefault(tax_year, [])
            year_acrued_income.append((interest_date, date, gilt, description, income))

    def report(self, report):
        tax_years = list(self.yearly_acrued_income.keys())
        tax_years.sort()

        for tax_year in tax_years:
            report.write_heading(f'Tax year {tax_year}')

            header = ['Interest date', 'Gilt', 'Transaction date', 'Description', 'Income']
            rows: list[tuple[typing.Any, ...]] = []
            total = Decimal(0)
            for interest_date, date, gilt, description, income in self.yearly_acrued_income[tax_year]:
                rows.append((interest_date, gilt.short_name(), date, description, income))
                total += income
            footer = ['Total', '', '', ' '*32, total]
            report.write_table(rows, header=header, footer=footer, just='llllr', indent='  ')

        # Holdings
        report.write_heading('Final holdings')
        header = ['Gilt', 'Holding']
        rows = []
        for gilt_state in self.gilt_states.values():
            gilt = gilt_state.gilt
            rows.append((gilt.short_name(), gilt_state.holding))
        report.write_table(rows, header=header, just='lr', indent='  ')

        # https://www.gov.uk/hmrc-internal-manuals/self-assessment-manual/sam121190
        if self.provisional:
            report.write_heading('Footnotes')
            report.write_paragraph(footnote_mark + ' Provisional figures')


def main():
    calculator = Calculator()
    for arg in sys.argv[1:]:
        calculator.parse(open(arg, 'rt'))
    calculator.process()
    report = TextReport(sys.stdout)
    calculator.report(report)


if __name__ == '__main__':
    main()
