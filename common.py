#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import os

import streamlit as st
import streamlit.components.v1 as components



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
            "About": f"""LateGenXer's financial tools.

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
        if "PYTEST_CURRENT_TEST" not in os.environ else
        '<div class="statcounter">'
        '</div>'
    )

    components.html(html)
