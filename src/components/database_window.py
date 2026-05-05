"""
Patient Database Window - Sleep Sense Application
Replicates the database interface shown in the reference image
"""

from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QSplitter, QGroupBox, QLineEdit, QCheckBox,
    QTableWidget, QTableWidgetItem, QPushButton, QHeaderView,
    QToolBar, QSizePolicy
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.utils.database_manager import DatabaseManager


class DatabaseWindow(QDialog):
    """Patient Database Window matching the reference image design"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(False)
        self.setWindowTitle("Patient Database")
        self.setFixedSize(1200, 800)
        self.db_manager = DatabaseManager()
        self.init_ui()
        self.load_patients_from_database()
        
    def init_ui(self):
        # Apply medical theme
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                color: #2c3e50;
            }
        """)
        
        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)
        
        # Create main content area
        content_splitter = QSplitter(Qt.Horizontal)
        
        # Left side - Patients section
        left_widget = self.create_patients_section()
        content_splitter.addWidget(left_widget)
        
        # Right side container
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        
        # Records section (top right)
        records_widget = self.create_records_section()
        right_layout.addWidget(records_widget)
        
        # Reports section (bottom right)
        reports_widget = self.create_reports_section()
        right_layout.addWidget(reports_widget)
        
        content_splitter.addWidget(right_widget)
        content_splitter.setSizes([400, 600])
        
        main_layout.addWidget(content_splitter)
        
        # Bottom toolbar with Cancel button
        toolbar = self.create_bottom_toolbar()
        main_layout.addWidget(toolbar)
        
    def create_patients_section(self):
        """Create the Patients section (top left)"""
        group = QGroupBox("1. Patients")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        
        # Search input
        search_layout = QHBoxLayout()
        search_label = QLabel("Selection:")
        search_label.setStyleSheet("""
            QLabel {
                font-weight: 600;
                color: #34495e;
                font-size: 13px;
            }
        """)
        search_label.setMinimumWidth(70)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search patients...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #d1e3f4;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                background-color: #ffffff;
                color: #2c3e50;
            }
            QLineEdit:focus {
                border-color: #3498db;
                outline: none;
            }
        """)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)
        
        # Checkboxes
        checkbox_layout = QHBoxLayout()
        self.full_text_search = QCheckBox("Full text search")
        self.search_at_keypress = QCheckBox("Search at key press")
        
        checkbox_style = """
            QCheckBox {
                font-size: 12px;
                color: #34495e;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #d1e3f4;
                border-radius: 3px;
                background-color: #ffffff;
            }
            QCheckBox::indicator:hover {
                border-color: #3498db;
            }
            QCheckBox::indicator:checked {
                background-color: #3498db;
                border-color: #3498db;
                l
        """
        
        self.full_text_search.setStyleSheet(checkbox_style)
        self.search_at_keypress.setStyleSheet(checkbox_style)
        
        checkbox_layout.addWidget(self.full_text_search)
        checkbox_layout.addWidget(self.search_at_keypress)
        checkbox_layout.addStretch()
        layout.addLayout(checkbox_layout)
        
        # Patients table
        self.patients_table = QTableWidget()
        self.patients_table.setColumnCount(3)
        self.patients_table.setHorizontalHeaderLabels(["Last name", "First name", "Date of birth"])
        
        # Professional medical table styling
        self.patients_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #d1e3f4;
                border-radius: 6px;
                background-color: #ffffff;
                gridline-color: #e8f4f8;
                selection-background-color: #e3f2fd;
                selection-color: #1565c0;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #e8f4f8;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: #1565c0;
            }
            QTableWidget::item:hover {
                background-color: #f5f9fc;
            }
            QHeaderView::section {
                background-color: #f8fbfd;
                color: #1e3a5f;
                font-weight: 600;
                font-size: 13px;
                padding: 10px 8px;
                border: 1px solid #d1e3f4;
                border-right: none;
                border-bottom: 2px solid #3498db;
            }
            QHeaderView::section:last {
                border-right: 1px solid #d1e3f4;
            }
        """)
        
        # Set table properties
        header = self.patients_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.patients_table.setAlternatingRowColors(True)
        self.patients_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.patients_table.setShowGrid(True)
        self.patients_table.verticalHeader().setVisible(False)
        self.patients_table.setSortingEnabled(True)
        
        layout.addWidget(self.patients_table)
        
        return group
        
    def create_records_section(self):
        """Create the Records section (top right)"""
        group = QGroupBox("2. Records")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: 600;
                font-size: 15px;
                color: #1e3a5f;
                border: 2px solid #d1e3f4;
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 15px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px 0 8px;
                background-color: #ffffff;
                border-radius: 4px;
            }
        """)
        
        layout = QVBoxLayout(group)
        
        # Records table
        self.records_table = QTableWidget()
        self.records_table.setColumnCount(6)
        self.records_table.setHorizontalHeaderLabels([
            "Last name", "First name", "Recording date", 
            "Start time", "Duration", "Archived"
        ])
        
        # Professional medical table styling
        self.records_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #d1e3f4;
                border-radius: 6px;
                background-color: #ffffff;
                gridline-color: #e8f4f8;
                selection-background-color: #e3f2fd;
                selection-color: #1565c0;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #e8f4f8;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: #1565c0;
            }
            QTableWidget::item:hover {
                background-color: #f5f9fc;
            }
            QHeaderView::section {
                background-color: #f8fbfd;
                color: #1e3a5f;
                font-weight: 600;
                font-size: 13px;
                padding: 10px 8px;
                border: 1px solid #d1e3f4;
                border-right: none;
                border-bottom: 2px solid #3498db;
            }
            QHeaderView::section:last {
                border-right: 1px solid #d1e3f4;
            }
        """)
        
        # Set table properties
        header = self.records_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.records_table.setAlternatingRowColors(True)
        self.records_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.records_table.setShowGrid(True)
        self.records_table.verticalHeader().setVisible(False)
        self.records_table.setSortingEnabled(True)
        
        layout.addWidget(self.records_table)
        
        return group
        
    def create_reports_section(self):
        """Create the Reports section (bottom right)"""
        group = QGroupBox("3. Reports")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: 600;
                font-size: 15px;
                color: #1e3a5f;
                border: 2px solid #d1e3f4;
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 15px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px 0 8px;
                background-color: #ffffff;
                border-radius: 4px;
            }
        """)
        
        layout = QVBoxLayout(group)
        
        # Reports table
        self.reports_table = QTableWidget()
        self.reports_table.setColumnCount(3)
        self.reports_table.setHorizontalHeaderLabels(["Date, time", "Analysis status", "Manual status"])
        
        # Professional medical table styling
        self.reports_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #d1e3f4;
                border-radius: 6px;
                background-color: #ffffff;
                gridline-color: #e8f4f8;
                selection-background-color: #e3f2fd;
                selection-color: #1565c0;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #e8f4f8;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: #1565c0;
            }
            QTableWidget::item:hover {
                background-color: #f5f9fc;
            }
            QHeaderView::section {
                background-color: #f8fbfd;
                color: #1e3a5f;
                font-weight: 600;
                font-size: 13px;
                padding: 10px 8px;
                border: 1px solid #d1e3f4;
                border-right: none;
                border-bottom: 2px solid #3498db;
            }
            QHeaderView::section:last {
                border-right: 1px solid #d1e3f4;
            }
        """)
        
        # Set table properties
        header = self.reports_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        self.reports_table.setAlternatingRowColors(True)
        self.reports_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.reports_table.setShowGrid(True)
        self.reports_table.verticalHeader().setVisible(False)
        self.reports_table.setSortingEnabled(True)
        
        layout.addWidget(self.reports_table)
        
        return group
        
    def create_bottom_toolbar(self):
        """Create the bottom toolbar with Selection, View, Delete buttons"""
        toolbar = QFrame()
        toolbar.setFixedHeight(60)
        toolbar.setStyleSheet("""
            QFrame {
                border-top: 2px solid #d1e3f4;
                background-color: #f8fbfd;
                border-radius: 0px 0px 8px 8px;
            }
        """)
        
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Add spacer to push buttons to the left
        layout.addStretch()
        
        # Create buttons
        self.selection_btn = QPushButton("Selection")
        self.delete_btn = QPushButton("Delete")
        self.cancel_btn = QPushButton("Cancel")
        
        # Style buttons with professional medical look
        button_style = """
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 13px;
                min-width: 90px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """
        
        # Special styling for delete button
        delete_style = """
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 13px;
                min-width: 90px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a93226;
            }
        """
        
        # Special styling for cancel button
        cancel_style = """
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 13px;
                min-width: 90px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
            QPushButton:pressed {
                background-color: #6c7a7b;
            }
        """
        
        self.selection_btn.setStyleSheet(button_style)
        self.delete_btn.setStyleSheet(delete_style)
        self.cancel_btn.setStyleSheet(cancel_style)
        
        # Add buttons to layout
        layout.addWidget(self.selection_btn)
        layout.addWidget(self.delete_btn)
        layout.addWidget(self.cancel_btn)
        
        return toolbar
        
    def load_patients_from_database(self):
        """Load patients from database"""
        patients = self.db_manager.get_all_patients()
        
        self.patients_table.setRowCount(len(patients))
        for row, patient in enumerate(patients):
            self.patients_table.setItem(row, 0, QTableWidgetItem(patient['last_name']))
            self.patients_table.setItem(row, 1, QTableWidgetItem(patient['first_name']))
            self.patients_table.setItem(row, 2, QTableWidgetItem(patient['dob']))
            # Store patient ID in the row for later retrieval
            self.patients_table.item(row, 0).setData(Qt.UserRole, patient['id'])
        
        # Clear records table for now
        self.records_table.setRowCount(0)
        # Load reports for patients
        self.load_reports_from_database()
        
        # Connect search functionality
        self.search_input.textChanged.connect(self.filter_patients)
        self.full_text_search.stateChanged.connect(self.filter_patients)
        self.search_at_keypress.stateChanged.connect(self.filter_patients)
        
        # Connect button actions
        self.selection_btn.clicked.connect(self.handle_selection)
        self.delete_btn.clicked.connect(self.handle_delete)
        self.cancel_btn.clicked.connect(self.reject)  # Close dialog
        
    def filter_patients(self):
        """Filter patients table based on search criteria"""
        search_text = self.search_input.text().lower()
        full_text = self.full_text_search.isChecked()
        
        for row in range(self.patients_table.rowCount()):
            visible = False
            
            if not search_text or self.search_at_keypress.isChecked():
                for col in range(self.patients_table.columnCount()):
                    item = self.patients_table.item(row, col)
                    if item and search_text in item.text().lower():
                        visible = True
                        break
            else:
                visible = True  # Show all if search at key press is disabled
                
            self.patients_table.setRowHidden(row, not visible)
            
    def handle_selection(self):
        """Handle Selection button click"""
        selected_items = self.patients_table.selectedItems()
        if selected_items:
            # Get the first selected row
            row = selected_items[0].row()
            
            # Get patient database ID from the row
            patient_db_id = self.patients_table.item(row, 0).data(Qt.UserRole)
            
            # Get patient data from the selected row
            last_name = self.patients_table.item(row, 0).text()
            first_name = self.patients_table.item(row, 1).text()
            dob = self.patients_table.item(row, 2).text()
            
            # Fetch full patient data from database
            full_patient_data = self.db_manager.get_patient_by_id(patient_db_id)
            
            if full_patient_data:
                print(f"Selected patient: {full_patient_data['last_name']} {full_patient_data['first_name']} (DB ID: {patient_db_id})")
                
                # Set patient data in parent dashboard
                if self.parent() and hasattr(self.parent(), 'load_patient_data'):
                    self.parent().load_patient_data(full_patient_data)
                else:
                    # Fallback to old method if load_patient_data doesn't exist
                    if self.parent() and hasattr(self.parent(), 'monitor_chart'):
                        patient_id_str = f"{last_name}_{first_name}_{dob}"
                        self.parent().monitor_chart.set_patient_id(patient_id_str)
                        
                        # Update patient info widget
                        if hasattr(self.parent(), 'patient_info'):
                            self.parent().patient_info.set_patient_data({
                                'last_name': last_name,
                                'first_name': first_name,
                                'dob': dob,
                                'patient_id': patient_id_str
                            })
                
                # Close the dialog
                self.accept()
            else:
                print("Error: Could not fetch patient data from database")
        else:
            print("No patients selected")
            
    def handle_view(self):
        """Handle View button click"""
        selected_rows = []
        if self.patients_table.selectedItems():
            selected_rows = list(set(item.row() for item in self.patients_table.selectedItems()))
        elif self.records_table.selectedItems():
            selected_rows = list(set(item.row() for item in self.records_table.selectedItems()))
        elif self.reports_table.selectedItems():
            selected_rows = list(set(item.row() for item in self.reports_table.selectedItems()))
            
        if selected_rows:
            print(f"View: {len(selected_rows)} items selected")
        else:
            print("No items selected to view")
            
    def handle_delete(self):
        """Handle Delete button click"""
        print("Delete action triggered")
        
        # Get selected patient
        selected_items = self.patients_table.selectedItems()
        if not selected_items:
            print("No patient selected for deletion")
            return
            
        # Get patient data
        row = selected_items[0].row()
        patient_db_id = self.patients_table.item(row, 0).data(Qt.UserRole)
        last_name = self.patients_table.item(row, 0).text()
        first_name = self.patients_table.item(row, 1).text()
        
        # Confirm deletion
        from PyQt5.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, 
            'Confirm Delete',
            f'Are you sure you want to delete patient "{last_name} {first_name}"?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Delete from database
            success = self.db_manager.delete_patient(patient_db_id)
            if success:
                print(f"Patient {last_name} {first_name} deleted successfully")
                # Refresh the patients list and reports
                self.load_patients_from_database()
                self.load_reports_from_database()
            else:
                print("Failed to delete patient")
        else:
            print("Delete cancelled")
    
    def load_reports_from_database(self):
        """Load reports from database"""
        reports = self.db_manager.get_all_reports()
        
        self.reports_table.setRowCount(len(reports))
        for row, report in enumerate(reports):
            self.reports_table.setItem(row, 0, QTableWidgetItem(report['patient_name']))
            self.reports_table.setItem(row, 1, QTableWidgetItem(report['report_date']))
            self.reports_table.setItem(row, 2, QTableWidgetItem(report['doctor_name']))
            self.reports_table.setItem(row, 3, QTableWidgetItem(report['specialization']))
            # Store report ID in row for later retrieval
            self.reports_table.item(row, 0).setData(Qt.UserRole, report['id'])
