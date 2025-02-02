#!/usr/bin/env python3
#
# SPDX-License-Identifier: Unlicense
#

#
# See also:
# - https://premiumbondsprizes.com/
# - https://www.moneysavingexpert.com/savings/premium-bonds-calculator/
#


import logging
import multiprocessing.dummy
import operator
import re
import sys

from math import exp, factorial, lgamma, log

import numpy as np
import requests
import bs4


logger = logging.getLogger('nsandi')


# Binomial PDF
# https://en.wikipedia.org/wiki/Binomial_distribution
def binomial(k, n, p):
    assert k <= n
    if n > 22:
        return exp(lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1) + log(p)*k + log(1 - p)*(n - k))
    else:
        return float(factorial(n)) / float(factorial(k) * factorial(n - k)) * p**k * (1 - p)**(n - k)


def combine(dist0, dist1):
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

    # Scrape prizes and odds from nsandi.com
    @classmethod
    def from_latest(cls):
        # https://nsandi-corporate.com/news-research/news/new-rates-premium-bonds-direct-saver-and-income-bonds
        odds = 1/22000
        prizes = [
            ( 1000000,       2 ),
            (  100000,      82 ),
            (   50000,     166 ),
            (   25000,     329 ),
            (   10000,     823 ),
            (    5000,    1648 ),
            (    1000,   17277 ),
            (     500,   51831 ),
            (     100, 2001028 ),
            (      50, 2001028 ),
            (      25, 1815854 ),
        ]
        desc = "January 2025 (estimate)"
        return cls(odds, prizes, desc)

        session = requests.Session()

        r = session.get('https://www.nsandi.com/get-to-know-us/monthly-prize-allocation')
        assert r.ok

        soup = bs4.BeautifulSoup(r.text, features='html.parser')

        table = soup.find('table')
        _ = table.find('thead')
        table_row = table.find('tr')
        cells = table_row.find_all('th')
        head = [cell.text for cell in cells]
        _, _, _, desc = head

        logger.info(f'using prizes for {desc}')

        table_body = table.find('tbody')

        prizes = []
        for table_row in table_body.find_all('tr'):
            cells = table_row.find_all('td')
            fields = [cell.text for cell in cells]

            band, value, _, draw = fields

            if value.startswith('£'):
                value = value.replace('£', '')
                value = value.replace(' million', '000000')
                value = value.replace(',', '')
                draw = draw.replace(',', '')

                prizes.append((int(value), int(draw)))

        assert(len(prizes) == 11)

        r = session.get('https://www.nsandi.com/products/premium-bonds')
        assert r.ok
        soup = bs4.BeautifulSoup(r.text, features='html.parser')
        dl = soup.find('dl', class_='product-definition')
        odds_re = re.compile("([0-9,]+) to 1 for every £1 Bond")
        text = dl.find(string=lambda text: not isinstance(text, bs4.Comment) and odds_re.search(text))
        mo = odds_re.search(text)
        inv_odds = int(mo.group(1).replace(',', ''))
        odds = 1/inv_odds

        return cls(odds, prizes, desc)

    def mean(self):
        mean = 0.0
        for value, volume in self.prizes:
            p = volume / self.total_volume * self.odds * 12
            mean += value * p
        return mean

    def median(self, n):
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
        median = np.searchsorted(cmf, 0.5, side='right')
        median *= 25
        return median

    # Divide samples in this number of chunks for efficiency.
    chunk = 1024

    def sample(self, p):
        prize = np.zeros([self.chunk], dtype=np.int64)
        for value, volume in self.prizes:
            k = np.random.binomial(12*volume, p, size=[self.chunk])
            prize += k*value
        return prize

    # Obtain the median through Monte Carlo simulation using multiple threads.
    # Essentially used to verify the correctness of the median() function above.
    def median_mc(self, n, N):
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


def main():
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
