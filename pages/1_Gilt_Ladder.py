#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import os.path


script = os.path.abspath("gilts/app.py")


with open(script) as f:
    code = compile(f.read(), script, 'exec')
    glbls = globals().copy()
    glbls['__file__'] = script
    exec(code, glbls)
