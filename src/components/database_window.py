"""
Patient Database Window - Sleep Sense Application.
Replicates the database interface shown in the reference image.
"""

from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QSplitter, QGroupBox, QLineEdit,
    QTableWidget, QTableWidgetItem, QPushButton, QHeaderView,
    QToolBar, QSizePolicy, QMessageBox, QInputDialog
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont
import hashlib
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.utils.database_manager import DatabaseManager
from src.utils.db_utils import list_sessions


# ---------------------------------------------------------------------------
# EDIT PASSWORD
# ---------------------------------------------------------------------------

#
#  password: admin123
EDIT_PASSWORD_HASH = "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9"


class StrictClickButton(QPushButton):
    """Push button that only activates on a deliberate click, not a drag."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._press_pos = None
        self._click_valid = False
        self.setFocusPolicy(Qt.NoFocus)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.pos()
            self._click_valid = True
        else:
            self._click_valid = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._click_valid and self._press_pos is not None:
            delta = event.pos() - self._press_pos
            if delta.manhattanLength() > 4:
                self._click_valid = False
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if not self._click_valid or event.button() != Qt.LeftButton:
            self._click_valid = False
            self._press_pos = None
            event.ignore()
            return

        if not self.rect().contains(event.pos()):
            self._click_valid = False
            self._press_pos = None
            event.ignore()
            return

        self._click_valid = False
        self._press_pos = None
        super().mouseReleaseEvent(event)


class DatabaseWindow(QDialog):
    """Patient Database Window matching the reference image design"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(False)
        self.setWindowTitle("Patient Database")
        self.setFixedSize(1200, 800)
        self.db_manager = DatabaseManager()
        self.init_ui()
 
        self.connect_signals()
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
        
        # Patients table
        self.patients_table = QTableWidget()
        self.patients_table.setColumnCount(4)
        self.patients_table.setHorizontalHeaderLabels(["Last name", "First name", "Date of birth", "Edit"])
        
        # Professional medical table styling
        self.patients_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #b7c8d8;
                border-radius: 6px;
                background-color: #ffffff;
                gridline-color: #b7c8d8;
                selection-background-color: #e3f2fd;
                selection-color: #1565c0;
            }
            QTableWidget::item {
                padding: 8px;
                border: 1px solid #c1cfdb;
            }
            QTableWidget::item:selected {
                background-color: #d9ecfb;
                color: #123b63;
            }
            QTableWidget::item:hover {
                background-color: #edf7fe;
            }
            QHeaderView::section {
                background-color: #f8fbfd;
                color: #1e3a5f;
                font-weight: 600;
                font-size: 13px;
                padding: 10px 8px;
                border: 1px solid #b7c8d8;
                border-right: none;
                border-bottom: 2px solid #3498db;
            }
            QHeaderView::section:last {
                border-right: 1px solid #b7c8d8;
            }
        """)
        
        # Set table properties
        header = self.patients_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.patients_table.setColumnWidth(3, 110)
        self.patients_table.setAlternatingRowColors(True)
        self.patients_table.setSelectionBehavior(QTableWidget.SelectRows)
        # KYON: default ExtendedSelection me halka sa drag hote hi kai rows
        # select ho jate the, aur neeche wala code sabse upar wali row utha
        # leta tha - isliye galat patient ke records dikhne lagte the.
        self.patients_table.setSelectionMode(QTableWidget.SingleSelection)
        self.patients_table.setShowGrid(True)
        self.patients_table.verticalHeader().setVisible(False)
        self.patients_table.setSortingEnabled(True)
        # Disable inline editing triggered by double-click. Edit must happen only
        # through the Edit button.
        self.patients_table.setEditTriggers(QTableWidget.NoEditTriggers)
        # Fix row height so the Edit button stays vertically centered.
        self.patients_table.verticalHeader().setDefaultSectionSize(36)
        
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
                border: 1px solid #b7c8d8;
                border-radius: 6px;
                background-color: #ffffff;
                gridline-color: #b7c8d8;
                selection-background-color: #e3f2fd;
                selection-color: #1565c0;
            }
            QTableWidget::item {
                padding: 8px;
                border: 1px solid #c1cfdb;
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
                border: 1px solid #b7c8d8;
                border-right: none;
                border-bottom: 2px solid #3498db;
            }
            QHeaderView::section:last {
                border-right: 1px solid #b7c8d8;
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
        self.records_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
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
        self.reports_table.setHorizontalHeaderLabels(["Report date", "Doctor", "Specialization"])
        
        # Professional medical table styling
        self.reports_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #b7c8d8;
                border-radius: 6px;
                background-color: #ffffff;
                gridline-color: #b7c8d8;
                selection-background-color: #e3f2fd;
                selection-color: #1565c0;
            }
            QTableWidget::item {
                padding: 8px;
                border: 1px solid #c1cfdb;
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
                border: 1px solid #b7c8d8;
                border-right: none;
                border-bottom: 2px solid #3498db;
            }
            QHeaderView::section:last {
                border-right: 1px solid #b7c8d8;
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
        self.reports_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
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

    def connect_signals(self):
        """Connect signals only once when the window is created."""
        # Connect search functionality
        self.search_input.textChanged.connect(self.filter_patients)

        # Connect button actions
        self.selection_btn.clicked.connect(self.handle_selection)
        self.delete_btn.clicked.connect(self.handle_delete)
        self.cancel_btn.clicked.connect(self.reject)  # Close dialog

        # Load recordings and reports only when a patient row is actually clicked
        self.patients_table.itemClicked.connect(self.on_patient_clicked)
        # Double-click a recording -> load that CSV into the charts
        self.records_table.itemDoubleClicked.connect(self.open_selected_record)
        # Double-click a report -> open the PDF
        self.reports_table.itemDoubleClicked.connect(self.open_selected_report)

    def on_patient_clicked(self, item):
        """Handle explicit patient-row clicks only."""
        self.on_patient_selection_changed()

    def on_patient_selection_changed(self):
        """Refresh Records and Reports for the selected patient.

        Pehle dono tables khali karte hain, taaki patient badalte waqt
        pichhle patient ka data ek pal ke liye bhi na dikhe.
        """
        self.records_table.setRowCount(0)
        self.reports_table.setRowCount(0)

        patient = self.get_selected_patient()
        if not patient:
            return

        self.load_records_for_patient(patient)
        self.load_reports_from_database(patient)

    def get_selected_patient(self):
        """Jis row par user ne click kiya, usi patient ka poora DB row (ya None).

        currentRow() use karte hain, selectedItems()[0] nahi - wo hamesha
        sabse UPAR wali selected row deta hai, click ki hui row nahi.
        """
        row = self.patients_table.currentRow()
        if row < 0 or self.patients_table.isRowHidden(row):
            return None

        name_item = self.patients_table.item(row, 0)
        if name_item is None:
            return None

        patient_db_id = name_item.data(Qt.UserRole)
        if patient_db_id is None:
            return None

        return self.db_manager.get_patient_by_id(patient_db_id)

    def show_patient_selected_success(self, patient):
        """Show a green confirmation popup after the user selects a patient."""
        if not patient:
            return

        first_name = str(patient.get("first_name") or "").strip()
        last_name = str(patient.get("last_name") or "").strip()
        display_name = " ".join(part for part in (first_name, last_name) if part).strip() or "Patient"
        patient_code = patient.get("patient_id") or patient.get("id") or "Unknown"

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Patient Selected")
        msg_box.setText(f"{display_name} with ID {patient_code} was selected successfully.")
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #f0fdf4;
            }
            QMessageBox QLabel {
                color: #166534;
                font-size: 13px;
                font-weight: 700;
            }
            QMessageBox QPushButton {
                min-width: 54px;
                min-height: 22px;
                padding: 4px 12px;
                border-radius: 6px;
                border: 1px solid #15803d;
                background-color: #22c55e;
                color: white;
                font-size: 11px;
                font-weight: 700;
            }
            QMessageBox QPushButton:hover {
                background-color: #4ade80;
                border: 1px solid #166534;
            }
            QMessageBox QPushButton:pressed {
                background-color: #16a34a;
                border: 1px solid #14532d;
            }
        """)
        msg_box.setStandardButtons(QMessageBox.Ok)
        ok_button = msg_box.button(QMessageBox.Ok)
        if ok_button is not None:
            ok_button.setAutoDefault(False)
            ok_button.setDefault(True)
            ok_button.setStyleSheet("""
                QPushButton {
                    min-width: 54px;
                    min-height: 22px;
                    padding: 4px 12px;
                    border-radius: 6px;
                    border: 1px solid #15803d;
                    background-color: #22c55e;
                    color: white;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #4ade80;
                    border: 1px solid #166534;
                }
                QPushButton:pressed {
                    background-color: #16a34a;
                    border: 1px solid #14532d;
                }
            """)
        msg_box.exec_()

    def load_records_for_patient(self, patient):
        """Populate the Records table with the selected patient's saved sessions."""
        self.records_table.setRowCount(0)
        if not patient:
            return

        try:
            sessions = list_sessions(
                patient_id=(patient.get('patient_id') or None),
                patient_db_id=patient.get('id'),
            )
        except Exception as error:
            print(f"Error loading sessions: {error}")
            return

        was_sorting = self.records_table.isSortingEnabled()
        self.records_table.setSortingEnabled(False)
        self.records_table.setRowCount(len(sessions))

        for row, session in enumerate(sessions):
            saved_at = str(session.get('saved_at') or '')
            if 'T' in saved_at:
                recording_date, start_time = saved_at.split('T', 1)
            else:
                recording_date, start_time = saved_at, ''

            file_path = str(session.get('file_path') or '')
            archived = "Yes" if file_path and os.path.exists(file_path) else "Missing"

            first_item = QTableWidgetItem(patient.get('last_name') or "")
            first_item.setData(Qt.UserRole, file_path)
            self.records_table.setItem(row, 0, first_item)
            self.records_table.setItem(row, 1, QTableWidgetItem(patient.get('first_name') or ""))
            self.records_table.setItem(row, 2, QTableWidgetItem(recording_date))
            self.records_table.setItem(row, 3, QTableWidgetItem(start_time))
            self.records_table.setItem(row, 4, QTableWidgetItem(session.get('duration') or "--"))
            self.records_table.setItem(row, 5, QTableWidgetItem(archived))

        self.records_table.setSortingEnabled(was_sorting)

    def open_selected_record(self, item):
        """Double-click a Records row to load that recording in the dashboard."""
        row = item.row()
        first_item = self.records_table.item(row, 0)
        if first_item is None:
            return

        file_path = first_item.data(Qt.UserRole)
        if not file_path:
            QMessageBox.warning(self, "No File", "This session did not save a file path.")
            return

        if not os.path.exists(file_path):
            QMessageBox.warning(
                self,
                "File Not Found",
                f"The recording file no longer exists:\n{file_path}",
            )
            return

        parent = self.parent()
        patient = self.get_selected_patient()
        if patient and parent and hasattr(parent, 'load_patient_data'):
            parent.load_patient_data(patient)

        if parent and hasattr(parent, 'load_psg_data_from_path'):
            if parent.load_psg_data_from_path(file_path):
                self.accept()
        else:
            QMessageBox.warning(self, "Not Available", "The dashboard cannot load this recording.")

    def load_patients_from_database(self):
        """Load patients from the database."""
        patients = self.db_manager.get_all_patients()

        # Disable sorting while filling, otherwise rows can shuffle mid-load.
        was_sorting = self.patients_table.isSortingEnabled()
        self.patients_table.setSortingEnabled(False)

        self.patients_table.setRowCount(len(patients))
        for row, patient in enumerate(patients):
            self.patients_table.setItem(row, 0, QTableWidgetItem(patient['last_name'] or ""))
            self.patients_table.setItem(row, 1, QTableWidgetItem(patient['first_name'] or ""))
            self.patients_table.setItem(row, 2, QTableWidgetItem(patient['dob'] or ""))
            # Store the patient ID in the row for later retrieval
            self.patients_table.item(row, 0).setData(Qt.UserRole, patient['id'])
            # Each row gets its own Edit button
            self.patients_table.setCellWidget(row, 3, self.create_edit_button())

        self.patients_table.setSortingEnabled(was_sorting)
        
        # Clear the Records table for now
        self.records_table.setRowCount(0)
        # Load reports for the selected patient
        self.load_reports_from_database(self.get_selected_patient())

    def create_edit_button(self):
        """Create a simple Edit button for one row."""
        button = StrictClickButton("Edit")
        button.setCursor(Qt.PointingHandCursor)
        button.setFixedHeight(24)
        button.setMinimumWidth(64)
        button.setStyleSheet("""
            QPushButton {
                background-color: #f8fbfd;
                color: #1e3a5f;
                border: 1px solid #3498db;
                border-radius: 4px;
                padding: 4px 12px;
                font-weight: 700;
                font-size: 12px;
                min-width: 64px;
            }
            QPushButton:hover {
                background-color: #e3f2fd;
                border-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #d6eaf8;
            }
        """)
        # NOTE: Do not capture the row index here. When QTableWidget sorts,
        # cell widgets do not move with the data, so we resolve the real row
        # at click time using indexAt().
        button.clicked.connect(lambda checked=False, btn=button: self.handle_edit_patient(btn))
        return button

    def verify_edit_password(self):
        """Ask for the password before editing. Return True only if it matches."""
        password, ok = QInputDialog.getText(
            self,
            "Password Required",
            "Please enter the password before editing:",
            QLineEdit.Password,
        )
        if not ok:
            return False

        entered_hash = hashlib.sha256((password or "").encode("utf-8")).hexdigest()
        if entered_hash != EDIT_PASSWORD_HASH:
            QMessageBox.warning(
                self,
                "Wrong Password",
                "The password is incorrect. These details cannot be edited.",
            )
            return False

        return True

    def handle_edit_patient(self, cell_widget):
        """Edit button -> password -> prefilled patient form -> DB update."""
        index = self.patients_table.indexAt(cell_widget.pos())
        if not index.isValid():
            print("Could not resolve row for edit button")
            return

        row = index.row()
        name_item = self.patients_table.item(row, 0)
        if name_item is None:
            return

        patient_db_id = name_item.data(Qt.UserRole)
        if patient_db_id is None:
            QMessageBox.warning(self, "Not Found", "Could not find the patient ID for this row.")
            return

        if not self.verify_edit_password():
            return

        patient_data = self.db_manager.get_patient_by_id(patient_db_id)
        if not patient_data:
            QMessageBox.critical(self, "Error", "Could not load patient details from the database.")
            return

        from src.components.patient_record_form import PatientRecordForm

        form = PatientRecordForm(self, patient_data=patient_data)
        if form.exec_() == QDialog.Accepted:
            self.load_patients_from_database()
        
    def filter_patients(self):
        """Filter patients table based on search criteria"""
        search_text = self.search_input.text().lower()
        
        for row in range(self.patients_table.rowCount()):
            visible = False

            if not search_text:
                visible = True
            else:
                for col in range(self.patients_table.columnCount()):
                    item = self.patients_table.item(row, col)
                    if item and search_text in item.text().lower():
                        visible = True
                        break
                
            self.patients_table.setRowHidden(row, not visible)
            
    def handle_selection(self):
        """Handle Selection button click"""
        row = self.patients_table.currentRow()
        if row >= 0 and not self.patients_table.isRowHidden(row):
            # Get the patient database ID from the row
            patient_db_id = self.patients_table.item(row, 0).data(Qt.UserRole)
            
            # Get patient data from the selected row
            last_name = self.patients_table.item(row, 0).text()
            first_name = self.patients_table.item(row, 1).text()
            dob = self.patients_table.item(row, 2).text()
            
            # Fetch the full patient data from the database
            full_patient_data = self.db_manager.get_patient_by_id(patient_db_id)
            
            if full_patient_data:
                print(f"Selected patient: {full_patient_data['last_name']} {full_patient_data['first_name']} (DB ID: {patient_db_id})")
                
                # Set patient data in the parent dashboard
                if self.parent() and hasattr(self.parent(), 'load_patient_data'):
                    self.parent().load_patient_data(full_patient_data)
                else:
                    # Fallback to the old method if load_patient_data does not exist
                    if self.parent() and hasattr(self.parent(), 'monitor_chart'):
                        patient_id_str = f"{last_name}_{first_name}_{dob}"
                        self.parent().monitor_chart.set_patient_id(patient_id_str)
                        
                        # Update the patient info widget
                        if hasattr(self.parent(), 'patient_info'):
                            self.parent().patient_info.set_patient_data({
                                'last_name': last_name,
                                'first_name': first_name,
                                'dob': dob,
                                'patient_id': patient_id_str
                            })

                self.show_patient_selected_success(full_patient_data)
                # Close the dialog
                self.accept()
            else:
                print("Error: Could not fetch patient data from the database")
        else:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("No Selection")
            msg_box.setText("Please select a patient first.")
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #f8fbff;
                }
                QMessageBox QLabel {
                    color: #111827;
                    font-size: 13px;
                    font-weight: 500;
                }
                QMessageBox QPushButton {
                    min-width: 54px;
                    min-height: 22px;
                    padding: 4px 12px;
                    border-radius: 6px;
                    border: 1px solid #1d4ed8;
                    background-color: #2563eb;
                    color: white;
                    font-size: 11px;
                    font-weight: 700;
                }
                QMessageBox QPushButton:hover {
                    background-color: #3b82f6;
                    border: 1px solid #1e40af;
                }
                QMessageBox QPushButton:pressed {
                    background-color: #1e40af;
                    border: 1px solid #1e3a8a;
                }
            """)
            msg_box.setStandardButtons(QMessageBox.Ok)
            ok_button = msg_box.button(QMessageBox.Ok)
            if ok_button is not None:
                ok_button.setAutoDefault(False)
                ok_button.setDefault(True)
                ok_button.setStyleSheet("""
                    QPushButton {
                        min-width: 54px;
                        min-height: 22px;
                        padding: 4px 12px;
                        border-radius: 6px;
                        border: 1px solid #1d4ed8;
                        background-color: #2563eb;
                        color: white;
                        font-size: 11px;
                        font-weight: 700;
                    }
                    QPushButton:hover {
                        background-color: #3b82f6;
                        border: 1px solid #1e40af;
                    }
                    QPushButton:pressed {
                        background-color: #1e40af;
                        border: 1px solid #1e3a8a;
                    }
                """)
            msg_box.exec_()
            
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
        row = self.patients_table.currentRow()
        if row < 0 or self.patients_table.isRowHidden(row):
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("No Selection")
            msg_box.setText("Please select a patient first.")
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #f8fbff;
                }
                QMessageBox QLabel {
                    color: #111827;
                    font-size: 13px;
                    font-weight: 500;
                }
                QMessageBox QPushButton {
                    min-width: 54px;
                    min-height: 22px;
                    padding: 4px 12px;
                    border-radius: 6px;
                    border: 1px solid #1d4ed8;
                    background-color: #2563eb;
                    color: white;
                    font-size: 11px;
                    font-weight: 700;
                }
                QMessageBox QPushButton:hover {
                    background-color: #3b82f6;
                    border: 1px solid #1e40af;
                }
                QMessageBox QPushButton:pressed {
                    background-color: #1e40af;
                    border: 1px solid #1e3a8a;
                }
            """)
            msg_box.setStandardButtons(QMessageBox.Ok)
            ok_button = msg_box.button(QMessageBox.Ok)
            if ok_button is not None:
                ok_button.setAutoDefault(False)
                ok_button.setDefault(True)
                ok_button.setStyleSheet("""
                    QPushButton {
                        min-width: 54px;
                        min-height: 22px;
                        padding: 4px 12px;
                        border-radius: 6px;
                        border: 1px solid #1d4ed8;
                        background-color: #2563eb;
                        color: white;
                        font-size: 11px;
                        font-weight: 700;
                    }
                    QPushButton:hover {
                        background-color: #3b82f6;
                        border: 1px solid #1e40af;
                    }
                    QPushButton:pressed {
                        background-color: #1e40af;
                        border: 1px solid #1e3a8a;
                    }
                """)
            msg_box.exec_()
            return
            
        # Get patient data
        patient_db_id = self.patients_table.item(row, 0).data(Qt.UserRole)
        last_name = self.patients_table.item(row, 0).text()
        first_name = self.patients_table.item(row, 1).text()
        
        # Confirm deletion
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Confirm Delete")
        msg_box.setText(f'Are you sure you want to delete patient "{last_name} {first_name}"?')
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #fffaf7;
            }
            QMessageBox QLabel {
                color: #111827;
                font-size: 13px;
                font-weight: 500;
            }
            QMessageBox QPushButton {
                min-width: 54px;
                min-height: 22px;
                padding: 4px 12px;
                border-radius: 6px;
                border: 1px solid #1d4ed8;
                background-color: #2563eb;
                color: white;
                font-size: 11px;
                font-weight: 700;
            }
            QMessageBox QPushButton:hover {
                background-color: #3b82f6;
                border: 1px solid #1e40af;
            }
            QMessageBox QPushButton:pressed {
                background-color: #1e40af;
                border: 1px solid #1e3a8a;
            }
        """)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        yes_button = msg_box.button(QMessageBox.Yes)
        no_button = msg_box.button(QMessageBox.No)
        if yes_button is not None:
            yes_button.setText("Yes")
            yes_button.setAutoDefault(False)
            yes_button.setDefault(False)
            yes_button.setStyleSheet("""
                QPushButton {
                    min-width: 54px;
                    min-height: 22px;
                    padding: 4px 12px;
                    border-radius: 6px;
                    border: 1px solid #dc2626;
                    background-color: #ef4444;
                    color: white;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #f87171;
                    border: 1px solid #b91c1c;
                }
                QPushButton:pressed {
                    background-color: #dc2626;
                    border: 1px solid #991b1b;
                }
            """)
        if no_button is not None:
            no_button.setText("No")
            no_button.setAutoDefault(False)
            no_button.setDefault(True)
            no_button.setStyleSheet("""
                QPushButton {
                    min-width: 54px;
                    min-height: 22px;
                    padding: 4px 12px;
                    border-radius: 6px;
                    border: 1px solid #1d4ed8;
                    background-color: #2563eb;
                    color: white;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #3b82f6;
                    border: 1px solid #1e40af;
                }
                QPushButton:pressed {
                    background-color: #1e40af;
                    border: 1px solid #1e3a8a;
                }
            """)
        reply = msg_box.exec_()
        
        if reply == QMessageBox.Yes:
            # Delete from database
            success = self.db_manager.delete_patient(patient_db_id)
            if success:
                print(f"Patient {last_name} {first_name} deleted successfully")
                # Refresh the patients list (reports/records update inside this call)
                self.load_patients_from_database()
            else:
                print("Failed to delete patient")
        else:
            print("Delete cancelled")
    
    def load_reports_from_database(self, patient=None):
        """Load reports. If a patient is provided, show only that patient's reports."""
        if patient and patient.get('id'):
            reports = self.db_manager.get_patient_reports(patient['id'])
        else:
            reports = self.db_manager.get_all_reports()

        was_sorting = self.reports_table.isSortingEnabled()
        self.reports_table.setSortingEnabled(False)
        self.reports_table.setRowCount(len(reports))

        for row, report in enumerate(reports):
            date_item = QTableWidgetItem(str(report.get('report_date') or ''))
            # Store both the PDF path and the report ID in the row
            date_item.setData(Qt.UserRole, str(report.get('pdf_path') or ''))
            date_item.setData(Qt.UserRole + 1, report.get('id'))
            self.reports_table.setItem(row, 0, date_item)
            self.reports_table.setItem(row, 1, QTableWidgetItem(str(report.get('doctor_name') or '')))
            self.reports_table.setItem(row, 2, QTableWidgetItem(str(report.get('specialization') or '')))

        self.reports_table.setSortingEnabled(was_sorting)

    def open_selected_report(self, item):
        """Double-click a report row to open its PDF."""
        first_item = self.reports_table.item(item.row(), 0)
        if first_item is None:
            return

        pdf_path = first_item.data(Qt.UserRole)
        if not pdf_path:
            QMessageBox.information(
                self,
                "No PDF",
                "This report did not save a PDF path.\n"
                "It was probably created before this feature existed.",
            )
            return

        if not os.path.exists(pdf_path):
            QMessageBox.warning(
                self,
                "File Not Found",
                f"The report PDF no longer exists:\n{pdf_path}",
            )
            return

        try:
            from .medical_report_form import PDFViewerWidget
            viewer = PDFViewerWidget(pdf_path, self, allow_print=True)
            viewer.exec_()
        except Exception as error:
            # If the internal viewer fails, open the PDF with the system default app
            print(f"Internal PDF viewer failed: {error}")
            from PyQt5.QtGui import QDesktopServices
            from PyQt5.QtCore import QUrl
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(pdf_path)):
                QMessageBox.critical(self, "Cannot Open", f"Could not open the PDF:\n{pdf_path}")
