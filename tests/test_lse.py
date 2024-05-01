#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import csv
import datetime
import io
import os.path
import subprocess
import sys
import types

import pytest

import lse


@pytest.mark.parametrize('isin,tidm', [
    ('GB00BBJNQY21', 'TR68'),
    ('LU1230136894', 'CSH2'),
])
def test_lookup_tidm(isin, tidm):
    assert lse.lookup_tidm(isin) == tidm


@pytest.mark.parametrize('tidm', ['TR68'])
def test_get_instrument_data(tidm):
    data = lse.get_instrument_data(tidm)
    assert isinstance(data['lastprice'], (float, int))
    assert isinstance(data['lastclose'], (float, int))


def test_get_latest_gilt_prices():
    dt, content = lse.get_latest_gilt_prices()
    for instrument in content:
        assert 'isin' in instrument
        assert 'tidm' in instrument
        assert isinstance(instrument['lastprice'], (float, int, types.NoneType))


def test_main():
    output = subprocess.check_output([sys.executable, lse.__file__], text=True)
    found = False
    with io.StringIO(output) as stream:
        for entry in list(csv.DictReader(stream)):
            if entry['tidm'] == 'TR68' and entry['isin'] == 'GB00BBJNQY21':
                found = True
    assert found
