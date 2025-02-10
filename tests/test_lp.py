#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import lp


def test():
    x = lp.LpVariable("x", 0, 3)
    y = lp.LpVariable("y", 0, None)
    prob = lp.LpProblem("myProblem", lp.LpMinimize)
    prob += x + y <= 2
    prob += -4*x + y
    status = prob.solve()
    assert status == lp.LpStatusOptimal
    assert lp.value(x) == 2.0
