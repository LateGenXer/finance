#
# Copyright (c) 2024-2025 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import copy
import datetime
import dataclasses
import io
import json
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

from environ import ci
from cgtcalc import calculate, DisposalResult, TaxYear
from report import TextReport, HtmlReport


data_dir = os.path.join(os.path.dirname(__file__), 'data')


def collect_filenames(no_raises=False):
    filenames = []
    for filename in glob(os.path.join(data_dir, 'cgtcalc', '*.tsv')):
        if no_raises:
            _, raises, _  = read_test_annotations(filename)
            if raises is not None:
                continue
        name, _ = os.path.splitext(os.path.basename(filename))
        filenames.append(pytest.param(filename, id=name))
    return filenames


class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.date):
            return str(obj)
        if isinstance(obj, Decimal):
            _, _, exponent = obj.as_tuple()
            if isinstance(exponent, str) or exponent < 0:
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
    stream = open(filename, 'wt')
    json.dump(obj, stream, indent=2, cls=JSONEncoder)
    stream.write('\n')


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
        tax_year = TaxYear.from_string(tyr['tax_year'])
        result[tax_year] = tyr
    return result


tax_year_section_re = re.compile(r'^TAX_YEAR (\d\d)-(\d\d)$')
disposal_re = re.compile(r'^\d+\. SELL: (?P<shares>[0-9]+)\S* (shares of\s+\S+ )?(?P<security>\S+) on (?P<date>\S+) at £(?P<price>\S+) gives (?P<sign>\w+) of £(?P<gain>\S+)$')
tax_return_1_re = re.compile(r'^(?P<year1>\d\d)-(?P<year2>\d\d): Disposal Proceeds = £(?P<proceeds>\S+) , Allowable Costs = £(?P<costs>\S+) , Disposals = (\d+)$')
tax_return_2_re = re.compile(r'^(?P<year1>\d\d)-(?P<year2>\d\d): Year Gains = £(?P<gains>\S+) ,? Year Losses = £(?P<losses>\S+)$')

def parse_cgtcalculator_result(filename):
    result:dict[tuple,dict] = {}

    tax_year = None
    for line in open(filename, 'rt'):
        line = line.rstrip('\n')

        mo = tax_year_section_re.match(line)
        if mo is not None:
            tax_year1 = int('20' + mo.group(1))
            tax_year2 = int('20' + mo.group(2))
            assert tax_year1 + 1 == tax_year2
            tax_year = TaxYear(tax_year1, tax_year2)

        mo = disposal_re.match(line)
        if mo is not None:
            date = datetime.datetime.strptime(mo.group('date'), '%d/%m/%Y').date()
            security = mo.group('security')
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

            try:
                tyr = result[tax_year]
            except KeyError:
                tyr = {
                    'tax_year': f'{tax_year1}/{tax_year2}',
                    'disposals': [],
                    'proceeds': None,
                    'costs': None,
                    'gains': Decimal(0),
                    'losses': Decimal(0),
                }
                result[tax_year] = tyr
            tyr['disposals'].append(disposal)

        mo = tax_return_1_re.match(line)
        if mo is not None:
            tax_year1 = int('20' + mo.group('year1'))
            tax_year2 = int('20' + mo.group('year2'))
            tax_year = TaxYear(tax_year1, tax_year2)
            tyr = result[tax_year]
            tyr["proceeds"] = Decimal(mo.group('proceeds').replace(',', ''))
            tyr["costs"] = Decimal(mo.group('costs').replace(',', ''))
        mo = tax_return_2_re.match(line)
        if mo is not None:
            tax_year1 = int('20' + mo.group('year1'))
            tax_year2 = int('20' + mo.group('year2'))
            tax_year = TaxYear(tax_year1, tax_year2)
            tyr = result[tax_year]
            tyr["gains"] = Decimal(mo.group('gains').replace(',', ''))
            tyr["losses"] = Decimal(mo.group('losses').replace(',', ''))

    for tyr in result.values():
        disposals = tyr['disposals']

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

        # XXX: Even when disposals are not split, CGTCalculator internally
        # accumulates the gains and losses on a matching basis
        tyr["gains"] = Decimal(0)
        tyr["losses"] = Decimal(0)
        for disposal in disposals:
            assert isinstance(disposal['gain'], Decimal)
            gain = disposal['gain']
            if gain >= Decimal(0):
                tyr["gains"] += gain
            else:
                tyr["losses"] -= gain

    return result


def read_test_annotations(filename):
    raises:type[BaseException]|None = None
    expected_warnings = {
        'cgtcalc.py is still work in progress!',
    }
    rounding = True

    warning_prefix = '# WARNING: '
    for line in open(filename, 'rt'):
        line = line.rstrip('\n')
        if line.startswith(warning_prefix):
            warning = line[len(warning_prefix):]
            expected_warnings.add(warning)
        if line == '# NOT_IMPLEMENTED_ERROR':
            raises = NotImplementedError
        if line == '# ASSERTION_ERROR':
            raises = AssertionError
        if line == '# VALUE_ERROR':
            raises = ValueError
        if line == '# NO_ROUNDING':
            rounding = False

    return expected_warnings, raises, rounding


@pytest.mark.parametrize("filename", collect_filenames())
def test_calculate(filename):
    expected_warnings, raises, rounding = read_test_annotations(filename)

    with open(filename, 'rt') as istream:
        if raises is None:
            result = calculate(istream, rounding=rounding)
        else:
            with pytest.raises(raises):
                result = calculate(istream, rounding=rounding)
            return

    result.write(TextReport(io.StringIO()))


    name, _ = os.path.splitext(filename)
    if os.path.isfile(name + '.json'):
        expected_result = parse_json_result(name + '.json')
    elif os.path.isfile(name + '.txt'):
        expected_result = parse_cgtcalculator_result(name + '.txt')
    else:
        encode_json_result(result, name + '.json')
        return

    assert set(result.warnings) == expected_warnings

    assert sorted(result.tax_years) == list(result.tax_years)

    assert result.tax_years.keys() == expected_result.keys()

    abs_tol = 2.0 if rounding else 0.02

    for tax_year in expected_result.keys():
        tyr = result.tax_years[tax_year]
        expected_tyr = expected_result[tax_year]
        disposals = tyr.disposals
        expected_disposals = expected_tyr["disposals"]

        for disposal, expected_disposal in zip(disposals, expected_disposals, strict=True):
            try:
                assert disposal.date == expected_disposal['date']
                assert disposal.security == expected_disposal['security']
                assert disposal.shares == expected_disposal['shares']
                assert disposal.proceeds == pytest.approx(expected_disposal['proceeds'], abs=abs_tol)

                gain = disposal.proceeds - disposal.costs
                assert round(gain) == pytest.approx(round(expected_disposal['gain']), abs=abs_tol)
            except:
                pp(dataclasses.asdict(disposal))
                pp(expected_disposal)
                raise

        assert round(tyr.proceeds) == pytest.approx(round(expected_tyr['proceeds']), abs=abs_tol)
        assert round(tyr.costs) == pytest.approx(round(expected_tyr['costs']), abs=abs_tol)
        assert round(tyr.gains) == pytest.approx(round(expected_tyr['gains']), abs=abs_tol)
        assert round(tyr.losses) == pytest.approx(round(expected_tyr['losses']), abs=abs_tol)


str_to_tax_year_params = [
    ("2023/2024", nullcontext(TaxYear(2023, 2024))),
    ("2023/24",   nullcontext(TaxYear(2023, 2024))),
    ("23/2024",   nullcontext(TaxYear(2023, 2024))),
    ("23/24",     nullcontext(TaxYear(2023, 2024))),
    ("2024",      nullcontext(TaxYear(2023, 2024))),
    ("24",        nullcontext(TaxYear(2023, 2024))),
    ("00",        nullcontext(TaxYear(1999, 2000))),
    ("0",         pytest.raises(ValueError)),
    ("10000",     pytest.raises(ValueError)),
    ("XX/YY",     pytest.raises(ValueError)),
    ("YY",        pytest.raises(ValueError)),
    ("2023/2025", pytest.raises(ValueError)),
]

@pytest.mark.parametrize("s,eyc", [pytest.param(s, eyc, id=s) for s, eyc in str_to_tax_year_params])
def test_str_to_tax_year(s, eyc):
    with eyc as ey:
        assert TaxYear.from_string(s) == ey


@pytest.mark.parametrize("filename", collect_filenames(no_raises=True))
def test_filter_tax_year(filename):
    _, _, rounding = read_test_annotations(filename)

    result = calculate(open(filename, 'rt'), rounding=rounding)

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
    filtered_result.filter_tax_year(TaxYear(9998, 9999))
    assert not filtered_result.tax_years


@pytest.mark.parametrize("filename", collect_filenames(no_raises=True))
def test_report_html(filename):
    _, _, rounding = read_test_annotations(filename)

    result = calculate(open(filename, 'rt'), rounding=rounding)

    html = io.StringIO()
    result.write(HtmlReport(html))

    # Validate HTML with Tidy if present
    try:
        subprocess.check_call(['tidy', '-v'])
    except (FileNotFoundError, subprocess.CalledProcessError):
        if ci:
            raise
        else:
            pytest.skip('no tidy')
    else:
        p = subprocess.Popen(['tidy', '-q', '-e'], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        assert p.stdin is not None
        p.stdin.write(html.getvalue().encode('utf-8'))
        p.stdin.close()
        p.wait()
        assert p.stderr is not None
        errors = io.TextIOWrapper(p.stderr).readlines()
        assert not errors
        assert p.returncode == 0


def test_main():
    filename = os.path.join(data_dir, 'cgtcalc', 'cgtcalculator-example1.tsv')

    from cgtcalc import __file__ as cgtcalc_path

    subprocess.check_call(args=[
            sys.executable,
            cgtcalc_path,
            '--tax-year', '2015/2016',
            filename
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL)

    with pytest.raises(subprocess.CalledProcessError):
        subprocess.check_call(args=[
                sys.executable,
                cgtcalc_path,
                '--tax-year', '2015/2017',
                filename
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)

    subprocess.check_call(args=[
            sys.executable,
            cgtcalc_path,
            '--format', 'html',
            filename
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL)
