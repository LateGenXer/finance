#!/usr/bin/env python3
#
# SPDX-License-Identifier: Unlicense
#

#
# Converts from http://cgtcalculator.com/instructions.htm#tradeformat
# to https://github.com/mattjgalloway/cgtcalc?tab=readme-ov-file#input-data
#
# It avoids decimal <-> floating point conversions and rounding.
#
# Usage: cgtcalculator2cgtcalc.py input.tsv > output.tsv
#


import datetime
import sys
import csv


def translate(istream, ostream):
    for fields in csv.reader(istream, delimiter='\t'):
        if not fields:
            ostream.write('\n')
            continue

        event, date, company = fields[:3]
        rest = fields[3:]

        if event in ('B', 'BUY'):
            shares, price, charges, tax = fields[3:]
            float_tax = float(tax)
            if float_tax:
                charges = f'{float(charges) + float_tax:.2f}'
            row = ['BUY', date, company, shares, price, charges]
        elif event in ('S', 'SELL'):
            shares, price, charges, tax = fields[3:]
            float_tax = float(tax)
            assert float_tax == 0.0
            row = ['SELL', date, company, shares, price, charges]
        elif event == 'R':
            factor, = fields[3:]
            float_factor = float(factor)
            if float_factor >= 1:
                row = ['UNSPLIT', date, company, factor]
            else:
                row = ['SPLIT', date, company, f'{1.0 / float_factor:.6g}']
        elif event == 'B/S':
            # Ignore header
            continue
        else:
            raise NotImplementedError(event)

        ostream.write('\t'.join(row) + '\n')


def main():
    for arg in sys.argv[1:]:
        translate(open(arg, 'rt'), sys.stdout)


if __name__ == '__main__':
    main()
