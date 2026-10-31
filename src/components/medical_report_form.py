from reportlab.platypus import Flowable, SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak, KeepTogether
from reportlab.graphics.shapes import Drawing, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog,
    QMessageBox, QScrollArea, QWidget,
)
from PyQt5.QtCore import Qt, QTimer, QRect
from PyQt5.QtGui import QImage, QPixmap, QPainter
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
import json
from pathlib import Path
from datetime import datetime
import os
import uuid
from ..utils.app_paths import get_resource_path as get_asset_path
from ..utils.runtime_config import get_configured_path

ANALYSIS_JSON_DIR = get_configured_path("analysis_json_dir")
CARD_BORDER_COLOR = colors.HexColor("#C9D5E3")
CARD_GRID_COLOR = colors.HexColor("#E6ECF3")
CARD_HEADER_BG = colors.HexColor("#E7F0F8")
CARD_SUBHEADER_BG = colors.HexColor("#F7FAFD")
CARD_TEXT_MUTED = colors.HexColor("#475569")
CARD_ACCENT = colors.HexColor("#0B5E75")
CARD_TITLE = colors.HexColor("#12344D")
CARD_SECTION_TEXT = colors.HexColor("#0F172A")
CARD_RADIUS = 10


class RoundedCard(Flowable):
    """Draw a rounded outer card behind a child flowable."""

    def __init__(self, content, width, padding=6, radius=CARD_RADIUS, stroke_color=CARD_BORDER_COLOR, fill_color=colors.white):
        super().__init__()
        self.content = content
        self.card_width = width
        self.padding = padding
        self.radius = radius
        self.stroke_color = stroke_color
        self.fill_color = fill_color
        self._content_width = max(0, width - (padding * 2))
        self._content_height = 0

    def wrap(self, availWidth, availHeight):
        _, self._content_height = self.content.wrap(self._content_width, availHeight)
        return self.card_width, self._content_height + (self.padding * 2)

    def draw(self):
        self.canv.saveState()
        card_height = self._content_height + (self.padding * 2)
        self.canv.setLineWidth(1)
        self.canv.setStrokeColor(self.stroke_color)
        self.canv.setFillColor(self.fill_color)
        self.canv.roundRect(0, 0, self.card_width, card_height, self.radius, stroke=1, fill=1)
        clip_path = self.canv.beginPath()
        clip_path.roundRect(0, 0, self.card_width, card_height, self.radius)
        self.canv.clipPath(clip_path, stroke=0, fill=0)
        self.content.drawOn(self.canv, self.padding, self.padding)
        self.canv.setStrokeColor(self.stroke_color)
        self.canv.setLineWidth(1)
        self.canv.roundRect(0, 0, self.card_width, card_height, self.radius, stroke=1, fill=0)
        self.canv.restoreState()


def _rounded_card(content, width, padding=6):
    return RoundedCard(content, width=width, padding=padding, radius=CARD_RADIUS)


# ============================================================================
# BLOCK A -- report helpers (KPI tiles, AHI scale, footer canvas)
# ============================================================================
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas as _rl_canvas

REPORT_NAVY = colors.HexColor("#1d3a6b")
REPORT_INK = colors.HexColor("#1c2431")
REPORT_MUTE = colors.HexColor("#1c2431")
REPORT_LINE = colors.HexColor("#d7dde6")
REPORT_TINT = colors.HexColor("#f3f6fa")
PDF_FIELD_LIMITS = {
    "patient_name": 62, "patient_id": 20, "phone": 15, "city_state": 30,
    "clinic": 40, "physician": 40, "status": 20, "history": 80, "comments": 80,
    "weight": 8, "height": 8, "bmi": 6, "blood_pressure": 9, "custom_note": 600,
}
SEVERITY_COLORS = {
    "normal": colors.HexColor("#3f7d20"),
    "borderline low": colors.HexColor("#b45309"),
    "mild": colors.HexColor("#b45309"),
    "moderate": colors.HexColor("#c2410c"),
    "severe": colors.HexColor("#b91c1c"),
    "low": colors.HexColor("#c2410c"),
    "significantly low": colors.HexColor("#b91c1c"),
    "high": colors.HexColor("#c2410c"),
}
EVENT_ROW_COLORS = {
    "Obstructive Apneas": colors.HexColor("#c2410c"),
    "Central Apneas": colors.HexColor("#b45309"),
    "Mixed Apneas": colors.HexColor("#7c2d12"),
    "Hypopneas": colors.HexColor("#3f7d20"),
    "Hypopnea Index (HI)": colors.HexColor("#3f7d20"),
    "Apnea Index (AI)": colors.HexColor("#1d3a6b"),
}
SCORING_NOTE = "Scoring: AASM 2012, hypopnea 3% desaturation rule"


def _severity_color(label):
    return SEVERITY_COLORS.get(str(label or "").strip().lower(), REPORT_MUTE)


def _minimum_spo2_severity(value):
    """Return the display band for the minimum recorded SpO2 value."""
    try:
        spo2 = float(value)
    except (TypeError, ValueError):
        return "-"
    if spo2 < 88.0:
        return "Significantly low"
    if spo2 < 90.0:
        return "Low"
    if spo2 < 95.0:
        return "Borderline low"
    return "Normal"


def _ps(name, size, color=REPORT_INK, bold=False, align=0, leading=None):
    return ParagraphStyle(
        name, fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size,
        leading=leading or size * 1.25, textColor=color, alignment=align,
    )


def _plain_card(content, width, padding=0, fill=colors.white):
    return RoundedCard(content, width=width, padding=padding, radius=6, stroke_color=REPORT_LINE, fill_color=fill)


def _section_title(text, sub=""):
    body = f'<font name="Helvetica-Bold" size="10" color="{REPORT_NAVY.hexval()}">{text}</font>'
    if sub:
        body += f'   <font size="7.5" color="{REPORT_MUTE.hexval()}">{sub}</font>'
    return Paragraph(body, _ps("SectionTitle", 10, leading=13))


def _kpi_tile(label, value, unit, severity, sub, width):
    sev_color = _severity_color(severity)
    dot = f'<font color="{sev_color.hexval()}">&#9679;</font> '
    rows = [
        [Paragraph(label.upper(), _ps("KpiLabel", 7.5, REPORT_INK, bold=True))],
        [Paragraph(
            f'<font name="Helvetica-Bold" size="15" color="{REPORT_INK.hexval()}">{value}</font>'
            f' <font size="8" color="{REPORT_MUTE.hexval()}">{unit}</font>', _ps("KpiValue", 15, leading=18))],
        [Paragraph(
            f'{dot}<font name="Helvetica-Bold" size="8" color="{sev_color.hexval()}">{severity}</font>'
            f'  <font size="7.5" color="{REPORT_MUTE.hexval()}">{sub}</font>', _ps("KpiSub", 8, leading=11))],
    ]
    t = Table(rows, colWidths=[width - 24])
    t.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))
    return _plain_card(t, width, padding=12)


def _mini_row(key, value, key_width, total_width):
    return [Paragraph(f"{key}:", _ps("MiniK", 8, REPORT_MUTE, leading=11)),
            Paragraph(str(value), _ps("MiniV", 8, REPORT_INK, leading=11, align=2))]


def _mini_table(rows, width):
    key_w = width * 0.45
    t = Table([_mini_row(k, v, key_w, width) for k, v in rows], colWidths=[key_w, width - key_w])
    t.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 2), ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return t


def _info_tile(label, value, width):
    t = Table([[Paragraph(label, _ps("TileL", 7, REPORT_MUTE, leading=9))],
               [Paragraph(str(value), _ps("TileV", 10, REPORT_INK, bold=True, leading=12))]],
              colWidths=[width - 16])
    t.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 1), ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))
    return _plain_card(t, width, padding=8)


def _ahi_scale_drawing(value, width):
    """4-band OSA severity scale (<5 / 5-15 / 15-30 / >30) with an AHI marker."""
    total = 40.0
    height = 64
    bar_y, bar_h = 26, 11
    d = Drawing(width, height)
    bands = [(0, 5, "#33A613", "Normal", "#33A613"), (5, 15, "#F5B933", "Mild", "#D99A00"),
             (15, 30, "#F99D1F", "Moderate", "#F99D1F"), (30, 40, "#F91719", "Severe", "#F91719")]
    x_of = lambda v: (min(max(v, 0.0), total) / total) * width
    for lo, hi, fill, name, txt in bands:
        d.add(Rect(x_of(lo), bar_y, x_of(hi) - x_of(lo), bar_h, fillColor=colors.HexColor(fill), strokeColor=None))
        mid = (x_of(lo) + x_of(hi)) / 2
        d.add(String(mid, bar_y + bar_h + 6, {0: "<5", 5: "5-15", 15: "15-30", 30: ">30"}[lo],
                     fontSize=7.5, fillColor=REPORT_MUTE, textAnchor="middle"))
        d.add(String(mid, bar_y - 12, name, fontName="Helvetica-Bold", fontSize=8,
                     fillColor=colors.HexColor(txt), textAnchor="middle"))
    mx = x_of(float(value))
    d.add(Polygon([mx - 5, bar_y + bar_h + 7, mx + 5, bar_y + bar_h + 7, mx, bar_y + bar_h + 1],
                  fillColor=REPORT_INK, strokeColor=REPORT_INK))
    d.add(String(min(mx + 8, width - 40), bar_y + bar_h + 18, f"AHI {float(value):.1f}",
                 fontName="Helvetica-Bold", fontSize=8, fillColor=REPORT_INK))
    return d


def _make_numbered_canvas(footer_left, footer_mid):
    """Footer on every page: 'Patient ... | Scoring ... | Page N of M'."""
    class _NumberedCanvas(_rl_canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self._draw_footer(total)
                super().showPage()
            super().save()

        def _draw_footer(self, total):
            w, _ = self._pagesize
            self.saveState()
            self.setStrokeColor(REPORT_LINE)
            self.setLineWidth(0.6)
            self.line(28, 22, w - 28, 22)
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(REPORT_INK)
            self.drawCentredString(w / 2, 12, footer_left)
            self.drawCentredString(w / 2, 12, footer_mid)
            self.drawRightString(w - 28, 12, f"Page {self._pageNumber} of {total}")
            self.restoreState()
    return _NumberedCanvas


def _age_from_dob(dob_text):
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            born = datetime.strptime(str(dob_text).strip(), fmt)
            today = datetime.now()
            return today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        except (ValueError, TypeError):
            continue
    return None


def _first(d, *keys, default="—"):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", "-", "/"):
            return v
    return default


def _build_report_styles(base_styles):
    """Create a cohesive medical-report style palette on top of reportlab defaults."""
    styles = base_styles

    styles["Title"].fontName = "Helvetica-Bold"
    styles["Title"].fontSize = 18
    styles["Title"].leading = 22
    styles["Title"].textColor = CARD_TITLE
    styles["Title"].alignment = 1

    styles["Heading2"].fontName = "Helvetica-Bold"
    styles["Heading2"].fontSize = 12
    styles["Heading2"].leading = 14
    styles["Heading2"].spaceAfter = 0
    styles["Heading2"].textColor = CARD_TITLE

    styles["Normal"].fontName = "Helvetica"
    styles["Normal"].fontSize = 8.5
    styles["Normal"].leading = 11
    styles["Normal"].textColor = CARD_TEXT_MUTED

    styles["BodyText"].fontName = "Helvetica"
    styles["BodyText"].fontSize = 8
    styles["BodyText"].leading = 10
    styles["BodyText"].textColor = CARD_TEXT_MUTED

    if "ReportSubTitle" not in styles.byName:
        styles.add(
            ParagraphStyle(
                name="ReportSubTitle",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=9,
                leading=12,
                alignment=1,
                textColor=CARD_TEXT_MUTED,
            )
        )
    if "ImageLabel" not in styles.byName:
        styles.add(
            ParagraphStyle(
                name="ImageLabel",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=9,
                leading=11,
                textColor=CARD_SECTION_TEXT,
                spaceAfter=0,
            )
        )
    return styles


def _section_heading(text, styles):
    return Paragraph(f"<b>{text}</b>", styles["Heading2"])


def _build_dashboard_screenshot_section(image_paths, doc, styles):
    """Create report elements for optional dashboard screenshots."""
    if not image_paths:
        return []

    if isinstance(image_paths, (str, os.PathLike)):
        image_paths = [image_paths]

    existing_paths = [str(path) for path in image_paths if path and os.path.exists(path)]
    if not existing_paths:
        return []

    elements = [Spacer(1, 12)]
    hypnogram_paths = []
    screenshot_paths = []

    for image_path in existing_paths:
        stem_name = Path(image_path).stem.lower()
        if "psg_hypnogram" in stem_name or "full_psg" in stem_name:
            hypnogram_paths.append(image_path)
        else:
            screenshot_paths.append(image_path)

    ordered_paths = hypnogram_paths + screenshot_paths
    screenshot_heading_added = False

    for index, image_path in enumerate(ordered_paths, start=1):
        if image_path in screenshot_paths and not screenshot_heading_added:
            elements.extend([
                Spacer(1, 8),
                _section_heading("ATTACHED SCREENSHOTS", styles),
                Spacer(1, 10),
            ])
            screenshot_heading_added = True
        elements.extend(_build_single_dashboard_screenshot(image_path, index, doc, styles))

    return elements


class _PageMarker(Flowable):
    """Invisible 1-pt flowable that records the (0-based) page it is drawn on."""

    def __init__(self, sink):
        super().__init__()
        self.sink = sink
        self.width = self.height = 1

    def wrap(self, availWidth, availHeight):
        return 1, 1

    def draw(self):
        self.sink.append(int(self.canv.getPageNumber()) - 1)


def _overlay_vector_report_pages(report_path, vector_paths, start_page_index=2, page_indexes=None):
    """Place vector-PDF attachments onto pre-created report pages.

    ``page_indexes`` are the real placeholder pages recorded while the report was built. The old fixed
    ``start_page_index`` assumed the report is always exactly 2 pages before the chart, so any extra page
    drew the chart on top of the wrong page.
    """
    vector_paths = [
        str(path) for path in (vector_paths or [])
        if path and os.path.exists(path)
    ]
    if not vector_paths:
        return os.path.abspath(report_path)

    import pymupdf

    target_path = Path(report_path).resolve()
    temp_path = target_path.with_name(
        f".{target_path.stem}.{uuid.uuid4().hex}.tmp.pdf"
    )
    target_document = pymupdf.open(str(target_path))
    try:
        required_pages = (max(page_indexes) + 1) if page_indexes else int(start_page_index) + len(vector_paths)
        if target_document.page_count < required_pages:
            raise ValueError(
                "The report does not contain enough placeholder pages for the vector chart."
            )

        real_pages = list(page_indexes or [])
        if len(real_pages) < len(vector_paths):
            real_pages = [int(start_page_index) + n for n in range(len(vector_paths))]

        for offset, vector_path in enumerate(vector_paths):
            source_document = pymupdf.open(os.path.abspath(vector_path))
            try:
                if source_document.page_count <= 0:
                    raise ValueError(f"Vector chart has no pages: {vector_path}")

                target_page = target_document.load_page(int(real_pages[offset]))
                source_page = source_document.load_page(0)
                page_rect = target_page.rect
                source_rect = source_page.rect

                # Match the report's 30-point content margins and leave its
                # numbered footer untouched. Preserve the chart page ratio.
                available_width = max(1.0, float(page_rect.width) - 60.0)
                available_height = max(1.0, float(page_rect.height) - 90.0)
                scale = min(
                    available_width / max(float(source_rect.width), 1.0),
                    available_height / max(float(source_rect.height), 1.0),
                )
                draw_width = float(source_rect.width) * scale
                draw_height = float(source_rect.height) * scale
                left = (float(page_rect.width) - draw_width) / 2.0
                top = 30.0
                target_rect = pymupdf.Rect(
                    left,
                    top,
                    left + draw_width,
                    top + draw_height,
                )
                target_page.show_pdf_page(
                    target_rect,
                    source_document,
                    0,
                    keep_proportion=True,
                    overlay=True,
                )
            finally:
                source_document.close()

        target_document.save(str(temp_path), garbage=4, deflate=True)
    finally:
        target_document.close()

    try:
        os.replace(str(temp_path), str(target_path))
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return str(target_path)


def _build_single_dashboard_screenshot(image_path, index, doc, styles):
    """Create report elements for one dashboard screenshot."""
    try:
        image_reader = ImageReader(image_path)
        image_width, image_height = image_reader.getSize()
        if image_width <= 0 or image_height <= 0:
            return []

        max_width = doc.width
        # Leave extra room for the section title and padding so the image never
        # spills onto a mostly blank follow-up page.
        max_height = doc.height - 24
        scale = min(max_width / image_width, max_height / image_height)
        screenshot = Image(
            image_path,
            width=image_width * scale,
            height=image_height * scale,
        )

        return [
            screenshot,
            Spacer(1, 8),
        ]
    except Exception as error:
        print(f"⚠️ Could not add dashboard screenshot to report: {error}")
        return []


def _default_report_output_path(filename, *, unique=False):
    """Return a local user-folder path for generated report files."""
    report_dir = Path.home() / "SleepSenseReports"
    report_dir.mkdir(parents=True, exist_ok=True)
    target = report_dir / filename
    if not unique:
        return str(target)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(target.with_name(f"{target.stem}_{timestamp}{target.suffix or '.pdf'}"))


def _text_or_dash(value):
    text = "" if value is None else str(value).strip()
    return text if text else "-"


def _truncate_text(value, limit=120):
    text = _text_or_dash(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _patient_display_name(patient_data):
    first_name = _text_or_dash(patient_data.get("first_name"))
    last_name = _text_or_dash(patient_data.get("last_name"))
    if first_name == "-" and last_name == "-":
        return "-"
    return f"{first_name} {last_name}".strip()


def _get_section(analysis_results, section_name):
    if not analysis_results:
        return {}
    return analysis_results.get(section_name, {}) or {}


def _load_latest_analysis_results():
    if not ANALYSIS_JSON_DIR.exists():
        return {}

    json_files = sorted(ANALYSIS_JSON_DIR.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not json_files:
        return {}

    latest_path = json_files[0]
    try:
        with open(latest_path, "r", encoding="utf-8") as file_handle:
            payload = json.load(file_handle)
        pass
        return payload if isinstance(payload, dict) else {}
    except Exception as error:
        print(f"⚠️ Could not load latest analysis JSON {latest_path}: {error}")
        return {}


def _get_report_logo_path():
    logo_path = get_asset_path("assets/images/DECKMOUNT_Logo.png")
    return logo_path if Path(logo_path).exists() else None


def _create_report_logo_image():
    """Load the bundled PNG logo for the report header."""
    logo_path = _get_report_logo_path()
    if not logo_path:
        return None

    source_width, source_height = ImageReader(logo_path).getSize()
    if source_width <= 0 or source_height <= 0:
        return None

    display_width = 82.0
    display_height = display_width * source_height / source_width
    return Image(logo_path, width=display_width, height=display_height)


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _format_snoring_minutes(seconds):
    minutes = max(0.0, _safe_float(seconds, 0.0)) / 60.0
    return f"{minutes:.1f} minutes"


def _format_snoring_percent(percent):
    return f"{max(0.0, _safe_float(percent, 0.0)):.1f}%"


def _snoring_level_label(percent):
    # App-defined bands (no published consensus for % of time with snoring).
    percent = max(0.0, _safe_float(percent, 0.0))
    if percent < 20.0:
        return "Minimal"
    if percent < 40.0:
        return "Mild"
    if percent < 60.0:
        return "Moderate"
    if percent < 80.0:
        return "High"
    return "Severe"


def _build_snoring_visual_section(snoring, styles, card_width=250):
    percentage = min(100.0, max(0.0, _safe_float(snoring.get("snoring_percentage"), 0.0)))
    total_duration_text = snoring.get("total_snoring_duration_display") or _format_snoring_minutes(snoring.get("total_snoring_duration_sec", 0.0))
    percentage_text = snoring.get("snoring_percentage_display") or _format_snoring_percent(percentage)
    episode_text = snoring.get("total_snoring_episodes_display", "0")
    mean_duration_text = snoring.get("mean_snoring_duration_display", "0.0 sec")
    severity_text = _snoring_level_label(percentage)

    card_height = 112
    content_center_x = card_width / 2.0
    bar_x = 14
    bar_y = 50
    bar_width = 210
    bar_height = 14
    pointer_x = bar_x + (bar_width * (percentage / 100.0))
    pointer_x = min(bar_x + bar_width - 3, max(bar_x + 3, pointer_x))
    segment_width = bar_width / 5.0
    fill_width = bar_width * (percentage / 100.0)

    drawing = Drawing(card_width, card_height)
    drawing.add(
        Rect(
            0,
            0,
            card_width,
            card_height,
            strokeColor=colors.HexColor("#CFCFCF"),
            fillColor=colors.white,
            strokeWidth=1,
            rx=7,
            ry=7,
        )
    )
    drawing.add(
        Rect(
            0,
            92,
            card_width,
            20,
            strokeColor=None,
            fillColor=CARD_HEADER_BG,
            rx=7,
            ry=7,
        )
    )
    drawing.add(Rect(0, 92, card_width, 10, strokeColor=None, fillColor=CARD_HEADER_BG))
    drawing.add(String(8, 98, "SNORING SUMMARY", fontName="Helvetica-Bold", fontSize=8.5, fillColor=colors.black))

    title_font = "Helvetica-Bold"
    title_font_size = 8.2
    value_font = "Helvetica-Bold"
    value_font_size = 9
    percent_font = "Helvetica-Bold"
    percent_font_size = 8.6
    title_text = "Total Snoring Time:"
    percent_text = f"({percentage_text})"

    title_width = stringWidth(title_text, title_font, title_font_size)
    value_width = stringWidth(total_duration_text, value_font, value_font_size)
    percent_width = stringWidth(percent_text, percent_font, percent_font_size)
    total_line_width = title_width + 6 + value_width + 4 + percent_width
    total_line_start_x = max(8, content_center_x - (total_line_width / 2.0))

    text_y = 78
    drawing.add(String(total_line_start_x, text_y, title_text, fontName=title_font, fontSize=title_font_size, fillColor=colors.black))
    drawing.add(String(total_line_start_x + title_width + 6, text_y, total_duration_text, fontName=value_font, fontSize=value_font_size, fillColor=CARD_ACCENT))
    drawing.add(String(total_line_start_x + title_width + 6 + value_width + 4, text_y, percent_text, fontName=percent_font, fontSize=percent_font_size, fillColor=CARD_ACCENT))

    segment_colors = ["#35A7A0", "#6CB68C", "#A8BA72", "#E7AA59", "#E36B6B"]
    for index, segment_color in enumerate(segment_colors):
        drawing.add(
            Rect(
                bar_x + (index * segment_width),
                bar_y,
                segment_width,
                bar_height,
                strokeColor=None,
                fillColor=colors.HexColor(segment_color),
            )
        )

    if fill_width > 0:
        drawing.add(
            Rect(
                bar_x,
                bar_y,
                fill_width,
                bar_height,
                strokeColor=None,
                fillColor=colors.Color(1, 1, 1, alpha=0.18),
            )
        )

    drawing.add(
        Polygon(
            [
                pointer_x, bar_y + bar_height + 2,
                pointer_x - 5, bar_y + bar_height + 9,
                pointer_x + 5, bar_y + bar_height + 9,
            ],
            strokeColor=colors.black,
            fillColor=colors.black,
        )
    )

    for tick in range(6):
        tick_x = bar_x + (bar_width * tick / 5.0)
        tick_label = f"{tick * 20}%"
        drawing.add(String(tick_x - 2, 30, tick_label, fontName="Helvetica-Bold", fontSize=7, fillColor=colors.HexColor("#153F46")))
    percent_label_x = min(bar_x + bar_width - 20, max(bar_x, pointer_x - 14))
    drawing.add(String(percent_label_x, 14, percentage_text, fontName="Helvetica-Bold", fontSize=7.4, fillColor=CARD_ACCENT))

    details_style = styles["BodyText"].clone("SnoringDetailsStyle")
    details_style.fontName = "Helvetica"
    details_style.fontSize = 7
    details_style.leading = 8
    details_style.textColor = colors.HexColor("#4A4A4A")

    severity_style = styles["BodyText"].clone("SnoringSeverityStyle")
    severity_style.fontName = "Helvetica"
    severity_style.fontSize = 7
    severity_style.leading = 8
    severity_style.textColor = colors.HexColor("#4A4A4A")

    severity_row = Paragraph(f"<b>Snoring Level:</b> <b>{severity_text}</b>", severity_style)

    snoring_card = Table([[drawing], [Spacer(1, 4)], [severity_row]], colWidths=[card_width - 8])
    snoring_card.setStyle(
        TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ])
    )
    return snoring_card


def _build_snoring_parameter_table(snoring, table_width, styles):
    """Render a compact medical-style snoring metrics table under the visual bar."""
    body_style = styles["BodyText"].clone("SnoringParameterBody")
    body_style.fontName = "Helvetica"
    body_style.fontSize = 7.2
    body_style.leading = 8.8
    body_style.textColor = CARD_TEXT_MUTED

    value_style = styles["BodyText"].clone("SnoringParameterValue")
    value_style.fontName = "Helvetica-Bold"
    value_style.fontSize = 7.2
    value_style.leading = 8.8
    value_style.textColor = CARD_ACCENT

    def label_cell(text):
        return Paragraph(_text_or_dash(text), body_style)

    def value_cell(text):
        return Paragraph(_text_or_dash(text), value_style)

    table_data = [
        ["SNORING PARAMETERS", ""],
        [label_cell("Snoring Level"), value_cell(_snoring_level_label(_safe_float(snoring.get("snoring_percentage"), 0.0)))],
        [label_cell("Percentage Of Snoring"), value_cell(snoring.get("snoring_percentage_display", "0.0 %"))],
        [label_cell("Total Snoring Episodes"), value_cell(snoring.get("total_snoring_episodes_display", "0"))],
        [label_cell("Total Duration With Snoring"), value_cell(snoring.get("total_snoring_duration_display", "0.0 sec"))],
        [label_cell("Mean Duration Of Snoring"), value_cell(snoring.get("mean_snoring_duration_display", "0.0 sec"))],
    ]

    col_widths = [table_width * 0.60, table_width * 0.40]
    table = Table(table_data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, CARD_GRID_COLOR),
        ("SPAN", (0, 0), (-1, 0)),
        ("BACKGROUND", (0, 0), (-1, 0), CARD_HEADER_BG),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.2),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, 0), "LEFT"),
        ("ALIGN", (0, 1), (0, -1), "LEFT"),
        ("ALIGN", (1, 1), (1, -1), "LEFT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def _build_patient_information_rows(patient_data, styles):
    cell_style = styles["BodyText"].clone("PatientCellStyle")
    cell_style.fontName = "Helvetica"
    cell_style.fontSize = 7.5
    cell_style.leading = 8.5

    def cell(value):
        return Paragraph(_text_or_dash(value), cell_style)

    return [
        [Paragraph("<b>PATIENT INFORMATION</b>", cell_style), "", "", ""],
        [cell("Patient Name"), cell(_patient_display_name(patient_data)), cell("Patient ID"), cell(patient_data.get("patient_id"))],
        [cell("DOB"), cell(patient_data.get("dob")), cell("Gender"), cell(patient_data.get("gender"))],
        [cell("Phone"), cell(patient_data.get("phone")), cell("City / State"), cell(patient_data.get("city_state"))],
        [cell("Clinic"), cell(patient_data.get("clinic")), cell("Physician"), cell(patient_data.get("physician"))],
        [cell("Weight"), cell(patient_data.get("weight")), cell("Height"), cell(patient_data.get("height"))],
        [cell("BMI"), cell(patient_data.get("bmi")), cell("Blood Pressure"), cell(patient_data.get("blood_pressure"))],
        [cell("Status"), cell(patient_data.get("status")), cell("Report Date"), cell(datetime.now().strftime("%d-%m-%Y"))],
        [cell("History"), cell(_truncate_text(patient_data.get("history"), 120)), cell("Comments"), cell(_truncate_text(patient_data.get("comments"), 120))],
    ]


def _build_interpretation_card(report_context, styles, card_width):
    interpretation = report_context.get("report_interpretation", {}) or {}
    diagnosis = _text_or_dash(interpretation.get("diagnosis"))
    findings = interpretation.get("findings", []) or []
    recommendations = interpretation.get("recommendations", []) or []
    manual_items = interpretation.get("manual_items", []) or []
    custom_note = str(interpretation.get("custom_note") or "").strip()

    body_style = styles["BodyText"].clone("InterpretationBody")
    body_style.fontName = "Helvetica"
    body_style.fontSize = 8
    body_style.leading = 10
    body_style.textColor = CARD_TEXT_MUTED

    value_style = styles["BodyText"].clone("InterpretationValue")
    value_style.fontName = "Helvetica-Bold"
    value_style.fontSize = 8
    value_style.leading = 10
    value_style.textColor = CARD_ACCENT

    findings_html = "<br/>".join(
        f"• {str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')}"
        for item in findings
    ) or "• No additional findings available."
    recommendations_html = "<br/>".join(
        f"• {str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')}"
        for item in recommendations
    ) or "• No recommendations available."

    manual_items_html = "<br/>".join(
        f"â€¢ {str(item).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')}"
        for item in manual_items
    )
    manual_items_html = manual_items_html.replace("Ã¢â‚¬Â¢", "-").replace("â€¢", "-")
    custom_note_html = (
        custom_note.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        if custom_note else ""
    )

    table_rows = [
        ["INTERPRETATION", ""],
        [Paragraph("Diagnosis", body_style), Paragraph(diagnosis, value_style)],
        [Paragraph("Findings", body_style), Paragraph(findings_html, body_style)],
        [Paragraph("Recommendations", body_style), Paragraph(recommendations_html, body_style)],
    ]
    if manual_items_html:
        table_rows.append([Paragraph("Selected Notes", body_style), Paragraph(manual_items_html, body_style)])
    if custom_note_html:
        table_rows.append([Paragraph("Custom Note", body_style), Paragraph(custom_note_html, body_style)])

    table = Table(
        table_rows,
        colWidths=[card_width * 0.22, card_width * 0.78],
    )
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, CARD_GRID_COLOR),
        ("SPAN", (0, 0), (-1, 0)),
        ("BACKGROUND", (0, 0), (-1, 0), CARD_HEADER_BG),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def generate_sleep_report(pdf_path=None, patient_data=None, analysis_results=None, dashboard_screenshot_path=None, report_context=None):
    """Generate basic sleep report format with improved visual presentation"""
    if pdf_path is None:
        pdf_path = _default_report_output_path("sleep_report.pdf", unique=True)

    patient_data = patient_data or {}
    analysis_results = analysis_results or {}
    report_context = report_context or {}
    time_information = report_context.get("time_information", {}) or {}
    respiratory_summary = report_context.get("respiratory_summary", {}) or {}
    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                           leftMargin=28, rightMargin=28,
                           topMargin=26, bottomMargin=24)
    styles = _build_report_styles(getSampleStyleSheet())
    content_width = doc.width
    page1_content_width = content_width - 10
    column_gap = 18.0
    content_width_half = (content_width - column_gap) / 2.0
    elements = []
    page1_elements = []  # Elements to keep together on page 1

    # =========================================================================
    # BLOCK B -- PAGE 1
    # =========================================================================
    oximetry = dict(_get_section(analysis_results, "oximetry"))
    # Report-context metrics include event-linked published HB calculated at
    # report generation time; prefer them over the pre-event analysis JSON.
    oximetry.update(report_context.get("oximetry", {}) or {})
    heart_rate = _get_section(analysis_results, "heart_rate")
    snoring = _get_section(analysis_results, "snoring")

    logo_image = None
    try:
        logo_image = _create_report_logo_image()
    except Exception as error:
        print(f"⚠️ Could not load report logo: {error}")

    study_date = _first(time_information, "study_date", "recording_date", default=_first(patient_data, "report_date", default=datetime.now().strftime("%d-%m-%Y")))
    generated_text = datetime.now().strftime('%d %b %Y, %I:%M %p')

    # ---------------- HEADER ----------------
    header_left = Table([
        [logo_image if logo_image else Paragraph('<font name="Helvetica-Bold" size="15" color="%s">DECK MOUNT</font> <font size="7" color="%s">ELECTRONICS</font>' % (REPORT_NAVY.hexval(), REPORT_MUTE.hexval()), _ps("Brand", 15, leading=18))],
    ], colWidths=[page1_content_width * 0.5])
    header_right = Table([
        [Paragraph("SLEEP TEST REPORT", _ps("HdrTitle", 11, REPORT_INK, bold=True, align=2, leading=14))],
        [Paragraph(f"Study {study_date} | Generated {generated_text}", _ps("HdrSub", 7.5, REPORT_MUTE, align=2, leading=10))],
    ], colWidths=[page1_content_width * 0.5])
    for t in (header_left, header_right):
        t.setStyle(TableStyle([
            ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ]))
    header_row = Table([[header_left, header_right]], colWidths=[page1_content_width * 0.5] * 2)
    header_row.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LINEBELOW', (0,0), (-1,-1), 1.5, REPORT_NAVY),
    ]))
    page1_elements.append(header_row)
    page1_elements.append(Spacer(1, 8))

    # ---------------- PATIENT CARD + KPI TILES ----------------
    first_name = str(patient_data.get("first_name", "") or "")
    last_name = str(patient_data.get("last_name", "") or "")
    patient_name = (f"{last_name} {first_name}").strip() or _first(patient_data, "name", "patient_name", default="[not entered]")
    dob = _first(patient_data, "dob", "date_of_birth", default="")
    age = _first(patient_data, "age", default="") or _age_from_dob(dob)
    dob_age = " | ".join(x for x in (str(dob), f"{age} y" if age else "") if x) or "[not entered]"

    def _with_unit(value, unit):
        text = str(value).strip()
        if text in ("", "-", "[not entered]") or text.lower().endswith(unit):
            return text
        return f"{text} {unit}"

    patient_rows = [
        ("Patient ID", _first(patient_data, "patient_id", "id")),
        ("DOB | Age", dob_age),
        ("Gender", str(_first(patient_data, "gender", "sex")).title()),
        ("Phone", _first(patient_data, "phone", "mobile")),
        ("City / State", _first(patient_data, "city_state", "city", "state")),
        ("Clinic", _first(patient_data, "clinic", "clinic_name")),
        ("Physician", _first(patient_data, "physician", "doctor_name", "referring_physician")),
        ("Weight", _with_unit(_first(patient_data, "weight"), "kg")),
        ("Height", _with_unit(_first(patient_data, "height"), "cm")),
        ("BMI", _first(patient_data, "bmi")),
        ("Blood Pressure", _first(patient_data, "blood_pressure", "bp")),
        ("Status", _first(patient_data, "status")),
        ("Report Date", _first(patient_data, "report_date", default=datetime.now().strftime("%d-%m-%Y"))),
        ("History", _first(patient_data, "history", "medical_history")),
        ("Comments", _first(patient_data, "comments", "comment")),
    ]
    # ---- 4 KPI tiles in one row ----
    # Use the exact same formatted AHI shown in the respiratory table/KPI.
    # This prevents raw floating-point values such as 6.75 rendering as 6.7
    # while the table shows 3.4 + 3.4 = 6.8.
    try:
        ahi_value = float(respiratory_summary.get("ahi_rei_display", 0.0) or 0.0)
    except (TypeError, ValueError):
        ahi_value = float(respiratory_summary.get("severity_value", 0.0) or 0.0)
    ahi_sev = "Normal" if ahi_value < 5 else "Mild" if ahi_value < 15 else "Moderate" if ahi_value < 30 else "Severe"
    min_spo2_txt = str(oximetry.get("min_spo2_display", "-")).replace("%", "").strip()
    min_spo2_sev = _minimum_spo2_severity(min_spo2_txt)
    odi_txt = str(oximetry.get("odi3_display", "0.0 /h")).replace("/h", "").strip()
    hb_txt = str(oximetry.get("hb_index_display", "0.0 %min/h")).replace("%min/h", "").strip()

    def _hb_total_text(oxi):
        text = str(oxi.get("hypoxic_burden_display", "-"))
        return text.replace(" %-min", "% min").replace("%-min", "% min")

    kpi_gap = 10
    kpi_width = (page1_content_width - kpi_gap * 3) / 4.0
    kpi_row = Table([[
        _kpi_tile("AHI", respiratory_summary.get("ahi_rei_display", f"{ahi_value:.1f}"), "/h", ahi_sev, "&lt;5 normal", kpi_width),
        _kpi_tile("Min SpO2", min_spo2_txt, "%", min_spo2_sev, f"mean {oximetry.get('mean_spo2_display', '-')}%", kpi_width),
        _kpi_tile("ODI 3%", odi_txt, "/h", oximetry.get("odi3_severity", "Normal"), f"{oximetry.get('odi3_event_count_display', '0')} desats", kpi_width),
        _kpi_tile("Hypoxic burden", hb_txt, "% min/h", oximetry.get("hb_severity", "Normal"), _hb_total_text(oximetry), kpi_width),
    ]], colWidths=[kpi_width + kpi_gap] * 3 + [kpi_width])
    kpi_row.setStyle(TableStyle([
        ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    page1_elements.append(kpi_row)
    page1_elements.append(Spacer(1, 6))

    # ---- Patient card: full width, 3 columns of key/value pairs ----
    patient_inner_w = page1_content_width - 24
    col_count = 3
    rows_per_col = -(-len(patient_rows) // col_count)   # ceil
    pk_w = (patient_inner_w / col_count) * 0.44
    pv_w = (patient_inner_w / col_count) - pk_w - 10
    grid_rows = []
    for r in range(rows_per_col):
        cells = []
        for c in range(col_count):
            i = c * rows_per_col + r
            if i < len(patient_rows):
                k, v = patient_rows[i]
                # Free-text fields can be any length; one very long value used to make the patient card
                # taller than page 1 and push the bottom cards onto an extra page.
                v_text = _truncate_text(str(v), 80 if k in ("History", "Comments") else 40)
                v_html = "—" if v_text in ("[not entered]", "", "-", "—") else f"<b>{v_text}</b>"
                cells += [Paragraph(k, _ps("PatK", 8, REPORT_MUTE, leading=11)),
                          Paragraph(v_html, _ps("PatV", 8, REPORT_INK, leading=11)), ""]
            else:
                cells += ["", "", ""]
        grid_rows.append(cells)
    patient_grid = Table(grid_rows, colWidths=[pk_w, pv_w, 10] * col_count)
    patient_grid.setStyle(TableStyle([
        ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    patient_inner = Table([
        [Paragraph(f'<font size="7" color="{REPORT_MUTE.hexval()}"><b>PATIENT</b></font>&nbsp;&nbsp;&nbsp;'
                   f'<font name="Helvetica-Bold" size="10" color="{REPORT_INK.hexval()}">{patient_name}</font>', _ps("PatN", 10, leading=13))],
        [patient_grid],
    ], colWidths=[patient_inner_w])
    patient_inner.setStyle(TableStyle([
        ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    page1_elements.append(_plain_card(patient_inner, page1_content_width, padding=12, fill=colors.white))
    page1_elements.append(Spacer(1, 4))

    # ---------------- OSA SEVERITY SCALE ----------------
    scale_inner_w = page1_content_width - 32
    scale_note = report_context.get("severity_note") or ""
    scale_rows = [[_section_title("OSA severity (AHI)", "Apnea + hypopnea events per hour of recording")],
                  [_ahi_scale_drawing(ahi_value, scale_inner_w)]]
    if scale_note:
        scale_rows.append([Paragraph(scale_note, _ps("ScaleNote", 7.5, REPORT_MUTE, leading=10))])
    scale_table = Table(scale_rows, colWidths=[scale_inner_w])
    scale_table.setStyle(TableStyle([
        ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    page1_elements.append(_plain_card(scale_table, page1_content_width, padding=10))
    page1_elements.append(Spacer(1, 6))

    # ---------------- RECORDING TILES ----------------
    page1_elements.append(_section_title("Recording", "Times from the device file timestamp"))
    page1_elements.append(Spacer(1, 4))
    tile_gap = 8
    tile_w = (page1_content_width - tile_gap * 4) / 5.0
    tiles = [
        _info_tile("Recording start", _first(time_information, "recording_start", "lights_off", default="-"), tile_w),
        _info_tile("Recording end", _first(time_information, "recording_end", "lights_on", default="-"), tile_w),
        _info_tile("Total recording time", _first(time_information, "trt_display", default="-"), tile_w),
        _info_tile("Valid analysis time", _first(time_information, "valid_time_display", default=f"{_first(oximetry, 'valid_spo2_ratio_display', default='-')} valid"), tile_w),
        _info_tile("Sensor-off ", _first(time_information, "sensor_off_display", default="-"), tile_w),
    ]
    tile_row = Table([tiles], colWidths=[tile_w + tile_gap] * 4 + [tile_w])
    tile_row.setStyle(TableStyle([
        ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    page1_elements.append(tile_row)
    page1_elements.append(Spacer(1, 8))

    # ---------------- RESPIRATORY EVENTS ----------------
    page1_elements.append(_section_title("Respiratory events", "Index = events per hour of valid analysis time"))
    page1_elements.append(Spacer(1, 4))
    respiratory_rows = respiratory_summary.get("rows", [])
    total_row = respiratory_summary.get("total_row", {}) or {}
    rei_in_position = respiratory_summary.get("rei_in_position", {}) or {}
    time_in_position = respiratory_summary.get("time_in_position", {}) or {}
    row_lookup = {row.get("name"): row for row in respiratory_rows}
    positions = ("Supine", "Prone", "Left", "Right", "Up")

    def _tip_minutes(value):
        # time_in_position values are dicts ({'minutes_display': '134.9', ...}) or plain numbers
        if isinstance(value, dict):
            return str(value.get("minutes_display") or value.get("minutes") or "0.0")
        return str(value if value not in (None, "") else "0.0")

    def _event_line(name, label):
        row = row_lookup.get(name, {})
        chip = f'<font color="{EVENT_ROW_COLORS.get(name, REPORT_MUTE).hexval()}">&#9632;</font>  '
        return ([Paragraph(chip + label, _ps("EvName", 8, leading=10)),
                 row.get("index_display", "0.0"), row.get("count_display", "0"),
                 row.get("mean_duration_display", "0.0"), row.get("max_duration_display", "0.0")]
                + [str(row.get("positions", {}).get(p, 0)) for p in positions])

    resp_data = [
        ["Event type", "Index /h", "Count", "Mean s", "Max s"] + list(positions),
        _event_line("Obstructive Apneas", "Obstructive apnea (OA)"),
        _event_line("Central Apneas", "Central apnea (CA)"),
        _event_line("Mixed Apneas", "Mixed apnea (MA)"),
        _event_line("Hypopnea Index (HI)", "Hypopnea Index (HI)"),
        _event_line("Apnea Index (AI)", "Apnea Index (AI)"),
        ["Apnea + Hypopnea (AHI)", total_row.get("index_display", "0.0"), total_row.get("count_display", "0"),
         total_row.get("mean_duration_display", "0.0"), total_row.get("max_duration_display", "0.0")]
        + [str(total_row.get("positions", {}).get(p, 0)) for p in positions],
        ["Time in position (min)", "", "", "", ""] + [_tip_minutes(time_in_position.get(p)) for p in positions],
        ["AHI in position", "", "", "", ""] + [str(rei_in_position.get(p, "–")) for p in positions],
    ]
    resp_ratios = (0.30, 0.09, 0.08, 0.08, 0.08, 0.074, 0.074, 0.074, 0.074, 0.074)
    resp_table = Table(resp_data, colWidths=[page1_content_width * r for r in resp_ratios])
    resp_table.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'), ('FONTSIZE', (0,0), (-1,-1), 8),
        ('TEXTCOLOR', (0,0), (-1,-1), REPORT_INK),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('FONTSIZE', (0,0), (-1,0), 7.5),
        ('TEXTCOLOR', (0,0), (-1,0), REPORT_MUTE),
        ('LINEBELOW', (0,0), (-1,0), 1, REPORT_INK),
        ('LINEBELOW', (0,1), (-1,-1), 0.5, REPORT_LINE),
        ('ALIGN', (1,0), (-1,-1), 'RIGHT'), ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BACKGROUND', (0,6), (-1,6), REPORT_TINT), ('FONTNAME', (0,6), (-1,6), 'Helvetica-Bold'),
        ('LEFTPADDING', (0,0), (-1,-1), 5), ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 3), ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    page1_elements.append(resp_table)
    page1_elements.append(Spacer(1, 8))

    # ---------------- OXIMETRY / PULSE & SNORING MINI CARDS ----------------
    half = (page1_content_width - 12) / 2.0
    oxi_rows = [
        ("Mean | Min | Max SpO2", f"{oximetry.get('mean_spo2_display', '-')} | {min_spo2_txt} | {oximetry.get('max_spo2_display', '-')} %"),
        ("Time SpO2 &lt; 90%", _first(oximetry, "duration_below_90_display", default="-")),
        ("Time SpO2 &lt; 85%", f"{oximetry.get('duration_below_85_display', '-')} ({oximetry.get('duration_below_85_pct_display', '-')})"),
        ("ODI 3% | events", f"{odi_txt} /h | {oximetry.get('odi3_event_count_display', '0')}"),
    ]
    def _num(v):
        return str(v).replace("BPM", "").replace("bpm", "").strip()

    hr_max = heart_rate.get("highest_hr_during_sleep_display", heart_rate.get("highest_hr_display", "-"))
    hr_mean = heart_rate.get("mean_hr_during_sleep_display", heart_rate.get("mean_hr_display", "-"))
    hr_min = heart_rate.get("lowest_hr_during_sleep_display", heart_rate.get("lowest_hr_display", "-"))
    pulse_rows = [
        ("Pulse mean | min | max", f"<b>{_num(hr_mean)} | {_num(hr_min)} | {_num(hr_max)} BPM</b>"),
        ("Snoring time", f"{snoring.get('total_snoring_duration_display', '-')} ({snoring.get('snoring_percentage_display', '-')})"),
        ("Snore episodes (3+ events)", snoring.get("total_snoring_episodes_display", "-")),
    ]
    def _mini_card(title, rows):
        inner = Table([[_section_title(title)], [_mini_table(rows, half - 24)]], colWidths=[half - 24])
        inner.setStyle(TableStyle([
            ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        return _plain_card(inner, half, padding=10)
    bottom_row = Table([[_mini_card("Oximetry", oxi_rows), _mini_card("Pulse &amp; snoring", pulse_rows)]], colWidths=[half + 12, half])
    bottom_row.setStyle(TableStyle([
        ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (0,0), 12), ('RIGHTPADDING', (1,0), (1,0), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    page1_elements.append(bottom_row)

    # Page 1 must stay ONE page: if the content is ever taller than the page (long free-text fields),
    # shrink it to fit instead of letting the last cards spill onto an extra page.
    from reportlab.platypus import KeepInFrame
    elements.append(KeepInFrame(doc.width - 12, doc.height - 12, page1_elements, mode="shrink"))
    elements.append(PageBreak())

    # =========================================================================
    # BLOCK C -- PAGE 2
    # =========================================================================
    page2_elements = []

    def _page_header(right_title):
        left = Table([
            [logo_image if logo_image else Paragraph('<font name="Helvetica-Bold" size="15" color="%s">DECK MOUNT</font> <font size="7" color="%s">ELECTRONICS</font>' % (REPORT_NAVY.hexval(), REPORT_MUTE.hexval()), _ps("Brand2", 15, leading=18))],
        ], colWidths=[page1_content_width * 0.5])
        right = Table([
            [Paragraph(right_title, _ps("HdrTitle2", 11, REPORT_INK, bold=True, align=2, leading=14))],
            [Paragraph(f"Study {study_date} | Generated {generated_text}", _ps("HdrSub2", 7.5, REPORT_MUTE, align=2, leading=10))],
        ], colWidths=[page1_content_width * 0.5])
        for t in (left, right):
            t.setStyle(TableStyle([
                ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0),
                ('TOPPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 1),
            ]))
        row = Table([[left, right]], colWidths=[page1_content_width * 0.5] * 2)
        row.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
            ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LINEBELOW', (0,0), (-1,-1), 1.5, REPORT_NAVY),
        ]))
        return row

    def _card(title, sub, rows, width, note=None):
        body = [[_section_title(title, sub)], [_mini_table(rows, width - 24)]]
        if note:
            body.append([Paragraph(note, _ps("CardNote", 7, REPORT_MUTE, leading=9))])
        inner = Table(body, colWidths=[width - 24])
        inner.setStyle(TableStyle([
            ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        return _plain_card(inner, width, padding=12)

    def _sev(text):
        c = _severity_color(text)
        return f'<font color="{c.hexval()}"><b>{text}</b></font>'

    page2_elements.append(_page_header("OXIMETRY, PULSE &amp; SNORING"))
    page2_elements.append(Spacer(1, 12))

    col_gap = 12
    col_w = (page1_content_width - col_gap) / 2.0

    # ---------------- LEFT: OXIMETRY ----------------
    oxi_rows2 = [
        ("SpO2 coverage (valid signal)", oximetry.get("valid_spo2_ratio_display", "-")),
        ("Mean SpO2 during sleep", f"{oximetry.get('mean_spo2_display', '-')} %"),
        ("Min SpO2 during sleep", f"{min_spo2_txt} %"),
        ("Max SpO2 during sleep", f"{oximetry.get('max_spo2_display', '-')} %"),
        ("ODI 3% | events", f"<b>{odi_txt} /h | {oximetry.get('odi3_event_count_display', '0')}</b>  {_sev(oximetry.get('odi3_severity', 'Normal'))}"),
        ("Hypoxic burden (total)", _hb_total_text(oximetry)),
        ("HB index", f"<b>{hb_txt} % min/h</b>  {_sev(oximetry.get('hb_severity', 'Normal'))}"),
        ("Longest desaturation", oximetry.get("longest_duration_display", oximetry.get("desat_max_sec_display", "-"))),
        ("Respiratory events used for HB", str(oximetry.get("hb_event_count", oximetry.get("total_count_event_display", "-")))),
        ("Time SpO2 &lt; 90%", _first(oximetry, "duration_below_90_display", default="-")),
        ("Time SpO2 &lt; 85%", f"{oximetry.get('duration_below_85_display', '-')} ({oximetry.get('duration_below_85_pct_display', '-')})"),
    ]
    oxi_note_text = (
        f"SpO2 quality: {oximetry.get('oximetry_quality_status', '-')}. "
        + (str(oximetry.get("oximetry_quality_reason")) if oximetry.get("oximetry_quality_reason")
           else ("Hypoxic burden uses Azarbarzin-style event-linked SpO2 areas; "
                 "HB index is normalised by analysed recording hours." if oximetry.get("hb_method")
                 else "Hypoxic burden uses a fixed 95% SpO2 baseline; HB index is normalised by recording hours."))
    )
    oxi_card2 = _card("Oximetry", "SpO2 during recording", oxi_rows2, col_w, note=oxi_note_text)

    hb_ref_rows = [
        ("0 – 5 % min/h", _sev("Normal")),
        ("5 – 30 % min/h", _sev("Mild")),
        ("30 – 70 % min/h", _sev("Moderate")),
        ("&gt; 70 % min/h", _sev("Severe")),
    ]
    hb_ref_card = _card("HB index reference", "Severity bands", hb_ref_rows, col_w)

    left_stack = Table([[oxi_card2], [Spacer(1, 10)], [hb_ref_card]], colWidths=[col_w])
    left_stack.setStyle(TableStyle([
        ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))

    # ---------------- RIGHT: PULSE + SNORING ----------------
    pulse_rows2 = [
        ("Mean pulse during sleep", f"<b>{hr_mean}</b>"),
        ("Highest pulse during sleep", f"<b>{hr_max}</b>"),
        ("Highest pulse during TIB", f"<b>{heart_rate.get('highest_hr_during_tib_display', hr_max)}</b>"),
        ("Lowest pulse during sleep", f"<b>{hr_min}</b>"),
        ("Lowest pulse during TIB", f"<b>{heart_rate.get('lowest_hr_during_tib_display', hr_min)}</b>"),
    ]
    pulse_card2 = _card("Pulse", "From the oximeter", pulse_rows2, col_w)

    snore_pct = min(100.0, max(0.0, _safe_float(snoring.get("snoring_percentage"), 0.0)))
    snore_level = _snoring_level_label(snore_pct)
    snore_basis_word = "sleep" if snoring.get("snoring_basis") == "sleep" else "recording"
    snore_rows2 = [
        ("Snoring level (app-defined)", _sev(snore_level)),
        (f"Percentage of {snore_basis_word}", snoring.get("snoring_percentage_display") or f"{snore_pct:.1f} %"),
        ("Snore episodes (3+ events)", f"{snoring.get('total_snoring_episodes_display', '0')} ({snoring.get('snore_episode_index_display', '-')})"),
        ("Total duration with snoring", snoring.get("total_snoring_duration_display", "-")),
        ("Mean | longest episode", f"{snoring.get('mean_snoring_episode_duration_display', '-')} | {snoring.get('longest_snoring_episode_duration_display', '-')}"),
    ]
    snore_bar_w = col_w - 24
    snore_bar = Drawing(snore_bar_w, 26)
    snore_segment_colors = ["#35A7A0", "#6CB68C", "#A8BA72", "#E7AA59", "#E36B6B"]
    snore_seg_w = snore_bar_w / 5.0
    for seg_index, seg_color in enumerate(snore_segment_colors):
        snore_bar.add(Rect(seg_index * snore_seg_w, 8, snore_seg_w, 10,
                           fillColor=colors.HexColor(seg_color), strokeColor=None))
    snore_pointer_x = min(snore_bar_w - 3, max(3, snore_bar_w * snore_pct / 100.0))
    snore_bar.add(Polygon([snore_pointer_x - 5, 25, snore_pointer_x + 5, 25, snore_pointer_x, 19],
                          fillColor=REPORT_INK, strokeColor=REPORT_INK))
    for pct in (0, 20, 40, 60, 80, 100):
        snore_bar.add(String(snore_bar_w * pct / 100.0, 0, f"{pct}%", fontSize=6.5, fillColor=REPORT_INK,
                             textAnchor="middle" if 0 < pct < 100 else ("start" if pct == 0 else "end")))
    snore_inner = Table([[_section_title("Snoring", f"Share of {snore_basis_word} with snoring")],
                         [snore_bar],
                         [_mini_table(snore_rows2, col_w - 24)]], colWidths=[col_w - 24])
    snore_inner.setStyle(TableStyle([
        ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    snore_card2 = _plain_card(snore_inner, col_w, padding=12)

    right_stack = Table([[pulse_card2], [Spacer(1, 10)], [snore_card2]], colWidths=[col_w])
    right_stack.setStyle(TableStyle([
        ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))

    two_col = Table([[left_stack, right_stack]], colWidths=[col_w + col_gap, col_w])
    two_col.setStyle(TableStyle([
        ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (0,0), col_gap), ('RIGHTPADDING', (1,0), (1,0), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    page2_elements.append(two_col)
    page2_elements.append(Spacer(1, 14))

    # ---------------- INTERPRETATION ----------------
    interpretation = report_context.get("report_interpretation", {}) or {}
    def _esc(s):
        return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    def _bullets(items, empty):
        items = [i for i in (items or []) if str(i).strip()]
        return "<br/>".join(f"• {_esc(i)}" for i in items) or empty
    interp_rows = [
        ("Diagnosis", f"<b>{_esc(_text_or_dash(interpretation.get('diagnosis')))}</b>"),
        ("Findings", _bullets(interpretation.get("findings"), "• No additional findings available.")),
        ("Recommendations", _bullets(interpretation.get("recommendations"), "• No recommendations available.")),
    ]
    if interpretation.get("manual_items"):
        interp_rows.append(("Selected notes", _bullets(interpretation.get("manual_items"), "")))
    if str(interpretation.get("custom_note") or "").strip():
        interp_rows.append(("Custom note", _esc(interpretation.get("custom_note"))))
    interp_key_w = (page1_content_width - 24) * 0.2
    interp_table = Table(
        [[Paragraph(k, _ps("IntK", 8, REPORT_INK, bold=True, leading=11)),
          Paragraph(v, _ps("IntV", 8, REPORT_INK, leading=11))] for k, v in interp_rows],
        colWidths=[interp_key_w, page1_content_width - 24 - interp_key_w],
    )
    interp_table.setStyle(TableStyle([
        ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LINEBELOW', (0,0), (-1,-2), 0.5, REPORT_LINE),
    ]))
    interp_inner = Table([[_section_title("Interpretation", " - To be reviewed by the reporting physician")],
                          [interp_table]], colWidths=[page1_content_width - 24])
    interp_inner.setStyle(TableStyle([
        ('LEFTPADDING', (0,0), (-1,-1), 0), ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 2), ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    # Interpretation must stay on page 2: measure the space left under the
    # two-column block and shrink the card into it if the text is very long.
    from reportlab.platypus import KeepInFrame
    _, two_col_h = two_col.wrap(page1_content_width, doc.height)
    _, header_h = page2_elements[0].wrap(page1_content_width, doc.height)
    space_left = doc.height - header_h - 12 - two_col_h - 14 - 40
    interp_card = _plain_card(interp_inner, page1_content_width, padding=12)
    page2_elements.append(KeepInFrame(page1_content_width, max(120, space_left), [interp_card], mode="shrink"))

    # Add page 2 content directly so reportlab can paginate cleanly without odd blank-page behavior.
    elements.extend(page2_elements)

    if isinstance(dashboard_screenshot_path, (str, os.PathLike)):
        attachment_paths = [str(dashboard_screenshot_path)]
    else:
        attachment_paths = [
            str(path) for path in (dashboard_screenshot_path or []) if path
        ]
    attachment_paths = [path for path in attachment_paths if os.path.exists(path)]
    vector_hypnogram_paths = [
        path for path in attachment_paths
        if Path(path).suffix.lower() == ".pdf"
        and (
            "psg_hypnogram" in Path(path).stem.lower()
            or "full_psg" in Path(path).stem.lower()
        )
    ]
    raster_attachment_paths = [
        path for path in attachment_paths if path not in vector_hypnogram_paths
    ]

    # ReportLab cannot import an existing PDF page as a Flowable. Create one
    # numbered placeholder page per vector chart; after the report is built,
    # PyMuPDF places the original vector page over that placeholder.
    placeholder_pages = []   # 0-based page index of each placeholder, filled while the PDF is built
    for _vector_path in vector_hypnogram_paths:
        elements.append(PageBreak())
        elements.append(_PageMarker(placeholder_pages))
        elements.append(Spacer(1, 1))

    dashboard_section = _build_dashboard_screenshot_section(
        raster_attachment_paths,
        doc,
        styles,
    )
    if dashboard_section:
        elements.append(PageBreak())
        elements.extend(dashboard_section)

    footer_left = f"Patient: {patient_name} | ID {_first(patient_data, 'patient_id', default='-')}"
    numbered_canvas = _make_numbered_canvas(footer_left, "")
    try:
        doc.build(elements, canvasmaker=numbered_canvas)
        return _overlay_vector_report_pages(
            pdf_path,
            vector_hypnogram_paths,
            start_page_index=2,
            page_indexes=placeholder_pages,
        )
    except PermissionError:
        fallback_path = _default_report_output_path("sleep_report_clean.pdf", unique=True)
        if os.path.abspath(fallback_path) == os.path.abspath(pdf_path):
            raise

        fallback_doc = SimpleDocTemplate(
            fallback_path,
            pagesize=A4,
            leftMargin=30,
            rightMargin=30,
            topMargin=30,
            bottomMargin=30,
        )
        placeholder_pages.clear()
        fallback_doc.build(elements, canvasmaker=numbered_canvas)
        return _overlay_vector_report_pages(
            fallback_path,
            vector_hypnogram_paths,
            start_page_index=2,
            page_indexes=placeholder_pages,
        )


def generate_sleep_report_pro(pdf_path=None):
    """Generate professional sleep report format"""
    if pdf_path is None:
        pdf_path = _default_report_output_path("sleep_report_pro.pdf")

    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # ---------------- HEADER ----------------
    title = Paragraph("<b>SLEEP STUDY REPORT</b>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 12))

    # ---------------- RECORDING INFORMATION ----------------
    subtitle = Paragraph("<b>Recording Information</b>", styles['Heading2'])
    elements.append(subtitle)
    elements.append(Spacer(1, 8))

    recording_data = [
        ["Patient Name", "MD. JAWED ALAM", "Study Date", "7/28/2022"],
        ["Sex", "M", "Device", "Alice NightOne"],
        ["DOB", "2/3/1978", "Height", "5'10\""],
        ["Age", "45 years", "BMI", "41.2"],
        ["Physician", "Dr. Smith", "Study Type", "Type II"],
        ["Referring", "Dr. Johnson", "Total Study Time", "479.9 min"],
    ]

    table = Table(recording_data, colWidths=[90, 140, 90, 140])
    table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10)
    ]))
    elements.append(table)
    elements.append(Spacer(1, 15))

    # ---------------- SLEEP STAGING ----------------
    subtitle = Paragraph("<b>Sleep Staging</b>", styles['Heading2'])
    elements.append(subtitle)
    elements.append(Spacer(1, 8))

    staging_data = [
        ["Parameter", "Value", "Reference Range"],
        ["Total Sleep Time", "408.9 min", "Normal: >420 min"],
        ["Sleep Efficiency", "85.2%", "Normal: >85%"],
        ["Sleep Latency", "12.5 min", "Normal: <30 min"],
        ["Wake After Sleep Onset", "58.7 min", "Normal: <30 min"],
        ["Stage N1", "45.2 min (11.1%)", "Normal: 5-10%"],
        ["Stage N2", "215.8 min (52.8%)", "Normal: 45-55%"],
        ["Stage N3", "98.5 min (24.1%)", "Normal: 15-25%"],
        ["REM Sleep", "49.4 min (12.1%)", "Normal: 20-25%"],
    ]

    table = Table(staging_data, colWidths=[120, 120, 120])
    table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9)
    ]))
    elements.append(table)
    elements.append(Spacer(1, 15))

    # ---------------- RESPIRATORY ANALYSIS ----------------
    subtitle = Paragraph("<b>Respiratory Analysis</b>", styles['Heading2'])
    elements.append(subtitle)
    elements.append(Spacer(1, 8))

    resp_summary_data = [
        ["Parameter", "Value", "Severity"],
        ["AHI", "41.1 events/hour", "Severe"],
        ["OAI", "5.7 events/hour", "Mild"],
        ["CAI", "0.2 events/hour", "Normal"],
        ["MAI", "33.9 events/hour", "Severe"],
        ["Lowest SpO2", "76%", "Severe"],
        ["Time SpO2 <90%", "30.2%", "Severe"],
        ["Time SpO2 <85%", "4.9%", "Moderate"],
    ]

    table = Table(resp_summary_data, colWidths=[120, 120, 80])
    table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('TEXTCOLOR', (2,2), (-1,-1), colors.red if 'Severe' in str(['Severe']) else colors.black)
    ]))
    elements.append(table)
    elements.append(Spacer(1, 15))

    # ---------------- DETAILED EVENTS ----------------
    subtitle = Paragraph("<b>Detailed Respiratory Events</b>", styles['Heading2'])
    elements.append(subtitle)
    elements.append(Spacer(1, 8))

    detailed_events = [
        ["Event Type", "Index", "Total Events", "Mean Duration", "Max Duration"],
        ["Obstructive Apneas", "5.7", "39", "28.2 sec", "95 sec"],
        ["Central Apneas", "0.2", "2", "10.5 sec", "11 sec"],
        ["Mixed Apneas", "0.9", "6", "29.8 sec", "101 sec"],
        ["Hypopneas", "33.9", "231", "21.0 sec", "56 sec"],
    ]

    table = Table(detailed_events, colWidths=[100, 80, 80, 80, 80])
    table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9)
    ]))
    elements.append(table)
    elements.append(Spacer(1, 15))

    # ---------------- CARDIAC ANALYSIS ----------------
    subtitle = Paragraph("<b>Cardiac Analysis</b>", styles['Heading2'])
    elements.append(subtitle)
    elements.append(Spacer(1, 8))

    cardiac_data = [
        ["Parameter", "Value", "Reference Range"],
        ["Mean Heart Rate", "87.8 bpm", "Normal: 60-100 bpm"],
        ["Maximum Heart Rate", "106 bpm", "Normal: <100 bpm"],
        ["Minimum Heart Rate", "73 bpm", "Normal: >60 bpm"],
        ["Heart Rate Variability", "Normal", "Normal: Present"],
    ]

    table = Table(cardiac_data, colWidths=[120, 120, 120])
    table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9)
    ]))
    elements.append(table)
    elements.append(Spacer(1, 15))

    # ---------------- POSITIONAL ANALYSIS ----------------
    subtitle = Paragraph("<b>Positional Analysis</b>", styles['Heading2'])
    elements.append(subtitle)
    elements.append(Spacer(1, 8))

    position_data = [
        ["Position", "Time (min)", "Percentage", "AHI"],
        ["Supine", "145.2", "35.5%", "58.3"],
        ["Right", "89.7", "21.9%", "32.1"],
        ["Left", "112.4", "27.5%", "38.7"],
        ["Prone", "61.6", "15.1%", "28.9"],
    ]

    table = Table(position_data, colWidths=[80, 80, 80, 80])
    table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9)
    ]))
    elements.append(table)
    elements.append(Spacer(1, 15))

    # ---------------- SUMMARY & RECOMMENDATIONS ----------------
    subtitle = Paragraph("<b>Summary & Recommendations</b>", styles['Heading2'])
    elements.append(subtitle)
    elements.append(Spacer(1, 8))

    summary_text = """
    <b>Findings:</b><br/>
    • Severe obstructive sleep apnea (AHI: 41.1 events/hour)<br/>
    • Significant oxygen desaturation (Lowest SpO2: 76%)<br/>
    • Poor sleep quality (Sleep Efficiency: 85.2%)<br/>
    • Positional dependence noted (worse in supine position)<br/><br/>
    
    <b>Recommendations:</b><br/>
    • Immediate evaluation for CPAP therapy<br/>
    • Weight loss program recommended (BMI: 41.2)<br/>
    • Positional therapy may be beneficial<br/>
    • Follow-up sleep study after 3 months of therapy<br/>
    • Consider ENT evaluation for upper airway obstruction<br/>
    """

    elements.append(Paragraph(summary_text, styles['Normal']))
    elements.append(Spacer(1, 20))

    # ---------------- FOOTER ----------------
    footer_text = "This report was generated on " + str(styles['Normal'].fontName) + " and is for medical professional use only."
    elements.append(Paragraph(footer_text, styles['Normal']))

    doc.build(elements)
    pass
    return os.path.abspath(pdf_path)


def generate_sleep_report_summary(pdf_path=None):
    """Generate summary sleep report format"""
    if pdf_path is None:
        pdf_path = _default_report_output_path("sleep_report_summary.pdf")

    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    # ---------------- HEADER ----------------
    title = Paragraph("<b>SLEEP STUDY SUMMARY</b>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 12))

    # ---------------- KEY METRICS ----------------
    subtitle = Paragraph("<b>Key Metrics</b>", styles['Heading2'])
    elements.append(subtitle)
    elements.append(Spacer(1, 8))

    key_metrics = [
        ["Parameter", "Value", "Status"],
        ["AHI", "41.1 events/hour", "❌ Severe"],
        ["Sleep Efficiency", "85.2%", "⚠️ Borderline"],
        ["Lowest SpO2", "76%", "❌ Severe"],
        ["Total Sleep Time", "408.9 min", "✅ Normal"],
        ["BMI", "41.2", "❌ Obese"],
    ]

    table = Table(key_metrics, colWidths=[120, 120, 80])
    table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10)
    ]))
    elements.append(table)
    elements.append(Spacer(1, 15))

    # ---------------- QUICK SUMMARY ----------------
    quick_summary = """
    <b>Diagnosis:</b> Severe Obstructive Sleep Apnea<br/><br/>
    <b>Treatment Recommended:</b> CPAP Therapy<br/><br/>
    <b>Follow-up Required:</b> Yes - within 2 weeks<br/><br/>
    <b>Urgency:</b> High - Immediate treatment needed
    """

    elements.append(Paragraph(quick_summary, styles['Normal']))
    elements.append(Spacer(1, 20))

    doc.build(elements)
    pass
    return os.path.abspath(pdf_path)


class PDFViewerWidget(QDialog):
    def __init__(
        self,
        pdf_path=None,
        parent=None,
        patient_data=None,
        analysis_results=None,
        dashboard_screenshot_path=None,
        report_context=None,
        allow_print=False,
        embedded=False,
    ):
        super().__init__(parent)
        self.pdf_path = pdf_path
        self.patient_data = patient_data or {}
        self.analysis_results = analysis_results or {}
        self.dashboard_screenshot_path = dashboard_screenshot_path
        self.report_context = report_context or {}
        self.allow_print = allow_print
        self._handling_fallback = False
        self._rendered_pdf_pages = []
        self._embedded = bool(embedded)
        self.setWindowTitle("Report")
        if self._embedded:
            # A plain child widget of the main window (shown by the caller): no separate OS window.
            from PyQt5.QtGui import QPalette, QColor
            self.setWindowFlags(Qt.Widget)
            self.setAttribute(Qt.WA_DeleteOnClose, True)
            palette = self.palette()
            palette.setColor(QPalette.Window, QColor("#e5e7eb"))
            self.setPalette(palette)
            self.setAutoFillBackground(True)  # a child widget is transparent by default
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            # Open the report viewer at the available screen size. A fixed size
            # forced the PDF container to appear in its small/default geometry.
            self.setMinimumSize(1000, 700)
        self.generating = False
        self.init_ui()
        if not self._embedded:
            self.showMaximized()

        if pdf_path and os.path.exists(pdf_path):
            QTimer.singleShot(500, lambda: self.load_pdf(pdf_path))

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(10, 5, 10, 5)

        title_label = QLabel("Report")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")

        generate_btn = QPushButton("Save PDF")
        generate_btn.setFixedSize(85, 25)
        generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 4px 12px;
                font-size: 11px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        generate_btn.clicked.connect(self.generate_new_report)

        if self.allow_print:
            print_btn = QPushButton("Print PDF")
            print_btn.setFixedSize(85, 25)
            print_btn.setStyleSheet("""
                QPushButton {
                    background-color: #d97706;
                    color: white;
                    border: none;
                    padding: 4px 12px;
                    font-size: 11px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #b45309;
                }
            """)
            print_btn.clicked.connect(self.print_pdf)
            header_layout.addWidget(print_btn)

        close_btn = QPushButton("Close")
        close_btn.setFixedSize(80, 25)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                color: #333;
                border: 1px solid #ccc;
                padding: 2px 8px;
                font-size: 11px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
        """)
        close_btn.clicked.connect(self.close)

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(generate_btn)
        header_layout.addWidget(close_btn)

        header_widget = QLabel()
        header_widget.setLayout(header_layout)
        header_widget.setStyleSheet("background-color: #f8f8f8; border-bottom: 1px solid #ddd;")
        header_widget.setFixedHeight(45)
        
        # Native in-app PDF pages. QtWebEngine's PDF plugin is inconsistent on
        # Windows and used to fall back to launching Adobe/a browser. Rendering
        # with MuPDF keeps the report inside this application on every OS.
        self.pdf_scroll_area = QScrollArea(self)
        self.pdf_scroll_area.setWidgetResizable(True)
        self.pdf_scroll_area.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.pdf_scroll_area.setStyleSheet("QScrollArea { background: #dfe3e8; border: none; }")

        self.pdf_pages_widget = QWidget()
        self.pdf_pages_widget.setStyleSheet("background: #dfe3e8;")
        self.pdf_pages_layout = QVBoxLayout(self.pdf_pages_widget)
        self.pdf_pages_layout.setContentsMargins(24, 24, 24, 24)
        self.pdf_pages_layout.setSpacing(18)
        self.pdf_pages_layout.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.pdf_scroll_area.setWidget(self.pdf_pages_widget)

        layout.addWidget(header_widget)
        layout.addWidget(self.pdf_scroll_area)
        self.setLayout(layout)

    def print_pdf(self):
        """Open the system print dialog for the current PDF."""
        if not self.pdf_path or not os.path.exists(self.pdf_path):
            QMessageBox.warning(self, "PDF Not Found", "The PDF file does not exist yet.")
            return

        printer = QPrinter(QPrinter.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec_() != QDialog.Accepted:
            return

        try:
            if not self._rendered_pdf_pages:
                self.load_pdf(self.pdf_path)
            painter = QPainter(printer)
            if not painter.isActive():
                raise RuntimeError("Printer painter could not be started.")
            page_rect = printer.pageRect()
            for index, page_pixmap in enumerate(self._rendered_pdf_pages):
                if index:
                    printer.newPage()
                scale = min(
                    page_rect.width() / max(page_pixmap.width(), 1),
                    page_rect.height() / max(page_pixmap.height(), 1),
                )
                target_width = max(1, int(page_pixmap.width() * scale))
                target_height = max(1, int(page_pixmap.height() * scale))
                x = page_rect.x() + (page_rect.width() - target_width) // 2
                y = page_rect.y() + (page_rect.height() - target_height) // 2
                painter.drawPixmap(
                    QRect(x, y, target_width, target_height),
                    page_pixmap,
                    page_pixmap.rect(),
                )
            painter.end()
            QMessageBox.information(self, "Print Sent", "The PDF was sent to the printer.")
        except Exception as error:
            QMessageBox.critical(self, "Print Failed", f"Could not print the PDF:\n{error}")

    def generate_new_report(self):
        """Generate a new report and save it to a local file."""
        if self.generating:
            return

        self.generating = True

        try:
            suggested_path = _default_report_output_path("sleep_report.pdf")
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Report",
                suggested_path,
                "PDF Files (*.pdf)"
            )
            if not file_path:
                return

            if not file_path.lower().endswith(".pdf"):
                file_path += ".pdf"

            # Prefer the analysis that came with the currently loaded upload.
            # Only fall back to the newest JSON on disk if we do not already
            # have report metrics in memory, otherwise a newer unrelated file
            # can overwrite the real values for this report.
            if not self.analysis_results:
                latest_analysis_results = _load_latest_analysis_results()
                if latest_analysis_results:
                    self.analysis_results = latest_analysis_results

            pdf_path = generate_sleep_report(
                pdf_path=file_path,
                patient_data=self.patient_data,
                analysis_results=self.analysis_results,
                dashboard_screenshot_path=self.dashboard_screenshot_path,
                report_context=self.report_context,
            )

            self.pdf_path = pdf_path
            saved_box = QMessageBox(self)
            saved_box.setWindowFlags(
                saved_box.windowFlags() & ~Qt.WindowContextHelpButtonHint
            )
            saved_box.setIcon(QMessageBox.Information)
            saved_box.setWindowTitle("Report Saved")
            saved_box.setText(f"Report saved locally to:\n{pdf_path}")
            saved_box.setStandardButtons(QMessageBox.Ok)
            saved_box.setDefaultButton(QMessageBox.Ok)

            ok_button = saved_box.button(QMessageBox.Ok)
            if ok_button is not None:
                ok_button.setMinimumSize(82, 32)
                ok_button.setStyleSheet("""
                    QPushButton {
                        background-color: #2563eb;
                        color: #ffffff;
                        border: 1px solid #1d4ed8;
                        border-radius: 5px;
                        padding: 5px 16px;
                        font-size: 12px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background-color: #1d4ed8;
                        border-color: #1e40af;
                    }
                    QPushButton:pressed {
                        background-color: #1e3a8a;
                        border-color: #172554;
                    }
                """)

            saved_box.exec_()
            QTimer.singleShot(100, lambda: self.load_pdf(pdf_path))
        finally:
            # The file picker and PDF generation are synchronous/modal, so no
            # delayed debounce is needed here. Keeping this flag set for two
            # extra seconds made the next Save PDF click get silently ignored.
            self.generating = False

    def load_pdf(self, pdf_path):
        """Render every PDF page inside the application (no browser/plugin)."""
        if not os.path.exists(pdf_path):
            self.show_error("PDF file not found", f"The file {pdf_path} could not be found.")
            return

        self.pdf_path = pdf_path
        self._handling_fallback = False
        self._clear_pdf_pages()
        try:
            import pymupdf

            document = pymupdf.open(os.path.abspath(pdf_path))
            try:
                if document.page_count <= 0:
                    raise ValueError("The PDF contains no pages.")

                viewport_width = max(700, self.pdf_scroll_area.viewport().width() - 64)
                first_width = max(float(document[0].rect.width), 1.0)
                render_scale = max(1.25, min(2.0, viewport_width / first_width))

                for page_number in range(document.page_count):
                    page = document.load_page(page_number)
                    rendered = page.get_pixmap(
                        matrix=pymupdf.Matrix(render_scale, render_scale),
                        colorspace=pymupdf.csRGB,
                        alpha=False,
                    )
                    image = QImage(
                        rendered.samples,
                        rendered.width,
                        rendered.height,
                        rendered.stride,
                        QImage.Format_RGB888,
                    ).copy()
                    page_pixmap = QPixmap.fromImage(image)
                    self._rendered_pdf_pages.append(page_pixmap)

                    page_label = QLabel(self.pdf_pages_widget)
                    page_label.setAlignment(Qt.AlignCenter)
                    page_label.setPixmap(page_pixmap)
                    page_label.setStyleSheet(
                        "background: white; border: 1px solid #b8c0cc;"
                    )
                    self.pdf_pages_layout.addWidget(page_label, 0, Qt.AlignHCenter)
            finally:
                document.close()
            pass
        except Exception as error:
            self.show_pdf_fallback_message(str(error))

    def _clear_pdf_pages(self):
        """Remove the currently rendered report pages/messages."""
        self._rendered_pdf_pages = []
        while self.pdf_pages_layout.count():
            item = self.pdf_pages_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def show_pdf_fallback_message(self, error_text=None):
        """Keep viewer failures inside the application; never auto-launch another app."""
        message = "The PDF could not be displayed inside the application."
        if error_text:
            message += f"\n\nViewer error: {error_text}"
        if self.pdf_path:
            message += f"\n\nPDF file:\n{self.pdf_path}"
        self.show_error("Unable to display PDF", message)

    def show_error(self, title, message):
        """Show an error message in the native viewer area."""
        self._clear_pdf_pages()
        error_label = QLabel(f"{title}\n\n{message}", self.pdf_pages_widget)
        error_label.setAlignment(Qt.AlignCenter)
        error_label.setWordWrap(True)
        error_label.setMinimumWidth(600)
        error_label.setStyleSheet(
            "QLabel { background: white; color: #7f1d1d; border: 1px solid #fecaca; "
            "border-radius: 8px; padding: 28px; font-size: 13px; }"
        )
        self.pdf_pages_layout.addWidget(error_label, 0, Qt.AlignHCenter | Qt.AlignTop)

    def set_pdf_path(self, pdf_path):
        """Set a new PDF path and load it."""
        self.pdf_path = pdf_path
        if os.path.exists(pdf_path):
            QTimer.singleShot(500, lambda: self.load_pdf(pdf_path))
