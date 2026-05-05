"""
Medical Report Form - Medical Data and Analysis Report Form
Creates a comprehensive medical report form for patient medical data
"""

from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QTextEdit, QPushButton, QFrame, QScrollArea,
    QDateEdit, QGroupBox, QGridLayout, QComboBox,
    QSizePolicy, QApplication, QMessageBox
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont, QPixmap
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.utils.database_manager import DatabaseManager


class MedicalReportForm(QDialog):
    """Medical Report Form Dialog"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Medical Report")
        self.setFixedSize(700, 550)
        self.db_manager = DatabaseManager()
        self.init_ui()
        
    def init_ui(self):
        """Initialize the medical report form UI"""
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title_label = QLabel("Medical Report")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #2c3e50; margin-bottom: 20px;")
        main_layout.addWidget(title_label)
        
        # Create scroll area for form content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        # Form container
        form_widget = QWidget()
        form_layout = QVBoxLayout()
        form_layout.setSpacing(15)
        
        # Patient Information Section
        patient_group = QGroupBox("Patient Information")
        patient_group.setFont(QFont("Arial", 10, QFont.Bold))
        patient_layout = QGridLayout()
        
        # Patient ID
        patient_layout.addWidget(QLabel("Patient ID:"), 0, 0)
        self.patient_id_edit = QLineEdit()
        self.patient_id_edit.setPlaceholderText("Enter patient ID")
        patient_layout.addWidget(self.patient_id_edit, 0, 1)
        
        # Patient Name
        patient_layout.addWidget(QLabel("Patient Name:"), 1, 0)
        self.patient_name_edit = QLineEdit()
        self.patient_name_edit.setPlaceholderText("Enter patient name")
        patient_layout.addWidget(self.patient_name_edit, 1, 1)
        
        # Date
        patient_layout.addWidget(QLabel("Report Date:"), 2, 0)
        self.report_date_edit = QDateEdit()
        self.report_date_edit.setDate(QDate.currentDate())
        self.report_date_edit.setCalendarPopup(True)
        patient_layout.addWidget(self.report_date_edit, 2, 1)
        
        patient_group.setLayout(patient_layout)
        form_layout.addWidget(patient_group)
        
        # Medical Findings Section
        findings_group = QGroupBox("Medical Findings")
        findings_group.setFont(QFont("Arial", 10, QFont.Bold))
        findings_layout = QVBoxLayout()
        
        self.findings_edit = QTextEdit()
        self.findings_edit.setPlaceholderText("Enter medical findings...")
        self.findings_edit.setMaximumHeight(100)
        findings_layout.addWidget(self.findings_edit)
        
        findings_group.setLayout(findings_layout)
        form_layout.addWidget(findings_group)
        
        # Diagnosis Section
        diagnosis_group = QGroupBox("Diagnosis")
        diagnosis_group.setFont(QFont("Arial", 10, QFont.Bold))
        diagnosis_layout = QVBoxLayout()
        
        self.diagnosis_edit = QTextEdit()
        self.diagnosis_edit.setPlaceholderText("Enter diagnosis...")
        self.diagnosis_edit.setMaximumHeight(80)
        diagnosis_layout.addWidget(self.diagnosis_edit)
        
        diagnosis_group.setLayout(diagnosis_layout)
        form_layout.addWidget(diagnosis_group)
        
        # Recommendations Section
        recommendations_group = QGroupBox("Recommendations")
        recommendations_group.setFont(QFont("Arial", 10, QFont.Bold))
        recommendations_layout = QVBoxLayout()
        
        self.recommendations_edit = QTextEdit()
        self.recommendations_edit.setPlaceholderText("Enter recommendations...")
        self.recommendations_edit.setMaximumHeight(80)
        recommendations_layout.addWidget(self.recommendations_edit)
        
        recommendations_group.setLayout(recommendations_layout)
        form_layout.addWidget(recommendations_group)
        
        # Doctor Information Section
        doctor_group = QGroupBox("Doctor Information")
        doctor_group.setFont(QFont("Arial", 10, QFont.Bold))
        doctor_layout = QGridLayout()
        
        # Doctor Name
        doctor_layout.addWidget(QLabel("Doctor Name:"), 0, 0)
        self.doctor_name_edit = QLineEdit()
        self.doctor_name_edit.setPlaceholderText("Enter doctor name")
        doctor_layout.addWidget(self.doctor_name_edit, 0, 1)
        
        # Specialization
        doctor_layout.addWidget(QLabel("Specialization:"), 1, 0)
        self.specialization_combo = QComboBox()
        self.specialization_combo.addItems([
            "General Practice", "Cardiology", "Pulmonology", 
            "Neurology", "Psychiatry", "Other"
        ])
        doctor_layout.addWidget(self.specialization_combo, 1, 1)
        
        doctor_group.setLayout(doctor_layout)
        form_layout.addWidget(doctor_group)
        
        form_widget.setLayout(form_layout)
        scroll_area.setWidget(form_widget)
        main_layout.addWidget(scroll_area)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Save Button
        self.save_button = QPushButton("Save Report")
        self.save_button.setFont(QFont("Arial", 10, QFont.Bold))
        self.save_button.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #219a52;
            }
        """)
        self.save_button.clicked.connect(self.save_report)
        button_layout.addWidget(self.save_button)
        
        # Cancel Button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFont(QFont("Arial", 10))
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
        
    def save_report(self):
        """Save medical report to database"""
        # Get form data
        report_data = {
            'patient_id': self.patient_id_edit.text(),
            'patient_name': self.patient_name_edit.text(),
            'report_date': self.report_date_edit.date().toString("dd-MM-yyyy"),
            'findings': self.findings_edit.toPlainText(),
            'diagnosis': self.diagnosis_edit.toPlainText(),
            'recommendations': self.recommendations_edit.toPlainText(),
            'doctor_name': self.doctor_name_edit.text(),
            'specialization': self.specialization_combo.currentText()
        }
        
        # Validate required fields
        if not report_data['patient_id'].strip():
            QMessageBox.warning(self, "Validation Error", "Patient ID is required!")
            self.patient_id_edit.setStyleSheet("background-color: #ffcccb; border: 2px solid red;")
            return
            
        if not report_data['patient_name'].strip():
            QMessageBox.warning(self, "Validation Error", "Patient Name is required!")
            self.patient_name_edit.setStyleSheet("background-color: #ffcccb; border: 2px solid red;")
            return
        
        # Save to database
        try:
            # Get patient ID from patient data
            patient_id = report_data.get('patient_id', '')
            if not patient_id:
                QMessageBox.warning(self, "Validation Error", "Patient ID is required!")
                return
            
            # Save medical report to database
            success = self.db_manager.save_report(report_data)
            if success:
                QMessageBox.information(self, "Success", "Medical report saved successfully!")
                print(f"Medical report saved: {report_data}")
                # Refresh parent database window if it exists
                if self.parent() and hasattr(self.parent(), 'database_window'):
                    self.parent().database_window.load_reports_from_database()
                self.accept()
            else:
                QMessageBox.critical(self, "Error", "Failed to save medical report!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save report: {str(e)}")
            print(f"Error saving medical report: {e}")
    
    def get_report_data(self):
        """Get all report data as dictionary"""
        return {
            'patient_id': self.patient_id_edit.text(),
            'patient_name': self.patient_name_edit.text(),
            'report_date': self.report_date_edit.date().toString("dd-MM-yyyy"),
            'findings': self.findings_edit.toPlainText(),
            'diagnosis': self.diagnosis_edit.toPlainText(),
            'recommendations': self.recommendations_edit.toPlainText(),
            'doctor_name': self.doctor_name_edit.text(),
            'specialization': self.specialization_combo.currentText()
        }
