#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import logging

import streamlit as st

import analytics


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    force=True,
)


# https://docs.streamlit.io/library/api-reference/utilities/st.set_page_config
st.set_page_config(
    page_title="LateGenXer's financial tools.",
    page_icon=":pound banknote:",
    layout="centered",
    initial_sidebar_state="expanded",
    menu_items={
        "Get help": "https://github.com/LateGenXer/finance/discussions",
        "Report a Bug": "https://github.com/LateGenXer/finance/issues",
        "About": """LateGenXer's finance tools.

https://github.com/LateGenXer/finance

Copyright (c) 2023 LateGenXer.

""",
    }
)

st.markdown('Welcome!  Choose a tool on the left sidebar.')

analytics.html()
