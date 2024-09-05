#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import copy
import datetime
import dataclasses
import io
import json
import logging
import operator
import os.path
import re
import subprocess
import sys

import pytest

from contextlib import nullcontext
from decimal import Decimal
from glob import glob
from pprint import pp

from cgtcalc import *


data_dir = os.path.join(os.path.dirname(__file__), 'data')


def collect_filenames():
    filenames = []
    for filename in glob(os.path.join(data_dir, 'cgtcalc', '*.tsv')):
        name, _ = os.path.splitext(os.path.basename(filename))
        filenames.append(pytest.param(filename, id=name))
    return filenames


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.date):
            return str(obj)
        if isinstance(obj, Decimal):
            _, _, exponent = obj.as_tuple()
            if exponent == 'n' or exponent < 0:
                return float(obj)
            else:
                assert Decimal(int(obj)) == obj
                return int(obj)
        if isinstance(obj, DisposalResult):
            return {
                'date': obj.date,
                'security': obj.security,
                'shares': obj.shares,
                'proceeds': obj.proceeds,
                'gain': obj.proceeds - obj.costs
            }
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return {field.name: getattr(obj, field.name) for field in dataclasses.fields(obj)}
        return super().default(obj)


def encode_json_result(result, filename):
    obj = list(result.tax_years.values())
    json.dump(obj, open(filename, 'wt'), indent=2, cls=JSONEncoder)


def object_hook(obj):
    try:
        date = obj['date']
    except KeyError:
        pass
    else:
        obj['date'] = datetime.date.fromisoformat(date)
    return obj


def parse_json_result(filename):
    result = {}
    for tyr in json.load(open(filename, 'rt'), parse_float=Decimal, object_hook=object_hook):
        tax_year = str_to_tax_year(tyr['tax_year'])
        result[tax_year] = tyr['disposals']
    return result


tax_year_re = re.compile(r'^TAX_YEAR (\d\d)-(\d\d)$')
disposal_re = re.compile(r'^\d+\. SELL: (?P<shares>[0-9]+)\S* (shares of\s+\S+ )?(?P<security>\S+) on (?P<date>\S+) at £(?P<price>\S+) gives (?P<sign>\w+) of £(?P<gain>\S+)$')

def parse_cgtcalculator_result(filename):
    result = {}

    tax_year = None
    for line in open(filename, 'rt'):
        line = line.rstrip('\n')

        mo = tax_year_re.match(line)
        if mo is not None:
            tax_year1 = int('20' + mo.group(1))
            tax_year2 = int('20' + mo.group(2))
            assert tax_year1 + 1 == tax_year2
            tax_year = tax_year1, tax_year2

        mo = disposal_re.match(line)
        if mo is not None:
            date = datetime.datetime.strptime(mo.group('date'), '%d/%m/%Y').date()
            security = mo.group('security')
            print(mo.group('shares'))
            shares = Decimal(mo.group('shares'))
            price = Decimal(mo.group('price'))
            proceeds = shares*price
            gain = Decimal(mo.group('gain').replace(',', ''))
            assert mo.group('sign') in ('GAIN', 'LOSS')
            if mo.group('sign') == 'LOSS':
                gain = -gain

            disposal = {
                'date': date,
                'security': security,
                'shares': shares,
                'proceeds': proceeds,
                'gain': gain
            }

            assert tax_year is not None
            disposals = result.setdefault(tax_year, [])
            disposals.append(disposal)

    for disposals in result.values():
        disposals.sort(key=operator.itemgetter('date', 'security'))

        # Sometimes cgtcalculator splits disposals, especially when all shares are liquidated
        i = 0
        while i + 1 < len(disposals):
            disposal0 = disposals[i + 0]
            disposal1 = disposals[i + 1]
            if disposal0['date'] == disposal1['date'] and disposal0['security'] == disposal1['security']:
                disposal0['shares'] += disposal1['shares']
                disposal0['proceeds'] += disposal1['proceeds']
                disposal0['gain'] += disposal1['gain']
                disposals.pop(i + 1)
            else:
                i += 1
        assert disposals
    return result


@pytest.mark.parametrize("filename", collect_filenames())
def test_calculate(caplog, filename):
    caplog.set_level(logging.DEBUG, logger="cgtcal")

    result = calculate(open(filename, 'rt'))
    stream = io.StringIO()
    result.write(stream)

    name, _ = os.path.splitext(filename)
    if os.path.isfile(name + '.json'):
        expected_result = parse_json_result(name + '.json')
    elif os.path.isfile(name + '.txt'):
        expected_result = parse_cgtcalculator_result(name + '.txt')
    else:
        encode_json_result(result, name + '.json')
        return

    pp(result)
    pp(expected_result)

    assert sorted(result.tax_years) == list(result.tax_years)

    assert result.tax_years.keys() == expected_result.keys()

    for tax_year in expected_result.keys():
        disposals = result.tax_years[tax_year].disposals
        expected_disposals = expected_result[tax_year]

        for disposal, expected_disposal in zip(disposals, expected_disposals, strict=True):
            print(disposal, 'vs', expected_disposal)

            assert disposal.date == expected_disposal['date']
            assert disposal.security == expected_disposal['security']
            assert disposal.shares == expected_disposal['shares']
            assert disposal.proceeds == pytest.approx(expected_disposal['proceeds'], abs=2)

            gain = disposal.proceeds - disposal.costs
            assert round(gain) == pytest.approx(round(expected_disposal['gain']), abs=2)


str_to_tax_year_params = [
    ("2023/2024", nullcontext((2023, 2024))),
    ("2023/24",   nullcontext((2023, 2024))),
    ("23/2024",   nullcontext((2023, 2024))),
    ("23/24",     nullcontext((2023, 2024))),
    ("2024",      nullcontext((2023, 2024))),
    ("24",        nullcontext((2023, 2024))),
    ("00",        nullcontext((1999, 2000))),
    ("0",         pytest.raises(ValueError)),
    ("10000",     pytest.raises(ValueError)),
    ("XX/YY",     pytest.raises(ValueError)),
    ("YY",        pytest.raises(ValueError)),
    ("2023/2025", pytest.raises(ValueError)),
]

@pytest.mark.parametrize("s,eyc", [pytest.param(s, eyc, id=s) for s, eyc in str_to_tax_year_params])
def test_str_to_tax_year(s, eyc):
    with eyc as ey:
        assert str_to_tax_year(s) == ey


@pytest.mark.parametrize("filename", collect_filenames())
def test_filter_tax_year(filename):

    result = calculate(open(filename, 'rt'))

    for tax_year in result.tax_years:
        filtered_result = copy.copy(result)
        filtered_result.filter_tax_year(tax_year)

        assert tax_year in filtered_result.tax_years
        assert filtered_result.tax_years[tax_year] == result.tax_years[tax_year]

        for security, table in filtered_result.section104_tables.items():
            assert table
            pool_cost = Decimal(0)
            pool_shares = Decimal(0)
            for update in table:
                assert pool_cost + update.delta_cost == pytest.approx(update.pool_cost, abs=1)
                if not update.identified.is_nan():
                    if update.delta_cost >= Decimal(0):
                        assert pool_shares + update.identified == pytest.approx(update.pool_shares, abs=1)
                    else:
                        assert pool_shares - update.identified == pytest.approx(update.pool_shares, abs=1)
                pool_cost = update.pool_cost
                pool_shares = update.pool_shares

    filtered_result = copy.copy(result)
    filtered_result.filter_tax_year((9998, 9999))
    assert not filtered_result.tax_years


def test_main():
    filename = os.path.join(data_dir, 'cgtcalc', 'cgtcalculator-example1.tsv')

    from cgtcalc import __file__ as cgtcalc_path

    subprocess.check_call(args=[
            sys.executable,
            cgtcalc_path,
            '--tax-year', '2015/2016',
            filename
        ],
        stdout=subprocess.DEVNULL)
