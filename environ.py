#
# SPDX-License-Identifier: Unlicense
#


import os


ci = os.environ.get('CI', 'false').lower() == 'true'
