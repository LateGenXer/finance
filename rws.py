#!/usr/bin/env python3
#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#

import os
import sys
import datetime
import math
import typing

import jax.scipy.optimize
import jax.nn

import jax.numpy as jnp
import numpy as onp

import scipy.stats

import pandas as pd

from numpy.typing import ArrayLike

from rtp import uk

from data.mortality import mortality
from data.boe import yield_curves


cur_year = datetime.datetime.utcnow().year

yc = yield_curves()


def annuity_rate(cur_age, kind, gender='unisex'):
    yob = cur_year - cur_age

    basis = 'cohort' if gender == 'unisex' else 'period'
    basis = 'cohort'

    ages = list(range(cur_age, 121))

    p = 1
    npv = 0
    s = yc[f'{kind}_Spot']
    for age in ages:
        years = age - cur_age
        index = float(years)
        index = max(index,  0.5)
        index = min(index, 40.0)
        rate = s[index]
        if False:
            print(f'{years:2d}  {r:6.2%}  {p:7.2%}')
        npv += p * (1 + rate)**-years
        qx = mortality(yob + age, age, gender=gender, basis=basis)
        p *= 1 - qx

    ar = 1.0/npv

    return ar


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


class Params(typing.NamedTuple):

    P: float
    R: ArrayLike
    N: int
    px: ArrayLike
    ar: float


def consumption(w, aw, cr, params):
    P = params.P
    R = params.R
    ar = params.ar

    R = (R - 1) * (1 - cr) + 1

    Wc = (1 - w) * R
    Wc = jnp.cumprod(Wc, axis=-1)

    p1 = Wc

    M = len(R)

    p0 = jnp.concatenate((jnp.full([M, 1], 1), p1[:, :-1]), axis=-1)

    c = p0*w

    if params.ar:
        c = c * (1 - aw) + aw * params.ar

    c = c * P

    return c


def expected_utility(w, aw, cr, params):
    px = params.px

    c = consumption(w, aw, cr, params)

    u = utility(c)

    #u = jnp.sum(u, axis=-1)
    u = jnp.dot(u, px)
    u *= 1/onp.sum(px)

    u = -jnp.mean(u)

    return u


def loss(x, params):
    N = params.N

    print(len(x), N)
    assert len(x) == (N - 1)*2 + 1

    w, aw, cr = unpack(x)
    assert len(w) == N

    return expected_utility(w, aw, cr, params)



# https://jax.readthedocs.io/en/latest/_autosummary/jax.scipy.optimize.OptimizeResults.html
status_to_msg = {
    0: 'converged (nominal)',
    1: 'max BFGS iters reached',
    3: 'zoom failed',
    4: 'saddle point reached',
    5: 'max line search iters reached',
    -1: 'undefined',
}


def constant_returns(r, N):
    return onp.full((1, N), 1.0 + r)


def black_scholes_sample(mu, sigma, N, M=1):
    W = scipy.stats.norm.rvs(size = (M, N))
    R = onp.exp((mu - sigma * sigma * 0.5) + sigma*W)
    return R


def pack(w, aw, cr):
    x = onp.concatenate((w[:-1], cr[:-1], onp.array([aw])))
    x = inv_sigmoid(x)
    x = x.astype(onp.float32)
    x = onp.minimum(x, float32_max)
    return x


def unpack(x):
    N = (len(x) - 1) // 2
    x = jax.nn.sigmoid(x)
    w  = jnp.concatenate((x[:N],    jnp.array([1.0], dtype=x.dtype)))
    cr = jnp.concatenate((x[N:2*N], jnp.array([1.0], dtype=x.dtype)))
    aw = x[-1]
    return w, aw, cr


def model(P, cur_age, r):

    yob = cur_year - cur_age
    gender = 'female' # longer life expectancy
    #gender = 'male'
    gender = 'unisex'

    ar = annuity_rate(cur_age, 'Real')
    if int(os.environ.get('ANNUITY', '1')) == 0:
        ar *= 0.0
    print(f'Annuity Rate: £{100000*ar:,.2f} / £100k')

    # XXX ONS cohort tables have a high survivorship
    basis = 'cohort' if gender == 'unisex' else 'period'

    max_age = 120 if gender == 'unisex' else 101

    N = max_age - cur_age + 1
    print(N)

    ages = list(range(cur_age, max_age + 1))

    qx = onp.array([mortality(yob + age, age, gender, basis) for age in ages], dtype=onp.float64)
    px = onp.cumprod(1 - qx)

    print("px", px)

    assert len(qx) == N

    M = 1024

    if False:
        R = constant_returns(r, N)
    else:
        mu = math.log(1.0 + r)
        sigma = math.log(1.0 + r*4)
        r = 4.33e-2
        mu = math.log(1.0 + r)
        sigma = math.log(1.0 + 16.08e-2)
        R = black_scholes_sample(mu, sigma, N, M)
    #Rm = onp.exp(onp.mean(onp.log(R), axis=0)) - 1
    Rm = onp.median(R, axis=0) - 1
    print(Rm)
    #sys.exit()


    params = Params(P=100, R=R, N=N, px=px, ar=ar)

    w0 = 1.0 / (N - onp.arange(N))
    aw0 = 0.5
    cr0 = onp.full([N], 5/N)
    x0 = pack(w0, aw0, cr0)

    print("C0", onp.mean(consumption(w0, aw0, cr0, params), axis=0))
    U0 = expected_utility(w0, aw0, cr0, params)
    print("U0", U0)
    print()

    # Optimize through JAX's automatic differentiation and  gradient descent algorithms
    if int(os.environ.get('GRAD', '1')) == 0:
        # https://github.com/google/jax/blob/main/jax/_src/scipy/optimize/bfgs.py
        options = {
            'gtol': 1e-3,
            'line_search_maxiter': 256,
            'maxiter': N*256,
        }
        result = jax.scipy.optimize.minimize(loss, x0, (params,), method="BFGS", options=options)
        if not result.success:
            status = int(result.status)
            raise ValueError(status_to_msg.get(status, repr(status)))
        w = result.x
    else:
        maxiter = 1024 * 4
        initial_learning_rate = 2**-1
        decay = initial_learning_rate / maxiter
        fun = lambda x: loss(x, params)
        grad_X = jax.value_and_grad(fun)
        grad_X = jax.jit(grad_X)
        x = x0
        xsp = onp.asarray(jax.nn.sigmoid(x))
        for i in range(maxiter):
            u, dudx = grad_X(x)
            learning_rate = initial_learning_rate / (1 + decay*i)
            x = x - learning_rate * dudx
            xs = onp.asarray(jax.nn.sigmoid(x))
            e = onp.max(onp.abs(xs - xsp))
            print(f'U = {u:8f}, e = {e:.6e}')
            if e <= 1e-4:
                break
            xsp = xs
        print("error",e)
        if e > 1e-4:
            raise ValueError(e)

    params = Params(P=P, R=R, N=N, px=px, ar=ar)

    # https://www.bogleheads.org/wiki/Amortization_based_withdrawal_formulas#Amortization_based_withdrawal_formula
    n = N - onp.arange(N)
    we = r / (1 - 1/(1 + r)**n) / (1 + r)
    #we = onp.flip(1/onp.cumsum(1/onp.cumprod(onp.flip(1 + Rm))))

    w, aw, cr = unpack(x)
    w = onp.asarray(w)
    aw = float(aw)

    print(f'Annuity allocation: {aw:.2%} -> £{P*aw*ar:,.2f}/yr')

    awe = 0
    cre = onp.full([N], 0.0)

    Ue = expected_utility(we, awe, cre, params)
    U  = expected_utility(w,   aw,  cr, params)

    C  = onp.asarray(consumption(w, aw, cr, params))[:,-1]
    print(C)
    if False:
        df = pd.DataFrame(C)
        df.hist(bins=onp.arange(0, 10000, 100), alpha=0.5)
        #df.plot.kde()
        import matplotlib.pyplot as plt
        plt.show()

    _c = onp.asarray(consumption(w,   aw,  cr, params))
    c05, c50, c95 = onp.percentile(_c, [5, 50, 95], axis=0)
    ce = onp.median(onp.asarray(consumption(we, awe, cre, params)), axis=0)

    df = pd.DataFrame(zip(ages, w,  cr, c05, c50, c95, we, ce, Rm, px), columns=['Age', 'W', 'CashRatio', 'C(05%)', 'C(50%)', 'C(90%)', 'Wref', 'Cref', 'Ravg', 'Survival'])
    print(df.to_string(
        index=False,
        justify='right',
        float_format='£{:,.0f}'.format,
        formatters = {
            'W': '{:.2%}'.format,
            'CashRatio': '{:.2%}'.format,
            'Wref': '{:.2%}'.format,
            'Ravg': '{:+.2%}'.format,
            'Survival': '{:+.2%}'.format,
        }
    ))

    with jnp.printoptions(precision=3, suppress=True):
        print("Ue", Ue)
        print("U ", U)


if __name__ == '__main__':
    model(P = 1e6, cur_age=65, r = .03)
