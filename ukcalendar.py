#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import os.path
import datetime


__all__ = [
    'is_business_day',
    'next_business_day',
    'prev_business_day',
    'days_in_month',
    'ukbankholidays',
    'isukbankholiday',
    'shift_year',
    'shift_month',
]


def is_business_day(date):
    return date.weekday() < 5 and not isukbankholiday(date)


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


_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

def days_in_month(year, month):
    if month == 2:
        return 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28
    else:
        return _days_in_month[month - 1]


def shift_year(date, years=1):
    assert isinstance(date, datetime.date)
    year = date.year + years
    month = date.month
    day = min(date.day, days_in_month(year, month))
    return date.replace(year=year, month=month, day=day)


def shift_month(date, months=1):
    assert isinstance(date, datetime.date)
    year_month = date.year*12 + date.month - 1 + months
    year = year_month // 12
    month = year_month % 12 + 1
    day = min(date.day, days_in_month(year, month))
    return date.replace(year=year, month=month, day=day)


def isukbankholiday(date):
    assert isinstance(date, datetime.date)
    return (date.year, date.month, date.day) in ukbankholidays


# Bank holidays from
# - https://www.dmo.gov.uk/publications/gilt-market/formulae-and-examples/
#     https://www.dmo.gov.uk/media/bfknrcrn/ukbankholidays-jul19.xls
# with corrections from
# - https://www.api.gov.uk/gds/bank-holidays/
#     curl -s https://www.gov.uk/bank-holidays.json | jq -r '.["england-and-wales"].events[].date'
def _read():
    dates = set()
    filename = os.path.join(os.path.dirname(__file__), 'ukbankholidays.csv')
    with open(filename, 'rt') as stream:
        for line in stream:
            date = datetime.datetime.strptime(line[:-1], "%Y-%m-%d").date()
            dates.add((date.year, date.month, date.day))
    return dates


ukbankholidays = _read()


def main():
    """Generate ukbankholidays.csv."""

    import xlrd
    from download import download

    # https://www.dmo.gov.uk/publications/gilt-market/formulae-and-examples/
    # XXX Merge https://www.api.gov.uk/gds/bank-holidays/ too
    #     `curl -s https://www.gov.uk/bank-holidays.json | jq -r '.["england-and-wales"].events[].date'`
    url = 'https://www.dmo.gov.uk/media/3lgd2zqc/ukbankholidays-nov23a.xls'
    filename = os.path.basename(url)
    download(url, filename, ttl=24*3600, content_type='application/vnd.ms-excel')
    wb = xlrd.open_workbook('ukbankholidays-nov23a.xls')
    sh = wb.sheet_by_index(0)
    for rowx in range(1, sh.nrows):
        cell = sh.cell(rowx, 0)
        assert cell.ctype == xlrd.XL_CELL_DATE
        date = datetime.datetime(*xlrd.xldate_as_tuple(cell.value, sh.book.datemode)).date()
        print(f'{date.strftime("%Y-%m-%d")}')


if __name__ == '__main__':  # pragma: no cover
    main()
