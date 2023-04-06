import pytest

from lp import *


def test_lp():
    # https://github.com/coin-or/pulp#documentation
    x = LpVariable("x", 0, 3)
    y = LpVariable("y", 0, None)
    prob = LpProblem()
    prob += x + y <= 2
    prob += -4*x + y
    status = prob.solve()
    assert status == LpStatusOptimal
    assert value(x) == 2.0


def test_milp():
    # https://www.cs.upc.edu/~erodri/webpage/cps/theory/lp/milp/slides.pdf#page=5
    x = LpVariable("x", 0, cat=LpInteger)
    y = LpVariable("y", 0, cat=LpInteger)
    prob = LpProblem(sense=LpMaximize)
    prob += x + y
    prob += -2*x + 2*y >= 1
    prob += -8*x + 10*y <= 13
    status = prob.solve()
    assert status == LpStatusOptimal
    assert value(x) == 1
    assert value(y) == 2
