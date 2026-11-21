#
# Copyright (c) 2026 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


from data import lse, tidm


def test_load() -> None:
    tidms = tidm.load()
    assert tidms
    for isin, ticker in tidms.items():
        assert lse.is_isin(isin)
        assert lse.is_tidm(ticker)
    assert tidms['GB00BBJNQY21'] == 'TR68'
