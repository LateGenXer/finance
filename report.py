#
# Copyright (c) 2024-2025 LateGenXer
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#


import base64
import html
import io
import logging
import sys
import textwrap


from typing import Sequence, Any, BinaryIO, TextIO
from abc import ABC, abstractmethod


class Report(ABC):

    def start(self, title:str) -> None:
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

    def __init__(self, stream:TextIO=sys.stdout):
        if sys.platform == 'win32' and not stream.isatty():
            stream.reconfigure(encoding='utf-8-sig')
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
        paragraph = '\n'.join(textwrap.wrap(paragraph, width=120))
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

    _css = '''
body {
  font-family: "Noto Sans Mono", monospace;
  font-optical-sizing: auto;
  font-weight: 400;
  font-style: normal;
  font-variation-settings: "wdth" 100;
  font-size: 0.75rem; /* 12px */
  background-color: white;
}

.fixed-right {
  position: fixed;
  top: 0;
  right: 0;
}

h1, h2, h3, h4 {
  font-size: 100%;
  font-weight: bold;
  font-style: normal;
  margin-top: 2em;
  margin-bottom: 1em;
}

h1 {
  text-align: center;
}

h1, h2, h3 {
  text-transform: uppercase;
}

.text-center { text-align: center; }
.text-right { text-align: right; }
.text-left { text-align: left; }
.text-justify { text-align: justify; }

.center-block { margin-left: auto; margin-right: auto; }

.visible-print-block { display: none; }
@media print {
  body { font-size: 10px; }
  .hidden-print { display: none !important; }
  .visible-print-block { display: block; }
}

.table {
  margin: 1em auto 1em 2ch;
  border-spacing: 0;
}

thead tr th {
  border-bottom: 1.5px solid;
  border-collapse: collapse;
}

tfoot tr th {
  border-top: 1.5px solid;
  border-collapse: collapse;
}

th, td {
  padding: 0.25em 1ch 0.25em 1ch;
}
'''

    def __init__(self, stream:TextIO):
        if sys.platform == 'win32' and not stream.isatty():
            stream.reconfigure(encoding='utf-8-sig')
        self.stream = stream

    def start(self, title:str) -> None:
        title = html.escape(title)
        # https://fonts.google.com/noto/specimen/Noto+Sans+Mono
        self.stream.write(f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Mono&amp;display=swap" rel="stylesheet">
<style>{self._css}</style>
</head>
<body>
<div class="fixed-right hidden-print">
<button class="btn btn-primary" onclick="window.print()">Print</button>
</div>
<div class="container-fluid">
<h1 class="visible-print-block">{title}</h1>
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


# https://py-pdf.github.io/fpdf2/Logging.html
logging.getLogger('fontTools.subset').level = logging.WARN


# https://py-pdf.github.io/fpdf2/
class PdfReport(Report):

    a4_width_mm = 210
    pt_to_mm = 25.4 / 72

    # https://fonts.google.com/noto
    font_family = 'NotoSansMono'
    fontsize_pt = 8
    fontsize_mm = fontsize_pt * pt_to_mm
    line_height = fontsize_mm * 1.25
    margin_bottom_mm = 10

    def __init__(self, stream:BinaryIO):
        self.stream = stream
        from fpdf import FPDF
        self.pdf = FPDF(orientation='P', unit='mm', format='A4')
        self.pdf.set_creator('https://lategenxer.github.io/')
        self.pdf.set_display_mode('fullwidth', 'continuous')
        self.pdf.set_auto_page_break(True, margin=self.margin_bottom_mm)
        self.pdf.add_font("NotoSansMono", style="",  fname="/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf")
        self.pdf.add_font("NotoSansMono", style="B", fname="/usr/share/fonts/truetype/noto/NotoSansMono-Bold.ttf")
        self.pdf.add_page()
        self.pdf.set_font(family=self.font_family, size=self.fontsize_pt)
        self.heading_sep = False

    def write_heading(self, heading:str, level:int=1) -> None:
        if level <= 1:
            heading = heading.upper()
        if self.heading_sep:
            self._ln()
        self.pdf.set_font(family=self.font_family, style='B', size=self.fontsize_pt)
        self.write_line(heading)
        self._ln()
        self.pdf.set_font(family=self.font_family, style='', size=self.fontsize_pt)
        self.heading_sep = False

    def write_paragraph(self, paragraph:str) -> None:
        for line in textwrap.wrap(paragraph, width=120): #XXX
            self.write_line(paragraph)
        self._ln()
        self.heading_sep = True

    def write_table(self, rows:list[list], header:Sequence[Any]|None=None, footer:Sequence[Any]|None=None, just:Sequence[Any]|None=None, indent:str='') -> None:  # pragma: no cover

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

        if header is not None:
            self.write_line(indent + sep.join(header).rstrip())
            self._rule(line_width, indent)
        for row in zip(*columns):
            self.write_line(indent + sep.join(row).rstrip())
        if footer is not None:
            self._rule(line_width, indent)
            self.write_line(indent + sep.join(footer).rstrip())

        self._ln()

        self.heading_sep = True

    def write_line(self, line:str) -> None:
        self.pdf.write(self.line_height, line)
        self._ln()

    def _rule(self, length:int, indent:str='') -> None:
        assert indent == ' '*len(indent)
        y1 = self.pdf.get_y()
        x1 = self.pdf.l_margin + self.pdf.c_margin + self.pdf.get_string_width(indent)
        x2 = x1 + self.pdf.get_string_width('─' * length)
        y = y1 + self.fontsize_mm * 0.5
        self.pdf.line(x1, y, x2, y)
        self._ln()

    def _ln(self) -> None:
        self.pdf.ln(self.line_height)

    def end(self) -> None:
        self.pdf.output(self.stream)  # type: ignore[call-overload]

    def as_html(self) -> str:
        assert isinstance(self.stream, io.BytesIO)
        data = self.stream.getvalue()

        b64 = base64.b64encode(data).decode('ASCII')

        return _html_template.replace("BASE64", b64)


_html_template = '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>PDF Viewer</title>
  <style>
    body { font-family: system-ui, -apple-system, 'Segoe UI', Roboto, Arial; margin: 16px; }
    .toolbar { display:flex; gap:8px; align-items:center; margin-bottom:12px; }
    .viewer { border: 1px solid #ddd; padding:8px; border-radius:8px; width:100%; }
    canvas { display:block; margin: 0 auto; }
    button, input { font-size:14px; padding:6px 8px; }
    input[type="number"] { width:64px; }
  </style>
</head>
<body>
  <div class="toolbar">
    <button id="prev">◀ Prev</button>
    <button id="next">Next ▶</button>
    <label>Page <input id="pageNum" type="number" min="1" value="1"> / <span id="pageCount">0</span></label>
    <button id="zoomOut">-</button>
    <button id="zoomIn">+</button>
    <label>Scale <span id="scaleLabel">1.0</span></label>
  </div>

  <div class="viewer">
    <canvas id="pdfCanvas"></canvas>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/pdfjs-dist@2.16.105/build/pdf.min.js"></script>
  <script>
    const data = atob("BASE64");

    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@2.16.105/build/pdf.worker.min.js';

    const canvas = document.getElementById('pdfCanvas');
    const ctx = canvas.getContext('2d');
    const prevBtn = document.getElementById('prev');
    const nextBtn = document.getElementById('next');
    const pageNumInput = document.getElementById('pageNum');
    const pageCountSpan = document.getElementById('pageCount');
    const zoomInBtn = document.getElementById('zoomIn');
    const zoomOutBtn = document.getElementById('zoomOut');
    const scaleLabel = document.getElementById('scaleLabel');

    let pdfDoc = null;
    let pageNum = 1;
    let scale = 1.0;

    const loadingTask = pdfjsLib.getDocument({ data: data });

    loadingTask.promise.then(function(pdf) {
      pdfDoc = pdf;
      pageCountSpan.textContent = pdfDoc.numPages;
      renderPage(pageNum);
    }).catch(function(err) {
      console.error('Error loading PDF:', err);
      document.body.insertAdjacentHTML('beforeend', '<p style="color:crimson">Error loading PDF: '+ (err && err.message ? err.message : err) + '</p>');
    });

    function renderPage(num) {
      pdfDoc.getPage(num).then(function(page) {
        const viewport = page.getViewport({ scale });
        canvas.width = Math.floor(viewport.width);
        canvas.height = Math.floor(viewport.height);

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const renderContext = {
          canvasContext: ctx,
          viewport: viewport
        };
        page.render(renderContext).promise.then(function() {
          // Render finished
        });

        pageNumInput.value = num;
        pageCountSpan.textContent = pdfDoc.numPages;
        scaleLabel.textContent = scale.toFixed(2);
      });
    }

    prevBtn.addEventListener('click', function() {
      if (pageNum <= 1) return;
      pageNum--;
      renderPage(pageNum);
    });

    nextBtn.addEventListener('click', function() {
      if (pageNum >= pdfDoc.numPages) return;
      pageNum++;
      renderPage(pageNum);
    });

    pageNumInput.addEventListener('change', function() {
      let v = parseInt(this.value, 10);
      if (isNaN(v) || v < 1) v = 1;
      if (v > pdfDoc.numPages) v = pdfDoc.numPages;
      pageNum = v;
      renderPage(pageNum);
    });

    zoomInBtn.addEventListener('click', function() {
      scale = Math.min(scale + 0.25, 4.0);
      renderPage(pageNum);
    });
    zoomOutBtn.addEventListener('click', function() {
      scale = Math.max(scale - 0.25, 0.25);
      renderPage(pageNum);
    });
  </script>
</body>
</html>
'''
