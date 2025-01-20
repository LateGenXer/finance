#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import json
import runpy

import pytest

from datetime import date, MINYEAR, MAXYEAR

from download import download

from environ import ci
from ukcalendar import *


@pytest.mark.parametrize("year,month,day,result", [
    (1998,  1,  1, True),
    (2110, 12, 26, True),
    (2023, 11, 17, False),
])
def test_isukbankholiday(year,month,day,result):
    assert isukbankholiday(date(year, month, day)) == result


@pytest.mark.skipif(ci, reason='CI')
def test_isukbankholiday_gov_api():
    download('https://www.gov.uk/bank-holidays.json', content_type='application/json')
    obj = json.load(open('bank-holidays.json', 'rt'))
    bank_holidays = set()
    min_year = MAXYEAR
    max_year = MINYEAR
    for event in obj['england-and-wales']['events']:
        d = date.fromisoformat(event['date'])
        bank_holidays.add(d)
        min_year = min(min_year, d.year)
        max_year = max(max_year, d.year)
    for o in range(date(min_year, 1, 1).toordinal(), date(max_year + 1, 1, 1).toordinal()):
        d = date.fromordinal(o)
        assert isukbankholiday(d) is (d in bank_holidays)


# https://docs.londonstockexchange.com/sites/default/files/documents/dmo-private-investor-guide-to-gilts.pdf
dates = [
    ((2004,  8, 25), (2004,  8, 26), (2004,  8, 27), True),
    ((2004,  8, 26), (2004,  8, 27), (2004,  8, 31), True),
    ((2004,  8, 27), (2004,  8, 28), (2004,  8, 31), False),
    ((2004,  8, 27), (2004,  8, 29), (2004,  8, 31), False),
    ((2004,  8, 27), (2004,  8, 30), (2004,  8, 31), False),
    ((2004,  8, 27), (2004,  8, 31), (2004,  9,  1), True),
    ((2004,  8, 31), (2004,  9,  1), (2004,  9,  2), True),
    ((2004,  9,  1), (2004,  9,  2), (2004,  9,  3), True),
    ((2004,  9,  2), (2004,  9,  3), (2004,  9,  6), True),
    ((2004,  9,  3), (2004,  9,  4), (2004,  9,  6), False),
    ((2004,  9,  3), (2004,  9,  5), (2004,  9,  6), False),
    ((2004,  9,  3), (2004,  9,  6), (2004,  9,  7), True),
    ((2004,  9,  6), (2004,  9,  7), (2004,  9,  8), True),
]
dates = [pytest.param(date(*dp), date(*d0), date(*dn), b, id=str(date(*d0))) for dp, d0, dn, b in dates]


@pytest.mark.parametrize("dp,d0,dn,b", dates)
def test_business_days(dp, d0, dn, b):
    assert prev_business_day(d0) == dp
    assert next_business_day(d0) == dn
    assert is_business_day(d0) is b


@pytest.mark.parametrize("d0,n,d1", [
    ((2024, 2, 29),  1, (2025, 2, 28)),
    ((2024, 2, 29),  0, (2024, 2, 29)),
    ((2024, 2, 29), -1, (2023, 2, 28)),
], ids=repr)
def test_shift_year(d0, n, d1):
    assert shift_year(date(*d0), n) == date(*d1)


@pytest.mark.parametrize("d0,n,d1", [
    ((2024, 1, 31), -1, (2023, 12, 31)),
    ((2024, 1, 31),  0, (2024,  1, 31)),
    ((2024, 1, 31),  1, (2024,  2, 29)),
    ((2024, 1, 31),  1, (2024,  2, 29)),
    ((2024, 1, 31),  2, (2024,  3, 31)),
    ((2024, 1, 31),  3, (2024,  4, 30)),
    ((2024, 1, 31),  4, (2024,  5, 31)),
    ((2024, 1, 31),  5, (2024,  6, 30)),
    ((2024, 1, 31),  6, (2024,  7, 31)),
    ((2024, 1, 31),  7, (2024,  8, 31)),
    ((2024, 1, 31),  8, (2024,  9, 30)),
    ((2024, 1, 31),  9, (2024, 10, 31)),
    ((2024, 1, 31), 10, (2024, 11, 30)),
    ((2024, 1, 31), 11, (2024, 12, 31)),
    ((2024, 1, 31), 12, (2025,  1, 31)),
    ((2024, 1, 31), 13, (2025,  2, 28)),
], ids=repr)
def test_shift_month(d0, n, d1):
    assert shift_month(date(*d0), n) == date(*d1)


def test_main():
    from ukcalendar import __file__ as path
    try:
        runpy.run_path(path, run_name='__main__')
    except ValueError:
        pytest.skip("captcha")
