"""
Patient Record Form - Full Page Patient Record Entry Form
Creates a comprehensive patient record form matching the provided design
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QRadioButton, QButtonGroup, QTextEdit, QPushButton,
    QFrame, QScrollArea, QDateEdit, QGroupBox, QGridLayout,
    QSizePolicy, QApplication
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont, QPixmap


class PatientRecordForm(QMainWindow):
    """Full Page Patient Record Form"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Patient Record Card")
        self.setGeometry(100, 100, 750, 650)
        self.setMinimumSize(700, 600)
        self.setMaximumSize(800, 700)
        
        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main Layout with reduced margins
        main_layout = QVBoxLayout(central_widget)
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
        note_label = QLabel("Required fields are yellow.")
        note_label.setAlignment(Qt.AlignRight)
        note_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #666;
                font-style: italic;
            }
        """)
        main_layout.addWidget(note_label)
        
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
        
        # Last Name (Required)
        self.last_name_edit = QLineEdit()
        self.last_name_edit.setPlaceholderText("Example")
        self.last_name_edit.setStyleSheet("""
            QLineEdit {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #fff9c4,
                    stop: 1 #ffeb3b
                );
                border: 2px solid #ffc107;
                font-weight: 600;
            }
            QLineEdit:focus {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffecb3,
                    stop: 1 #ffe082
                );
                border: 2px solid #ff9800;
                box-shadow: 0 0 8px rgba(255, 193, 7, 0.4);
            }
        """)  # Attractive yellow gradient for required
        layout.addWidget(QLabel("Last name:"), 0, 0)
        layout.addWidget(self.last_name_edit, 0, 1)
        
        # First Name
        self.first_name_edit = QLineEdit()
        self.first_name_edit.setPlaceholderText("Normal")
        layout.addWidget(QLabel("First name:"), 0, 2)
        layout.addWidget(self.first_name_edit, 0, 3)
        
        # DOB (Required)
        self.dob_edit = QDateEdit()
        self.dob_edit.setDate(QDate(1967, 2, 14))
        self.dob_edit.setCalendarPopup(True)
        self.dob_edit.setStyleSheet("""
            QDateEdit {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #fff9c4,
                    stop: 1 #ffeb3b
                );
                border: 2px solid #ffc107;
                font-weight: 600;
            }
            QDateEdit:focus {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffecb3,
                    stop: 1 #ffe082
                );
                border: 2px solid #ff9800;
                box-shadow: 0 0 8px rgba(255, 193, 7, 0.4);
            }
        """)  # Attractive yellow gradient for required
        layout.addWidget(QLabel("DOB:"), 1, 0)
        layout.addWidget(self.dob_edit, 1, 1)
        
        # Patient ID
        self.patient_id_edit = QLineEdit()
        self.patient_id_edit.setPlaceholderText("14021967")
        layout.addWidget(QLabel("Patient ID:"), 1, 2)
        layout.addWidget(self.patient_id_edit, 1, 3)
        
        # Gender
        gender_group = QButtonGroup()
        self.male_radio = QRadioButton("male")
        self.female_radio = QRadioButton("female")
        self.female_radio.setChecked(True)
        gender_group.addButton(self.male_radio, 0)
        gender_group.addButton(self.female_radio, 1)
        
        gender_layout = QHBoxLayout()
        gender_layout.addWidget(QLabel("Gender:"))
        gender_layout.addWidget(self.male_radio)
        gender_layout.addWidget(self.female_radio)
        gender_layout.addStretch()
        
        layout.addLayout(gender_layout, 2, 0, 1, 2)
        
        group.setLayout(layout)
        return group
    
    def create_contact_information_section(self):
        """Create Contact Information section"""
        group = QGroupBox("Contact Information")
        layout = QGridLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(10, 15, 10, 10)
        
        # First row
        self.title_edit = QLineEdit()
        layout.addWidget(QLabel("Title:"), 0, 0)
        layout.addWidget(self.title_edit, 0, 1)
        
        self.street_edit = QLineEdit()
        layout.addWidget(QLabel("Street:"), 0, 2)
        layout.addWidget(self.street_edit, 0, 3)
        
        # Second row
        self.name_suffix_edit = QLineEdit()
        layout.addWidget(QLabel("Name suffix:"), 1, 0)
        layout.addWidget(self.name_suffix_edit, 1, 1)
        
        self.zip_edit = QLineEdit()
        layout.addWidget(QLabel("Zip code:"), 1, 2)
        layout.addWidget(self.zip_edit, 1, 3)
        
        # Third row
        self.phone_edit = QLineEdit()
        layout.addWidget(QLabel("Phone:"), 2, 0)
        layout.addWidget(self.phone_edit, 2, 1)
        
        self.city_state_edit = QLineEdit()
        layout.addWidget(QLabel("City, State:"), 2, 2)
        layout.addWidget(self.city_state_edit, 2, 3)
        
        # Fourth row
        self.fax_edit = QLineEdit()
        layout.addWidget(QLabel("Fax:"), 3, 0)
        layout.addWidget(self.fax_edit, 3, 1)
        
        self.country_edit = QLineEdit()
        layout.addWidget(QLabel("Country:"), 3, 2)
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
        layout.addWidget(QLabel("Clinic:"), 0, 0)
        layout.addWidget(self.clinic_edit, 0, 1)
        
        self.cost_unit_edit = QLineEdit()
        layout.addWidget(QLabel("Cost unit:"), 0, 2)
        layout.addWidget(self.cost_unit_edit, 0, 3)
        
        # Second row
        self.department_edit = QLineEdit()
        layout.addWidget(QLabel("Department:"), 1, 0)
        layout.addWidget(self.department_edit, 1, 1)
        
        self.ins_no_edit = QLineEdit()
        layout.addWidget(QLabel("Ins. No.:"), 1, 2)
        layout.addWidget(self.ins_no_edit, 1, 3)
        
        # Third row
        self.physician_edit = QLineEdit()
        layout.addWidget(QLabel("Physician:"), 2, 0)
        layout.addWidget(self.physician_edit, 2, 1)
        
        self.policyholder_edit = QLineEdit()
        layout.addWidget(QLabel("Policyholder No.:"), 2, 2)
        layout.addWidget(self.policyholder_edit, 2, 3)
        
        # Fourth row
        self.valid_until_edit = QDateEdit()
        self.valid_until_edit.setDate(QDate.currentDate())
        self.valid_until_edit.setCalendarPopup(True)
        layout.addWidget(QLabel("Valid until:"), 3, 0)
        layout.addWidget(self.valid_until_edit, 3, 1)
        
        self.status_edit = QLineEdit()
        layout.addWidget(QLabel("Status:"), 3, 2)
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
        self.weight_edit.setPlaceholderText("58.89")
        weight_layout = QHBoxLayout()
        weight_layout.addWidget(self.weight_edit)
        weight_layout.addWidget(QLabel("kg"))
        weight_layout.setContentsMargins(0, 0, 0, 0)
        
        layout.addWidget(QLabel("Weight:"), 0, 0)
        layout.addLayout(weight_layout, 0, 1)
        
        # BMI
        self.bmi_edit = QLineEdit()
        self.bmi_edit.setPlaceholderText("22.3")
        bmi_layout = QHBoxLayout()
        bmi_layout.addWidget(self.bmi_edit)
        bmi_layout.addWidget(QLabel("kg/m²"))
        bmi_layout.setContentsMargins(0, 0, 0, 0)
        
        layout.addWidget(QLabel("BMI:"), 0, 2)
        layout.addLayout(bmi_layout, 0, 3)
        
        # Height
        self.height_edit = QLineEdit()
        self.height_edit.setPlaceholderText("162.56")
        height_layout = QHBoxLayout()
        height_layout.addWidget(self.height_edit)
        height_layout.addWidget(QLabel("cm"))
        height_layout.setContentsMargins(0, 0, 0, 0)
        
        layout.addWidget(QLabel("Height:"), 1, 0)
        layout.addLayout(height_layout, 1, 1)
        
        # Blood Pressure
        self.bp_edit = QLineEdit()
        bp_layout = QHBoxLayout()
        bp_layout.addWidget(self.bp_edit)
        bp_layout.addWidget(QLabel("mmHg"))
        bp_layout.setContentsMargins(0, 0, 0, 0)
        
        layout.addWidget(QLabel("Syst./diast:"), 1, 2)
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
    
    def accept_form(self):
        """Handle OK button click"""
        # Validate required fields
        if not self.last_name_edit.text().strip():
            self.last_name_edit.setStyleSheet("background-color: #ffcccb; border: 2px solid red;")
            return
        
        if not self.dob_edit.date().isValid():
            self.dob_edit.setStyleSheet("background-color: #ffcccb; border: 2px solid red;")
            return
        
        # Here you can save the form data
        print("Patient record saved successfully!")
        self.close()
    
    def reject_form(self):
        """Handle Cancel button click"""
        print("Patient record cancelled")
        self.close()
    
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
            'blood_pressure': self.bp_edit.text(),
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
