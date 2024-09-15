#!/usr/bin/env python3

import csv
import sys

from data import lse


for entry in csv.DictReader(open('tests/data/dmo_issued.csv', 'rt')):
    isin = entry['ISIN_CODE']
    assert lse.is_isin(isin)
    try:
        tidm = lse.lookup_tidm(isin)
    except (IndexError, KeyError):
        continue
    assert lse.is_tidm(tidm)
    sys.stdout.write(f'{isin},{tidm}\n')
