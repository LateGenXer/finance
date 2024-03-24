#
# Copyright (c) 2023-2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


# https://taxsummaries.pwc.com/japan/individual/taxes-on-personal-income
income_tax_bands = [
    (   1950000, 0.05 + 0.10 + 0.023),
    (   3300000, 0.10 + 0.10 + 0.023),
    (   6950000, 0.20 + 0.10 + 0.023),
    (   9000000, 0.23 + 0.10 + 0.023),
    (  18000000, 0.33 + 0.10 + 0.023),
    (  40000000, 0.40 + 0.10 + 0.023),
    (      None, 0.45 + 0.10 + 0.023),
]


cgt_rate = 0.20315


def income_tax(gross_income, factor=1.0):
    tax = 0
    lbound = 0
    for ubound, rate in income_tax_bands:
        delta = max(gross_income - lbound, 0)
        if ubound is not None:
            ubound *= factor
            delta = min(delta, ubound - lbound)
        tax += delta * rate
        lbound = ubound
    assert tax <= gross_income
    return tax
