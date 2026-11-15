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
| `DIVIDEND` | Notional distribution² | _ex-dividend-date⁴_ _security_ _holding³_ _total-income⁶_ |
| `CAPRETURN` | Equalisation payment | _ex-dividend-date⁴_ _security_ _group2-holding³_ _total-equalisation⁶_ |
| `R` | Restructuring | _date_ _security_ _restructuring-factor⁵_ |
| `SPLIT` | Stock split | _date_ _security_ _factor_ |
| `UNSPLIT` | Reverse stock split | _date_ _security_ _factor_ |

Notes:

1. _tax_ fields of `BUY`/`SELL` transactions are optional, are supported for CGTCalculator compatibility, and will be added to the expenses
2. notional distribution is, for example, reinvested dividends in accumulation class of UK Authorized Investments Funds, or Excess Reportable Income in Offshore Funds
3. _holding_ and _group2-holding_ fields are used for consistency check  and have no bearing on calculated gains/losses.
4. To ensure notional dividends and equalization payments are assigned to the right disposals, it is imperative that the _ex-dividend-date_ is used for these transactions, and not the distribution date.
5. For example, _10_ for a 10-for-1 stock split, _0.1_ for a 1-for-10 reverse stock split; for [CGTCalculator compatibiliy](https://www.cgtcalculator.com/instructions.htm#restructuring).
6. Unlike the _price_ field of `BUY`/`SELL` transactions, which is the price _per share_, the _total-income_ and _total-equalisation_ fields of `DIVIDEND`/`CAPRETURN` transactions are the _total_ amounts in pounds across your whole holding, and _not_ the per share rates.  See [Notional distributions and equalisation](#notional-distributions-and-equalisation) below.

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

1. This sale is not in the example but was added to illustrate how a future disposal would be handled.

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

### Notional distributions and equalisation

Funds (OEICs, unit trusts, and offshore reporting funds such as ETFs domiciled in Ireland or Luxembourg) held outside tax wrappers need two extra kinds of entries, besides `BUY`/`SELL`, to get gains right.
The figures for these are found in the fund's annual _Consolidated Tax Certificate_ (CTC) provided by your broker/platform, or in the fund's distribution/reporting tables.

#### `DIVIDEND` — notional distributions

A notional distribution is income which you are taxed on, but which was never paid out to you as cash, namely:

* dividends/interest of _accumulation_ units/shares, which are automatically reinvested in the fund;
* _Excess Reportable Income_ (ERI) of offshore reporting funds.

You must declare this income in your Self Assessment and pay Income Tax on it.
Because the income stays inside the fund, it increases the value of your shares, and therefore it would be taxed _again_ as a capital gain when you sell, were nothing done about it.
To prevent this double taxation, [HMRC allows the notional distribution to be added to the cost of your Section 104 holding](https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg57707), which is what a `DIVIDEND` entry does.

Things to keep in mind:

* Use the _total_ notional distribution for your whole holding (e.g., 100 shares × £0.1469 per share = £14.69), not the per share rate.
* If you bought shares during the distribution period, then read [When both notional distributions and equalisation apply](#when-both-notional-distributions-and-equalisation-apply) below to decide whether to use the figure gross or net of equalisation.
* ERI is a notional distribution too, therefore it must be entered as a `DIVIDEND` (not `CAPRETURN`).
* Dividends from _income_ units/shares, which are actually paid out to you as cash, must _not_ be entered, as they don't affect the value of your shares.
* The _holding_ field is the number of shares you held at the ex-dividend date. It's merely used as a self-consistency check (a warning is shown if it doesn't match the holding implied by your `BUY`/`SELL` entries).

#### `CAPRETURN` — equalisation payments

When you buy fund shares part way through a distribution period, the price you pay already includes income which the fund accrued since the start of the period, but before you bought them (shares bought during the period are known as _Group 2_ shares, as opposed to _Group 1_ shares which were held since the start of the period.)
At the next distribution, Group 2 shares receive the same distribution as Group 1 shares, but part of it, the _equalisation_, is not income: it is merely a refund of part of the purchase price you paid.

Equalisation is therefore not subject to Income Tax, and, for Capital Gains Tax purposes, [it must be deducted from the cost of your acquisition](https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg57705), which is what a `CAPRETURN` entry does.
For income units/shares this is intuitive: part of the purchase price was effectively handed back to you in cash, so your acquisition cost must be reduced by the same amount (otherwise the drop in the share price on the ex-dividend date would give you an artificial capital loss.)

Things to keep in mind:

* Use the _total_ equalisation for your Group 2 shares (e.g., 100 shares × £0.1671 per share = £16.71), not the per share rate.
* Equalisation only applies to the first distribution after you buy, and only to the shares bought during that distribution period.
* For accumulation units/shares, equalisation is usually already accounted for in the notional distribution figure, in which case it must _not_ be entered -- see [below](#when-both-notional-distributions-and-equalisation-apply).
* The _group2-holding_ field is the number of shares bought during this distribution period (and still held at the ex-dividend date). Like _holding_ above, it is merely used as a self-consistency check.
* As equalisation is a return of part of the price initially paid for the new units, [it is deducted from that price when computing the gain on their eventual disposal](https://www.gov.uk/hmrc-internal-manuals/capital-gains-manual/cg57705); cgtcalc.py does so by deducting it from the Section 104 holding cost, which is where the price paid for the new units normally ends up.

#### When both notional distributions and equalisation apply

When you buy _accumulation_ units/shares part way through a distribution period, both of the above rules apply at once.
Your Group 2 shares get the same distribution per share as Group 1 shares, all of which is reinvested in the fund, but only part of it is income, the remainder being equalisation:

```text
gross distribution = Group 2 shares × distribution per share
                   = income + equalisation
```

The net effect on your acquisition cost is to add the reinvested gross distribution and deduct the equalisation, that is, to add just the income net of equalisation:

```text
+ gross distribution − equalisation = + income
```

Therefore there are two equivalent ways of entering these:

* **net** -- a single `DIVIDEND` entry with the income _net_ of equalisation, and _no_ `CAPRETURN` entry; or
* **gross** -- a `DIVIDEND` entry with the _gross_ distribution, _plus_ a `CAPRETURN` entry with the equalisation.

What you must _not_ do is enter the income net of equalisation as `DIVIDEND` _and_ the equalisation as `CAPRETURN`, as that would deduct the equalisation twice, understating your costs and overstating your gains.

The choice is normally dictated by which figures your Consolidated Tax Certificate provides.
Most CTCs report the income you must declare for Income Tax, which is already _net_ of equalisation, therefore the net way is usually the simplest.
If unsure, multiply the number of shares by the distribution per share:

* if the result matches the income _plus_ the equalisation, then the income figure is net of equalisation (net way);
* if the result matches the income alone, then the income figure is gross of equalisation (gross way).

This is also what fund providers mean by remarks such as _"for accumulation units no book cost adjustment is made for Capital Gains Tax purposes as the equalisation payment is effectively offset by its reinvestment"_: the equalisation is already netted off the notional distribution, so no _separate_ adjustment is needed.
See also the [abrdn](https://techzone.abrdn.com/public/investment/Guide-Taxation-of-Collectives) and [Fidelity](https://adviserservices.fidelity.co.uk/media/fnw/guides/taxing-calculations-capital-gains-tax.pdf) guides, and [Monevator's explanation](https://monevator.com/income-tax-on-accumulation-unit/).

For example, consider a CTC for an accumulation fund with:

| | |
| - | -: |
| Group 1 units | 0.00 |
| Group 2 units | 39843.30 |
| Interest per unit | 0.4414p |
| Equalisation | £94.19 |
| Interest | £81.68 |

Since 39843.30 × £0.004414 = £175.87 = £81.68 + £94.19, the interest is net of equalisation, so one would enter either

```text
DIVIDEND   01/04/2025  FUND  39843.30  81.68
```

or, equivalently,

```text
DIVIDEND   01/04/2025  FUND  39843.30  175.87
CAPRETURN  01/04/2025  FUND  39843.30  94.19
```

but never `DIVIDEND ... 81.68` together with `CAPRETURN ... 94.19`.

For [offshore reporting funds](#vanguard-uk-reporting-fund-faq-guide-example), ERI is reported at the same rate per share for Group 1 and Group 2 shares (i.e., gross), so any equalisation reported alongside it should be entered separately as a `CAPRETURN`, as in the Vanguard example above:

```text
BUY        21/11/2016  IE00B3X1LS57  100  229.2590  0
DIVIDEND   30/12/2016  IE00B3X1LS57  100  14.69
CAPRETURN  30/12/2016  IE00B3X1LS57  100  16.71
```

#### Summary

| Holding | `DIVIDEND` | `CAPRETURN` |
| ------- | ---------- | ----------- |
| Income units/shares | — | equalisation |
| Accumulation units/shares, CTC income net of equalisation (most common) | income (net) | — |
| Accumulation units/shares, CTC income gross of equalisation | gross distribution | equalisation |
| Offshore reporting funds | ERI | equalisation (if any) |

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
