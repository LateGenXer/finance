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
def exchange_rates(year, month):
    assert year >= 2021
    assert 1 <= month and month <= 12
    url = f'https://www.trade-tariff.service.gov.uk/api/v2/exchange_rates/files/monthly_xml_{year}-{month}.xml'
    headers = {'user-agent': 'Mozilla/5.0'}
    r = _session.get(url, headers=headers, stream=False)
    stream = io.BytesIO(r.content)
    tree = xml.etree.ElementTree.parse(stream)
    root = tree.getroot()
    rates = {}
    for node in root:
        currency = node.find('currencyCode').text
        rate = float(node.find('rateNew').text)
        rates[currency] = rate
    return rates


def exchange_rate(currency):
    today = datetime.datetime.utcnow().date()
    rates = exchange_rates(today.year, today.month)
    return rates[currency]
