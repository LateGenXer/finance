#
# Copyright (c) 2023-2025 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import copy
import csv
import datetime
import logging
import math
import operator
import os.path
import subprocess
import sys

import pytest

from pytest import approx

from glob import glob
from typing import cast

import matplotlib.pyplot as plt

from data.rpi import RPI
from gilts.gilts import logger, Gilt, IndexLinkedGilt, Issued, GiltPrices, yield_curve
from gilts.ladder import BondLadder, schedule
from ukcalendar import is_business_day, next_business_day, shift_month, shift_year

import data.tradeweb


data_dir = os.path.join(os.path.dirname(__file__), 'data')


@pytest.mark.parametrize("coupon_date,xd_date", [
    # https://docs.londonstockexchange.com/sites/default/files/documents/dmo-private-investor-guide-to-gilts.pdf
    ((2004,  9,  7), (2004,  8, 26)),
], ids=repr)
def test_ex_dividend_date(coupon_date, xd_date):
    coupon_date = datetime.date(*coupon_date)
    xd_date = datetime.date(*xd_date)
    assert Gilt.ex_dividend_date(coupon_date) == xd_date


@pytest.fixture
def issued(scope='module'):
    rpi_filename = os.path.join(data_dir, 'rpi-series-20231115.csv')
    rpi_series = RPI(rpi_filename)
    filename = os.path.join(data_dir, 'dmo-D1A-20231201.xml')
    return Issued(filename, rpi_series=rpi_series)


gilts_closing_prices_csv = os.path.join(data_dir, 'gilts-closing-prices-20231201.csv')


@pytest.fixture
def prices(scope='module'):
    return GiltPrices.from_last_close(gilts_closing_prices_csv)


@pytest.mark.parametrize('filename', [
    pytest.param(None, id="cached"),
    pytest.param(gilts_closing_prices_csv, id="local"),
])
def test_prices_last_close(filename):
    prices = GiltPrices.from_last_close(filename)
    isin, tidm = 'GB00BBJNQY21', 'TR68'
    assert prices.lookup_tidm(isin) == tidm
    assert prices.get_price(tidm) >= 0
    assert isinstance(prices.get_prices_date(), datetime.datetime)


def test_prices_latest():
    prices = GiltPrices.from_latest()
    isin, tidm = 'GB00BLBDX619', 'TR73'
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


@pytest.fixture
def tradeweb_issued(scope='module'):
    entries = {}
    for entry in csv.DictReader(open(os.path.join(data_dir, '..', '..', 'data', 'dmo_issued.csv'), 'rt')):
        isin = entry['ISIN_CODE']
        entries[isin] = entry
    return entries


@pytest.fixture
def tradeweb_rpi(scope='module'):
    return RPI()


# https://reports.tradeweb.com/closing-prices/gilts/ > Type: Gilts Only > Export
tradeweb_csvs = [
    'Tradeweb_FTSE_ClosePrices_20231201.csv',
    'Tradeweb_FTSE_ClosePrices_TS27.csv',
    'Tradeweb_FTSE_ClosePrices_T24.csv',
    'Tradeweb_FTSE_ClosePrices_T2IL.csv', # long first dividend
]


# Allow to use external data
try:
    tradeweb_data_dir = os.environ['TRADEWEB_DATA']
except KeyError:
    pass
else:
    tradeweb_csvs = [os.path.relpath(f, data_dir) for f in glob(os.path.join(tradeweb_data_dir, 'Tradeweb_FTSE_ClosePrices_????????.csv'))]


def tradeweb_parse():
    params = []
    isins:dict[str, list] = {}
    for tradeweb_csv in tradeweb_csvs:
        filename = os.path.join(data_dir, tradeweb_csv)
        for row in data.tradeweb.parse(filename):
            assert row['Type'] in ('Conventional', 'Index-linked')
            params.append(pytest.param([row], id=f"{row['Gilt Name'].replace(' ', '_')}@{row['Close of Business Date']}"))
            isins.setdefault(row['ISIN'], []).append(row)

    # Group params by gilt
    if not int(os.environ.get('TRADEWEB_SPLIT', '0')):
        return [ pytest.param(entries, id=entries[0]['Gilt Name'].replace(' ', '_')) for entries in isins.values() ]

    return params


def tradeweb_str_to_float(s:str, na:float=math.nan) -> float:
    if s == 'N/A':
        return na
    else:
        return float(s)


@pytest.mark.parametrize("entries", tradeweb_parse())
def test_tradeweb(caplog, tradeweb_issued, tradeweb_rpi, entries):
    caplog.set_level(logging.DEBUG, logger="gilts")

    row = entries[0]

    type_ = row["Type"]
    assert type_ in ["Conventional", "Index-linked"]

    isin = row['ISIN']
    try:
        entry = tradeweb_issued[isin]
    except KeyError:
        pytest.skip()

    for name, value in entry.items():
        logger.debug('%s = %s', name, value)
    logger.debug('')

    conventional = type_ == 'Conventional'

    coupon = float(row['Coupon'])

    maturity = datetime.datetime.strptime(row['Maturity'], '%d/%m/%Y').date()

    name = entry['INSTRUMENT_NAME']
    kwargs = {
        'name': name,
        'isin': entry['ISIN_CODE'],
        'coupon': Issued._parse_coupon(name),
        'maturity': Issued._parse_date(entry['REDEMPTION_DATE']),
        'issue_date': Issued._parse_date(entry['FIRST_ISSUE_DATE']),
    }

    gilt:Gilt|IndexLinkedGilt
    if conventional:
        gilt = Gilt(**kwargs)

    for row in entries:
        for name, value in row.items():
            logger.debug('%s = %s', name, value)
        logger.debug('')

        assert row['ISIN'] == isin

        close_date = datetime.datetime.strptime(row['Close of Business Date'], '%d/%m/%Y').date()

        if not conventional:
            # Truncate RPI series to match close TradeWeb close date
            rpi_series = copy.deepcopy(tradeweb_rpi)
            index = rpi_series.lookup_index(close_date)
            rpi_series.series = rpi_series.series[:index]

            kwargs['base_rpi'] = float(entry['BASE_RPI_87'])
            kwargs['rpi_series'] = rpi_series
            gilt = IndexLinkedGilt(**kwargs)

        assert gilt.maturity == maturity
        assert gilt.type_ == type_
        assert gilt.coupon == coupon

        settlement_date = next_business_day(close_date)

        # Tradweb publishes close prices when trading before issued and after the final ex-dividend date
        if settlement_date < gilt.issue_date or \
           settlement_date > gilt.ex_dividend_date(maturity):
            continue

        clean_price = tradeweb_str_to_float(row['Clean Price'])
        accrued_interest = tradeweb_str_to_float(row['Accrued Interest'], na=0.0)
        dirty_price = tradeweb_str_to_float(row['Dirty Price'])

        if math.isnan(dirty_price):
            continue
        assert not math.isnan(clean_price)

        # Ensure Tradeweb's clean and dirty prices are consistent
        if conventional or cast(IndexLinkedGilt, gilt).lag == 8:
            assert clean_price + accrued_interest == approx(dirty_price, abs=1e-6)
        else:
            assert isinstance(gilt, IndexLinkedGilt)
            index_ratio = gilt.index_ratio(settlement_date)
            assert clean_price * index_ratio + accrued_interest == approx(dirty_price, abs=1e-6)

        accrued_interest_ = gilt.accrued_interest(settlement_date)
        dirty_price_ = gilt.dirty_price(clean_price, settlement_date)

        # Tradeweb accrued interest looks off when maturity happens after a weekend
        if settlement_date >= gilt.maturity:
            continue

        abs_tol = 1e-6 if conventional or cast(IndexLinkedGilt, gilt).lag == 3 else 1e-4
        assert accrued_interest_ == approx(accrued_interest, abs=abs_tol)
        assert dirty_price_ == approx(dirty_price, abs=abs_tol)

        if row['Yield'] == 'N/A':
            continue

        ytm = float(row['Yield'])
        gilt_ytm = gilt.ytm(dirty_price, settlement_date)
        if not conventional:
            gilt_ytm = (1.0 + gilt_ytm)/(1.0 + IndexLinkedGilt.inflation_rate) - 1.0
        gilt_ytm *= 100.0

        logger.debug(f'YTM: {gilt_ytm:8.6f} vs {ytm:8.6f} (abs={gilt_ytm - ytm:+9.6f} rel={gilt_ytm/ytm -1:+.1e})')

        if conventional:
            if settlement_date >= shift_month(maturity, -6):
                # Tradeweb uses simple interest, and a slightly different day count convention

                redemption = maturity if is_business_day(maturity) else next_business_day(maturity)
                days = (redemption - settlement_date).days
                expected_ytm = ((coupon/2 + 100)/dirty_price - 1) / (days / 365) * 100
                assert expected_ytm == approx(ytm, rel=1e-5)

                r = (maturity - settlement_date).days
                s = (maturity - shift_month(maturity, -6)).days
                expected_gilt_ytm = 2 * (((coupon/2 + 100) / dirty_price) ** (s/r) - 1) * 100
                assert gilt_ytm == approx(expected_gilt_ytm, rel=1e-5)
            elif settlement_date >= shift_year(maturity, -1):
                # XXX: Tradeweb seems to be using simple interest
                # (non-compounding) for all bonds maturing less than one year
                assert gilt_ytm == approx(ytm, rel=5e-2)
            else:
                assert gilt_ytm == approx(ytm, abs=5e-6)


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


@pytest.mark.parametrize("issue_date,maturity,redemption_fixed", [
    # 3m
    ("2005-09-22", "2013-12-01", "2013-09-01"),
    ("2005-09-22", "2013-12-02", "2013-10-01"),
    ("2005-09-22", "2013-12-31", "2013-10-01"),

    # 8m
    ("2005-09-21", "2013-12-01", "2013-04-01"),
    ("2005-09-21", "2013-12-02", "2013-04-01"),
    ("2005-09-21", "2013-12-31", "2013-04-01"),
])
def test_redemption_fixed(issue_date, maturity, redemption_fixed):
    coupon = 0
    maturity = datetime.date.fromisoformat(maturity)
    issue_date = datetime.date.fromisoformat(issue_date)
    redemption_fixed = datetime.date.fromisoformat(redemption_fixed)

    isin="0"*12

    g = IndexLinkedGilt(name=None, isin=isin, coupon=coupon, maturity=maturity, issue_date=issue_date, base_rpi=100.0, rpi_series = None)
    redemption_fixed_ = g.redemption_fixed()

    assert redemption_fixed_ == redemption_fixed


@pytest.mark.parametrize("entry", il_cash_flows, ids=operator.itemgetter(0))
def test_il_cash_flows(issued, entry):
    settlement_date = next_business_day(datetime.date(2023, 1, 1))

    name, dividends = entry
    for gilt in issued.filter(index_linked=True, settlement_date=settlement_date):
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

    assert issued.rpi_series.last_date() == datetime.date(2023, 10, 1)

    name, redemption_0, redemption_3 = entry
    for gilt in issued.filter(index_linked=True, settlement_date=settlement_date):
        if gilt.name == name:
            for inflation_rate, redemption_exp in [
                (0.00, redemption_0),
                (None, redemption_3),
            ]:

                cash_flows = list(gilt.cash_flows(settlement_date, inflation_rate=inflation_rate))

                _, redemption = cash_flows[-1]

                assert redemption == approx(redemption_exp, abs=2e-2, rel=1e-3)

            return

    raise AssertionError(f'{name} not found')


def test_issued_latest():
    rpi_series = RPI()
    Issued(rpi_series=rpi_series)


@pytest.mark.parametrize("lag", [0, 24])
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
    assert df is not None
    for cf in df.itertuples():
        assert math.isnan(cf.In) != math.isnan(cf.Out)
        assert not cf.In < 0.005
        assert not cf.Out < 0.005

        assert cf.Balance > -0.005

    withdrawals = df['Out'].loc[df['Description'] == 'Withdrawal'].sum()
    withdrawals_exp = sum([value for _, value in s])
    assert withdrawals == approx(withdrawals_exp, abs=0.005)

    income_loc = df['Tax. Inc.'] == df['Tax. Inc.']
    incoming = df['In'].loc[income_loc].sum()
    income = df['Tax. Inc.'].loc[income_loc].sum()
    assert income <= incoming + .005


def test_ladder_main():
    cmd = [
        sys.executable, '-m',
        'gilts.ladder',
        os.path.join(data_dir, 'test_schedule.csv')
    ]
    output = subprocess.check_output(cmd, text=True)
    assert output
