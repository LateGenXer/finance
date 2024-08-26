# About

**WARNING: `cgtcalc.py` is still very much work in progress!**

`cgtcalc.py` is UK Capital Gains Tax calculator.

It is inspired by [other](#Other) free calculators, but unlike most it
handles notional income and equalisation payments in a consistent manner.

It is written in Python.


## Known issues

- Rounding not yet consistent
- Restructurings not yet supported


# Usage

```
python cgtcalc.py trades.txt
```


## Format

`cgtcalc.py` can input in both formats:
- [CGTCalculator](http://cgtcalculator.com/instructions.htm#tradeformat)
- [cgtcalc](https://github.com/mattjgalloway/cgtcalc?tab=readme-ov-file#input-data)


## Example

```
python cgtcalc.py tests/data/cgtcalc/cgtcalculator-example1.tsv
```

```
warning: cgtcal.py is still work in progress!
TAX YEAR 2013/2014

1. SOLD 6000 BARC on 14/04/2013 for GAIN of £3999.06
Matches with:
- SECTION_104: 6000 shares of 8000 at average cost of 4.850990
Calculation: 33120.00 - (15.00 + 29105.94) = 3999.06

2. SOLD 9000 VOD on 23/02/2014 for GAIN of £5068.20
Matches with:
- SECTION_104: 9000 shares of 18000 at average cost of 3.055756
Calculation: 32580.00 - (10.00 + 27501.80) = 5068.20

3. SOLD 9000 VOD on 24/02/2014 for GAIN of £5113.20
Matches with:
- SECTION_104: 9000 shares of 9000 at average cost of 3.055756
Calculation: 32625.000 - (10.00 + 27501.80) = 5113.200

13-14: Disposal Proceeds = £98325.00 , Allowable Costs = £84144.54 , Disposals = 3
13-14: Year Gains = £14180.46  Year Losses = £0


TAX YEAR 2015/2016

1. SOLD 8000 BP. on 15/07/2015 for GAIN of £19848.95
Matches with:
- SECTION_104: 8000 shares of 8000 at average cost of 3.797631
Calculation: 50240.00 - (10.00 + 30381.05) = 19848.95

15-16: Disposal Proceeds = £50240.00 , Allowable Costs = £30391.05 , Disposals = 1
15-16: Year Gains = £19848.95  Year Losses = £0


TAX YEAR 2022/2023

1. SOLD 5000 BP. on 24/12/2022 for LOSS of £5283.14
Matches with:
- SECTION_104: 5000 shares of 7000 at average cost of 5.390629
Calculation: 21680.000 - (10.00 + 26953.14) = -5283.140

22-23: Disposal Proceeds = £21680.00 , Allowable Costs = £26963.14 , Disposals = 1
22-23: Year Gains = £0  Year Losses = £5283.14


SECTION 104

BARC:
      Date Trade       Shares   Amount Holding     Cost
2010-12-01   BUY 3000 of 3000 14547.30    3000 14547.30
2010-12-02   BUY 5000 of 5000 24260.62    8000 38807.92
2013-04-14  SELL 6000 of 6000             2000  9701.98

BP.:
      Date Trade       Shares   Amount Holding     Cost
2013-01-15   BUY 5000 of 5000 18853.75    5000 18853.75
2013-03-24   BUY 3000 of 3000 11527.30    8000 30381.05
2015-07-15  SELL 8000 of 8000                0     0.00
2017-01-22   BUY 5000 of 5000 27634.20    5000 27634.20
2019-06-22   BUY 2000 of 2000 10100.20    7000 37734.40
2022-12-24  SELL 5000 of 5000             2000 10781.26

VOD:
      Date Trade         Shares   Amount Holding     Cost
2012-09-03   BUY 18000 of 18000 55003.60   18000 55003.60
2014-02-23  SELL   9000 of 9000             9000 27501.80
2014-02-24  SELL   9000 of 9000                0     0.00
```


# Other

- [CGTCalculator](http://cgtcalculator.com/instructions.htm#tradeformat)
- [cgtcalc](https://github.com/mattjgalloway/cgtcalc)
