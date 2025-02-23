#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


"""
Wrapper around scipy.optimize.linprog with similar interface to PuLP.

"""


import numbers
import operator
import time

import numpy as np

from scipy.sparse import csr_array  # type: ignore[import-untyped]
from scipy.optimize import linprog  # type: ignore[import-untyped]


class LpVariable:

    def __init__(self, name, lbound=None, ubound=None):
        self.name = name
        self._lbound = lbound
        self._ubound = ubound
        self._index = None
        self._value = None

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    def __add__(self, other):
        return toAffine(self) + other

    def __radd__(self, other):
        return toAffine(self) + other

    def __sub__(self, other):
        return toAffine(self) - other

    def __rsub__(self, other):
        return other - toAffine(self)

    def __neg__(self):
        return -toAffine(self)

    def __mul__(self, other):
        return toAffine(self) * other

    def __rmul__(self, other):
        return other * toAffine(self)

    def __truediv__(self, other):
        return toAffine(self) / other

    def __hash__(self):
        return id(self)

    def __eq__(self, other):
        if isinstance(other, LpVariable):
            return self is other
        else:
            return toAffine(self) == other

    def __le__(self, other):
        return toAffine(self) <= other

    def __ge__(self, other):
        return toAffine(self) >= other

    def value(self):
        return self._value


def toAffine(x):
    if isinstance(x, LpAffineExpression):
        return x
    if isinstance(x, LpVariable):
        return LpAffineExpression({x: 1.0}, 0.0)
    if isinstance(x, numbers.Number):
        return LpAffineExpression({}, x)
    raise ValueError(x)


class LpAffineExpression:

    def __init__(self, AX, b):
        assert isinstance(AX, dict)
        for x, a in AX.items():
            assert isinstance(x, LpVariable)
            assert isinstance(a, numbers.Number)
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
        other = toAffine(other)
        AX = self.AX.copy()
        for x, a in other.AX.items():
            AX[x] = op(AX.get(x, 0.0), a)
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
        return toAffine(0.0) - self

    def __mul__(self, other):
        assert isinstance(other, numbers.Number)
        if other == 0.0:
            return 0.0
        elif other == 1.0:
            return self
        else:
            return self._unary(lambda a: a * other)

    def __rmul__(self, other):
        return self * other

    def __truediv__(self, other):
        assert isinstance(other, numbers.Number)
        if other == 1.0:
            return self
        else:
            return self._unary(lambda a: a / other)

    def __eq__(self, other):
        return LpConstraint(self - other, LpConstraintEQ)

    def __le__(self, other):
        return LpConstraint(self - other, LpConstraintLE)

    def __ge__(self, other):
        return LpConstraint(self - other, LpConstraintGE)

    def value(self):
        res = self.b
        for x, a in self.AX.items():
            res += a*x._value
        return res


LpConstraintLE, LpConstraintGE, LpConstraintEQ = range(3)


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


_status_map = [
    LpStatusOptimal,    # 0. Optimization proceeding nominally.
    LpStatusNotSolved,  # 1. Iteration limit reached.
    LpStatusInfeasible, # 2. Problem appears to be infeasible.
    LpStatusUnbounded,  # 3. Problem appears to be unbounded.
    LpStatusUndefined,  # 4. Numerical difficulties encountered.
]


class LpProblem:

    def __init__(self, name=None, sense=LpMinimize):
        self.constraints = []
        self.objective = None
        assert sense == LpMinimize
        self.vd = {}

    def addConstraint(self, constraint):
        assert isinstance(constraint, LpConstraint)
        self.constraints.append(constraint)

    def setObjective(self, objective):
        if isinstance(objective, LpVariable):
            objective = toAffine(objective)
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

        variables: dict[LpVariable, int] = {}
        n_ub = 0
        n_eq = 0

        dtype = np.float64

        A_ub_indptr = [0]
        A_ub_indices = []
        A_ub_data = []

        A_eq_indptr = [0]
        A_eq_indices = []
        A_eq_data = []

        b_ub_data = []
        b_eq_data = []

        for constraint in self.constraints:
            if msg:
                print(constraint)
            lhs = constraint.lhs
            if constraint.sense == LpConstraintEQ:
                n_eq += 1
            else:
                n_ub += 1
                if constraint.sense == LpConstraintGE:
                    lhs = -lhs

            rhs = -lhs.b

            indices = []
            data = []
            for x, a in lhs.AX.items():
                index = variables.setdefault(x, len(variables))
                indices.append(index)
                data.append(a)

            if constraint.sense == LpConstraintEQ:
                A_eq_indices.extend(indices)
                A_eq_data.extend(data)
                A_eq_indptr.append(len(A_eq_indices))
                b_eq_data.append(rhs)
            else:
                A_ub_indices.extend(indices)
                A_ub_data.extend(data)
                A_ub_indptr.append(len(A_ub_indices))
                b_ub_data.append(rhs)

        n = len(variables)

        A_ub = csr_array((A_ub_data, A_ub_indices, A_ub_indptr), shape=(n_ub, n), dtype=dtype)
        A_eq = csr_array((A_eq_data, A_eq_indices, A_eq_indptr), shape=(n_eq, n), dtype=dtype)
        b_ub = np.array(b_ub_data, dtype=dtype)
        b_eq = np.array(b_eq_data, dtype=dtype)

        bounds:list[tuple[float|int|None, float|int|None]] = [(None, None)] * n
        for x, i in variables.items():
            if msg:
                print(f'{x._lbound} <= {x.name} <= {x._ubound}')
            bounds[i] = (x._lbound, x._ubound)

        assert self.objective is not None
        if msg:
            print(f'argmin({self.objective})')
        c = np.zeros(shape=(n,), dtype=dtype)
        for x, a in self.objective.AX.items():
            i = variables[x]
            c[i] = a

        if msg:
            print(variables)
            print(f'A_ub: {A_ub.toarray()}')
            print(f'b_ub: {b_ub}')
            print(f'A_eq: {A_eq.toarray()}')
            print(f'b_eq: {b_eq}')
            print(f'c: {c}')
            print(f'bounds: {bounds}')

        st = time.perf_counter()
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds,
                      method='highs-ds', options={})
        et = time.perf_counter()
        if msg:
            print(f'{et - st:.3f} seconds')

        if res.status == 0:
            for x, i in variables.items():
                x._value = res.x[i]
                assert x.name not in self.vd
                self.vd[x.name] = x
        else:
            print(res.message)

        return _status_map[res.status]

    def variablesDict(self):
        return self.vd


def value(x):
    if isinstance(x, numbers.Number):
        return x
    else:
        assert isinstance(x, (LpVariable, LpAffineExpression))
        return x.value()


def GLPK_CMD(msg=0):
    return msg


def PULP_CBC_CMD(msg=0):
    return msg


def COIN_CMD(msg=0):
    return msg


def listSolvers(onlyAvailable):
    return ['GLPK_CMD', 'PULP_CBC_CMD', 'COIN_CMD']
