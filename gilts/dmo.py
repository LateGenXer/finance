#!/usr/bin/env python3
#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import csv

from pprint import pp

from gilts import Issued


fieldnames = [
    'INSTRUMENT_TYPE',
    'INSTRUMENT_NAME',
    'ISIN_CODE',
    'REDEMPTION_DATE',
    'FIRST_ISSUE_DATE',
    'BASE_RPI_87',
]


def write(filename='dmo-D1A.csv'):
    with open(filename, 'wt') as stream:
        w = csv.DictWriter(stream, fieldnames, extrasaction='ignore')
        w.writeheader()
        for entry in Issued.load_xml():
            pp(entry)
            w.writerow(entry)


if __name__ == '__main__':
    write()
