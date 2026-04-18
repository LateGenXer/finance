#!/usr/bin/env python3
#
# SPDX-License-Identifier: Unlicense
#

#
# See also:
# - https://premiumbondsprizes.com/
# - https://www.moneysavingexpert.com/savings/premium-bonds-calculator/
#


from __future__ import annotations

import logging
import multiprocessing.dummy
import operator
import sys

from math import exp, factorial, lgamma, log

import numpy as np


logger = logging.getLogger('nsandi')


# Binomial PDF
# https://en.wikipedia.org/wiki/Binomial_distribution
def binomial(k:int, n:int, p:float) -> float:
    assert k <= n
    if n > 22:
        return exp(lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1) + log(p)*k + log(1 - p)*(n - k))
    else:
        return float(factorial(n)) / float(factorial(k) * factorial(n - k)) * p**k * (1 - p)**(n - k)


def combine(dist0:np.ndarray, dist1:np.ndarray) -> np.ndarray:
    # This is a form of convolution, but it's not easy to coerce numpy.convolve
    # to do exactly what we want.
    N, = dist0.shape
    dist2 = np.zeros(N)
    for i in range(N):
        dist2[i:] += dist0[i]*dist1[:N - i]
    return dist2


class Calculator:

    def __init__(self, odds:float, prizes:list[tuple[int, int]], desc:str):
        self.odds = odds
        self.prizes = prizes.copy()
        self.prizes.sort(key=operator.itemgetter(0))

        self.total_volume = 0
        for value, volume in prizes:
            self.total_volume += volume

        odds_per_bond = 25 * odds
        self.total_bonds = self.total_volume / odds_per_bond

        self.desc = desc

    # https://www.nsandi.com/get-to-know-us/monthly-prize-allocation
    @staticmethod
    def _prizes(odds:float, fund_rate:float, total_prizes:float) -> list[tuple[int, int]]:
        fund_rate /= 12.0

        total = total_prizes / fund_rate

        fund = total * fund_rate

        total_prizes = round(total * odds)

        prizes = []

        # High value band
        higher_value_band = fund * .10
        prizes += [
            ( 1000000, 2 )
        ]
        higher_value_band -= 2*1000000
        x = higher_value_band / (5*100000)
        prizes += [
            (  100000, round(    x ) ),
            (   50000, round(  2*x ) ),
            (   25000, round(  4*x ) ),
            (   10000, round( 10*x ) ),
            (    5000, round( 20*x ) ),
        ]

        # Mediuam value band
        medium_value_band = fund * .10
        x = medium_value_band / (1000 + 3*500)
        prizes += [
            (    1000, round(   x ) ),
            (     500, round( 3*x ) ),
        ]

        # Low value band
        low_value_band = fund * .80

        partial_prizes = sum([volume for _, volume in prizes])
        missing_prizes = total_prizes - partial_prizes

        # x: £100 and £50 volume
        # y: £25 volume

        # 2*x + y = missing_prizes
        # 150/25*x + 25/25*y = low_value_band/25

        x = round((low_value_band / 25 - missing_prizes) / (150/25 - 2))
        y = missing_prizes - 2 *x

        prizes += [
            (     100, x ),
            (      50, x ),
            (      25, y ),
        ]

        return prizes

    # Scrape prizes and odds from nsandi.com
    @classmethod
    def from_latest(cls) -> Calculator:
        # https://nsandi-corporate.com/news-research/news/nsi-reduces-prize-fund-rate-and-lengthens-odds-premium-bonds
        fund_rate = 3.3e-2
        odds = 1/23000
        total_prizes = 375515275
        prizes = cls._prizes(odds, fund_rate, total_prizes)
        desc = "April 2026 (estimate)"
        return cls(odds, prizes, desc)

    def mean(self) -> float:
        mean = 0.0
        for value, volume in self.prizes:
            p = volume / self.total_volume * self.odds * 12
            mean += value * p
        return mean

    def median(self, n:int) -> int:
        assert n > 0
        assert n <= 50000
        assert n % 25 == 0

        our_bonds = n // 25

        # Probability of winning exactly one prize
        assert our_bonds < self.total_bonds
        p = our_bonds / self.total_bonds

        # Truncated length of the Probability Mass Functions (PMF).
        # We ignore the right tail (ie, very large prizes) since it won't affect the median.
        N = 50000 // 25

        # Start with a PMF zero, that is, 100% chance of receiving £0
        pmf0 = np.zeros(N)
        pmf0[0] = 1.0

        for value, volume in self.prizes:
            assert value % 25 == 0

            # The PMF of all prizes of equal value is given by the Bernoulli distribuion
            pmf1 = np.zeros(N)
            for k in range(0, min(N // value, 12*volume) + 1):
                pmf1[k * value // 25] = binomial(k, 12*volume, p)

            # Ensure the truncated PMF captures the bulk of the probability mass
            assert pmf1.sum() >= .99

            # The PMF of the sum of the prize PMF can
            # https://en.wikipedia.org/wiki/Convolution_of_probability_distributions
            pmf0 = combine(pmf0, pmf1)

        # Obtain the median through the Cumulative Mass Function (CMF)
        cmf = np.cumsum(pmf0)
        median = int(np.searchsorted(cmf, 0.5, side='right'))
        median *= 25
        return median

    # Divide samples in this number of chunks for efficiency.
    chunk = 1024

    def sample(self, p:float) -> np.ndarray:
        prize = np.zeros([self.chunk], dtype=np.int64)
        for value, volume in self.prizes:
            k = np.random.binomial(12*volume, p, size=[self.chunk])
            prize += k*value
        return prize

    # Obtain the median through Monte Carlo simulation using multiple threads.
    # Essentially used to verify the correctness of the median() function above.
    def median_mc(self, n:int, N:int) -> int:
        assert n > 0
        assert n <= 50000
        assert n % 25 == 0

        our_bonds = n // 25

        assert our_bonds < self.total_bonds
        p = our_bonds / self.total_bonds

        pool = multiprocessing.dummy.Pool((multiprocessing.cpu_count() + 1) // 2)

        nchunks = (N + 1) // self.chunk

        samples = pool.map(self.sample, [p]*nchunks )

        median = np.median(samples)
        return median


def main() -> None:
    logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s %(message)s', level=logging.INFO)
    c = Calculator.from_latest()
    print(f'Mean:   {c.mean():.2%}')
    args = sys.argv[1:] if len(sys.argv) > 1 else ["50000"]
    for arg in args:
        n = int(arg)
        print(f'{n}:')
        m = c.median(n)
        print(f'  Median (accurate):  {m:4.0f} {m/n:.2%}')
        m = c.median_mc(n, 512*1024)
        print(f'  Median (MC):        {m:4.0f} {m/n:.2%}')


if __name__ == '__main__':
    main()
