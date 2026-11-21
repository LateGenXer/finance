#
# SPDX-License-Identifier: Unlicense
#


import io
import os.path
import sys

from cgtcalculator2cgtcalc import translate, main


data_dir = os.path.join(os.path.dirname(__file__), 'data')


def test_translate():
    istream = open(os.path.join(data_dir, 'cgtcalculator2cgtcalc-input.tsv'), 'rt')
    ostream = io.StringIO()

    translate(istream, ostream)

    output = ostream.getvalue()
    expected_output = open(os.path.join(data_dir, 'cgtcalculator2cgtcalc-output.tsv'), 'rt').read()

    for line, expected_line in zip(output.split('\n'), expected_output.split('\n')):
        assert line == expected_line


def test_translate_comments() -> None:
    istream = io.StringIO('# comment\nB\t01/01/2020\tXYZ\t10\t1.0\t0.0\t0.0\n')
    ostream = io.StringIO()
    translate(istream, ostream)
    assert ostream.getvalue() == 'BUY\t01/01/2020\tXYZ\t10\t1.0\t0.0\n'


def test_main(monkeypatch, capsys) -> None:
    filename = os.path.join(data_dir, 'cgtcalculator2cgtcalc-input.tsv')
    monkeypatch.setattr(sys, 'argv', ['cgtcalculator2cgtcalc.py', filename])
    main()
    expected_output = open(os.path.join(data_dir, 'cgtcalculator2cgtcalc-output.tsv'), 'rt').read()
    assert capsys.readouterr().out == expected_output
