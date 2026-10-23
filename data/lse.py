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
import os.path
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


def is_tidm(tidm:str) -> bool:
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
    'accept': 'application/json',
    'origin': 'https://www.londonstockexchange.com',
    'referer': 'https://www.londonstockexchange.com/',
    'user-agent': 'Mozilla/5.0'
}


_api = 'https://apidata.londonstockexchange.com'


# https://requests.readthedocs.io/en/latest/user/advanced/#keep-alive
_session = requests.Session()


def _get(path:str, params:dict) -> dict:
    r = _session.get(_api + path, params=params, headers=_headers, stream=False)
    try:
        obj = r.json()
    except ValueError:
        obj = {}
    if not r.ok:
        raise ValueError(obj.get('message', str(r.status_code)))
    return obj['data']


# https://www.londonstockexchange.com/live-markets/market-data-dashboard/price-explorer
def _search(quick_filter_text:str, filter_model:dict|None=None) -> tuple[datetime.datetime, list[dict]]:
    url = _api + '/search/v1/query'
    page_size = 100
    start_row = 0
    content: list[dict] = []
    while True:
        payload = {
            'type': 'instrument',
            'group': False,
            'tradingVenue': 'LSE',
            'quickFilterText': quick_filter_text,
            'startRow': start_row,
            'endRow': start_row + page_size - 1,
        }
        if filter_model is not None:
            payload['filterModel'] = filter_model
        r = _session.post(url, headers=_headers, json=payload, stream=False)
        assert r.ok
        # This can create troubles with timezones
        dt = email.utils.parsedate_to_datetime(r.headers['Date'])
        obj = r.json()
        data = obj.get('Data', [])
        content.extend(item for item in data if item['type'] == 'instrument')
        start_row += page_size
        if not data or start_row >= obj['rowCount']:
            return dt, content


def lookup_tidm(isin:str) -> str:
    logger.info(f'Looking up TIDM of {isin}')
    _, instruments = _search(isin)
    instruments = [instrument for instrument in instruments if instrument['isin'] == isin]
    if len(instruments) != 1:
        logger.warning(f'Found {len(instruments)} TIDMs for ISIN {isin}')
    return instruments[0]['tidm']


def _parse_price(value:str|None) -> float|None:
    if value is None or value in ('', '-'):
        return None
    return float(value.replace(',', ''))


def _parse_date(value:str|None) -> datetime.date|None:
    if value is None or value in ('', '-'):
        return None
    return datetime.datetime.strptime(value, '%d %B %Y').date()


def get_instrument_data(tidm:str) -> dict:
    logger.info(f'Getting {tidm} instrument data')

    instrument = _get('/nrdp/v1', {'tidm': tidm})
    ric = _get('/rdp/v1/ric', {'tidm': tidm})['ric']
    pricing = _get('/rdp/v1/pricing', {'ric': ric})

    # Last close is formatted as "<price> on <date>"
    lastclose, _, lastclosedate = pricing.get('LAST_CLOSE_LAST_CLOSE_DATE', '').partition(' on ')
    if not lastclosedate:
        lastclose = pricing.get('LAST_CLOSE')
        lastclosedate = pricing.get('OFF_CLS_DT')
    lastclosedate_ = _parse_date(lastclosedate)

    return {
        'tidm': instrument['tidm'],
        'isin': instrument['isinCode'],
        'ric': ric,
        'name': instrument['instrumentName'],
        'currency': instrument['currency'],
        'lastprice': _parse_price(pricing.get('TRDPRC_1')),
        'lastclose': _parse_price(lastclose),
        'lastclosedate': None if lastclosedate_ is None else lastclosedate_.isoformat(),
        'bid': _parse_price(pricing.get('BID')),
        'offer': _parse_price(pricing.get('ASK')),
        'midPrice': _parse_price(pricing.get('MID_PRICE')),
    }


def get_latest_gilt_prices() -> tuple[datetime.datetime, list]:
    '''Get the latest gilt prices'''

    logger.info('Getting gilt prices from LSE')

    # https://www.londonstockexchange.com/en/price-explorer?priceExplorer_searchTag=Gilts
    # The searchTag filter alone merely ranks Gilts first, so also search for
    # TRIH (HM Treasury's issuer code) which excludes STRIPS (UKTS).
    filter_model = {'searchTag': {'filterType': 'set', 'values': ['Gilts']}}
    dt, instruments = _search('TRIH', filter_model)
    content: list[dict] = []
    for instrument in instruments:
        if instrument['issuerCode'] != 'TRIH' or 'Gilts' not in (instrument['searchTag'] or []):
            continue
        lastprice = _parse_price(instrument['price'])
        if lastprice is None:
            continue
        content.append({
            'isin': instrument['isin'],
            'tidm': instrument['tidm'],
            'ric': instrument['ric'],
            'description': instrument['instrumentName'],
            'currency': instrument['currency'],
            'lastprice': lastprice,
        })
    return dt, content


def main() -> None:
    logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s %(message)s', level=logging.INFO)

    dt, content = get_latest_gilt_prices()

    isins = set()
    latestclosedate = datetime.date(datetime.MINYEAR, 1, 1)

    w = csv.writer(sys.stdout, lineterminator='\n')

    th = ['date', 'isin', 'tidm', 'price']
    w.writerow(th)

    for item in content:
        isin = item['isin']
        tidm = item['tidm']

        data = get_instrument_data(tidm)

        try:
            assert data['tidm'] == tidm
            assert data['isin'] == isin
            assert data['currency'] == 'GBP'

            lastclose = data['lastclose']
            if lastclose is None:
                # Newly auctioned gilts often start with a null closing price
                continue

            lastclosedate = datetime.datetime.fromisoformat(data['lastclosedate']).date()

        except Exception:  # pragma: no cover
            pp(data, stream=sys.stderr)
            raise

        tr = [lastclosedate.isoformat(), isin, tidm, lastclose]
        w.writerow(tr)

        isins.add(isin)
        latestclosedate = max(latestclosedate, lastclosedate)

    # LSE sometimes gives incomplete data when ongoing maitenance
    from gilts.gilts import Issued
    issued = Issued(csv_filename = os.path.join(os.path.dirname(__file__), 'dmo_issued.csv'), rpi_series=None)
    from ukcalendar import next_business_day
    settlement_date = next_business_day(latestclosedate)

    status = 0
    for gilt in issued.filter(settlement_date=settlement_date):
        if gilt.isin not in isins:
            sys.stderr.write(f'error: {gilt.isin} ({gilt.short_name()}): price missing\n')
            status = 1
    sys.exit(status)


if __name__ == '__main__':
    main()
