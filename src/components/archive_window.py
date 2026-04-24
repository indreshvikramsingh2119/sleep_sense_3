"""
Archive Window - Sleep Sense Application
Replicates the archive interface shown in the reference image
"""

import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QGroupBox, QLineEdit, QCheckBox,
    QTableWidget, QTableWidgetItem, QPushButton, QHeaderView,
    QToolBar, QSizePolicy, QFileDialog, QMessageBox, QSplitter
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont


class ArchiveWindow(QMainWindow):
    """Archive Window matching the reference image design"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_sample_data()
        
    def init_ui(self):
        self.setWindowTitle("Archive Records")
        self.setGeometry(150, 150, 1000, 600)
        
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
        
        # Create main content area with splitter
        content_splitter = QSplitter(Qt.Horizontal)
        
        # Left side - Records Available section
        left_widget = self.create_records_available_section()
        content_splitter.addWidget(left_widget)
        
        # Middle - Transfer buttons
        transfer_widget = self.create_transfer_buttons()
        content_splitter.addWidget(transfer_widget)
        
        # Right side - Records to be Archived section
        right_widget = self.create_records_to_archive_section()
        content_splitter.addWidget(right_widget)
        
        content_splitter.setSizes([400, 80, 400])
        
        main_layout.addWidget(content_splitter)
        
        # Bottom toolbar with Archive and Cancel buttons
        bottom_toolbar = self.create_bottom_toolbar()
        main_layout.addWidget(bottom_toolbar)
        
    def create_records_available_section(self):
        """Create the Records Available section (left)"""
        group = QGroupBox("Records available")
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
        layout.setSpacing(10)
        
        # Search input
        search_layout = QHBoxLayout()
        search_label = QLabel("Go to:")
        search_label.setStyleSheet("""
            QLabel {
                font-weight: 600;
                color: #34495e;
                font-size: 13px;
            }
        """)
        search_label.setMinimumWidth(50)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search records...")
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
        
        # Records Available table
        self.available_table = QTableWidget()
        self.available_table.setColumnCount(5)
        self.available_table.setHorizontalHeaderLabels([
            "Last name", "First name", "Recording date", "Start time", "Duration"
        ])
        
        # Professional medical table styling
        self.available_table.setStyleSheet("""
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
        header = self.available_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.available_table.setAlternatingRowColors(True)
        self.available_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.available_table.setShowGrid(True)
        self.available_table.verticalHeader().setVisible(False)
        self.available_table.setSortingEnabled(True)
        
        layout.addWidget(self.available_table)
        
        return group
        
    def create_records_to_archive_section(self):
        """Create the Records to be Archived section (right)"""
        group = QGroupBox("Records to be archived")
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
        layout.setSpacing(10)
        
        # Target path section
        target_layout = QHBoxLayout()
        target_label = QLabel("Target:")
        target_label.setStyleSheet("""
            QLabel {
                font-weight: 600;
                color: #34495e;
                font-size: 13px;
            }
        """)
        target_label.setMinimumWidth(50)
        
        self.target_path = QLineEdit()
        self.target_path.setText("C:\\\\Export\\")
        self.target_path.setStyleSheet("""
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
        
        self.change_target_btn = QPushButton("Change target")
        self.change_target_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 12px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
        """)
        
        target_layout.addWidget(target_label)
        target_layout.addWidget(self.target_path)
        target_layout.addWidget(self.change_target_btn)
        layout.addLayout(target_layout)
        
        # Media name section
        media_layout = QHBoxLayout()
        media_label = QLabel("Media name:")
        media_label.setStyleSheet("""
            QLabel {
                font-weight: 600;
                color: #34495e;
                font-size: 13px;
            }
        """)
        media_label.setMinimumWidth(70)
        
        self.media_name = QLineEdit()
        self.media_name.setPlaceholderText("Enter media name...")
        self.media_name.setStyleSheet("""
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
        
        media_layout.addWidget(media_label)
        media_layout.addWidget(self.media_name)
        layout.addLayout(media_layout)
        
        # Records to Archive table
        self.archive_table = QTableWidget()
        self.archive_table.setColumnCount(5)
        self.archive_table.setHorizontalHeaderLabels([
            "Last name", "First name", "Recording date", "Start time", "Duration"
        ])
        
        # Professional medical table styling
        self.archive_table.setStyleSheet("""
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
        header = self.archive_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.archive_table.setAlternatingRowColors(True)
        self.archive_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.archive_table.setShowGrid(True)
        self.archive_table.verticalHeader().setVisible(False)
        self.archive_table.setSortingEnabled(True)
        
        layout.addWidget(self.archive_table)
        
        return group
        
    def create_transfer_buttons(self):
        """Create transfer buttons between the two sections"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)
        
        # Add vertical spacer to center buttons
        layout.addStretch()
        
        # Transfer right button (>>)
        self.transfer_right_btn = QPushButton(">>")
        self.transfer_right_btn.setFixedSize(50, 40)
        self.transfer_right_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        
        # Transfer left button (<<)
        self.transfer_left_btn = QPushButton("<<")
        self.transfer_left_btn.setFixedSize(50, 40)
        self.transfer_left_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        
        layout.addWidget(self.transfer_right_btn)
        layout.addWidget(self.transfer_left_btn)
        
        # Add vertical spacer to center buttons
        layout.addStretch()
        
        return widget
        
    def create_bottom_toolbar(self):
        """Create the bottom toolbar with Archive and Cancel buttons"""
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
        
        # Add spacer to push buttons to the right
        layout.addStretch()
        
        # Create buttons
        self.archive_btn = QPushButton("Archive")
        self.cancel_btn = QPushButton("Cancel")
        
        # Style buttons
        archive_style = """
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 13px;
                min-width: 90px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
        """
        
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
                background-color: #707b7c;
            }
        """
        
        self.archive_btn.setStyleSheet(archive_style)
        self.cancel_btn.setStyleSheet(cancel_style)
        
        # Add buttons to layout
        layout.addWidget(self.archive_btn)
        layout.addWidget(self.cancel_btn)
        
        return toolbar
        
    def load_sample_data(self):
        """Load sample data matching the reference image"""
        # Available records data
        available_data = [
            ("Example", "OSA", "23-08-2008", "23:33:44", "04:10:43"),
            ("Example", "Cheyne Stc", "21-01-2009", "21:13:18", "08:42:50"),
            ("0", "Normal", "28-04-2010", "22:34:10", "03:38:42")
        ]
        
        self.available_table.setRowCount(len(available_data))
        for row, (last_name, first_name, rec_date, start_time, duration) in enumerate(available_data):
            self.available_table.setItem(row, 0, QTableWidgetItem(last_name))
            self.available_table.setItem(row, 1, QTableWidgetItem(first_name))
            self.available_table.setItem(row, 2, QTableWidgetItem(rec_date))
            self.available_table.setItem(row, 3, QTableWidgetItem(start_time))
            self.available_table.setItem(row, 4, QTableWidgetItem(duration))
        
        # Initialize archive table as empty
        self.archive_table.setRowCount(0)
        
        # Connect functionality
        self.search_input.textChanged.connect(self.filter_available_records)
        self.full_text_search.stateChanged.connect(self.filter_available_records)
        self.search_at_keypress.stateChanged.connect(self.filter_available_records)
        
        # Transfer buttons
        self.transfer_right_btn.clicked.connect(self.transfer_to_archive)
        self.transfer_left_btn.clicked.connect(self.transfer_from_archive)
        
        # Bottom buttons
        self.change_target_btn.clicked.connect(self.change_target_path)
        self.archive_btn.clicked.connect(self.archive_records)
        self.cancel_btn.clicked.connect(self.close)
        
        # Update button states
        self.available_table.itemSelectionChanged.connect(self.update_transfer_buttons)
        self.archive_table.itemSelectionChanged.connect(self.update_transfer_buttons)
        
        # Initial button state
        self.update_transfer_buttons()
        
    def filter_available_records(self):
        """Filter available records table based on search criteria"""
        search_text = self.search_input.text().lower()
        full_text = self.full_text_search.isChecked()
        
        for row in range(self.available_table.rowCount()):
            visible = False
            
            if not search_text or self.search_at_keypress.isChecked():
                for col in range(self.available_table.columnCount()):
                    item = self.available_table.item(row, col)
                    if item and search_text in item.text().lower():
                        visible = True
                        break
            else:
                visible = True  # Show all if search at key press is disabled
                
            self.available_table.setRowHidden(row, not visible)
            
    def update_transfer_buttons(self):
        """Update transfer button states based on selection"""
        has_available_selection = len(self.available_table.selectedItems()) > 0
        has_archive_selection = len(self.archive_table.selectedItems()) > 0
        
        self.transfer_right_btn.setEnabled(has_available_selection)
        self.transfer_left_btn.setEnabled(has_archive_selection)
        
    def transfer_to_archive(self):
        """Transfer selected records from available to archive table"""
        selected_rows = sorted(set(item.row() for item in self.available_table.selectedItems()))
        
        if not selected_rows:
            return
            
        # Get selected data
        transfer_data = []
        for row in selected_rows:
            row_data = []
            for col in range(self.available_table.columnCount()):
                item = self.available_table.item(row, col)
                row_data.append(item.text() if item else "")
            transfer_data.append(row_data)
        
        # Add to archive table
        current_row_count = self.archive_table.rowCount()
        self.archive_table.setRowCount(current_row_count + len(transfer_data))
        
        for i, row_data in enumerate(transfer_data):
            for col, data in enumerate(row_data):
                self.archive_table.setItem(current_row_count + i, col, QTableWidgetItem(data))
        
        # Remove from available table (in reverse order to maintain indices)
        for row in reversed(selected_rows):
            self.available_table.removeRow(row)
            
    def transfer_from_archive(self):
        """Transfer selected records from archive to available table"""
        selected_rows = sorted(set(item.row() for item in self.archive_table.selectedItems()))
        
        if not selected_rows:
            return
            
        # Get selected data
        transfer_data = []
        for row in selected_rows:
            row_data = []
            for col in range(self.archive_table.columnCount()):
                item = self.archive_table.item(row, col)
                row_data.append(item.text() if item else "")
            transfer_data.append(row_data)
        
        # Add to available table
        current_row_count = self.available_table.rowCount()
        self.available_table.setRowCount(current_row_count + len(transfer_data))
        
        for i, row_data in enumerate(transfer_data):
            for col, data in enumerate(row_data):
                self.available_table.setItem(current_row_count + i, col, QTableWidgetItem(data))
        
        # Remove from archive table (in reverse order to maintain indices)
        for row in reversed(selected_rows):
            self.archive_table.removeRow(row)
            
    def change_target_path(self):
        """Open file dialog to change target path"""
        folder_path = QFileDialog.getExistingDirectory(self, "Select Target Directory")
        if folder_path:
            self.target_path.setText(folder_path)
            
    def archive_records(self):
        """Archive the records in the archive table"""
        if self.archive_table.rowCount() == 0:
            QMessageBox.warning(self, "Warning", "No records to archive!")
            return
            
        if not self.media_name.text().strip():
            QMessageBox.warning(self, "Warning", "Please enter a media name!")
            return
            
        # Show confirmation dialog
        reply = QMessageBox.question(
            self, 
            "Confirm Archive", 
            f"Archive {self.archive_table.rowCount()} record(s) to:\n{self.target_path.text()}\n\nMedia name: {self.media_name.text()}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Simulate archiving process
            QMessageBox.information(
                self, 
                "Archive Complete", 
                f"Successfully archived {self.archive_table.rowCount()} record(s)!"
            )
            
            # Clear archive table and reset
            self.archive_table.setRowCount(0)
            self.media_name.clear()
            
            # Optionally close the window
            # self.close()
