#
# Copyright (c) 2026 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import re

import environ


def test_get_version() -> None:
    version = environ.get_version()
    assert version == 'unknown' or re.fullmatch(r'[0-9a-f]+ \(\d{4}-\d{2}-\d{2}\)', version)


def test_pages_url() -> None:
    assert environ.pages_url.endswith('/')
