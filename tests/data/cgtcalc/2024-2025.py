#!/usr/bin/env python3


import csv
import json
import math
import os.path


gains = None, 0, 3000, 5000

losses = None, 0, 2000, 4000


def abbreviate(n: int|None) -> str:
    if n is None:
        return 'n'
    assert n % 1000 == 0
    return str(n // 1000)


def genereate(gain_1:int|None, loss_1:int|None, gain_2:int|None, loss_2:int|None) -> None:
    if (gain_1, loss_1, gain_2, loss_2) == (None, None, None, None):
        return

    name = os.path.join(os.path.dirname(__file__), f'2024-2025-g{abbreviate(gain_1)}l{abbreviate(loss_1)}-g{abbreviate(gain_2)}l{abbreviate(loss_2)}')

    q = 1000
    buy_price = 10

    gains_1 = 0
    losses_1 = 0
    gains_2 = 0
    losses_2 = 0

    disposals_1 = []
    disposals_2 = []

    proceeds_1 = 0
    proceeds_2 = 0
    costs_1 = 0
    costs_2 = 0

    with open(name + '.tsv', 'wt') as stream:
        if (gain_1 is not None or loss_1 is not None) and (gain_2 is not None or loss_2 is not None):
            stream.write('# WARNING: 2024/2025 pre- / post- Autumn budget support is still work in progress!\n')
        writer = csv.writer(stream, delimiter = '\t', lineterminator = '\n')
        if loss_1 is not None:
            assert (buy_price*q - loss_1) % q == 0
            loss_1_price = (buy_price*q - loss_1) // q
            writer.writerow(('BUY',   '06/01/2024',  'FOO',  q,  buy_price,    0))
            writer.writerow(('SELL',  '28/10/2024',  'FOO',  q,  loss_1_price, 0))
            proceeds_1 += q*loss_1_price
            costs_1 += q*buy_price
            losses_1 += loss_1
            disposals_1.append({ "date": "2024-10-28", "security": "FOO", "shares": q, "proceeds": q*loss_1_price, "gain": -loss_1 })
        if gain_1 is not None:
            assert (buy_price*q + gain_1) % q == 0
            gain_1_price = (buy_price*q + gain_1) // q
            writer.writerow(('BUY',   '06/01/2024',  'FOO',  q,  buy_price,    0))
            writer.writerow(('SELL',  '29/10/2024',  'FOO',  q,  gain_1_price, 0))
            proceeds_1 += q*gain_1_price
            costs_1 += q*buy_price
            gains_1 += gain_1
            disposals_1.append({ "date": "2024-10-29", "security": "FOO", "shares": q, "proceeds": q*gain_1_price, "gain": gain_1 })
        if gain_2 is not None:
            assert (buy_price*q + gain_2) % q == 0
            gain_2_price = (buy_price*q + gain_2) // q
            writer.writerow(('BUY',   '06/01/2024',  'FOO',  q,  buy_price,    0))
            writer.writerow(('SELL',  '30/10/2024',  'FOO',  q,  gain_2_price, 0))
            proceeds_2 += q*gain_2_price
            costs_2 += q*buy_price
            gains_2 += gain_2
            disposals_2.append({ "date": "2024-10-30", "security": "FOO", "shares": q, "proceeds": q*gain_2_price, "gain": gain_2 })
        if loss_2 is not None:
            assert (buy_price*q - loss_2) % q == 0
            loss_2_price = (buy_price*q - loss_2) // q
            writer.writerow(('BUY',   '06/01/2024',  'FOO',  q,  buy_price,    0))
            writer.writerow(('SELL',  '31/10/2024',  'FOO',  q,  loss_2_price, 0))
            disposals_2.append({ "date": "2024-10-31", "security": "FOO", "shares": q, "proceeds": q*loss_2_price, "gain": -loss_2 })
            proceeds_2 += q*loss_2_price
            costs_2 += q*buy_price
            losses_2 += loss_2

    # Allocate losses first to post-budget period
    losses = losses_1 + losses_2
    if (gain_1 is not None or loss_1 is not None) and (gain_2 is not None or loss_2 is not None):
        losses_2 = min(losses, gains_2)
        losses_1 = min(losses - losses_2, gains_1)
        losses_2 = losses - losses_1

    # Allocate allowance first to post-budget period
    taxable_gain_1 = gains_1 - losses_1
    taxable_gain_2 = gains_2 - losses_2
    if gain_1 is not None or loss_1 is not None:
        allowance_2 = min(max(taxable_gain_2, 0), 3000)
        allowance_1 = min(max(taxable_gain_1, 0 ), 3000 - allowance_2)
    else:
        allowance_1 = 0
    allowance_2 = 3000 - allowance_1
    assert allowance_1 + allowance_2 == 3000

    taxable_gain_1 = max(taxable_gain_1 - allowance_1, 0)
    taxable_gain_2 = max(taxable_gain_2 - allowance_2, 0)
    assert taxable_gain_1 + taxable_gain_2 == max(proceeds_1 + proceeds_2 - costs_1 - costs_2 - 3000, 0)

    carried_losses_1:int|float
    carried_losses_2:int|float
    if gain_2 is not None or loss_2 is not None:
        carried_losses_1 = math.nan
        carried_losses_2 = max(costs_1 + costs_2 - proceeds_1 - proceeds_2, 0)
    else:
        carried_losses_1 = max(costs_1 - proceeds_1, 0)
        carried_losses_2 = math.nan

    result_1 = {
        "tax_year": "2024/2025¹",
        "disposals": disposals_1,
        "proceeds": proceeds_1,
        "costs": costs_1,
        "gains": gains_1,
        "losses": losses_1,
        "allowance": allowance_1,
        "taxable_gain": taxable_gain_1,
        "carried_losses": carried_losses_1
    }

    result_2 = {
        "tax_year": "2024/2025²",
        "disposals": disposals_2,
        "proceeds": proceeds_2,
        "costs": costs_2,
        "gains": gains_2,
        "losses": losses_2,
        "allowance": allowance_2,
        "taxable_gain": taxable_gain_2,
        "carried_losses": carried_losses_2
    }

    result = []
    if gain_1 is not None or loss_1 is not None:
        result.append(result_1)
    if gain_2 is not None or loss_2 is not None:
        result.append(result_2)

    with open(name + '.json', 'wt') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')


def main() -> None:
    for gain_1 in gains:
        for loss_1 in losses:
            for gain_2 in gains:
                for loss_2 in losses:
                    genereate(gain_1, loss_1, gain_2, loss_2)


if __name__ == '__main__':
    main()
