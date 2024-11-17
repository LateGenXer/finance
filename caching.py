'''Caching helpers.'''


#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import logging


__all__ = [
    'cache_data',
]


logger = logging.getLogger('caching')
logger.setLevel(logging.DEBUG)


# Stub for streamlit.cache_data.
def cache_data(ttl=None):
    logger.debug('cache_data wrapper called', stack_info=True)
    return lambda fn: fn


# Use Streamlit's cache_data when serving
try:
    from streamlit import runtime
except ImportError:  # pragma: no cover
    pass
else:
    if runtime.exists():
        from streamlit import cache_data
