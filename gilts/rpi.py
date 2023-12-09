#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import csv
import datetime
import io
import os.path
import logging
import re
import sys
import urllib.request

import requests

from download import download

import caching

from pprint import pp


logger = logging.getLogger('rpi')


_months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
_monthly_re = re.compile('^(?P<year>[0-9]{4}) (?P<month>[A-Z]{3})$')

_long_months = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

_next_release_re = re.compile(r'^(?P<day>[0-9]+) (?P<month>[A-Z][a-z]+) (?P<year>[0-9]+)$')


class OutOfDateError(Exception):

    pass


# https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/chaw/mm23
class RPI:

    ref_year = 1987

    def __init__(self, filename=None):
        if filename is None:
            self.series = self._load()
        else:
            self.series = self._parse(filename, ignore_date=True)
        assert self.series

    _url = 'https://www.ons.gov.uk/generator?format=csv&uri=/economy/inflationandpriceindices/timeseries/chaw/mm23'

    @classmethod
    def _load(cls):
        filename = os.path.join(os.path.dirname(__file__), 'rpi-series.csv')
        try:
            return cls._parse(filename)
        except (FileNotFoundError, OutOfDateError):
            download(RPI._url, filename)
            return cls._parse(filename)

    def last_date(self):
        months = len(self.series) - 1
        year = self.ref_year + months // 12
        month = months % 12 + 1
        return datetime.date(year, month, 1)

    @staticmethod
    @caching.cache_data(ttl=24*3600)
    def _parse(filename, verbosity=0, ignore_date=False):
        stream = open(filename, 'rt')
        series = []
        next_year = RPI.ref_year
        next_month = 1
        for row in csv.reader(stream):
            if verbosity >= 2:
                print(row)
            if len(row) != 2:
                continue
            date, value = row
            if date == "Next release":
                mo = _next_release_re.match(value)
                assert mo
                year = int(mo.group('year'))
                month = _long_months.index(mo.group('month')) + 1
                day = int(mo.group('day'))
                next_release = datetime.date(year, month, day)
                if datetime.datetime.utcnow().date() > next_release:
                    logger.warning(f'{filename} has been superseded on {next_release}')
                    raise OutOfDateError
            mo = _monthly_re.match(date)
            if not mo:
                continue
            year = int(mo.group('year'))
            month = _months.index(mo.group('month')) + 1
            date = datetime.date(year, month, 1)
            value = float(value)
            if verbosity >= 1:
                print(f'{date}, {value:.1f}')
            assert year == next_year
            assert month == next_month
            series.append(value)
            next_year += next_month // 12
            next_month = next_month % 12 + 1
        return series

    # https://www.dmo.gov.uk/media/0ltegugd/igcalc.pdf
    def _index(self, date):
        assert date.year >= self.ref_year
        return (date.year - self.ref_year)*12 + (date.month - 1)

    # https://www.dmo.gov.uk/media/1sljygul/yldeqns.pdf,
    # Annex B: Method of indexation for index-linked gilts with a 3-month indexation lag
    def _interpolate(self, date, rpi0, rpi1):
        date0 = date.replace(day = 1)
        date1 = date.replace(year = date.year + date.month // 12, month = date.month % 12 + 1, day=1)

        rpi = rpi0 + ((date.day - 1)/(date1 - date0).days) * (rpi1 - rpi0)
        rpi = round(rpi, 5)

        return rpi

    def value(self, date):
        assert date.year >= self.ref_year

        idx = self._index(date)
        rpi0 = self.series[idx]
        if date.day == 1:
            return rpi0
        rpi1 = self.series[idx + 1]

        return self._interpolate(date, rpi0, rpi1)

    def latest(self):
        return self.series[-1]

    def _extrapolate(self, idx, inflation_rate):
        try:
            return self.series[idx]
        except IndexError:
            months = idx + 1 - len(self.series)
            return self.series[-1] * (1 + inflation_rate) ** (months / 12)

    def estimate(self, date, inflation_rate=.03):
        idx = self._index(date)
        rpi0 = self._extrapolate(idx, inflation_rate)
        if date.day == 1:
            return rpi0
        rpi1 = self._extrapolate(idx + 1, inflation_rate)

        return self._interpolate(date, rpi0, rpi1)


