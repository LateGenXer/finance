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
import os.path

from gilts.gilts import Issued
from data import lse


data_dir = os.path.dirname(__file__)
tidm_csv = os.path.join(data_dir, 'tidm.csv')


def main():
    logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s %(message)s', level=logging.INFO)

    tidms = {}

    for isin, tidm in csv.reader(open(tidm_csv, 'rt')):
        assert lse.is_isin(isin)
        assert lse.is_tidm(tidm)
        tidms[isin] = tidm

    today = datetime.datetime.now(datetime.timezone.utc).date()

    for entry in csv.DictReader(open(os.path.join(data_dir, 'dmo_issued.csv'), 'rt')):
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

    _tidm_csv = os.path.join(data_dir, '.tidm.csv')

    with open(_tidm_csv, 'wt') as stream:
        for isin, tidm in tidms.items():
            stream.write(f'{isin},{tidm}\n')

    os.replace(_tidm_csv, tidm_csv)


if __name__ == '__main__':
    main()
