#
# Copyright (c) 2023-2024 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import os.path
import sys


sys.path.insert(0, os.path.abspath('rtp'))


script = os.path.abspath("rtp/app.py")


with open(script) as f:
    code = compile(f.read(), script, 'exec')
    glbls = globals().copy()
    glbls['__file__'] = script
    exec(code, glbls)
