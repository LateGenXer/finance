#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import io
import os.path
import subprocess
import sys
import warnings

import pytest

from glob import glob

from accrued_income import Calculator, TextReport


data_dir = os.path.join(os.path.dirname(__file__), 'data')


def collect_filenames():
    filenames = []
    for filename in glob(os.path.join(data_dir, 'accrued_income', '*.csv')):
        name, _ = os.path.splitext(os.path.basename(filename))
        filenames.append(pytest.param(filename, id=name))
    return filenames


@pytest.mark.parametrize("filename", collect_filenames())
def test_calculate(filename):
    calculator = Calculator()
    with warnings.catch_warnings(record=True):
        with open(filename, 'rt') as istream:
            calculator.parse(istream)
        calculator.process()
    report = TextReport(io.StringIO())
    calculator.report(report)


def test_main():
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
