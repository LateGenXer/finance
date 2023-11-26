#!/usr/bin/env python3
#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import os.path
import datetime


__all__ = [
    'next_business_day',
    'prev_business_day',
    'ukbankholidays',
    'isukbankholiday',
]


def next_business_day(date):
    delta = [1, 1, 1, 1, 3, 2, 1]
    while True:
        days = delta[date.weekday()]
        date = date + datetime.timedelta(days=days)
        if not isukbankholiday(date):
            return date


def prev_business_day(date):
    delta = [3, 1, 1, 1, 1, 1, 2]
    while True:
        days = delta[date.weekday()]
        date = date - datetime.timedelta(days=days)
        if not isukbankholiday(date):
            return date


def isukbankholiday(date):
    assert isinstance(date, datetime.date)
    return (date.year, date.month, date.day) in ukbankholidays


_filename = os.path.join(os.path.dirname(__file__), 'ukbankholidays.csv')


def _write():
    import xlrd
    from download import download

    # https://www.dmo.gov.uk/publications/gilt-market/formulae-and-examples/
    # XXX: Use https://www.api.gov.uk/gds/bank-holidays/ instead?
    download('https://www.dmo.gov.uk/media/bfknrcrn/ukbankholidays-jul19.xls', ttl=10*365*24*3600, content_type='application/vnd.ms-excel')
    wb = xlrd.open_workbook('ukbankholidays-jul19.xls')
    sh = wb.sheet_by_index(0)
    with open(_filename, 'wt') as stream:
        for rowx in range(2, sh.nrows):
            cell = sh.cell(rowx, 0)
            assert cell.ctype == xlrd.XL_CELL_DATE
            date = datetime.datetime(*xlrd.xldate_as_tuple(cell.value, sh.book.datemode)).date()
            stream.write(f'{date.strftime("%Y-%m-%d")}\n')


def _read():
    dates = set()
    with open(_filename, 'rt') as stream:
        for line in stream:
            date = datetime.datetime.strptime(line[:-1], "%Y-%m-%d").date()
            dates.add((date.year, date.month, date.day))
    return dates


if __name__ == '__main__':
    _write()


ukbankholidays = _read()
