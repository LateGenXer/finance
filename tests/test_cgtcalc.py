#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


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

from glob import glob
from decimal import Decimal
from pprint import pp

from cgtcalc import calculate


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
    assert results
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

    result = calculate(filename)
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


def test_main():
    filename = os.path.join(data_dir, 'cgtcalc', 'cgtcalculator-example1.tsv')

    from cgtcalc import __file__ as cgtcalc_path

    subprocess.check_call([sys.executable, cgtcalc_path, filename], stdout=subprocess.DEVNULL)
