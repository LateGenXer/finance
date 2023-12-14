#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import datetime
import operator

import pytest

from pytest import approx

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


gilts_closing_prices_csv = os.path.join(os.path.dirname(__file__), 'gilts-closing-prices-20231201.csv')


# https://reports.tradeweb.com/closing-prices/gilts/ > Type: Gilts Only > Export
tradeweb_csv = os.path.join(os.path.dirname(__file__), 'Tradeweb_FTSE_ClosePrices_20231201.csv')


class TradewebClosePrices(Prices):

    def __init__(self, filename=tradeweb_csv):
        Prices.__init__(self)

        self.tidms = {}
        for row in csv.DictReader(open(gilts_closing_prices_csv, 'rt')):
            tidm = row['tidm']
            isin = row['isin']
            self.tidms[isin] = tidm

        self.prices = {}
        for row in self.parse(filename):
            isin = row['ISIN']
            price = float(row['Clean Price'])
            tidm = self.tidms[isin]
            self.prices[tidm] = price
            self.datetime = datetime.datetime.strptime(row['Close of Business Date'], '%d/%m/%Y')
        self.datetime = self.datetime.replace(hour=23, minute=59, second=59)

    @staticmethod
    def parse(filename=tradeweb_csv):
        for row in csv.DictReader(open(filename, 'rt', encoding='utf-8-sig')):
            if row['Type'] in ('Conventional', 'Index-linked'):
                yield row

    def lookup_tidm(self, isin):
        return self.tidms[isin]

    def get_price(self, tidm):
        return self.prices[tidm]

    def get_prices_date(self):
        return self.datetime


@pytest.fixture
def prices():
    return TradewebClosePrices()


@pytest.mark.parametrize('prices', [
    pytest.param(GiltPrices(None), id="cached"),
    pytest.param(GiltPrices(os.path.join(os.path.dirname(__file__), 'gilts-closing-prices-20231201.csv')), id="local"),
    pytest.param(TradewebClosePrices(), id="tradeweb"),
])
def test_prices(prices):
    isin, tidm = 'GB00BBJNQY21', 'TR68'
    assert prices.lookup_tidm(isin) == tidm
    assert prices.get_price(tidm) >= 0
    assert isinstance(prices.get_prices_date(), datetime.datetime)


@pytest.mark.parametrize("index_linked", [False, True])
def test_yield_curve(issued, prices, index_linked, show_plots):
    df = yield_curve(issued, prices, index_linked)
    df.plot(x='Maturity', y='Yield', kind='scatter', logx=False, xlim=(0, 50), xticks=[2, 5, 10, 15, 30], ylim=(0, 6), grid=True)
    if show_plots:
        plt.draw()
        plt.pause(0.5)
    else:
        plt.savefig(os.devnull, format='svg')


@pytest.mark.parametrize("row", [
    pytest.param(row, id=row['Gilt Name']) for row in TradewebClosePrices.parse(tradeweb_csv)
])
def test_tradeweb(caplog, issued, row):
    caplog.set_level(logging.DEBUG, logger="gilts")

    for name, value in row.items():
        logger.debug('%s = %s', name, value)
    logger.debug('')

    type_ = row["Type"]
    assert type_ in ["Conventional", "Index-linked"]

    isin = row['ISIN']
    gilt = issued.isin[isin]

    assert gilt.type_ == type_
    conventional = type_ == 'Conventional'

    coupon = float(row['Coupon'])
    assert gilt.coupon == coupon

    maturity = datetime.datetime.strptime(row['Maturity'], '%d/%m/%Y').date()
    assert gilt.maturity == maturity

    close_date = datetime.datetime.strptime(row['Close of Business Date'], '%d/%m/%Y').date()
    settlement_date = next_business_day(close_date)

    clean_price = float(row['Clean Price'])
    accrued_interest = float(row['Accrued Interest'])
    dirty_price = float(row['Dirty Price'])

    abs_tol = 1e-6 if conventional or gilt.lag != 8 else 1e-4
    assert gilt.accrued_interest(settlement_date) == approx(accrued_interest, abs=abs_tol)
    assert gilt.dirty_price(clean_price, settlement_date) == approx(dirty_price, abs=abs_tol)

    ytm = float(row['Yield'])
    ytm_ = gilt.ytm(dirty_price, settlement_date)
    if not conventional:
        ytm_ = (1 + ytm_)/(1 + .03) - 1
    ytm_ *= 100

    logger.debug(f'YTM: {ytm_:8.6f} vs {ytm:8.6f} (abs={ytm_ - ytm:+9.6f} rel={ytm_/ytm -1:+.1e})')

    if conventional:
        _, next_coupon_dates = gilt.coupon_dates(settlement_date=settlement_date)
        if len(next_coupon_dates) == 2:
            # XXX: Tradeweb seems to be using simple interest
            # (non-compounding) for all bonds maturing less than one year
            assert ytm_ == approx(ytm, rel=1e-2)
        else:
            assert ytm_ == approx(ytm, abs=5e-6)


# Index-linked Gilt Cash Flows, taken from
# https://www.dmo.gov.uk/data/ExportReport?reportCode=D5I
# on 2023-12-08 for 2023-2024 range
il_cash_flows = [
    # Name, [Dividend Date, Dividend Amount, Reference RPI, Index Ratio]*
    ( "0 1/8% Index-linked Treasury Gilt 2024", [
        ( "22-Mar-2023", 0.092900, 360.33226, 1.48640 ),
        ( "22-Sep-2023", 0.096646, 374.86000, 1.54633 ),
    ]),
    ( "2½% Index-linked Treasury Stock 2024", [
        ( "17-Jan-2023", 4.3143, 337.10000, 3.45149 ),
        ( "17-Jul-2023", 4.5856, 358.30000, 3.66855 ),
        ( "17-Jan-2024", 4.8032, 375.30000, 3.84261 ),
    ]),
    ( "0 1/8% Index-linked Treasury Gilt 2026", [
        ( "22-Mar-2023", 0.087208, 360.33226, 1.39533 ),
        ( "22-Sep-2023", 0.090724, 374.86000, 1.45158 ),
    ]),
    ( "1¼% Index-linked Treasury Gilt 2027", [
        ( "22-May-2023", 1.179781, 366.32903, 1.88765 ),
        ( "22-Nov-2023", 1.216913, 377.86000, 1.94706 ),
    ]),
    ( "0 1/8% Index-linked Treasury Gilt 2028", [
        ( "10-Feb-2023", 0.080348, 358.97500, 1.28557 ),
        ( "10-Aug-2023", 0.084074, 375.61935, 1.34518 ),
    ]),
    ( "0 1/8% Index-linked Treasury Gilt 2029", [
        ( "22-Mar-2023", 0.094856, 360.33226, 1.51770 ),
        ( "22-Sep-2023", 0.098681, 374.86000, 1.57889 ),
    ]),
    ( "4 1/8% Index-linked Treasury Stock 2030", [
        ( "22-Jan-2023", 5.1463, 337.10000, 2.49519 ),
        ( "22-Jul-2023", 5.4699, 358.30000, 2.65211 ),
        ( "22-Jan-2024", 5.7295, 375.30000, 2.77794 ),
    ]),
    ( "0 1/8% Index-linked Treasury Gilt 2031", [
        ( "10-Feb-2023", 0.076416, 358.97500, 1.22265 ),
        ( "10-Aug-2023", 0.079959, 375.61935, 1.27934 ),
    ]),
    ( "1¼% Index-linked Treasury Gilt 2032", [
        ( "22-May-2023", 1.054450, 366.32903, 1.68712 ),
        ( "22-Nov-2023", 1.087644, 377.86000, 1.74023 ),
    ]),
    ( "0¾% Index-linked Treasury Gilt 2033", [
        ( "22-Nov-2023", 0.304116, 377.86000, 1.01510 ),
    ]),
    ( "0¾% Index-linked Treasury Gilt 2034", [
        ( "22-Mar-2023", 0.581858, 360.33226, 1.55162 ),
        ( "22-Sep-2023", 0.605318, 374.86000, 1.61418 ),
    ]),
    ( "2% Index-linked Treasury Stock 2035", [
        ( "26-Jan-2023", 1.941820, 337.10000, 1.94182 ),
        ( "26-Jul-2023", 2.063940, 358.30000, 2.06394 ),
        ( "26-Jan-2024", 2.161866, 375.30000, 2.16187 ),
    ]),
    ( "0 1/8% Index-linked Treasury Gilt 2036", [
        ( "22-May-2023", 0.088053, 366.32903, 1.40885 ),
        ( "22-Nov-2023", 0.090825, 377.86000, 1.45320 ),
    ]),
    ( "1 1/8% Index-linked Treasury Gilt 2037", [
        ( "22-May-2023", 1.018873, 366.32903, 1.81133 ),
        ( "22-Nov-2023", 1.050947, 377.86000, 1.86835 ),
    ]),
    ( "0 1/8% Index-linked Treasury Gilt 2039", [
        ( "22-Mar-2023", 0.075898, 360.33226, 1.21436 ),
        ( "22-Sep-2023", 0.078958, 374.86000, 1.26332 ),
    ]),
    ( "0 5/8% Index-linked Treasury Gilt 2040", [
        ( "22-Mar-2023", 0.520056, 360.33226, 1.66418 ),
        ( "22-Sep-2023", 0.541022, 374.86000, 1.73127 ),
    ]),
    ( "0 1/8% Index-linked Treasury Gilt 2041", [
        ( "10-Feb-2023", 0.080113, 358.97500, 1.28180 ),
        ( "10-Aug-2023", 0.083827, 375.61935, 1.34123 ),
    ]),
    ( "0 5/8% Index-linked Treasury Gilt 2042", [
        ( "22-May-2023", 0.538809, 366.32903, 1.72419 ),
        ( "22-Nov-2023", 0.555769, 377.86000, 1.77846 ),
    ]),
    ( "0 1/8% Index-linked Treasury Gilt 2044", [
        ( "22-Mar-2023", 0.092899, 360.33226, 1.48638 ),
        ( "22-Sep-2023", 0.096644, 374.86000, 1.54631 ),
    ]),
    ( "0 5/8% Index-linked Treasury Gilt 2045", [
        ( "22-Sep-2023", 0.258899, 374.86000, 1.03000 ),
    ]),
    ( "0 1/8% Index-linked Treasury Gilt 2046", [
        ( "22-Mar-2023", 0.087361, 360.33226, 1.39777 ),
        ( "22-Sep-2023", 0.090883, 374.86000, 1.45413 ),
    ]),
    ( "0¾% Index-linked Treasury Gilt 2047", [
        ( "22-May-2023", 0.661193, 366.32903, 1.76318 ),
        ( "22-Nov-2023", 0.682001, 377.86000, 1.81867 ),
    ]),
    ( "0 1/8% Index-linked Treasury Gilt 2048", [
        ( "10-Feb-2023", 0.081647, 358.97500, 1.30635 ),
        ( "10-Aug-2023", 0.085433, 375.61935, 1.36692 ),
    ]),
    ( "0½% Index-linked Treasury Gilt 2050", [
        ( "22-Mar-2023", 0.422133, 360.33226, 1.68853 ),
        ( "22-Sep-2023", 0.439153, 374.86000, 1.75661 ),
    ]),
    ( "0 1/8% Index-linked Treasury Gilt 2051", [
        ( "22-Mar-2023", 0.076573, 360.33226, 1.22516 ),
        ( "22-Sep-2023", 0.079659, 374.86000, 1.27455 ),
    ]),
    ( "0¼% Index-linked Treasury Gilt 2052", [
        ( "22-Mar-2023", 0.186084, 360.33226, 1.48867 ),
        ( "22-Sep-2023", 0.193586, 374.86000, 1.54869 ),
    ]),
    ( "1¼% Index-linked Treasury Gilt 2055", [
        ( "22-May-2023", 1.191238, 366.32903, 1.90598 ),
        ( "22-Nov-2023", 1.228731, 377.86000, 1.96597 ),
    ]),
    ( "0 1/8% Index-Linked Treasury Gilt 2056", [
        ( "22-May-2023", 0.086436, 366.32903, 1.38298 ),
        ( "22-Nov-2023", 0.089157, 377.86000, 1.42651 ),
    ]),
    ( "0 1/8% Index-linked Treasury Gilt 2058", [
        ( "22-Mar-2023", 0.088011, 360.33226, 1.40817 ),
        ( "22-Sep-2023", 0.091559, 374.86000, 1.46494 ),
    ]),
    ( "0 3/8% Index-linked Treasury Gilt 2062", [
        ( "22-Mar-2023", 0.286489, 360.33226, 1.52794 ),
        ( "22-Sep-2023", 0.298039, 374.86000, 1.58954 ),
    ]),
    ( "0 1/8% Index-linked Treasury Gilt 2065", [
        ( "22-May-2023", 0.087913, 366.32903, 1.40661 ),
        ( "22-Nov-2023", 0.090680, 377.86000, 1.45088 ),
    ]),
    ( "0 1/8% Index-linked Treasury Gilt 2068", [
        ( "22-Mar-2023", 0.090191, 360.33226, 1.44306 ),
        ( "22-Sep-2023", 0.093828, 374.86000, 1.50124 ),
    ]),
    ( "0 1/8% Index-linked Treasury Gilt 2073", [
        ( "22-Mar-2023", 0.073044, 360.33226, 1.16870 ),
        ( "22-Sep-2023", 0.075988, 374.86000, 1.21581 ),
    ]),
]


@pytest.mark.parametrize("entry", il_cash_flows, ids=operator.itemgetter(0))
def test_il_cash_flows(issued, entry):
    settlement_date = next_business_day(datetime.date(2023, 1, 1))

    name, dividends = entry
    for gilt in issued.filter(index_linked=True):
        if gilt.name == name:
            cash_flows = dict(gilt.cash_flows(max(settlement_date, gilt.issue_date)))

            abs_tol = 1.5e-6 if gilt.issue_date.year >= 2002 else 1.5e-4

            for dividend_date, dividend_amount, ref_rpi, index_ratio in dividends:
                dividend_date = datetime.datetime.strptime(dividend_date, '%d-%b-%Y').date()

                assert dividend_date in cash_flows

                assert gilt.ref_rpi(dividend_date) == ref_rpi

                assert gilt.index_ratio(dividend_date) == approx(index_ratio, abs=5e-6)

                amount = cash_flows[dividend_date]

                assert amount == approx(dividend_amount, abs=abs_tol)

            return

    raise AssertionError(f'{name} not found')


# Estimated Redemption Payments for Index-linked Gilts, taken from
# https://www.dmo.gov.uk/data/pdfdatareport?reportCode=D9C
# on 2023-12-08 with assumed inflation rates of 0% and 3%
il_estimated_redemptions = [
    #  Name                                         0%       3%
    ( "0 1/8% Index-linked Treasury Gilt 2024",   155.85,  156.87 ),
    ( "2½% Index-linked Treasury Stock 2024",     386.82,  387.77 ),
    ( "0 1/8% Index-linked Treasury Gilt 2026",   146.30,  156.23 ),
    ( "1¼% Index-linked Treasury Gilt 2027",      194.68,  218.42 ),
    ( "0 1/8% Index-linked Treasury Gilt 2028",   135.30,  155.06 ),
    ( "0 1/8% Index-linked Treasury Gilt 2029",   159.13,  185.70 ),
    ( "4 1/8% Index-linked Treasury Stock 2030",  279.64,  334.73 ),
    ( "0 1/8% Index-linked Treasury Gilt 2031",   128.68,  161.14 ),
    ( "1¼% Index-linked Treasury Gilt 2032",      174.00,  226.34 ),
    ( "0¾% Index-linked Treasury Gilt 2033",      101.49,  135.99 ),
    ( "0¾% Index-linked Treasury Gilt 2034",      162.68,  220.11 ),
    ( "2% Index-linked Treasury Stock 2035",      217.63,  297.56 ),
    ( "0 1/8% Index-linked Treasury Gilt 2036",   145.30,  212.75 ),
    ( "1 1/8% Index-linked Treasury Gilt 2037",   186.81,  281.74 ),
    ( "0 1/8% Index-linked Treasury Gilt 2039",   127.32,  199.72 ),
    ( "0 5/8% Index-linked Treasury Gilt 2040",   174.49,  281.93 ),
    ( "0 1/8% Index-linked Treasury Gilt 2041",   134.90,  227.09 ),
    ( "0 5/8% Index-linked Treasury Gilt 2042",   177.82,  310.92 ),
    ( "0 1/8% Index-linked Treasury Gilt 2044",   155.84,  283.44 ),
    ( "0 5/8% Index-linked Treasury Gilt 2045",   103.81,  194.46 ),
    ( "0 1/8% Index-linked Treasury Gilt 2046",   146.55,  282.77 ),
    ( "0¾% Index-linked Treasury Gilt 2047",      181.84,  368.62 ),
    ( "0 1/8% Index-linked Treasury Gilt 2048",   137.49,  284.69 ),
    ( "0½% Index-linked Treasury Gilt 2050",      177.04,  384.50 ),
    ( "0 1/8% Index-linked Treasury Gilt 2051",   128.46,  287.35 ),
    ( "0¼% Index-linked Treasury Gilt 2052",      156.08,  359.66 ),
    ( "1¼% Index-linked Treasury Gilt 2055",      196.57,  504.86 ),
    ( "0 1/8% Index-Linked Treasury Gilt 2056",   142.63,  377.35 ),
    ( "0 1/8% Index-linked Treasury Gilt 2058",   147.64,  406.26 ),
    ( "0 3/8% Index-linked Treasury Gilt 2062",   160.20,  496.19 ),
    ( "0 1/8% Index-linked Treasury Gilt 2065",   145.07,  500.85 ),
    ( "0 1/8% Index-linked Treasury Gilt 2068",   151.30,  559.65 ),
    ( "0 1/8% Index-linked Treasury Gilt 2073",   122.54,  525.48 ),
]

@pytest.mark.parametrize("entry", il_estimated_redemptions, ids=operator.itemgetter(0))
def test_il_estimated_redemption(issued, entry):
    settlement_date = next_business_day(datetime.date(2023, 12, 8))

    from gilts import rpi

    # Truncate RPI to Oct 2023
    # XXX: Avoid monkey patching
    months = (2023 - rpi.ref_year)*12 + 10
    rpi_series = rpi.series
    try:
        rpi.series = rpi.series[:months]

        name, redemption_0, redemption_3 = entry
        for gilt in issued.filter(index_linked=True):
            if gilt.name == name:
                years = (gilt.maturity - settlement_date).days / 365.25

                for inflation_rate, redemption_exp in [
                    (0.00, redemption_0),
                    (None, redemption_3),
                ]:

                    cash_flows = list(gilt.cash_flows(settlement_date, inflation_rate=inflation_rate))

                    _, redemption = cash_flows[-1]

                    assert redemption == approx(redemption_exp, abs=2e-2, rel=1e-3)

                return
    finally:
        rpi.series = rpi_series

    raise AssertionError(f'{name} not found')


@pytest.mark.parametrize("lag", [0, 2])
@pytest.mark.parametrize("interest_rate", [0.0, 0.02])
@pytest.mark.parametrize("marginal_income_tax", [0.0, 0.40])
@pytest.mark.parametrize("index_linked", [False, True])
@pytest.mark.parametrize("count,amount,shift", [
    (50   , 10000, shift_year ),
    (10*12,  1000, shift_month),
])
#@pytest.mark.parametrize("count,amount,shift,index_linked,marginal_income_tax,interest_rate,lag", [(10, 10000, shift_year, True, 0.40, 0.25, 0)])
def test_bond_ladder(issued, prices, count, amount, shift, index_linked, marginal_income_tax, interest_rate, lag):
    s = schedule(count, amount, shift)
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
