#
# Copyright (c) 2023 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import os

import dmo


def test_write():
    dmo.write(os.devnull)
