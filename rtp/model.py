#!/usr/bin/env python3
#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import os
import math
import sys

from dataclasses import dataclass, field
from typing import Any

if int(os.environ.get('PULP', '0')) != 0:
    import pulp as lp
else:
    import lp

import hmrc

import uk as UK
import pt as PT
import jp as JP

from uk import *


verbosity = 0

uid = 0


@dataclass
class LPState:
    sipp_uf_1: Any
    sipp_uf_2: Any
    sipp_df_1: Any
    sipp_df_2: Any
    contrib_1: Any
    contrib_2: Any
    tfc_1: Any
    tfc_2: Any
    lta_1: Any
    lta_2: Any
    lac_1: Any
    lac_2: Any
    isa: Any
    gia: Any
    cg: Any
    drawdown_1: Any
    drawdown_2: Any
    drawdown_isa: Any
    drawdown_gia: Any
    income_state_1: Any
    income_state_2: Any
    income_gross_1: Any
    income_gross_2: Any


@dataclass
class ResState:
    year: int
    income_state: float
    sipp_uf_1: float
    sipp_uf_2: float
    sipp_df_1: float
    sipp_df_2: float
    sipp_delta_1: float
    sipp_delta_2: float
    contrib_1: float
    contrib_2: float
    tfc_1: float
    tfc_2: float
    lta_ratio_1: float
    lta_ratio_2: float
    isa: float
    isa_delta: float
    gia: float
    gia_delta: float
    income_gross_1: float
    income_gross_2: float
    cg: float
    income_net: float
    income_surplus: float
    income_tax_1: float
    income_tax_2: float
    income_tax_rate_1: float
    income_tax_rate_2: float
    cgt: float
    cgt_rate: float
    lac: float


@dataclass
class Result:
    retirement_income_net: float = 0
    net_worth_start: float = 0
    net_worth_end: float = 0
    total_tax: float = 0
    data: list[ResState] = field(default_factory=list)
    ls_sipp_1: float = 0
    ls_sipp_2: float = 0
    ls_isa: float = 0
    ls_gia: float = 0


def income_tax_lp(prob, gross_income, income_tax_bands, factor=1.0):
    global uid
    total = 0
    tax = 0
    lbound = 0
    for ubound, rate in income_tax_bands:
        if ubound is None:
            ub = None
        else:
            ubound *= factor
            ub = ubound - lbound
        income_tax_band = lp.LpVariable(f'net_{uid}_{int(rate*1000)}', 0, ub)
        uid += 1
        total += income_tax_band
        tax += income_tax_band * rate
        lbound = ubound
    prob += total == gross_income
    return tax


uk_income_tax_bands = [
    (income_tax_threshold_20,  0.00),
    (income_tax_threshold_40,  0.20),
    (               pa_limit,  0.40),
    (                   None,  0.60), # 0.40 + 0.5*0.40
    # FIXME: we can't model the 45% tax rate, as it's no longer convex
]


def uk_income_tax_lp(prob, gross_income):
    # Although the following condition is necessary for accurate tax
    # modeling, but it would effectively lead to the maximization of the
    # marginal 60% income tax band.
    #prob += gross_income <= pa_limit + 2*income_tax_threshold_20
    return income_tax_lp(prob, gross_income, uk_income_tax_bands)


def uk_cgt_lp(prob, cg, cgt_rate, cgt_allowance):
    global uid
    cg_00 = lp.LpVariable(f'cgt_{uid}_00', 0, cgt_allowance)
    cg_xx = lp.LpVariable(f'cgt_{uid}_xx', 0)
    uid += 1
    prob += cg_00 + cg_xx == cg
    tax = cg_xx * cgt_rate
    return tax


def pt_income_tax_lp(prob, gross_income, factor=1.0):
    return income_tax_lp(prob, gross_income, PT.income_tax_bands, factor)


def normalize(x, ndigits=None):
    # https://bugs.python.org/issue45995
    return round(x, ndigits) + 0.0


def aa_lbound(marginal_income_tax):
    return {
        0.00: UK.uiaa,
        0.20: income_tax_threshold_20,
        0.40: min(income_tax_threshold_40, UK.aa),
        0.45: UK.aa_taper,
    }[marginal_income_tax]


# https://www.investopedia.com/terms/i/inflation_adjusted_return.asp
def inflation_ajusted_return(return_rate, inflation_rate):
    return (1.0 + return_rate) / (1.0 + inflation_rate) - 1.0


class DCP:
    """Defined Contribution Pension."""

    def __init__(self, prob, uf, growth_rate_real, inflation_rate, lta, lacs, nmpa):
        self.prob = prob

        self.uf = uf
        self.df = 0
        self.df_cost = 0

        self.growth_rate_real = growth_rate_real
        self.inflation_rate = inflation_rate

        self.lta = lta
        self.lacs = lacs

        self.nmpa = nmpa

    def contrib(self, contrib):
        self.uf += contrib

    def drawdown(self, drawdown, age):
        if self.lacs:
            # Benefit Crystallisation Event 5
            # https://www.gov.uk/hmrc-internal-manuals/pensions-tax-manual/ptm088650
            if age == 75:
                lac = self.bce_5a_5b_lp()
            else:
                lac = 0

            # Flexible-Access Drawdown
            if age >= self.nmpa:
                tfc, lac_bce1 = self.bce_1_6_lp(age)
                lac += lac_bce1
            else:
                tfc = 0
        else:
            # Flexible-Access Drawdown
            if age >= self.nmpa:
                tfc = self.tfc_lp(age)
            else:
                tfc = 0
            lac = 0

        self.df -= drawdown
        self.prob += self.df >= 0

        self.uf *= 1.0 + self.growth_rate_real

        self.df_cost *= 1.0 / (1.0 + self.inflation_rate)

        self.df *= 1.0 + self.growth_rate_real

        return tfc, lac

    def bce_lp(self, lta):
        global uid
        crystalized_lta = lp.LpVariable(f'crystalized_lta_{uid}', 0)
        crystalized_lae = lp.LpVariable(f'crystalized_lae_{uid}', 0)
        uid += 1
        lta -= crystalized_lta
        self.prob += lta >= 0
        return lta, crystalized_lta, crystalized_lae

    def bce_lac_lp(self, lta, crystalized):
        lta, crystalized_lta, crystalized_lae = self.bce_lp(lta)
        self.prob += crystalized_lta + crystalized_lae == crystalized
        lac = 0.25 * crystalized_lae
        return lta, lac

    # Benefit Crystallisation Event 5A and 5B
    # https://www.gov.uk/hmrc-internal-manuals/pensions-tax-manual/ptm088650
    def bce_5a_5b_lp(self):
        global uid

        # BCE 5A
        # https://moneyengineer.co.uk/13-anticipating-pension-growth-and-bce-5a/
        df_loss = lp.LpVariable(f'df_loss_{uid}', 0)
        df_gain = lp.LpVariable(f'df_gain_{uid}', 0)
        uid += 1
        self.prob += self.df_cost - df_loss + df_gain == self.df
        self.lta, lac_bce_5a = self.bce_lac_lp(self.lta, df_gain)
        self.df -= lac_bce_5a

        # BCE 5B
        # Funds aren't actually crystallized -- just tested and charged -- so LTA
        # is not updated.
        _, lac_bce_5b = self.bce_lac_lp(self.lta, self.uf)
        self.uf -= lac_bce_5b

        lac = lac_bce_5a + lac_bce_5b

        return lac

    # Benefit Crystallisation Event 1 (DD) and 6 (TFC)
    # https://www.gov.uk/hmrc-internal-manuals/pensions-tax-manual/ptm062701
    def bce_1_6_lp(self, age):
        lac_bce1 = 0
        self.lta, crystalized_lta, crystalized_lae = self.bce_lp(self.lta)
        crystalized = crystalized_lta + crystalized_lae
        self.uf -= crystalized
        self.prob += self.uf >= 0
        tfc = crystalized_lta * 0.25
        dd = crystalized - tfc - lac_bce1
        if age < 75:
            lac_bce1 = crystalized_lae * 0.25
            dd -= lac_bce1
        self.df += dd
        self.df_cost += dd
        return tfc, lac_bce1

    def tfc_lp(self, age):
        global uid
        crystalized_tfc = lp.LpVariable(f'crystalized_tfc_{uid}', 0)
        crystalized_inc = lp.LpVariable(f'crystalized_inc_{uid}', 0)
        uid += 1
        self.prob += 3*crystalized_tfc <= crystalized_inc
        self.lta -= crystalized_tfc*4
        self.prob += self.lta >= 0
        self.uf -= crystalized_tfc + crystalized_inc
        self.prob += self.uf >= 0
        self.df += crystalized_inc
        tfc = crystalized_tfc
        return tfc


class GIA:

    def __init__(self, prob, balance, growth_rate, inflation_rate):
        self.prob = prob

        self.assets = [balance]

        self.growth_rate = growth_rate
        self.inflation_rate = inflation_rate
        self.growth_rate_real = inflation_ajusted_return(self.growth_rate, self.inflation_rate)

    def flow(self):
        global uid

        total = 0
        gains = 0

        purchase = lp.LpVariable(f'gia_purchase_{uid}', 0)
        self.assets.insert(0, purchase)

        for yr in range(1, len(self.assets)):
            proceeds = lp.LpVariable(f'gia_proceeds_{uid}_{yr}', 0)
            self.assets[yr] -= proceeds
            self.prob += self.assets[yr] >= 0
            total += proceeds
            gains += proceeds * (1.0 - (1.0 + self.growth_rate) ** -yr)

        for yr in range(0, len(self.assets)):
            self.assets[yr] *= (1.0 + self.growth_rate_real) * (1.0 - eps)

        uid += 1

        return total - purchase, gains


    def value(self):
        total = 0
        for balance in self.assets:
            total += balance
        return total


# Introduce a tiny bias towards SIPPs uncrystalized funds and against
# GIAs to stabilize results, and prevent redundant money flows that
# arise when the optimal solution is not unique
eps = 2**-14


cgt_rate_map = {
    0.00: cgt_rates[0],
    0.20: cgt_rates[0],
    0.40: cgt_rates[1],
    0.45: cgt_rates[1],
}

def model(
        joint,
        dob_1,
        dob_2,
        present_year,
        retirement_year,
        inflation_rate,
        retirement_income_net,
        country,
        sipp_1,
        sipp_2,
        sipp_growth_rate_1,
        sipp_growth_rate_2,
        sipp_contrib_1,
        sipp_contrib_2,
        sipp_extra_contrib,
        isa,
        isa_growth_rate,
        gia,
        gia_growth_rate,
        misc_contrib,
        marginal_income_tax_1,
        marginal_income_tax_2,
        state_pension_years_1,
        state_pension_years_2,
        lacs,
        lump_sum,
        aa_1,
        aa_2,
        marriage_allowance,
    ):

    end_age = 100
    if joint:
        N = 2
        end_year = max(dob_1, dob_2) + end_age
    else:
        N = 1
        dob_2 = sys.maxsize
        sipp_2 = 0
        sipp_growth_rate_2 = 0
        sipp_contrib_2 = 0
        marginal_income_tax_2 = 0
        state_pension_years_2 = 0
        end_year = dob_1 + end_age
    #end_year = retirement_year + 3

    assert N in (1, 2)
    income_ratio_1 = float(1    ) / float(N)
    income_ratio_2 = float(N - 1) / float(N)
    assert income_ratio_1 + income_ratio_2 == 1.0

    result = Result()

    result.net_worth_start = normalize(sipp_1 + sipp_2 + isa + gia, 2)

    state_pension_1 = UK.state_pension_full * state_pension_years_1 / 35
    state_pension_2 = UK.state_pension_full * state_pension_years_2 / 35

    lta = UK.lta

    sipp_growth_rate_real_1 = inflation_ajusted_return(sipp_growth_rate_1, inflation_rate)
    sipp_growth_rate_real_2 = inflation_ajusted_return(sipp_growth_rate_2, inflation_rate)
    isa_growth_rate_real    = inflation_ajusted_return(isa_growth_rate,    inflation_rate)

    assert sipp_contrib_1 <= UK.aa
    assert sipp_contrib_2 <= UK.aa

    lta_1 = lta
    lta_2 = lta

    if country == 'PT':
        gbpeur = hmrc.exchange_rate('EUR')
    if country == 'JP':
        gbpjpy = hmrc.exchange_rate('JPY')

    prob = lp.LpProblem("Retirement")

    max_income = retirement_income_net == 0
    if max_income:
        retirement_income_net = lp.LpVariable("income", 0)

    # XXX: Lump sum analysis
    if lump_sum:
        ls_sipp_1 = lp.LpVariable("ls_sipp_1", 0)
        ls_sipp_2 = lp.LpVariable("ls_sipp_2", 0, None if joint else 0)
        ls_isa    = lp.LpVariable("ls_isa", 0, N*isa_allowance)
        ls_gia    = lp.LpVariable("ls_gia", 0)
        prob += ls_sipp_1 + ls_sipp_2 + ls_isa + ls_gia == lump_sum
        ls_sipp_gross_1 = ls_sipp_1 * (1.0 / (1.0 - max(marginal_income_tax_1, 0.20)))
        ls_sipp_gross_2 = ls_sipp_2 * (1.0 / (1.0 - max(marginal_income_tax_2, 0.20)))
        prob += sipp_contrib_1 + ls_sipp_gross_1 <= aa_1
        prob += sipp_contrib_2 + ls_sipp_gross_2 <= aa_2
        sipp_1 += ls_sipp_gross_1
        sipp_2 += ls_sipp_gross_2
        isa    += ls_isa
        gia    += ls_gia * (1 - eps)

    nmpa_1 = nmpa(dob_1)
    nmpa_2 = nmpa(dob_2)

    sipp_1 = DCP(prob=prob, uf=sipp_1, growth_rate_real = sipp_growth_rate_real_1, inflation_rate=inflation_rate, lta=lta, lacs=lacs, nmpa=nmpa_1)
    sipp_2 = DCP(prob=prob, uf=sipp_2, growth_rate_real = sipp_growth_rate_real_2, inflation_rate=inflation_rate, lta=lta, lacs=lacs, nmpa=nmpa_2)

    gia = GIA(prob=prob, balance=gia, growth_rate=gia_growth_rate, inflation_rate=inflation_rate)

    states = {}

    # XXX: SIPP contributions
    # https://www.gov.uk/government/publications/rates-and-allowances-pension-schemes/pension-schemes-rates#member-contributions
    # Limit post drawdown contributions to %30 over standard contributions to follow TFC recycling rule
    if sipp_extra_contrib:
        # Pension income is not classed as earned income, therefore one's limited to the 3600 limit
        sipp_contrib_limit = UK.uiaa
        sipp_contrib_limit_1 = min(sipp_contrib_1 * 1.30, sipp_contrib_limit, mpaa)
        sipp_contrib_limit_2 = min(sipp_contrib_2 * 1.30, sipp_contrib_limit, mpaa)

    for yr in range(present_year, end_year):
        retirement = yr >= retirement_year
        uk_yr = not retirement or country == 'UK'

        if yr == retirement_year and country != 'UK':
            gia.assets[0] += isa
            isa = 0

        age_1 = yr - dob_1
        age_2 = yr - dob_2

        # SIPP contributions
        if not retirement:
            # Regular contributions from earned income
            contrib_1 = sipp_contrib_1
            contrib_2 = sipp_contrib_2
        else:
            # Extra contributions from non-earned income.
            # XXX: FAD income recycling is OK, but PCLS recycling is not
            # https://www.gov.uk/hmrc-internal-manuals/pensions-tax-manual/ptm133800
            # https://techzone.abrdn.com/public/pensions/tech-guide-recycle-tax-free-cash
            contrib_1 = 0
            contrib_2 = 0
            if sipp_extra_contrib: #XXX
                if country == 'UK' or yr < retirement_year + 5:
                    if age_1 < 75:
                        contrib_1 = lp.LpVariable(f'contrib_1@{yr}', 0, sipp_contrib_limit_1)
                    if age_2 < 75 and joint:
                        contrib_2 = lp.LpVariable(f'contrib_2@{yr}', 0, sipp_contrib_limit_2)

        sipp_1.contrib(contrib_1)
        sipp_2.contrib(contrib_2)

        # Don't drawdown pension pre-retirement if there's a chance of violating MPAA
        drawdown_1 = lp.LpVariable(f'dd_1@{yr}', 0) if age_1 >= nmpa_1 and (retirement or sipp_contrib_1 <= mpaa) else 0
        drawdown_2 = lp.LpVariable(f'dd_2@{yr}', 0) if age_2 >= nmpa_2 and (retirement or sipp_contrib_2 <= mpaa) else 0

        tfc_1, lac_1 = sipp_1.drawdown(drawdown_1, age=age_1)
        tfc_2, lac_2 = sipp_2.drawdown(drawdown_2, age=age_2)

        if uk_yr:
            isa_allowance_yr = isa_allowance*N
            drawdown_isa = lp.LpVariable(f'dd_isa@{yr}', -isa_allowance_yr)  # Bed & ISA
            isa       -= drawdown_isa
            prob += isa >= 0
            isa *= 1.0 + isa_growth_rate_real
        else:
            drawdown_isa = 0

        drawdown_gia, cg = gia.flow()

        sipp_1.uf *= 1.0 + eps
        sipp_2.uf *= 1.0 + eps

        # State pension
        spa_1 = state_pension_age(dob_1)
        spa_2 = state_pension_age(dob_2)
        income_state_1 = state_pension_1 if age_1 >= spa_1 else 0
        income_state_2 = state_pension_2 if age_2 >= spa_2 else 0
        if country not in ('UK', 'PT'):
            # https://www.gov.uk/government/publications/state-pensions-annual-increases-if-you-live-abroad/countries-where-we-pay-an-annual-increase-in-the-state-pension
            income_state_1 *= (1.0/(1.0 + inflation_rate)) ** max(age_1 - spa_1, 0)
            income_state_2 *= (1.0/(1.0 + inflation_rate)) ** max(age_2 - spa_2, 0)

        # Income and Capital Gain Taxes modelling
        income_gross_1 = income_state_1 + drawdown_1
        income_gross_2 = income_state_2 + drawdown_2

        if uk_yr:
            # UK
            if yr < retirement_year:
                cgt_rate = min(cgt_rate_map[marginal_income_tax_1], cgt_rate_map[marginal_income_tax_2])
                tax_1 = income_gross_1 * marginal_income_tax_1
                tax_2 = income_gross_2 * marginal_income_tax_2
            elif marriage_allowance and income_state_2 <= UK.income_tax_threshold_20:
                prob += income_gross_1 <= UK.income_tax_threshold_40
                prob += income_gross_2 <= UK.income_tax_threshold_20
                tax_1 = income_tax_lp(prob, income_gross_1, [(income_tax_threshold_20 + UK.marriage_allowance, 0.00), (None, 0.20)])
                tax_2 = income_tax_lp(prob, income_gross_2, [(income_tax_threshold_20 - UK.marriage_allowance, 0.00), (None, 0.20)])
                cgt_rate = cgt_rates[0] # Basic rate
            else:
                cgt_rate = cgt_rates[1] # Higher rate
                tax_1 = uk_income_tax_lp(prob, income_gross_1)
                tax_2 = uk_income_tax_lp(prob, income_gross_2)
            cgt = uk_cgt_lp(prob, cg, cgt_rate, N*cgt_allowance)
        elif country == 'PT':
            income_gross = (income_gross_1 + tfc_1 +
                            income_gross_2 + tfc_2)

            tax = pt_income_tax_lp(prob, income_gross, factor=N/gbpeur)
            cgt = cg * PT.cgt_rate

            income_gross_1 = income_gross * income_ratio_1
            income_gross_2 = income_gross * income_ratio_2
            tax_1 = tax * income_ratio_1
            tax_2 = tax * income_ratio_2
        elif country == 'JP':
            income_gross_1 = income_gross_1 + tfc_1
            income_gross_2 = income_gross_2 + tfc_2

            tax_1 = income_tax_lp(prob, income_gross_1, JP.income_tax_bands, 1/gbpjpy)
            tax_2 = income_tax_lp(prob, income_gross_2, JP.income_tax_bands, 1/gbpjpy)
            cgt = cg * JP.cgt_rate
        else:
            raise NotImplemetedError

        incomings = income_gross_1 + income_gross_2 + drawdown_isa + drawdown_gia
        if uk_yr:
            incomings += tfc_1 + tfc_2
        if yr < retirement_year:
            incomings += misc_contrib
        outgoings = tax_1 + tax_2 + cgt
        if yr >= retirement_year:
            outgoings += retirement_income_net
            outgoings += contrib_1*0.80
            outgoings += contrib_2*0.80

        surplus = incomings - outgoings

        prob += surplus == 0

        states[yr] = LPState(
            sipp_uf_1=sipp_1.uf,
            sipp_uf_2=sipp_2.uf,
            sipp_df_1=sipp_1.df,
            sipp_df_2=sipp_2.df,
            contrib_1=contrib_1,
            contrib_2=contrib_2,
            tfc_1=tfc_1,
            tfc_2=tfc_2,
            lta_1=sipp_1.lta,
            lta_2=sipp_2.lta,
            lac_1=lac_1,
            lac_2=lac_2,
            isa=isa,
            gia=gia.value(),
            cg=cg,
            drawdown_1=drawdown_1,
            drawdown_2=drawdown_2,
            drawdown_isa=drawdown_isa,
            drawdown_gia=drawdown_gia,
            income_state_1=income_state_1,
            income_state_2=income_state_2,
            income_gross_1=income_gross_1,
            income_gross_2=income_gross_2,
        )

    if max_income:
        prob.setObjective(-retirement_income_net)
    else:
        # TODO: IHT
        net_worth = sipp_1.uf + sipp_2.uf + sipp_1.df + sipp_2.df + isa + gia.value()
        prob.setObjective(-net_worth)

    prob.checkDuplicateVars()

    #prob.writeLP('retirement.lp')

    solvers = lp.listSolvers(onlyAvailable=True)
    if 'PULP_CBC_CMD' in solvers:
        solver = lp.PULP_CBC_CMD(msg=0)
    else:
        assert 'COIN_CMD' in solvers
        solver = lp.COIN_CMD(msg=0)

    status = prob.solve(solver)
    if status != lp.LpStatusOptimal:
        statusMsg = {
            lp.LpStatusNotSolved: "Not Solved",
            lp.LpStatusOptimal: "Optimal",
            lp.LpStatusInfeasible: "Infeasible",
            lp.LpStatusUnbounded: "Unbounded",
            lp.LpStatusUndefined: "Undefined",
        }.get(status, "Unexpected")
        raise ValueError(f"Failed to solve the problem ({statusMsg})")

    result.net_worth_end = normalize(lp.value(sipp_1.uf + sipp_1.df + sipp_2.uf + sipp_2.df + isa + gia.value()), 0)

    if max_income:
        result.retirement_income_net = lp.value(retirement_income_net)
    else:
        result.retirement_income_net = retirement_income_net

    if max_income:
        retirement_income_net = lp.value(retirement_income_net)

    for yr in range(present_year, end_year):
        retirement = yr >= retirement_year
        uk_yr = not retirement or country == 'UK'

        s = states[yr]
        if verbosity > 1:
            if yr == retirement_year:
                for n, v in s._asdict().items():
                    print(f' {n} = {lp.value(v)}')

        contrib_1 = lp.value(s.contrib_1)
        contrib_2 = lp.value(s.contrib_2)

        sipp_uf_1 = lp.value(s.sipp_uf_1)
        sipp_uf_2 = lp.value(s.sipp_uf_2)

        sipp_df_1 = lp.value(s.sipp_df_1)
        sipp_df_2 = lp.value(s.sipp_df_2)

        tfc_1 = lp.value(s.tfc_1)
        tfc_2 = lp.value(s.tfc_2)

        lta_1 = lp.value(s.lta_1)
        lta_2 = lp.value(s.lta_2)

        isa = lp.value(s.isa)
        gia = lp.value(s.gia)

        drawdown_1   = lp.value(s.drawdown_1)
        drawdown_2   = lp.value(s.drawdown_2)
        drawdown_isa = lp.value(s.drawdown_isa)
        drawdown_gia = lp.value(s.drawdown_gia)

        cg = lp.value(s.cg)

        # State pension
        income_state_1 = s.income_state_1
        income_state_2 = s.income_state_2

        # Income and Capital Gain Taxes calculation
        income_gross_1 = lp.value(s.income_gross_1)
        income_gross_2 = lp.value(s.income_gross_2)
        if uk_yr:
            # UK
            if yr < retirement_year:
                cgt_rate = min(cgt_rate_map[marginal_income_tax_1], cgt_rate_map[marginal_income_tax_2])
                tax_1 = income_gross_1 * marginal_income_tax_1
                tax_2 = income_gross_2 * marginal_income_tax_2
            elif marriage_allowance and income_state_2 <= UK.income_tax_threshold_20:
                tax_1 = UK.income_tax(income_gross_1, UK.marriage_allowance)
                tax_2 = UK.income_tax(income_gross_2, -UK.marriage_allowance)
                cgt_rate = cgt_rates[0] # Basic rate
            else:
                cgt_rate = cgt_rates[1] # Higher rate
                tax_1 = UK.income_tax(income_gross_1)
                tax_2 = UK.income_tax(income_gross_2)
            cgt = max(cg - N*cgt_allowance, 0) * cgt_rate
        elif country == 'PT':
            income_gross = income_gross_1 + income_gross_2

            tax = PT.income_tax(income_gross, factor=N/gbpeur)
            cgt = cg * PT.cgt_rate
            if cg >= 0 and False:
                tax_a = tax
                income_gross_b = income_gross + cg
                tax_b = PT.income_tax(income_gross_b, factor=N/gbpeur)
                cgt_alt = tax_b - tax_a
                if cgt_alt < cgt:
                    cgt = cgt_alt

            tax_1 = tax * income_ratio_1
            tax_2 = tax * income_ratio_2
        elif country == 'JP':
            tax_1 = JP.income_tax(income_gross_1, factor=1/gbpjpy)
            tax_2 = JP.income_tax(income_gross_2, factor=1/gbpjpy)
            cgt = cg * JP.cgt_rate

        incomings = income_gross_1 + income_gross_2 + drawdown_isa + drawdown_gia
        if uk_yr:
            incomings += tfc_1 + tfc_2
        if yr < retirement_year:
            incomings += misc_contrib
        outgoings = tax_1 + tax_2 + cgt
        if yr >= retirement_year:
            outgoings += contrib_1*0.80
            outgoings += contrib_2*0.80
        surplus = incomings - outgoings
        income_net = surplus
        if yr >= retirement_year:
            surplus -= retirement_income_net

        tax_rate_1 = tax_1 / max(income_gross_1, 1)
        tax_rate_2 = tax_2 / max(income_gross_2, 1)
        cgt_rate   = cgt   / max(cg, 1)

        lac_1 = lp.value(s.lac_1)
        lac_2 = lp.value(s.lac_2)
        lac = lac_1 + lac_2

        if verbosity > 0:
            print(' '.join((
                    '%4u:',
                    'St %5.0f',
                    'SIPP1 [%7.0f %7.0f] (%6.0f %7.0f) %5.1f%%',
                    'SIPP2 [%7.0f %7.0f] (%6.0f %7.0f) %5.1f%%',
                    'ISA %7.0f (%7.0f)',
                    'GIA %7.0f (%7.0f)',
                    'Inc Gr %6.0f %6.0f Nt %6.0f (%+6.0f)',
                    'Tax %6.0f %4.1f%% %6.0f %4.1f%% %6.0f %4.1f%% %6.0f'
                )) % (
                    yr,
                    income_state_1 + income_state_2,
                    sipp_uf_1, sipp_df_1, contrib_1, -tfc_1 - drawdown_1, 100*lta_1/lta,
                    sipp_uf_2, sipp_df_2, contrib_2, -tfc_2 - drawdown_2, 100*lta_2/lta,
                    isa, -drawdown_isa,
                    gia, -drawdown_gia,
                    income_gross_1, income_gross_2, income_net, surplus,
                    tax_1, 100 * tax_rate_1,
                    tax_2, 100 * tax_rate_2,
                    cgt, 100 * cgt_rate,
                    lac
                ))
        tax = tax_1 + tax_2 + cgt + lac
        result.total_tax += tax

        rs = ResState(
            year=yr,
            income_state=income_state_1 + income_state_2,
            sipp_uf_1=normalize(sipp_uf_1, 2),
            sipp_uf_2=normalize(sipp_uf_2, 2),
            sipp_df_1=normalize(sipp_df_1, 2),
            sipp_df_2=normalize(sipp_df_2, 2),
            contrib_1=normalize(contrib_1, 2),
            contrib_2=normalize(contrib_2, 2),
            sipp_delta_1=normalize(-drawdown_1, 2),
            sipp_delta_2=normalize(-drawdown_2, 2),
            tfc_1=normalize(tfc_1, 2),
            tfc_2=normalize(tfc_2, 2),
            lta_ratio_1=normalize(lta_1/lta, 4),
            lta_ratio_2=normalize(lta_2/lta, 4),
            isa=isa,
            isa_delta=normalize(-drawdown_isa, 2),
            gia=normalize(gia, 2),
            gia_delta=normalize(-drawdown_gia, 2),
            income_gross_1=income_gross_1,
            income_gross_2=income_gross_2,
            cg=cg,
            income_net=income_net,
            income_surplus=normalize(surplus, 2),
            income_tax_1=tax_1,
            income_tax_2=tax_2,
            income_tax_rate_1=tax_rate_1,
            income_tax_rate_2=tax_rate_2,
            cgt=cgt,
            cgt_rate=cgt_rate,
            lac=lac
        )

        result.data.append(rs)

    if lump_sum:
        result.ls_sipp_1 = lp.value(ls_sipp_1)
        result.ls_sipp_2 = lp.value(ls_sipp_2)
        result.ls_isa    = lp.value(ls_isa)
        result.ls_gia    = lp.value(ls_gia)

    return result

# Columns headers for DataFrame
column_headers = {
    'year': 'Year',

    'income_state': 'SP',

    'sipp_uf_1': 'UF1',
    'contrib_1': '(+\u0394)',
    'tfc_1': 'TFC1',
    'sipp_df_1': 'DF1',
    'sipp_delta_1': '(\u0394)',
    'lta_ratio_1': '(%)',
    'sipp_uf_2': 'UF2',
    'contrib_2': '(+\u0394)',
    'tfc_2': 'TFC2',
    'sipp_df_2': 'DF2',
    'sipp_delta_2': '(\u0394)',
    'lta_ratio_2': '(%)',

    'isa': 'ISAs',
    'isa_delta': '(\u0394)',
    'gia': 'GIA',
    'gia_delta': '(\u0394)',
    'income_gross_1': 'GI1',
    'income_gross_2': 'GI2',
    'cg': 'CG',
    'income_net': 'NI',
    'income_surplus': 'Error',
    'income_tax_1': 'IT1',
    'income_tax_rate_1': '(%)',
    'income_tax_2': 'IT2',
    'income_tax_rate_2': '(%)',
    'cgt': 'CGT',
    'cgt_rate': '(%)',
    'lac': 'LAC',
}


def dataframe(data):
    import pandas as pd

    df = pd.DataFrame(data)

    return df


def run(params):

    result = model(**params)

    df = dataframe(result.data)

    # https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_string.html#pandas.DataFrame.to_string

    float_format = '{:5.0f}'.format
    perc_format = '{:5.1%}'.format
    delta_format = '{:+4.0f}'.format
    formatters = {
        'year': '{:}'.format,
        'sipp_delta_1': delta_format,
        'sipp_delta_2': delta_format,
        'contrib_1': delta_format,
        'contrib_2': delta_format,
        'isa_delta': delta_format,
        'gia_delta': delta_format,
        'income_surplus': delta_format,
        'lta_ratio_1':  perc_format,
        'lta_ratio_2':  perc_format,
        'income_tax_rate_1': perc_format,
        'income_tax_rate_2': perc_format,
        'cgt_rate':     perc_format,
    }

    print(df.to_string(
        index=False,
        columns=column_headers.keys(),
        header=column_headers.values(),
        justify='center',
        float_format=float_format,
        formatters=formatters
    ))

    #df.to_csv('data.csv', index=False, float_format='{:.3f}'.format)

    print(f"Start net worth:       {result.net_worth_start:10,.0f}")
    print(f"Retirement net income: {result.retirement_income_net:10,.0f}")
    print(f"End net worth:         {result.net_worth_end:10,.0f}")
    print(f"Total tax:             {result.total_tax:10,.0f}")

    if result.ls_sipp_1 + result.ls_sipp_2 + result.ls_isa + result.ls_gia:
        print(f"Lump sump allocation:")
        print(f"  SIPP1: {result.ls_sipp_1:8.0f}")
        print(f"  SIPP2: {result.ls_sipp_2:8.0f}")
        print(f"  ISA:   {result.ls_isa:8.0f}")
        print(f"  GIA:   {result.ls_gia:8.0f}")
