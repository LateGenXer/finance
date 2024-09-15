#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


#
# Stub for old https://lategenxer-rtp.streamlit.app/
#

import sys
import os

import streamlit as st

sys.path.insert(0, os.getcwd())
import common


common.set_page_config(
    page_title="Retirement Tax Planner",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.title('Retirement Tax Planner has moved!')

url = 'https://lategenxer.streamlit.app/Retirement_Tax_Planner'

st.warning(f'''
_Retirement Tax Planner_ is now hosted on [{url}]({url}) together with other finance calculators.

Please update your bookmarks.
''', icon='⚠️')

common.analytics_html()
