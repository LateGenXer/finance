#
# Copyright (c) 2023-2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#



import csv
import datetime
import os.path
import sys


def parse(filename):
    for entry in csv.DictReader(open(filename, 'rt', encoding='utf-8-sig')):
        if entry['Type'] in ('Conventional', 'Index-linked'):
            yield entry


# Derive gilt closing prices from Tradeweb
#
# https://reports.tradeweb.com/closing-prices/gilts/ > Type: Gilts Only > Export
#
def main():

    from data.tidm import load as load_tidms

    tidms = load_tidms()

    w = csv.writer(sys.stdout)
    th = ['date', 'isin', 'tidm', 'price']
    w.writerow(th)
    for arg in sys.argv[1:]:

        for entry in parse(arg):
            lastclosedate = datetime.datetime.strptime(entry['Close of Business Date'], '%d/%m/%Y').date()
            isin = entry['ISIN']
            price = entry['Clean Price']
            tidm = tidms[isin]

            tr = [lastclosedate, isin, tidm, price]
            w.writerow(tr)


if __name__ == '__main__':
    main()
