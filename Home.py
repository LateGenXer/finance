#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import logging

import streamlit as st

import common


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    force=True,
)


common.set_page_config(
    page_title="LateGenXer's financial tools.",
    layout="centered",
    initial_sidebar_state="expanded"
)

st.title("LateGenXer's financial tools.")

st.markdown('Welcome!  Choose a tool on the left sidebar.')

common.analytics_html()
