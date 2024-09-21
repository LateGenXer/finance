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

Personal data entered into the website will not persist across page reloads.
However some tools will give you the option to download or upload the relevant data.

The site uses analytic cookies for traffic analysis.
This helps me understand which tools are most used, and therefore which tools to further invest time into.
You can opt out of analytic cookies [here](https://statcounter.com/about/set-refusal-cookie/).

Please read the [disclaimer](/Disclaimer) and choose a tool on the left sidebar.

If you have issues or suggestions, open the menu by clicking on the top-right `⋮` button, followed by _"Report a bug"_ or _"Get help"_.
Alternatively, you can message me through [Reddit](https://www.reddit.com/message/compose/?to=LateGenXer).
''')

common.analytics_html()
