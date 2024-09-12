#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import os

import streamlit as st


# Use https://statcounter.com/ to understand which of the calculators are being
# used, and therefore worthy of further attention.
def html():

    html = (
        '<div class="statcounter">'
        '<a title="Web Analytics Made Easy - Statcounter" href="https://statcounter.com/" target="_blank">'
        '<img class="statcounter" src="https://c.statcounter.com/13036387/0/3699fd22/1/" alt="Web Analytics Made Easy - Statcounter" referrerPolicy="no-referrer-when-downgrade">'
        '</a>'
        '</div>'
        if "PYTEST_CURRENT_TEST" not in os.environ else
        '<div class="statcounter">'
        '</div>'
    )

    st.markdown(html, unsafe_allow_html=True)
