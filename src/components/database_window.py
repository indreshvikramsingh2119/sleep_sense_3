"""
Patient Database Window - Sleep Sense Application
Replicates the database interface shown in the reference image
"""

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QSplitter, QGroupBox, QLineEdit, QCheckBox,
    QTableWidget, QTableWidgetItem, QPushButton, QHeaderView,
    QToolBar, QSizePolicy
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont


class DatabaseWindow(QMainWindow):
    """Patient Database Window matching the reference image design"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_sample_data()
        
    def init_ui(self):
        self.setWindowTitle("Patient Database")
        self.setGeometry(100, 100, 1200, 800)
        
        # Apply medical theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8f9fa;
            }
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                color: #2c3e50;
            }
        """)
        
        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main Layout
        main_layout = QVBoxLayout(central_widget)
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
        
        # Bottom toolbar
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
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAiIGhlaWdodD0iOCIgdmlld0JveD0iMCAwIDEwIDgiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTEgNEwzLjUgNi41TDkgMSIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPjwvc3ZnPg==);
            }
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
        self.view_btn = QPushButton("View")
        self.delete_btn = QPushButton("Delete")
        
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
        
        self.selection_btn.setStyleSheet(button_style)
        self.view_btn.setStyleSheet(button_style)
        self.delete_btn.setStyleSheet(delete_style)
        
        # Add buttons to layout
        layout.addWidget(self.selection_btn)
        layout.addWidget(self.view_btn)
        layout.addWidget(self.delete_btn)
        
        return toolbar
        
    def load_sample_data(self):
        """Load sample data matching the reference image"""
        # Patients data
        patients_data = [
            ("0", "Normal", "14-02-1967"),
            ("Example", "DSA", "21-09-1945"),
            ("Example", "Cheyne Stokes", "01-12-1958")
        ]
        
        self.patients_table.setRowCount(len(patients_data))
        for row, (last_name, first_name, dob) in enumerate(patients_data):
            self.patients_table.setItem(row, 0, QTableWidgetItem(last_name))
            self.patients_table.setItem(row, 1, QTableWidgetItem(first_name))
            self.patients_table.setItem(row, 2, QTableWidgetItem(dob))
        
        # Records data
        records_data = [
            ("0", "Normal", "28-04-2010", "22:34:10", "03:38:42", False),
            ("Example", "DSA", "23-08-2008", "23:33:44", "04:10:43", False),
            ("Example", "Cheyne Sto", "21-01-2009", "21:13:18", "08:42:50", False)
        ]
        
        self.records_table.setRowCount(len(records_data))
        for row, (last_name, first_name, rec_date, start_time, duration, archived) in enumerate(records_data):
            self.records_table.setItem(row, 0, QTableWidgetItem(last_name))
            self.records_table.setItem(row, 1, QTableWidgetItem(first_name))
            self.records_table.setItem(row, 2, QTableWidgetItem(rec_date))
            self.records_table.setItem(row, 3, QTableWidgetItem(start_time))
            self.records_table.setItem(row, 4, QTableWidgetItem(duration))
            
            # Add checkbox for archived column
            checkbox = QCheckBox()
            checkbox.setChecked(archived)
            checkbox.setEnabled(False)  # Make it read-only
            self.records_table.setCellWidget(row, 5, checkbox)
        
        # Reports data
        reports_data = [
            ("23-04-2026 11:39:39", "Analyzed automatically", ""),
            ("23-04-2026 11:31:35", "", "Edited manually"),
            ("18-04-2026 12:23:00", "", "Edited manually")
        ]
        
        self.reports_table.setRowCount(len(reports_data))
        for row, (datetime, analysis_status, manual_status) in enumerate(reports_data):
            self.reports_table.setItem(row, 0, QTableWidgetItem(datetime))
            self.reports_table.setItem(row, 1, QTableWidgetItem(analysis_status))
            self.reports_table.setItem(row, 2, QTableWidgetItem(manual_status))
        
        # Connect search functionality
        self.search_input.textChanged.connect(self.filter_patients)
        self.full_text_search.stateChanged.connect(self.filter_patients)
        self.search_at_keypress.stateChanged.connect(self.filter_patients)
        
        # Connect button actions
        self.selection_btn.clicked.connect(self.handle_selection)
        self.view_btn.clicked.connect(self.handle_view)
        self.delete_btn.clicked.connect(self.handle_delete)
        
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
        selected_rows = self.patients_table.selectedItems()
        if selected_rows:
            print(f"Selection: {len(set(item.row() for item in selected_rows))} patients selected")
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
        # Implementation for delete functionality
