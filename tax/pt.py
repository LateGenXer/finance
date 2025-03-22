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
#
# Capital gains of assets held more than 24 months can be inflation adjusted.  See:
# - Código do IRS, Artigo 50.º - Correção monetária
# - Código do IRS, Artigo 10.º - Mais-valias, alínea b), n.º 5, which explicitly refers investment funds
# - https://www.pwc.pt/pt/pwcinforfisco/flash/irc/irc-irs-coeficientes-desvalorizacao-moeda-2024.html
#
cgt_rate = 0.28
