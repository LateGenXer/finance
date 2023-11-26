"""London Stock Exchange helpers."""


#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import atexit
import csv
import datetime
import email.utils
import logging
import os.path
import pickle
import re
import requests
import sys
import pprint

import caching


__all__ = [
    'LSE',
]


logger = logging.getLogger('lse')


_headers = {
    'authority': 'api.londonstockexchange.com',
    'accept': 'application/json',
    'origin': 'https://www.londonstockexchange.com',
    'referer': 'https://www.londonstockexchange.com/',
    'user-agent': 'Mozilla/5.0'
}


# Tradable Instrument Display Mnemonics (TIDM)
_tidm_re = re.compile(r'^https://www\.londonstockexchange\.com/stock/(?P<tidm>\w+)/.*$')


@caching.cache_data(ttl=24*3600)
def lookup_tidm(isin):
    # https://www.londonstockexchange.com/live-markets/market-data-dashboard/price-explorer?categories=BONDS&subcategories=14
    url = f'https://api.londonstockexchange.com/api/gw/lse/search?worlds=quotes&q={isin}'
    r = requests.get(url, headers=_headers, stream=False)
    assert r.ok

    obj = r.json()

    mo = _tidm_re.match(obj['instruments'][0]['url'])
    assert mo
    tidm = mo.group('tidm')

    return tidm


@caching.cache_data(ttl=15*60)
def get_instrument_data(tidm):
    url = f'https://api.londonstockexchange.com/api/gw/lse/instruments/alldata/{tidm}'
    r = requests.get(url, headers=_headers, stream=False)
    assert r.ok
    obj = r.json()
    return obj


_tidm_csv = os.path.join(os.path.dirname(__file__), 'tidm.csv')


@caching.cache_data(ttl=15*60)
def get_latest_gilt_prices():
    '''Get the latest gilt prices with a single request'''

    logger.warning('Getting gilt prices from LSE...\n')

    # https://www.londonstockexchange.com/live-markets/market-data-dashboard/price-explorer?issuers=TRIH&categories=BONDS
    # https://www.londonstockexchange.com/live-markets/market-data-dashboard/price-explorer?issuers=TRIH&categories=BONDS&page=2
    payload = {
        "path": "live-markets/market-data-dashboard/price-explorer",
        "parameters": "issuers%3DTRIH%26categories%3DBONDS",
        "components": [
            {
                "componentId": "block_content%3A9524a5dd-7053-4f7a-ac75-71d12db796b4",
                "parameters":"categories=BONDS&issuers=TRIH&size=100"
            }
        ]
    }
    headers = _headers.copy()
    headers['content-type'] = 'application/json'
    url ='https://api.londonstockexchange.com/api/v1/components/refresh'
    r = requests.post(url, headers=headers, json=payload)
    assert r.ok
    if False:
        # XXX: this creates troubles with timezones
        date = email.utils.parsedate_to_datetime(r.headers['Date'])
    else:
        date = datetime.datetime.now()
    obj = r.json()
    for item in obj[0]['content']:
        if item['name'] == 'priceexplorersearch':
            value = item['value']
            assert value['first'] is True
            assert value['last'] is True
            return date, value['content']
    raise ValueError


class Prices:

    def __init__(self):
        pass

    def lookup_tidm(self, isin):
        raise NotImplementedError

    def get_price(self, isin):
        raise NotImplementedError

    def get_prices_date(self):
        raise NotImplementedError


class CachedPrices(Prices):

    def __init__(self):
        Prices.__init__(self)
        self._init_tidms()
        self._init_data()
        self.datetime = datetime.datetime(1980, 1, 1, 0, 0, 0)

    def _init_tidms(self):
        self.tidms = {}

        try:
            self.stream = open(_tidm_csv, 'r+b')
        except FileNotFoundError:
            self.stream = open(_tidm_csv, 'wb')
        else:
            for line in self.stream:
                line = line.decode('ascii')
                line = line.rstrip('\r\n')
                isin, tidm = line.split(',')
                self.tidms[isin] = tidm

    def _init_data(self):
        try:
            stream = open('lse.pickle', 'rb')
        except FileNotFoundError:
            self.data = {}
        else:
            self.data = pickle.load(stream)

        self.data_dirty = False
        atexit.register(self._cleanup)

    def lookup_tidm(self, isin):
        try:
            return self.tidms[isin]
        except KeyError:
            pass

        tidm = lookup_tidm(self, isin)

        self.stream.write(f'{isin},{tidm}\n'.encode('ascii'))
        self.stream.flush()

        return tidm

    def get_price(self, tidm):
        #try:
        #    return self.data[tidm]
        #except KeyError:
        #    pass

        obj = get_instrument_data(tidm)
        logger.debug(pprint.pformat(obj, indent=2))

        self.data[tidm] = obj
        self.data_dirty = True

        self.datetime = datetime.datetime.fromisoformat(obj['lastclosedate'])

        return obj['lastprice']

    def get_prices_date(self):
        return self.datetime

    def _cleanup(self):
        if self.data_dirty:
            pickle.dump(self.data, open('lse.pickle', 'wb'))


class GiltPrices(Prices):

    def __init__(self, ttl=15*60):
        Prices.__init__(self)
        self.ttl = datetime.timedelta(seconds=ttl)
        self.datetime = datetime.datetime.now() - 2*self.ttl
        self.tidms = {}
        self.prices = {}

    def _refresh(self):
        now = datetime.datetime.now()
        if now < self.datetime + self.ttl:
            return
        self.datetime, content = get_latest_gilt_prices()
        assert now < self.datetime + self.ttl
        for price in content:
            isin = price['isin']
            tidm = price['tidm']
            self.tidms[isin] = tidm
            self.prices[tidm] = price

    def lookup_tidm(self, isin):
        try:
            return self.tidms[isin]
        except KeyError:
            self._refresh()
        return self.tidms[isin]

    def get_price(self, tidm):
        self._refresh()
        price = self.prices[tidm]
        return price['lastprice']

    def get_prices_date(self):
        return self.datetime


class TradewebClosePrices(Prices):
    # https://reports.tradeweb.com/closing-prices/gilts/ > Type: Gilts Only > Export

    default = os.path.join(os.path.dirname(__file__), 'Tradeweb_FTSE_ClosePrices_20231117.csv')

    def __init__(self, filename=default):
        self.tidms = {}
        for isin, tidm in csv.reader(open(_tidm_csv, 'rt')):
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
    def parse(filename):
        for row in csv.DictReader(open(filename, 'rt', encoding='utf-8-sig')):
            if row['Type'] in ('Conventional', 'Index-linked'):
                yield row

    def lookup_tidm(self, isin):
        return self.tidms[isin]

    def get_price(self, tidm):
        return self.prices[tidm]

    def get_prices_date(self):
        return self.datetime


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s:%(name)s:%(levelname)s:%(message)s', level=logging.INFO)
    logger.setLevel(logging.DEBUG)
    #prices = GiltPrices()
    prices = CachedPrices()
    if len(sys.argv) == 1:
        for isin, tidm in csv.reader(open(_tidm_csv, 'rt')):
            tidm = prices.lookup_tidm(isin)
            price = prices.get_price(tidm)
            print(f'{tidm} {price}')
    else:
        for tidm in sys.argv[1:]:
            price = prices.get_price(tidm)
            print(f'{tidm} {price}')
