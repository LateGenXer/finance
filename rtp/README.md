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

* Support single (unmarried) individuals.
* [Abolition of Lifetime Allowance and increases to Pension Tax Limits](https://www.gov.uk/government/publications/abolition-of-lifetime-allowance-and-increases-to-pension-tax-limits/pension-tax-limits)

## Features

* Joint calculation for married couples.
* Lifetime Allowance Charges modelling, specifically [Benefit Crystallization Events](https://www.gov.uk/hmrc-internal-manuals/pensions-tax-manual/ptm088600) (BCEs) 1, 5A, 5B, and 6.

## Assumptions

This tool makes the following simplifying assumptions:
* all tax rates of 2023/2024 stay constant;
* all tax thresholds and allowances will follow inflation;
* that the CGT allowance is fully used on gains from GIA, while still avoiding [_bed & breakfast rule_](https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg13350).

## Limitations

* The tool enforces a fixed income in _real_ terms (that is, growing with inflation) until both retirees reach 100 year of age.

* Capital Gains Tax (CGT) is _overestimated_.  CGT rate depends on the marginal income tax rate.  This implies a non-linearity which can't be modeled as an ordinary linear programming problems.

* Equally, income tax after the Personal Allowance disappears (currently £125,140) is overestimated.  This is because the marginal income tax rate drops from 60% back to 45%, which can't be accurately modeled as a linear programming problem.

* All pension contributions are assumed to cease at retirement.  Although there can be good and valid reasons to continue contributing into pension pots past retirement, it is difficult to safely/accurately model such contributions without running afoul of the [pension tax-free cash recycling rules](https://www.gov.uk/hmrc-internal-manuals/pensions-tax-manual/ptm133800).

* It cannot model post-retirement scenarios.

* It cannot model defined benefits pension pots or annuities.

* It doesn't model mortality or the impact of different asset allocations on
  IHT.

## Known issues

* When there are multiple optimal solutions the solution found is chosen
  somewhat arbitrarily, almost randomly.  For example, when two pots are equal
  from a tax perspective, or when withdrawing money sooner or later makes no
  net difference.

* Sometimes the balances go slightly negative due to rounding errors, causing the stacked area charts to get weird.

## Questions

* **Can you please add support for XYZ?**  Maybe.  If it's relatively straightforward and generally useful I can consider it.  But I have no intention to accommodate the long tail of subtly different personal circumstances out there.  At some point people will need to accept this is a generic tool, and that they need to work out their own calculations, or pay somebody to do it.

* **Will you release the source code?**  I'm still mulling over.  FWIW, the key technologies used for this tool were: [Python](https://www.python.org/), [PuLP](https://coin-or.github.io/pulp/), [Pandas](https://pandas.pydata.org/) and [Streamlit](https://streamlit.io/).

* **How can I contact you?**  Try https://www.reddit.com/user/LateGenXer but no promise.
