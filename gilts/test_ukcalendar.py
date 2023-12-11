#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import pytest

from datetime import date

from ukcalendar import *



@pytest.mark.parametrize("year,month,day,result", [
    (1998,  1,  1, True),
    (2110, 12, 26, True),
    (2023, 11, 17, False),
])
def test(year,month,day,result):
    assert isukbankholiday(date(year, month, day)) == result


# https://docs.londonstockexchange.com/sites/default/files/documents/dmo-private-investor-guide-to-gilts.pdf
d = [
    (2004,  8, 26),
    (2004,  8, 27),
    (2004,  8, 31),
    (2004,  9,  1),
    (2004,  9,  2),
    (2004,  9,  3),
    (2004,  9,  6),
    (2004,  9,  7),
]
d = [(d[i], d[i + 1]) for i in range(len(d) - 1)]


@pytest.mark.parametrize("d0,d1", d, ids=lambda val: str(date(*val)))
def test_prev_business_day(d0, d1):
    d0 = date(*d0)
    d1 = date(*d1)
    assert prev_business_day(d1) == d0


@pytest.mark.parametrize("d0,d1", d, ids=repr)
def test_next_business_day(d0, d1):
    d0 = date(*d0)
    d1 = date(*d1)
    assert next_business_day(d0) == d1


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
    from ukcalendar import main
    try:
        main()
    except ValueError:
        pytest.skip("captcha")
