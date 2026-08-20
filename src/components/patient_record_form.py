"""
Patient Record Form - Full Page Patient Record Entry Form
Creates a comprehensive patient record form matching the provided design
"""

from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QRadioButton, QButtonGroup, QTextEdit, QPushButton,
    QFrame, QScrollArea, QDateEdit, QGroupBox, QGridLayout,
    QSizePolicy, QApplication, QMessageBox
)
from PyQt5.QtCore import Qt, QDate, QRegularExpression
from PyQt5.QtGui import QFont, QPixmap, QRegularExpressionValidator
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils.database_manager import DatabaseManager


class PatientRecordForm(QDialog):
    """Full Page Patient Record Form"""

    FORM_LABEL_WIDTH = 122
    FORM_FIELD_WIDTH = 136
    FORM_FIELD_HEIGHT = 34
    PHONE_PREFIX = "+91 "

    REQUIRED_LINE_EDIT_STYLE = """
        QLineEdit {
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 #fff9c4,
                stop: 1 #ffeb3b
            );
            border: 2px solid #ffc107;
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 13px;
            color: #2c3e50;
            font-weight: 600;
        }
        QLineEdit:focus {
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 #ffecb3,
                stop: 1 #ffe082
            );
            border: 2px solid #ff9800;
        }
    """

    DEFAULT_LINE_EDIT_STYLE = """
        QLineEdit {
            border: 2px solid #e1e8ed;
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 13px;
            background-color: #ffffff;
            color: #2c3e50;
        }
        QLineEdit:focus {
            border: 2px solid #4a90e2;
            background-color: #f0f8ff;
        }
        QLineEdit:hover {
            border-color: #4a90e2;
        }
    """

    REQUIRED_DATE_EDIT_STYLE = """
        QDateEdit {
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 #fff9c4,
                stop: 1 #ffeb3b
            );
            border: 2px solid #ffc107;
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 13px;
            color: #2c3e50;
            font-weight: 600;
        }
        QDateEdit:focus {
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 #ffecb3,
                stop: 1 #ffe082
            );
            border: 2px solid #ff9800;
        }
    """

    DEFAULT_DATE_EDIT_STYLE = """
        QDateEdit {
            border: 2px solid #e1e8ed;
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 13px;
            background-color: #ffffff;
            color: #2c3e50;
        }
        QDateEdit:focus {
            border: 2px solid #4a90e2;
            background-color: #f0f8ff;
        }
        QDateEdit:hover {
            border-color: #4a90e2;
        }
    """

    ERROR_LINE_EDIT_STYLE = """
        QLineEdit {
            background-color: #ffcccb;
            border: 2px solid red;
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 13px;
            color: #2c3e50;
            font-weight: 600;
        }
        QLineEdit:focus {
            background-color: #ffcccb;
            border: 2px solid #dc2626;
        }
    """

    ERROR_DATE_EDIT_STYLE = """
        QDateEdit {
            background-color: #ffcccb;
            border: 2px solid red;
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 13px;
            color: #2c3e50;
            font-weight: 600;
        }
        QDateEdit:focus {
            background-color: #ffcccb;
            border: 2px solid #dc2626;
        }
    """

    def _create_form_label(self, text):
        label = QLabel(text)
        label.setFixedWidth(self.FORM_LABEL_WIDTH)
        return label

    def _apply_uniform_field_size(self, widget):
        widget.setFixedHeight(self.FORM_FIELD_HEIGHT)
        widget.setFixedWidth(self.FORM_FIELD_WIDTH)

    def _style_default_line_edit(self, widget):
        widget.setStyleSheet(self.DEFAULT_LINE_EDIT_STYLE)

    def _style_default_date_edit(self, widget):
        widget.setStyleSheet(self.DEFAULT_DATE_EDIT_STYLE)

    def _set_regex_validator(self, widget, pattern):
        widget.setValidator(QRegularExpressionValidator(QRegularExpression(pattern), widget))

    def _configure_field_limits(self):
        self.last_name_edit.setMaxLength(50)
        self.first_name_edit.setMaxLength(50)
        self.patient_id_edit.setMaxLength(20)
        self._set_regex_validator(self.patient_id_edit, r"[A-Za-z0-9]{0,20}")

        self.title_edit.setMaxLength(20)
        self.street_edit.setMaxLength(100)
        self.name_suffix_edit.setMaxLength(4)
        self._set_regex_validator(self.name_suffix_edit, r"[A-Za-z0-9]{0,4}")
        self.zip_edit.setMaxLength(10)
        self._set_regex_validator(self.zip_edit, r"[A-Za-z0-9\- ]{0,10}")
        self.phone_edit.setMaxLength(15)
        self.fax_edit.setMaxLength(15)
        self.city_state_edit.setMaxLength(50)
        self.country_edit.setMaxLength(40)

        self.clinic_edit.setMaxLength(50)
        self.cost_unit_edit.setMaxLength(10)
        self._set_regex_validator(self.cost_unit_edit, r"[A-Za-z0-9]{0,10}")
        self.department_edit.setMaxLength(50)
        self.ins_no_edit.setMaxLength(20)
        self._set_regex_validator(self.ins_no_edit, r"[A-Za-z0-9]{0,20}")
        self.physician_edit.setMaxLength(50)
        self.policyholder_edit.setMaxLength(50)
        self.status_edit.setMaxLength(30)

        self.weight_edit.setMaxLength(6)
        self._set_regex_validator(self.weight_edit, r"\d{0,3}(\.\d{0,2})?")
        self.bmi_edit.setMaxLength(5)
        self._set_regex_validator(self.bmi_edit, r"\d{0,2}(\.\d{0,2})?")
        self.height_edit.setMaxLength(6)
        self._set_regex_validator(self.height_edit, r"\d{0,3}(\.\d{0,1})?")
        self.bp_systolic_edit.setMaxLength(3)
        self._set_regex_validator(self.bp_systolic_edit, r"\d{0,3}")
        self.bp_diastolic_edit.setMaxLength(3)
        self._set_regex_validator(self.bp_diastolic_edit, r"\d{0,3}")

        numeric_hint = Qt.ImhFormattedNumbersOnly | Qt.ImhPreferNumbers
        self.weight_edit.setInputMethodHints(numeric_hint)
        self.bmi_edit.setInputMethodHints(numeric_hint)
        self.height_edit.setInputMethodHints(numeric_hint)
        self.bp_systolic_edit.setInputMethodHints(Qt.ImhDigitsOnly)
        self.bp_diastolic_edit.setInputMethodHints(Qt.ImhDigitsOnly)

    def _ensure_phone_prefix(self, widget):
        text = widget.text()
        if not text.startswith(self.PHONE_PREFIX):
            suffix = "".join(ch for ch in text if ch.isdigit())
            widget.blockSignals(True)
            widget.setText(f"{self.PHONE_PREFIX}{suffix}")
            widget.setCursorPosition(len(widget.text()))
            widget.blockSignals(False)

    def _validate_phone_like_field(self, widget):
        self._ensure_phone_prefix(widget)
        text = widget.text()
        if not text:
            return
        digits = "".join(ch for ch in text if ch.isdigit())
        if digits.startswith("91"):
            digits = digits[2:]
        limited_digits = digits[:10]
        widget.blockSignals(True)
        widget.setText(f"{self.PHONE_PREFIX}{limited_digits}")
        widget.setCursorPosition(len(widget.text()))
        widget.blockSignals(False)

    def _validate_bp_values(self):
        systolic_text = self.bp_systolic_edit.text().strip()
        diastolic_text = self.bp_diastolic_edit.text().strip()

        if not systolic_text and not diastolic_text:
            return None

        if not systolic_text or not diastolic_text:
            return "Both systolic and diastolic blood pressure values are required."

        systolic = int(systolic_text)
        diastolic = int(diastolic_text)

        if not 60 <= systolic <= 250:
            return "BP systolic must be between 60 and 250."
        if not 40 <= diastolic <= 150:
            return "BP diastolic must be between 40 and 150."
        if systolic <= diastolic:
            return "BP systolic must be greater than diastolic."

        return None
    
    def __init__(self, parent=None, patient_data=None, edit_mode=None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Patient Record Card")
        self.setFixedSize(750, 650)
        self.db_manager = DatabaseManager()
        self._base_styles = {}
        self.patient_db_id = None
        self.edit_mode = bool(patient_data) if edit_mode is None else edit_mode
        self.patient_data = patient_data or {}
        self.init_ui()
        if self.edit_mode and self.patient_data:
            self.patient_db_id = self.patient_data.get("id")
            self.setWindowTitle("Edit Patient Record Card")
            self.populate_form(self.patient_data)
        
    def init_ui(self):
        # Main Layout with reduced margins
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)
        
        # Title
        title_label = QLabel("Patient record card")
        title_label.setObjectName("formTitle")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            QLabel#formTitle {
                font-size: 28px;
                font-weight: bold;
                color: #2c3e50;
                margin: 10px 0 20px 0;
                padding: 15px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #4a90e2,
                    stop: 0.5 #357abd,
                    stop: 1 #4a90e2
                );
                color: white;
                border-radius: 12px;
                box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
                text-transform: uppercase;
                letter-spacing: 1px;
            }
        """)
        main_layout.addWidget(title_label)
        
        # Scroll Area for the form
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(8, 8, 8, 8)
        form_layout.setSpacing(10)
        
        # Create form sections
        patient_id_section = self.create_patient_identification_section()
        contact_section = self.create_contact_information_section()
        medical_section = self.create_medical_information_section()
        measurements_section = self.create_physical_measurements_section()
        additional_section = self.create_additional_information_section()
        buttons_section = self.create_action_buttons()
        
        form_layout.addWidget(patient_id_section)
        form_layout.addWidget(contact_section)
        form_layout.addWidget(medical_section)
        form_layout.addWidget(measurements_section)
        form_layout.addWidget(additional_section)
        form_layout.addWidget(buttons_section)
        form_layout.addStretch()
        
        scroll_area.setWidget(form_widget)
        main_layout.addWidget(scroll_area)
        
        # Required fields note
        note_label = QLabel("Required fields are marked with *.")
        note_label.setAlignment(Qt.AlignRight)
        note_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #666;
                font-style: italic;
            }
        """)
        main_layout.addWidget(note_label)
        self._configure_field_limits()
        
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f0f4f8,
                    stop: 1 #d9e2ec
                );
            }
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #2c3e50;
                border: 2px solid #e1e8ed;
                border-radius: 12px;
                margin-top: 15px;
                padding-top: 15px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 1 #f8f9fa
                );
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px 0 8px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #4a90e2,
                    stop: 1 #357abd
                );
                color: white;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
            }
            QLabel {
                color: #34495e;
                font-weight: 600;
                font-size: 12px;
            }
            QLineEdit {
                border: 2px solid #e1e8ed;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                background-color: #ffffff;
                color: #2c3e50;
            }
            QLineEdit:focus {
                border: 2px solid #4a90e2;
                background-color: #f0f8ff;
                box-shadow: 0 0 8px rgba(74, 144, 226, 0.3);
            }
            QLineEdit:hover {
                border-color: #4a90e2;
            }
            QTextEdit {
                border: 2px solid #e1e8ed;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                background-color: #ffffff;
                color: #2c3e50;
            }
            QTextEdit:focus {
                border: 2px solid #4a90e2;
                background-color: #f0f8ff;
                box-shadow: 0 0 8px rgba(74, 144, 226, 0.3);
            }
            QTextEdit:hover {
                border-color: #4a90e2;
            }
            QDateEdit {
                border: 2px solid #e1e8ed;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                background-color: #ffffff;
                color: #2c3e50;
            }
            QDateEdit:focus {
                border: 2px solid #4a90e2;
                background-color: #f0f8ff;
                box-shadow: 0 0 8px rgba(74, 144, 226, 0.3);
            }
            QDateEdit:hover {
                border-color: #4a90e2;
            }
            QRadioButton {
                color: #34495e;
                font-weight: 600;
                font-size: 13px;
                spacing: 8px;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #4a90e2;
                border-radius: 9px;
                background-color: white;
            }
            QRadioButton::indicator:checked {
                background: qradialgradient(
                    cx: 0.5, cy: 0.5,
                    radius: 0.5,
                    fx: 0.5, fy: 0.5,
                    stop: 0 #4a90e2,
                    stop: 1 #357abd
                );
                border: 2px solid #357abd;
            }
            QRadioButton::indicator:hover {
                border: 2px solid #357abd;
            }
            QPushButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #4a90e2,
                    stop: 1 #357abd
                );
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 14px;
                min-width: 100px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #5ba0f2,
                    stop: 1 #4680ce
                );
                box-shadow: 0 6px 8px rgba(0, 0, 0, 0.15);
            }
            QPushButton:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #357abd,
                    stop: 1 #2968a3
                );
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }
            QPushButton#cancelBtn {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #e74c3c,
                    stop: 1 #c0392b
                );
            }
            QPushButton#cancelBtn:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f75c4c, 
                    stop: 0 #d0493b
                );
            }
            QPushButton#cancelBtn:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #c0392b,
                    stop: 1 #a93226
                );
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QScrollBar:vertical {
                background: #f0f4f8;
                width: 12px;
                border-radius: 6px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #4a90e2;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #357abd;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
    
    def create_patient_identification_section(self):
        """Create Patient Identification section"""
        group = QGroupBox("Patient Identification")
        layout = QGridLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 0)
        layout.setColumnStretch(3, 1)
        
        # Last Name (Required)
        self.last_name_edit = QLineEdit()
        self.last_name_edit.setPlaceholderText("Example")
        self.last_name_edit.setStyleSheet(self.REQUIRED_LINE_EDIT_STYLE)
        self.last_name_edit.textChanged.connect(self._reset_required_field_styles)
        self._apply_uniform_field_size(self.last_name_edit)
        layout.addWidget(self._create_form_label("Last name:"), 0, 0)
        layout.addWidget(self.last_name_edit, 0, 1)
        
        # First Name
        self.first_name_edit = QLineEdit()
        self._style_default_line_edit(self.first_name_edit)
        self._apply_uniform_field_size(self.first_name_edit)
        layout.addWidget(self._create_form_label("First name:"), 0, 2)
        layout.addWidget(self.first_name_edit, 0, 3)
        self._remember_base_style(self.first_name_edit)
        
        # DOB (Required)
        self.dob_edit = QDateEdit()
        self.dob_edit.setDate(QDate(2000, 1, 1))
        self.dob_edit.setDisplayFormat("dd/MM/yyyy")
        self.dob_edit.setCalendarPopup(True)
        self.dob_edit.setStyleSheet(self.REQUIRED_DATE_EDIT_STYLE)
        self.dob_edit.dateChanged.connect(self._reset_required_field_styles)
        self._apply_uniform_field_size(self.dob_edit)
        layout.addWidget(self._create_form_label("DOB:"), 1, 0)
        layout.addWidget(self.dob_edit, 1, 1)
        self._remember_base_style(self.dob_edit)
        
        # Patient ID
        self.patient_id_edit = QLineEdit()
        self.patient_id_edit.setPlaceholderText("14021967")
        self._style_default_line_edit(self.patient_id_edit)
        self._apply_uniform_field_size(self.patient_id_edit)
        layout.addWidget(self._create_form_label("Patient ID:"), 1, 2)
        layout.addWidget(self.patient_id_edit, 1, 3)
        self._remember_base_style(self.patient_id_edit)
        
        # Gender
        gender_group = QButtonGroup()
        gender_group.setExclusive(False)
        self.male_radio = QRadioButton("Male")
        self.female_radio = QRadioButton("Female")
        gender_group.addButton(self.male_radio, 0)
        gender_group.addButton(self.female_radio, 1)
        self.male_radio.setChecked(False)
        self.female_radio.setChecked(False)
        gender_group.setExclusive(True)
        
        gender_layout = QHBoxLayout()
        gender_layout.addWidget(self._create_form_label("Gender:"))
        gender_layout.addWidget(self.male_radio)
        gender_layout.addWidget(self.female_radio)
        gender_layout.addStretch()
        
        layout.addLayout(gender_layout, 2, 0, 1, 2)
        
        group.setLayout(layout)
        return group

    def _make_field_label(self, text, required=False):
        """Create a consistent field label, with a required marker when needed."""
        label_text = f"{text} *" if required else text
        label = QLabel(label_text + ":")
        if required:
            label.setStyleSheet("color: #b8860b; font-weight: 700;")
        return label

    def _remember_base_style(self, widget):
        """Store the widget's original stylesheet so validation can restore it."""
        self._base_styles[widget] = widget.styleSheet()

    def _reset_validation_styles(self):
        """Restore every tracked widget to its original style."""
        for widget, style in self._base_styles.items():
            widget.setStyleSheet(style)

    def _mark_field_invalid(self, widget):
        """Highlight a field in red when validation fails."""
        base_style = self._base_styles.get(widget, widget.styleSheet())
        invalid_style = """
            border: 2px solid #e74c3c;
            background-color: #fff5f5;
        """
        widget.setStyleSheet(f"{base_style}\n{invalid_style}")
    
    def create_contact_information_section(self):
        """Create Contact Information section"""
        group = QGroupBox("Contact Information")
        layout = QGridLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(10, 15, 10, 10)
        
        # First row
        self.title_edit = QLineEdit()
        self._style_default_line_edit(self.title_edit)
        self._apply_uniform_field_size(self.title_edit)
        layout.addWidget(self._create_form_label("Title:"), 0, 0)
        layout.addWidget(self.title_edit, 0, 1)
        
        self.street_edit = QLineEdit()
        self._style_default_line_edit(self.street_edit)
        self._apply_uniform_field_size(self.street_edit)
        layout.addWidget(self._create_form_label("Street:"), 0, 2)
        layout.addWidget(self.street_edit, 0, 3)
        
        # Second row
        self.name_suffix_edit = QLineEdit()
        self._style_default_line_edit(self.name_suffix_edit)
        self._apply_uniform_field_size(self.name_suffix_edit)
        layout.addWidget(self._create_form_label("Name suffix:"), 1, 0)
        layout.addWidget(self.name_suffix_edit, 1, 1)
        
        self.zip_edit = QLineEdit()
        self._style_default_line_edit(self.zip_edit)
        self._apply_uniform_field_size(self.zip_edit)
        layout.addWidget(self._create_form_label("Zip code:"), 1, 2)
        layout.addWidget(self.zip_edit, 1, 3)
        
        # Third row
        self.phone_edit = QLineEdit()
        self._style_default_line_edit(self.phone_edit)
        self._apply_uniform_field_size(self.phone_edit)
        self.phone_edit.setPlaceholderText("+91 9876543210")
        self.phone_edit.setText(self.PHONE_PREFIX)
        self.phone_edit.textChanged.connect(lambda _=None: self._validate_phone_like_field(self.phone_edit))
        layout.addWidget(self._create_form_label("Phone:"), 2, 0)
        layout.addWidget(self.phone_edit, 2, 1)
        
        self.city_state_edit = QLineEdit()
        self._style_default_line_edit(self.city_state_edit)
        self._apply_uniform_field_size(self.city_state_edit)
        layout.addWidget(self._create_form_label("City, State:"), 2, 2)
        layout.addWidget(self.city_state_edit, 2, 3)
        
        # Fourth row
        self.fax_edit = QLineEdit()
        self._style_default_line_edit(self.fax_edit)
        self._apply_uniform_field_size(self.fax_edit)
        self.fax_edit.setPlaceholderText("+91 9876543210")
        self.fax_edit.setText(self.PHONE_PREFIX)
        self.fax_edit.textChanged.connect(lambda _=None: self._validate_phone_like_field(self.fax_edit))
        layout.addWidget(self._create_form_label("Fax:"), 3, 0)
        layout.addWidget(self.fax_edit, 3, 1)
        
        self.country_edit = QLineEdit()
        self._style_default_line_edit(self.country_edit)
        self._apply_uniform_field_size(self.country_edit)
        layout.addWidget(self._create_form_label("Country:"), 3, 2)
        layout.addWidget(self.country_edit, 3, 3)
        
        group.setLayout(layout)
        return group
    
    def create_medical_information_section(self):
        """Create Medical/Administrative Information section"""
        group = QGroupBox("Medical/Administrative Information")
        layout = QGridLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(10, 15, 10, 10)
        
        # First row
        self.clinic_edit = QLineEdit()
        self._style_default_line_edit(self.clinic_edit)
        self._apply_uniform_field_size(self.clinic_edit)
        layout.addWidget(self._create_form_label("Clinic:"), 0, 0)
        layout.addWidget(self.clinic_edit, 0, 1)
        
        self.cost_unit_edit = QLineEdit()
        self._style_default_line_edit(self.cost_unit_edit)
        self._apply_uniform_field_size(self.cost_unit_edit)
        layout.addWidget(self._create_form_label("Cost unit:"), 0, 2)
        layout.addWidget(self.cost_unit_edit, 0, 3)
        
        # Second row
        self.department_edit = QLineEdit()
        self._style_default_line_edit(self.department_edit)
        self._apply_uniform_field_size(self.department_edit)
        layout.addWidget(self._create_form_label("Department:"), 1, 0)
        layout.addWidget(self.department_edit, 1, 1)
        
        self.ins_no_edit = QLineEdit()
        self._style_default_line_edit(self.ins_no_edit)
        self._apply_uniform_field_size(self.ins_no_edit)
        layout.addWidget(self._create_form_label("Ins. No.:"), 1, 2)
        layout.addWidget(self.ins_no_edit, 1, 3)
        
        # Third row
        self.physician_edit = QLineEdit()
        self._style_default_line_edit(self.physician_edit)
        self._apply_uniform_field_size(self.physician_edit)
        layout.addWidget(self._create_form_label("Physician:"), 2, 0)
        layout.addWidget(self.physician_edit, 2, 1)
        
        self.policyholder_edit = QLineEdit()
        self._style_default_line_edit(self.policyholder_edit)
        self._apply_uniform_field_size(self.policyholder_edit)
        layout.addWidget(self._create_form_label("Policyholder No.:"), 2, 2)
        layout.addWidget(self.policyholder_edit, 2, 3)
        
        # Fourth row
        self.valid_until_edit = QDateEdit()
        self.valid_until_edit.setDate(QDate.currentDate())
        self.valid_until_edit.setDisplayFormat("dd/MM/yyyy")
        self.valid_until_edit.setCalendarPopup(True)
        self._style_default_date_edit(self.valid_until_edit)
        self._apply_uniform_field_size(self.valid_until_edit)
        layout.addWidget(self._create_form_label("Valid until:"), 3, 0)
        layout.addWidget(self.valid_until_edit, 3, 1)
        
        self.status_edit = QLineEdit()
        self._style_default_line_edit(self.status_edit)
        self._apply_uniform_field_size(self.status_edit)
        layout.addWidget(self._create_form_label("Status:"), 3, 2)
        layout.addWidget(self.status_edit, 3, 3)
        
        group.setLayout(layout)
        return group
    
    def create_physical_measurements_section(self):
        """Create Physical Measurements section"""
        group = QGroupBox("Physical Measurements")
        layout = QGridLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(10, 15, 10, 10)
        
        # Weight
        self.weight_edit = QLineEdit()
        self.weight_edit.setPlaceholderText("120.50")
        self._style_default_line_edit(self.weight_edit)
        self._apply_uniform_field_size(self.weight_edit)
        weight_layout = QHBoxLayout()
        weight_layout.addWidget(self.weight_edit)
        weight_layout.addWidget(QLabel("kg"))
        weight_layout.setContentsMargins(0, 0, 0, 0)
        
        layout.addWidget(self._create_form_label("Weight:"), 0, 0)
        layout.addLayout(weight_layout, 0, 1)
        
        # BMI
        self.bmi_edit = QLineEdit()
        self.bmi_edit.setPlaceholderText("35.50")
        self._style_default_line_edit(self.bmi_edit)
        self._apply_uniform_field_size(self.bmi_edit)
        bmi_layout = QHBoxLayout()
        bmi_layout.addWidget(self.bmi_edit)
        bmi_layout.addWidget(QLabel("kg/m²"))
        bmi_layout.setContentsMargins(0, 0, 0, 0)
        
        layout.addWidget(self._create_form_label("BMI:"), 0, 2)
        layout.addLayout(bmi_layout, 0, 3)
        
        # Height
        self.height_edit = QLineEdit()
        self.height_edit.setPlaceholderText("175.5")
        self._style_default_line_edit(self.height_edit)
        self._apply_uniform_field_size(self.height_edit)
        height_layout = QHBoxLayout()
        height_layout.addWidget(self.height_edit)
        height_layout.addWidget(QLabel("cm"))
        height_layout.setContentsMargins(0, 0, 0, 0)
        
        layout.addWidget(self._create_form_label("Height:"), 1, 0)
        layout.addLayout(height_layout, 1, 1)
        
        # Blood Pressure
        self.bp_systolic_edit = QLineEdit()
        self._style_default_line_edit(self.bp_systolic_edit)
        self._apply_uniform_field_size(self.bp_systolic_edit)
        self.bp_systolic_edit.setFixedWidth(60)
        self.bp_systolic_edit.setPlaceholderText("120")

        self.bp_diastolic_edit = QLineEdit()
        self._style_default_line_edit(self.bp_diastolic_edit)
        self._apply_uniform_field_size(self.bp_diastolic_edit)
        self.bp_diastolic_edit.setFixedWidth(60)
        self.bp_diastolic_edit.setPlaceholderText("80")
        bp_layout = QHBoxLayout()
        bp_layout.addWidget(self.bp_systolic_edit)
        bp_layout.addWidget(QLabel("/"))
        bp_layout.addWidget(self.bp_diastolic_edit)
        bp_layout.addWidget(QLabel("mmHg"))
        bp_layout.setContentsMargins(0, 0, 0, 0)
        
        layout.addWidget(self._create_form_label("Syst./diast:"), 1, 2)
        layout.addLayout(bp_layout, 1, 3)
        
        group.setLayout(layout)
        return group
    
    def create_additional_information_section(self):
        """Create Additional Information section"""
        group = QGroupBox("Additional Information")
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(10, 15, 10, 10)
        
        # Referred by doctor
        self.referred_edit = QTextEdit()
        self.referred_edit.setMaximumHeight(60)
        self.referred_edit.setPlaceholderText("Enter referring doctor information...")
        layout.addWidget(QLabel("Referred by doctor:"))
        layout.addWidget(self.referred_edit)
        
        # History
        self.history_edit = QTextEdit()
        self.history_edit.setMaximumHeight(60)
        self.history_edit.setPlaceholderText("Enter patient medical history...")
        layout.addWidget(QLabel("History:"))
        layout.addWidget(self.history_edit)
        
        # Comments
        self.comments_edit = QTextEdit()
        self.comments_edit.setMaximumHeight(60)
        self.comments_edit.setPlaceholderText("Enter additional comments...")
        layout.addWidget(QLabel("Comments:"))
        layout.addWidget(self.comments_edit)
        
        group.setLayout(layout)
        return group
    
    def create_action_buttons(self):
        """Create Action buttons section"""
        button_container = QFrame()
        button_container.setObjectName("buttonContainer")
        button_container.setStyleSheet("""
            QFrame#buttonContainer {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f8f9fa,
                    stop: 1 #e9ecef
                );
                border: 1px solid #dee2e6;
                border-radius: 10px;
                padding: 15px;
                margin: 10px;
            }
        """)
        
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(20, 10, 20, 10)
        button_layout.setSpacing(20)
        
        # Add spacers to center the buttons
        button_layout.addStretch()
        
        # OK Button with enhanced styling
        self.ok_button = QPushButton("✓ OK")
        self.ok_button.setObjectName("okButton")
        self.ok_button.setFixedSize(120, 40)
        self.ok_button.clicked.connect(self.accept_form)
        self.ok_button.setStyleSheet("""
            QPushButton#okButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #28a745,
                    stop: 1 #20c997
                );
                color: white;
                border: none;
                border-radius: 20px;
                font-weight: bold;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            QPushButton#okButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #218838,
                    stop: 1 #1ea085
                );
                transform: scale(1.05);
            }
            QPushButton#okButton:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #1e7e34,
                    stop: 1 #1c7a6e
                );
                transform: scale(0.98);
            }
        """)
        button_layout.addWidget(self.ok_button)
        
        # Cancel Button with enhanced styling
        self.cancel_button = QPushButton("✕ Cancel")
        self.cancel_button.setObjectName("cancelBtn")
        self.cancel_button.setFixedSize(120, 40)
        self.cancel_button.clicked.connect(self.reject_form)
        self.cancel_button.setStyleSheet("""
            QPushButton#cancelBtn {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #dc3545,
                    stop: 1 #c82333
                );
                color: white;
                border: none;
                border-radius: 20px;
                font-weight: bold;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            QPushButton#cancelBtn:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #c82333,
                    stop: 1 #bd2130
                );
                transform: scale(1.05);
            }
            QPushButton#cancelBtn:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #bd2130,
                    stop: 1 #a71e2a
                );
                transform: scale(0.98);
            }
        """)
        button_layout.addWidget(self.cancel_button)
        
        # Add spacers to center the buttons
        button_layout.addStretch()
        
        return button_container

    def _reset_required_field_styles(self):
        """Restore the default required-field styling after validation feedback."""
        self.last_name_edit.setStyleSheet(self.REQUIRED_LINE_EDIT_STYLE)
        self.dob_edit.setStyleSheet(self.REQUIRED_DATE_EDIT_STYLE)
    
    def accept_form(self):
        """Handle OK button click"""
        self._reset_required_field_styles()
        self._validate_phone_like_field(self.phone_edit)
        self._validate_phone_like_field(self.fax_edit)

        # Validate required fields
        self._reset_validation_styles()
        if not self.last_name_edit.text().strip():
            self.last_name_edit.setStyleSheet(self.ERROR_LINE_EDIT_STYLE)
            self.last_name_edit.setFocus()
            QMessageBox.warning(self, "Validation Error", "Last name is required!")
            return

        if not self.first_name_edit.text().strip():
            self._mark_field_invalid(self.first_name_edit)
            QMessageBox.warning(self, "Validation Error", "First name is required!")
            return

        if not self.patient_id_edit.text().strip():
            self._mark_field_invalid(self.patient_id_edit)
            QMessageBox.warning(self, "Validation Error", "Patient ID is required!")
            return
        
        if not self.dob_edit.date().isValid():
            self.dob_edit.setStyleSheet(self.ERROR_DATE_EDIT_STYLE)
            self.dob_edit.setFocus()
            QMessageBox.warning(self, "Validation Error", "Date of birth is required!")
            return

        bp_error = self._validate_bp_values()
        if bp_error:
            self.bp_systolic_edit.setFocus()
            QMessageBox.warning(self, "Validation Error", bp_error)
            return
        
        patient_data = self.get_patient_data()
        duplicate_patient = self.db_manager.get_patient_by_name_dob(
            patient_data.get('last_name', '').strip(),
            patient_data.get('first_name', '').strip(),
            patient_data.get('dob', '').strip(),
        )
        if duplicate_patient and duplicate_patient.get('id') != self.patient_db_id:
            QMessageBox.warning(
                self,
                "Duplicate Patient",
                "Same patient details already exist.\n"
                "A duplicate patient record cannot be saved.",
            )
            return

        if self.edit_mode:
            if self.patient_db_id is None:
                QMessageBox.critical(self, "Error", "Missing patient ID for edit mode!")
                return

            # EDIT MODE -> UPDATE existing row
            updated = self.db_manager.update_patient(self.patient_db_id, patient_data)
            if not updated:
                QMessageBox.critical(self, "Error", "Failed to update patient record!")
                return

            patient_data['id'] = self.patient_db_id
            QMessageBox.information(
                self, "Updated",
                f"Patient details updated successfully!\nDatabase ID: {self.patient_db_id}",
            )
            print(f"Patient record updated (ID: {self.patient_db_id})")
            self.accept()
            return

        # ADD MODE -> INSERT new row
        patient_id = self.db_manager.save_patient(patient_data)

        if patient_id:
            patient_data['id'] = patient_id
            QMessageBox.information(self, "Success", f"Patient record saved successfully!\nDatabase ID: {patient_id}")
            print(f"Patient record saved with ID: {patient_id}")
            if self.parent() and hasattr(self.parent(), 'load_patient_data'):
                try:
                    self.parent().load_patient_data(patient_data)
                except Exception as error:
                    print(f"Warning: Could not sync saved patient to dashboard: {error}")
            self.accept()
        else:
            QMessageBox.critical(self, "Error", "Failed to save patient record to database!")

    def populate_form(self, data):
        """ (edit mode)."""
        def text_of(key):
            value = data.get(key)
            return "" if value is None else str(value)

        self.last_name_edit.setText(text_of('last_name'))
        self.first_name_edit.setText(text_of('first_name'))
        self.patient_id_edit.setText(text_of('patient_id'))

        dob = QDate.fromString(text_of('dob'), "dd-MM-yyyy")
        if dob.isValid():
            self.dob_edit.setDate(dob)

        valid_until = QDate.fromString(text_of('valid_until'), "dd-MM-yyyy")
        if valid_until.isValid():
            self.valid_until_edit.setDate(valid_until)

        if text_of('gender').strip().lower() == 'male':
            self.male_radio.setChecked(True)
        else:
            self.female_radio.setChecked(True)

        line_fields = {
            'title': self.title_edit,
            'street': self.street_edit,
            'name_suffix': self.name_suffix_edit,
            'zip_code': self.zip_edit,
            'phone': self.phone_edit,
            'city_state': self.city_state_edit,
            'fax': self.fax_edit,
            'country': self.country_edit,
            'clinic': self.clinic_edit,
            'cost_unit': self.cost_unit_edit,
            'department': self.department_edit,
            'ins_no': self.ins_no_edit,
            'physician': self.physician_edit,
            'policyholder_no': self.policyholder_edit,
            'status': self.status_edit,
            'weight': self.weight_edit,
            'bmi': self.bmi_edit,
            'height': self.height_edit,
        }
        for key, widget in line_fields.items():
            widget.setText(text_of(key))

        bp_text = text_of('blood_pressure').strip()
        systolic, _, diastolic = bp_text.partition("/")
        self.bp_systolic_edit.setText(systolic.strip())
        self.bp_diastolic_edit.setText(diastolic.strip())

        text_fields = {
            'referred_by': self.referred_edit,
            'history': self.history_edit,
            'comments': self.comments_edit,
        }
        for key, widget in text_fields.items():
            widget.setPlainText(text_of(key))
    
    def reject_form(self):
        """Handle Cancel button click"""
        print("Patient record cancelled")
        self.reject()
    
    def get_patient_data(self):
        """Get all patient data as dictionary"""
        return {
            'last_name': self.last_name_edit.text(),
            'first_name': self.first_name_edit.text(),
            'dob': self.dob_edit.date().toString("dd-MM-yyyy"),
            'patient_id': self.patient_id_edit.text(),
            'gender': 'male' if self.male_radio.isChecked() else 'female',
            'title': self.title_edit.text(),
            'street': self.street_edit.text(),
            'name_suffix': self.name_suffix_edit.text(),
            'zip_code': self.zip_edit.text(),
            'phone': self.phone_edit.text(),
            'city_state': self.city_state_edit.text(),
            'fax': self.fax_edit.text(),
            'country': self.country_edit.text(),
            'clinic': self.clinic_edit.text(),
            'cost_unit': self.cost_unit_edit.text(),
            'department': self.department_edit.text(),
            'ins_no': self.ins_no_edit.text(),
            'physician': self.physician_edit.text(),
            'policyholder_no': self.policyholder_edit.text(),
            'valid_until': self.valid_until_edit.date().toString("dd-MM-yyyy"),
            'status': self.status_edit.text(),
            'weight': self.weight_edit.text(),
            'bmi': self.bmi_edit.text(),
            'height': self.height_edit.text(),
            'blood_pressure': f"{self.bp_systolic_edit.text().strip()}/{self.bp_diastolic_edit.text().strip()}",
            'referred_by': self.referred_edit.toPlainText(),
            'history': self.history_edit.toPlainText(),
            'comments': self.comments_edit.toPlainText()
        }


if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = PatientRecordForm()
    window.show()
    sys.exit(app.exec_())
