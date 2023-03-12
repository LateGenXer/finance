#!/usr/bin/env python3
#
# Copyright (c) 2023 LateGenXer.  All rights reserved
#


import os
import math

from dataclasses import dataclass, field
from typing import Any

#import pulp as lp
import lp

import uk as UK
import pt as PT

from uk import *


verbosity = 0

uid = 0


@dataclass
class LPState:
    contrib_1: Any = 0
    contrib_2: Any = 0
    crystalize_lta_1: Any = 0
    crystalize_lta_2: Any = 0
    crystalize_lae_1: Any = 0
    crystalize_lae_2: Any = 0
    lta_1: Any = 0
    lta_2: Any = 0
    lac_1: Any = 0
    lac_2: Any = 0
    drawdown_1: Any = 0
    drawdown_2: Any = 0
    drawdown_isa: Any = 0
    drawdown_gia: Any = 0
    income_state_1: Any = 0
    income_state_2: Any = 0
    income_gross_1: Any = 0
    income_gross_2: Any = 0


@dataclass
class ResState:
    year: int
    income_state: float = 0
    sipp_uf_1: float = 0
    sipp_uf_2: float = 0
    sipp_df_1: float = 0
    sipp_df_2: float = 0
    sipp_delta_1: float = 0
    sipp_delta_2: float = 0
    lta_ratio_1: float = 0
    lta_ratio_2: float = 0
    isa: float = 0
    isa_delta: float = 0
    gia: float = 0
    gia_delta: float = 0
    income_gross_1: float = 0
    income_gross_2: float = 0
    income_net: float = 0
    income_surplus: float = 0
    income_tax_1: float = 0
    income_tax_2: float = 0
    income_tax_rate_1: float = 0
    income_tax_rate_2: float = 0
    cgt: float = 0
    cgt_rate: float = 0
    lac: float = 0


@dataclass
class Result:
    retirement_income_net: float = 0
    net_worth_start: float = 0
    net_worth_end: float = 0
    total_tax: float = 0
    data: list[ResState] = field(default_factory=list)


def normalize(x, ndigits=None):
    # https://bugs.python.org/issue45995
    return round(x, ndigits) + 0.0


def model(
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
        isa,
        isa_growth_rate,
        gia,
        gia_growth_rate,
        misc_contrib,
        marginal_income_tax_1,
        marginal_income_tax_2,
        state_pension_years_1=35,
        state_pension_years_2=35,
        **kwargs
    ):

    result = Result()

    result.net_worth_start = normalize(sipp_1 + sipp_2 + isa + gia, 2)

    state_pension_1 = UK.state_pension_full * state_pension_years_1 / 35
    state_pension_2 = UK.state_pension_full * state_pension_years_2 / 35

    # LTA was due to grow with inflation but it's frozen for 5 years
    lta = UK.lta
    lta *= (1 - 0.025) ** 5

    lta_1 = lta
    lta_2 = lta

    sipp_growth_rate_real_1 = sipp_growth_rate_1 - inflation_rate
    sipp_growth_rate_real_2 = sipp_growth_rate_2 - inflation_rate
    isa_growth_rate_real   = isa_growth_rate   - inflation_rate

    cgt_rate = 0.20
    #cgt_rate = 0.10 #XXX

    assert sipp_contrib_1 <= 40000
    assert sipp_contrib_2 <= 40000

    # https://www.expatistan.com/cost-of-living/comparison/london/lisbon
    # https://www.expatistan.com/cost-of-living/comparison/london/tokyo

    #assert net_income(retirement_income_gross) == retirement_income_net

    # https://www.ftadviser.com/pensions/2018/04/27/actuaries-set-3-5-as-safe-drawdown-rate/

    lta_1 = lta
    lta_2 = lta

    gbpeur = 1.13895

    # TODO: Maximize dividend allowance https://www.gov.uk/tax-on-dividends

    # https://eportugal.gov.pt/en/migrantes-viver-e-trabalhar-em-portugal/migrantes-impostos-e-seguranca-social-em-portugal
    # https://www.expat.hsbc.com/expat-explorer/expat-guides/japan/tax-in-japan/

    prob = lp.LpProblem("Retirement")

    max_income = retirement_income_net == 0
    if max_income:
        retirement_income_net = lp.LpVariable("income", 0)

    def income_tax_(gross_income, income_tax_bands):
        global uid
        total = 0
        tax = 0
        lbound = 0
        for ubound, rate in income_tax_bands:
            if ubound is None:
                ub = None
            else:
                ub = ubound - lbound
            income_tax_band = lp.LpVariable(f'net_{uid}_{int(rate*1000)}', 0, ub)
            uid += 1
            total += income_tax_band
            tax += income_tax_band * rate
            lbound = ubound
        prob.addConstraint(total == gross_income)
        return tax


    uk_income_tax_bands = [
        (income_tax_threshold_20,  0.00),
        (income_tax_threshold_40,  0.20),
        (               pa_limit,  0.40),
        (                   None,  0.60), # 0.40 + 0.5*0.40
        # FIXME: we can't model the 45% tax rate, as it's no longer convex
    ]


    def net_income_(gross_income):
        global prob
        # Although the following condition is necessary for accurate tax
        # modeling, but it would effectively leads to maximize the marginal 60%
        # income tax band.
        #prob += gross_income <= 100000 + 2*income_tax_threshold_20
        tax = income_tax_(gross_income, uk_income_tax_bands)
        return gross_income - tax


    def net_income_pt_(gross_income):
        tax = income_tax_(gross_income, PT.income_tax_bands)
        return gross_income - tax


    def cgt_(cg):
        global uid
        cg_00 = lp.LpVariable(f'cgt_{uid}_00', 0, cgt_allowance*2)
        cg_20 = lp.LpVariable(f'cgt_{uid}_20', 0)
        uid += 1
        prob.addConstraint(cg_00 + cg_20 == cg)
        return cg_20 * cgt_rate

    bak_sipp_1 = sipp_1
    bak_sipp_2 = sipp_2
    bak_lta_1 = lta_1
    bak_lta_2 = lta_2
    bak_isa = isa
    bak_gia = gia

    marginal = False
    if marginal:
        employee_contribution = 7.0
        employer_contribution = 10.0

        employee_nic_rate =  2.0/100.0 # marginal
        employer_nic_rate = 13.8/100.0

        marginal_sipp_1 = lp.LpVariable('marginal_sipp_1', 0.0)
        marginal_sipp_2 = lp.LpVariable('marginal_sipp_2', 0.0)
        marginal_isa    = lp.LpVariable('marginal_isa', 0)

        prob += marginal_sipp_1 + marginal_sipp_2 + marginal_isa == 1.000000

        delta_sipp_1 = marginal_sipp_1
        delta_sipp_2 = marginal_sipp_2
        delta_isa    = marginal_isa

        delta_sipp_1 *= 1.0 / (1 - marginal_income_tax_1 - employee_nic_rate)
        delta_sipp_2 *= 1.0 / (1 - marginal_income_tax_2)

        # Consider employers' matching
        match_benefit_gross = (employee_contribution + employer_contribution) / employee_contribution
        # Same, but minus employer's and employee's taxes
        match_benefit_net   = (employee_contribution + employer_contribution*(1 - employer_nic_rate)) / employee_contribution

        if True:
            delta_sipp_1 *= match_benefit_gross
            delta_sipp_2 *= match_benefit_net
            delta_isa    *= match_benefit_net

        sipp_1 += delta_sipp_1
        sipp_2 += delta_sipp_2
        isa   += delta_isa


    sipp_uf_1 = sipp_1
    sipp_uf_2 = sipp_2
    sipp_df_1 = 0
    sipp_df_2 = 0
    del sipp_1
    del sipp_2

    end_year = max(dob_1, dob_2) + 100
    #end_year = retirement_year + 3

    states = {}

    sipp_df_1_paid = 0
    sipp_df_2_paid = 0

    # SIPP contributions
    # https://www.gov.uk/government/publications/rates-and-allowances-pension-schemes/pension-schemes-rates#member-contributions
    # Limit post drawdown contributions to %30 over standard contributions to follow TFC recycling rule
    sipp_contrib = False
    if sipp_contrib:
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

        # State pension
        income_state_1 = state_pension_1 if age_1 >= state_pension_age else 0
        income_state_2 = state_pension_2 if age_2 >= state_pension_age else 0

        lac_1 = 0
        lac_2 = 0

        # Benefit Crystallisation Event 5
        # https://www.gov.uk/hmrc-internal-manuals/pensions-tax-manual/ptm088650
        if age_1 == 75:
            # BCE 5A
            # https://moneyengineer.co.uk/13-anticipating-pension-growth-and-bce-5a/
            loss = lp.LpVariable(f'bce_5a_loss_1', 0)
            gain = lp.LpVariable(f'bce_5a_gain_1', 0)
            prob += sipp_df_1_paid - loss + gain == sipp_df_1
            lac_1 += gain * 0.25
            sipp_df_1 -= gain * 0.25
            prob += sipp_df_1 >= 0
            # BCE 5B
            cf_1 = lp.LpVariable(f'cf_1@{yr}', 0)
            prob += cf_1 <= lta_1
            surplus_1 = sipp_uf_1 - cf_1
            prob += surplus_1 >= 0
            sipp_uf_1 -= surplus_1 * 0.25
            lac_1 += surplus_1 * 0.25
        if age_2 == 75:
            # BCE 5A
            # https://moneyengineer.co.uk/13-anticipating-pension-growth-and-bce-5a/
            loss = lp.LpVariable(f'bce_5a_loss_2', 0)
            gain = lp.LpVariable(f'bce_5a_gain_2', 0)
            prob += sipp_df_2_paid - loss + gain == sipp_df_2
            lac_2 += gain * 0.25
            sipp_df_2 -= gain * 0.25
            prob += sipp_df_2 >= 0
            # BCE 5B
            cf_2 = lp.LpVariable(f'cf_2@{yr}', 0)
            prob += cf_2 <= lta_2
            surplus_2 = sipp_uf_2 - cf_2
            prob += surplus_2 >= 0
            sipp_uf_2 -= surplus_2 * 0.25
            lac_2 += surplus_2 * 0.25

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
            if sipp_contrib: #XXX
                if not pt and yr < retirement_year + 5:
                    if age_2 < state_pension_age:
                        contrib_2 = sipp_contrib_pre_2
                    elif age_2 < 75:
                        contrib_2 = sipp_contrib_post_2
        sipp_uf_1 += contrib_1
        sipp_uf_2 += contrib_2

        # Flexible-Access Drawdown
        # https://www.gov.uk/hmrc-internal-manuals/pensions-tax-manual/ptm062701
        crystalize_lta_1 = 0
        crystalize_lae_1 = 0
        if age_1 >= nmpa:
            crystalize_lta_1 = lp.LpVariable(f'crystalize_lta_1@{yr}', 0)
            lta_1 -= crystalize_lta_1
            prob += lta_1 >= 0
            sipp_uf_1 -= crystalize_lta_1
            sipp_df_1 += 0.75*crystalize_lta_1
            sipp_df_1_paid += 0.75*crystalize_lta_1
            crystalize_lae_1 = lp.LpVariable(f'crystalize_lae_1@{yr}', 0)
            sipp_uf_1 -= crystalize_lae_1
            if age_1 < 75:
                sipp_df_1 += crystalize_lae_1 * (1 - 0.25)
                sipp_df_1_paid += crystalize_lae_1 * (1 - 0.25)
                lac_1 += crystalize_lae_1 * 0.25
            else:
                sipp_df_1 += crystalize_lae_1
                sipp_df_1_paid += crystalize_lae_1
            crystalize_1 = crystalize_lta_1 + crystalize_lae_1
        crystalize_lta_2 = 0
        crystalize_lae_2 = 0
        if age_2 >= nmpa:
            crystalize_lta_2 = lp.LpVariable(f'crystalize_lta_2@{yr}', 0)
            lta_2 -= crystalize_lta_2
            prob += lta_2 >= 0
            sipp_uf_2 -= crystalize_lta_2
            sipp_df_2 += 0.75*crystalize_lta_2
            sipp_df_2_paid += 0.75*crystalize_lta_2
            crystalize_lae_2 = lp.LpVariable(f'crystalize_lae_2@{yr}', 0)
            sipp_uf_2 -= crystalize_lae_2
            if age_2 < 75:
                sipp_df_2 += crystalize_lae_2 * (1 - 0.25)
                sipp_df_2_paid += crystalize_lae_2 * (1 - 0.25)
                lac_2 += crystalize_lae_2 * 0.25
            else:
                sipp_df_2 += crystalize_lae_2
                sipp_df_2_paid += crystalize_lae_2
            crystalize_2 = crystalize_lta_2 + crystalize_lae_2

        tfc_1 = 0.25*crystalize_lta_1
        tfc_2 = 0.25*crystalize_lta_2

        prob += sipp_uf_1 >= 0
        prob += sipp_uf_2 >= 0

        # Don't drawdown pension pre-retirement if there's a chance of violating MPAA
        drawdown_1 = lp.LpVariable(f'dd_1@{yr}', 0) if age_1 >= nmpa and (retirement or sipp_contrib_1 <= mpaa) else 0
        drawdown_2 = lp.LpVariable(f'dd_2@{yr}', 0) if age_2 >= nmpa and (retirement or sipp_contrib_2 <= mpaa) else 0

        if pt_yr:
            isa_allowance_yr = 0
        else:
            isa_allowance_yr = isa_allowance*2

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

        sipp_df_1_paid *= 1 - inflation_rate
        sipp_df_2_paid *= 1 - inflation_rate

        sipp_df_1 *= 1.0 + sipp_growth_rate_real_1
        sipp_df_2 *= 1.0 + sipp_growth_rate_real_2

        isa *= 1.0 + isa_growth_rate_real
        cg = gia * gia_growth_rate
        gia += cg
        gia *= 1.0 - inflation_rate

        # Income and Capital Gain Taxes modelling
        income_gross_1 = income_state_1 + drawdown_1
        income_gross_2 = income_state_2 + drawdown_2
        if not pt_yr:
            # UK
            if yr < retirement_year:
                income_net_1 = marginal_income_tax_1 * income_gross_1
                income_net_2 = marginal_income_tax_2 * income_gross_2
            else:
                income_net_1 = net_income_(income_gross_1)
                income_net_2 = net_income_(income_gross_2)
            cgt = cgt_(cg)
        else:
            # PT
            # https://sjb-global.com/portugal
            income_gross = (income_gross_1 + tfc_1 +
                            income_gross_2 + tfc_2)*0.5
            tfc_2 = tfc_1 = 0

            nhr = yr - retirement_year < 10
            if nhr:
                # https://www.mondaq.com/capital-gains-tax/1234848/moving-to-portugal--tax-planning-and-the-non-habitual-resident-regime#:~:text=Non%2Dhabitual%20residents,source%20dividend%20income.
                income_tax_rate = 0.10
                income_net = income_gross * (1.0 - income_tax_rate)
                cgt = 0
            else:
                # https://www.comparaja.pt/blog/escaloes-irs
                income_net = net_income_pt_(income_gross * gbpeur) * (1 / gbpeur)
                cgt = cg * PT.cgt_rate

            income_gross_1 = income_gross
            income_gross_2 = income_gross
            income_net_1 = income_net
            income_net_2 = income_net

        tax_1 = income_gross_1 - income_net_1
        tax_2 = income_gross_2 - income_net_2

        incomings = income_gross_1 + income_gross_2 + tfc_1 + tfc_2 + drawdown_isa + drawdown_gia
        if yr < retirement_year:
            incomings += misc_contrib
        outgoings = tax_1 + tax_2 + cgt
        if yr >= retirement_year:
            outgoings += retirement_income_net + contrib_2*(1 - 0.80)

        surplus = incomings - outgoings

        prob += surplus == 0

        states[yr] = LPState(
            contrib_1=contrib_1,
            contrib_2=contrib_2,
            crystalize_lta_1=crystalize_lta_1,
            crystalize_lta_2=crystalize_lta_2,
            crystalize_lae_1=crystalize_lae_1,
            crystalize_lae_2=crystalize_lae_2,
            lta_1=lta_1,
            lta_2=lta_2,
            lac_1=lac_1,
            lac_2=lac_2,
            drawdown_1=drawdown_1,
            drawdown_2=drawdown_2,
            drawdown_isa=drawdown_isa,
            drawdown_gia=drawdown_gia,
            income_state_1=income_state_1,
            income_state_2=income_state_2,
            income_gross_1=income_gross_1,
            income_gross_2=income_gross_2,
        )

    #net_worth = (sipp_uf_1 + sipp_uf_2) + (sipp_df_1 + sipp_df_2) + isa + gia
    net_worth = (sipp_uf_1 + sipp_uf_2)*1.001 + (sipp_df_1 + sipp_df_2)*1.0001 + isa*1.00001 + gia

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

    if verbosity > 0:
        print('Expected net worth: %7.0f' % lp.value(net_worth))
    if max_income:
        result.retirement_income_net = lp.value(retirement_income_net)
        if verbosity > 0:
            print('Expected net income: %7.0f' % result.retirement_income_net)
    else:
        result.retirement_income_net = retirement_income_net

    sipp_1 = bak_sipp_1
    sipp_2 = bak_sipp_2
    lta_1 = bak_lta_1
    lta_2 = bak_lta_2
    isa = bak_isa
    gia = bak_gia

    if verbosity > 0:
        print('Net worth: %7.0f' % (sipp_1 + sipp_2 + isa + gia))

    sipp_uf_1 = sipp_1
    sipp_uf_2 = sipp_2
    sipp_df_1 = 0
    sipp_df_2 = 0
    del sipp_1
    del sipp_2

    sipp_df_1_paid = 0
    sipp_df_2_paid = 0

    if verbosity > 0:
        print('SIPP 1: %7.0f (UF %7.0f CF %7.0f)' % (sipp_uf_1 + sipp_df_1, sipp_uf_1, sipp_df_1))
        print('SIPP 2: %7.0f (UF %7.0f CF %7.0f)' % (sipp_uf_2 + sipp_df_2, sipp_uf_2, sipp_df_2))
        print('ISA:    %7.0f' % isa)
        print('GIA:    %7.0f' % gia)

    if max_income:
        retirement_income_net = lp.value(retirement_income_net)

    def lta_test(lta, crystalized):
        lta -= crystalized
        if lta < 0:
            # Income
            lac = -lta * 0.25
            lta = 0
        else:
            lac = 0
        return lta, lac

    for yr in range(present_year, end_year):
        retirement = yr >= retirement_year
        pt_yr = retirement and pt

        if pt and yr == retirement_year:
            gia += isa
            isa = 0

        age_1 = yr - dob_1
        age_2 = yr - dob_2

        s = states[yr]
        if verbosity > 1:
            if yr == retirement_year:
                for n, v in s._asdict().items():
                    print(f' {n} = {lp.value(v)}')

        lac_ = 0

        # Bed & SIPP
        contrib_1 = lp.value(s.contrib_1)
        contrib_2 = lp.value(s.contrib_2)
        sipp_uf_1 += contrib_1
        sipp_uf_2 += contrib_2

        # BCE 5
        if age_1 == 75:
            # BCE 5A
            gain_1 = max(sipp_df_1 - sipp_df_1_paid, 0)
            #print('BCE5A', sipp_df_1_paid, sipp_df_1)
            lta_1, lac_5a = lta_test(lta_1, gain_1)
            sipp_df_1 -= lac_5a
            lac_ += lac_5a
            # BCE 5B
            lta_1, lac_5b = lta_test(lta_1, sipp_uf_1)
            sipp_uf_1 -= lac_5b
            lac_ += lac_5b
            #print('BCE5', lac_5a, lac_5b)
        if age_2 == 75:
            surplus_2 = max(sipp_uf_2 - lta_2, 0)
            sipp_uf_2 -= surplus_2 * 0.25
            lac_ += surplus_2 * 0.25

        crystalize_lta_1  = lp.value(s.crystalize_lta_1)
        crystalize_lta_2  = lp.value(s.crystalize_lta_2)
        crystalize_lae_1  = lp.value(s.crystalize_lae_1)
        crystalize_lae_2  = lp.value(s.crystalize_lae_2)

        # BCE 1 & BCE 6
        lta_1 -= crystalize_lta_1
        lta_2 -= crystalize_lta_2

        sipp_uf_1 -= crystalize_lta_1
        sipp_uf_2 -= crystalize_lta_2
        sipp_uf_1 -= crystalize_lae_1
        sipp_uf_2 -= crystalize_lae_2

        tfc_1 = 0.25*crystalize_lta_1
        tfc_2 = 0.25*crystalize_lta_2

        sipp_df_1_paid *= 1 - inflation_rate
        sipp_df_2_paid *= 1 - inflation_rate
        sipp_df_1_paid += 0.75*crystalize_lta_1
        sipp_df_2_paid += 0.75*crystalize_lta_2
        sipp_df_1_paid += crystalize_lae_1 * (0.75 if age_1 < 75 else 1)
        sipp_df_2_paid += crystalize_lae_2 * (0.75 if age_2 < 75 else 1)

        sipp_df_1 += 0.75*crystalize_lta_1
        sipp_df_2 += 0.75*crystalize_lta_2
        sipp_df_1 += crystalize_lae_1 * (0.75 if age_1 < 75 else 1)
        sipp_df_2 += crystalize_lae_2 * (0.75 if age_2 < 75 else 1)
        lac_ += crystalize_lae_1 * (0.25 if age_1 < 75 else 0)
        lac_ += crystalize_lae_2 * (0.25 if age_2 < 75 else 0)

        drawdown_1    = lp.value(s.drawdown_1)
        drawdown_2    = lp.value(s.drawdown_2)
        drawdown_isa = lp.value(s.drawdown_isa)
        drawdown_gia  = lp.value(s.drawdown_gia)

        # State pension
        income_state_1 = s.income_state_1
        income_state_2 = s.income_state_2

        sipp_df_1 -= drawdown_1
        sipp_df_2 -= drawdown_2
        isa       -= drawdown_isa
        gia       -= drawdown_gia

        sipp_uf_1 *= 1.0 + sipp_growth_rate_real_1
        sipp_df_1 *= 1.0 + sipp_growth_rate_real_1
        sipp_uf_2 *= 1.0 + sipp_growth_rate_real_2
        sipp_df_2 *= 1.0 + sipp_growth_rate_real_2
        isa *= 1.0 + isa_growth_rate_real
        cg = gia * gia_growth_rate
        gia += cg
        gia *= 1.0 - inflation_rate

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
            income_gross = (income_gross_1 +
                            income_gross_2)*0.5
            tfc_2 = tfc_1 = 0

            nhr = yr - retirement_year < 10
            if nhr:
                # XXX Correct? https://www.blevinsfranks.com/tax-and-pensions-portugal/#:~:text=Portugal%20at%20all.-,personal%20pensions,-This%20is%20where
                # XXX ICAE?
                # - https://www.blacktowerfm.com/benefits-of-life-assurance-in-portugal/
                # - https://www.blacktowerfm.com/news/tax-compliant-solutions-for-the-portuguese-tax-resident-by-antonio-rosa-regional-manager-lisbon/

                # https://www.mondaq.com/capital-gains-tax/1234848/moving-to-portugal--tax-planning-and-the-non-habitual-resident-regime#:~:text=Non%2Dhabitual%20residents,source%20dividend%20income.
                income_tax_rate = 0.10
                income_net = income_gross * (1.0 - income_tax_rate)
                cgt = 0
            else:
                # https://www.comparaja.pt/blog/escaloes-irs
                income_net = PT.net_income_pt(income_gross * gbpeur) / gbpeur
                cgt = cg * PT.cgt_rate
                if cg >= 0 and False:
                    tax_a = income_gross - income_net
                    income_gross_b = income_gross + cg/2
                    income_net_b = PT.net_income_pt(income_gross_b * gbpeur) / gbpeur
                    tax_b = income_gross_b - income_net_b
                    cgt_alt = tax_b - tax_a
                    if cgt_alt < cgt:
                        cgt = cgt_alt

            income_net_1 = income_net
            income_net_2 = income_net

        tax_1 = income_gross_1 - income_net_1
        tax_2 = income_gross_2 - income_net_2

        incomings = income_gross_1 + income_gross_2 + tfc_1 + tfc_2 + drawdown_isa + drawdown_gia
        if yr < retirement_year:
            incomings += misc_contrib
        outgoings = tax_1 + tax_2 + cgt
        if yr >= retirement_year:
            outgoings += retirement_income_net + contrib_2*(1 - 0.80)
        surplus = incomings - outgoings

        income_net = income_net_1 + income_net_2 + tfc_1 + tfc_2 + drawdown_isa + drawdown_gia - cgt
        if yr < retirement_year:
            income_net += misc_contrib
        else:
            income_net -= contrib_2*(1 - 0.80)
        delta = surplus

        tax_rate_1 = tax_1 / max(income_gross_1, 1)
        tax_rate_2 = tax_2 / max(income_gross_2, 1)
        cgt_rate_  = cgt / max(cg, 1)

        lac_1 = lp.value(s.lac_1)
        lac_2 = lp.value(s.lac_2)
        lac = lac_1 + lac_2
        if not marginal and 0:
            assert math.isclose(lac, lac_, rel_tol=.001, abs_tol=.01)

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
                    sipp_uf_1, sipp_df_1, contrib_1  -tfc_1 - drawdown_1, 100*lta_1/lta,
                    sipp_uf_2, sipp_df_2, contrib_2, -tfc_2 - drawdown_2, 100*lta_2/lta,
                    isa, -drawdown_isa,
                    gia, -drawdown_gia,
                    income_gross_1, income_gross_2, income_net, delta,
                    tax_1, 100 * tax_rate_1,
                    tax_2, 100 * tax_rate_2,
                    cgt, 100 * cgt_rate_, lac
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
            income_surplus=normalize(delta, 2),
            income_tax_1=tax_1,
            income_tax_2=tax_2,
            income_tax_rate_1=tax_rate_1,
            income_tax_rate_2=tax_rate_2,
            cgt=cgt,
            cgt_rate=cgt_rate_,
            lac=lac
        )

        result.data.append(rs)

    result.net_worth_end = normalize(sipp_uf_1 + sipp_df_1 + sipp_uf_2 + sipp_df_2 + isa + gia, 0)

    if marginal:
        print('Marginal SIPP 1: %7.0f' % (lp.value(marginal_sipp_1)))
        print('Marginal SIPP 2: %7.0f' % (lp.value(marginal_sipp_2)))
        print('Marginal ISA:    %7.0f' % (lp.value(marginal_isa)))

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


# TODO: IHT
# https://spectrum-ifa.com/can-i-keep-my-uk-pension-as-a-portuguese-resident/


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
