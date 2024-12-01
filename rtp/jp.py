#
# Copyright (c) 2023-2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


# https://taxsummaries.pwc.com/japan/individual/taxes-on-personal-income
local_income_tax = 0.10
surtax = 0.021
income_tax_bands = [
    (   1950000, 0.05 + local_income_tax + surtax),
    (   3300000, 0.10 + local_income_tax + surtax),
    (   6950000, 0.20 + local_income_tax + surtax),
    (   9000000, 0.23 + local_income_tax + surtax),
    (  18000000, 0.33 + local_income_tax + surtax),
    (  40000000, 0.40 + local_income_tax + surtax),
    (      None, 0.45 + local_income_tax + surtax),
]


# https://taxsummaries.pwc.com/japan
cgt_rate = 0.20315
