#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import datetime

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
    assert isinstance(data['lastprice'], float)
    assert isinstance(data['lastclose'], float)


@pytest.mark.parametrize('cls', [
    lse.GiltPrices,
    lse.CachedPrices,
    lse.TradewebClosePrices,
])
def test_prices(cls):
    prices = cls()
    isin, tidm = 'GB00BBJNQY21', 'TR68'
    assert prices.lookup_tidm(isin) == tidm
    assert prices.get_price(tidm) >= 0
    assert isinstance(prices.get_prices_date(), datetime.datetime)
