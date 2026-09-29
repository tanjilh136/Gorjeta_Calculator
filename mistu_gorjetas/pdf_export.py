"""PDF rendering (ReportLab) for the weekly and final exports. Landscape A4."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import APP_NAME, CREDIT, paths
from .i18n import fmt_date, fmt_datetime, fmt_day_month, tr, weekday_short
from .money import format_euro, format_percent
from .reports import ABSENT, NO_DATA, FinalReport, WeeklyReport

PAGE = landscape(A4)
MARGIN_X = 28
MARGIN_TOP = 64
MARGIN_BOTTOM = 40
CONTENT_W = PAGE[0] - 2 * MARGIN_X

HEADER_BG = colors.HexColor("#1F4E5A")
HEADER_SUB_BG = colors.HexColor("#2F6B78")
ZEBRA = colors.HexColor("#F2F6F7")
TOTAL_BG = colors.HexColor("#DDE7EA")
GRID = colors.HexColor("#B8C7CC")
ABSENT_COLOR = colors.HexColor("#B03A2E")
MUTED = colors.HexColor("#8A9599")
TEXT = colors.HexColor("#1B1F21")

MAX_WEEKS_PER_PAGE = 6

_fonts: tuple[str, str] | None = None
ABSENT_MARK = "✗"
NO_DATA_MARK = "—"


def _register_fonts() -> tuple[str, str]:
    """DejaVu Sans (bundled) has the €, ✗ and — glyphs; fall back to Helvetica."""
    global _fonts, ABSENT_MARK
    if _fonts is None:
        font_dir = paths.resource_dir() / "fonts"
        try:
            pdfmetrics.registerFont(TTFont("MG-Regular", str(font_dir / "DejaVuSans.ttf")))
            pdfmetrics.registerFont(TTFont("MG-Bold", str(font_dir / "DejaVuSans-Bold.ttf")))
            _fonts = ("MG-Regular", "MG-Bold")
        except Exception:
            _fonts = ("Helvetica", "Helvetica-Bold")
            ABSENT_MARK = "x"
    return _fonts


def _fit_font(texts: list[str], font: str, width: float, base: float, minimum: float = 5.0) -> float:
    widest = max((pdfmetrics.stringWidth(t, font, 1.0) for t in texts), default=0)
    if widest <= 0:
        return base
    return max(minimum, min(base, (width - 6) / widest))


def _truncate(text: str, font: str, size: float, width: float) -> str:
    width -= 6
    if pdfmetrics.stringWidth(text, font, size) <= width:
        return text
    while text and pdfmetrics.stringWidth(text + "…", font, size) > width:
        text = text[:-1]
    return text.rstrip() + "…"


def _make_canvas(title: str, subtitle: str, generated: str):
    regular, bold = _register_fonts()

    class NumberedCanvas(rl_canvas.Canvas):
        """Draws header/footer after layout so that 'page X/Y' is known."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._pages = []

        def showPage(self):
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._pages)
            for state in self._pages:
                self.__dict__.update(state)
                self._decorate(total)
                super().showPage()
            super().save()

        def _decorate(self, total: int) -> None:
            w, h = PAGE
            self.saveState()
            self.setFillColor(HEADER_BG)
            self.setFont(bold, 16)
            self.drawString(MARGIN_X, h - 34, APP_NAME)
            self.setFillColor(TEXT)
            self.setFont(regular, 10)
            self.drawString(MARGIN_X, h - 50, subtitle)
            self.setFont(bold, 11)
            self.drawRightString(w - MARGIN_X, h - 34, title)
            self.setStrokeColor(HEADER_BG)
            self.setLineWidth(1)
            self.line(MARGIN_X, h - 56, w - MARGIN_X, h - 56)

            self.setStrokeColor(GRID)
            self.setLineWidth(0.5)
            self.line(MARGIN_X, 28, w - MARGIN_X, 28)
            self.setFillColor(MUTED)
            self.setFont(regular, 8)
            self.drawString(MARGIN_X, 17, CREDIT)
            self.drawCentredString(w / 2, 17, tr("pdf.generated", when=generated))
            self.drawRightString(
                w - MARGIN_X, 17, tr("pdf.page", x=self._pageNumber, y=total)
            )
            self.restoreState()

    return NumberedCanvas


def _build(path: Path, story: list, title: str, subtitle: str) -> None:
    generated = fmt_datetime(datetime.now())
    doc = SimpleDocTemplate(
        str(path),
        pagesize=PAGE,
        leftMargin=MARGIN_X,
        rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
        title=f"{APP_NAME} – {title} – {subtitle}",
        author=CREDIT.replace("Designed by ", ""),
        creator=APP_NAME,
        producer=APP_NAME,
        subject=subtitle,
    )
    doc.build(story, canvasmaker=_make_canvas(title, subtitle, generated))


def _header_style(font: str, size: float) -> ParagraphStyle:
    return ParagraphStyle(
        "hdr", fontName=font, fontSize=size, leading=size * 1.2,
        textColor=colors.white, alignment=TA_CENTER,
    )


def _legend(text: str) -> Paragraph:
    regular, _ = _register_fonts()
    style = ParagraphStyle("legend", fontName=regular, fontSize=7, leading=9, textColor=MUTED)
    return Paragraph(text, style)


def _base_style(n_header_rows: int, n_rows: int, font_size: float) -> list:
    regular, bold = _register_fonts()
    last = n_rows - 1
    style = [
        ("FONT", (0, 0), (-1, -1), regular, font_size),
        ("TEXTCOLOR", (0, 0), (-1, -1), TEXT),
        ("FONT", (0, 0), (-1, n_header_rows - 1), bold, font_size),
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, n_header_rows - 1), colors.white),
        ("ALIGN", (0, 0), (-1, n_header_rows - 1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, n_header_rows), (-1, -1), "RIGHT"),
        ("ALIGN", (0, n_header_rows), (0, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.25, GRID),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("FONT", (0, last), (-1, last), bold, font_size),
        ("BACKGROUND", (0, last), (-1, last), TOTAL_BG),
        ("LINEABOVE", (0, last), (-1, last), 1, HEADER_BG),
    ]
    if n_header_rows > 1:
        style.append(("BACKGROUND", (0, 1), (-1, n_header_rows - 1), HEADER_SUB_BG))
    for r in range(n_header_rows, last):
        if (r - n_header_rows) % 2 == 1:
            style.append(("BACKGROUND", (0, r), (-1, r), ZEBRA))
    return style


# ---------------------------------------------------------------- weekly
def weekly_filename(report: WeeklyReport) -> str:
    return f"Gorjetas_Semana_{report.monday.isoformat()}.pdf"


def render_weekly(report: WeeklyReport, path: Path) -> None:
    regular, bold = _register_fonts()
    title = tr("pdf.weekly")
    subtitle = f"{fmt_date(report.monday)} – {fmt_date(report.sunday)}"

    head0 = [tr("staff")]
    head1 = [""]
    for d in report.days:
        head0 += [f"{weekday_short(d)} {fmt_day_month(d)}", ""]
        head1 += [tr("cash"), tr("card")]
    head0 += [tr("pdf.week_total"), ""]
    head1 += [tr("cash"), tr("card")]

    body = []
    marks = []  # (col, row, kind)
    for r, row in enumerate(report.rows):
        line = [row.staff.name]
        for i, cell in enumerate(row.cells):
            if cell.state == NO_DATA:
                line += [NO_DATA_MARK, NO_DATA_MARK]
                marks.append((1 + 2 * i, r, NO_DATA))
            elif cell.state == ABSENT:
                line += [ABSENT_MARK, ABSENT_MARK]
                marks.append((1 + 2 * i, r, ABSENT))
            else:
                line += [format_euro(cell.cash), format_euro(cell.card)]
        line += [format_euro(row.total_cash), format_euro(row.total_card)]
        body.append(line)

    totals = [tr("pdf.totals")]
    for i, (c, k) in enumerate(report.day_totals):
        if report.has_data[i]:
            totals += [format_euro(c), format_euro(k)]
        else:
            totals += [NO_DATA_MARK, NO_DATA_MARK]
    totals += [format_euro(report.total_cash), format_euro(report.total_card)]

    staff_w = 112
    col_w = (CONTENT_W - staff_w) / 16
    values = [v for line in body + [totals] for v in line[1:]] + head1[1:]
    size = _fit_font(values, bold, col_w, 7.5)
    head_size = _fit_font([h for h in head0[1:] if h], bold, col_w * 2, 7.5)
    names = [_truncate(line[0], regular, size + 0.5, staff_w) for line in body]
    for line, name in zip(body, names):
        line[0] = name

    data = [head0, head1] + body + [totals]
    t = Table(data, colWidths=[staff_w] + [col_w] * 16, repeatRows=2, hAlign="LEFT")
    style = _base_style(2, len(data), size)
    style += [
        ("SPAN", (0, 0), (0, 1)),
        ("BACKGROUND", (0, 0), (0, 1), HEADER_BG),
        ("FONT", (0, 0), (-1, 0), bold, head_size),
        ("FONT", (0, 2), (0, -2), regular, size + 0.5),
    ]
    for i in range(8):
        style.append(("SPAN", (1 + 2 * i, 0), (2 + 2 * i, 0)))
        style.append(("LINEAFTER", (2 + 2 * i, 0), (2 + 2 * i, -1), 0.9, HEADER_BG))
    style.append(("LINEAFTER", (0, 0), (0, -1), 0.9, HEADER_BG))
    for col, r, kind in marks:
        row_idx = r + 2
        color = ABSENT_COLOR if kind == ABSENT else MUTED
        style += [
            ("ALIGN", (col, row_idx), (col + 1, row_idx), "CENTER"),
            ("TEXTCOLOR", (col, row_idx), (col + 1, row_idx), color),
        ]
    for i, has in enumerate(report.has_data):
        if not has:
            style += [
                ("ALIGN", (1 + 2 * i, len(data) - 1), (2 + 2 * i, len(data) - 1), "CENTER"),
                ("TEXTCOLOR", (1 + 2 * i, len(data) - 1), (2 + 2 * i, len(data) - 1), MUTED),
            ]
    t.setStyle(TableStyle(style))

    story = [t, Spacer(1, 6), _legend(tr("pdf.legend_weekly").replace("✗", ABSENT_MARK))]
    _build(path, story, title, subtitle)


# ----------------------------------------------------------------- final
def final_filename(report: FinalReport) -> str:
    return f"Gorjetas_Final_{report.start.isoformat()}_{report.end.isoformat()}.pdf"


def render_final(report: FinalReport, path: Path) -> None:
    regular, bold = _register_fonts()
    title = tr("pdf.final")
    subtitle = f"{fmt_date(report.start)} – {fmt_date(report.end)}"
    pct = format_percent(report.deduction_pct)
    n_weeks = len(report.weeks)

    chunks = [
        list(range(i, min(i + MAX_WEEKS_PER_PAGE, n_weeks)))
        for i in range(0, n_weeks, MAX_WEEKS_PER_PAGE)
    ] or [[]]

    story: list = []
    for ci, weeks in enumerate(chunks):
        last_chunk = ci == len(chunks) - 1
        if ci > 0:
            story.append(PageBreak())
        if len(chunks) > 1:
            part_style = ParagraphStyle("part", fontName=bold, fontSize=9, leading=12, textColor=HEADER_BG)
            story += [
                Paragraph(tr("pdf.part", a=weeks[0] + 1, b=weeks[-1] + 1, n=n_weeks), part_style),
                Spacer(1, 4),
            ]
        story += [_final_table(report, weeks, last_chunk, pct), Spacer(1, 6)]
        if last_chunk:
            story.append(_legend(tr("pdf.legend_final")))
    _build(path, story, title, subtitle)


def _final_table(report: FinalReport, weeks: list[int], with_summary: bool, pct: str) -> Table:
    regular, bold = _register_fonts()
    staff_w = 112
    summary_w = 68 if with_summary else 0
    n_summary = 3 if with_summary else 0
    col_w = (CONTENT_W - staff_w - n_summary * summary_w) / max(1, 2 * len(weeks))
    col_w = min(col_w, 70)

    head0: list = [tr("staff")]
    head1: list = [""]
    for wi in weeks:
        ws, we = report.weeks[wi]
        head0 += [f"{tr('week')} {wi + 1}\n({fmt_day_month(ws)}–{fmt_day_month(we)})", ""]
        head1 += [tr("cash"), tr("card")]
    if with_summary:
        head0 += [tr("total"), tr("pdf.deduction_col", pct=pct), tr("receivable")]
        head1 += ["", "", ""]

    body = []
    for row in report.rows:
        line = [row.staff.name]
        for wi in weeks:
            if report.week_has_data[wi]:
                c, k = row.weeks[wi]
                line += [format_euro(c), format_euro(k)]
            else:
                line += [NO_DATA_MARK, NO_DATA_MARK]
        if with_summary:
            line += [format_euro(row.total), format_euro(row.deduction), format_euro(row.receivable)]
        body.append(line)

    totals = [tr("pdf.totals")]
    for wi in weeks:
        if report.week_has_data[wi]:
            c, k = report.week_totals[wi]
            totals += [format_euro(c), format_euro(k)]
        else:
            totals += [NO_DATA_MARK, NO_DATA_MARK]
    if with_summary:
        totals += [format_euro(report.total), format_euro(report.deduction), format_euro(report.receivable)]

    week_values = [v for line in body + [totals] for v in line[1:1 + 2 * len(weeks)]] + head1[1:]
    summary_values = [v for line in body + [totals] for v in line[1 + 2 * len(weeks):]]
    size = min(
        _fit_font(week_values, bold, col_w, 8),
        _fit_font(summary_values, bold, summary_w, 8) if with_summary else 8,
    )
    hs = _header_style(bold, min(size, 7.5))
    head0 = [head0[0]] + [Paragraph(h.replace("\n", "<br/>"), hs) if h else "" for h in head0[1:]]
    for line in body:
        line[0] = _truncate(line[0], regular, size + 0.5, staff_w)

    data = [head0, head1] + body + [totals]
    widths = [staff_w] + [col_w] * (2 * len(weeks)) + [summary_w] * n_summary
    t = Table(data, colWidths=widths, repeatRows=2, hAlign="LEFT")
    style = _base_style(2, len(data), size)
    style += [
        ("SPAN", (0, 0), (0, 1)),
        ("BACKGROUND", (0, 0), (0, 1), HEADER_BG),
        ("FONT", (0, 2), (0, -2), regular, size + 0.5),
        ("LINEAFTER", (0, 0), (0, -1), 0.9, HEADER_BG),
    ]
    for i in range(len(weeks)):
        c0 = 1 + 2 * i
        style.append(("SPAN", (c0, 0), (c0 + 1, 0)))
        style.append(("LINEAFTER", (c0 + 1, 0), (c0 + 1, -1), 0.9, HEADER_BG))
        if not report.week_has_data[weeks[i]]:
            style += [
                ("ALIGN", (c0, 2), (c0 + 1, -1), "CENTER"),
                ("TEXTCOLOR", (c0, 2), (c0 + 1, -1), MUTED),
            ]
    if with_summary:
        first = 1 + 2 * len(weeks)
        for c in range(first, first + 3):
            style.append(("SPAN", (c, 0), (c, 1)))
        style.append(("BACKGROUND", (first, 0), (first + 2, 1), HEADER_BG))
        style += [
            ("FONT", (first, 2), (first, -1), bold, size),
            ("FONT", (first + 2, 2), (first + 2, -1), bold, size),
            ("BACKGROUND", (first + 2, 2), (first + 2, -2), colors.HexColor("#E8F2EC")),
        ]
    t.setStyle(TableStyle(style))
    return t
