#
# SPDX-License-Identifier: Unlicense
#


import subprocess

import pytest


from nsandi_premium_bonds import *


amounts = [50, 500, 5000, 50000]


def test_binomial():
    assert binomial(4, 6, 0.3) == pytest.approx(0.059535, abs=1e-6)


@pytest.mark.parametrize('n', amounts)
def test_median(n):
    N = 512*1024
    assert median(n) == pytest.approx(median_mc(n, N), abs=1e-4)


@pytest.mark.parametrize('n', amounts)
def test_main(n):
    from nsandi_premium_bonds import __file__ as script_path
    subprocess.check_call([sys.executable, script_path, str(n)])
