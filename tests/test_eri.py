#
# Copyright (c) 2026 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import datetime
import io
import pathlib
import re
import subprocess
import sys
import warnings

import pytest

from decimal import Decimal

import eri

from cgtcalc import Calculator, PoolUpdate


def pool_update(date:datetime.date, pool_shares:int) -> PoolUpdate:
    return PoolUpdate(
        date=date,
        description='',
        identified=Decimal(0),
        delta_cost=Decimal(0),
        pool_shares=Decimal(pool_shares),
        pool_cost=Decimal(0),
    )


pool_updates = [
    pool_update(datetime.date(2022, 1, 10), 100),
    pool_update(datetime.date(2022, 6, 15), 150),
    pool_update(datetime.date(2023, 3, 1), 0),
    pool_update(datetime.date(2023, 9, 1), 50),
]


@pytest.mark.parametrize("date,shares", [
    (datetime.date(2022, 1, 9), 0),
    (datetime.date(2022, 1, 10), 100),
    (datetime.date(2022, 6, 14), 100),
    (datetime.date(2022, 6, 15), 150),
    (datetime.date(2022, 12, 31), 150),
    (datetime.date(2023, 3, 1), 0),
    (datetime.date(2023, 8, 31), 0),
    (datetime.date(2024, 1, 1), 50),
])
def test_shares_held_at(date:datetime.date, shares:int) -> None:
    assert eri.shares_held_at(pool_updates, date) == Decimal(shares)


def test_shares_held_at_empty() -> None:
    assert eri.shares_held_at([], datetime.date(2024, 1, 1)) == Decimal(0)


def test_lookup_rate_gbp() -> None:
    assert eri.lookup_rate('GBP', datetime.date(2024, 8, 1)) == Decimal(1)


@pytest.mark.parametrize("currency,date,rate", [
    ('EUR', datetime.date(2021, 1, 31), Decimal('1.1075')),
    ('USD', datetime.date(2024, 8, 15), Decimal('1.3033')),
])
def test_lookup_rate(currency:str, date:datetime.date, rate:Decimal) -> None:
    assert eri.lookup_rate(currency, date) == rate


# Fixed exchange rates, to avoid network access
fake_rates = {
    'GBP': Decimal(1),
    'USD': Decimal('1.25'),
    'EUR': Decimal('1.20'),
}


def fake_lookup_rate(currency:str, date:datetime.date) -> Decimal:
    return fake_rates[currency]


trades = '''\
BUY 10/01/2022 VWRL 100 80.00 5
BUY 15/06/2022 LSE:VUSA 200 60.00 5
BUY 01/02/2023 IE00B4L5Y983 40 50.00 5
BUY 01/03/2023 ABCD 10 10.00 0
SELL 01/05/2023 ABCD 10 11.00 0
BUY 01/06/2023 VWRL 50 85.00 5
'''

eri_csv = '''\
TIDM,ISIN,ReportEndDate,Currency,ERI,DistributionDate
VWRL,IE00B3RBWM25,30/06/2022,USD,0.10,31/12/2022
VWRL,IE00B3RBWM25,30/06/2023,USD,0.20,31/12/2023
VUSA,IE00B3XXRP09,30/06/2022,GBP,0.05,31/12/2022
,IE00B4L5Y983,31/03/2023,EUR,0.30,30/09/2023
ABCD,GB0000000001,30/06/2023,GBP,1.00,31/12/2023
WXYZ,GB0000000002,30/06/2023,GBP,1.00,31/12/2023
VWRL,IE00B3RBWM25,30/06/2021,USD,0.10,31/12/2021
'''


def calculate(trades:str, eri_csv:str) -> list[eri.ERI]:
    return eri.calculate([io.StringIO(trades)], io.StringIO(eri_csv), rate_lookup=fake_lookup_rate)


def write_report(entries:list[eri.ERI], dividends:bool=False) -> str:
    stream = io.StringIO()
    eri.write_report(entries, stream, dividends=dividends)
    return stream.getvalue()


def test_calculate() -> None:
    entries = calculate(trades, eri_csv)

    # Securities not held, or not held on the report end date, are skipped;
    # entries are sorted by distribution date
    assert [(entry.security, entry.report_end_date, entry.shares, entry.rate, entry.eri_gbp) for entry in entries] == [
        # 200 * 0.05 GBP, matched despite the exchange prefix
        ('VUSA', datetime.date(2022, 6, 30), Decimal(200), Decimal(1), Decimal('10.00')),
        # 100 * 0.10 / 1.25 USD
        ('VWRL', datetime.date(2022, 6, 30), Decimal(100), Decimal('1.25'), Decimal('8.00')),
        # 40 * 0.30 / 1.20 EUR, matched by ISIN
        ('IE00B4L5Y983', datetime.date(2023, 3, 31), Decimal(40), Decimal('1.20'), Decimal('10.00')),
        # 150 * 0.20 / 1.25 USD
        ('VWRL', datetime.date(2023, 6, 30), Decimal(150), Decimal('1.25'), Decimal('24.00')),
    ]


def test_calculate_multiple_trades() -> None:
    lines = trades.splitlines(keepends=True)
    entries = eri.calculate([io.StringIO(''.join(lines[:3])), io.StringIO(''.join(lines[3:]))], io.StringIO(eri_csv), rate_lookup=fake_lookup_rate)
    assert entries == calculate(trades, eri_csv)


def test_write_report() -> None:
    out = write_report(calculate(trades, eri_csv))

    # Entries are grouped by the tax year of the distribution date
    assert 'TAX YEAR 2022/2023' in out
    assert 'TAX YEAR 2023/2024' in out
    assert 'TAX YEAR 2021/2022' not in out
    assert out.index('TAX YEAR 2022/2023') < out.index('TAX YEAR 2023/2024')
    year1, year2 = out.split('TAX YEAR 2023/2024')

    assert re.search(r'Total +18\.00\n', year1)
    assert re.search(r'Total +34\.00\n', year2)

    assert 'DIVIDEND' not in out


def test_write_report_dividends() -> None:
    out = write_report(calculate(trades, eri_csv), dividends=True)

    lines = [line for line in out.splitlines() if line.startswith('DIVIDEND')]
    assert lines == [
        'DIVIDEND\t30/06/2022\tVUSA\t200\t10.00',
        'DIVIDEND\t30/06/2022\tVWRL\t100\t8.00',
        'DIVIDEND\t31/03/2023\tIE00B4L5Y983\t40\t10.00',
        'DIVIDEND\t30/06/2023\tVWRL\t150\t24.00',
    ]

    # The DIVIDEND lines should be consistent with the trades when fed back
    # into the CGT calculator
    calculator = Calculator()
    calculator.parse(io.StringIO(trades.replace('LSE:', '') + '\n'.join(lines) + '\n'))
    with warnings.catch_warnings():
        warnings.simplefilter('error')
        result = calculator.calculate()
    pool = result.section104_tables['VWRL']
    assert [update.delta_cost for update in pool if update.description.strip() == 'Notional distribution'] == [Decimal('8.00'), Decimal('24.00')]


def test_write_report_no_matches() -> None:
    entries = calculate('BUY 10/01/2022 FOO 100 1.00 0\n', eri_csv)
    assert entries == []

    out = write_report(entries, dividends=True)

    assert 'No matching securities found.' in out
    assert 'TAX YEAR' not in out
    assert 'DIVIDEND' not in out


def test_main(tmp_path:pathlib.Path) -> None:
    trades_path = tmp_path / 'trades.tsv'
    trades_path.write_text(trades)

    # GBP only, to avoid network access
    eri_path = tmp_path / 'eri.csv'
    eri_path.write_text('''\
TIDM,ISIN,ReportEndDate,Currency,ERI,DistributionDate
VUSA,IE00B3XXRP09,30/06/2022,GBP,0.05,31/12/2022
''')

    from eri import __file__ as eri_script

    out = subprocess.check_output(args=[
            sys.executable,
            eri_script,
            '--dividends',
            str(trades_path),
            str(eri_path),
        ],
        stderr=subprocess.DEVNULL,
        text=True)

    assert 'TAX YEAR 2022/2023' in out
    assert 'DIVIDEND\t30/06/2022\tVUSA\t200\t10.00\n' in out

    with pytest.raises(subprocess.CalledProcessError):
        subprocess.check_call(args=[
                sys.executable,
                eri_script,
                str(trades_path),
                str(tmp_path / 'missing.csv'),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
