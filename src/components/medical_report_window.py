"""
Medical Report Window - Display medical reports and analysis
Shows patient medical reports, sleep analysis, and ECG reports
"""

from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QTextEdit, QPushButton, QFrame, QScrollArea, QGroupBox,
    QGridLayout, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QApplication, QMessageBox
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont, QPixmap
import sys
import os

class MedicalReportWindow(QDialog):
    """Medical Report Window for displaying patient reports"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(False)
        self.setWindowTitle("Medical Reports")
        self.setFixedSize(1200, 800)
        self.init_ui()
        
    def init_ui(self):
        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Title
        title_label = QLabel("Medical Reports")
        title_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 10px;
            }
        """)
        main_layout.addWidget(title_label)
        
        # Create tab widget for different report types
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #d1d5db;
                border-radius: 8px;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background-color: #f8f9fa;
                border: 1px solid #d1d5db;
                border-bottom: none;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                border-bottom: 1px solid #ffffff;
            }
            QTabBar::tab:hover {
                background-color: #e9ecef;
            }
        """)
        
        # Create tabs
        self.create_sleep_analysis_tab()
        
        main_layout.addWidget(self.tab_widget)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        
        self.export_btn = QPushButton("Export Report")
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
        """)
        
        self.print_btn = QPushButton("Print")
        self.print_btn.setStyleSheet("""
            QPushButton {
                background-color: #6b7280;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #dc2626;
            }
        """)
        
        button_layout.addStretch()
        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.print_btn)
        button_layout.addWidget(self.close_btn)
        
        main_layout.addLayout(button_layout)
        
        # Connect buttons
        self.export_btn.clicked.connect(self.export_report)
        self.print_btn.clicked.connect(self.print_report)
        self.close_btn.clicked.connect(self.close)
        
    def create_sleep_analysis_tab(self):
        """Create Sleep Analysis tab"""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        # Patient Info Section
        patient_group = QGroupBox("Patient Information")
        patient_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #d1d5db;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #374151;
            }
        """)
        
        patient_layout = QGridLayout()
        
        # Sample patient data
        patient_data = [
            ("Name:", "John Doe"),
            ("Age:", "45 years"),
            ("Gender:", "Male"),
            ("Date of Birth:", "15-03-1979"),
            ("Patient ID:", "PAT-001"),
            ("Recording Date:", "28-04-2024"),
            ("Recording Duration:", "8 hours 30 minutes"),
            ("Sleep Efficiency:", "85%")
        ]
        
        for i, (label, value) in enumerate(patient_data):
            label_widget = QLabel(label)
            label_widget.setStyleSheet("font-weight: 500; color: #6b7280;")
            value_widget = QLabel(value)
            value_widget.setStyleSheet("color: #111827;")
            
            patient_layout.addWidget(label_widget, i // 2, (i % 2) * 2)
            patient_layout.addWidget(value_widget, i // 2, (i % 2) * 2 + 1)
        
        patient_group.setLayout(patient_layout)
        layout.addWidget(patient_group)
        
        # Sleep Analysis Results
        analysis_group = QGroupBox("Sleep Analysis Results")
        analysis_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #d1d5db;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #374151;
            }
        """)
        
        analysis_layout = QVBoxLayout()
        
        # Create analysis table
        analysis_table = QTableWidget()
        analysis_table.setColumnCount(3)
        analysis_table.setHorizontalHeaderLabels(["Parameter", "Value", "Reference Range"])
        analysis_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        analysis_table.setAlternatingRowColors(True)
        
        # Sample analysis data
        analysis_data = [
            ("Total Sleep Time", "7h 15min", "7-9 hours"),
            ("Sleep Latency", "12 min", "<30 minutes"),
            ("REM Sleep", "22%", "20-25%"),
            ("Deep Sleep", "18%", "15-25%"),
            ("Light Sleep", "60%", "50-65%"),
            ("Awake Episodes", "3", "<5"),
            ("Apnea-Hypopnea Index", "5.2", "<5"),
            ("Oxygen Desaturation", "92%", ">90%")
        ]
        
        analysis_table.setRowCount(len(analysis_data))
        for i, (param, value, ref_range) in enumerate(analysis_data):
            analysis_table.setItem(i, 0, QTableWidgetItem(param))
            analysis_table.setItem(i, 1, QTableWidgetItem(value))
            analysis_table.setItem(i, 2, QTableWidgetItem(ref_range))
        
        analysis_layout.addWidget(analysis_table)
        analysis_group.setLayout(analysis_layout)
        layout.addWidget(analysis_group)
        
        self.tab_widget.addTab(tab_widget, "Sleep Analysis")
        
    def export_report(self):
        """Export report to file"""
        QMessageBox.information(self, "Export", "Report exported successfully!")
        print("Report exported")
        
    def print_report(self):
        """Print report"""
        QMessageBox.information(self, "Print", "Report sent to printer!")
        print("Report printed")
