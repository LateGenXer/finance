## About

This is a retirement tax estimation / planning tool.
It uses _[linear
programming](https://en.wikipedia.org/wiki/Linear_programming)_ to determine
when and how much to withdraw from the different pots to fund retirement
spending, in order to make the money last as much as possible.

I initially wrote this for my own personal use, after running against limitations in other retirement planners such as [Guiide](https://guiide.co.uk/) and [MyNetwealth](https://my.netwealth.com/).  Specifically, for failing to take in consideration the particular circumstances of married couples and/or Lifetime Allowance.
The main driver was to better understand and estimate the impact of the Lifetime Allowance, in order to make better informed choices of savings products / tax wrappers.
I am not a financial or tax adviser.

## Disclaimers

* There is no guarantee of accuracy or completeness of the calculations.
  In fact, at this point, it is best to assume they will be wrong.

* This information does not constitute financial advice or tax advice.

* This tool is meant for efficient **tax planning**, not **tax avoidance**.
  Per [this HMRC's paper](https://www.gov.uk/government/publications/tackling-tax-avoidance-evasion-and-other-forms-of-non-compliance),
  _"**tax avoidance** involves bending the rules of the tax system to gain a tax
  advantage that Parliament never intended_",
  whereas
  _"**tax planning** involves using tax reliefs for the purpose for which they were
  intended -- it is not tax avoidance. For example, claiming relief on capital
  investment, saving in a tax-exempt ISA or saving for retirement by
  contributing to a pension scheme are all legitimate forms of tax planning."_
  In any doubt, get professional advice, or contact HMRC.

## Recent changes

* Avoid compounding CGT.
* Adjust income tax thresholds in real terms for being frozen in nominal terms until 2027/2028.
* Drop Portuguese NHR regime
* Stablize results by avoiding multiple optimal solutions.
* Allow to download/upload parameters.
* Allow to analyse how to best allocate a lump sump (experimental.)
* Allow contributing into pension after retirement (experimental.)
* [Abolition of Lifetime Allowance and increases to Pension Tax Limits](https://www.gov.uk/government/publications/abolition-of-lifetime-allowance-and-increases-to-pension-tax-limits/pension-tax-limits)
* Support single (unmarried) individuals.

## Features

* Joint calculation for married couples.
* Option to model Lifetime Allowance Charges, specifically [Benefit Crystallization Events](https://www.gov.uk/hmrc-internal-manuals/pensions-tax-manual/ptm088600) (BCEs) 1, 5A, 5B, and 6.

## Assumptions

This tool makes the following simplifying assumptions:
* all tax rates of 2023/2024 stay constant;
* all tax thresholds and allowances will follow inflation;
* that the CGT allowance is fully used on gains from GIA, while still avoiding [_bed & breakfast rule_](https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg13350).

## Limitations

* The tool enforces a fixed income in _real_ terms (that is, growing with inflation) until both retirees reach 100 year of age.

* Capital Gains Tax (CGT) is _overestimated_.  CGT rate depends on the marginal income tax rate.  This implies a non-linearity which can't be modeled as an ordinary linear programming problems.

* Equally, income tax after the Personal Allowance disappears (currently £125,140) is overestimated.  This is because the marginal income tax rate drops from 60% back to 45%, which can't be accurately modeled as a linear programming problem.

* It cannot model post-retirement scenarios.

* It cannot model defined benefits pension pots or annuities.

* It doesn't model mortality or the impact of different asset allocations on
  IHT.

## Known issues

* Sometimes the balances go slightly negative due to rounding errors, causing the stacked area charts to get weird.

## Questions

* **Can you please add support for XYZ?**
  Maybe.  If it's relatively straightforward and generally useful I can consider it.  But I have no intention to accommodate the long tail of subtly different personal circumstances out there.  At some point people will need to accept this is a generic tool, and that they need to work out their own calculations, or pay somebody to do it.

* **Can I have the source code?**
  Source code is available [here](https://github.com/LateGenXer/finance/tree/main/rtp).  The key technologies used for this tool are: [Python](https://www.python.org/), [SciPy](https://scipy.org/), [Pandas](https://pandas.pydata.org/) and [Streamlit](https://streamlit.io/).

* **How can I contact you?**
  Try [here](https://www.reddit.com/user/LateGenXer/) but no promise.
