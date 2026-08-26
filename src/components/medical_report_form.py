from reportlab.platypus import Flowable, SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak, KeepTogether
from reportlab.graphics.shapes import Drawing, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt, QUrl, QTimer
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
from PyQt5.QtWebEngineWidgets import QWebEngineView
import json
from pathlib import Path
from datetime import datetime
import os
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


class SilentPdfWebEnginePageMixin:
    """Filter noisy PDF.js console errors that do not block report viewing."""

    _IGNORED_CONSOLE_SNIPPETS = (
        "Cannot read property 'getStrings' of undefined",
        "Cannot read properties of undefined (reading 'getStrings')",
    )

    def javaScriptConsoleMessage(self, level, message, line_number, source_id):
        text = str(message or "")
        if any(snippet in text for snippet in self._IGNORED_CONSOLE_SNIPPETS):
            print("Ignoring embedded PDF viewer console warning:", text)
            return
        super().javaScriptConsoleMessage(level, message, line_number, source_id)


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

    elements = [_section_heading("FULL PSG DATA", styles), Spacer(1, 12)]
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
        max_height = doc.height - 130
        scale = min(max_width / image_width, max_height / image_height)
        screenshot = Image(
            image_path,
            width=image_width * scale,
            height=image_height * scale,
        )

        graph_label = f"Full PSG Graph {index}"
        try:
            stem_name = Path(image_path).stem
            if "psg_hypnogram" in stem_name or "full_psg" in stem_name:
                graph_label = "Full-Duration PSG Overview"
        except Exception:
            pass

        return [
            Paragraph(f"<b>{graph_label}</b>", styles["ImageLabel"]),
            Spacer(1, 6),
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
        print(f"📝 Loaded latest analysis JSON: {latest_path}")
        return payload if isinstance(payload, dict) else {}
    except Exception as error:
        print(f"⚠️ Could not load latest analysis JSON {latest_path}: {error}")
        return {}


def _get_report_logo_path():
    logo_path = get_asset_path("assets/images/dmk_logo.png")
    return logo_path if Path(logo_path).exists() else None


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
    return _rounded_card(table, width=table_width, padding=0)


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
        [cell("History"), cell(patient_data.get("history")), cell("Comments"), cell(patient_data.get("comments"))],
    ]


def generate_sleep_report(pdf_path=None, patient_data=None, analysis_results=None, dashboard_screenshot_path=None, report_context=None):
    """Generate basic sleep report format with improved visual presentation"""
    if pdf_path is None:
        pdf_path = _default_report_output_path("sleep_report_clean.pdf", unique=True)

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

    # ---------------- HEADER CONTAINER ----------------
    logo_path = _get_report_logo_path()
    logo_image = None
    if logo_path:
        try:
            logo_image = Image(logo_path, width=90, height=60)
        except Exception as error:
            print(f"⚠️ Could not load report logo: {error}")

    report_subtitle = (
        f"Professional Sleep Analysis Report<br/>"
        f"Generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}"
    )
    header_data = [[
        logo_image if logo_image else "",
        Table(
            [
                [Paragraph("<b>SLEEP TEST REPORT</b>", styles["Title"])],
                [Paragraph(report_subtitle, styles["ReportSubTitle"])],
            ],
            colWidths=[page1_content_width - 118],
        )
    ]]

    header_container = Table(header_data, colWidths=[102, page1_content_width - 102])
    header_container.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.white),
        ('BORDER', (0,0), (-1,-1), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (0,0), 'LEFT'),
        ('ALIGN', (1,0), (1,0), 'CENTER'),
    ]))
    page1_elements.append(_rounded_card(header_container, width=page1_content_width, padding=6))
    page1_elements.append(Spacer(1, 10))

    # ---------------- PATIENT INFO CONTAINER ----------------
    patient_table_data = _build_patient_information_rows(patient_data, styles)
    patient_col_widths = [page1_content_width * ratio for ratio in (0.19, 0.31, 0.19, 0.31)]
    patient_table = Table(patient_table_data, colWidths=patient_col_widths)
    patient_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, CARD_GRID_COLOR),
        
        # Heading row (row 0) - colored background, bold
        ('SPAN', (0,0), (-1,0)),
        ('BACKGROUND', (0,0), (-1,0), CARD_HEADER_BG),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('TOPPADDING', (0,0), (-1,0), 5),
        ('BOTTOMPADDING', (0,0), (-1,0), 5),
        ('LEFTPADDING', (0,0), (-1,0), 6),
        
        # Data rows (row 1 onwards)
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 7),
        ('ALIGN', (0,1), (-1,-1), 'LEFT'),
        ('LEFTPADDING', (0,1), (-1,-1), 7),
        ('RIGHTPADDING', (0,1), (-1,-1), 7),
        ('TOPPADDING', (0,1), (-1,-1), 5),
        ('BOTTOMPADDING', (0,1), (-1,-1), 5),
        ('TEXTCOLOR', (0,1), (-1,-1), CARD_TEXT_MUTED),
    ]))
    page1_elements.append(_rounded_card(patient_table, width=page1_content_width, padding=0))
    page1_elements.append(Spacer(1, 12))

    # ---------------- TIME INFORMATION CONTAINER ----------------
    times_data = [
        ["TIME INFORMATION", "", "", ""],
        ["Lights off", time_information.get("lights_off", "-"), "TRT", time_information.get("trt_display", "-")],
        ["Lights on", time_information.get("lights_on", "-"), "TIB", time_information.get("tib_display", "-")],
        # ["", "", "MT", "408.9 min"],
    ]

    time_table = Table(times_data, colWidths=[page1_content_width / 4.0] * 4)
    time_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, CARD_GRID_COLOR),
        
        # Heading row (row 0) - colored background, bold
        ('SPAN', (0,0), (-1,0)),
        ('BACKGROUND', (0,0), (-1,0), CARD_HEADER_BG),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('TOPPADDING', (0,0), (-1,0), 5),
        ('BOTTOMPADDING', (0,0), (-1,0), 5),
        ('LEFTPADDING', (0,0), (-1,0), 6),
        
        # Data rows (row 1 onwards)
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('ALIGN', (0,1), (-1,-1), 'CENTER'), 
        ('LEFTPADDING', (0,1), (-1,-1), 6),
        ('RIGHTPADDING', (0,1), (-1,-1), 6),
        ('TOPPADDING', (0,1), (-1,-1), 6),
        ('BOTTOMPADDING', (0,1), (-1,-1), 6),
        ('TEXTCOLOR', (0,1), (-1,-1), CARD_TEXT_MUTED),
    ]))
    page1_elements.append(_rounded_card(time_table, width=page1_content_width, padding=0))
    page1_elements.append(Spacer(1, 12))

    # ---------------- SUMMARY CONTAINER ----------------
    summary_data = [
        ["RESPIRATORY EVENT SUMMARY", "", "", "", "", "", "", ""],
        [
            "AHI/REI", respiratory_summary.get("ahi_rei_display", "0.0"),
            "OAI", respiratory_summary.get("oai_display", "0.0"),
            "CAI", respiratory_summary.get("cai_display", "0.0"),
            "Hypopnea", respiratory_summary.get("hypopnea_display", "0.0"),
        ]
    ]

    summary_col_widths = [page1_content_width * ratio for ratio in (0.12, 0.12, 0.11, 0.12, 0.11, 0.12, 0.18, 0.12)]
    summary_table = Table(summary_data, colWidths=summary_col_widths)
    summary_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, CARD_GRID_COLOR),
        
        # Heading row (row 0) - colored background, bold
        ('SPAN', (0,0), (-1,0)),
        ('BACKGROUND', (0,0), (-1,0), CARD_HEADER_BG),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('TOPPADDING', (0,0), (-1,0), 5),
        ('BOTTOMPADDING', (0,0), (-1,0), 5),
        ('LEFTPADDING', (0,0), (-1,0), 6),
        
        # Data rows (row 1 onwards)
        ('BACKGROUND', (0,1), (-1,-1), CARD_SUBHEADER_BG),
        ('ALIGN', (0,1), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('TEXTCOLOR', (0,1), (-1,-1), colors.black),
        ('TEXTCOLOR', (1,1), (1,1), CARD_ACCENT),  # AHI value
        ('TEXTCOLOR', (3,1), (3,1), CARD_ACCENT),  # OAI
        ('TEXTCOLOR', (5,1), (5,1), CARD_ACCENT),  # CAI
        ('TEXTCOLOR', (7,1), (7,1), CARD_ACCENT),  # Hypopnea
        ('LEFTPADDING', (0,1), (-1,-1), 8),
        ('RIGHTPADDING', (0,1), (-1,-1), 8),
        ('TOPPADDING', (0,1), (-1,-1), 8),
        ('BOTTOMPADDING', (0,1), (-1,-1), 8),
        ('VALIGN', (0,1), (-1,-1), 'MIDDLE'),
    ]))
    page1_elements.append(_rounded_card(summary_table, width=page1_content_width, padding=0))
    page1_elements.append(Spacer(1, 12))

    # ---------------- Severity Meter ----------------
     # ---------------- SEVERITY INDICATOR ----------------
    def create_severity_meter(value=0.0):
        width = page1_content_width - 16
        height = 20
        total = 50

        d = Drawing(width, 50)

        # ---- Color Segments ----
        green_w  = (5 / total) * width
        yellow_w = (10 / total) * width
        orange_w = (10 / total) * width
        red_w    = (25 / total) * width

        x = 0
 
        # Green (0-5)
        d.add(Rect(
            x, 20, green_w, height,
            fillColor=colors.HexColor("#38B000"),
            strokeColor=None
        ))
        x += green_w

        # Yellow (5-15)
        d.add(Rect(
            x, 20, yellow_w, height,
            fillColor=colors.HexColor("#FFFF00"),
            strokeColor=None
        ))
        x += yellow_w

        # Orange (15-25)
        d.add(Rect(
            x, 20, orange_w, height,
            fillColor=colors.HexColor("#FFA500"),
            strokeColor=None
        ))
        x += orange_w

        # Dark Red (25-50)
        d.add(Rect(
            x, 20, red_w, height,
            fillColor=colors.HexColor("#FF0000"),
            strokeColor=None
        ))

        # Outer Border
        d.add(Rect(
            0, 20, width, height,
            fillColor=None,
            strokeColor=colors.black,
            strokeWidth=1
        ))

        # ---- Current Value ----
        marker_x = (value / total) * width

        d.add(String(
            marker_x - 10,
            43,
            f"{value:.1f}",
            fontSize=10,
            fillColor=colors.black
        ))

        # ---- Bottom Scale ----
        for i in range(0, 51, 10):
            label_x = (i / total) * width

            d.add(String(
                label_x - 5,
                5,
                str(i),
                fontSize=8
            ))

        return d

   

    
    severity_meter = create_severity_meter(float(respiratory_summary.get("severity_value", 0.0) or 0.0))
    severity_wrapper = Table([[severity_meter]], colWidths=[page1_content_width])
    severity_wrapper.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.white),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    page1_elements.append(_rounded_card(severity_wrapper, width=page1_content_width, padding=0))
    page1_elements.append(Spacer(1, 12))

    # ---------------- RESPIRATORY EVENTS CONTAINER ----------------
    # ✅ Full structured data (exact image)
    respiratory_rows = respiratory_summary.get("rows", [])
    total_row = respiratory_summary.get("total_row", {}) or {}
    rei_in_position = respiratory_summary.get("rei_in_position", {}) or {}
    row_lookup = {
        row.get("name"): row for row in respiratory_rows
    }
    central_row = row_lookup.get("Central Apneas", {})
    obstructive_row = row_lookup.get("Obstructive Apneas", {})
    mixed_row = row_lookup.get("Mixed Apneas", {})
    hypopnea_row = row_lookup.get("Hypopneas", {})

    resp_data = [
        ["RESPIRATORY EVENTS", "", "", "", "", "", "", "", "", ""],
        ["", "Index\n(#/hour)", "Total # of\nEvents", "Mean duration\n(sec)", "Max duration\n(sec)", "# of Events by Position", "", "", "", ""],
        ["", "", "", "", "", "Supine", "Prone", "Left", "Right", "Up"],

        ["Central Apneas", central_row.get("index_display", "0.0"), central_row.get("count_display", "0"), central_row.get("mean_duration_display", "0.0"), central_row.get("max_duration_display", "0.0"), str(central_row.get("positions", {}).get("Supine", 0)), str(central_row.get("positions", {}).get("Prone", 0)), str(central_row.get("positions", {}).get("Left", 0)), str(central_row.get("positions", {}).get("Right", 0)), str(central_row.get("positions", {}).get("Up", 0))],
        ["Obstructive Apneas", obstructive_row.get("index_display", "0.0"), obstructive_row.get("count_display", "0"), obstructive_row.get("mean_duration_display", "0.0"), obstructive_row.get("max_duration_display", "0.0"), str(obstructive_row.get("positions", {}).get("Supine", 0)), str(obstructive_row.get("positions", {}).get("Prone", 0)), str(obstructive_row.get("positions", {}).get("Left", 0)), str(obstructive_row.get("positions", {}).get("Right", 0)), str(obstructive_row.get("positions", {}).get("Up", 0))],
        ["Mixed Apneas", mixed_row.get("index_display", "0.0"), mixed_row.get("count_display", "0"), mixed_row.get("mean_duration_display", "0.0"), mixed_row.get("max_duration_display", "0.0"), str(mixed_row.get("positions", {}).get("Supine", 0)), str(mixed_row.get("positions", {}).get("Prone", 0)), str(mixed_row.get("positions", {}).get("Left", 0)), str(mixed_row.get("positions", {}).get("Right", 0)), str(mixed_row.get("positions", {}).get("Up", 0))],
        ["Hypopneas", hypopnea_row.get("index_display", "0.0"), hypopnea_row.get("count_display", "0"), hypopnea_row.get("mean_duration_display", "0.0"), hypopnea_row.get("max_duration_display", "0.0"), str(hypopnea_row.get("positions", {}).get("Supine", 0)), str(hypopnea_row.get("positions", {}).get("Prone", 0)), str(hypopnea_row.get("positions", {}).get("Left", 0)), str(hypopnea_row.get("positions", {}).get("Right", 0)), str(hypopnea_row.get("positions", {}).get("Up", 0))],
        ["Apneas + Hypopneas", total_row.get("index_display", "0.0"), total_row.get("count_display", "0"), total_row.get("mean_duration_display", "0.0"), total_row.get("max_duration_display", "0.0"), str(total_row.get("positions", {}).get("Supine", 0)), str(total_row.get("positions", {}).get("Prone", 0)), str(total_row.get("positions", {}).get("Left", 0)), str(total_row.get("positions", {}).get("Right", 0)), str(total_row.get("positions", {}).get("Up", 0))],
        # ["RERAs", "0.0", "0", "0.0", "0.0", "0", "", "0", "0", "0"],

        ["Total", total_row.get("index_display", "0.0"), total_row.get("count_display", "0"), total_row.get("mean_duration_display", "0.0"), total_row.get("max_duration_display", "0.0"), str(total_row.get("positions", {}).get("Supine", 0)), str(total_row.get("positions", {}).get("Prone", 0)), str(total_row.get("positions", {}).get("Left", 0)), str(total_row.get("positions", {}).get("Right", 0)), str(total_row.get("positions", {}).get("Up", 0))],

        # ["Time in Position", "", "", "", "", "51.7", "", "293.6", "64.3", "36.8"],
        ["REI in Position", "", "", "", "", rei_in_position.get("Supine", "0.0"), rei_in_position.get("Prone", "0.0"), rei_in_position.get("Left", "0.0"), rei_in_position.get("Right", "0.0"), rei_in_position.get("Up", "0.0")],
    ]

    resp_width_ratios = (0.19, 0.08, 0.10, 0.12, 0.12, 0.078, 0.078, 0.078, 0.078, 0.078)
    resp_col_widths = [page1_content_width * ratio for ratio in resp_width_ratios]
    resp_table = Table(resp_data, colWidths=resp_col_widths)

    resp_table.setStyle(TableStyle([
        # Base style
        ('GRID', (0,0), (-1,-1), 0.5, CARD_GRID_COLOR),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 7),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),

        # Heading row (row 0) - colored background, bold
        ('SPAN', (0,0), (-1,0)),
        ('BACKGROUND', (0,0), (-1,0), CARD_HEADER_BG),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('TOPPADDING', (0,0), (-1,0), 5),
        ('BOTTOMPADDING', (0,0), (-1,0), 5),
        ('LEFTPADDING', (0,0), (-1,0), 6),

        # Data rows (row 1 onwards)
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        
        # Header background
        ('BACKGROUND', (0,1), (-1,2), CARD_SUBHEADER_BG),

        # LEFT ALIGN first column
        ('ALIGN', (0,1), (0,-1), 'LEFT'),

        # ✅ Merge top header "# of Events by Position"
        ('SPAN', (5,1), (9,1)),

        # Merge empty header cells
        ('SPAN', (0,1), (0,2)),
        ('SPAN', (1,1), (1,2)),
        ('SPAN', (2,1), (2,2)),
        ('SPAN', (3,1), (3,2)),
        ('SPAN', (4,1), (4,2)),

        # Section line before Total
        ('LINEABOVE', (0,9), (-1,9), 1, CARD_BORDER_COLOR),

        # Section line before Time in Position
        ('LINEABOVE', (0,9), (-1,9), 1, CARD_BORDER_COLOR),

        # Blue color for index and duration values
        ('TEXTCOLOR', (1,2), (4,8), CARD_ACCENT),  # index + duration values
        ('TEXTCOLOR', (5,2), (9,7), CARD_ACCENT),  # position event counts
        ('TEXTCOLOR', (5,9), (9,10), CARD_ACCENT),  # position time/REI values

        # Padding
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))

    page1_elements.append(_rounded_card(resp_table, width=page1_content_width, padding=0))
    page1_elements.append(Spacer(1, 10))
    
    # Add all page 1 elements without KeepTogether (content is too large)
    elements.extend(page1_elements)
    elements.append(PageBreak())

    # ---------------- PAGE 2 ELEMENTS ----------------
    page2_elements = []

    # ==========================================
    # MAIN COLUMN WIDTHS
    # ==========================================
    LEFT_SECTION_WIDTH = content_width_half
    RIGHT_SECTION_WIDTH = content_width_half

    # ---------------- OXIMETRY CONTAINER ----------------
    oximetry = _get_section(analysis_results, "oximetry")
    spo2_tib_pct = oximetry.get("mean_spo2_tib_pct", 0.0)
    spo2_tib_pct_text = f"{float(spo2_tib_pct):.1f}" if spo2_tib_pct is not None else "-"
    oxi_data = [
        ["OXIMETRY SUMMARY", "", ""],
        ["Parameter", "% TIB", "Value"],
        ["Mean SpO2 % during sleep", "99", oximetry.get("mean_spo2_display", "0")],
        ["Min SpO2 % during sleep", "99", oximetry.get("min_spo2_display", "0")],
        ["Max SpO2 % during sleep", "99", oximetry.get("max_spo2_display", "0")],
        ["Total # of Desats", "", oximetry.get("total_desats_display", "0")],
        ["Desat Index (#/hour)", "", oximetry.get("desaturation_index_display", "0")],
        ["Hypoxic Burden", "", oximetry.get("hypoxic_burden_display", oximetry.get("desat_max_pct_display", "0"))],
        ["HB Index", "", oximetry.get("hb_index_display", "0.0 %min/h")],
        ["HB Severity", "", oximetry.get("hb_severity", "Normal")],
        ["Longest Duration", "", oximetry.get("longest_duration_display", oximetry.get("desat_max_sec_display", "0 sec"))],
        ["Total Count Event", "", oximetry.get("total_count_event_display", oximetry.get("total_desats_display", "0"))],
        # ["Desat Max (%)", "", oximetry.get("desat_max_pct_display", "0")],
        # ["Desat Max dur (sec)", "", oximetry.get("desat_max_sec_display", "0 sec")],
        # ["Lowest SpO2 % during sleep", "", oximetry.get("lowest_spo2_display", "0")],
        # ["Duration of Min SpO2 (sec)", "", oximetry.get("duration_of_min_spo2_display", "0 sec")],
        # ["Highest SpO2 % during sleep", "", oximetry.get("highest_spo2_display", "0")],
        # ["Duration of Max SpO2 (sec)", "", oximetry.get("duration_of_max_spo2_display", "0 sec")],
        # ["SpO2 < 90% duration", "", oximetry.get("duration_below_90_display", "0 sec")],
        ["SpO2 < 85% duration", "", oximetry.get("duration_below_85_display", "0 sec")],
        # ["SpO2 < 80% duration", "", oximetry.get("duration_below_80_display", "0 sec")],
        # ["Baseline SpO2", "", oximetry.get("baseline_spo2_display", "0")],
        # ["SpO2 Variability", "", oximetry.get("spo2_variability", "0")],
        # ["Oxygen Saturation Trend", "", oximetry.get("oxygen_saturation_trend", "0")],
    ]

    oxi_col_widths = [LEFT_SECTION_WIDTH * ratio for ratio in (0.69, 0.11, 0.20)]
    oxi_table = Table(oxi_data, colWidths=oxi_col_widths)

    oxi_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, CARD_GRID_COLOR),
        
        # Heading row (row 0) - colored background, bold
        ('BACKGROUND', (0,0), (-1,0), CARD_HEADER_BG),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('TOPPADDING', (0,0), (-1,0), 5),
        ('BOTTOMPADDING', (0,0), (-1,0), 5),
        ('LEFTPADDING', (0,0), (-1,0), 4),
        
        # Data rows (row 1 onwards)
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 7),
        ('BACKGROUND', (0,1), (-1,1), CARD_SUBHEADER_BG),
        
        # Align
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),

        # Blue color for values
        ('TEXTCOLOR', (1,1), (-1,-1), CARD_ACCENT),
        ('TEXTCOLOR', (0,1), (0,-1), CARD_TEXT_MUTED),

        # Padding
        ('LEFTPADDING', (0,1), (-1,-1), 5),
        ('RIGHTPADDING', (0,1), (-1,-1), 5),
        ('TOPPADDING', (0,1), (-1,-1), 4),
        ('BOTTOMPADDING', (0,1), (-1,-1), 4),

        # ✅ SECTION BREAK (important)
        # ('LINEABOVE', (0,7), (-1,7), 1, colors.black),

        # ✅ No SPAN needed - values should appear in % TIB column
        # Center align the % TIB column values
        ('ALIGN', (2,7), (2,15), 'CENTER'),
    ]))
    oxi_card = _rounded_card(oxi_table, width=LEFT_SECTION_WIDTH, padding=0)
    oxi_note_style = styles["BodyText"].clone("OximetryNoteStyle")
    oxi_note_style.fontSize = 7
    oxi_note_style.leading = 9
    oxi_note_style.textColor = CARD_TEXT_MUTED
    oxi_note = Paragraph(
        "Hypoxic burden is calculated from a fixed 95% SpO2 baseline. HB Index is normalized as total hypoxic burden divided by total recording hours.",
        oxi_note_style,
    )
    oxi_note_table = Table([[oxi_note]], colWidths=[LEFT_SECTION_WIDTH])
    oxi_note_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.white),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
    ]))
    oxi_note_card = _rounded_card(oxi_note_table, width=LEFT_SECTION_WIDTH, padding=0)
    hb_severity_data = [
        ["HB Index (%min/h)", "Severity"],
        ["0 - 5", "Normal"],
        ["5 - 30", "Mild"],
        ["30 - 70", "Moderate"],
        ["> 70", "Severe"],
    ]
    hb_col_widths = [LEFT_SECTION_WIDTH * 0.62, LEFT_SECTION_WIDTH * 0.38]
    hb_severity_table = Table(
        hb_severity_data,
        colWidths=hb_col_widths,
    )
    hb_severity_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, CARD_GRID_COLOR),
        ('BACKGROUND', (0,0), (-1,0), CARD_HEADER_BG),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 7.5),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 7),
        ('TEXTCOLOR', (0,1), (-1,-1), CARD_TEXT_MUTED),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    hb_severity_card = _rounded_card(hb_severity_table, width=LEFT_SECTION_WIDTH, padding=0)
    oxi_card_stack = Table([
        [oxi_card],
        [Spacer(1, 8)],
        [oxi_note_card],
        [Spacer(1, 8)],
        [hb_severity_card],
    ], colWidths=[LEFT_SECTION_WIDTH])
    oxi_card_stack.setStyle(TableStyle([
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))

    # ---------------- HEART RATE CONTAINER ----------------
    heart_rate = _get_section(analysis_results, "heart_rate")
    hr_data = [
        ["HEART RATE STATS", ""],
        ["Parameter", "Value"],
        ["Mean HR during sleep", heart_rate.get("mean_hr_display", "0 BPM")],
        ["Highest HR during sleep", heart_rate.get("highest_hr_display", "0 BPM")],
        ["Highest HR during TIB", heart_rate.get("highest_hr_display", "0 BPM")],
        ["Lowest HR during sleep", heart_rate.get("lowest_hr_display", "0 BPM")],
        ["Lowest HR during TIB", heart_rate.get("lowest_hr_display", "0 BPM")]
    ]

    hr_col_widths = [RIGHT_SECTION_WIDTH / 2.0, RIGHT_SECTION_WIDTH / 2.0]
    hr_table = Table(hr_data, colWidths=hr_col_widths)
    hr_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, CARD_GRID_COLOR),
        
        # Heading row (row 0) - colored background, bold
        ('BACKGROUND', (0,0), (-1,0), CARD_HEADER_BG),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('TOPPADDING', (0,0), (-1,0), 5),
        ('BOTTOMPADDING', (0,0), (-1,0), 5),
        ('LEFTPADDING', (0,0), (-1,0), 4),
        
        # Data rows (row 1 onwards)
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 7),
        ('BACKGROUND', (0,1), (-1,1), CARD_SUBHEADER_BG),
        ('ALIGN', (0,1), (-1,-1), 'CENTER'),
        ('TEXTCOLOR', (1,1), (1,-1), CARD_ACCENT),
        ('TEXTCOLOR', (0,1), (0,-1), CARD_TEXT_MUTED),
        ('LEFTPADDING', (0,1), (-1,-1), 5),
        ('RIGHTPADDING', (0,1), (-1,-1), 5),
        ('TOPPADDING', (0,1), (-1,-1), 4),
        ('BOTTOMPADDING', (0,1), (-1,-1), 4),
    ]))
    hr_card = _rounded_card(hr_table, width=RIGHT_SECTION_WIDTH, padding=0)

    # ---------------- SNORING ANALYSIS ----------------
    snoring = _get_section(analysis_results, "snoring")
    snore_table = _build_snoring_visual_section(snoring, styles, card_width=RIGHT_SECTION_WIDTH)
    snore_parameter_table = _build_snoring_parameter_table(snoring, RIGHT_SECTION_WIDTH, styles)

    # ==========================================
    # RIGHT COLUMN
    # ==========================================
    right_column_stack = Table([
        [hr_card],
        [Spacer(1, 8)],
        [snore_table],
        [Spacer(1, 8)],
        [snore_parameter_table],
    ], colWidths=[RIGHT_SECTION_WIDTH])
    right_column_stack.setStyle(TableStyle([
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))

    # ==========================================
    # MAIN SIDE-BY-SIDE LAYOUT
    # ==========================================
    page2_main_table = Table([
        [
            oxi_card_stack,
            Spacer(1, 1),
            right_column_stack
        ]
    ], colWidths=[LEFT_SECTION_WIDTH, column_gap, RIGHT_SECTION_WIDTH])
    page2_main_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))

    page2_elements.append(page2_main_table)
    page2_elements.append(Spacer(1, 20))

    # Add page 2 content directly so reportlab can paginate cleanly without odd blank-page behavior.
    elements.extend(page2_elements)
    dashboard_section = _build_dashboard_screenshot_section(dashboard_screenshot_path, doc, styles)
    if dashboard_section:
        elements.append(PageBreak())
        elements.extend(dashboard_section)

    try:
        doc.build(elements)
        print(" Basic Report Generated:", pdf_path)
        return os.path.abspath(pdf_path)
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
        fallback_doc.build(elements)
        print(" Basic Report Generated (fallback path):", fallback_path)
        return os.path.abspath(fallback_path)


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
    print("✅ Professional Report Generated:", pdf_path)
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
    print("✅ Summary Report Generated:", pdf_path)
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
    ):
        super().__init__(parent)
        self.pdf_path = pdf_path
        self.patient_data = patient_data or {}
        self.analysis_results = analysis_results or {}
        self.dashboard_screenshot_path = dashboard_screenshot_path
        self.report_context = report_context or {}
        self.allow_print = allow_print
        self._handling_fallback = False
        self.setWindowTitle("Medical Report")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setFixedSize(1200, 850)
        self.generating = False
        self.init_ui()

        if pdf_path and os.path.exists(pdf_path):
            QTimer.singleShot(500, lambda: self.load_pdf(pdf_path))

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(10, 5, 10, 5)

        title_label = QLabel("Medical Report")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")

        generate_btn = QPushButton("Generate")
        generate_btn.setFixedSize(80, 25)
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

        open_external_btn = QPushButton("Open PDF")
        open_external_btn.setFixedSize(85, 25)
        open_external_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976D2;
                color: white;
                border: none;
                padding: 4px 12px;
                font-size: 11px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #1565C0;
            }
        """)
        open_external_btn.clicked.connect(self.open_pdf_externally)

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
        header_layout.addWidget(open_external_btn)
        header_layout.addWidget(close_btn)

        header_widget = QLabel()
        header_widget.setLayout(header_layout)
        header_widget.setStyleSheet("background-color: #f8f8f8; border-bottom: 1px solid #ddd;")
        header_widget.setFixedHeight(45)
        
        # Web view for PDF, lazily imported to avoid QtWebEngine initialization at module import time
        from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView

        class SilentPdfWebEnginePage(SilentPdfWebEnginePageMixin, QWebEnginePage):
            pass

        self.web_view = QWebEngineView()
        self.web_view.setPage(SilentPdfWebEnginePage(self.web_view))
        self.web_view.settings().setAttribute(self.web_view.settings().PluginsEnabled, True)
        self.web_view.settings().setAttribute(self.web_view.settings().PdfViewerEnabled, True)
        self.web_view.settings().setAttribute(self.web_view.settings().JavascriptEnabled, True)
        self.web_view.loadFinished.connect(self.on_load_finished)

        layout.addWidget(header_widget)
        layout.addWidget(self.web_view)
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
            def _finished(success):
                if success:
                    QMessageBox.information(self, "Print Sent", "The PDF was sent to the printer.")
                else:
                    QMessageBox.warning(self, "Print Failed", "Could not print the PDF.")

            self.web_view.page().print(printer, _finished)
        except Exception as error:
            QMessageBox.critical(self, "Print Failed", f"Could not print the PDF:\n{error}")

    def generate_new_report(self):
        """Generate a new report and save it to a local file."""
        if self.generating:
            return

        self.generating = True

        try:
            suggested_path = _default_report_output_path("sleep_report_clean.pdf")
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Medical Report",
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
            QMessageBox.information(
                self,
                "Report Saved",
                f"Report saved locally to:\n{pdf_path}"
            )
            QTimer.singleShot(100, lambda: self.load_pdf(pdf_path))
        finally:
            QTimer.singleShot(2000, lambda: setattr(self, 'generating', False))

    def load_pdf(self, pdf_path):
        """Load the PDF inside the embedded viewer first."""
        if not os.path.exists(pdf_path):
            self.show_error("PDF file not found", f"The file {pdf_path} could not be found.")
            return

        self.pdf_path = pdf_path
        self._handling_fallback = False
        pdf_url = QUrl.fromLocalFile(os.path.abspath(pdf_path))
        print(f"Loading PDF in embedded viewer: {os.path.abspath(pdf_path)}")
        self.web_view.load(pdf_url)

    def on_load_finished(self, success):
        """Handle PDF load completion."""
        if success:
            print("PDF loaded successfully in viewer")
            self._handling_fallback = False
            return

        print("Failed to load PDF in viewer")
        if self._handling_fallback:
            self.show_pdf_fallback_message()
            return

        self._handling_fallback = True
        self.try_alternative_loading()

    def try_alternative_loading(self):
        """Try a data URL fallback before switching to the external viewer."""
        try:
            with open(self.pdf_path, 'rb') as file_handle:
                pdf_data = file_handle.read()

            import base64

            b64_data = base64.b64encode(pdf_data).decode('utf-8')
            data_url = f"data:application/pdf;base64,{b64_data}"
            self.web_view.load(QUrl(data_url))
            print("Trying alternative PDF loading method...")
        except Exception as error:
            self.show_pdf_fallback_message(str(error))

    def open_pdf_externally(self):
        """Open the PDF in the default system PDF application."""
        if not self.pdf_path or not os.path.exists(self.pdf_path):
            QMessageBox.warning(self, "PDF Not Found", "The PDF file does not exist yet.")
            return False

        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(self.pdf_path)))
        if not opened:
            QMessageBox.warning(
                self,
                "Open Failed",
                f"Could not open the PDF automatically.\n\nPath:\n{self.pdf_path}"
            )
        return opened

    def show_pdf_fallback_message(self, error_text=None):
        """Show a clean fallback message and open the PDF externally."""
        details = ""
        if error_text:
            details = f"<p><b>Viewer error:</b> {error_text}</p>"

        fallback_html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    padding: 32px;
                    background: #f5f7fb;
                    color: #1f2937;
                }}
                .card {{
                    max-width: 720px;
                    margin: 30px auto;
                    background: white;
                    border: 1px solid #dbe4f0;
                    border-radius: 10px;
                    padding: 28px;
                    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
                }}
                h2 {{
                    margin-top: 0;
                    color: #b45309;
                }}
                code {{
                    display: block;
                    padding: 10px;
                    background: #f3f4f6;
                    border-radius: 6px;
                    word-break: break-word;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <h2>Report Opened In PDF App</h2>
                <p>The report was generated successfully and has been opened in your default PDF application for the most reliable viewing experience.</p>
                <p>You can use the <b>Open PDF</b> button again any time to reopen it.</p>
                <code>{self.pdf_path or ''}</code>
                {details}
            </div>
        </body>
        </html>
        """
        self.web_view.setHtml(fallback_html)
        self.open_pdf_externally()

    def show_error(self, title, message):
        """Show an error message in the viewer area."""
        error_html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    padding: 40px;
                    background-color: #f5f5f5;
                    margin: 0;
                }}
                .error-container {{
                    background-color: white;
                    padding: 30px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    max-width: 600px;
                    margin: 0 auto;
                }}
                h2 {{
                    color: #d32f2f;
                    margin-top: 0;
                }}
                p {{
                    color: #666;
                    line-height: 1.5;
                }}
            </style>
        </head>
        <body>
            <div class="error-container">
                <h2>{title}</h2>
                <p>{message.replace(chr(10), '<br>')}</p>
            </div>
        </body>
        </html>
        """
        self.web_view.setHtml(error_html)

    def set_pdf_path(self, pdf_path):
        """Set a new PDF path and load it."""
        self.pdf_path = pdf_path
        if os.path.exists(pdf_path):
            QTimer.singleShot(500, lambda: self.load_pdf(pdf_path))
