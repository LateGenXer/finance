#
# Copyright (c) 2023-2026 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


# https://taxsummaries.pwc.com/portugal/individual/taxes-on-personal-income
income_tax_bands = [
   (   8342, 0.1250 ),
   (  12587, 0.1570 ),
   (  17838, 0.2120 ),
   (  23089, 0.2410 ),
   (  29397, 0.3110 ),
   (  43090, 0.3490 ),
   (  46566, 0.4310 ),
   (  80000, 0.4460 ),
   (  86634, 0.4460 + 0.025 ),
   ( 250000, 0.4800 + 0.025 ),
   (   None, 0.4800 + 0.050 ),
]


# https://taxsummaries.pwc.com/portugal/individual/income-determination
#
# Capital gains of assets held more than 24 months can be inflation adjusted.  See:
# - Código do IRS, Artigo 50.º - Correção monetária
# - Código do IRS, Artigo 10.º - Mais-valias, alínea b), n.º 5, which explicitly refers investment funds
# - https://www.pwc.pt/pt/pwcinforfisco/flash/outros/irc-irs-coeficientes-desvalorizacao-moeda-2025.html
#
cgt_rate = 0.28
