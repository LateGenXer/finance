#!/usr/bin/env python3
#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#

import os
import sys
import datetime

import jax.scipy.optimize
import jax.nn

import jax.numpy as jnp
import numpy as onp

import pandas as pd

from rtp import uk

from data.mortality import mortality


# TODO: Use https://jax.readthedocs.io/en/latest/persistent_compilation_cache.html ?


float32_max = onp.finfo(onp.float32).max


def inv_sigmoid(x):
    x = onp.asarray(x)
    # https://stackoverflow.com/a/77031201
    return onp.log(x) - onp.log(1 - x)


def utility(c, n=1.5):
    # Constant relative risk aversion utility function, as per
    # https://en.wikipedia.org/wiki/Isoelastic_utility
    # but simplified -- without affine transformation.
    if n == 0.0:
        return c
    elif n == 1.0:
        return jnp.log(c)
    elif n == 1.5:
        return -jnp.reciprocal(jnp.sqrt(c))
    else:
        return c ** (1.0 - n) / (1.0 - n)


def consumption(w, P, r, N):
    assert len(w) + 1 == N

    w = jnp.concatenate((w, jnp.array([1.0])))

    Wc = 1 - w
    Wc *= 1 + r
    Wc = jnp.cumprod(Wc)

    p1 = P*Wc
    p0 = jnp.concatenate((jnp.array([P]), p1[:-1]))

    c = p0*w

    return c


def expected_utility(w, P, r, N, px):

    assert len(w) + 1 == N

    w = jax.nn.sigmoid(w)

    c = consumption(w, P, r, N)

    u = utility(c)

    #return -jnp.sum(u)
    return -jnp.dot(u, px)


# https://jax.readthedocs.io/en/latest/_autosummary/jax.scipy.optimize.OptimizeResults.html
status_to_msg = {
    0: 'converged (nominal)',
    1: 'max BFGS iters reached',
    3: 'zoom failed',
    4: 'saddle point reached',
    5: 'max line search iters reached',
    -1: 'undefined',
}


def model(P, cur_age, r):

    cur_year = datetime.datetime.utcnow().year
    yob = cur_year - cur_age
    gender = 'female' # longer life expectancy
    #gender = 'male'

    N = 101 - cur_age
    print(N)

    ages = list(range(cur_age, 101))

    qx = onp.array([mortality(yob + age, age, gender, basis='cohort') for age in ages], dtype=onp.float64)
    px = onp.cumprod(1 - qx)

    #px *= 0.96 ** onp.arange(N)

    print("px", px)

    assert len(qx) == N

    w0 = 1.0 / (N - onp.arange(N))
    #w0 = onp.full([N], 0.5/N)
    w0 = w0[:-1]
    print("w0", w0)

    w0 = inv_sigmoid(w0)
    w0 = w0.astype(onp.float32)
    w0 = onp.minimum(w0, float32_max)
    print("inv_sigmoid(w0)", w0)

    print()

    # Optimize through JAX's automatic differentiation and  gradient descent algorithms
    P0 = 100
    if int(os.environ.get('GRAD', '0')) == 0:
        # https://github.com/google/jax/blob/main/jax/_src/scipy/optimize/bfgs.py
        options = {
            'gtol': 1e-3,
            'line_search_maxiter': 256,
            'maxiter': N*256,
        }
        result = jax.scipy.optimize.minimize(expected_utility, w0, (P0, r, N, px), method="BFGS", options=options)
        if not result.success:
            status = int(result.status)
            raise ValueError(status_to_msg.get(status, repr(status)))
        w = result.x
    else:
        maxiter = 1024
        initial_learning_rate = 2**-1
        decay = initial_learning_rate / maxiter
        fun = lambda w: expected_utility(w, P0, r, N, px)
        grad_X = jax.value_and_grad(fun)
        grad_X = jax.jit(grad_X)
        w = w0
        for i in range(maxiter):
            wp = w
            u, dudw = grad_X(w)
            learning_rate = initial_learning_rate / (1 + decay*i)
            w = w - learning_rate * dudw
            e = float(onp.max(onp.abs(jax.nn.sigmoid(w) - jax.nn.sigmoid(wp))))
            print(u, e)
            if e <= 1e-4:
                break
        print("error",e)

    n = N - onp.arange(N)

    # https://www.bogleheads.org/wiki/Amortization_based_withdrawal_formulas#Amortization_based_withdrawal_formula
    we = r / (1 - 1/(1 + r)**n) / (1 + r)
    #we = 1 / (N - onp.arange(N))
    we = we[:-1]

    w_ = onp.asarray(jax.nn.sigmoid(w))

    Ue = expected_utility(inv_sigmoid(we), P, r, N, px)
    U  = expected_utility(inv_sigmoid(w_), P, r, N, px)

    c  = onp.asarray(consumption(w_, P, r, N))
    ce = onp.asarray(consumption(we, P, r, N))

    w_ = jnp.concatenate((w_, jnp.array([1.0])))
    we = jnp.concatenate((we, jnp.array([1.0])))

    df = pd.DataFrame(zip(ages, w_, c, we, ce), columns=['Age', 'W', 'C', 'Wref', 'Cref'])
    print(df.to_string(
        index=False,
        justify='right',
        float_format='£{:,.0f}'.format,
        formatters = {
            'W': '{:.2%}'.format,
            'Wref': '{:.2%}'.format,
        }
    ))

    with jnp.printoptions(precision=3, suppress=True):
        print("sw0", w0)
        print("sw ", w)
        print("Ue", Ue)
        print("U ", U)


if __name__ == '__main__':
    model(P = 1e5, cur_age=65, r = .03)
