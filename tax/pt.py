#
# Copyright (c) 2023-2025 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


# https://taxsummaries.pwc.com/portugal/individual/taxes-on-personal-income
income_tax_bands = [
   (   8059, 0.1300 ),
   (  12160, 0.1650 ),
   (  17233, 0.2200 ),
   (  22306, 0.2500 ),
   (  28400, 0.3200 ),
   (  41629, 0.3550 ),
   (  44987, 0.4350 ),
   (  80000, 0.4500 ),
   (  83696, 0.4500 + 0.025 ),
   ( 250000, 0.4800 + 0.025 ),
   (   None, 0.4800 + 0.050 ),
]


# https://taxsummaries.pwc.com/portugal/individual/income-determination
# XXX: gains are inflation adjusted
cgt_rate = 0.28
