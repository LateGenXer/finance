## About

This is a tool for building a bond ladder of UK government bonds, commonly referred as [_gilts_](https://www.dmo.gov.uk/responsibilities/gilt-market/about-gilts/).

It uses _[linear
programming](https://en.wikipedia.org/wiki/Linear_programming)_ to determine which gilts to buy in order to meet the desired future consuption with the minimum upfront cost.

I initially wrote this for my own personal education and simulations on gilts, mostly due to the lack of short term index-linked gilt funds, and the relative unpredictability of bond funds cash flows in general.

## Disclaimers

* I am not a financial or tax adviser.

* There is no guarantee of accuracy or completeness of the calculations.
  In fact, at this point, it is best to assume they will be wrong.

* This information does not constitute financial advice or tax advice.

* In any doubt, get professional advice.

## Recent changes

- Treat index-linked gilts whose redemption value is known as conventional gilts.
- Allow to set a start date in the future.
- Automatically download latest issued gilts from DMO's website.
- Always present UK local time.

## Features

* It can optimize tax, taking advantage of the fact that coupon payments are subject to income tax but that gilt sales and redemptions are not subject to capital gains tax.
* Withdrawals can be done on a yearly or monthly basis.
* Calculation results can be downloaded as an Excel spreadsheet.

## Assumptions

* It assumes a constant inflation rate of 3% for predicting index-linked gilts' future cash-flows, and the depreciation of cash balances in real terms.  This is not a bad estimate on the long term (at least as long the BoE's 2% inflation target mandate remains), but can be in the short term.

## Known issues

* For start dates in the future, early coupons are not reinvested.
* The tool does not yet consider the possibility of selling gilts before maturity, which might be advantageous, especially with index-linked gilts and/or high income marginal tax rates, as low coupon gilts are fewer and further apart.
* The tool does not consider BoE's yield or inflation curves.

## Questions

* **What's the clean/dirty price?**
  Read the [Debt Management Office's Glossary](https://www.dmo.gov.uk/help/glossary/) for a description of these and other key concepts.
  _Clean price_ is the price normally quoted for nominal £100, it doesn't include the accrued interest (or any inflation adjustment) therefore it's relatively stable from day to day, only varying as market expectations of the future vary (interest rates, inflation, economy.)
  _Dirty price_ is the price one will actually pay per nominal £100, and vary systematically relative to the clean price to include accrued interest (which increases daily between coupon dates, goes negative on ex-dividend date, and is zero on coupon distributions), and the published RPI index (on index-linked gilts.)

## Additional resources

### Recommended reading

#### On gilts

* Debt Management Office, [_About gilts_ page](https://www.dmo.gov.uk/responsibilities/gilt-market/about-gilts/)
* CG Asset Management, [_Introduction to Index-Linked Bonds Webinar_](https://www.cgasset.com/category/webinars/?s=index-linked) ([slides](https://www.cgasset.com/2024/02/21/introduction-to-index-linked-bonds-webinar-slides/), [recording](https://player.vimeo.com/video/915128868))
* PIMCO, [_Everything you need to know about bonds_](https://europe.pimco.com/en-eu/resources/education/everything-you-need-to-know-about-bonds)
* Occam Investing, [bond articles](https://occaminvesting.co.uk/portfolio-construction/)
* Office for National Statistics, [_The calculation of interest payable on government gilts_](https://www.ons.gov.uk/economy/governmentpublicsectorandtaxes/publicsectorfinance/methodologies/thecalculationofinterestpayableongovernmentgilts)

#### On gilt ladders

* Monevator, [Should you build an index-linked gilt ladder?](https://monevator.com/should-you-build-an-index-linked-gilt-ladder/)
* Fidelity, [Bond investment strategies](https://www.fidelity.com/learning-center/investment-products/fixed-income-bonds/bond-investment-strategies)
* PensionCraft, [Creating A Bond Ladder For Passive Income](https://www.youtube.com/watch?v=UqrO9Wi6rSY)

### Tools

* [Index-linked gilt ladder spreadsheet](https://www.lemonfool.co.uk/viewtopic.php?p=621213#p621213)
* [The Lemon Fool's _Gilts and Bonds_ forum](https://www.lemonfool.co.uk/viewforum.php?f=52)
* [Yield Gimp](https://www.yieldgimp.com/)
* [Gilt Prices and Yields](https://www.dividenddata.co.uk/uk-gilts-prices-yields.py)
* [Gilt Closing Prices](https://www.tradeweb.com/our-markets/data--reporting/gilt-closing-prices/)
* [US TIPS Ladder builder](https://www.tipsladder.com/)
