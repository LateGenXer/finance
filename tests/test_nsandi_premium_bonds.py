#
# SPDX-License-Identifier: Unlicense
#


import datetime
import subprocess
import sys

import pytest


from nsandi_premium_bonds import binomial, Calculator


# https://www.nsandi.com/products/premium-bonds
# https://www.nsandi.com/get-to-know-us/monthly-prize-allocation
odds = 1/21000
prizes = [
    ( 1000000, 	       2 ),
    (  100000, 	      90 ),
    (   50000, 	     181 ),
    (   25000, 	     360 ),
    (   10000, 	     902 ),
    (    5000, 	    1803 ),
    (    1000, 	   18834 ),
    (     500, 	   56502 ),
    (     100, 	 2339946 ),
    (      50, 	 2339946 ),
    (      25, 	 1027651 ),
]
desc = "Data from October 2023 draw"


amounts = [25, 50, 500, 5000, 50000]


def test_binomial() -> None:
    assert binomial(4, 6, 0.3) == pytest.approx(0.059535, abs=1e-6)


@pytest.mark.parametrize('n', amounts)
def test_median(n:int) -> None:
    N = 512*1024
    c = Calculator(odds, prizes, desc)
    assert c.median(n) == pytest.approx(c.median_mc(n, N), abs=1e-4)


def test_main() -> None:
    from nsandi_premium_bonds import __file__ as script_path
    subprocess.check_call([sys.executable, script_path] + [str(amount) for amount in amounts])
