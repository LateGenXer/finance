#!/usr/bin/env python3


import csv
import os.path
import sys


sys.path.insert(0, os.getcwd())

from gilts.gilts import Issued


fieldnames = [
    'ISIN_CODE',
    'INSTRUMENT_NAME',
    'REDEMPTION_DATE',
    'FIRST_ISSUE_DATE',
    'BASE_RPI_87',
]


csv_path = os.path.join(os.path.dirname(__file__), 'dmo_issued.csv')


entries = {}
try:
    for entry in csv.DictReader(open(csv_path, 'rt')):
        entries[entry['ISIN_CODE']] = entry
except FileNotFoundError:
    pass


def parse(parser):
    for entry in parser:
        entry['REDEMPTION_DATE'] = Issued._parse_date(entry['REDEMPTION_DATE']).isoformat()
        entry['FIRST_ISSUE_DATE'] = Issued._parse_date(entry['FIRST_ISSUE_DATE']).isoformat()
        try:
            entry['BASE_RPI_87'] = '{:.5f}'.format(float(entry['BASE_RPI_87']))
        except KeyError:
            entry['BASE_RPI_87'] = ''

        entries[entry['ISIN_CODE']] = entry


if len(sys.argv) > 1:
    for arg in sys.argv[1:]:
        parse(Issued._parse_xml(arg))
else:
    parse(Issued._download())

isin_codes = list(entries.keys())
isin_codes.sort()

with open(csv_path, 'wt') as stream:
    w = csv.DictWriter(stream, fieldnames, extrasaction='ignore', lineterminator='\n')
    w.writeheader()
    for isin_code in isin_codes:
        entry = entries[isin_code]
        #pp(entry)
        w.writerow(entry)
