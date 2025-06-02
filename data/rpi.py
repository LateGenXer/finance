#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import csv
import datetime
import os.path
import logging
import re

from download import download



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

    def __init__(self, filename:str|None=None):
        if filename is None:
            self.series, self.release_date = self._load()
        else:
            self.series, self.release_date = self.parse(filename, ignore_date=True)
        assert self.series
        assert self.release_date >= self.last_date()

    _url = 'https://lategenxer.github.io/finance/rpi-series.csv'
    _filename = os.path.join(os.path.dirname(__file__), 'rpi-series.csv')

    @classmethod
    def _load(cls) -> tuple[list[float], datetime.date]:
        download(RPI._url, cls._filename)
        return cls.parse(cls._filename)

    def last_date(self) -> datetime.date:
        months = len(self.series) - 1
        year = self.ref_year + months // 12
        month = months % 12 + 1
        return datetime.date(year, month, 1)

    @staticmethod
    def parse(filename:str, ignore_date:bool=False) -> tuple[list[float], datetime.date]:
        stream = open(filename, 'rt')
        series:list[float] = []
        next_year = RPI.ref_year
        next_month = 1
        release_date = None
        for row in csv.reader(stream):
            assert len(row) == 2
            label, value = row
            if label == "Release date":
                release_date = datetime.datetime.strptime(value, '%d-%m-%Y').date()
            elif label == "Next release":
                mo = _next_release_re.match(value)
                assert mo
                year = int(mo.group('year'))
                month = _long_months.index(mo.group('month')) + 1
                day = int(mo.group('day'))
                next_release = datetime.date(year, month, day)
                if datetime.datetime.now(datetime.timezone.utc).date() > next_release and not ignore_date:
                    logger.warning(f'{filename} has been superseded on {next_release}')
                    raise OutOfDateError
            else:
                mo = _monthly_re.match(label)
                if not mo:
                    continue
                year = int(mo.group('year'))
                month = _months.index(mo.group('month')) + 1
                rpi = float(value)
                assert year == next_year
                assert month == next_month
                series.append(rpi)
                next_year += next_month // 12
                next_month = next_month % 12 + 1
        assert release_date is not None
        return series, release_date

    # https://www.dmo.gov.uk/media/0ltegugd/igcalc.pdf
    def lookup_index(self, date:datetime.date) -> int:
        assert date.year >= self.ref_year
        return (date.year - self.ref_year)*12 + (date.month - 1)

    def lookup(self, date:datetime.date) -> float:
        month_idx = self.lookup_index(date)
        return self.series[month_idx]

    # https://www.dmo.gov.uk/media/1sljygul/yldeqns.pdf,
    # Annex B: Method of indexation for index-linked gilts with a 3-month indexation lag
    @staticmethod
    def _interpolate(date:datetime.date, rpi0:float, rpi1:float) -> float:
        date0 = date.replace(day = 1)
        date1 = date.replace(year = date.year + date.month // 12, month = date.month % 12 + 1, day=1)

        rpi = rpi0 + ((date.day - 1)/(date1 - date0).days) * (rpi1 - rpi0)
        rpi = round(rpi, 5)

        return rpi

    def interpolate(self, date:datetime.date) -> float:
        assert date.year >= self.ref_year

        month_idx = self.lookup_index(date)
        rpi0 = self.series[month_idx]
        if date.day == 1:
            return rpi0
        rpi1 = self.series[month_idx + 1]

        return self._interpolate(date, rpi0, rpi1)

    def latest(self) -> float:
        return self.series[-1]

    # https://www.dmo.gov.uk/media/1sljygul/yldeqns.pdf
    # ANNEX A: Estimation of the nominal values of future unknown cash
    # flows on index-linked gilts with an 8-month indexation lag.
    def extrapolate_from_index(self, month_idx:int, inflation_rate:float) -> float:
        try:
            return self.series[month_idx]
        except IndexError:
            months = month_idx + 1 - len(self.series)
            return self.series[-1] * (1 + inflation_rate) ** (months / 12)

    def extrapolate(self, date:datetime.date, inflation_rate:float) -> float:
        month_idx = self.lookup_index(date)
        rpi0 = self.extrapolate_from_index(month_idx, inflation_rate)
        if date.day == 1:
            return rpi0
        rpi1 = self.extrapolate_from_index(month_idx + 1, inflation_rate)

        return self._interpolate(date, rpi0, rpi1)


