#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import importlib
import os.path
import sys

import streamlit as st


# https://docs.streamlit.io/library/api-reference/utilities/st.set_page_config
st.set_page_config(
    page_title="LateGenXer's financial tools.",
    page_icon=":pound banknote:",
    layout="centered",
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
