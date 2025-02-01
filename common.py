#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import math

import streamlit as st
import streamlit.components.v1 as components

import environ

from data.rpi import RPI


# https://docs.streamlit.io/library/api-reference/utilities/st.set_page_config
def set_page_config(page_title, page_icon=":material/savings:", layout="centered", initial_sidebar_state="auto"):
    st.set_page_config(
        page_title=page_title,
        page_icon=page_icon,
        layout=layout,
        initial_sidebar_state=initial_sidebar_state,
        menu_items={
            "Get help": "https://github.com/LateGenXer/finance/discussions",
            "Report a Bug": "https://github.com/LateGenXer/finance/issues",
            "About": """LateGenXer's financial tools.

https://lategenxer.streamlit.app/

https://github.com/LateGenXer/finance

Copyright (c) 2024 LateGenXer.
""",
        }
    )


def analytics_html():
    # An invisible test marker, used when testing with Selenium to ensure a page ran till the end
    st.html('<span id="test-marker" style="display:none"></span>')

    # Use https://statcounter.com/ to understand which of the calculators are being
    # used, and therefore worthy of further attention.
    html = (
        '<script type="text/javascript">'
        'var sc_project=13036387; '
        'var sc_invisible=1; '
        'var sc_security="3699fd22"; '
        '</script>'
        '<script type="text/javascript" src="https://www.statcounter.com/counter/counter.js" async></script>'
        '<noscript>'
        '<div class="statcounter">'
        '<a title="Statcounter" href="https://statcounter.com/" target="_blank">'
        '<img class="statcounter" src="https://c.statcounter.com/13036387/0/3699fd22/1/" alt="Statcounter" referrerPolicy="no-referrer-when-downgrade">'
        '</a>'
        '</div>'
        '</noscript>'
        if environ.production else
        '<div class="statcounter">'
        '</div>'
    )

    components.html(html)


@st.cache_data(ttl=1*60*60, show_spinner='Getting latest RPI data...')
def get_latest_rpi():
    return RPI()


def rpi_hash(rpi_series: RPI):
    assert rpi_series.ref_year == RPI.ref_year
    return hash(tuple(rpi_series.series))


@st.cache_data(ttl=30*60, hash_funcs={RPI: rpi_hash}, show_spinner='Getting issued gilts...')
def get_issued_gilts(rpi_series):
    from gilts.gilts import Issued
    return Issued(rpi_series=rpi_series)


@st.cache_data(ttl=30*60, show_spinner='Getting latest gilt close prices...')
def get_latest_gilt_close_prices():
    from gilts.gilts import GiltPrices
    return GiltPrices.from_last_close()


@st.cache_data(ttl=5*60, show_spinner='Getting latest gilt offer prices...')
def get_latest_gilt_offer_prices():
    from gilts.gilts import GiltPrices
    return GiltPrices.from_latest(kind='offer')


def plot_yield_curve(df, yTitle, ySeries='Yield', cSeries='TIDM'):
    import altair as alt

    xAxisValues = [0, 1, 2, 3, 5, 10, 15, 30, 50]

    maxMaturity = int(math.ceil(df['Maturity'].max()))
    for v in xAxisValues[1:]:
        xDomainMax = v
        if v >= maxMaturity:
            break

    xAxisValues = [v for v in xAxisValues if v <= xDomainMax]

    xScale = alt.Scale(zero=True, domain=[0, xDomainMax])
    xAxis = alt.Axis(format=".2~f", values=xAxisValues, title="Maturity (years)")
    yDomainMin = min(int(math.floor(df[ySeries].min())), 0)
    yDomainMax = int(math.ceil(df[ySeries].max() + 0.25))
    yScale = alt.Scale(zero=True, domain=[yDomainMin, yDomainMax])
    yAxis = alt.Axis(format=".2~f", values=list(range(yDomainMin, yDomainMax + 1)), title=yTitle)

    chart = (
        alt.Chart(df)
        .mark_point()
        .encode(
            alt.X("Maturity:Q", scale=xScale, axis=xAxis),
            alt.Y(ySeries + ":Q", scale=yScale, axis=yAxis),
            alt.Color(cSeries + ":N", legend=None),
        )
    )
    st.altair_chart(chart, use_container_width=True)
