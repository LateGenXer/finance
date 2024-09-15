# About

`accrued_income.py` is is an accrued income calculator for gilts.

If one has more than nominal £5,000 units of gilts then one is supposed adjust
the received interest by interested accrued when buying/selling gilts, and
report it in one's Self Assessment (more specifically in
_Other UK income_ >
_Interest from gilt edged and other UK securities, deeply discounted securities and accrued income profits_ >
_Gross amount before tax_ ) as explained in the [references below](#References).

The accrued income calculations are arithmetically simple (mere additions and
subtractions), but the rules as to when to add/subtract are subtle, making the
whole exercise head-splitting and error prone.

This calculator automates the task, aided by the fact that all gilts interest
payments and accrued interest can be determined exactly from the trade
settlement dates and units traded.


## Disclaimer

> [!WARNING]
> `accrued_income.py` is still work in progress!

I wrote `accrued_income.py` primarily for helping filing my own Self Assessment.
It's accurate to the best of my abilities, but I am not an accountant or financial adviser.
Always check carefully its results and engage a tax advisor in any doubt.

## Known limitations

- Only gilts are supported
- Index linked gilts are implemented, but not throuhgly tested


# Usage

```
python accrued_income.py trades.csv
```

## Format

The input format is a Comma Separated Value (CSV) file with the following fields:

* `SettlementDate`: trade settlement date (typically 1 to 2 days after trade date)

* `Security`: gilt's ISIN or TIDM (LSE's ticker)

* `Units`: units bought (if positive) or sold (if negative) in _nominal_ pounds (a.k.a. _face value_)

* `AccruedInterest` (optional but recommended): interest accrued from previous interest payment


For example:

```csv
SettlementDate,Security,Units,AccruedInterest
2023-12-07,TG24,50000.00,62.84
2024-01-02,TN25,25000.00,26.32
2024-07-01,TG25,10000.00,4.10
```

# References

- HMRC:
  - [Self Assessment: additional information notes (SA101)](https://www.gov.uk/government/publications/self-assessment-additional-information-sa101)
  - [Accrued Income Scheme (Self Assessment helpsheet HS343](https://www.gov.uk/government/publications/accrued-income-scheme-hs343-self-assessment-helpsheet)
  - [Savings and Investment Manual - Accrued Income Scheme](https://www.gov.uk/hmrc-internal-manuals/savings-and-investment-manual/saim4000)
- DMO:
  - [Summary of the main features of the taxation rules for gilts](https://www.dmo.gov.uk/responsibilities/gilt-market/buying-selling/taxation)
