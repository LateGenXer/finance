#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#

#
# Script to convert the Historical Prices and Yields
# https://www.dmo.gov.uk/data/gilt-market/historical-prices-and-yields/
# in Excel format to the CSV format used by Tradeweb
#


import csv
import datetime
import operator
import re
import sys

import xlrd  # type: ignore[import-untyped]

from gilts.gilts import Issued


# DMO columns:
#  "Gilt Name","ISIN Code","Redemption Date","Close of Business Date","Clean Price (£)","Dirty Price (£)","Accrued Interest (£)","Yield (%)","Modified Duration"

# Tradeweb columns
fieldnames = ["Gilt Name","Close of Business Date","ISIN","Type","Coupon","Maturity","Clean Price","Dirty Price","Yield","Mod Duration","Accrued Interest"]


index_linked_re = re.compile(r'.*\bI(ndex)? *-l(inked)?\b.*', re.IGNORECASE)

assert index_linked_re.match('2½% Index-linked Treasury Stock 2020') is not None


def fmt2(x):
    if x is None:
        return "N/A"
    else:
        return f'{x:.2f}'

def fmt3(x):
    if x is None:
        return "N/A"
    else:
        return f'{x:.3f}'

def fmt6(x):
    if x is None:
        return "N/A"
    else:
        return f'{x:.6f}'


def convert(input, output):
    entries = []

    header_row = 4

    wb = xlrd.open_workbook(input)
    sh = wb.sheet_by_index(0)
    header = []
    for value in sh.row_values(header_row):
        value = value.replace(' \n', ' ')
        value = value.replace('\n', ' ')
        header.append(value)
    for rowx in range(header_row + 1, sh.nrows):
        row = []
        for cell in sh.row(rowx):
            if cell.ctype == xlrd.XL_CELL_DATE:
                value = datetime.datetime(*xlrd.xldate_as_tuple(cell.value, sh.book.datemode)).date()
            elif cell.ctype == xlrd.XL_CELL_EMPTY:
                value = None
            else:
                value = cell.value
            row.append(value)

        fields = dict(zip(header, row))

        print(row)

        isin = fields['ISIN Code']
        if isin is None or len(isin) != 12:
            continue

        try:
            name = fields['Gilt Name']

            if index_linked_re.match(name):
                type_ = 'Index-linked'
            elif name.find('Strip') >= 0:
                type_ = 'Strips'
            else:
                type_ = 'Conventional'

            if type_ == 'Strips':
                coupon = None
            else:
                coupon = Issued._parse_coupon(name)

            assert fields['Redemption Date'] is not None

            entry = {}
            entry['Gilt Name'] = name
            entry['Close of Business Date'] = fields['Close of Business Date']
            entry['ISIN'] = isin
            entry['Type'] = type_
            entry['Coupon'] = coupon
            entry['Maturity'] = fields['Redemption Date']
            entry['Clean Price'] = fields['Clean Price (£)']
            entry['Dirty Price'] = fields['Dirty Price (£)']
            entry['Yield'] = fields['Yield (%)']
            entry['Mod Duration'] = fields['Modified Duration']
            entry['Accrued Interest'] = fields['Accrued Interest (£)']

        except Exception:
            print(row)
            raise

        entries.append(entry)

    entries.sort(key=operator.itemgetter('Close of Business Date'))

    w = csv.DictWriter(open(output, "wt"), fieldnames, lineterminator='\n')
    w.writeheader()
    for entry in entries:
        entry['Close of Business Date'] = entry['Close of Business Date'].strftime('%d/%m/%Y')
        entry['Coupon'] = fmt3(entry['Coupon'])
        entry['Maturity'] = entry['Maturity'].strftime('%d/%m/%Y')
        if entry['Type'] == 'Strips':
            entry['Clean Price'] = fmt2(entry['Clean Price'])
        else:
            entry['Clean Price'] = fmt6(entry['Clean Price'])
        entry['Dirty Price'] = fmt6(entry['Dirty Price'])
        entry['Yield'] = fmt6(entry['Yield'])
        entry['Mod Duration'] = fmt2(entry['Mod Duration'])
        entry['Accrued Interest'] = fmt6(entry['Accrued Interest'])
        w.writerow(entry)


def main():
    for input in sys.argv[1:]:
        output = input.replace('.xls', '.csv')
        assert input != output
        sys.stderr.write(f'{input} -> {output}\n')
        convert(input, output)


if __name__ == '__main__':
    main()
