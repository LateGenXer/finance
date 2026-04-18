
# SPDX-License-Identifier: Unlicense
#


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


# Test cases from tests.txt
_prizes_cases = [
    # https://nsandi-corporate.com/news-research/news/nsi-reduces-prize-fund-rate-and-lengthens-odds-premium-bonds
    dict(
        fund_rate=3.3e-2, reciprocal_odds=23000,
        prizes=[
            (      25, 2806003 ),
            (      50, 1537125 ),
            (     100, 1537125 ),
            (     500,   45105 ),
            (    1000,   15035 ),
            (    5000,    1424 ),
            (   10000,     712 ),
            (   25000,     284 ),
            (   50000,     143 ),
            (  100000,      71 ),
            ( 1000000,       2 ),
        ],
    ),
    # https://nsandi-corporate.com/news-research/news/new-prize-fund-rate-august-premium-bonds-draw
    dict(
        fund_rate=3.6e-2, reciprocal_odds=22000,
        prizes=[
            (      25, 2569568 ),
            (      50, 1687680 ),
            (     100, 1687680 ),
            (     500,   47607 ),
            (    1000,   15869 ),
            (    5000,    1507 ),
            (   10000,     754 ),
            (   25000,     302 ),
            (   50000,     151 ),
            (  100000,      75 ),
            ( 1000000,       2 ),
        ],
    ),
    # https://nsandi-corporate.com/news-research/news/new-interest-rates-selected-nsi-accounts
    dict(
        fund_rate=3.8e-2, reciprocal_odds=22000,
        prizes=[
            (      25, 2170903 ),
            (      50, 1830825 ),
            (     100, 1830825 ),
            (     500,   49335 ),
            (    1000,   16445 ),
            (    5000,    1565 ),
            (   10000,     781 ),
            (   25000,     313 ),
            (   50000,     157 ),
            (  100000,      78 ),
            ( 1000000,       2 ),
        ],
    ),
    # https://nsandi-corporate.com/news-research/news/nsi-announces-rate-changes-some-variable-and-fixed-term-products
    dict(
        fund_rate=4.15e-2, reciprocal_odds=22000,
        prizes=[
            (      25, 1509458 ),
            (      50, 2072099 ),
            (     100, 2072099 ),
            (     500,   52278 ),
            (    1000,   17426 ),
            (    5000,    1664 ),
            (   10000,     830 ),
            (   25000,     332 ),
            (   50000,     167 ),
            (  100000,      83 ),
            ( 1000000,       2 ),
        ],
    ),
]


@pytest.mark.parametrize('case', _prizes_cases)
def test_prizes(case: dict) -> None:
    total_prizes = sum(value * volume for value, volume in case['prizes'])
    result = Calculator._prizes(1/case['reciprocal_odds'], case['fund_rate'], total_prizes)
    result_by_value = {value: volume for value, volume in result}
    for value, expected_volume in case['prizes']:
        assert result_by_value[value] == pytest.approx(expected_volume, abs=1, rel=1e-4)


def test_main() -> None:
    from nsandi_premium_bonds import __file__ as script_path
    subprocess.check_call([sys.executable, script_path] + [str(amount) for amount in amounts])
