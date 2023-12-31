#
# SPDX-License-Identifier: Unlicense
#


import pytest


from nsandi_premium_bonds import *


@pytest.mark.parametrize('n', [50, 500, 5000, 50000])
def test_median(n):
    N = 512*1024
    assert median(n) == pytest.approx(median_mc(n, N), abs=1e-4)
