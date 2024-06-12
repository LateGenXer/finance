#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import math
import os.path

from datetime import date

import pytest

from pytest import approx

from rpi import RPI, OutOfDateError


def _test(rpi):

    rpi = RPI()

    assert len(rpi.series) >= 442

    assert rpi.lookup(date(1987,  1,  1)) == 100.0

    assert rpi.interpolate(date(2023,  9,  1)) == approx(378.4)
    assert rpi.interpolate(date(2023, 10,  1)) == approx(377.8)

    assert rpi.interpolate(date(2023,  9, 16)) == approx(378.1)

    last_date = rpi.last_date()
    assert last_date >= date(2023, 10, 1)

    assert rpi.interpolate(last_date) == rpi.series[-1]
    assert rpi.latest() == rpi.series[-1]

    d0 = last_date
    d1 = d0.replace(year = d0.year + d0.month // 12, month = d0.month % 12 + 1)
    assert rpi.extrapolate(d1, .03) / rpi.interpolate(d0) == approx(1.03**(1.0/12.0))

    d2 = d0.replace(day=15)
    r = (d2 - d0).days / (d1 - d0).days
    assert rpi.extrapolate(d2, .03) / rpi.interpolate(d0) == approx(1.03**(r/12.0))


def test_rpi():
    if os.path.exists(RPI._filename):
        os.unlink(RPI._filename)

    rpi = RPI()
    _test(rpi)

    rpi = RPI()
    _test(rpi)


def test_rpi_superseded():
    filename = os.path.join(os.path.dirname(__file__), 'data', 'rpi-series-20231115.csv')
    with pytest.raises(OutOfDateError):
        series, release_date = RPI.parse(filename)
