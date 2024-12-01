#!/usr/bin/env python3
#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import csv
import datetime
import io
import math
import operator
import logging

from zoneinfo import ZoneInfo

import requests

import streamlit as st
import pandas as pd

import nsandi_premium_bonds
import ukcalendar

from gilts.gilts import Issued, IndexLinkedGilt, GiltPrices
from xirr import xirr

from rtp.uk import cgt_rates

import common


common.set_page_config(
    page_title="Net Yields",
)

st.title('Net Yields')


logger = logging.getLogger('app')


#
# Parameters
#

gilt_types = {
    'Conventional': False,
    'Index-linked': True,
    'Both': None,
}

marginal_income_tax = st.select_slider("Marginal income tax rate:", value=0.40, options=(0.00, 0.20, 0.40, 0.45), format_func='{:.0%}'.format, key="marginal_income_tax")
col1, col2 = st.columns(2)
with col1:
    gilts_type = st.radio("Gilts type:", options=gilt_types.keys(), horizontal=True, key="gilts_type")
    index_linked = gilt_types[gilts_type]
with col2:
    maturity = st.number_input("Maturity (years):", value=5, min_value=1, max_value=100, key="maturity")


#
# Data
#


today = datetime.datetime.now(datetime.timezone.utc).date()
settlement_date = ukcalendar.next_business_day(today)

# transaction cost
# XXX: add option or remove
tc = 5*0
qt = 1000/100


cgt_rate = cgt_rates[0] if marginal_income_tax <= 0.20 else cgt_rates[1]


# https://www.bankofengland.co.uk/boeapps/database/help.asp?Back=Y&Highlight=CSV#CSV
@st.cache_data(ttl=24*60*60, show_spinner='Getting latest SONIA rate.')
def latest_sonia_rate():
    logger.info('Getting latest SONIA rate.')

    rate = math.nan
    date = None

    series = 'IUDSOIA'
    date_from = (today - datetime.timedelta(days=7))
    url = f'http://www.bankofengland.co.uk/boeapps/database/_iadb-FromShowColumns.asp?csv.x=yes&SeriesCodes={series}&UsingCodes=Y&CSVF=TN&Datefrom={date_from:%d/%b/%Y}&Dateto=now'
    headers = {'user-agent': 'Mozilla/5.0'}
    r = requests.get(url, headers=headers)
    if r.ok:
        for row in csv.DictReader(io.StringIO(r.text)):
            date = datetime.datetime.strptime(row['DATE'], '%d %b %Y').date()
            rate = float(row[series])

    # Scale from percentage
    rate *= .01

    # SONIA compounds daily
    # https://www.bankofengland.co.uk/markets/sonia-benchmark/sonia-key-features-and-policies
    rate = (1.0 + rate/365.0)**365 - 1.0

    return rate, date


@st.cache_data(ttl=24*60*60)
def latest_premium_bonds_rate(show_spinner='Getting latest NS&I Premium Bonds prizes.'):
    logger.info('Getting latest NS&I Premium Bonds prizes.')
    amount = 50000
    calculator = nsandi_premium_bonds.Calculator.from_latest()
    return calculator.median(amount) / amount, calculator.desc


#
# Calculations
#

data = []
msgs = []


if index_linked:
    msgs.append('_Real_ gross/net yields shown.')
if index_linked is None:
    msgs.append(f'_Nominal_ gross/net yields shown.  Assuming {IndexLinkedGilt.inflation_rate:.1%} inflation rate for index-linked gilts.')
msgs.append('Net yield ignores the '
'[Personal Savings Allowance](https://www.gov.uk/apply-tax-free-interest-on-savings#personal-savings-allowance) and the '
'[Capital Gains Tax allowance](https://www.gov.uk/capital-gains-tax/allowances).')
msgs.append('Equivalent gross yield is the standard cash savings account interest necessary to yield the same net interest.')

if not index_linked:
    premium_bonds_rate, premium_bonds_desc = latest_premium_bonds_rate()
    data.append(("Premium bonds", '', '', premium_bonds_rate, premium_bonds_rate))
    msgs.append(f"Premium Bonds' yield is the [median](https://www.moneysavingexpert.com/savings/premium-bonds/#tips-3) interest rate for a £50k investment, based on the [{premium_bonds_desc}](https://nsandi-corporate.com/news-research/news/nsi-announces-rate-changes-some-variable-and-fixed-term-products).")

    sonia_rate, sonia_date = latest_sonia_rate()
    data.append(('GBP Money Market Fund', '', '', sonia_rate, sonia_rate * (1 - marginal_income_tax)))
    msgs.append(f'GBP MMF and Lyxor Smart Overnight Return gross yield is based from [SONIA interest rate benchmark](https://www.bankofengland.co.uk/markets/sonia-benchmark) from {sonia_date.day} {sonia_date:%B} {sonia_date.year}.  Fees have _not_ been deducted.')


issued = Issued()
prices = GiltPrices()
maturity_limit = ukcalendar.shift_year(today, maturity)
for g in issued.filter(index_linked=index_linked, settlement_date=settlement_date):
    if g.maturity > maturity_limit:
        continue

    isin = g.isin
    tidm = prices.lookup_tidm(isin)
    clean_price = prices.get_price(tidm)
    accrued_interest = g.accrued_interest(settlement_date)
    dirty_price = g.dirty_price(clean_price, settlement_date)

    gross_yield = g.ytm(dirty_price, settlement_date)
    if index_linked:
        gross_yield = (1.0 + gross_yield)/(1.0 + IndexLinkedGilt.inflation_rate) - 1.0

    transactions = []
    purchase_price = qt*dirty_price + tc
    if index_linked:
        purchase_price /= g.index_ratio(settlement_date)
    transactions.append((settlement_date, -purchase_price))

    cf = list(g.cash_flows(settlement_date))
    for i in range(len(cf) - 1):
        d, v = cf[i]
        net_interest = qt*v - qt*(v - accrued_interest)*marginal_income_tax
        if index_linked:
            net_interest /= g.index_ratio(d)
        transactions.append((d, net_interest))
        accrued_interest = 0
    d, v = cf[-1]
    redemption_value = qt*v
    if index_linked:
        redemption_value /= g.index_ratio(d)
    transactions.append((d, redemption_value))

    dates, values = zip(*transactions)
    net_yield = xirr(values, dates)

    url = f'https://www.londonstockexchange.com/stock/{tidm}/united-kingdom'

    data.append((g.short_name() + ' Gilt', tidm, url, gross_yield, net_yield))


prices_date = prices.get_prices_date()
prices_date = prices_date.astimezone(ZoneInfo("Europe/London"))

msgs.append(f'Gilt prices from {prices_date.date()}, based on gilts in issue on the close of {issued.close_date}.')
if index_linked is not False:
    msgs.append(f'Using RPI published on {issued.rpi_series.release_date}.')


#
# Output
#


data = [
    (instrument, url, gross_yield*100.0, net_yield*100.0, net_yield*100.0/(1.0 - marginal_income_tax))
    for instrument, tidm, url, gross_yield, net_yield in data
]

data.sort(key=operator.itemgetter(-1), reverse=True)

df = pd.DataFrame(data, columns=['Instrument', 'TIDM', 'GrossYield', 'NetYield', 'EquivalentGrossYield'])

st.dataframe(
    df,
    use_container_width=True,
    height=768,
    hide_index=True,
    column_config={
        "Instrument": st.column_config.TextColumn(width="medium"),
        "TIDM": st.column_config.LinkColumn(display_text=r'https://www\.londonstockexchange\.com/stock/([^/]*).*', width='small'),
        "GrossYield": st.column_config.NumberColumn(label="Gross Yield", format="%.2f%%"),
        "NetYield": st.column_config.NumberColumn(label="Net Yield", format="%.2f%%"),
        "EquivalentGrossYield": st.column_config.NumberColumn(label="Equivalent Gross", format="%.2f%%"),
    },
)

st.info(''.join([f'- {msg}\n' for msg in msgs]), icon="ℹ️")


#
# Links
#

st.header('Resources')

st.markdown(
'''Further reading:
- https://monevator.com/money-market-funds/
- https://www.foxymonkey.com/best-places-cash/

Related tools:
- https://www.yieldgimp.com/
- https://www.dividenddata.co.uk/uk-gilts-prices-yields.py
''')

common.analytics_html()
