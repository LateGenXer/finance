#!/usr/bin/env python3


#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import math

from datetime import date

import pytest

from pytest import approx

from rpi import RPI


def test_rpi():

    rpi = RPI()

    assert len(rpi.series) >= 442

    assert rpi.value(date(1987,  1,  1)) == 100.0

    assert rpi.value(date(2023,  9,  1)) == approx(378.4)
    assert rpi.value(date(2023, 10,  1)) == approx(377.8)

    assert rpi.value(date(2023,  9, 16)) == approx(378.1)

    last_date = rpi.last_date()
    assert last_date >= date(2023, 10, 1)

    assert rpi.value(last_date) == rpi.series[-1]

    d0 = last_date
    d1 = d0.replace(year = d0.year + d0.month // 12, month = d0.month % 12 + 1)
    assert rpi.estimate(d1) / rpi.value(d0) == approx(1.03**(1.0/12.0))

