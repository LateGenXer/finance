# Contributing

## State override

To avoid re-entering the desired parameters all the time, one can add a
`rtp/devel.py` file containing the desired parameters as a Python dictionary
named `state`, for example:

```python

state = {
    "dob_1": 1980,
    "sipp_1": 500000,
    "sipp_contrib_1": 0,
    "isa": 0,
    "gia": 0,
    "misc_contrib": 0,
    "retirement_year": 2045,
}

```

See the `default_state` dictionary in `pages/2_Retirement_Tax_Planner.py` for
the definitive reference of what state parameters are there.

## Linear Programming problem set-up

The main variables are:

- cash flows, i.e., withdrawals/top-ups across all accounts
- retirement income, when unspecificed

Equality constraints are:

- for every account:
  - $ balance_{year+1} = balance_{year} * growth\_factor + top\_ups - withdrawals $
- $incomings - outgoings = 0$, where:
  - incomings include:
    - account withdrawals
    - pensions
  - outgoings include:
    - account top-ups
    - income tax (pensions)
    - capital gain tax (growth in GIA)
    - net retirement income (post-retirement)

Inequality constraints are:

- balances must be positive or zero

Objective is:

- net retirement income (when unspecificed),
- or residual total wealth after 100 y.o. (when a target net retirement income is given.)

### Tax

Tax is a non-linear function of income/capital gains, but because it is a convex piecewise linear function, it works.

This is achived for income tax by defining a bounded variable for the income (or capital gain) in every tax band, and enforcing the sum of income bands to match the total income.  Because the model minimizes tax, it causes the lower tax bands to be filled first.

The exception is the 60% to 45% marginal income tax transition, which can't be modelled as it makes the relation not-convex.

Capital gain tax follow the same principle, using capital gain tax allowance and the income tax bands, with different tax rates.

Post-retirement, all income is assumed to be known.  Pre-retirement, base income is unknown, and only marginal income tax is considered.
