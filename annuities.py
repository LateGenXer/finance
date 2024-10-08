#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import datetime

from data import mortality


cur_year = datetime.datetime.now(datetime.timezone.utc).year


def escalation_level(years):
    return 1.0


def escalation_fixed(rate):
    def escalation(years):
        return (1.0 + rate) ** years
    return escalation


def escalation_deferred(delay):
    def decorate(fn):
        def escalation(years):
            return 0.0 if years < delay else fn(years - delay)
    return decorate


# https://en.wikipedia.org/wiki/Actuarial_present_value
def present_value(cur_age, yield_curve, table:mortality.Table, escalation=escalation_level):
    yob = cur_year - cur_age

    ages = list(range(cur_age, 121))

    p = 1.0
    pv = 0.0
    for age in ages:
        years = age - cur_age
        index = float(years)
        index = max(index,  0.5)
        index = min(index, 40.0)
        pay = escalation(years)
        rate = yield_curve(index)
        if False:
            print(f'{years:2d}  {rate:6.2%}  {p:7.2%}')
        pv += pay * p * (1.0 + rate)**-years
        qx = table.mortality(yob + age, age)
        p *= 1.0 - qx
    assert p == 0.0

    return pv


def annuity_rate(cur_age, yield_curve, table:mortality.Table):
    pv = present_value(cur_age, yield_curve, table)
    ar = 1.0/pv
    return ar
