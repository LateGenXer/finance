#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import os

import pytest

import lp


pulp = int(os.environ.get('PULP', '0')) != 0


def test_variable_name():
    x = lp.LpVariable("x")
    assert x.name == "x"
    assert str(x) == "x"
    assert repr(x) == "x"


@pytest.mark.parametrize("lbound", [-1.0, 0.0, 1.0])
def test_variable_lbound(lbound):
    x = lp.LpVariable("x", lbound, None)
    prob = lp.LpProblem()
    prob += x
    status = prob.solve()
    assert status == lp.LpStatusOptimal
    assert lp.value(x) == lbound


@pytest.mark.parametrize("ubound", [-1.0, 0.0, 1.0])
def test_variable_ubound(ubound):
    x = lp.LpVariable("x", None, ubound)
    prob = lp.LpProblem()
    prob += -x
    status = prob.solve()
    assert status == lp.LpStatusOptimal
    assert lp.value(x) == ubound

xv = 11
yv = 101
zv = 1009


def test_variable_add():
    x = lp.LpVariable("x", xv)
    y = lp.LpVariable("y", yv)
    e = x + y
    prob = lp.LpProblem()
    prob += e
    status = prob.solve()
    assert status == lp.LpStatusOptimal
    assert lp.value(e) == xv + yv
    assert lp.value(x + yv) == xv + yv


def test_variable_radd():
    x = lp.LpVariable("x", xv)
    e = yv + x
    prob = lp.LpProblem()
    prob += e
    status = prob.solve()
    assert status == lp.LpStatusOptimal
    assert lp.value(e) == xv + yv


def test_variable_sub():
    x = lp.LpVariable("x", xv)
    y = lp.LpVariable("y", None, yv)
    e = x - y
    prob = lp.LpProblem()
    prob += e
    status = prob.solve()
    assert status == lp.LpStatusOptimal
    assert lp.value(e) == xv - yv
    assert lp.value(x - yv) == xv - yv


def test_variable_rsub():
    x = lp.LpVariable("x", xv)
    e = yv - x
    prob = lp.LpProblem()
    prob += x
    status = prob.solve()
    assert status == lp.LpStatusOptimal
    assert lp.value(e) == yv - xv


def test_variable_neg():
    x = lp.LpVariable("x", None, xv)
    e = -x
    prob = lp.LpProblem()
    prob += e
    status = prob.solve()
    assert status == lp.LpStatusOptimal
    assert lp.value(e) == -xv


def test_variable_mul():
    x = lp.LpVariable("x", xv)
    e = x * yv
    prob = lp.LpProblem()
    prob += e
    status = prob.solve()
    assert status == lp.LpStatusOptimal
    assert lp.value(e) == xv * yv


def test_variable_eq():
    x = lp.LpVariable("x")
    prob = lp.LpProblem()
    if not pulp:
        assert (x == x) is True
    prob += True
    prob += x == xv
    prob += x
    status = prob.solve()
    assert status == lp.LpStatusOptimal
    assert lp.value(x) == xv


def test_variable_le():
    x = lp.LpVariable("x")
    prob = lp.LpProblem()
    prob += x <= xv
    prob += -x
    status = prob.solve()
    assert status == lp.LpStatusOptimal
    assert lp.value(x) == xv


def test_variable_ge():
    x = lp.LpVariable("x")
    prob = lp.LpProblem()
    prob += x >= xv
    prob += x
    status = prob.solve()
    assert status == lp.LpStatusOptimal
    assert lp.value(x) == xv


@pytest.mark.xfail(pulp, reason="PuLP", raises=TypeError)
def test_variable_truediv():
    x = lp.LpVariable("x", xv)
    e = x / yv
    prob = lp.LpProblem()
    prob += e
    status = prob.solve()
    assert status == lp.LpStatusOptimal
    assert lp.value(e) == pytest.approx(xv / yv)
    assert lp.value(x / 1) == xv


def test_expression_mul():
    x = lp.LpVariable("x", xv)
    y = lp.LpVariable("y", yv)
    e = x + y * 2
    prob = lp.LpProblem()
    prob += e
    status = prob.solve()
    assert status == lp.LpStatusOptimal
    assert lp.value(e * 0) == 0
    assert lp.value(e * 1) == xv + 2*yv
    assert lp.value(e * zv) == (xv + 2*yv) * zv


def test_expression_rmul():
    x = lp.LpVariable("x", xv)
    y = lp.LpVariable("y", yv)
    e = x + 2*y
    prob = lp.LpProblem()
    prob += e
    status = prob.solve()
    assert status == lp.LpStatusOptimal
    assert lp.value(0 * e) == 0
    assert lp.value(1 * e) == xv + 2*yv
    assert lp.value(zv  * e ) == (xv + 2*yv) * zv


@pytest.mark.xfail(pulp, reason="PuLP", raises=TypeError)
def test_expression_truediv():
    x = lp.LpVariable("x", xv)
    y = lp.LpVariable("y", yv)
    e = (x + 2*y) / zv
    prob = lp.LpProblem()
    prob += e
    status = prob.solve()
    assert status == lp.LpStatusOptimal
    assert lp.value(e) == pytest.approx((xv + 2*yv) / zv)
    assert lp.value((x + yv) / 1) == xv + yv


def test_duplicate_vars():
    x = lp.LpVariable("x")
    prob = lp.LpProblem()
    prob += x >= xv
    prob += x

    prob.checkDuplicateVars()

    y = lp.LpVariable("x", yv)
    prob += x - y == 0
    with pytest.raises(Exception):
        prob.checkDuplicateVars()


def test_status_unbounded():
    x = lp.LpVariable("x")
    prob = lp.LpProblem()
    prob += x <= 0
    prob += x
    status = prob.solve()
    assert status == lp.LpStatusUnbounded


def test_status_infeasible():
    x = lp.LpVariable("x")
    prob = lp.LpProblem()
    prob += x <= 0
    prob += x >=  xv
    prob += x
    status = prob.solve()
    assert status == lp.LpStatusInfeasible


def test_variable_add_type_error():
    x = lp.LpVariable("x", xv)
    with pytest.raises(TypeError):
        x + complex(0, 1)


def test_problem_iadd_type_error():
    prob = lp.LpProblem()
    with pytest.raises(TypeError):
        prob += None


def test_value():
    assert lp.value(xv) == xv
    assert lp.value(float(yv)) == float(yv)


@pytest.mark.parametrize('solver_name', lp.listSolvers(onlyAvailable=True))
def test_solver(solver_name):
    solver_fn = getattr(lp, solver_name)
    solver = solver_fn(msg=1)
    x = lp.LpVariable("x", 0, 3)
    y = lp.LpVariable("y", 0, None)
    prob = lp.LpProblem()
    prob += x + y <= 2
    prob += -4*x + y
    status = prob.solve(solver=solver)
    assert status == lp.LpStatusOptimal
    assert lp.value(x) == 2.0


def test_variables_dict():
    x = lp.LpVariable("x", 0, 3)
    y = lp.LpVariable("y", 0, None)
    prob = lp.LpProblem()
    prob += x + y <= 2
    prob += -4*x + y
    status = prob.solve()
    assert status == lp.LpStatusOptimal
    vd = prob.variablesDict()
    assert set(vd.keys()) == {'x', 'y'}
    assert vd['x'] is x
    assert vd['y'] is y


@pytest.mark.skipif(pulp, reason="PuLP")
def test_inplace():
    z = lp.LpVariable("z", 0, None)
    e = z + 0
    z0 = e
    with pytest.warns(UserWarning, match='in-place addition is not compatible with PuLP'):
        e += 2
    with pytest.warns(UserWarning, match='in-place subtraction is not compatible with PuLP'):
        e -= 1
    z1 = e
    prob = lp.LpProblem()
    prob += z
    status = prob.solve()
    assert status == lp.LpStatusOptimal
    assert lp.value(z0) == 0.0
    assert lp.value(z1) == 1.0
