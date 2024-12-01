#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import os
import subprocess


ci = os.environ.get('CI', 'false').lower() == 'true'


production = int(os.environ.get('PRODUCTION', '0'))


def get_version():
    try:
        version = subprocess.check_output([
            'git', 'show', '-s', '--date=format:%Y-%m-%d', '--format=%h (%cd)', 'HEAD',
        ], text=True)
    except subprocess.CalledProcessError:
        if ci:
            raise
        else:
            version = 'unknown'
    else:
        version = version.rstrip()
    return version
