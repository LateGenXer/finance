#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import os


if int(os.environ.get('PULP', '0')) != 0:  # pragma: no cover
    from pulp import *  # type: ignore[import-untyped]
else:
    from .lp import *

del os
