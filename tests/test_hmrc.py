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


def test_current_exchange_rates() -> None:
    rates = data.hmrc.current_exchange_rates()
    assert {'EUR', 'JPY', 'USD'} <= rates.keys()

    # Filtering by currency, from any iterable
    filtered = data.hmrc.current_exchange_rates(currency for currency in ['EUR', 'JPY'])
    assert filtered == {'EUR': rates['EUR'], 'JPY': rates['JPY']}

    assert data.hmrc.current_exchange_rates([]) == {}

    with pytest.raises(KeyError):
        data.hmrc.current_exchange_rates(['XXX'])

    # Filtering must not modify the cached rates
    assert data.hmrc.current_exchange_rates() == rates
    assert len(rates) > 2
