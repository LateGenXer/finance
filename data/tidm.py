#!/usr/bin/env python3
#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import csv
import datetime
import logging
import operator
import os

from gilts.gilts import Issued
from data import lse


def main():
    logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s %(message)s', level=logging.INFO)

    tidms = {}

    for isin, tidm in csv.reader(open('data/tidm.csv', 'rt')):
        assert lse.is_isin(isin)
        assert lse.is_tidm(tidm)
        tidms[isin] = tidm

    today = datetime.datetime.now(datetime.timezone.utc).date()

    for entry in csv.DictReader(open('tests/data/dmo_issued.csv', 'rt')):
        isin = entry['ISIN_CODE']
        assert lse.is_isin(isin)
        if isin in tidms:
            continue
        maturity = Issued._parse_date(entry['REDEMPTION_DATE'])
        if maturity < today:
            continue
        try:
            tidm = lse.lookup_tidm(isin)
        except (IndexError, KeyError):
            continue
        assert lse.is_tidm(tidm)
        tidms[isin] = tidm

    # https://realpython.com/sort-python-dictionary/
    tidms = dict(sorted(tidms.items(), key=operator.itemgetter(0)))

    with open('data/.tidm.csv', 'wt') as stream:
        for isin, tidm in tidms.items():
            stream.write(f'{isin},{tidm}\n')

    os.replace('data/.tidm.csv', 'data/tidm.csv')


if __name__ == '__main__':
    main()
