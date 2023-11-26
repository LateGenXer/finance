'''Caching helpers.'''


#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import logging


logger = logging.getLogger('caching')
logger.setLevel(logging.DEBUG)


stub_use_count = 0


# Stub for streamlit.cache_data.  Replaced with the real function when running
# under Streamlit.
def cache_data(ttl=None):
    logger.debug('cache_date wrapper called', stack_info=True)
    global stub_use_count
    stub_use_count += 1
    return lambda fn: fn
