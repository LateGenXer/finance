#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import pytest

import annuities


@pytest.mark.parametrize('kind', ('Real', 'Nominal'))
@pytest.mark.parametrize('gender', ('unisex', 'male', 'female'))
def test_annuity_rate(kind, gender):
    ar = annuities.annuity_rate(66, kind, gender)
    assert 0.0 < ar < 1.0
