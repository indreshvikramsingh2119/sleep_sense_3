from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak, KeepTogether
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog, QMessageBox
from PyQt5.QtCore import Qt, QUrl, QTimer
from PyQt5.QtWebEngineWidgets import QWebEngineView
import json
from pathlib import Path
from datetime import datetime
import os

REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_JSON_DIR = REPO_ROOT / "data" / "analysis_json"


def _build_dashboard_screenshot_section(image_paths, doc, styles):
    """Create report elements for optional dashboard screenshots."""
    if not image_paths:
        return []

    if isinstance(image_paths, (str, os.PathLike)):
        image_paths = [image_paths]

    existing_paths = [str(path) for path in image_paths if path and os.path.exists(path)]
    if not existing_paths:
        return []

    elements = [PageBreak(), Paragraph("<b>DASHBOARD SCREENSHOTS</b>", styles['Heading2']), Spacer(1, 12)]

    for index, image_path in enumerate(existing_paths, start=1):
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
        max_height = doc.height - 60
        scale = min(max_width / image_width, max_height / image_height)
        screenshot = Image(
            image_path,
            width=image_width * scale,
            height=image_height * scale,
        )

        return [
            Paragraph(f"<b>Screenshot {index}</b>", styles['Normal']),
            Spacer(1, 6),
            screenshot,
            Spacer(1, 16),
        ]
    except Exception as error:
        print(f"⚠️ Could not add dashboard screenshot to report: {error}")
        return []


def _default_report_output_path(filename):
    """Return a local user-folder path for generated report files."""
    report_dir = Path.home() / "SleepSenseReports"
    report_dir.mkdir(parents=True, exist_ok=True)
    return str(report_dir / filename)


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


def generate_sleep_report(pdf_path=None, patient_data=None, analysis_results=None, dashboard_screenshot_path=None):
    """Generate basic sleep report format with improved visual presentation"""
    if pdf_path is None:
        pdf_path = _default_report_output_path("sleep_report_clean.pdf")

    patient_data = patient_data or {}
    latest_analysis_results = _load_latest_analysis_results()
    analysis_results = latest_analysis_results or analysis_results or {}
    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                           leftMargin=30, rightMargin=30,
                           topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    elements = []
    page1_elements = []  # Elements to keep together on page 1

    # ---------------- HEADER CONTAINER ----------------
    header_container = Table([[
        Paragraph("<b>SLEEP TEST REPORT</b>", styles['Title'])
    ]], colWidths=[500])
    header_container.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.white),
        ('BORDER', (0,0), (-1,-1), 1, colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    page1_elements.append(header_container)
    page1_elements.append(Spacer(1, 8))

    # ---------------- PATIENT INFO CONTAINER ----------------
    patient_table_data = _build_patient_information_rows(patient_data, styles)
    patient_table = Table(patient_table_data, colWidths=[95, 155, 95, 155])
    patient_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        
        # Heading row (row 0) - colored background, bold
        ('SPAN', (0,0), (-1,0)),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#DCEFD8")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('TOPPADDING', (0,0), (-1,0), 3),
        ('BOTTOMPADDING', (0,0), (-1,0), 3),
        ('LEFTPADDING', (0,0), (-1,0), 6),
        
        # Data rows (row 1 onwards)
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 7),
        ('ALIGN', (0,1), (-1,-1), 'LEFT'),
        ('LEFTPADDING', (0,1), (-1,-1), 6),
        ('RIGHTPADDING', (0,1), (-1,-1), 6),
        ('TOPPADDING', (0,1), (-1,-1), 3),
        ('BOTTOMPADDING', (0,1), (-1,-1), 3),
    ]))
    page1_elements.append(patient_table)
    page1_elements.append(Spacer(1, 12))

    # ---------------- TIME INFORMATION CONTAINER ----------------
    times_data = [
        ["TIME INFORMATION", "", "", ""],
        ["Lights off", "09:00 PM", "TRT", "479.9 min"],
        ["Lights on", "04:59 AM", "TIB", "479.9 min"],
        ["", "", "MT", "408.9 min"],
    ]

    time_table = Table(times_data, colWidths=[125, 125, 125, 125])
    time_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        
        # Heading row (row 0) - colored background, bold
        ('SPAN', (0,0), (-1,0)),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#DCEFD8")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('TOPPADDING', (0,0), (-1,0), 3),
        ('BOTTOMPADDING', (0,0), (-1,0), 3),
        ('LEFTPADDING', (0,0), (-1,0), 6),
        
        # Data rows (row 1 onwards)
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('ALIGN', (0,1), (-1,-1), 'CENTER'), 
        ('LEFTPADDING', (0,1), (-1,-1), 6),
        ('RIGHTPADDING', (0,1), (-1,-1), 6),
        ('TOPPADDING', (0,1), (-1,-1), 4),
        ('BOTTOMPADDING', (0,1), (-1,-1), 4),
    ]))
    page1_elements.append(time_table)
    page1_elements.append(Spacer(1, 12))

    # ---------------- SUMMARY CONTAINER ----------------
    summary_data = [
        ["SLEEP APNEA SUMMARY", "", "", "", "", "", "", ""],
        ["AHI", "41.1", "OAI", "5.7", "CAI", "0.2", "Hypopnea", "33.9"]
    ]

    summary_table = Table(summary_data, colWidths=[60, 60, 60, 60, 60, 60, 80, 60])
    summary_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        
        # Heading row (row 0) - colored background, bold
        ('SPAN', (0,0), (-1,0)),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#DCEFD8")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('TOPPADDING', (0,0), (-1,0), 3),
        ('BOTTOMPADDING', (0,0), (-1,0), 3),
        ('LEFTPADDING', (0,0), (-1,0), 6),
        
        # Data rows (row 1 onwards)
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        ('ALIGN', (0,1), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('TEXTCOLOR', (0,1), (-1,-1), colors.black),
        ('TEXTCOLOR', (1,1), (1,1), colors.HexColor(0x007BFF)),  # AHI value
        ('TEXTCOLOR', (3,1), (3,1), colors.HexColor(0x007BFF)),  # OAI
        ('TEXTCOLOR', (5,1), (5,1), colors.HexColor(0x007BFF)),  # CAI
        ('TEXTCOLOR', (7,1), (7,1), colors.HexColor(0x007BFF)),  # Hypopnea
        ('LEFTPADDING', (0,1), (-1,-1), 6),
        ('RIGHTPADDING', (0,1), (-1,-1), 6),
        ('TOPPADDING', (0,1), (-1,-1), 4),
        ('BOTTOMPADDING', (0,1), (-1,-1), 4),
    ]))
    page1_elements.append(summary_table)
    page1_elements.append(Spacer(1, 12))

    # ---------------- Severity Meter ----------------
     # ---------------- SEVERITY INDICATOR ----------------
    def create_severity_meter(value=41.1):
        width = 500
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
            str(value),
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

   

    
    severity_meter = create_severity_meter(41.1)
    severity_wrapper = Table([[severity_meter]], colWidths=[500])
    severity_wrapper.setStyle(TableStyle([
        ('LEFTPADDING', (0,0), (-1,-1), 1),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    page1_elements.append(severity_wrapper)
    page1_elements.append(Spacer(1, 12))

    # ---------------- RESPIRATORY EVENTS CONTAINER ----------------
    # ✅ Full structured data (exact image)
    resp_data = [
        ["RESPIRATORY EVENTS", "", "", "", "", "", "", "", "", ""],
        ["", "Index\n(#/hour)", "Total # of\nEvents", "Mean duration\n(sec)", "Max duration\n(sec)", "# of Events by Position", "", "", "", ""],
        ["", "", "", "", "", "Supine", "Prone", "Left", "Right", "Up"],

        ["Central Apneas", "0.2", "2", "10.5", "11.0", "0", "0", "0", "1", "1"],
        ["Obstructive Apneas", "5.7", "39", "28.2", "95.0", "0", "", "19", "20", "0"],
        ["Mixed Apneas", "0.9", "6", "29.8", "101.0", "2", "", "2", "1", "1"],
        ["Hypopneas", "33.9", "231", "21.0", "56.0", "53", "", "173", "1", "4"],
        ["Apneas + Hypopneas", "41.1", "280", "22.0", "101.0", "55", "", "196", "23", "6"],
        ["RERAs", "0.0", "0", "0.0", "0.0", "0", "", "0", "0", "0"],

        ["Total", "41.1", "280", "22.0", "101.0", "55", "", "196", "23", "6"],

        ["Time in Position", "", "", "", "", "51.7", "", "293.6", "64.3", "36.8"],
        ["REI in Position", "", "", "", "", "68.9", "", "40.1", "21.5", "97.3"],
    ]

    resp_table = Table(resp_data, colWidths=[96, 41, 51, 61, 61, 38, 38, 38, 38, 38])

    resp_table.setStyle(TableStyle([
        # Base style
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 7),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),

        # Heading row (row 0) - colored background, bold
        ('SPAN', (0,0), (-1,0)),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#DCEFD8")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('TOPPADDING', (0,0), (-1,0), 2),
        ('BOTTOMPADDING', (0,0), (-1,0), 2),
        ('LEFTPADDING', (0,0), (-1,0), 6),

        # Data rows (row 1 onwards)
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        
        # Header background
        ('BACKGROUND', (0,1), (-1,2), colors.HexColor(0xE6F3FF)),

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
        ('LINEABOVE', (0,9), (-1,9), 1, colors.black),

        # Section line before Time in Position
        ('LINEABOVE', (0,9), (-1,9), 1, colors.black),

        # Blue color for index and duration values
        ('TEXTCOLOR', (1,2), (4,8), colors.HexColor(0x007BFF)),  # index + duration values
        ('TEXTCOLOR', (5,2), (9,7), colors.HexColor(0x007BFF)),  # position event counts
        ('TEXTCOLOR', (5,9), (9,10), colors.HexColor(0x007BFF)),  # position time/REI values

        # Padding
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))

    page1_elements.append(resp_table)
    page1_elements.append(Spacer(1, 10))
    
    # Add all page 1 elements without KeepTogether (content is too large)
    elements.extend(page1_elements)
    elements.append(PageBreak())

    # ---------------- PAGE 2 ELEMENTS ----------------
    page2_elements = []

    # ==========================================
    # MAIN COLUMN WIDTHS
    # ==========================================
    LEFT_SECTION_WIDTH = 250
    RIGHT_SECTION_WIDTH = 250

    # ---------------- OXIMETRY CONTAINER ----------------
    oximetry = _get_section(analysis_results, "oximetry")
    oxi_data = [
        ["OXIMETRY SUMMARY", "", ""],
        ["Parameter", "% TIB", "Value"],
        ["Mean SpO2 % during sleep", "99", oximetry.get("mean_spo2_display", "0")],
        ["Min SpO2 % during sleep", "99", oximetry.get("min_spo2_display", "0")],
        ["Max SpO2 % during sleep", "99", oximetry.get("max_spo2_display", "0")],
        ["Total # of Desats", "", oximetry.get("total_desats_display", "0")],
        ["Desat Index (#/hour)", "", oximetry.get("desaturation_index_display", "0")],
        ["Desat Max (%)", "", oximetry.get("desat_max_pct_display", "0")],
        ["Desat Max dur (sec)", "", oximetry.get("desat_max_sec_display", "0 sec")],
        ["Lowest SpO2 % during sleep", "", oximetry.get("lowest_spo2_display", "0")],
        ["Duration of Min SpO2 (sec)", "", oximetry.get("duration_of_min_spo2_display", "0 sec")],
        ["Highest SpO2 % during sleep", "", oximetry.get("highest_spo2_display", "0")],
        ["Duration of Max SpO2 (sec)", "", oximetry.get("duration_of_max_spo2_display", "0 sec")],
        ["SpO2 < 90% duration", "", oximetry.get("duration_below_90_display", "0 sec")],
        ["SpO2 < 85% duration", "", oximetry.get("duration_below_85_display", "0 sec")],
        ["SpO2 < 80% duration", "", oximetry.get("duration_below_80_display", "0 sec")],
        ["Baseline SpO2", "", oximetry.get("baseline_spo2_display", "0")],
        ["SpO2 Variability", "", oximetry.get("spo2_variability", "0")],
        ["Oxygen Saturation Trend", "", oximetry.get("oxygen_saturation_trend", "0")],
    ]

    oxi_table = Table(oxi_data, colWidths=[182, 30, 30])

    oxi_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        
        # Heading row (row 0) - colored background, bold
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#DCEFD8")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('TOPPADDING', (0,0), (-1,0), 4),
        ('BOTTOMPADDING', (0,0), (-1,0), 4),
        ('LEFTPADDING', (0,0), (-1,0), 4),
        
        # Data rows (row 1 onwards)
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 7),
        
        # Align
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),

        # Blue color for values
        ('TEXTCOLOR', (1,1), (-1,-1), colors.HexColor(0x007BFF)),
        ('TEXTCOLOR', (0,1), (0,-1), colors.black),

        # Padding
        ('LEFTPADDING', (0,1), (-1,-1), 4),
        ('RIGHTPADDING', (0,1), (-1,-1), 4),
        ('TOPPADDING', (0,1), (-1,-1), 2),
        ('BOTTOMPADDING', (0,1), (-1,-1), 2),

        # ✅ SECTION BREAK (important)
        # ('LINEABOVE', (0,7), (-1,7), 1, colors.black),

        # ✅ No SPAN needed - values should appear in % TIB column
        # Center align the % TIB column values
        ('ALIGN', (2,7), (2,15), 'CENTER'),
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

    hr_table = Table(hr_data, colWidths=[121, 121])
    hr_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        
        # Heading row (row 0) - colored background, bold
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#DCEFD8")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('TOPPADDING', (0,0), (-1,0), 4),
        ('BOTTOMPADDING', (0,0), (-1,0), 4),
        ('LEFTPADDING', (0,0), (-1,0), 4),
        
        # Data rows (row 1 onwards)
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 7),
        ('ALIGN', (0,1), (-1,-1), 'CENTER'),
        ('TEXTCOLOR', (1,1), (1,-1), colors.HexColor(0x007BFF)),
        ('TEXTCOLOR', (0,1), (0,-1), colors.black),
        ('LEFTPADDING', (0,1), (-1,-1), 4),
        ('RIGHTPADDING', (0,1), (-1,-1), 4),
        ('TOPPADDING', (0,1), (-1,-1), 2),
        ('BOTTOMPADDING', (0,1), (-1,-1), 2),
    ]))

    # ---------------- SNORING ANALYSIS ----------------
    snoring = _get_section(analysis_results, "snoring")
    snore_data = [
        ["SNORING SUMMARY", ""],
        ["Parameter", "Value"],
        [" Total Snoring Episodes", snoring.get("total_snoring_episodes_display", "0")],
        [" Total Duration with Snoring ", snoring.get("total_snoring_duration_display", "0 sec")],
        [" Mean Duration of Snoring ", snoring.get("mean_snoring_duration_display", "0 sec")],
        [" Percentage of Snoring ", snoring.get("snoring_percentage_display", "0 %")],
        
    ]

    snore_table = Table(snore_data, colWidths=[121, 121])
    snore_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        
        # Heading row (row 0) - colored background, bold
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#DCEFD8")),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('TOPPADDING', (0,0), (-1,0), 4),
        ('BOTTOMPADDING', (0,0), (-1,0), 4),
        ('LEFTPADDING', (0,0), (-1,0), 4),
        
        # Data rows (row 1 onwards)
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 7),
        ('ALIGN', (0,1), (-1,-1), 'CENTER'),
        ('TEXTCOLOR', (1,1), (1,-1), colors.HexColor(0x007BFF)),
        ('TEXTCOLOR', (0,1), (0,-1), colors.black),
        ('LEFTPADDING', (0,1), (-1,-1), 4),
        ('RIGHTPADDING', (0,1), (-1,-1), 4),
        ('TOPPADDING', (0,1), (-1,-1), 2),
        ('BOTTOMPADDING', (0,1), (-1,-1), 2),
    ]))

    # ==========================================
    # RIGHT COLUMN
    # ==========================================
    right_column_stack = Table([
        [hr_table],
        [Spacer(1, 12)],
        [snore_table]
    ], colWidths=[250])

    # ==========================================
    # MAIN SIDE-BY-SIDE LAYOUT
    # ==========================================
    page2_main_table = Table([
        [
            oxi_table,
            right_column_stack
        ]
    ], colWidths=[260, 260])
    page2_main_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))

    page2_elements.append(page2_main_table)
    page2_elements.append(Spacer(1, 20))

    # ---------------- FOOTER CONTAINER ----------------
    footer_container = Table([[
        Paragraph("<b>Medical Report Generated - Sleep Sense System</b>", styles['Normal'])
    ]], colWidths=[500])
    footer_container.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.white),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    page2_elements.append(footer_container)

    # Add all page 2 elements with KeepTogether to keep them on page 2
    elements.append(KeepTogether(page2_elements))
    elements.extend(_build_dashboard_screenshot_section(dashboard_screenshot_path, doc, styles))

    doc.build(elements)
    print(" Basic Report Generated:", pdf_path)
    return os.path.abspath(pdf_path)


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
    def __init__(self, pdf_path=None, parent=None, patient_data=None, analysis_results=None, dashboard_screenshot_path=None):
        super().__init__(parent)
        self.pdf_path = pdf_path
        self.patient_data = patient_data or {}
        self.analysis_results = analysis_results or {}
        self.dashboard_screenshot_path = dashboard_screenshot_path
        self.setWindowTitle("Medical Report")
        self.setFixedSize(1200, 850)
        self.generating = False  # Flag to prevent multiple generations
        self.init_ui()
        
        # Load PDF after a short delay to ensure proper initialization
        if pdf_path and os.path.exists(pdf_path):
            QTimer.singleShot(500, lambda: self.load_pdf(pdf_path))
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header with title and close button only
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(10, 5, 10, 5)
        
        title_label = QLabel("Medical Report")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        
        # Generate button
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
        
        close_btn = QPushButton("✕ Close")
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
        
        # Create header widget
        header_widget = QLabel()
        header_widget.setLayout(header_layout)
        header_widget.setStyleSheet("background-color: #f8f8f8; border-bottom: 1px solid #ddd;")
        header_widget.setFixedHeight(45)
        
        # Web view for PDF
        self.web_view = QWebEngineView()
        self.web_view.settings().setAttribute(self.web_view.settings().PluginsEnabled, True)
        self.web_view.settings().setAttribute(self.web_view.settings().PdfViewerEnabled, True)
        
        # Add to layout
        layout.addWidget(header_widget)
        layout.addWidget(self.web_view)
        
        self.setLayout(layout)
    
    def generate_new_report(self):
        """Generate a new report and save it to a local file."""
        if self.generating:
            return  # Prevent multiple generations
        
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

            # Always refresh from the newest JSON before generating the PDF.
            latest_analysis_results = _load_latest_analysis_results()
            if latest_analysis_results:
                self.analysis_results = latest_analysis_results

            # Always use the basic report format and save it to the chosen local path.
            pdf_path = generate_sleep_report(
                pdf_path=file_path,
                patient_data=self.patient_data,
                analysis_results=self.analysis_results,
                dashboard_screenshot_path=self.dashboard_screenshot_path
            )
            
            # Update the PDF path and reload
            self.pdf_path = pdf_path
            QMessageBox.information(
                self,
                "Report Saved",
                f"Report saved locally to:\n{pdf_path}"
            )
            QTimer.singleShot(100, lambda: self.load_pdf(pdf_path))
            
        finally:
            # Re-enable generation after a short delay
            QTimer.singleShot(2000, lambda: setattr(self, 'generating', False))
    
    def load_pdf(self, pdf_path):
        """Load PDF file in web view"""
        if not os.path.exists(pdf_path):
            self.show_error("PDF file not found", f"The file {pdf_path} could not be found.")
            return
        
        try:
            # Convert file path to file URL
            file_url = QUrl.fromLocalFile(os.path.abspath(pdf_path))
            print(f"Loading PDF from: {file_url.toString()}")
            
            # Load the PDF
            self.web_view.load(file_url)
            
            # Set up load finished handler
            self.web_view.loadFinished.connect(lambda success: self.on_load_finished(success))
            
        except Exception as e:
            self.show_error("Error loading PDF", f"Error: {str(e)}\nFile: {pdf_path}")
    
    def on_load_finished(self, success):
        """Handle PDF load completion"""
        if success:
            print("✅ PDF loaded successfully in viewer")
        else:
            print("❌ Failed to load PDF in viewer")
            # Try alternative loading method
            self.try_alternative_loading()
    
    def try_alternative_loading(self):
        """Try alternative PDF loading method"""
        try:
            # Try loading with data URL
            with open(self.pdf_path, 'rb') as f:
                pdf_data = f.read()
            
            import base64
            import urllib.parse
            
            # Create data URL
            b64_data = base64.b64encode(pdf_data).decode('utf-8')
            data_url = f"data:application/pdf;base64,{b64_data}"
            
            self.web_view.load(QUrl(data_url))
            print("✅ Trying alternative PDF loading method...")
            
        except Exception as e:
            self.show_error("PDF Loading Failed", 
                          f"Could not load PDF in viewer.\n\n"
                          f"File: {self.pdf_path}\n"
                          f"Error: {str(e)}\n\n"
                          f"Please open the PDF file manually.")
    
    def show_error(self, title, message):
        """Show error message in web view"""
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
                <p>{message.replace('\n', '<br>')}</p>
            </div>
        </body>
        </html>
        """
        self.web_view.setHtml(error_html)
    
    def set_pdf_path(self, pdf_path):
        """Set new PDF path and load it"""
        self.pdf_path = pdf_path
        if os.path.exists(pdf_path):
            QTimer.singleShot(500, lambda: self.load_pdf(pdf_path))
