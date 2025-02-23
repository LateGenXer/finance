#
# Copyright (c) 2023-2025 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


"""
Wrapper around scipy.optimize.linprog with similar interface to PuLP.

"""


from __future__ import annotations

import operator
import time
import warnings
import sys

import numpy as np

from scipy.sparse import csr_array  # type: ignore[import-untyped]
from scipy.optimize import linprog  # type: ignore[import-untyped]


class LpVariable:

    def __init__(self, name, lbound=None, ubound=None):
        self.name = name
        self._lbound = lbound
        self._ubound = ubound
        self._index:int|None = None
        self._value:float|None = None

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    def _affine(self):
        return LpAffineExpression({self: 1.0}, 0.0)

    def __add__(self, other):
        return self._affine() + other

    def __radd__(self, other):
        return self._affine() + other

    def __sub__(self, other):
        return self._affine() - other

    def __rsub__(self, other):
        return other - self._affine()

    def __neg__(self):
        return LpAffineExpression({self: -1.0}, 0.0)

    def __mul__(self, other):
        return self._affine() * other

    def __rmul__(self, other):
        return other * self._affine()

    def __truediv__(self, other):
        return self._affine() / other

    def __hash__(self) -> int:
        return id(self)

    def __eq__(self, other):
        if isinstance(other, LpVariable):
            return self is other
        else:
            return self._affine() == other

    def __le__(self, other):
        return self._affine() <= other

    def __ge__(self, other):
        return self._affine() >= other

    def value(self) -> float:
        assert self._value is not None
        return self._value


def toAffine(x) -> LpAffineExpression:
    if isinstance(x, LpAffineExpression):
        return x
    if isinstance(x, LpVariable):
        return LpAffineExpression({x: 1.0}, 0.0)
    if isinstance(x, (float, int)):
        return LpAffineExpression({}, x)
    raise TypeError(x)


class LpAffineExpression:

    def __init__(self, AX, b):
        assert isinstance(AX, dict)
        for x, a in AX.items():
            assert isinstance(x, LpVariable)
            assert isinstance(a, (float, int))
        assert isinstance(b, (float, int))
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

    def __iadd__(self, other):
        warnings.warn('in-place addition is not compatible with PuLP', stacklevel=2)
        return self + other

    def __add__(self, other):
        return self._binary(other, operator.add)

    def __radd__(self, other):
        return self + other

    def __isub__(self, other):
        warnings.warn('in-place subtraction is not compatible with PuLP', stacklevel=2)
        return self - other

    def __sub__(self, other):
        return self._binary(other, operator.sub)

    def __rsub__(self, other):
        return other + -self

    def __neg__(self):
        return toAffine(0.0) - self

    def __mul__(self, other):
        assert isinstance(other, (float, int))
        if other == 0.0:
            return 0.0
        elif other == 1.0:
            return self
        else:
            return self._unary(lambda a: a * other)

    def __rmul__(self, other):
        return self * other

    def __truediv__(self, other):
        assert isinstance(other, (float, int))
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
            assert x._value is not None
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
            raise TypeError(other)
        return self

    def checkDuplicateVars(self):
        variables = set(self._iter_variables())
        unique = set()
        duplicates = set()
        for x in variables:
            if x.name in unique:
                duplicates.add(x.name)
            else:
                unique.add(x.name)
        if duplicates:
            raise ValueError(duplicates)

    def _iter_affines(self):
        for constraint in self.constraints:
            yield constraint.lhs
        assert self.objective is not None
        yield self.objective

    def _iter_variables(self):
        for e in self._iter_affines():
            for x in e.AX:
                yield x

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
                sys.stderr.write(f'{constraint}\n')
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

        assert self.objective is not None
        for x, a in self.objective.AX.items():
            variables.setdefault(x, len(variables))

        n = len(variables)

        A_ub = csr_array((A_ub_data, A_ub_indices, A_ub_indptr), shape=(n_ub, n), dtype=dtype)
        A_eq = csr_array((A_eq_data, A_eq_indices, A_eq_indptr), shape=(n_eq, n), dtype=dtype)
        b_ub = np.array(b_ub_data, dtype=dtype)
        b_eq = np.array(b_eq_data, dtype=dtype)

        bounds:list[tuple[float|int|None, float|int|None]] = [(None, None)] * n
        for x, i in variables.items():
            if msg:
                sys.stderr.write(f'{x._lbound} <= {x.name} <= {x._ubound}\n')
            bounds[i] = (x._lbound, x._ubound)

        if msg:
            sys.stderr.write(f'argmin({self.objective})\n')
        c = np.zeros(shape=(n,), dtype=dtype)
        for x, a in self.objective.AX.items():
            i = variables[x]
            c[i] = a

        if msg:
            sys.stderr.write(' '.join([str(v) for v in variables]) + '\n')
            sys.stderr.write(f'A_ub: {A_ub.toarray()}\n')
            sys.stderr.write(f'b_ub: {b_ub}\n')
            sys.stderr.write(f'A_eq: {A_eq.toarray()}\n')
            sys.stderr.write(f'b_eq: {b_eq}\n')
            sys.stderr.write(f'c: {c}\n')
            sys.stderr.write(f'bounds: {bounds}\n')

        st = time.perf_counter()
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds,
                      method='highs-ds', options={})
        et = time.perf_counter()
        if msg:
            sys.stderr.write(f'{et - st:.3f} seconds\n')

        if res.status == 0:
            for x, i in variables.items():
                x._value = res.x[i]
                assert x.name not in self.vd
                self.vd[x.name] = x
        else:
            sys.stderr.write(res.message + '\n')

        return _status_map[res.status]

    def variablesDict(self):
        return self.vd


def value(x):
    if isinstance(x, (float, int)):
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


def listSolvers(onlyAvailable=False):
    return ['GLPK_CMD', 'PULP_CBC_CMD', 'COIN_CMD']
