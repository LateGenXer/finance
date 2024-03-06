#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import datetime
import io

import xml.etree.ElementTree

import requests


# https://taxsummaries.pwc.com/portugal/individual/taxes-on-personal-income
income_tax_bands = [
   ( 7703, 0.1325),
   (11623, 0.1800),
   (16472, 0.2300),
   (21321, 0.2600),
   (27146, 0.3275),
   (39791, 0.3700),
   (51997, 0.4350),
   (81199, 0.4500),
   ( None, 0.4800),
]


cgt_rate = 0.28


def _gbpeur():
    today = datetime.datetime.utcnow().date()
    url = f'https://www.trade-tariff.service.gov.uk/api/v2/exchange_rates/files/monthly_xml_{today.year}-{today.month}.xml'
    headers = {'user-agent': 'Mozilla/5.0'}
    r = requests.get(url, headers=headers)
    stream = io.BytesIO(r.content)
    tree = xml.etree.ElementTree.parse(stream)
    root = tree.getroot()
    for node in root:
        currency = node.find('currencyCode').text
        rate = float(node.find('rateNew').text)
        if currency == 'EUR':
            return rate
    raise ValueError


gbpeur = _gbpeur()


def income_tax(gross_income, factor=1.0):
    tax = 0
    lbound = 0
    for ubound, rate in income_tax_bands:
        delta = max(gross_income - lbound, 0)
        if ubound is not None:
            ubound *= factor
            delta = min(delta, ubound - lbound)
        tax += delta * rate
        lbound = ubound
    assert tax <= gross_income
    return tax
