#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import pytest

import data.hmrc

from decimal import Decimal


@pytest.mark.parametrize("year,month,currency,rate", [
    (2021, 1, 'EUR', Decimal('1.1075')),
    (2024, 8, 'USD', Decimal('1.3033')),
])
def test_exchange_rates(year:int, month:int, currency:str, rate:Decimal) -> None:
    rates = data.hmrc.exchange_rates(year, month)
    assert rates[currency] == rate


@pytest.mark.parametrize("currency", [
    'EUR',
    'JPY',
    'USD',
])
def test_exchange_rate(currency:str) -> None:
    rate = data.hmrc.exchange_rate(currency)
    assert rate > Decimal(0)
