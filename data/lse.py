"""London Stock Exchange helpers."""


#
# Copyright (c) 2023-2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import csv
import datetime
import email.utils
import logging
import re
import requests
import string
import sys

from pprint import pp


__all__ = [
    'lookup_tidm',
    'get_instrument_data',
    'get_latest_gilt_prices',
]


logger = logging.getLogger('lse')


def is_tidm(tidm):
    if len(tidm) not in (3, 4):
        return False

    for c in tidm:
        if c not in string.ascii_uppercase + string.digits + string.punctuation:
            return False

    return True


# Luhn algorithm
def luhn(n: str) -> str:
    assert isinstance(n, str)
    assert n.isnumeric()

    ln = len(n)
    s = 0
    for i in range(ln):
        d = n[ln - i - 1]
        if i & 1 == 0:
            d = str(int(d) * 2)
        for c in d:
            s += int(c)
    ck = 10 - (s % 10)

    ck = ck % 10

    return str(ck)


# https://en.wikipedia.org/wiki/International_Securities_Identification_Number
def is_isin(ticker: str) -> bool:
    assert isinstance(ticker, str)

    if len(ticker) != 12:
        return False

    if not ticker[:2].isalpha():
        return False

    if not ticker[2:11].isalnum():
        return False

    if not ticker[11].isnumeric():
        return False

    n = ''
    for c in ticker[:11]:
        if c.isalpha():
            n += str(ord(c.upper()) - 55)
        else:
            assert c.isnumeric()
            n += c
    ck = luhn(n)

    assert ticker[11] == ck

    return True


_headers = {
    'authority': 'api.londonstockexchange.com',
    'accept': 'application/json',
    'origin': 'https://www.londonstockexchange.com',
    'referer': 'https://www.londonstockexchange.com/',
    'user-agent': 'Mozilla/5.0'
}


# Tradable Instrument Display Mnemonics (TIDM)
_tidm_re = re.compile(r'^https://www\.londonstockexchange\.com/[^/]+/(?P<tidm>[^/]+)/.*$')


# https://requests.readthedocs.io/en/latest/user/advanced/#keep-alive
_session = requests.Session()


def lookup_tidm(isin):
    logger.info(f'Looking up TIDM of {isin}')
    # https://www.londonstockexchange.com/live-markets/market-data-dashboard/price-explorer?categories=BONDS&subcategories=14
    url = f'https://api.londonstockexchange.com/api/gw/lse/search?worlds=quotes&q={isin}'
    r = _session.get(url, headers=_headers, stream=False)
    assert r.ok

    obj = r.json()

    mo = _tidm_re.match(obj['instruments'][0]['url'])
    assert mo
    tidm = mo.group('tidm')

    return tidm


def get_instrument_data(tidm):
    logger.info(f'Getting {tidm} instrument data')
    url = f'https://api.londonstockexchange.com/api/gw/lse/instruments/alldata/{tidm}'
    r = _session.get(url, headers=_headers, stream=False)
    assert r.ok
    obj = r.json()
    return obj


def get_latest_gilt_prices():
    '''Get the latest gilt prices with a single request'''

    logger.info('Getting gilt prices from LSE')

    # https://www.londonstockexchange.com/live-markets/market-data-dashboard/price-explorer?issuers=TRIH&categories=BONDS
    # https://www.londonstockexchange.com/live-markets/market-data-dashboard/price-explorer?issuers=TRIH&categories=BONDS&page=2
    payload = {
        "path": "live-markets/market-data-dashboard/price-explorer",
        "parameters": "issuers%3DTRIH%26categories%3DBONDS",
        "components": [
            {
                "componentId": "block_content%3A9524a5dd-7053-4f7a-ac75-71d12db796b4",
                "parameters": "categories=BONDS&issuers=TRIH&size=128"
            }
        ]
    }
    headers = _headers.copy()
    headers['content-type'] = 'application/json'
    url ='https://api.londonstockexchange.com/api/v1/components/refresh'
    r = _session.post(url, headers=headers, json=payload, stream=False)
    assert r.ok
    # This can create troubles with timezones
    dt = email.utils.parsedate_to_datetime(r.headers['Date'])
    obj = r.json()
    for item in obj[0]['content']:
        if item['name'] == 'priceexplorersearch':
            value = item['value']
            assert value['first'] is True
            assert value['last'] is True
            return dt, value['content']
    raise ValueError  # pragma: no cover


def main():
    logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s %(message)s', level=logging.INFO)

    dt, content = get_latest_gilt_prices()

    w = csv.writer(sys.stdout)

    th = ['date', 'isin', 'tidm', 'price']
    w.writerow(th)

    for item in content:
        isin = item['isin']
        tidm = item['tidm']

        data = get_instrument_data(tidm)

        try:
            assert data['currency'] == 'GBP'

            assert data['tidm'] == tidm
            assert data['isin'] == isin

            lastclose = data['lastclose']
            if lastclose is None:
                # Newly auctioned gilts often start with a null closing price
                continue

            lastclosedate = data['lastclosedate']
            lastclosedate = datetime.datetime.fromisoformat(lastclosedate)
            lastclosedate = lastclosedate.date()
            lastclosedate = lastclosedate.isoformat()

        except:  # pragma: no cover
            pp(data, stream=sys.stderr)
            raise

        tr = [lastclosedate, isin, tidm, lastclose]
        w.writerow(tr)


if __name__ == '__main__':
    main()
