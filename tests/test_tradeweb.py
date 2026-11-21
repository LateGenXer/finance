#
# Copyright (c) 2026 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import csv
import io
import os.path
import sys

from data import tradeweb


data_dir = os.path.join(os.path.dirname(__file__), 'data')


def test_main(monkeypatch, capsys) -> None:
    filename = os.path.join(data_dir, 'Tradeweb_FTSE_ClosePrices_20231201.csv')
    monkeypatch.setattr(sys, 'argv', ['tradeweb.py', filename])
    tradeweb.main()
    rows = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    assert rows
    for row in rows:
        assert row['date'] == '2023-12-01'
        assert float(row['price']) > 0.0
    assert len(rows) == len(list(tradeweb.parse(filename)))
