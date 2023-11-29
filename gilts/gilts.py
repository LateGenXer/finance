#!/usr/bin/env python3
#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import csv
import datetime
import dataclasses
import enum
import json
import math
import numbers
import re
import operator
import os.path
import typing
import sys

import xml.etree.ElementTree

import requests

from pprint import pp

from download import download

import scipy.optimize as optimize

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

if int(os.environ.get('PULP', '0')) != 0:
    import pulp as lp
else:
    # XXX move lp into a shared folder
    # https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly
    import importlib.util
    _spec = importlib.util.spec_from_file_location('lp', os.path.join(os.path.dirname(__file__), '..', 'rtp', 'lp.py'))
    lp = importlib.util.module_from_spec(_spec)
    sys.modules['lp'] = lp
    _spec.loader.exec_module(lp)
    del _spec

from xirr import *
from ukbankholidays import next_business_day, prev_business_day
from lse import GiltPrices



# https://www.dmo.gov.uk/responsibilities/gilt-market/about-gilts/
class Gilt:

    type_ = 'Conventional'

    def __init__(self, isin, coupon, maturity, issue_date):
        assert isinstance(isin, str) and len(isin) == 12
        self.isin = isin
        assert isinstance(coupon, numbers.Number)
        self.coupon = coupon
        assert isinstance(maturity, datetime.date)
        self.maturity = maturity
        self.issue_date = issue_date

    @staticmethod
    def previous_coupon_date(d):
        assert isinstance(d, datetime.date)
        if d.month >= 7:
            return d.replace(d.year, d.month - 6, d.day)
        else:
            return d.replace(d.year - 1, d.month + 6, d.day)

    def coupon_dates(self, settlement_date):
        assert settlement_date <= self.maturity
        next_coupon_dates = []
        prev_coupon_date = self.maturity
        while True:
            next_coupon_dates.append(prev_coupon_date)
            prev_coupon_date = self.previous_coupon_date(prev_coupon_date)
            if prev_coupon_date < settlement_date:
                previous_coupon_date = prev_coupon_date
                break
        next_coupon_dates.reverse()
        return prev_coupon_date, next_coupon_dates

    def prev_next_coupon_date(self, settlement_date):
        prev_coupon_date, next_coupon_dates = self.coupon_dates(settlement_date=settlement_date)
        return prev_coupon_date, next_coupon_dates[0]

    @staticmethod
    def ex_dividend_date(coupon_date):
        xd_date = coupon_date
        for i in range(7):
            xd_date = prev_business_day(xd_date)
        return xd_date

    # https://www.dmo.gov.uk/media/1sljygul/yldeqns.pdf Section 3
    # https://docs.londonstockexchange.com/sites/default/files/documents/calculator.xls
    # https://docs.londonstockexchange.com/sites/default/files/documents/accrued-interest-gilts.pdf
    def accrued_interest(self, settlement_date):
        prev_coupon_date, next_coupon_date = self.prev_next_coupon_date(settlement_date)

        full_coupon_days = (next_coupon_date - prev_coupon_date).days

        assert self.issue_date is not None
        if prev_coupon_date >= self.issue_date:
            interest_days = (settlement_date - prev_coupon_date).days
            coupon_days = full_coupon_days
        else:
            # See DMO's Formulae for Calculating Gilt Prices from Yields, Section 3, (2), Short first dividend periods
            interest_days = (settlement_date - self.issue_date).days
            coupon_days = (next_coupon_date - self.issue_date).days

        coupon = self.coupon / 2

        xd_date = self.ex_dividend_date(next_coupon_date)

        if settlement_date < xd_date:
            accrued_interest = interest_days/full_coupon_days * coupon
        else:
            accrued_interest = (interest_days - coupon_days)/full_coupon_days * coupon

        return accrued_interest

    def dirty_price(self, clean_price, settlement_date):
        return clean_price + self.accrued_interest(settlement_date=settlement_date)

    def clean_price(self, dirty_price, settlement_date):
        return dirty_price - self.accrued_interest(settlement_date=settlement_date)

    def cash_flows(self, settlement_date):
        prev_coupon_date, next_coupon_dates = self.coupon_dates(settlement_date=settlement_date)

        transactions = []

        if prev_coupon_date < self.issue_date:
            next_coupon_date = next_coupon_dates.pop(0)
            r = (settlement_date - self.issue_date).days/(next_coupon_date - prev_coupon_date).days
            transactions.append((next_coupon_date, r*self.coupon/2))

        for next_coupon_date in next_coupon_dates:
            transactions.append((next_coupon_date, self.coupon/2))

        transactions.append((self.maturity, 100))

        return transactions

    def ytm(self, dirty_price, settlement_date):
        # https://www.dmo.gov.uk/media/1sljygul/yldeqns.pdf , Section 1: price/yield formulae
        # https://www.lseg.com/content/dam/ftse-russell/en_us/documents/ground-rules/ftse-actuaries-uk-gilts-index-series-guide-to-calc.pdf Section 6, Formulae – applying to conventional gilts only

        #print()
        #print(self.short_name())

        P = dirty_price

        prev_coupon_date, next_coupon_dates = self.coupon_dates(settlement_date=settlement_date)
        next_coupon_date = next_coupon_dates[0]
        n = len(next_coupon_dates) - 1

        r = (next_coupon_date - settlement_date).days
        assert r > 0
        s = (next_coupon_date - prev_coupon_date).days
        assert s > 0

        c = self.coupon
        f = 2
        d1 = c/f
        d2 = c/f

        if prev_coupon_date < self.issue_date:
            d1 *= (next_coupon_date - self.issue_date).days/(next_coupon_date - prev_coupon_date).days

        xd_date = self.ex_dividend_date(next_coupon_date)
        if settlement_date >= xd_date:
            d1 = 0

        if False:
            print()
            print('settlement_date', settlement_date)
            print('xd_date', xd_date)
            print('prev_coupon_date', prev_coupon_date)
            print('next_coupon_date', next_coupon_date)
            print('P', P)
            print('n', n)
            print('c', c)
            print('d1', d1)
            print('d2', d2)
            print('r', r)
            print('s', s)

        def fn(y):
            v = 1 / (1 + y / f)
            return v**(r/s) * (d1 + d2 * v + c * v**2 / (f * (1 - v)) * (1 - v**(n - 1)) + 100 * v**n) - P

        if n > 0:
            y = optimize.newton(fn, .05)
        else:
            y = ((d1 + 100) / P - 1) / (r / 365)

        return y

    def value(self, rate, settlement_date):
        transactions = []
        transactions.append((settlement_date, 0))
        transactions.extend(self.cash_flows(settlement_date=settlement_date))

        dates, values = zip(*transactions)
        npv = xnpv(rate, values, dates)

        return npv

    def short_name(self):
        return f'{self.coupon:.3f}% {self.maturity}'


class IndexLinkedGilt(Gilt):

    type_ = 'Index-linked'

    def __init__(self, isin, coupon, maturity, issue_date, base_rpi):
        Gilt.__init__(self, isin, coupon, maturity, issue_date=issue_date)
        self.base_rpi = base_rpi
        self.lag = 3 if issue_date >= datetime.date(2005, 9, 22) else 8

    # https://www.dmo.gov.uk/media/0ltegugd/igcalc.pdf
    def ref_date(self, settlement_date):
        if self.lag == 3:
            return lagged_date(settlement_date, months=3)
        else:
            assert self.lag == 8
            next_coupon_date = self.maturity
            while self.previous_coupon_date(next_coupon_date) >= settlement_date:
                next_coupon_date = Gilt.previous_coupon_date(next_coupon_date)
            return lagged_date(next_coupon_date, months=8).replace(day = 1)

    def ref_rpi(self, settlement_date):
        ref_date = self.ref_date(settlement_date)
        return rpi.estimate(ref_date)

    def index_ratio(self, settlement_date):
        return round(self.ref_rpi(settlement_date) / self.base_rpi, 5)

    def dirty_price(self, clean_price, settlement_date):
        # For index-linked gilts with a 3-month indexation lag, the quoted price is the real clean price.
        if self.lag == 3:
            clean_price *= self.index_ratio(settlement_date)
        return clean_price + self.accrued_interest(settlement_date=settlement_date)

    def clean_price(self, dirty_price, settlement_date):
        clean_price = dirty_price - self.accrued_interest(settlement_date=settlement_date)
        if self.lag == 3:
            clean_price /= self.index_ratio(settlement_date)
        return clean_price

    def accrued_interest(self, settlement_date):
        accrued_interest = Gilt.accrued_interest(self, settlement_date=settlement_date)
        accrued_interest *= self.index_ratio(settlement_date)
        return accrued_interest

    def cash_flows(self, settlement_date):
        for date, value in Gilt.cash_flows(self, settlement_date=settlement_date):
            ref_date = self.ref_date(date)
            index_ratio = rpi.estimate(ref_date) / self.base_rpi
            # Round to 6 decimal places, per https://www.dmo.gov.uk/media/0ltegugd/igcalc.pdf
            # Annex: Rounding Conventions for Interest and Redemption Cash Flows for Index-linked Gilts
            value = round(value * index_ratio, 6)
            yield date, value

    def ytm(self, dirty_price, settlement_date):
        # XXX: This is not the standard formula, but it's very difficult to
        # match published figures (e.g, Tradeweb) as there's lot of leeway in
        # the handling of the indexation.

        transactions = []
        transactions.append((settlement_date, -dirty_price))
        transactions.extend(self.cash_flows(settlement_date=settlement_date))

        dates, values = zip(*transactions)
        ytm = xirr(values, dates)

        return ytm

    def short_name(self):
        return f'{self.coupon:.3f}% IL {self.maturity}'


class Issued:

    def __init__(self, entries=None):
        if entries is None:
            entries = self.load_xml()

        self.all = []
        for entry in entries:
            kwargs = {
                'isin': entry['ISIN_CODE'],
                'coupon': self._parse_coupon(entry['INSTRUMENT_NAME']),
                'maturity': datetime.datetime.fromisoformat(entry['REDEMPTION_DATE']).date(),
                'issue_date': datetime.datetime.fromisoformat(entry['FIRST_ISSUE_DATE']).date(),
            }
            type_ = entry['INSTRUMENT_TYPE']
            if type_ == 'Conventional ':
                gilt = Gilt(**kwargs)
            else:
                mo = re.match(r'^Index-linked (3|8) months$', type_)
                assert mo
                lag = int(mo.group(1))
                assert lag == 3 if kwargs['issue_date'] >= datetime.date(2005, 9, 22) else 8
                kwargs['base_rpi'] = float(entry['BASE_RPI_87'])
                gilt = IndexLinkedGilt(**kwargs)

            # Check ex-divdend dates match when loading DMO's XML
            try:
                current_xd_date = datetime.datetime.fromisoformat(entry['CURRENT_EX_DIV_DATE']).date()
                close_date = datetime.datetime.fromisoformat(entry['CLOSE_OF_BUSINESS_DATE']).date()
            except KeyError:
                pass
            else:
                settlement_date = next_business_day(close_date)
                _, next_coupon_date = gilt.prev_next_coupon_date(settlement_date)
                assert gilt.ex_dividend_date(next_coupon_date) == current_xd_date

            self.all.append(gilt)

        self.all.sort(key=operator.attrgetter('maturity'))

        self.isin = {gilt.isin: gilt for gilt in self.all}

    # https://www.dmo.gov.uk/data/
    @staticmethod
    def load_xml():
        filename = os.path.join(os.path.dirname(__file__), 'dmo-D1A.xml')
        download('https://www.dmo.gov.uk/data/XmlDataReport?reportCode=D1A', filename, ttl=12*3600, content_type='text/xml')
        stream = open(filename, 'rt')
        tree = xml.etree.ElementTree.parse(stream)
        root = tree.getroot()
        for node in root:
            yield node.attrib

    @staticmethod
    def load_csv():
        filename = os.path.join(os.path.dirname(__file__), 'dmo-D1A.csv')
        stream = open(filename, 'rt')
        return csv.DictReader(stream)

    _coupon_re = re.compile(r'^(?P<unit>[0-9]+) ?(?P<fraction>|½|¼|¾|[1357]/8) ?%$')
    _fractions = {
        '':    0.000,
        '1/8': 0.125, # ⅛
        '¼':   0.250,
        '3/8': 0.375, # ⅜
        '½':   0.500,
        '5/8': 0.625, # ⅝
        '¾':   0.750,
        '7/8': 0.875, # ⅞
    }
    @classmethod
    def _parse_coupon(cls, name):
        # Derive coupon from name
        coupon = name[:name.index('%') + 1]
        mo = cls._coupon_re.match(coupon)
        assert mo
        return float(mo.group('unit')) + cls._fractions[mo.group('fraction')]

    def filter(self, index_linked):
        type_ = 'Index-linked' if index_linked else 'Conventional'
        for g in self.all:
            if g.type_ == type_:
                yield g


from rpi import RPI

rpi = RPI()


def lagged_date(date, months):
    assert months <= 12
    if date.month > months:
        return date.replace(month=date.month - months)
    else:
        return date.replace(year=date.year - 1, month=date.month + 12 - months)


def yield_curve(issued, prices, index_linked=False):
    today = datetime.datetime.utcnow().date()
    settlement_date = next_business_day(today)
    data = []
    for g in issued.filter(index_linked):
        isin = g.isin
        tidm = prices.lookup_tidm(isin)
        clean_price = prices.get_price(tidm)
        dirty_price = g.dirty_price(clean_price, settlement_date)

        ytm = g.ytm(dirty_price, settlement_date) * 100.0
        maturity = (g.maturity - today).days / 365.0
        data.append((maturity, ytm, tidm))

    return pd.DataFrame(data, columns=['Maturity', 'Yield', 'TIDM'])



EventKind = enum.IntEnum("EventKind", ['CASH_FLOW', 'CONSUMPTION', 'TAX_YEAR_END', 'TAX_PAYMENT'])


def yearly(date):
    return date.replace(year=date.year + 1)

def monthly(date):
    # XXX Deal more graceuflly with variable number of days per month
    return date.replace(year=date.year + date.month // 12, month=date.month % 12 + 1, day=min(date.day, 28))


def schedule(count, amount=10000, frequency=yearly, start=None):
    if start is None:
        start = datetime.datetime.utcnow().date()
    result = []
    d = start
    for i in range(count):
        d = frequency(d)
        result.append((d, amount))
    return result


class BondLadder:

    index_linked = False
    marginal_income_tax = 0.0
    interest_rate = 0.0
    lag = 0


    def __init__(self, issued, prices, schedule):
        self.issued = issued
        self.prices = prices
        self.schedule = schedule
        self.buy_df = None
        self.cash_flow_df = None

    def solve(self):
        today = datetime.datetime.utcnow().date()
        date, amount = self.schedule[0]
        yearly_consumption = amount * 365 / (date - today).days

        prob = lp.LpProblem("Ladder")

        @dataclasses.dataclass
        class Event:
            date: datetime.date
            description: str
            kind: EventKind
            operand: None

        events = []
        transactions = []

        # Add consumption events
        d = today
        base_rpi = rpi.estimate(d)
        for d, amount in self.schedule:
            if self.index_linked:
                amount = amount * rpi.estimate(d) / base_rpi
            events.append(Event(d, "Withdrawal", EventKind.CONSUMPTION, amount))
            transactions.append((d, amount))
        last_consuption = d
        #last_consuption = last_consuption.replace(year=last_consuption.year + 1)

        # Add tax events
        if self.marginal_income_tax:
            d = today.replace(month=4, day=5)
            while d < today:
                d = d.replace(year=d.year + 1)
            while True:
                tax_year = f'{d.year-1:d}/{d.year % 100:02d}'
                events.append(Event(d, f"Tax year {tax_year} end", EventKind.TAX_YEAR_END, None))
                d2 = d.replace(year=d.year + 1, month=1, day=31)
                events.append(Event(d2, f"Tax for year {tax_year}", EventKind.TAX_PAYMENT, None))
                if d >= last_consuption:
                    break
                d = d.replace(year=d.year + 1)

        initial_cash = lp.LpVariable('initial_cash', 0)
        total_cost = initial_cash

        settlement_date = next_business_day(today)

        @dataclasses.dataclass
        class Holding:
            gilt: Gilt
            tidm: str
            clean_price: float
            dirty_price: float
            initial_quantity: typing.Any

        # Add bond coupon/redemption events
        holdings = []
        for g in self.issued.filter(self.index_linked):
            coupon = g.coupon
            issue_date = g.issue_date
            maturity = g.maturity
            # XXX handle this better
            if maturity > last_consuption.replace(year=last_consuption.year + self.lag):
                continue
            isin = g.isin
            tidm = self.prices.lookup_tidm(isin)
            clean_price = self.prices.get_price(tidm)

            accrued_interest = g.accrued_interest(settlement_date)
            dirty_price = g.dirty_price(clean_price, settlement_date)
            ytm = g.ytm(dirty_price, settlement_date=settlement_date)

            quantity = lp.LpVariable(tidm, 0)
            cost = quantity * dirty_price
            total_cost = total_cost + cost

            holding = Holding(g, tidm, clean_price, dirty_price, quantity)

            cash_flows = list(g.cash_flows(settlement_date))
            assert cash_flows

            consumption_dates = [d for d, v in self.schedule]

            income = quantity * -accrued_interest
            for d, amount in cash_flows[:-1]:
                if self.lag:
                    while consumption_dates and consumption_dates[0] <= d:
                        cd = consumption_dates.pop(0)
                        if maturity < cd.replace(year=cd.year + self.lag):
                            sell = lp.LpVariable(f'Sell_{tidm}_{cd.strftime("%Y%m%d")}', 0)
                            quantity = quantity - sell
                            prob += quantity >= 0
                            income += sell * g.accrued_interest(cd)
                            ref_dirty_price = g.value(rate=ytm, settlement_date=cd)
                            dirty_price = g.value(rate=0.10, settlement_date=cd)
                            discount = dirty_price/ref_dirty_price - 1
                            clean_price = g.clean_price(dirty_price, settlement_date=cd)
                            operand = sell * dirty_price, income
                            description = self._description('*** Sell {sell:.2f} × {tidm} @ {clean_price:.2f} ({discount:+.1%}) ***', tidm=tidm, sell=sell, clean_price=clean_price, discount=discount)
                            events.append(Event(cd, description, EventKind.CASH_FLOW, operand))

                # Coupons
                if d <= last_consuption:
                    income += quantity * amount
                    operand = quantity * amount, income
                    description = self._description('Coupon from {quantity:.2f} × {tidm} @ {amount:.4f}', tidm=tidm, quantity=quantity, amount=amount)
                    events.append(Event(d, description, EventKind.CASH_FLOW, operand))
                    income = 0

            # Sell/redemption
            d, amount = cash_flows[-1]
            assert d == maturity
            if maturity <= last_consuption:
                assert income == 0
                operand = quantity * amount, None
                events.append(Event(maturity, f'Redemption of {tidm}', EventKind.CASH_FLOW, operand))
                quantity = 0
            else:
                #income += quantity * g.accrued_interest(last_consuption)
                #price = g.value(rate=0.0525, settlement_date=last_consuption)
                #operand = quantity * price, income
                #events.append(Event(last_consuption, f'Sell {tidm}', EventKind.CASH_FLOW, operand))
                pass

            holdings.append(holding)

        # Sort events chronologically
        events.sort(key=operator.attrgetter("date", "kind"))

        @dataclasses.dataclass
        class CashFlow:
            date: datetime.date
            description: str | typing.Callable[[], str]
            incoming: typing.Any = math.nan
            outgoing: typing.Any = math.nan
            balance: typing.Any = math.nan
            income: typing.Any = math.nan

        cash_flows = []

        # Initial cash deposit
        balance = initial_cash
        cash_flows.append(CashFlow(date=today, description="Deposit", incoming=initial_cash, balance=balance))

        accrued_income = 0
        tax_due = None
        prev_date = today
        for ev in events:
            #pp(event)

            # Accumulate interest on cash balance
            if ev.date != prev_date:
                assert ev.date >= prev_date
                if self.interest_rate:
                    interest = balance * self.interest_rate * (ev.date - prev_date).days / 365
                    balance = balance + interest
                    accrued_income = accrued_income + interest
                    cash_flows.append(CashFlow(date=ev.date, description="Interest", incoming=interest, balance=balance, income=interest))
                prev_date = ev.date

            cf = CashFlow(date=ev.date, description=ev.description)

            if ev.kind == EventKind.CONSUMPTION:
                outgoing = ev.operand
                cf.outgoing = outgoing
                balance = balance - outgoing
                prob += balance >= 0
            elif ev.kind == EventKind.CASH_FLOW:
                incoming, income = ev.operand
                cf.incoming = incoming
                balance = balance + incoming
                if income is not None:
                    accrued_income = accrued_income + income
                    cf.income = income
            elif ev.kind == EventKind.TAX_YEAR_END:
                assert tax_due is None
                tax_due = accrued_income * self.marginal_income_tax
                accrued_income = 0
                continue
            elif ev.kind == EventKind.TAX_PAYMENT:
                assert tax_due is not None
                balance = balance - tax_due
                prob += balance >= 0
                cf.outgoing = tax_due
                tax_due = None
            else:
                raise ValueError(ev.kind)

            cf.balance = balance
            cash_flows.append(cf)

        prob.checkDuplicateVars()

        solvers = lp.listSolvers(onlyAvailable=True)
        if 'PULP_CBC_CMD' in solvers:
            solver = lp.PULP_CBC_CMD(msg=0)
        else:
            assert 'COIN_CMD' in solvers
            solver = lp.COIN_CMD(msg=0)

        prob.setObjective(total_cost)

        status = prob.solve(solver)
        if status != lp.LpStatusOptimal:
            statusMsg = {
                lp.LpStatusNotSolved: "Not Solved",
                lp.LpStatusOptimal: "Optimal",
                lp.LpStatusInfeasible: "Infeasible",
                lp.LpStatusUnbounded: "Unbounded",
                lp.LpStatusUndefined: "Undefined",
            }.get(status, "Unexpected")
            raise ValueError(f"Failed to solve the problem ({statusMsg})")

        # There should be no cash left, barring rounding errors
        assert lp.value(balance) < 1.0

        assert tax_due is None
        if self.marginal_income_tax:
            if self.interest_rate:
                # There's always some residual interest outstanding
                assert lp.value(accrued_income) < 1000.0
            else:
                assert lp.value(accrued_income) < 0.01

        total_cost = lp.value(total_cost)

        buy_rows = []
        for h in holdings:
            quantity = lp.value(h.initial_quantity)
            g = h.gilt
            ytm = g.ytm(h.dirty_price, settlement_date=settlement_date)
            if self.index_linked:
                ytm = (1 + ytm)/(1 + 0.03) - 1
            buy_rows.append({
                'Instrument': g.short_name(),
                'TIDM': h.tidm,
                'Clean Price': h.clean_price,
                'Dirty Price': h.dirty_price,
                'GRY': ytm,
                'Quantity': quantity,
                'Cost': h.dirty_price * quantity,
            })
        buy_rows.append({
            'Instrument': 'Cash',
            'Cost': lp.value(initial_cash),
        })
        buy_rows.append({
            'Instrument': 'Total',
            'Cost': total_cost,
        })
        self.buy_df = pd.DataFrame(data=buy_rows)

        self.cost = total_cost

        # Use real values
        for cf in cash_flows:
            if callable(cf.description):
                cf.description = cf.description()
            assert isinstance(cf.description, str)
            if self.index_linked:
                index_ratio = base_rpi / rpi.estimate(cf.date)
            else:
                index_ratio = 1.0
            cf.incoming = index_ratio * lp.value(cf.incoming)
            cf.outgoing = index_ratio * lp.value(cf.outgoing)
            cf.balance  = index_ratio * lp.value(cf.balance)
            cf.income   = index_ratio * lp.value(cf.income)

        df = pd.DataFrame(data=cash_flows)
        df = df.drop(df[df.incoming < .005].index)
        df = df.drop(df[df.outgoing < .005].index)
        df = df.rename(columns=str.title)
        self.cash_flow_df = df

        self.withdrawal_rate = yearly_consumption/total_cost

        transactions.append((settlement_date, -total_cost))

        transactions.sort(key=operator.itemgetter(0))

        dates, values = zip(*transactions)
        self.yield_ = xirr(values, dates)

    @staticmethod
    def _description(fmt, **kwargs):
        return lambda: fmt.format(**{k: lp.value(v) if isinstance(v, (lp.LpVariable, lp.LpAffineExpression)) else v for k, v in kwargs.items()})

    def print(self):
        print(self.buy_df.to_string(
            justify='center',
            index=False,
            na_rep='',
            float_format='{:6,.2f}'.format,
            formatters={
                'Instrument': '{:20s}'.format,
                'TIDM': '{:4s}'.format,
                'GRY': '{:6.2%}'.format,
            },
        ))

        print()

        df = self.cash_flow_df

        # https://stackoverflow.com/a/25777111
        description_len = df['Description'].str.len().max()
        description_len = max(description_len + 1, 32)

        print(df.to_string(
            justify='center',
            index=False,
            na_rep='',
            float_format='{:6,.2f}'.format,
            formatters={'Description': f'{{:<{description_len}s}}'.format},
        ))

        print()

        print(f'Withdrawal Rate: {self.withdrawal_rate:,.2%}')
        print(f'Net Yield: {self.yield_:.2%}')


def bond_ladder(schedule, index_linked=False, marginal_income_tax=0, interest_rate=0, lag=0, issued=None, prices=None):
    if issued is None:
        issued = Issued()
    if prices is None:
        prices = GiltPrices()
    bl = BondLadder(issued, prices, schedule)
    bl.index_linked = index_linked
    bl.marginal_income_tax = marginal_income_tax
    bl.interest_rate = interest_rate
    bl.lag = lag
    bl.solve()
    bl.print()


if __name__ == '__main__':
    bond_ladder(schedule(30, 10000), index_linked=False, marginal_income_tax=0.45, lag=1, interest_rate=0.025)
