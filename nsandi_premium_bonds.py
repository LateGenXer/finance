#!/usr/bin/env python3
#
# SPDX-License-Identifier: Unlicense
#


import sys
import random
import multiprocessing

import numpy as np

from math import *


# https://www.nsandi.com/products/premium-bonds
odds = 1/24000

# https://www.nsandi.com/get-to-know-us/monthly-prize-allocation
# Data from May 2023 draw estimate
prizes = [
    ( 1000000, 	       2 ),
    (  100000, 	      62 ),
    (   50000, 	     125 ),
    (   25000, 	     250 ),
    (   10000, 	     622 ),
    (    5000, 	    1246 ),
    (    1000, 	   13259 ),
    (     500, 	   39777 ),
    (     100, 	 1410123 ),
    (      50, 	 1410123 ),
    (      25, 	 2147004 ),
]
prizes.reverse()

total_volume = 0
for value, volume in prizes:
    total_volume += volume

mean = 0
for value, volume in prizes:
    p = volume / total_volume * odds * 12
    mean += value * p


# Binomial PDF
# https://en.wikipedia.org/wiki/Binomial_distribution
def binomial(k, n, p):
    assert k <= n
    if n > 22:
        return exp(lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1) + log(p)*k + log(1 - p)*(n - k))
    else:
        return float(factorial(n)) / float(factorial(k) * factorial(n - k)) * p**k * (1 - p)**(n - k)


# Rough approximation.
def median_approx(n):
    assert n > 0
    assert n <= 50000
    assert n % 25 == 0
    median = 0
    for value, volume in prizes:
        p = volume / total_volume * odds * 12
        median += value * round(n * p)
    return median


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

    p = our_bonds / total_bonds

    N = 50000 // 25

    dist0 = np.zeros(N)
    dist0[0] = 1.0
    for value, volume in prizes:
        assert value % 25 == 0

        dist1 = np.zeros(N)
        for k in range(0, min(N // value, 12*volume) + 1):
            dist1[k * value // 25] = binomial(k, 12*volume, p)
        assert dist1.sum() >= .99

        dist0 = combine(dist0, dist1)

    cum = np.cumsum(dist0)
    median = np.searchsorted(cum, 0.5, side='right')
    median *= 25
    return median


def sample(p):
    prize = 0
    for value, volume in prizes:
        k = np.random.binomial(12*volume, p)
        prize += k*value
    return prize


def median_mc(n, N):
    assert n > 0
    assert n <= 50000
    assert n % 25 == 0

    our_bonds = n // 25

    assert our_bonds < total_bonds
    p = our_bonds / total_bonds

    pool = multiprocessing.Pool((multiprocessing.cpu_count() + 1) // 2)
    samples = pool.map(sample, [p]*N)

    median = np.median(samples)
    return median


print(f'Mean:   {mean:.2%}')
for arg in sys.argv[1:]:
    n = int(arg)
    print(f'{n}:')
    m = median_approx(n)
    print(f'  Median (approx):    {m:4.0f} {m/n:.2%}')
    m = median(n)
    print(f'  Median (accurate):  {m:4.0f} {m/n:.2%}')
    m = median_mc(n, 512*1024)
    print(f'  Median (MC):        {m:4.0f} {m/n:.2%}')
