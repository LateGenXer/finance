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
import math
import sys

from decimal import Decimal


def translate(istream, ostream):
    for line in istream:
        line = line.rstrip('\n')
        if line.startswith('#'):
            continue
        fields = line.split()
        if not fields:
            ostream.write('\n')
            continue

        event, date, company = fields[:3]
        rest = fields[3:]

        if event in ('B', 'BUY'):
            shares, price, charges, tax = fields[3:]
            float_tax = Decimal(tax)
            if float_tax:
                charges = str(Decimal(charges) + float_tax)
            row = ['BUY', date, company, shares, price, charges]
        elif event in ('S', 'SELL'):
            shares, price, charges, tax = fields[3:]
            float_tax = Decimal(tax)
            assert not float_tax
            row = ['SELL', date, company, shares, price, charges]
        elif event == 'R':
            factor, = fields[3:]
            float_factor = Decimal(factor)
            if float_factor >= 1:
                row = ['UNSPLIT', date, company, factor]
            else:
                float_factor = Decimal(1) / float_factor
                int_factor = round(float_factor)
                print(float_factor, int_factor)
                assert math.isclose(float_factor, int_factor, abs_tol=.05)
                factor = str(int_factor)
                row = ['SPLIT', date, company, factor]
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
