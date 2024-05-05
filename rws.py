#!/usr/bin/env python3
#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import sys

import jax.numpy as jnp
from jax import grad
import jax.scipy.optimize
import jax.nn

import numpy as onp


float_max = 3.402823E+38


def inv_sigmoid(x):
    # https://stackoverflow.com/a/77031201
    return onp.log(x) - jnp.log(1 - x)


def utility(c, n=1.0):
    # Constant relative risk aversion utility function, as per
    # https://en.wikipedia.org/wiki/Isoelastic_utility
    # but simplified -- without affine transformation.
    if n == 0.0:
        return c
    elif n == 0.5:
        return jnp.sqrt(c)
    elif n == 1.0:
        return jnp.log(c)
    elif n == 1.5:
        return -jnp.reciprocal(jnp.sqrt(c))
    else:
        return c ** (1.0 - n)


def consumption(W, P, r, N):
    assert len(W) + 1 == N

    W = jnp.concatenate((W, jnp.array([1.0])))

    Wc = 1 - W
    Wc *= 1 + r
    Wc = jnp.cumprod(Wc)

    p1 = P*Wc
    p0 = jnp.concatenate((jnp.array([P]), p1[:-1]))

    c = p0*W

    return c


def expected_utility(W, P, r, N):

    assert len(W) + 1 == N

    W = jax.nn.sigmoid(W)

    c = consumption(W, P, r, N)

    u = utility(c)

    return -jnp.sum(u)


# https://jax.readthedocs.io/en/latest/_autosummary/jax.scipy.optimize.OptimizeResults.html
status_to_msg = {
    0: 'converged (nominal)',
    1: 'max BFGS iters reached',
    3: 'zoom failed',
    4: 'saddle point reached',
    5: 'max line search iters reached',
    -1: 'undefined',
}


def model(P, N, r):

    w0 = 1.0 / (N - onp.arange(N))
    w0 = w0[:-1]
    print(w0)

    w0 = inv_sigmoid(w0)
    print(w0)
    w0 = jnp.minimum(w0, float_max)
    print(w0)
    print("<<<<<<<<")
    print(expected_utility(w0, P, r, N))
    print(">>>>>>>>")

    print()

    # Optimize through JAX's automatic differentiation and  gradient descent algorithms
    result = jax.scipy.optimize.minimize(expected_utility, w0, (P, r, N), method="BFGS", tol=1e-1)


    if not result.success:
        status = int(result.status)
        raise ValueError(status_to_msg.get(status, repr(status)))


    n = N - onp.arange(N)

    # https://www.bogleheads.org/wiki/Amortization_based_withdrawal_formulas#Amortization_based_withdrawal_formula
    we = r / (1 - 1/(1 + r)**n) / (1 + r)
    #we = 1 / (N - onp.arange(N))
    we = we[:-1]

    with jnp.printoptions(precision=3, suppress=True):
        print("sw0", w0)
        print("sw ", result.x)
        w = jax.nn.sigmoid(result.x)
        print("we", we)
        print("w ", w)
        print("c ", consumption(w, P, r, N))
        print("Ue", expected_utility(we, P, r, N))
        print("U ", expected_utility(w, P, r, N))


if __name__ == '__main__':
    model(P = 100000, N = 100 - 65, r = .03)
