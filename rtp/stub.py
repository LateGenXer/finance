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
import analytics


st.set_page_config(
    page_title="Retirement Tax Planner",
    page_icon=":pound banknote:",
    layout="centered",
    initial_sidebar_state="collapsed",
    menu_items={
        "Get help": "https://github.com/LateGenXer/finance/discussions",
        "Report a Bug": "https://github.com/LateGenXer/finance/issues",
        "About": """Retirement Tax Planner

https://github.com/LateGenXer/finance/tree/main/rtp

Copyright (c) 2023 LateGenXer.

""",
    }
)

st.title('Retirement Tax Planner has moved!')

url = 'https://lategenxer.streamlit.app/Retirement_Tax_Planner'

st.warning(f'''
The _Retirement Tax Planner_ tool is now hosted on [{url}]({url}) together with other finance calculators.

Please update your bookmarks.
''', icon='⚠️')

analytics.html()
