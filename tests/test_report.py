#
# Copyright (c) 2026 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import io
import sys

import pytest

from report import TextReport


class TtyStringIO(io.StringIO):

    def isatty(self) -> bool:
        return True


@pytest.mark.skipif(sys.platform == 'win32', reason='no ANSI escapes on Windows')
def test_text_report_tty_heading() -> None:
    stream = TtyStringIO()
    report = TextReport(stream)
    report.write_heading('Heading')
    report.write_heading('Subheading', level=2)
    assert stream.getvalue() == '\33[1mHEADING\33[0m\n\n\33[1mSubheading\33[0m\n\n'


def test_text_report_heading() -> None:
    stream = io.StringIO()
    report = TextReport(stream)
    report.write_heading('Heading')
    report.write_paragraph('Paragraph.')
    report.write_heading('Subheading', level=2)
    assert stream.getvalue() == 'HEADING\n\nParagraph.\n\n\nSubheading\n\n'
