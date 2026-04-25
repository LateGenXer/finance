# About

`eri.py` is an Excess Reportable Income (ERI) calculator for offshore reporting
funds (e.g., Irish-domiciled ETFs).

Reporting funds report, for each reporting period, an ERI figure per share.
Investors holding shares at the end of the reporting period must declare the
corresponding ERI as income in the tax year of the fund's distribution date,
and (being notional income) it also increases the base cost of the holding for
Capital Gains Tax purposes.

`eri.py` works out the holdings at the end of each reporting period from the
same trades file used by [`cgtcalc.py`](cgtcalc.md), converts the ERI to pounds
using [HMRC monthly exchange rates](https://www.gov.uk/government/collections/exchange-rates-for-customs-and-vat)
for the distribution month, and totals it per tax year.  It can also output the
`DIVIDEND` lines to feed the ERI back into `cgtcalc.py`.


## Disclaimer

I wrote `eri.py` primarily to assist filing my own Self Assessment.
It's accurate to the best of my abilities, but I am not an accountant nor a financial adviser.
Always check carefully its results and engage a tax advisor in any doubt.

## Known limitations

- ERI figures must be sourced manually from each fund's reporting fund reports
- Currency conversion requires network access to fetch HMRC exchange rates


# Usage

```
python eri.py [--dividends] trades.tsv [trades2.tsv ...] eri.csv
```

where:

* `trades.tsv` is one or more trades files in [`cgtcalc.py` format](cgtcalc.md#format)

* `eri.csv` is a CSV file with the ERI figures, as described [below](#format)

* `--dividends` additionally prints `DIVIDEND` lines, for use with `cgtcalc.py`

## Format

The ERI input is a Comma Separated Value (CSV) file with the following fields:

* `TIDM`: fund's LSE ticker

* `ISIN`: fund's ISIN

* `ReportEndDate`: end of the fund's reporting period, as _DD/MM/YYYY_

* `Currency`: currency of the ERI figure (e.g. `GBP`, `USD`, `EUR`)

* `ERI`: excess reportable income per share, in the above currency

* `DistributionDate`: fund distribution date (i.e., date the ERI is deemed received), as _DD/MM/YYYY_

A row matches a security in the trades file if either its TIDM or ISIN matches
(ignoring any exchange prefix such as `LSE:`).  Rows for securities not held at
the end of the reporting period are ignored, so the same ERI file can be reused
across years.

The holding is the [Section 104 pool](cgtcalc.md#behavior) at the end of the
reporting period, including any trades on its last day.

## Example

Given `trades.tsv`:

```text
BUY   15/03/2023  LSE:VUSA  100  65.20  5
BUY   10/01/2024  LSE:VUSA   50  70.10  5
SELL  20/08/2024  LSE:VUSA  150  88.00  5
```

and `eri.csv` (illustrative figures):

```csv
TIDM,ISIN,ReportEndDate,Currency,ERI,DistributionDate
VUSA,IE00B3XXRP09,30/06/2023,USD,0.2317,31/12/2023
VUSA,IE00B3XXRP09,30/06/2024,USD,0.2452,31/12/2024
```

then:

```bash
python eri.py --dividends trades.tsv eri.csv
```

```text
TAX YEAR 2023/2024

  Security  Report End  Distribution  Shares  ERI/share  CCY    Rate  ERI (GBP)
  ─────────────────────────────────────────────────────────────────────────────
  LSE:VUSA  2023-06-30   2023-12-31      100     0.2317  USD  1.2536      18.48
  ─────────────────────────────────────────────────────────────────────────────
  Total                                                                   18.48


TAX YEAR 2024/2025

  Security  Report End  Distribution  Shares  ERI/share  CCY    Rate  ERI (GBP)
  ─────────────────────────────────────────────────────────────────────────────
  LSE:VUSA  2024-06-30   2024-12-31      150     0.2452  USD  1.2662      29.05
  ─────────────────────────────────────────────────────────────────────────────
  Total                                                                   29.05

DIVIDEND	01/07/2023	LSE:VUSA	100	18.48
DIVIDEND	01/07/2024	LSE:VUSA	150	29.05
```

Note that ERI for the 2024 reporting period is still due even though the shares
were sold before the distribution date.

The `DIVIDEND` lines are dated the day after the reporting period end (i.e.,
effectively the ex-dividend date), and can be appended to the trades file so
that `cgtcalc.py` adjusts the Section 104 pool cost accordingly (see
[notional distributions](cgtcalc.md#format)).


# References

- HMRC:
  - [Investment Funds Manual](https://www.gov.uk/hmrc-internal-manuals/investment-funds)
  - [Offshore funds: list of reporting funds](https://www.gov.uk/government/publications/offshore-funds-list-of-reporting-funds)
  - [Exchange rates from HMRC in CSV and XML format](https://www.gov.uk/government/collections/exchange-rates-for-customs-and-vat)
- [The Offshore Funds (Tax) Regulations 2009](https://www.legislation.gov.uk/uksi/2009/3001/contents), regulation 94
- See also [`cgtcalc.md` references](cgtcalc.md#references)
