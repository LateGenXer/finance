
from lp import *


def test():
    x = LpVariable("x", 0, 3)
    y = LpVariable("y", 0, None)
    prob = LpProblem("myProblem", LpMinimize)
    prob += x + y <= 2
    prob += -4*x + y
    status = prob.solve()
    assert status == LpStatusOptimal
    assert value(x) == 2.0
