#
# Copyright (c) 2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import os

import streamlit.components.v1 as components


# Use https://statcounter.com/ to understand which of the calculators are being
# used, and therefore worthy of further attention.
def html():

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
