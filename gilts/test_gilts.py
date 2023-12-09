#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import datetime

import pytest

from pytest import approx

import lse

from gilts import *


@pytest.mark.parametrize("coupon_date,xd_date", [
    # https://docs.londonstockexchange.com/sites/default/files/documents/dmo-private-investor-guide-to-gilts.pdf
    ((2004,  9,  7), (2004,  8, 26)),
], ids=repr)
def test_ex_dividend_date(coupon_date, xd_date):
    coupon_date = datetime.date(*coupon_date)
    xd_date = datetime.date(*xd_date)
    assert Gilt.ex_dividend_date(coupon_date) == xd_date


@pytest.fixture
def issued():
    filename = os.path.join(os.path.dirname(__file__), 'dmo-D1A-20231201.xml')
    return Issued(filename)


@pytest.fixture
def prices():
    filename = lse.TradewebClosePrices.default
    return lse.TradewebClosePrices(filename)


@pytest.mark.parametrize("index_linked", [False, True])
def test_yield_curve(issued, prices, index_linked, show_plots):
    df = yield_curve(issued, prices, index_linked)
    df.plot(x='Maturity', y='Yield', kind='scatter', logx=False, xlim=(0, 50), xticks=[2, 5, 10, 15, 30], ylim=(0, 6), grid=True)
    if show_plots:
        plt.draw()
        plt.pause(0.5)
    else:
        plt.savefig(os.devnull, format='svg')


@pytest.fixture
def tradeweb():
    filename = lse.TradewebClosePrices.default
    return list(lse.TradewebClosePrices.parse(filename))


def test_tradeweb(issued, tradeweb):
    for row in tradeweb:
        isin = row['ISIN']
        gilt = issued.isin[isin]

        print(row)
        print(gilt.issue_date)

        assert gilt.type_ == row['Type']
        #print(row['Type'])
        conventional = row['Type'] == 'Conventional'

        coupon = float(row['Coupon'])
        assert gilt.coupon == coupon

        maturity = datetime.datetime.strptime(row['Maturity'], '%d/%m/%Y').date()
        assert gilt.maturity == maturity

        close_date = datetime.datetime.strptime(row['Close of Business Date'], '%d/%m/%Y').date()
        settlement_date = next_business_day(close_date)

        clean_price = float(row['Clean Price'])
        accrued_interest = float(row['Accrued Interest'])
        dirty_price = float(row['Dirty Price'])

        assert gilt.accrued_interest(settlement_date) == approx(accrued_interest, abs=1e-6 if conventional else 1e-4)
        assert gilt.dirty_price(clean_price, settlement_date) == approx(dirty_price, abs=1e-6 if conventional else 5e-2)

        if conventional:
            ytm = float(row['Yield'])
            ytm_ = gilt.ytm(dirty_price, settlement_date)
            ytm_ *= 100

            print(f'YTM: {ytm_:8.6f} vs {ytm:8.6f} (abs={ytm_ - ytm:+9.6f} rel={ytm_/ytm -1:+.1e})')

            _, next_coupon_dates = gilt.coupon_dates(settlement_date=settlement_date)
            if len(next_coupon_dates) == 2:
                # XXX: Tradeweb seems to be using simple interest
                # (non-compounding) for all bonds maturing less than one year
                assert ytm_ == approx(ytm, rel=1e-2)
            else:
                assert ytm_ == approx(ytm, abs=5e-6)


@pytest.mark.parametrize("lag", [0, 2])
@pytest.mark.parametrize("interest_rate", [0.0, 0.02])
@pytest.mark.parametrize("marginal_income_tax", [0.0, 0.40])
@pytest.mark.parametrize("index_linked", [False, True])
@pytest.mark.parametrize("count,amount,frequency", [
    (50   , 10000,  yearly),
    (10*12,  1000, monthly),
])
#@pytest.mark.parametrize("count,amount,frequency,index_linked,marginal_income_tax,interest_rate,lag", [(10, 10000, yearly, True, 0.40, 0.25, 0)])
def test_bond_ladder(issued, prices, count, amount, frequency, index_linked, marginal_income_tax, interest_rate, lag):
    s = schedule(count, amount, frequency)
    bl = BondLadder(issued=issued, prices=prices, schedule=s)
    bl.index_linked = index_linked
    bl.marginal_income_tax = marginal_income_tax
    bl.interest_rate = interest_rate
    bl.lag = lag
    bl.today = prices.get_prices_date().date()
    bl.solve()
    bl.print()

    df = bl.cash_flow_df
    for cf in df.itertuples():
        assert math.isnan(cf.Incoming) != math.isnan(cf.Outgoing)
        assert not cf.Incoming < 0.005
        assert not cf.Outgoing < 0.005

        assert cf.Balance > -0.005

    withdrawals = df['Outgoing'].loc[df['Description'] == 'Withdrawal'].sum()
    withdrawals_exp = sum([value for _, value in s])
    assert withdrawals == approx(withdrawals_exp, abs=0.005)

    income_loc = df['Income'] == df['Income']
    incoming = df['Incoming'].loc[income_loc].sum()
    income = df['Income'].loc[income_loc].sum()
    assert income <= incoming + .005
