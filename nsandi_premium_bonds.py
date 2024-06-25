#!/usr/bin/env python3
#
# SPDX-License-Identifier: Unlicense
#

#
# See also:
# - https://premiumbondsprizes.com/
# - https://www.moneysavingexpert.com/savings/premium-bonds-calculator/
#


import sys
import random
import multiprocessing.dummy

import numpy as np

from math import *


# https://www.nsandi.com/products/premium-bonds
odds = 1/21000

# https://www.nsandi.com/get-to-know-us/monthly-prize-allocation
# Data from October 2023 draw
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
prizes.reverse()

total_volume = 0
for value, volume in prizes:
    total_volume += volume


def mean():
    mean = 0
    for value, volume in prizes:
        p = volume / total_volume * odds * 12
        mean += value * p
    return mean


# Binomial PDF
# https://en.wikipedia.org/wiki/Binomial_distribution
def binomial(k, n, p):
    assert k <= n
    if n > 22:
        return exp(lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1) + log(p)*k + log(1 - p)*(n - k))
    else:
        return float(factorial(n)) / float(factorial(k) * factorial(n - k)) * p**k * (1 - p)**(n - k)


odds_per_bond = 25 * odds
total_bonds = total_volume / odds_per_bond


def combine(dist0, dist1):
    # This is a form of convolution, but it's not easy to coerce numpy.convolve
    # to do exactly what we want.
    N, = dist0.shape
    dist2 = np.zeros(N)
    for i in range(N):
        dist2[i:] += dist0[i]*dist1[:N - i]
    return dist2


def median(n):
    assert n > 0
    assert n <= 50000
    assert n % 25 == 0

    our_bonds = n // 25

    # Probability of winning exactly one prize
    p = our_bonds / total_bonds

    # Truncated length of the Probability Mass Functions (PMF).
    # We ignore the right tail (ie, very large prizes) since it won't affect the median.
    N = 50000 // 25

    # Start with a PMF zero, that os, 100% change of receiving £0
    pmf0 = np.zeros(N)
    pmf0[0] = 1.0

    for value, volume in prizes:
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
    median = np.searchsorted(cmf, 0.5, side='right')
    median *= 25
    return median


# Divide samples in this number of chunks for efficiency.
chunk = 1024


def sample(p):
    prize = np.zeros([chunk], dtype=np.int64)
    for value, volume in prizes:
        k = np.random.binomial(12*volume, p, size=[chunk])
        prize += k*value
    return prize


# Obtain the median through Monte Carlo simulation using multiple threads.
# Essentially used to verify the correctness of the median() function above.
def median_mc(n, N):
    assert n > 0
    assert n <= 50000
    assert n % 25 == 0

    our_bonds = n // 25

    assert our_bonds < total_bonds
    p = our_bonds / total_bonds

    pool = multiprocessing.dummy.Pool((multiprocessing.cpu_count() + 1) // 2)

    nchunks = (N + 1) // chunk

    samples = pool.map(sample, [p]*nchunks )

    median = np.median(samples)
    return median


def main(args):
    print(f'Mean:   {mean():.2%}')
    for arg in args:
        n = int(arg)
        print(f'{n}:')
        m = median(n)
        print(f'  Median (accurate):  {m:4.0f} {m/n:.2%}')
        m = median_mc(n, 512*1024)
        print(f'  Median (MC):        {m:4.0f} {m/n:.2%}')


if __name__ == '__main__': # pragma: no cover
    main(sys.argv[1:])
