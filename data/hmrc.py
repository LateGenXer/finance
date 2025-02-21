#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import datetime
import io
import functools

import xml.etree.ElementTree

import requests


# https://requests.readthedocs.io/en/latest/user/advanced/#keep-alive
_session = requests.Session()


@functools.lru_cache
def exchange_rates(year:int, month:int) -> dict[str, float]:
    assert year >= 2021
    assert 1 <= month and month <= 12
    url = f'https://www.trade-tariff.service.gov.uk/api/v2/exchange_rates/files/monthly_xml_{year}-{month}.xml'
    headers = {'user-agent': 'Mozilla/5.0'}
    r = _session.get(url, headers=headers, stream=False)
    assert r.ok
    stream = io.BytesIO(r.content)
    tree = xml.etree.ElementTree.parse(stream)
    root = tree.getroot()
    rates: dict[str, float] = {}
    for node in root:
        currencyCode = node.find('currencyCode')
        assert currencyCode is not None
        currency = currencyCode.text
        assert currency is not None
        rateNew = node.find('rateNew')
        assert rateNew is not None
        rateText = rateNew.text
        assert rateText is not None
        rate = float(rateText)
        rates[currency] = rate
    return rates


def exchange_rate(currency:str) -> float:
    today = datetime.datetime.now(datetime.timezone.utc).date()
    rates = exchange_rates(today.year, today.month)
    return rates[currency]
