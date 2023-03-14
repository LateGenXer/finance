#!/usr/bin/env python3
#
# Copyright (c) 2023 LateGenXer.  All rights reserved
#


import os
import math
import sys

from dataclasses import dataclass, field
from typing import Any

#import pulp as lp
import lp

import uk as UK
import pt as PT

from uk import *
from pt import gbpeur


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
    lta_ratio_1: float
    lta_ratio_2: float
    isa: float
    isa_delta: float
    gia: float
    gia_delta: float
    income_gross_1: float
    income_gross_2: float
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


def uk_net_income_lp(prob, gross_income):
    # Although the following condition is necessary for accurate tax
    # modeling, but it would effectively leads to maximize the marginal 60%
    # income tax band.
    #prob += gross_income <= 100000 + 2*income_tax_threshold_20
    tax = income_tax_lp(prob, gross_income, uk_income_tax_bands)
    return gross_income - tax


def uk_cgt_lp(prob, cg, cgt_rate):
    global uid
    cg_00 = lp.LpVariable(f'cgt_{uid}_00', 0, cgt_allowance*2)
    cg_20 = lp.LpVariable(f'cgt_{uid}_20', 0)
    uid += 1
    prob += cg_00 + cg_20 == cg
    return cg_20 * cgt_rate


def pt_net_income_lp(prob, gross_income, factor=1.0):
    tax = income_tax_lp(prob, gross_income, PT.income_tax_bands, factor)
    return gross_income - tax


def bce_lp(prob, lta):
    global uid
    crystalized_lta = lp.LpVariable(f'crystalized_lta_{uid}', 0)
    crystalized_lae = lp.LpVariable(f'crystalized_lae_{uid}', 0)
    uid += 1
    lta -= crystalized_lta
    prob += lta >= 0
    return lta, crystalized_lta, crystalized_lae


def bce_lac_lp(prob, lta, crystalized):
    lta, crystalized_lta, crystalized_lae = bce_lp(prob, lta)
    prob += crystalized_lta + crystalized_lae == crystalized
    lac = 0.25 * crystalized_lae
    return lta, lac


# Benefit Crystallisation Event 5A and 5B
# https://www.gov.uk/hmrc-internal-manuals/pensions-tax-manual/ptm088650
def bce_5a_5b_lp(prob, lta, sipp_uf, sipp_df, sipp_df_cost):
    global uid

    # BCE 5A
    # https://moneyengineer.co.uk/13-anticipating-pension-growth-and-bce-5a/
    df_loss = lp.LpVariable(f'df_loss_{uid}', 0)
    df_gain = lp.LpVariable(f'df_gain_{uid}', 0)
    uid += 1
    prob += sipp_df_cost - df_loss + df_gain == sipp_df
    lta, lac_bce_5a = bce_lac_lp(prob, lta, df_gain)
    sipp_df -= lac_bce_5a

    # BCE 5B
    # Funds aren't actually crystallized -- just tested and charged -- so LTA
    # is not updated.
    _, lac_bce_5b = bce_lac_lp(prob, lta, sipp_uf)
    sipp_uf -= lac_bce_5b

    lac = lac_bce_5a + lac_bce_5b

    return lta, sipp_uf, sipp_df, lac


# Benefit Crystallisation Event 1 (DD) and 6 (TFC)
# https://www.gov.uk/hmrc-internal-manuals/pensions-tax-manual/ptm062701
def bce_1_6_lp(prob, lta, sipp_uf, sipp_df, sipp_df_cost, age):
    lac_bce1 = 0
    assert age >= nmpa
    lta, crystalized_lta, crystalized_lae = bce_lp(prob, lta)
    crystalized = crystalized_lta + crystalized_lae
    sipp_uf -= crystalized
    prob += sipp_uf >= 0
    tfc = crystalized_lta * 0.25
    dd = crystalized - tfc - lac_bce1
    if age < 75:
        lac_bce1 = crystalized_lae * 0.25
        dd -= lac_bce1
    sipp_df += dd
    sipp_df_cost += dd
    return lta, sipp_uf, tfc, sipp_df, sipp_df_cost, lac_bce1


def normalize(x, ndigits=None):
    # https://bugs.python.org/issue45995
    return round(x, ndigits) + 0.0


def model(
        joint,
        dob_1,
        dob_2,
        present_year,
        retirement_year,
        inflation_rate,
        retirement_income_net,
        pt,
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
        **kwargs
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

    # LTA was due to grow with inflation but it's frozen until 2028
    lta = UK.lta
    lta *= (1 - inflation_rate) ** max(2028 - present_year, 0)

    sipp_growth_rate_real_1 = sipp_growth_rate_1 - inflation_rate
    sipp_growth_rate_real_2 = sipp_growth_rate_2 - inflation_rate
    isa_growth_rate_real    = isa_growth_rate    - inflation_rate

    cgt_rate = 0.20
    #cgt_rate = 0.10 #XXX

    assert sipp_contrib_1 <= 40000
    assert sipp_contrib_2 <= 40000

    lta_1 = lta
    lta_2 = lta


    prob = lp.LpProblem("Retirement")

    max_income = retirement_income_net == 0
    if max_income:
        retirement_income_net = lp.LpVariable("income", 0)

    sipp_uf_1 = sipp_1
    sipp_uf_2 = sipp_2
    sipp_df_1 = 0
    sipp_df_2 = 0
    del sipp_1
    del sipp_2

    states = {}

    sipp_df_cost_1 = 0
    sipp_df_cost_2 = 0

    # XXX: SIPP contributions
    # https://www.gov.uk/government/publications/rates-and-allowances-pension-schemes/pension-schemes-rates#member-contributions
    # Limit post drawdown contributions to %30 over standard contributions to follow TFC recycling rule
    if sipp_extra_contrib:
        sipp_contrib_limit = 3600
        sipp_contrib_pre_1 = lp.LpVariable('sipp_contrib_pre_1', 0, min(sipp_contrib_limit, sipp_contrib_1 * 1.30))
        sipp_contrib_pre_2 = lp.LpVariable('sipp_contrib_pre_2', 0, min(sipp_contrib_limit, sipp_contrib_2 * 1.30))
        sipp_contrib_post_1 = lp.LpVariable('sipp_contrib_post_1', 0, max(sipp_contrib_limit, min(state_pension_1, mpaa)))
        sipp_contrib_post_2 = lp.LpVariable('sipp_contrib_post_2', 0, max(sipp_contrib_limit, min(state_pension_2, mpaa)))

    for yr in range(present_year, end_year):
        retirement = yr >= retirement_year
        pt_yr = retirement and pt

        if pt and yr == retirement_year:
            gia += isa
            isa = 0

        age_1 = yr - dob_1
        age_2 = yr - dob_2

        # Bed & SIPP
        # XXX: FAD income recycling is OK, but PCLS recycling is not
        # https://www.gov.uk/hmrc-internal-manuals/pensions-tax-manual/ptm133800
        # https://techzone.abrdn.com/public/pensions/tech-guide-recycle-tax-free-cash
        if not retirement:
            contrib_1 = sipp_contrib_1
            contrib_2 = sipp_contrib_2
        else:
            contrib_1 = 0
            contrib_2 = 0
            if sipp_extra_contrib: #XXX
                if not pt and yr < retirement_year + 5:
                    if age_2 < state_pension_age:
                        contrib_2 = sipp_contrib_pre_2
                    elif age_2 < 75:
                        contrib_2 = sipp_contrib_post_2
        sipp_uf_1 += contrib_1
        sipp_uf_2 += contrib_2

        # Benefit Crystallisation Event 5
        # https://www.gov.uk/hmrc-internal-manuals/pensions-tax-manual/ptm088650
        if age_1 == 75:
            lta_1, sipp_uf_1, sipp_df_1, lac_1 = \
                bce_5a_5b_lp(prob, lta_1, sipp_uf_1, sipp_df_1, sipp_df_cost_1)
        else:
            lac_1 = 0
        if age_2 == 75:
            lta_2, sipp_uf_2, sipp_df_2, lac_2 = \
                bce_5a_5b_lp(prob, lta_2, sipp_uf_2, sipp_df_2, sipp_df_cost_2)
        else:
            lac_2 = 0

        # Flexible-Access Drawdown
        if age_1 >= nmpa:
            lta_1, sipp_uf_1, tfc_1, sipp_df_1, sipp_df_cost_1, lac_bce1_1 = \
                bce_1_6_lp(prob, lta_1, sipp_uf_1, sipp_df_1, sipp_df_cost_1, age_1)
            lac_1 += lac_bce1_1
        else:
            tfc_1 = 0
        if age_2 >= nmpa:
            lta_2, sipp_uf_2, tfc_2, sipp_df_2, sipp_df_cost_2, lac_bce1_2 = \
                bce_1_6_lp(prob, lta_2, sipp_uf_2, sipp_df_2, sipp_df_cost_2, age_2)
            lac_2 += lac_bce1_2
        else:
            tfc_2 = 0

        # Don't drawdown pension pre-retirement if there's a chance of violating MPAA
        drawdown_1 = lp.LpVariable(f'dd_1@{yr}', 0) if age_1 >= nmpa and (retirement or sipp_contrib_1 <= mpaa) else 0
        drawdown_2 = lp.LpVariable(f'dd_2@{yr}', 0) if age_2 >= nmpa and (retirement or sipp_contrib_2 <= mpaa) else 0

        if pt_yr:
            isa_allowance_yr = 0
        else:
            isa_allowance_yr = isa_allowance*N

        drawdown_isa = lp.LpVariable(f'dd_isa@{yr}', -isa_allowance_yr)  # Bed & ISA
        drawdown_gia = lp.LpVariable(f'dd_gia@{yr}')

        sipp_df_1 -= drawdown_1
        sipp_df_2 -= drawdown_2
        isa       -= drawdown_isa
        gia       -= drawdown_gia

        prob += sipp_df_1 >= 0
        prob += sipp_df_2 >= 0
        prob += isa >= 0
        prob += gia >= 0

        sipp_uf_1 *= 1.0 + sipp_growth_rate_real_1
        sipp_uf_2 *= 1.0 + sipp_growth_rate_real_2

        sipp_df_cost_1 *= 1 - inflation_rate
        sipp_df_cost_2 *= 1 - inflation_rate

        sipp_df_1 *= 1.0 + sipp_growth_rate_real_1
        sipp_df_2 *= 1.0 + sipp_growth_rate_real_2

        isa *= 1.0 + isa_growth_rate_real
        cg = gia * gia_growth_rate
        gia += cg
        gia *= 1.0 - inflation_rate

        # State pension
        income_state_1 = state_pension_1 if age_1 >= state_pension_age else 0
        income_state_2 = state_pension_2 if age_2 >= state_pension_age else 0

        # Income and Capital Gain Taxes modelling
        income_gross_1 = income_state_1 + drawdown_1
        income_gross_2 = income_state_2 + drawdown_2
        if not pt_yr:
            # UK
            if yr < retirement_year:
                income_net_1 = marginal_income_tax_1 * income_gross_1
                income_net_2 = marginal_income_tax_2 * income_gross_2
            else:
                income_net_1 = uk_net_income_lp(prob, income_gross_1)
                income_net_2 = uk_net_income_lp(prob, income_gross_2)
            cgt = uk_cgt_lp(prob, cg, cgt_rate)
        else:
            # PT
            income_gross = (income_gross_1 + tfc_1 +
                            income_gross_2 + tfc_2)

            nhr = yr - retirement_year < 10
            if nhr:
                income_net = income_gross * (1.0 - PT.nhr_income_tax_rate)
                cgt = 0
            else:
                income_net = pt_net_income_lp(prob, income_gross, factor=N/gbpeur)
                cgt = cg * PT.cgt_rate

            income_gross_1 = income_gross * income_ratio_1
            income_gross_2 = income_gross * income_ratio_2
            income_net_1 = income_net * income_ratio_1
            income_net_2 = income_net * income_ratio_2

        tax_1 = income_gross_1 - income_net_1
        tax_2 = income_gross_2 - income_net_2

        incomings = income_gross_1 + income_gross_2 + drawdown_isa + drawdown_gia
        if not pt_yr:
            incomings += tfc_1 + tfc_2
        if yr < retirement_year:
            incomings += misc_contrib
        outgoings = tax_1 + tax_2 + cgt
        if yr >= retirement_year:
            outgoings += retirement_income_net + contrib_2*(1 - 0.80)

        surplus = incomings - outgoings

        prob += surplus == 0

        states[yr] = LPState(
            sipp_uf_1=sipp_uf_1,
            sipp_uf_2=sipp_uf_2,
            sipp_df_1=sipp_df_1,
            sipp_df_2=sipp_df_2,
            contrib_1=contrib_1,
            contrib_2=contrib_2,
            tfc_1=tfc_1,
            tfc_2=tfc_2,
            lta_1=lta_1,
            lta_2=lta_2,
            lac_1=lac_1,
            lac_2=lac_2,
            isa=isa,
            gia=gia,
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

    # IHT
    if not pt:
        net_worth = (sipp_uf_1 + sipp_uf_2)*1.001 + (sipp_df_1 + sipp_df_2)*1.0001 + (isa*1.00001 + gia)*(1 - 0.40)
    else:
        net_worth = (sipp_uf_1 + sipp_uf_2)*1.001 + (sipp_df_1 + sipp_df_2)*1.0001 + (isa*1.00001 + gia)

    if max_income:
        prob.setObjective(-retirement_income_net)
    else:
        prob.setObjective(-net_worth)

    prob.checkDuplicateVars()

    #prob.writeLP('retirement.lp')

    solver = lp.COIN_CMD(msg=0)
    #solver = lp.GLPK_CMD()
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

    result.net_worth_end = normalize(lp.value(sipp_uf_1 + sipp_df_1 + sipp_uf_2 + sipp_df_2 + isa + gia), 0)

    if max_income:
        result.retirement_income_net = lp.value(retirement_income_net)
    else:
        result.retirement_income_net = retirement_income_net

    if max_income:
        retirement_income_net = lp.value(retirement_income_net)

    for yr in range(present_year, end_year):
        retirement = yr >= retirement_year
        pt_yr = retirement and pt

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
        if not pt_yr:
            # UK
            if yr < retirement_year:
                income_net_1 = marginal_income_tax_1 * income_gross_1
                income_net_2 = marginal_income_tax_2 * income_gross_2
            else:
                income_net_1 = net_income(income_gross_1)
                income_net_2 = net_income(income_gross_2)
            cgt = max(cg - cgt_allowance*2, 0) * cgt_rate
        else:
            # PT
            income_gross = income_gross_1 + income_gross_2

            nhr = yr - retirement_year < 10
            if nhr:
                income_net = income_gross * (1.0 - PT.nhr_income_tax_rate)
                cgt = 0
            else:
                income_net = PT.net_income(income_gross, factor=N/gbpeur)
                cgt = cg * PT.cgt_rate
                if cg >= 0 and False:
                    tax_a = income_gross - income_net
                    income_gross_b = income_gross + cg
                    income_net_b = PT.net_income(income_gross_b, factor=N/gbpeur)
                    tax_b = income_gross_b - income_net_b
                    cgt_alt = tax_b - tax_a
                    if cgt_alt < cgt:
                        cgt = cgt_alt

            income_net_1 = income_net * income_ratio_1
            income_net_2 = income_net * income_ratio_2

        tax_1 = income_gross_1 - income_net_1
        tax_2 = income_gross_2 - income_net_2

        incomings = income_gross_1 + income_gross_2  + drawdown_isa + drawdown_gia
        if not pt_yr:
            incomings += tfc_1 + tfc_2
        if yr < retirement_year:
            incomings += misc_contrib
        outgoings = tax_1 + tax_2 + cgt
        if yr >= retirement_year:
            outgoings += contrib_2*(1 - 0.80)
        surplus = incomings - outgoings
        income_net = surplus
        if yr >= retirement_year:
            surplus -= retirement_income_net

        tax_rate_1 = tax_1 / max(income_gross_1, 1)
        tax_rate_2 = tax_2 / max(income_gross_2, 1)
        cgt_rate_  = cgt / max(cg, 1)

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
                    cgt, 100 * cgt_rate_,
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
            sipp_delta_1=normalize(contrib_1 - tfc_1 - drawdown_1, 2),
            sipp_delta_2=normalize(contrib_2 - tfc_2 - drawdown_2, 2),
            lta_ratio_1=normalize(lta_1/lta, 4),
            lta_ratio_2=normalize(lta_2/lta, 4),
            isa=isa,
            isa_delta=normalize(-drawdown_isa, 2),
            gia=normalize(gia, 2),
            gia_delta=normalize(-drawdown_gia, 2),
            income_gross_1=income_gross_1,
            income_gross_2=income_gross_2,
            income_net=income_net,
            income_surplus=normalize(surplus, 2),
            income_tax_1=tax_1,
            income_tax_2=tax_2,
            income_tax_rate_1=tax_rate_1,
            income_tax_rate_2=tax_rate_2,
            cgt=cgt,
            cgt_rate=cgt_rate_,
            lac=lac
        )

        result.data.append(rs)

    return result

# Columns headers for DataFrame
column_headers = {
    'year': 'Year',

    'income_state': 'SP',

    'sipp_uf_1': 'UF1',
    'sipp_df_1': 'DF1',
    'sipp_delta_1': '(\u0394)',
    'lta_ratio_1': 'LTA1',
    'sipp_uf_2': 'UF2',
    'sipp_df_2': 'DF2',
    'sipp_delta_2': '(\u0394)',
    'lta_ratio_2': 'LTA2',

    'isa': 'ISAs',
    'isa_delta': '(\u0394)',
    'gia': 'GIA',
    'gia_delta': '(\u0394)',
    'income_gross_1': 'GI1',
    'income_gross_2': 'GI2',
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

    print(f"Start net worth:       {result.net_worth_start:10,.0f}")
    print(f"Retirement net income: {result.retirement_income_net:10,.0f}")
    print(f"End net worth:         {result.net_worth_end:10,.0f}")
    print(f"Total tax:             {result.total_tax:10,.0f}")

    #df.to_csv('data.csv', index=False, float_format='{:.3f}'.format)
