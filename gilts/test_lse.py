#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import datetime
import os.path
import subprocess
import sys

import pytest

import lse


@pytest.mark.parametrize('isin,tidm', [
    ('GB00BBJNQY21', 'TR68'),
    ('LU1230136894', 'CSH2'),
])
def test_lookup_tidm(isin, tidm):
    assert lse.lookup_tidm(isin) == tidm


@pytest.mark.parametrize('tidm', ['TR68'])
def test_get_instrument_data(tidm):
    data = lse.get_instrument_data(tidm)
    assert isinstance(data['lastprice'], (float, int))
    assert isinstance(data['lastclose'], (float, int))


def test_get_latest_gilt_prices():
    dt, content = lse.get_latest_gilt_prices()
    for instrument in content:
        assert 'isin' in instrument
        assert 'tidm' in instrument
        assert isinstance(instrument['lastprice'], (float, int))


@pytest.mark.parametrize('prices', [
    pytest.param(lse.GiltPrices(None), id="cached"),
    pytest.param(lse.GiltPrices(os.path.join(os.path.dirname(__file__), 'gilts-closing-prices-20231201.csv')), id="local"),
    pytest.param(lse.TradewebClosePrices(), id="tradeweb"),
])
def test_prices(prices):
    isin, tidm = 'GB00BBJNQY21', 'TR68'
    assert prices.lookup_tidm(isin) == tidm
    assert prices.get_price(tidm) >= 0
    assert isinstance(prices.get_prices_date(), datetime.datetime)


def test_main():
    status = subprocess.call([sys.executable, lse.__file__])
    assert status == 0
