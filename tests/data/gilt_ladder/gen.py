#!/usr/bin/env python3
#
# Copyright (c) 2026 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


"""Generate bond ladder test cases by Latin sampling.

Each parameter takes N values, each used exactly once across the N cases, with
the columns shuffled independently.  Only the parameters are written; run
`pytest tests/test_gilts.py -k bond_ladder` afterwards to fill in the expected
results.

Usage: python tests/data/gilt_ladder/gen.py [SEED]
"""


import datetime
import json
import os
import random
import sys

from typing import Callable

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from ukcalendar import shift_month, shift_year


N = 8

# Must match the prices date used by the test fixtures
today = datetime.date(2023, 12, 1)


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    rng = random.Random(seed)

    cols: dict[str, list] = {
        'marginal_income_tax': [0.0, 0.0, 0.20, 0.20, 0.40, 0.40, 0.45, 0.45],
        'interest_rate': [0.0, 0.005, 0.01, 0.015, 0.02, 0.03, 0.04, 0.05],
        'lag': [0, 0, 6, 12, 18, 24, 30, 36],
        'index_linked': [False] * 4 + [True] * 4,
        'shift': ['year'] * 4 + ['month'] * 4,
    }
    for values in cols.values():
        assert len(values) == N
        rng.shuffle(values)

    outdir = os.path.dirname(os.path.abspath(__file__))
    for i in range(N):
        shift = cols['shift'][i]
        shift_fn: Callable[[datetime.date, int], datetime.date]
        if shift == 'year':
            count, amount, shift_fn = 50, 10000, shift_year
        else:
            count, amount, shift_fn = 120, 1000, shift_month
        params = {
            'today': today.isoformat(),
            'count': count,
            'amount': amount,
            'shift': shift,
            'start': shift_fn(today, 1).isoformat(),
            'index_linked': cols['index_linked'][i],
            'marginal_income_tax': cols['marginal_income_tax'][i],
            'interest_rate': cols['interest_rate'][i],
            'lag': cols['lag'][i],
        }
        name = '{}ly-{}-tax{:g}-int{:g}-lag{}'.format(
            shift,
            'il' if params['index_linked'] else 'conv',
            params['marginal_income_tax'] * 100,
            params['interest_rate'] * 1000,
            params['lag'],
        )
        path = os.path.join(outdir, name + '.json')
        if os.path.exists(path):
            print(f'{name}: already exists, skipping', file=sys.stderr)
            continue
        with open(path, 'wt') as ostream:
            json.dump({'params': params}, ostream, indent=2)
            ostream.write('\n')
        print(name)


if __name__ == '__main__':
    main()
