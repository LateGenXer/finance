#
# Copyright (c) 2023-2025 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


from __future__ import annotations

import argparse
import datetime
import dataclasses
import logging
import enum
import math
import operator
import typing

import pandas as pd

import lp

from typing import Any

from xirr import xirr
from ukcalendar import next_business_day, shift_month, shift_year
from .gilts import Gilt, IndexLinkedGilt, Issued, GiltPrices
from data.rpi import RPI



EventKind = enum.IntEnum("EventKind", ['CASH_FLOW', 'CONSUMPTION', 'TAX_YEAR_END', 'TAX_PAYMENT'])


def schedule(count, amount=10000, shift=shift_year, start=None):
    result = []
    if start is None:
        start = datetime.datetime.now(datetime.timezone.utc).date()
        for i in range(count):
            d = shift(start, 1 + i)
            result.append((d, amount))
    else:
        for i in range(count):
            d = shift(start, i)
            result.append((d, amount))
    return result


def schedule_from_csv(stream):
    df = pd.read_csv(stream, header=0, names=['Date', 'Value'], parse_dates=['Date'])
    df['Date'] = df['Date'].dt.date
    df.sort_values(by=['Date'], inplace=True)
    return df


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
        self.rpi_series = issued.rpi_series
        self.prices = prices
        self.schedule = schedule
        self.buy_df = None
        self.cash_flow_df = None
        self.today = datetime.datetime.now(datetime.timezone.utc).date()

    def solve(self):
        today = self.today
        date, amount = self.schedule[0]
        yearly_consumption = amount * 365.25 / (date - today).days

        prob = lp.LpProblem("Ladder")

        @dataclasses.dataclass
        class Event:
            date: datetime.date
            description: str|Description
            kind: EventKind
            operand: Any

        events = []
        transactions = []

        # Add consumption events
        d = today
        base_rpi = self.rpi_series.extrapolate(d, IndexLinkedGilt.inflation_rate)
        for d, amount in self.schedule:
            if self.index_linked:
                amount = amount * self.rpi_series.extrapolate(d, IndexLinkedGilt.inflation_rate) / base_rpi
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
        for g in self.issued.filter(self.index_linked, settlement_date):
            maturity = g.maturity
            assert maturity > settlement_date
            # XXX handle this better
            if maturity > shift_month(last_consuption, self.lag):
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
                        if maturity < shift_month(cd, self.lag) and cd <= g.ex_dividend_date(maturity):
                            sell = lp.LpVariable(f'Sell_{tidm}_{cd:%Y%m%d}', 0)
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
                #quantity = 0

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
                    pro_rata_interest_rate = self.interest_rate * (ev.date - prev_date).days / 365.25
                    interest = balance * pro_rata_interest_rate
                    balance = balance * (1.0 + pro_rata_interest_rate)
                    accrued_income = accrued_income + interest
                    cash_flows.append(CashFlow(date=ev.date, description=interest_desc, incoming=interest, balance=balance, income=interest))
                prev_date = ev.date


            incoming = None
            outgoing = None
            income = None
            if ev.kind == EventKind.CONSUMPTION:
                outgoing = ev.operand
            elif ev.kind == EventKind.CASH_FLOW:
                incoming, income = ev.operand
                if income is not None:
                    accrued_income = accrued_income + income
            elif ev.kind == EventKind.TAX_YEAR_END:
                assert tax_due is None
                tax_due = accrued_income * self.marginal_income_tax
                accrued_income = 0
                continue
            elif ev.kind == EventKind.TAX_PAYMENT:
                assert tax_due is not None
                outgoing = tax_due
                tax_due = None
            else:
                raise ValueError(ev.kind)

            cf = CashFlow(date=ev.date, description=ev.description)
            if incoming is not None:
                balance = balance + incoming
                cf.incoming = incoming
            if outgoing is not None:
                if False:  # pragma: no cover
                    # While simpler, this is numerically unstable
                    balance = balance - outgoing
                    prob += balance >= 0
                else:
                    # Introducing a variable avoids numerical instability
                    v = lp.LpVariable(f'balance_{ev.date:%Y%m%d}_{len(cash_flows)}', 0)
                    prob += v == balance - outgoing
                    balance = v
                cf.outgoing = outgoing
            if income is not None:
                cf.income = income
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
        assert status == lp.LpStatusOptimal

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
                ytm = (1.0 + ytm)/(1.0 + IndexLinkedGilt.inflation_rate) - 1.0
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
                index_ratio = base_rpi / self.rpi_series.extrapolate(cf.date, IndexLinkedGilt.inflation_rate)
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
                prev_cf.date = cf.date
                prev_cf.incoming += cf.incoming
                assert math.isnan(cf.outgoing)
                prev_cf.balance = cf.balance
                prev_cf.income += cf.income
                continue

            data.append(cf)
            prev_cf = cf

        df = pd.DataFrame(data=data)

        df.rename(columns={
            'date':         'Date',
            'description':  'Description',
            'incoming':     'In',
            'outgoing':     'Out',
            'balance':      'Balance',
            'income':       'Tax. Inc.',
        }, inplace=True, errors='raise')

        self.cash_flow_df = df

        self.withdrawal_rate = yearly_consumption/total_cost

        transactions.append((settlement_date, -total_cost))

        transactions.sort(key=operator.itemgetter(0))

        dates, values = zip(*transactions)
        self.yield_ = xirr(values, dates)

    def print(self):
        assert self.buy_df is not None
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
        assert df is not None

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


def main():
    logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s %(message)s', level=logging.INFO)

    argparser = argparse.ArgumentParser()
    argparser.add_argument('-I', '--index-linked', action='store_true')
    argparser.add_argument('-L', '--live', action='store_true')
    argparser.add_argument('-i', '--interest-rate', metavar='PERCENTAGE', type=float, default=0.0)
    argparser.add_argument('-l', '--lag', metavar='MONTHS', type=int, default=0)
    argparser.add_argument('-t', '--marginal-income-tax-rate', metavar='PERCENTAGE', type=float, default=0.0)
    argparser.add_argument('schedule', metavar="SCHEDULE_CSV")
    args = argparser.parse_args()

    rpi_series = RPI()
    issued = Issued(rpi_series=rpi_series)
    prices = GiltPrices.from_latest(kind='offer') if args.live else GiltPrices.from_last_close()

    schedule_df = schedule_from_csv(open(args.schedule, 'rt'))
    s = list(schedule_df.itertuples(index=False))
    bl = BondLadder(issued, prices, s)
    bl.index_linked = args.index_linked
    bl.marginal_income_tax = args.marginal_income_tax_rate / 100.0
    bl.interest_rate = args.interest_rate / 100.0
    bl.lag = args.lag
    bl.solve()
    bl.print()


if __name__ == '__main__':
    main()
