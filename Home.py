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

st.markdown('''Welcome!

This site hosts several UK personal finance tools which I wrote primarily for myself but hope can be useful to others.

Please read the [disclaimer](/Disclaimer) and choose a tool on the left sidebar.

If you have issues or suggestions, open the menu by clicking on the top-right `⋮` button, followed by _"Report a bug"_ or _"Get help"_.
Alternatively, you can [send me a private message on Reddit](https://www.reddit.com/message/compose/?to=LateGenXer).
''')

common.analytics_html()
