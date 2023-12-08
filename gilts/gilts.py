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

import caching

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

    def __init__(self, name, isin, coupon, maturity, issue_date):
        self.name = name
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
        assert settlement_date >= self.issue_date
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
            r = (next_coupon_date - self.issue_date).days / (next_coupon_date - prev_coupon_date).days
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
        assert r >= 0
        s = (next_coupon_date - prev_coupon_date).days
        assert s >= 181 and s <= 184

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

        if n > 0:
            # https://www.dmo.gov.uk/media/1sljygul/yldeqns.pdf
            # Section 1
            def fn(v):
                return v**(r/s) * (d1 + d2 * v + c * v**2 / (f * (1 - v)) * (1 - v**(n - 1)) + 100 * v**n) - P

            v0 = 1 / (1 + .05 / f)
            v = optimize.newton(fn, v0)
            y = (1 / v - 1) * f
        else:
            # Simple interest, like Tradeweb
            # https://www.lseg.com/content/dam/ftse-russell/en_us/documents/ground-rules/ftse-actuaries-uk-gilts-index-series-guide-to-calc.pdf
            # Section 6.1
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

    def __init__(self, name, isin, coupon, maturity, issue_date, base_rpi):
        Gilt.__init__(self, name, isin, coupon, maturity, issue_date=issue_date)
        self.base_rpi = base_rpi
        self.lag = 3 if issue_date >= datetime.date(2005, 9, 22) else 8

    # https://www.dmo.gov.uk/media/0ltegugd/igcalc.pdf
    def ref_rpi(self, settlement_date, inflation_rate=None):
        if self.lag == 3:
            d = settlement_date
            month_idx = (d.year - rpi.ref_year) * 12 + (d.month - 1)
            month_idx -= self.lag
            weight = (d.day - 1) / days_in_month(d.year, d.month)
            assert weight >= 0 and weight < 1
            rpi0 = self._rpi(month_idx,     inflation_rate)
            rpi1 = self._rpi(month_idx + 1, inflation_rate)
            return round(rpi0 + weight * (rpi1 - rpi0), 5)
        else:
            assert self.lag == 8
            _, d = self.prev_next_coupon_date(settlement_date)
            month_idx = (d.year - rpi.ref_year) * 12 + (d.month - 1)
            month_idx -= self.lag
            return self._rpi(month_idx, inflation_rate)

    inflation_rate = 0.03

    def _rpi(self, month_idx, inflation_rate):
        assert month_idx >= 0
        try:
            return rpi.series[month_idx]
        except IndexError:
            if inflation_rate is None:
                raise
            # https://www.dmo.gov.uk/media/1sljygul/yldeqns.pdf
            # ANNEX A: Estimation of the nominal values of future unknown cash
            # flows on index-linked gilts with an 8-month indexation lag.
            months = month_idx + 1 - len(rpi.series)
            return round(rpi.series[-1] * (1 + inflation_rate) ** (months / 12), 5)

    def index_ratio(self, settlement_date, inflation_rate=None):
        if inflation_rate is None:
            inflation_rate = self.inflation_rate
        index_ratio = self.ref_rpi(settlement_date, inflation_rate=inflation_rate) / self.base_rpi
        if self.lag == 3:
            index_ratio = round(index_ratio, 5)
        return index_ratio

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

    def cash_flows(self, settlement_date, inflation_rate=None):
        if inflation_rate is None:
            inflation_rate = self.inflation_rate
        for date, value in Gilt.cash_flows(self, settlement_date=settlement_date):
            index_ratio = self.index_ratio(date, inflation_rate=inflation_rate)
            # See https://www.dmo.gov.uk/media/0ltegugd/igcalc.pdf
            # Annex: Rounding Conventions for Interest and Redemption Cash Flows for Index-linked Gilts
            value = round(value * index_ratio, 6 if self.issue_date.year >= 2002 else 4)
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
    # https://www.dmo.gov.uk/data/

    def __init__(self, filename=None):
        if filename is None:
            entries = self._download()
        else:
            entries = self._parse_xml(filename)

        self.all = []
        for entry in entries:
            name = entry['INSTRUMENT_NAME']
            kwargs = {
                'name': name,
                'isin': entry['ISIN_CODE'],
                'coupon': self._parse_coupon(name),
                'maturity': self._parse_date(entry['REDEMPTION_DATE']),
                'issue_date': self._parse_date(entry['FIRST_ISSUE_DATE']),
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

            self.close_date = self._parse_date(entry['CLOSE_OF_BUSINESS_DATE'])

            # Check ex-divdend dates match when testing
            if "PYTEST_CURRENT_TEST" in os.environ:
                current_xd_date = self._parse_date(entry['CURRENT_EX_DIV_DATE'])
                settlement_date = next_business_day(self.close_date)
                _, next_coupon_date = gilt.prev_next_coupon_date(settlement_date)
                assert gilt.ex_dividend_date(next_coupon_date) == current_xd_date

            self.all.append(gilt)

        self.all.sort(key=operator.attrgetter('maturity'))

        self.isin = {gilt.isin: gilt for gilt in self.all}

    @staticmethod
    @caching.cache_data(ttl=15*60)
    def _download():
        # Cache of https://www.dmo.gov.uk/data/XmlDataReport?reportCode=D1A
        # updated daily by .github/workflows/gh-pages.yml to avoid Captchas on
        # more frequent downloads.
        filename = os.path.join(os.path.dirname(__file__), 'dmo-D1A.xml')
        download('https://lategenxer.github.io/finance/dmo-D1A.xml', filename)
        return list(Issued._parse_xml(filename))

    @staticmethod
    def _parse_xml(filename):
        stream = open(filename, 'rt')
        tree = xml.etree.ElementTree.parse(stream)
        root = tree.getroot()
        for node in root:
            yield node.attrib

    @staticmethod
    def _parse_date(string):
        return datetime.datetime.fromisoformat(string).date()

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


_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

def days_in_month(year, month):
    if month == 2:
        return 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28
    else:
        return _days_in_month[month - 1]


def yield_curve(issued, prices, index_linked=False):
    settlement_date = next_business_day(issued.close_date)
    data = []
    for g in issued.filter(index_linked):
        isin = g.isin
        tidm = prices.lookup_tidm(isin)
        clean_price = prices.get_price(tidm)
        dirty_price = g.dirty_price(clean_price, settlement_date)

        ytm = g.ytm(dirty_price, settlement_date) * 100.0
        maturity = (g.maturity - issued.close_date).days / 365.25
        data.append((maturity, ytm, tidm))

    return pd.DataFrame(data, columns=['Maturity', 'Yield', 'TIDM'])



EventKind = enum.IntEnum("EventKind", ['CASH_FLOW', 'CONSUMPTION', 'TAX_YEAR_END', 'TAX_PAYMENT'])


def yearly(date):
    year = year=date.year + 1
    month = date.month
    day = min(date.day, days_in_month(year, month))
    return date.replace(year=year, month=month, day=day)


def monthly(date):
    # XXX Deal more gracefully with variable number of days per month
    year = year=date.year + date.month // 12
    month = date.month % 12 + 1
    day = min(date.day, days_in_month(year, month))
    return date.replace(year=year, month=month, day=day)


def schedule(count, amount=10000, frequency=yearly, start=None):
    if start is None:
        d = datetime.datetime.utcnow().date()
        d = frequency(d)
    else:
        d = start
    result = []
    for i in range(count):
        result.append((d, amount))
        d = frequency(d)
    return result


class Description:
    '''Deferred description.'''

    def __init__(self, fmt, **kwargs):
        self.fmt = fmt
        self.kwargs = kwargs

    def __str__(self):
        return self.fmt.format(**{k: lp.value(v) if isinstance(v, (lp.LpVariable, lp.LpAffineExpression)) else v for k, v in self.kwargs.items()})

    def __repr__(self):  # pragma: no cover
        return repr(self.fmt.format(**{k: math.nan if isinstance(v, (lp.LpVariable, lp.LpAffineExpression)) else v for k, v in self.kwargs.items()}))


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
        self.today = datetime.datetime.utcnow().date()

    def solve(self):
        today = self.today
        date, amount = self.schedule[0]
        yearly_consumption = amount * 365.25 / (date - today).days

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
            if maturity <= settlement_date:
                continue
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
                            income = income + sell * g.accrued_interest(cd)
                            ref_dirty_price = g.value(rate=ytm, settlement_date=cd)
                            dirty_price = g.value(rate=0.10, settlement_date=cd)
                            discount = dirty_price/ref_dirty_price - 1
                            clean_price = g.clean_price(dirty_price, settlement_date=cd)
                            operand = sell * dirty_price, income
                            description = Description('*** Sell {sell:.2f} × {tidm} @ {clean_price:.2f} ({discount:+.1%}) ***', tidm=tidm, sell=sell, clean_price=clean_price, discount=discount)
                            events.append(Event(cd, description, EventKind.CASH_FLOW, operand))
                            income = 0

                # Coupons
                if d <= last_consuption:
                    income = income + quantity * amount
                    operand = quantity * amount, income
                    description = Description('Coupon from {quantity:.2f} × {tidm} @ {amount:.4f}', tidm=tidm, quantity=quantity, amount=amount)
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

            holdings.append(holding)

        # Sort events chronologically
        events.sort(key=operator.attrgetter("date", "kind"))

        @dataclasses.dataclass
        class CashFlow:
            date: datetime.date
            description: str | Description
            incoming: typing.Any = math.nan
            outgoing: typing.Any = math.nan
            balance: typing.Any = math.nan
            income: typing.Any = math.nan

        cash_flows = []

        # Initial cash deposit
        balance = initial_cash
        cash_flows.append(CashFlow(date=today, description="Deposit", incoming=initial_cash, balance=balance))

        interest_desc = "Interest"

        accrued_income = 0
        tax_due = None
        prev_date = today
        for ev in events:
            #pp(event)

            # Accumulate interest on cash balance
            if ev.date != prev_date:
                assert ev.date >= prev_date
                if self.interest_rate and ev.date <= last_consuption:
                    interest = balance * self.interest_rate * (ev.date - prev_date).days / 365.25
                    balance = balance + interest
                    accrued_income = accrued_income + interest
                    cash_flows.append(CashFlow(date=ev.date, description=interest_desc, incoming=interest, balance=balance, income=interest))
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
        assert not self.marginal_income_tax or lp.value(accrued_income) < 0.01

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
        data = []
        prev_cf = None
        for cf in cash_flows:
            cf.description = str(cf.description)
            if self.index_linked:
                index_ratio = base_rpi / rpi.estimate(cf.date)
            else:
                index_ratio = 1.0
            cf.incoming = index_ratio * lp.value(cf.incoming)
            cf.outgoing = index_ratio * lp.value(cf.outgoing)
            cf.balance  = index_ratio * lp.value(cf.balance)
            cf.income   = index_ratio * lp.value(cf.income)

            # Filter out zero flows
            if cf.incoming <= .005:
                assert math.isnan(cf.outgoing)
                assert not cf.income > .005
                continue
            if cf.outgoing <= .005:
                assert math.isnan(cf.incoming)
                assert not cf.income > .005
                continue

            # Coalesce consecutive cash interest
            if cf.description is interest_desc and prev_cf is not None and prev_cf.description is interest_desc:
                prev_cf.incoming += cf.incoming
                assert math.isnan(cf.outgoing)
                prev_cf.balance = cf.balance
                prev_cf.income += cf.income
                continue

            data.append(cf)
            prev_cf = cf

        df = pd.DataFrame(data=data)
        df = df.rename(columns=str.title)
        self.cash_flow_df = df

        self.withdrawal_rate = yearly_consumption/total_cost

        transactions.append((settlement_date, -total_cost))

        transactions.sort(key=operator.itemgetter(0))

        dates, values = zip(*transactions)
        self.yield_ = xirr(values, dates)

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
