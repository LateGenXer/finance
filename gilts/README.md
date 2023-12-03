## About

This is a tool for building a bond ladder of UK government bonds, commonly referred as _gilts_.

It uses _[linear
programming](https://en.wikipedia.org/wiki/Linear_programming)_ to determine which gilts to buy in order to meet the desired future consuption with the minimum upfront cost, also taking in consideration the income tax due.

I initially wrote this for my own personal education and simulations on gilts, mostly due to the lack of short term index-linked gilt funds, and the relative unpredictability of bond funds cash flows in general.

I am not a financial or tax adviser.

## Disclaimers

* There is no guarantee of accuracy or completeness of the calculations.
  In fact, at this point, it is best to assume they will be wrong.

* This information does not constitute financial advice or tax advice.

## Recent changes

- Allow to set a start date in the future.
- Automatically download latest issued gilts from DMO's website.
- Always present UK local time.

## Features

* Withdrawals can be done on a yearly or monthly basis.
* Calculation results can be downloaded as an Excel spreadsheet.

## Assumptions

* It uses an hard-coded constant inflation rate of 3% for predicting index-linked gilts cash-flows, and depreciation of cash balances.  This is not a bad estimate on the long term (at least as long the BoE's 2% inflation target mandate remains), but can be quite poor in

## Known issues

* For start dates in the future, early coupons are not reinvested.
* The tool does not yet consider the possibility of selling gilts before maturity, which might be advantageous, especially with index-linked gilts and/or high income marginal tax rates, as good gilts became fewer and further apart.
* The tool does not consider BoE's yield or inflation curves.
* It does not take special care with index-linked gilts whose redemption value is know (due to the indexation lag) and therefore are more akin to convential gilts.

## Questions

* **Can I have the source code?**  Source code is available [here](https://github.com/LateGenXer/finance/).  The key technologies used for this tool are: [Python](https://www.python.org/), [PuLP](https://coin-or.github.io/pulp/), [Pandas](https://pandas.pydata.org/) and [Streamlit](https://streamlit.io/).

* **How can I contact you?**  Try [here](https://github.com/LateGenXer/finance/discussions) but no promise.
