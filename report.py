#
# Copyright (c) 2024-2025 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import html
import sys


from typing import Sequence, Any, TextIO
from abc import ABC, abstractmethod


class Report(ABC):

    def start(self) ->None:
        pass

    @abstractmethod
    def write_heading(self, heading:str, level:int=1) -> None:  # pragma: no cover
        raise NotImplementedError

    @abstractmethod
    def write_paragraph(self, paragraph:str) -> None:  # pragma: no cover
        raise NotImplementedError

    @abstractmethod
    def write_table(self, rows:list[list], header:Sequence[Any]|None=None, footer:Sequence[Any]|None=None, just:Sequence[Any]|None=None, indent:str='') -> None:  # pragma: no cover
        raise NotImplementedError

    @staticmethod
    def format(field:Any) -> str:
        if field is None or field != field:
            return ''
        else:
            return str(field)

    def end(self) -> None:
        pass


class TextReport(Report):

    def __init__(self, stream:TextIO):
        self.stream = stream
        self.heading_sep = ''

    def write_heading(self, heading:str, level:int=1) -> None:
        if level <= 1:
            heading = heading.upper()
        if sys.platform != 'win32' and self.stream.isatty():
            # Ansi escape
            _csi = '\33['
            normal = _csi + '0m'
            bold = _csi + '1m'
            heading = bold + heading + normal
        self.stream.write(self.heading_sep + heading + '\n\n')
        self.heading_sep = ''

    def write_paragraph(self, paragraph:str) -> None:
        self.stream.write(paragraph + '\n\n')
        self.heading_sep = '\n'

    def write_table(self, rows:list[list], header:Sequence[Any]|None=None, footer:Sequence[Any]|None=None, just:Sequence[Any]|None=None, indent:str='') -> None:  # pragma: no cover
        stream = self.stream

        columns = [list(col) for col in zip(*rows)]
        if header is not None:
            header = list(header)
            assert len(header) == len(columns)
        if footer is not None:
            footer = list(footer)
            assert len(footer) == len(columns)
        if just is None:
            just = [str.center]*len(columns)
        else:
            assert len(just) == len(columns)
            m = {
                'c': str.center,
                'l': str.ljust,
                'r': str.rjust,
            }
            just = [m[j] for j in just]

        widths = []
        for c in range(len(columns)):
            width = 0
            if header is not None:
                header[c] = self.format(header[c])
                width = max(width, len(header[c]))
            if footer is not None:
                footer[c] = self.format(footer[c])
                width = max(width, len(footer[c]))
            column = columns[c]
            for r in range(len(column)):
                cell = column[r]
                cell = self.format(cell)
                column[r] = cell
                width = max(width, len(cell))
            if header is not None:
                header[c] = just[c](header[c], width)
            for r in range(len(column)):
                column[r] = just[c](column[r], width)
            if footer is not None:
                footer[c] = just[c](footer[c], width)
            widths.append(width)

        sep = '  '

        line_width = len(sep.join([' '*width for width in widths]))
        rule = '─' * line_width

        if header is not None:
            stream.write(indent + sep.join(header).rstrip() + '\n')
            stream.write(indent + rule + '\n')
        for row in zip(*columns):
            stream.write(indent + sep.join(row).rstrip() + '\n')
        if footer is not None:
            stream.write(indent + rule + '\n')
            stream.write(indent + sep.join(footer).rstrip() + '\n')

        stream.write('\n')

        self.heading_sep = '\n'


class HtmlReport(Report):

    def __init__(self, stream:TextIO):
        self.stream = stream

    def start(self) -> None:
        # https://getbootstrap.com/docs/3.4/getting-started/#template
        self.stream.write('''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Capital Gains Calculation</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@3.4.1/dist/css/bootstrap.min.css" integrity="sha384-HSMxcRTRxnN+Bdg0JdbxYKrThecOKuH5zCYotlSAcp1+c8xmyTe9GYg1l9a69psu" crossorigin="anonymous">
<style>
.fixed-right {
  position: fixed;
  top: 0;
  right: 0;
}
</style>
</head>
<body>
<script src="https://code.jquery.com/jquery-1.12.4.min.js" integrity="sha384-nvAa0+6Qg9clwYCGGPpDQLVpLNn0fRaROjHqs13t4Ggj3Ez50XnGQqc/r8MhnRDZ" crossorigin="anonymous"></script>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@3.4.1/dist/js/bootstrap.min.js" integrity="sha384-aJ21OjlMXNL5UyIl/XNwTMqvzeRMZH2w8c5cRVpzpU8Y5bApTppSuUkhZXN0VxHd" crossorigin="anonymous"></script>
<div class="fixed-right hidden-print">
<button class="btn btn-primary" onclick="window.print()">Print</button>
</div>
<div class="container-fluid">
<h1 class="visible-print-block">Capital Gains Calculation</h1>
''')

    def write_heading(self, heading:str, level:int=1) -> None:
        level += 1
        heading = html.escape(heading)
        self.stream.write(f'\n<h{level}>{heading}</h{level}>\n\n')

    def write_paragraph(self, paragraph:str) -> None:
        paragraph = html.escape(paragraph)
        self.stream.write(f'<p>{paragraph}</p>\n\n')

    @staticmethod
    def format_and_escape(field:Any) -> str:
        field = Report.format(field)
        field = html.escape(field)
        return field

    def write_table(self, rows:list[list], header:Sequence[Any]|None=None, footer:Sequence[Any]|None=None, just:Sequence[Any]|None=None, indent:str='') -> None:  # pragma: no cover
        fmt = self.format_and_escape

        if just is None:
            just = ['text-center'] * 99
        else:
            m = {
                'c': 'text-center',
                'l': 'text-left',
                'r': 'text-right',
            }
            just = [m[j] for j in just]

        self.stream.write('<div class="table-responsive">\n')
        # https://stackoverflow.com/questions/19857469/center-align-content-using-bootstrap#comment29535494_19858083
        self.stream.write('<table class="table table-condensed center-block" style="width: initial; display: table;">\n')

        if header:
            self.stream.write('<thead><tr>' + ''.join([f'<th class="{j}">{fmt(field)}</th>' for field, j in zip(header, just)]) + '</tr></thead>\n')
        self.stream.write('<tbody>\n')
        for row in rows:
            self.stream.write('<tr>' + ''.join([f'<td class="{j}">{fmt(field)}</td>' for field, j in zip(row, just)]) + '</tr>\n')
        self.stream.write('</tbody>\n')

        if footer:
            self.stream.write('<tfoot><tr>' + ''.join([f'<th class="{j}">{fmt(field)}</th>' for field, j in zip(footer, just)]) + '</tr></tfoot>\n')

        self.stream.write('</table>\n')
        self.stream.write('</div>\n')

    def end(self) -> None:
        self.stream.write('\n')
        self.stream.write('</div>\n')
        self.stream.write('</body>\n')
        self.stream.write('</html>\n')
