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


class MedicalReportForm(QDialog):
    """Medical Report Form Dialog"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Medical Report")
        self.setFixedSize(700, 550)
        self.init_ui()
        
    def init_ui(self):
        # Main Layout with reduced margins
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)
        
        # Title
        title_label = QLabel("Medical Report")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                padding: 8px;
                background-color: #ecf0f1;
                border-radius: 4px;
                border: 1px solid #bdc3c7;
            }
        """)
        main_layout.addWidget(title_label)
        
        # Create scroll area for form content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        
        # Content widget
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        
        # Patient Information Section
        patient_group = QGroupBox("Patient Information")
        patient_layout = QGridLayout()
        
        # Patient selection
        self.patient_combo = QComboBox()
        self.patient_combo.setEditable(True)
        patient_layout.addWidget(QLabel("Patient:"), 0, 0)
        patient_layout.addWidget(self.patient_combo, 0, 1)
        
        # Report Date
        self.report_date = QDateEdit()
        self.report_date.setDate(QDate.currentDate())
        self.report_date.setCalendarPopup(True)
        patient_layout.addWidget(QLabel("Report Date:"), 1, 0)
        patient_layout.addWidget(self.report_date, 1, 1)
        
        # Report Type
        self.report_type = QComboBox()
        self.report_type.addItems(["Sleep Study", "ECG Report", "Blood Analysis", "X-Ray Report", "Other"])
        patient_layout.addWidget(QLabel("Report Type:"), 2, 0)
        patient_layout.addWidget(self.report_type, 2, 1)
        
        patient_group.setLayout(patient_layout)
        content_layout.addWidget(patient_group)
        
        # Medical Findings Section
        findings_group = QGroupBox("Medical Findings")
        findings_layout = QVBoxLayout()
        
        self.findings_text = QTextEdit()
        self.findings_text.setPlaceholderText("Enter medical findings and observations...")
        self.findings_text.setMaximumHeight(120)
        findings_layout.addWidget(QLabel("Findings:"))
        findings_layout.addWidget(self.findings_text)
        
        findings_group.setLayout(findings_layout)
        content_layout.addWidget(findings_group)
        
        # Diagnosis Section
        diagnosis_group = QGroupBox("Diagnosis")
        diagnosis_layout = QVBoxLayout()
        
        self.diagnosis_text = QTextEdit()
        self.diagnosis_text.setPlaceholderText("Enter diagnosis...")
        self.diagnosis_text.setMaximumHeight(100)
        diagnosis_layout.addWidget(QLabel("Diagnosis:"))
        diagnosis_layout.addWidget(self.diagnosis_text)
        
        diagnosis_group.setLayout(diagnosis_layout)
        content_layout.addWidget(diagnosis_group)
        
        # Recommendations Section
        recommendations_group = QGroupBox("Recommendations")
        recommendations_layout = QVBoxLayout()
        
        self.recommendations_text = QTextEdit()
        self.recommendations_text.setPlaceholderText("Enter treatment recommendations...")
        self.recommendations_text.setMaximumHeight(100)
        recommendations_layout.addWidget(QLabel("Recommendations:"))
        recommendations_layout.addWidget(self.recommendations_text)
        
        recommendations_group.setLayout(recommendations_layout)
        content_layout.addWidget(recommendations_group)
        
        # Doctor Information Section
        doctor_group = QGroupBox("Doctor Information")
        doctor_layout = QGridLayout()
        
        self.doctor_name = QLineEdit()
        self.doctor_name.setPlaceholderText("Dr. Smith")
        doctor_layout.addWidget(QLabel("Doctor Name:"), 0, 0)
        doctor_layout.addWidget(self.doctor_name, 0, 1)
        
        self.doctor_specialization = QLineEdit()
        self.doctor_specialization.setPlaceholderText("Cardiologist")
        doctor_layout.addWidget(QLabel("Specialization:"), 1, 0)
        doctor_layout.addWidget(self.doctor_specialization, 1, 1)
        
        doctor_group.setLayout(doctor_layout)
        content_layout.addWidget(doctor_group)
        
        # Set scroll area content
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.ok_button = QPushButton("Save Report")
        self.ok_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)
        self.ok_button.clicked.connect(self.accept_form)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton:pressed {
                background-color: #5d6d7e;
            }
        """)
        self.cancel_button.clicked.connect(self.reject_form)
        
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(button_layout)
        
    def accept_form(self):
        """Handle Save button click"""
        QMessageBox.information(self, "Success", "Medical report saved successfully!")
        print("Medical report saved successfully!")
        self.close()
    
    def reject_form(self):
        """Handle Cancel button click"""
        print("Medical report cancelled")
        self.close()
    
    def get_report_data(self):
        """Get all report data as dictionary"""
        return {
            'patient': self.patient_combo.currentText(),
            'report_date': self.report_date.date().toString("dd-MM-yyyy"),
            'report_type': self.report_type.currentText(),
            'findings': self.findings_text.toPlainText(),
            'diagnosis': self.diagnosis_text.toPlainText(),
            'recommendations': self.recommendations_text.toPlainText(),
            'doctor_name': self.doctor_name.text(),
            'doctor_specialization': self.doctor_specialization.text()
        }
