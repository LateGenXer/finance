#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


"""
Wrapper around scipy.optimize.linprog with interface compatible to PuLP.

PuLP has an easy to use interface, but in practice results are not reliable nor results are fast.
"""


import numbers
import operator
import time

import numpy as np

from scipy.sparse import csr_array
from scipy.optimize import linprog


LpContinuous = 'Continuous'
LpInteger = 'Integer'
LpBinary = 'Binary'


class LpVariable:

    def __init__(self, name, lowBound=None, upBound=None, cat=LpContinuous):
        self.name = name
        self.lbound = lowBound
        self.ubound = upBound
        self.cat = cat
        self.index = None
        self.value = None

    def __str__(self):
        return self.name

    def __repr__(self):
        return f'<{self.name}>'

    def __add__(self, other):
        return LpAffineExpression(self) + other

    def __radd__(self, other):
        return LpAffineExpression(self) + other

    def __sub__(self, other):
        return LpAffineExpression(self) - other

    def __rsub__(self, other):
        return other - LpAffineExpression(self)

    def __neg__(self):
        return -LpAffineExpression(self)

    def __mul__(self, other):
        return LpAffineExpression(self) * other

    def __rmul__(self, other):
        return other * LpAffineExpression(self)

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        if isinstance(other, LpVariable):
            return self is other
        else:
            return LpAffineExpression(self) == other

    def __le__(self, other):
        return LpAffineExpression(self) <= other

    def __ge__(self, other):
        return LpAffineExpression(self) >= other


class LpAffineExpression:

    def __init__(self, e=None, constant=0):
        if e is None:
            assert constant == 0
            AX = {}
            b = constant
        elif isinstance(e, LpAffineExpression):
            assert constant == 0
            AX = e.AX.copy()
            b = e.b
        elif isinstance(e, LpVariable):
            assert constant == 0
            AX = {e: 1}
            b = constant
        elif isinstance(e, dict):
            for x, a in e.items():
                assert isinstance(x, LpVariable)
                assert isinstance(a, numbers.Number)
            assert isinstance(constant, numbers.Number)
            AX = e
            b = constant
        elif isinstance(e, numbers.Number):
            assert constant == 0
            AX = {}
            b = e

        assert isinstance(AX, dict)
        assert isinstance(b, numbers.Number)

        self.AX = AX
        self.b = b

    def __str__(self):
        return ' '.join([f'{a:+g}*{x.name}' for x, a in self.AX.items()] + [f'{self.b:+g}'])

    def _unary(self, op):
        AX = {x: op(a) for x, a in self.AX.items()}
        b = op(self.b)
        return LpAffineExpression(AX, b)

    def _binary(self, other, op):
        other = LpAffineExpression(other)
        AX = self.AX.copy()
        for x, a in other.AX.items():
            AX[x] = op(AX.get(x, 0), a)
        b = op(self.b, other.b)
        return LpAffineExpression(AX, b)

    def __add__(self, other):
        return self._binary(other, operator.add)

    def __radd__(self, other):
        return self + other

    def __sub__(self, other):
        return self._binary(other, operator.sub)

    def __rsub__(self, other):
        return other + -self

    def __neg__(self):
        return LpAffineExpression(0) - self

    def __mul__(self, other):
        assert isinstance(other, numbers.Number)
        if other == 0:
            return 0
        elif other == 1:
            return self
        else:
            return self._unary(lambda a: a * other)

    def __rmul__(self, other):
        return self * other

    def __eq__(self, other):
        return LpConstraint(self - other, EQ)

    def __le__(self, other):
        return LpConstraint(self - other, LE)

    def __ge__(self, other):
        return LpConstraint(self - other, GE)

    def value(self):
        res = self.b
        for x, a in self.AX.items():
            res += a*x.value
        return res


LE, GE, EQ = range(3)


class LpConstraint:

    def __init__(self, lhs, sense):
        self.lhs = lhs
        self.sense = sense

    def __str__(self):
        return '%s %s 0' % (self.lhs, ['<=', '>=', '=='][self.sense])


LpMinimize, LpMaximize = range(2)

LpStatusUndefined  = -3
LpStatusUnbounded  = -2
LpStatusInfeasible = -1
LpStatusNotSolved  =  0
LpStatusOptimal    =  1


class LpProblem:

    def __init__(self, name="NoName", sense=LpMinimize):
        self.constraints = []
        self.objective = None
        self.sense = sense
        self.vd = {}

    def addConstraint(self, constraint):
        assert isinstance(constraint, LpConstraint)
        self.constraints.append(constraint)

    def setObjective(self, objective):
        if isinstance(objective, LpVariable):
            objective = LpAffineExpression(objective)
        else:
            assert isinstance(objective, LpAffineExpression)
        assert self.objective is None
        self.objective = objective

    def __iadd__(self, other):
        if other is True:
            pass
        elif isinstance(other, LpConstraint):
            self.addConstraint(other)
        elif isinstance(other, LpVariable):
            self.setObjective(other)
        elif isinstance(other, LpAffineExpression):
            self.setObjective(other)
        else:
            raise ValueError(other)
        return self

    def checkDuplicateVars(self):
        pass

    def solve(self, solver=0):
        msg = solver != 0

        # https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linprog.html

        variables = {}
        n_ub = 0
        n_eq = 0

        dtype = np.float64

        A_ub_indptr = [0]
        A_ub_indices = []
        A_ub_data = []

        A_eq_indptr = [0]
        A_eq_indices = []
        A_eq_data = []

        b_ub = []
        b_eq = []

        for constraint in self.constraints:
            if msg:
                print(constraint)
            lhs = constraint.lhs
            if constraint.sense == EQ:
                n_eq += 1
            else:
                n_ub += 1
                if constraint.sense == GE:
                    lhs = -lhs

            rhs = -lhs.b

            indices = []
            data = []
            for x, a in lhs.AX.items():
                index = variables.setdefault(x, len(variables))
                indices.append(index)
                data.append(a)

            if constraint.sense == EQ:
                A_eq_indices.extend(indices)
                A_eq_data.extend(data)
                A_eq_indptr.append(len(A_eq_indices))
                b_eq.append(rhs)
            else:
                A_ub_indices.extend(indices)
                A_ub_data.extend(data)
                A_ub_indptr.append(len(A_ub_indices))
                b_ub.append(rhs)

        n = len(variables)

        A_ub = csr_array((A_ub_data, A_ub_indices, A_ub_indptr), shape=(n_ub, n), dtype=dtype)
        A_eq = csr_array((A_eq_data, A_eq_indices, A_eq_indptr), shape=(n_eq, n), dtype=dtype)
        b_ub = np.array(b_ub, dtype=dtype)
        b_eq = np.array(b_eq, dtype=dtype)

        bounds = [None] * n
        integrality = np.zeros(shape=(n,), dtype=np.uint8)
        for x, i in variables.items():
            if msg:
                print(f'{x.lbound} <= {x.name} <= {x.ubound}')
            bounds[i] = (x.lbound, x.ubound)
            integrality[i] = 0 if x.cat == LpContinuous else 1

        if msg:
            print(f'argmin({self.objective})')
        c = np.zeros(shape=(n,), dtype=dtype)
        for x, a in self.objective.AX.items():
            i = variables[x]
            c[i] = a
        if self.sense == LpMaximize:
            c = -c

        if np.amax(integrality) == 0:
            integrality = None

        method = 'highs'
        options = {}

        if msg:
            print(variables)
            print(f'A_ub: {A_ub.toarray()}')
            print(f'b_ub: {b_ub}')
            print(f'A_eq: {A_eq.toarray()}')
            print(f'b_eq: {b_eq}')
            print(f'c: {c}')
            print(f'bounds: {bounds}')
            print(f'integrality: {integrality}')

        st = time.perf_counter()
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds,
                      method=method, options=options, integrality=integrality)
        et = time.perf_counter()
        if msg:
            print(f'{et - st:.3f} seconds')

        if res.status == 0:
            for x, i in variables.items():
                x.value = res.x[i]
                assert x.name not in self.vd
                self.vd[x.name] = x
        else:
            print(res.message)

        return [
            # 0. Optimization proceeding nominally.
            LpStatusOptimal,
            # 1. Iteration limit reached.
            LpStatusNotSolved,
            # 2. Problem appears to be infeasible.
            LpStatusInfeasible,
            # 3. Problem appears to be unbounded.
            LpStatusUnbounded,
            # 4. Numerical difficulties encountered.
            LpStatusOptimal,
        ][res.status]
        return LpStatusOptimal

    def variablesDict(self):
        return self.vd


def value(x):
    if isinstance(x, numbers.Number):
        return x
    elif isinstance(x, LpAffineExpression):
        return x.value()
    else:
        assert isinstance(x, LpVariable)
        return x.value


def GLPK_CMD(msg=0):
    return msg

def PULP_CBC_CMD(msg=0):
    return msg

def COIN_CMD(msg=0):
    return msg

def listSolvers(onlyAvailable):
    return ['GLPK_CMD', 'PULP_CBC_CMD', 'COIN_CMD']
