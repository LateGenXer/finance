#
# Copyright (c) 2024-2025 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import datetime
import io
import json
import os.path
import subprocess
import sys
import typing
import warnings

import pytest

from decimal import Decimal
from glob import glob

from tax.uk import TaxYear
from accrued_income import Calculator, TextReport, footnote_mark


data_dir = os.path.join(os.path.dirname(__file__), 'data')


def collect_filenames() -> list:
    filenames = []
    for filename in glob(os.path.join(data_dir, 'accrued_income', '*.csv')):
        if not os.path.islink(filename) or os.path.exists(filename):
            name, _ = os.path.splitext(os.path.basename(filename))
            filenames.append(pytest.param(filename, id=name))
    return filenames


class JSONEncoder(json.JSONEncoder):
    def default(self, obj: typing.Any) -> typing.Any:
        if isinstance(obj, datetime.date):
            return str(obj)
        if isinstance(obj, Decimal):
            _, _, exponent = obj.as_tuple()
            if isinstance(exponent, str) or exponent < 0:
                return float(obj)
            else:
                assert Decimal(int(obj)) == obj
                return int(obj)
        return super().default(obj)


def encode_json_result(calculator: Calculator, filename: str) -> None:
    obj = []
    for tax_year, entries in sorted(calculator.yearly_acrued_income.items()):
        total = sum(income for _, _, _, _, income in entries)
        obj.append({
            'tax_year': str(tax_year),
            'entries': [
                {
                    'interest_date': interest_date,
                    'transaction_date': date,
                    'gilt': gilt_state.name(),
                    'description': description,
                    'income': income,
                }
                for interest_date, date, gilt_state, description, income in entries
            ],
            'total': total,
        })
    stream = open(filename, 'wt')
    json.dump(obj, stream, indent=2, cls=JSONEncoder)
    stream.write('\n')


def parse_json_result(filename: str) -> dict:
    result = {}
    for tyr in json.load(open(filename, 'rt'), parse_float=Decimal):
        tax_year = TaxYear.from_string(tyr['tax_year'])
        for entry in tyr['entries']:
            entry['interest_date'] = datetime.date.fromisoformat(entry['interest_date'])
            entry['transaction_date'] = datetime.date.fromisoformat(entry['transaction_date'])
            entry['income'] = Decimal(str(entry['income']))
        tyr['total'] = Decimal(str(tyr['total']))
        result[tax_year] = tyr
    return result


@pytest.mark.parametrize('filename', collect_filenames())
def test_calculate(filename: str) -> None:
    name, _ = os.path.splitext(filename)
    json_filename = name + '.json'

    if os.path.isfile(json_filename):
        expected_result = parse_json_result(json_filename)
        last_tax_year = max(expected_result.keys())
        tax_year_end = last_tax_year.end_date()
    else:
        tax_year_end = None

    calculator = Calculator(tax_year_end=tax_year_end)
    with warnings.catch_warnings(record=True):
        with open(filename, 'rt') as istream:
            calculator.parse(istream)
        calculator.process()

    report = TextReport(io.StringIO())
    calculator.report(report)

    if tax_year_end is None:
        encode_json_result(calculator, json_filename)
        return

    assert set(calculator.yearly_acrued_income.keys()) == set(expected_result.keys())

    abs_tol = Decimal('0.02')

    provisional = False
    for tax_year, entries in calculator.yearly_acrued_income.items():
        expected_tyr = expected_result[tax_year]
        expected_entries = expected_tyr['entries']

        assert len(entries) == len(expected_entries)

        for (interest_date, date, gilt_state, description, income), expected_entry in zip(entries, expected_entries):
            assert interest_date == expected_entry['interest_date']
            assert date == expected_entry['transaction_date']
            assert gilt_state.name() == expected_entry['gilt']
            assert description == expected_entry['description'] or description + footnote_mark == expected_entry['description']
            if not expected_entry['description'].endswith(footnote_mark):
                provisional = True
                assert income == pytest.approx(expected_entry['income'], abs=abs_tol)

        total = sum(income for _, _, _, _, income in entries)
        if not provisional:
            assert total == pytest.approx(expected_tyr['total'], abs=abs_tol)


def test_main() -> None:
    filename = os.path.join(data_dir, 'accrued_income', 'example.csv')

    from accrued_income import __file__ as accrued_income_path

    subprocess.check_call(args=[
            sys.executable,
            accrued_income_path,
            filename
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
