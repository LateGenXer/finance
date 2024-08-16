#
# SPDX-License-Identifier: Unlicense
#


import io
import os.path

from cgtcalculator2cgtcalc import translate


data_dir = os.path.join(os.path.dirname(__file__), 'data')


def test_translate():
    istream = open(os.path.join(data_dir, 'cgtcalculator2cgtcalc-input.tsv'), 'rt')
    ostream = io.StringIO()

    translate(istream, ostream)

    output = ostream.getvalue()
    expected_output = open(os.path.join(data_dir, 'cgtcalculator2cgtcalc-output.tsv'), 'rt').read()

    for line, expected_line in zip(output.split('\n'), expected_output.split('\n')):
        assert line == expected_line
