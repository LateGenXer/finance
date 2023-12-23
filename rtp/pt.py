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
   ( 7479, 0.145),
   (11284, 0.210),
   (15992, 0.265),
   (20700, 0.285),
   (26355, 0.350),
   (38632, 0.370),
   (50483, 0.435),
   (78834, 0.450),
   ( None, 0.480),
]


cgt_rate = 0.28


def _gbpeur():
    today = datetime.datetime.utcnow().date()
    last_month = today.replace(year = (today.year*12 + today.month - 2) // 12, month = (today.month - 2) % 12 + 1, day=1)
    url = f'https://www.trade-tariff.service.gov.uk/api/v2/exchange_rates/files/monthly_xml_{last_month:%Y-%m}.xml'
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
