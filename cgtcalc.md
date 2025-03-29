# cgtcalc.py

## About

cgtcalc.py is a UK Capital Gains calculator written in Python.

It was inspired by [other](#alternatives) free CGT calculators, but unlike most
of them it handles notional distributions and equalisation payments in a consistent manner.

### Disclaimer

* I wrote cgtcalc.py primarily for filing my own Self Assessment.
* It's accurate to the best of my abilities, but I am not a tax or financial adviser.
* Always check carefully its results and engage a tax advisor or HMRC in any doubt.

### Behavior

* Follows [share identification rules](https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg51560)
* Rounding done as per HMRC example calculations and HMRC Community Forums clarifications:
  * proceeds and gains always rounded down to whole pound
  * individual costs (charges, acquisition costs, Section 104 pool cost) and losses always rounded up to whole pound
* Number of shares and unit share price kept at full precision
* Notional income (i.e., reinvested dividends from UK shares, and _Excess Reportable Income_ from offshore reporting funds)
and equalisation payments is handled by adjusting Section 104 pool cost accordingly.
* Provides the necessary figures to [work out the Capital Gains Tax adjustment for the 2024 to 2025 tax year](https://www.gov.uk/guidance/work-out-your-capital-gains-tax-adjustment-for-the-2024-to-2025-tax-year)

### Known limitations

* Disposals before 6 April 2008 (when Section 104 rule was introduced) are not supported.

## Usage

```bash
python cgtcalc.py trades.txt
```

### Format

cgtcalc.py's input format is compatible both with
[CGTCalculator](https://www.cgtcalculator.com/instructions.htm#tradeformat) and
[cgtcalc](https://github.com/mattjgalloway/cgtcalc?tab=readme-ov-file#input-data) formats.

The input consists of a text file, with a line per transaction, each comprised by space separated fields in the form:

```text
kind  date  security  parameter*
```

The number and meaning of the fields varies with the kind of transaction:

| Kind | Description | Fields |
| ---- | ----------- | ------ |
| `B`/`BUY` | Buy transaction | _date_ _security_ _shares_ _price_ _expenses_ [_tax¹_] |
| `S`/`SELL` | Sell transaction | _date_ _security_ _shares_ _price_ _expenses_ [_tax¹_] |
| `DIVIDEND` | Notional distribution² | _ex-dividend-date⁴_ _security_ _holding³_ _income_ |
| `CAPRETURN` | Equalisation payment | _ex-dividend-date⁴_ _security_ _group2-holding³_ _equalisation_ |
| `R` | Restructuring | _date_ _security_ _restructuring-factor⁵_ |
| `SPLIT` | Stock split | _date_ _security_ _factor_ |
| `UNSPLIT` | Reverse stock split | _date_ _security_ _factor_ |

Notes:

1. _tax_ fields of `BUY`/`SELL` transactions are optional, are supported for CGTCalculator compatibility, and will be added to the expenses
2. notional distribution is, for example, reinvested dividends in accumulation class of UK Authorized Investments Funds, or Excess Reportable Income in Offshore Funds
3. _holding_ and _group2-holding_ fields are used for consistency check  and have no bearing on calculated gains/losses.
4. To ensure notional dividends and equalization payments are assigned to the right disposals, it is imperative that the _ex-dividend-date_ is used for these transactions, and not the distribution date.
5. For example, _10_ for a 10-for-1 stock split, _0.1_ for a 1-for-10 reverse stock split; for [CGTCalculator compatibiliy](https://www.cgtcalculator.com/instructions.htm#restructuring).

Empty lines or lines starting with `#` are ignored.

### Example

#### HMRC HS284 Example 3

This is [Example 3 from Shares Self Assessment helpsheet HS284](https://www.gov.uk/government/publications/shares-and-capital-gains-tax-hs284-self-assessment-helpsheet).

| Kind  |    Date    | Company | Shares | Price | Charges |
| ----- | :--------: | ------- | -----: | ----: | ------: |
| BUY   | 01/04/2015 | LOBSTER |   1000 | 4.00  |     150 |
| BUY   | 01/09/2018 | LOBSTER |    500 | 4.10  |      80 |
| SELL  | 01/05/2023 | LOBSTER |    700 | 4.80  |     100 |
| SELL  | 01/02/2024 | LOBSTER |    400 | 5.20  |     105 |

```bash
python cgtcalc.py tests/data/cgtcalc/hmrc-hs284-example3.tsv
```

```text
SUMMARY

Tax Year   Disposals  Proceeds  Costs  Gains  Losses  Allowance  Taxable Gain  Carried Losses
─────────────────────────────────────────────────────────────────────────────────────────────
2023/2024          2      5440   4811    629       0       6000             0               0


TAX YEAR 2023/2024

1. SOLD 700 LOBSTER on 2023-05-01 for £3360 giving GAIN of £329

  Disposal proceeds                                       3360
  Disposal costs                                          -100
  Cost of 700 shares of 1500 in S.104 holding for £6280  -2931  (-6280 × 700 / 1500)
  ──────────────────────────────────────────────────────────────────────────────────
  Gain                                                     329

2. SOLD 400 LOBSTER on 2024-02-01 for £2080 giving GAIN of £300

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

#### Vanguard UK Reporting Fund FAQ guide example

This is the [Excess Reportable Income example calculation from Vanguard UK Reporting Fund FAQ guide](https://fund-docs.vanguard.com/uk-reporting-fund-faq.pdf#page=8).

| Kind      |    Date    | Company      | Shares |          |         |
| --------- | :--------: | ------------ | -----: | :------: | ------: |
| BUY       | 21/11/2016 | IE00B3X1LS57 |    100 | 229.2590 |       0 |
| DIVIDEND  | 30/12/2016 | IE00B3X1LS57 |    100 |  14.69   |         |
| CAPRETURN | 30/12/2016 | IE00B3X1LS57 |    100 |  16.71   |         |
| SELL¹     | 29/03/2017 | IE00B3X1LS57 |    100 | 238.9156 |       0 |

1. This sale is not in the example but was added to illustrate how a future disposal would be handlded.

```text
SUMMARY

Tax Year   Disposals  Proceeds  Costs  Gains  Losses  Allowance  Taxable Gain  Carried Losses
─────────────────────────────────────────────────────────────────────────────────────────────
2016/2017          1     23891  22925    966       0      11100             0               0


TAX YEAR 2016/2017

1. SOLD 100 IE00B3X1LS57 on 2017-03-29 for £23891 giving GAIN of £966

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

## References

* HMRC:
  * [Self Assessment: Capital Gains Tax summary notes](https://www.gov.uk/government/publications/self-assessment-capital-gains-summary-sa108)
  * [Shares and Capital Gains Tax helpsheet HS284](https://www.gov.uk/government/publications/shares-and-capital-gains-tax-hs284-self-assessment-helpsheet/hs284-shares-and-capital-gains-tax-2024)
  * [Capital Gains Manual](https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual)
  * [Investment Funds Manual](https://www.gov.uk/hmrc-internal-manuals/investment-funds)
* Quilter Capital Gains Tax quick reference guides:
  * [Quick reference guide 1 - section 104 Holdings](https://www.quilter.com/siteassets/documents/platform/guides-and-brochures/20719-cgt-quick-reference-guide-1-section-104-holdings.pdf)
  * [Quick reference guide 2 - Share identification rules](https://www.quilter.com/siteassets/documents/platform/guides-and-brochures/20720-cgt-quick-reference-guide-2-share-identification-rules.pdf)
* abrdn guides:
  * [Taxation of OEICs and unit trusts](https://techzone.abrdn.com/public/investment/Guide-Taxation-of-Collectives)
  * [CGT and share matching](https://techzone.abrdn.com/public/personal-taxation/Practical-G-Share-match)
* Fidelity:
  * [Taxing calculations: Capital Gains Tax](https://adviserservices.fidelity.co.uk/media/fnw/guides/taxing-calculations-capital-gains-tax.pdf)
* Vanguard:
  * [UK Reporting Fund FAQ guide](https://fund-docs.vanguard.com/uk-reporting-fund-faq.pdf)
* James Hay:
  * [Capital gains tax on investments by individuals in UK stocks and shares](https://www.jameshay.co.uk/media/1579/capital-gains-tax-on-investment-by-individuals-in-uk-stocks-and-shares.pdf)
* Monevator:
  * [Accumulation units – tax on reinvested dividends UK](https://monevator.com/income-tax-on-accumulation-unit/)
  * [Excess reportable income: what it is, where to find it, and what to do with it](https://monevator.com/excess-reportable-income/)
* KPMG
  * [Excess Reported Income Guidance](https://www.kpmgreportingfunds.co.uk/guidance)

## Alternatives

* [CGTCalculator](https://www.cgtcalculator.com/instructions.htm#tradeformat)
* [cgtcalc](https://github.com/mattjgalloway/cgtcalc)
