#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import copy
import datetime
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

from cgtcalc import calculate, str_to_tax_year, date_to_tax_year


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
            return float(obj)
        return super().default(obj)


def parse_json_results(filename):
    results = []
    for disposal in json.load(open(filename, 'rt'), parse_float=Decimal):
        date, security, gain = disposal
        date = datetime.date.fromisoformat(date)
        gain = round(gain, 2)
        results.append((date, security, gain))
    return results


disposal_re = re.compile(r'^\d+\. SELL: \S+ (shares of\s+\S+ )?(?P<security>\S+) on (?P<date>\S+) at £\S+ gives (?P<sign>\w+) of £(?P<gain>\S+)$')

def parse_cgtcalculator_results(filename):
    results = []
    for line in open(filename, 'rt'):
        line = line.rstrip('\n')

        mo = disposal_re.match(line)
        if mo is not None:
            date = datetime.datetime.strptime(mo.group('date'), '%d/%m/%Y').date()
            security = mo.group('security')
            gain = Decimal(mo.group('gain').replace(',', ''))
            assert mo.group('sign') in ('GAIN', 'LOSS')
            if mo.group('sign') == 'LOSS':
                gain = -gain
            results.append((date, security, gain))

    results.sort(key=operator.itemgetter(0, 1))

    # Sometimes cgtcalculator splits disposals, especially when all shares are liquidated
    i = 0
    while i + 1 < len(results):
        date0, security0, gain0 = results[i + 0]
        date1, security1, gain1 = results[i + 1]
        if date0 == date1 and security0 == security1:
            gain = gain0 + gain1
            results[i] = date0, security0, gain
            results.pop(i + 1)
        else:
            i += 1

    assert results
    return results


@pytest.mark.parametrize("filename", collect_filenames())
def test_calculate(caplog, filename):
    caplog.set_level(logging.DEBUG, logger="cgtcal")

    result = calculate(open(filename, 'rt'))
    stream = io.StringIO()
    result.write(stream)

    results = [(disposal.date, disposal.security, disposal.proceeds - disposal.costs) for disposal in result.disposals]

    name, _ = os.path.splitext(filename)
    if os.path.isfile(name + '.json'):
        expected_results = parse_json_results(name + '.json')
    elif os.path.isfile(name + '.txt'):
        expected_results = parse_cgtcalculator_results(name + '.txt')
    else:
        json.dump(results, open(name + '.json', 'wt'), indent=2, cls=JSONEncoder)
        return

    pp(results)
    pp(expected_results)

    for disposal, expected_disposal in zip(results, expected_results, strict=True):
        print(disposal, 'vs', expected_disposal)
        date, security, gain = disposal
        expected_date, expected_security, expected_gain = expected_disposal

        assert date == expected_date
        assert security == expected_security

        assert round(gain) == pytest.approx(round(expected_gain), abs=2)


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

    total_disposals = 0
    for tax_year in result.tax_years:
        filtered_result = copy.copy(result)
        filtered_result.filter_tax_year(tax_year)

        assert tax_year in filtered_result.tax_years
        assert len(filtered_result.disposals) == result.tax_years[tax_year].disposals
        for disposal in filtered_result.disposals:
            assert date_to_tax_year(disposal.date) == tax_year
        total_disposals += len(filtered_result.disposals)

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

    assert len(result.disposals) == total_disposals


    filtered_result = copy.copy(result)
    filtered_result.filter_tax_year((9998, 9999))
    assert not filtered_result.tax_years
    assert not filtered_result.disposals


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
