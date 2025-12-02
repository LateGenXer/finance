#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import os.path
import subprocess


ci: bool = os.environ.get('CI', 'false').lower() == 'true'


production: bool = int(os.environ.get('PRODUCTION', '0')) != 0


def get_version() -> str:
    try:
        version = subprocess.check_output([
            'git',
                '-C', os.path.dirname(__file__),
            'show',
                '-s',
                '--date=format:%Y-%m-%d',
                '--format=%h (%cd)',
                'HEAD',
        ], text=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        if ci:
            raise
        else:
            version = 'unknown'
    else:
        version = version.rstrip()
    return version
