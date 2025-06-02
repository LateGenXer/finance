#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import csv
import io
import subprocess
import sys
import types

import pytest

from data import lse


isin_tidm = {
    'GB0007980591': 'BP.',
    'GB00BBJNQY21': 'TR68',
    'LU1230136894': 'CSH2',
    'US0846707026': '0R37',
}

def test_is_tidm() -> None:
    for tidm in isin_tidm.values():
        assert lse.is_tidm(tidm)

    for isin in isin_tidm.keys():
        assert not lse.is_tidm(isin)

    assert not lse.is_tidm('X'*2)
    assert not lse.is_tidm(' '*4)
    assert not lse.is_tidm('X'*5)


def test_is_isin() -> None:
    for isin in isin_tidm.keys():
        assert lse.is_isin(isin)

    for tidm in isin_tidm.values():
        assert not lse.is_isin(tidm)

    assert not lse.is_isin('X' * 11)
    assert not lse.is_isin('X' * 12)
    assert not lse.is_isin('X' * 13)


@pytest.mark.parametrize('isin,tidm', isin_tidm.items())
def test_lookup_tidm(isin:str, tidm:str) -> None:
    assert lse.lookup_tidm(isin) == tidm


@pytest.mark.parametrize('tidm', isin_tidm.values())
def test_get_instrument_data(tidm:str) -> None:
    data = lse.get_instrument_data(tidm)
    assert isinstance(data['lastprice'], (float, int))
    assert isinstance(data['lastclose'], (float, int))


def test_get_latest_gilt_prices() -> None:
    dt, content = lse.get_latest_gilt_prices()
    for instrument in content:
        assert 'isin' in instrument
        assert 'tidm' in instrument
        assert isinstance(instrument['lastprice'], (float, int, types.NoneType))


def test_main() -> None:
    output = subprocess.check_output([sys.executable, '-m', 'data.lse'], text=True)
    found = False
    with io.StringIO(output) as stream:
        for entry in list(csv.DictReader(stream)):
            if entry['tidm'] == 'TR68' and entry['isin'] == 'GB00BBJNQY21':
                found = True
    assert found
