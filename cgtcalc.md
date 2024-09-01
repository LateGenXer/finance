# About

`cgtcalc.py` is a UK Capital Gains Tax calculator writtten in Python.

It is inspired by [other](#Alternative) free CGT calculators, but unlike most
of them it handles notional income and equalisation payments in a consistent manner.

It is written in Python.

## Disclaimer

**WARNING: `cgtcalc.py` is still work in progress!**

I wrote `cgtcalc.py` primarily for helping filing my own Self Assessment.
It's accurate to the best of my abilities, but I am not an accountant or financial adviser.
Always check carefully its results and engage a tax advisor in any doubt.

## Behavior

- Followings [share identification rules](https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg51560)
- Rounding done as per HMRC example calculations and Community Forums clarifications:
  - proceeds and gains always rounded down to whole poound
  - individual costs (charges, acquisition costs, Section 104 pool cost) and losses always rounded up to whole pound, _before_ addition
- Number of shares and unit share price kept at full precision
- Notional income (i.e., reinvested dividends from UK shares, and _Excess Reportable Income_ from offshore reporting funds)
and equalisation payments by adjusting Section 104 pool cost accordingly.

## Known limitations

- Disposals before 6 April 2008 (when Section 104 rule was introduced) are not supported.
- Restructurings not yet supported


# Usage

```
python cgtcalc.py trades.txt
```


## Format

`cgtcalc.py` input format is compatible both with
[CGTCalculator](http://cgtcalculator.com/instructions.htm#tradeformat) and
[cgtcalc](https://github.com/mattjgalloway/cgtcalc?tab=readme-ov-file#input-data) formats.

The input consists is a text file, with a line per transaction, each comprised by space separated fields in the form:

```
kind date security parameter*
```

The number and meaning of the fields varies with the kind of transaction:

| Kind | Description | Fields |
| ---- | ----------- | ------ |
| `B`/`BUY` | Buy transaction | _date_ _security_ _shares_ _price_ _expenses_ [_tax¹_]
| `S`/`SELL` | Sell transaction | _date_ _security_ _shares_ _price_ _expenses_ [_tax¹_]
| `DIVIDEND` | Notional income | _ex-dividend-date_ _security_ _holding²_ _income_
| `CAPRETURN` | Equalisation payment | _ex-dividend-date_ _security_ _group2-holding²_ _equalisation_

Notes:
1. _tax_ fields of `BUY`/`SELL` transactions are optional, for CGTCalculator compatibility, and are added to the expenses
2. _holding_ and _group2-holding_ fields are used for consistency check and have no bearing on calculated gains/losses.

Empty lines or lines starting with `#` are ignored.


## Example

### HMRC HS284 Example 3

This is [Example 3 from Shares Self Assessment helpsheet HS284](https://www.gov.uk/government/publications/shares-and-capital-gains-tax-hs284-self-assessment-helpsheet).

| Kind  |    Date    | Company | Shares | Price | Charges |
| ----- | :--------: | ------- | -----: | ----: | ------: |
| BUY   | 01/04/2015 | LOBSTER |   1000 | 4.00  |     150 |
| BUY   | 01/09/2018 | LOBSTER |    500 | 4.10  |      80 |
| SELL  | 01/05/2023 | LOBSTER |    700 | 4.80  |     100 |
| SELL  | 01/02/2024 | LOBSTER |    400 | 5.20  |     105 |

```
python cgtcalc.py tests/data/cgtcalc/hmrc-hs284-example3.tsv
```

```
SUMMARY

Tax Year   Disposals  Proceeds  Costs  Gains  Losses  Allowance  Taxable Gain  Carried Losses
─────────────────────────────────────────────────────────────────────────────────────────────
2023/2024          2      5440   4811    629       0       6000             0               0


TAX YEAR 2023/2024

1. SOLD 700 LOBSTER on 01/05/2023 for £3360 giving GAIN of £329

  Disposal proceeds                                       3360
  Disposal costs                                          -100
  Cost of 700 shares of 1500 in S.104 holding for £6280  -2931  (-6280 × 700 / 1500)
  ──────────────────────────────────────────────────────────────────────────────────
  Gain                                                     329

2. SOLD 400 LOBSTER on 01/02/2024 for £2080 giving GAIN of £300

  Disposal proceeds                                      2080
  Disposal costs                                         -105
  Cost of 400 shares of 800 in S.104 holding for £3349  -1675  (-3349 × 400 / 800)
  ────────────────────────────────────────────────────────────────────────────────
  Gain                                                    300


SECTION 104 HOLDINGS

LOBSTER

     Date     Description                       Identified  ΔCost  Pool Shares  Pool Cost
  ───────────────────────────────────────────────────────────────────────────────────────
  2015-04-01  Bought 1000 shares for £4150            1000   4150         1000       4150
  2018-09-01  Bought 500 shares for £2130              500   2130         1500       6280
  2023-05-01  Sold 700 shares                          700  -2931          800       3349
  2024-02-01  Sold 400 shares                          400  -1675          400       1674
```

## Vanguard UK Reporting Fund FAQ guide example


| Kind      |    Date    | Company      |        |          |         |
| --------- | :--------: | ------------ | ------ | :------: | ------: |
| BUY       | 21/11/2016 | IE00B3X1LS57 |    100 | 229.2590 |       0 |
| DIVIDEND  | 30/12/2016 | IE00B3X1LS57 |    100 |  14.69   |         |
| CAPRETURN | 30/12/2016 | IE00B3X1LS57 |    100 |  16.71   |         |
| SELL      | 29/03/2017 | IE00B3X1LS57 |    100 | 238.9156 |       0 |


```
SUMMARY

Tax Year   Disposals  Proceeds  Costs  Gains  Losses  Allowance  Taxable Gain  Carried Losses
─────────────────────────────────────────────────────────────────────────────────────────────
2016/2017          1     23891  22925    966       0      11100             0               0


TAX YEAR 2016/2017

1. SOLD 100 IE00B3X1LS57 on 29/03/2017 for £23891 giving GAIN of £966

  Disposal proceeds                                23891
  Cost of 100 shares in S.104 holding for £22925  -22925
  ────────────────────────────────────────────────────────
  Gain                                               966


SECTION 104 HOLDINGS

IE00B3X1LS57

     Date     Description                       Identified  ΔCost   Pool Shares  Pool Cost
  ────────────────────────────────────────────────────────────────────────────────────────
  2016-11-21  Bought 100 shares for £22926             100   22926          100      22926
  2016-12-30  Notional distribution                             15          100      22941
  2016-12-30  Equalisation payment                             -16          100      22925
  2017-03-29  Sold 100 shares                          100  -22925            0          0
```

# References

- HMRC:
  - [Self Assessment: Capital Gains Tax summary notes](https://www.gov.uk/government/publications/self-assessment-capital-gains-summary-sa108)
  - [Shares and Capital Gains Tax helpsheet HS284](https://www.gov.uk/government/publications/shares-and-capital-gains-tax-hs284-self-assessment-helpsheet/hs284-shares-and-capital-gains-tax-2024)
  - [Capital Gains Manual](https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual)
- Quilter Capital Gains Tax quick reference guides:
  - [Quick reference guide 1 - section 104 Holdings](https://www.quilter.com/siteassets/documents/platform/guides-and-brochures/20719-cgt-quick-reference-guide-1-section-104-holdings.pdf)
  - [Quick reference guide 2 - Share identification rules](https://www.quilter.com/siteassets/documents/platform/guides-and-brochures/20720-cgt-quick-reference-guide-2-share-identification-rules.pdf)
- abrdn guides:
  - [Taxation of OEICs and unit trusts](https://techzone.abrdn.com/public/investment/Guide-Taxation-of-Collectives)
  - [CGT and share matching](https://techzone.abrdn.com/public/personal-taxation/Practical-G-Share-match)
- Fidelity:
  - [Taxing calculations: Capital Gains Tax](https://adviserservices.fidelity.co.uk/media/fnw/guides/taxing-calculations-capital-gains-tax.pdf)
- Vanguard:
  - [UK Reporting Fund FAQ guide](https://fund-docs.vanguard.com/uk-reporting-fund-faq.pdf)
- Monevator:
  - [Accumulation units – tax on reinvested dividends UK](https://monevator.com/income-tax-on-accumulation-unit/)
  - [Excess reportable income: what it is, where to find it, and what to do with it](https://monevator.com/excess-reportable-income/)


# Alternatives

- [CGTCalculator](http://cgtcalculator.com/instructions.htm#tradeformat)
- [cgtcalc](https://github.com/mattjgalloway/cgtcalc)
