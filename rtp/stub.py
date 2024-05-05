#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


#
# Stub for old https://lategenxer-rtp.streamlit.app/
#

import streamlit as st


st.set_page_config(
    page_title="Retirement Tax Planner",
    page_icon=":pound banknote:",
    layout="wide",
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

url = 'https://lategenxer.streamlit.app/Retirement_Tax_Planner'
timer = 5

st.write(f'''
The Retirement Tax Planner tool moved to [{url}]({url})

Please update your bookmark.

You'll be automatically redirected in {timer} seconds.
''')

# https://discuss.streamlit.io/t/programmatically-send-user-to-a-web-page-with-no-click/21904/10
st.write(f'''<meta http-equiv="refresh" content="{timer}; URL='{url}'" />''', unsafe_allow_html=True)
