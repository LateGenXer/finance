#
# Copyright (c) 2023-2025 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import csv
import datetime
import io
import math
import logging

from zoneinfo import ZoneInfo

import requests

import streamlit as st
import pandas as pd

import nsandi_premium_bonds
import ukcalendar

from data.boe import Curve, YieldCurve
from gilts.gilts import IndexLinkedGilt
from xirr import xirr

from tax.uk import cgt_rates

import common

from environ import production


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

mortgage_rate = st.number_input("Mortgage rate (%)", value=0., min_value=0., max_value=100., format='%.2f', key='mortgage_rate')


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
@st.cache_data(ttl=8*60*60, show_spinner='Getting latest SONIA rate.')
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


implied_inflation = int(st.query_params.get("implied_inflation", "0")) != 0


gross_yield_footnote = f'_{"Real" if index_linked else "Nominal"}_ gross/net yields shown.'
if index_linked is None:
    if implied_inflation:
        gross_yield_footnote += '  Assuming implied inflation from latest BoE yield curves for index-linked gilts.'
    else:
        gross_yield_footnote += f'  Assuming {IndexLinkedGilt.inflation_rate:.1%} inflation rate for index-linked gilts.'

premium_bonds_rate, premium_bonds_desc = latest_premium_bonds_rate()

sonia_rate, sonia_date = latest_sonia_rate()

if not index_linked:
    data.append(("Premium bonds⁴", '', '', premium_bonds_rate, premium_bonds_rate, 1.0/12.0))


    data.append(('GBP MMF - Income⁵', '', '', sonia_rate, sonia_rate * (1 - marginal_income_tax), 1.5/12.0))
    data.append(('GBP MMF - Capital Gain⁶', '', '', sonia_rate, sonia_rate * (1 - cgt_rate), 1.5/12.0))

    # https://www.amundietf.co.uk/en/professional/products/fixed-income/amundi-smart-overnight-return-ucits-etf-gbp-hedged-acc/lu1230136894
    # https://www.gov.uk/tax-on-dividends#how-much-tax-you-pay
    # https://www.gov.uk/government/publications/budget-2025-document/budget-2025-html#taxation-of-income-from-assets
    if not production:
        dividend_tax = {
            0.00: 0.0875 + .02,
            0.20: 0.0875 + .02,
            0.40: 0.3375 + .02,
            0.45: 0.3975,
        }[marginal_income_tax]
        data.append(('GBP MMF - Dividend', '', '', sonia_rate, sonia_rate * (1 - dividend_tax), 1.5/12.0))

    if mortgage_rate:
        mortgage_rate = float(mortgage_rate) / 100.0
        data.append(('Mortgage Overpayment', '', '', mortgage_rate, mortgage_rate, 0.0))


rpi_series = common.get_latest_rpi()
inflation_curve = YieldCurve('Inflation')

# Extend RPI series using impled inflation curve
if index_linked is None and implied_inflation:
    # TODO: Move this as a factory method of the RPI class
    n0 = len(rpi_series.series) -1
    date0 = datetime.date(year=rpi_series.ref_year + n0 // 12, month=0 % 12 + 1, day=1)
    rpi0 = rpi_series.series[-1]
    while True:
        n1 = len(rpi_series.series)
        date1 = datetime.date(year=rpi_series.ref_year + n1 // 12, month=n1 % 12 + 1, day=1)
        years_exact = (n1 - n0) / 12
        years_round = ((n1 - n0) + 5) // 6 * 0.5
        if years_round > 40.0:
            break
        rpi1 = rpi0 * (1 + inflation_curve(years_round)) ** years_exact
        rpi_series.series.append(rpi1)


issued = common.get_issued_gilts(rpi_series)


if int(st.query_params.get("latest", "0")) != 0:
    prices = common.get_latest_gilt_offer_prices()
else:
    prices = common.get_latest_gilt_close_prices()


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
        tax_rate = marginal_income_tax
        if d >= datetime.date(2027, 4, 6):
            # https://www.gov.uk/government/publications/budget-2025-document/budget-2025-html#taxation-of-income-from-assets
            tax_rate += .02
        net_interest = qt*v - qt*(v - accrued_interest)*tax_rate
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

    maturity_ = (g.maturity - issued.close_date).days / 365.25

    url = f'https://www.londonstockexchange.com/stock/{tidm}/united-kingdom'

    data.append((g.short_name() + ' Gilt⁷', tidm, url, gross_yield, net_yield, maturity_))


prices_date = prices.get_prices_date()
prices_date = prices_date.astimezone(ZoneInfo("Europe/London"))

gilts_footnote = f'Gilt prices from {prices_date.date()}, based on gilts in issue on the close of {issued.close_date}.'
if index_linked is not False:
    gilts_footnote += f'  Using RPI published on {issued.rpi_series.release_date}.'


#
# Output
#


st.divider()

rows = [
    (instrument, tidm, url, gross_yield*100.0, net_yield*100.0, net_yield*100.0/(1.0 - marginal_income_tax), maturity_)
    for instrument, tidm, url, gross_yield, net_yield, maturity_ in data
]

df = pd.DataFrame(rows, columns=['Instrument', 'TIDM', 'URL', 'GrossYield', 'NetYield', 'EquivalentGrossYield', 'Maturity'])
df.sort_values(by='NetYield', ascending=False, inplace=True, ignore_index=True)

st.dataframe(
    df,
    width='stretch',
    height=768,
    hide_index=True,
    column_config={
        "Instrument": st.column_config.TextColumn(width="medium"),
        "TIDM": None,
        "URL": st.column_config.LinkColumn(label='TIDM', display_text=r'https://www\.londonstockexchange\.com/stock/([^/]*).*', width='small'),
        "GrossYield": st.column_config.NumberColumn(label="Gross Yield¹", format="%.2f%%"),
        "NetYield": st.column_config.NumberColumn(label="Net Yield²", format="%.2f%%"),
        "EquivalentGrossYield": st.column_config.NumberColumn(label="Equivalent Gross³", format="%.2f%%"),
        "Maturity": None,
    },
)

with st.expander('Notes'):
    st.markdown(f"""
1. {gross_yield_footnote}
2. Net yield deducts tax but ignores the [Personal Savings Allowance](https://www.gov.uk/apply-tax-free-interest-on-savings#personal-savings-allowance) and the [Capital Gains Tax allowance](https://www.gov.uk/capital-gains-tax/allowances).
3. Equivalent gross yield is the standard cash savings account interest necessary to yield the same net yield.
4. Premium Bonds' yield is the [median](https://www.moneysavingexpert.com/savings/premium-bonds/#tips-3) interest rate for a £50k investment, based on the [{premium_bonds_desc}](https://www.nsandi.com/get-to-know-us/monthly-prize-allocation).
5. GBP Money Market Fund (MMF) gross yield is based from [SONIA interest rate benchmark](https://www.bankofengland.co.uk/markets/sonia-benchmark) from {sonia_date.day} {sonia_date:%B} {sonia_date.year}, ignoring fees.
6. GBP MMF _Capital Gain_ figure assumes funds are held for a short time, without overlapping income distribution or [Excess Reportable Income (ERI)](https://www.gov.uk/government/publications/offshore-funds-self-assessment-helpsheet-hs265/hs265-offshore-funds), therefore being only liable for Capital Gains Tax.
7. {gilts_footnote}
""")


st.divider()
st.subheader('Yield Curves')

ois_curve = YieldCurve('OIS')
ois_net_curve = Curve(ois_curve.xp, ois_curve.yp * (1.0 - marginal_income_tax))

common.plot_yield_curve(df, yTitle='Gross Yield (%)', ySeries='GrossYield', cSeries='Instrument', ois=ois_curve)
common.plot_yield_curve(df, yTitle='Net Yield (%)', ySeries='NetYield', cSeries='Instrument', ois=ois_net_curve)


#
# Links
#

st.header('Resources')

st.markdown(
'''Further reading:
- https://monevator.com/money-market-funds/
- https://www.foxymonkey.com/best-places-cash/

Related tools:
- https://giltsyield.com/tax/
- https://www.dividenddata.co.uk/uk-gilts-prices-yields.py
- https://www.yieldgimp.com/
''')

common.analytics_html()
