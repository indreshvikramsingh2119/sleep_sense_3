"""
Patient Database Window - Sleep Sense Application.
Replicates the database interface shown in the reference image.
"""

from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QSplitter, QGroupBox, QLineEdit,
    QTableWidget, QTableWidgetItem, QPushButton, QHeaderView,
    QToolBar, QSizePolicy, QMessageBox, QInputDialog, QDialogButtonBox,
    QApplication
)
from PyQt5.QtCore import Qt, QSize, QEvent
from PyQt5.QtGui import QFont, QColor, QBrush
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
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setWindowTitle("Patient Database")
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        available_width = available.width() if available else 1366
        available_height = available.height() if available else 768
        target_width = min(1200, max(900, available_width - 32))
        target_height = min(800, max(560, available_height - 32))
        self.setMinimumSize(min(900, target_width), min(560, target_height))
        self.resize(target_width, target_height)
        self.db_manager = DatabaseManager()
        self._record_group_rows = {}
        self._last_child_table = None
        self._syncing_child_selection = False
        self._patient_hover_row = -1
        self._record_hover_row = -1
        self._record_hover_backgrounds = {}
        self._report_hover_row = -1
        self._report_hover_backgrounds = {}
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
                outline: none;
                background-color: #ffffff;
                gridline-color: #b7c8d8;
                selection-background-color: #e3f2fd;
                selection-color: #1565c0;
            }
            QTableWidget::item {
                padding: 4px 8px;
                border: 1px solid #c1cfdb;
            }
            QTableWidget::item:selected {
                background-color: #d9ecfb;
                color: #123b63;
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
        # A normal click keeps one patient selected. Holding Shift selects the
        # complete range between the current row and the clicked row. The
        # Delete action uses these selected rows; Selection still uses only
        # the current row below.
        self.patients_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.patients_table.setMouseTracking(True)
        self.patients_table.viewport().setMouseTracking(True)
        self.patients_table.viewport().installEventFilter(self)
        self.patients_table.setShowGrid(True)
        self.patients_table.verticalHeader().setVisible(False)
        # Disable inline editing triggered by double-click. Edit must happen only
        # through the Edit button.
        self.patients_table.setEditTriggers(QTableWidget.NoEditTriggers)
        # Fix row height so the Edit button stays vertically centered.
        self.patients_table.verticalHeader().setMinimumSectionSize(40)
        self.patients_table.verticalHeader().setDefaultSectionSize(40)
        
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
        # Column 0 is a narrow "+/-" expand column: a root recording row that
        # has reanalyzed ("New report") versions saved under it gets a toggle
        # button there to show/hide those child rows.
        self.records_table = QTableWidget()
        self.records_table.setColumnCount(7)
        self.records_table.setHorizontalHeaderLabels([
            "", "Last name", "First name", "Patient ID", "Recording date",
            "Start time", "Duration"
        ])
        
        # Professional medical table styling
        self.records_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #b7c8d8;
                border-radius: 6px;
                outline: none;
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
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.records_table.setColumnWidth(0, 32)
        self.records_table.setAlternatingRowColors(True)
        self.records_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.records_table.setMouseTracking(True)
        self.records_table.viewport().setMouseTracking(True)
        self.records_table.viewport().installEventFilter(self)
        self.records_table.setShowGrid(True)
        self.records_table.verticalHeader().setVisible(False)
        # Sorting stays off here: root/child (reanalyzed) rows must sit next
        # to each other for the +/- expand toggle to work.
        self.records_table.setSortingEnabled(False)
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
                outline: none;
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
        self.reports_table.setMouseTracking(True)
        self.reports_table.viewport().setMouseTracking(True)
        self.reports_table.viewport().installEventFilter(self)
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
        self.delete_btn.setAutoRepeat(False)
        
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
        # Double-click a recording -> load that binary recording into the charts.
        self.records_table.itemDoubleClicked.connect(self.open_selected_record)
        # Double-click a report -> open the PDF
        self.reports_table.itemDoubleClicked.connect(self.open_selected_report)

        self.records_table.itemSelectionChanged.connect(
            lambda: self._on_child_table_selection_changed(self.records_table, self.reports_table)
        )
        self.reports_table.itemSelectionChanged.connect(
            lambda: self._on_child_table_selection_changed(self.reports_table, self.records_table)
        )

    def _on_child_table_selection_changed(self, active_table, other_table):
        """Remember the table the user is working in and clear the other one."""
        if self._syncing_child_selection:
            return
        if not active_table.selectedRanges():
            return
        self._last_child_table = active_table
        self._syncing_child_selection = True
        try:
            other_table.clearSelection()
        finally:
            self._syncing_child_selection = False

    def on_patient_clicked(self, item):
        """Handle explicit patient-row clicks only."""
        self._last_child_table = None
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

        # Remember this on the main dashboard window (NOT on self) - this
        # DatabaseWindow dialog gets thrown away and recreated from scratch
        # (see dashboard.py's open_database()) every time it's closed, e.g.
        # right after double-clicking a Records row to load a recording.
        # Storing it on the parent means the NEXT DatabaseWindow instance
        # can still find out who was selected before.
        parent = self.parent()
        if parent is not None:
            parent._last_selected_database_patient_id = patient.get('id')

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
        msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
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
        """Populate the Records table with the selected patient's saved sessions.

        Sessions are grouped: an original recording is a "root" row, and any
        Re-analyze -> "New report" saves made from that same recording are
        nested underneath it as hidden "child" rows, revealed with the +/-
        button in column 0. Recordings saved before this feature existed have
        no parent_session_id, so they simply show up as roots with no
        children - nothing about them changes.
        """
        self._set_record_hover_row(-1)
        self.records_table.setRowCount(0)
        self._record_group_rows = {}
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

        self.records_table.setSortingEnabled(False)
        sessions_by_id = {s.get('id'): s for s in sessions if s.get('id') is not None}
        children_by_root = {}
        roots = []
        for session in sessions:
            parent_id = session.get('parent_session_id')
            if parent_id and parent_id in sessions_by_id and parent_id != session.get('id'):
                children_by_root.setdefault(parent_id, []).append(session)
            else:
                roots.append(session)

        total_rows = len(roots) + sum(len(v) for v in children_by_root.values())
        self.records_table.setRowCount(total_rows)

        row = 0
        for root_session in roots:
            self._populate_record_row(row, patient, root_session, is_child=False)
            root_row = row
            row += 1

            child_rows = []
            for child_session in children_by_root.get(root_session.get('id'), []):
                self._populate_record_row(row, patient, child_session, is_child=True)
                self.records_table.setRowHidden(row, True)
                child_rows.append(row)
                row += 1

            if child_rows:
                self._record_group_rows[root_row] = child_rows
                self.records_table.setCellWidget(root_row, 0, self.create_expand_button(child_rows))

    def _populate_record_row(self, row, patient, session, is_child):
        """Fill one Records row (either a root recording or a reanalyzed child)."""
        saved_at = str(session.get('saved_at') or '')
        if 'T' in saved_at:
            recording_date, start_time = saved_at.split('T', 1)
        else:
            recording_date, start_time = saved_at, ''

        file_path = str(session.get('file_path') or '')
        patient_id_value = str(patient.get('patient_id') or session.get('patient_id') or '')

        first_name_text = patient.get('first_name') or ""
        if is_child:
            first_name_text = f"↳ Reanalyzed - {first_name_text}".strip(" -")

        last_item = QTableWidgetItem(patient.get('last_name') or "")
        # File path + session identity travel on the Last name cell so
        # open_selected_record() and a later re-analyze save can find them.
        last_item.setData(Qt.UserRole, file_path)
        last_item.setData(Qt.UserRole + 1, session.get('id'))
        last_item.setData(Qt.UserRole + 2, session.get('parent_session_id'))

        items = [
            last_item,
            QTableWidgetItem(first_name_text),
            QTableWidgetItem(patient_id_value),
            QTableWidgetItem(recording_date),
            QTableWidgetItem(start_time),
            QTableWidgetItem(session.get('duration') or "--"),
        ]

        if is_child:
            for cell in items:
                cell.setBackground(QColor("#f3f8fc"))
                cell.setForeground(QColor("#5b6b7c"))
                font = cell.font()
                font.setItalic(True)
                cell.setFont(font)

        for col, cell in enumerate(items, start=1):
            self.records_table.setItem(row, col, cell)

    def create_expand_button(self, child_rows):
        """+/- toggle shown on a root Records row that has reanalyzed children."""
        button = StrictClickButton("+")
        button.setProperty("recordExpandButton", True)
        button.installEventFilter(self)
        button.setCursor(Qt.PointingHandCursor)
        button.setFixedSize(24, 24)
        button.setStyleSheet("""
            QPushButton {
                background-color: #eef6fc;
                color: #1e3a5f;
                border: 1px solid #3498db;
                border-radius: 4px;
                font-weight: 700;
                font-size: 13px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #d9ecfb;
            }
            QPushButton:pressed {
                background-color: #bfe0f7;
            }
        """)
        button.clicked.connect(lambda checked=False, btn=button, rows=child_rows: self.toggle_record_group(btn, rows))
        return button

    def toggle_record_group(self, button, child_rows):
        """Expand/collapse the reanalyzed (child) rows beneath a record."""
        expanding = button.text() == "+"
        for row in child_rows:
            if row < self.records_table.rowCount():
                self.records_table.setRowHidden(row, not expanding)
        button.setText("−" if expanding else "+")

    def open_selected_record(self, item):
        """Double-click a Records row to load that recording in the dashboard."""
        row = item.row()
        last_item = self.records_table.item(row, 1)
        if last_item is None:
            return

        file_path = last_item.data(Qt.UserRole)
        session_id = last_item.data(Qt.UserRole + 1)
        parent_session_id = last_item.data(Qt.UserRole + 2)
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
            # The chart's loading overlay belongs to the dashboard.  Keeping
            # this dialog visible here used to cover that overlay, making the
            # load look as if it were happening silently in the background.
            self.hide()
            QApplication.processEvents()
            if parent.load_psg_data_from_path(file_path):
                # Tell the chart which saved session this is, so a later
                # Re-analyze -> "New report" save nests under the same root
                # instead of starting an unrelated new one.
                monitor_chart = getattr(parent, 'monitor_chart', None)
                if monitor_chart is not None and hasattr(monitor_chart, 'set_current_session') and session_id is not None:
                    monitor_chart.set_current_session(session_id, parent_session_id)
                self.accept()
            else:
                # Let the user choose another record when loading fails.
                self.show()
                self.raise_()
                self.activateWindow()
        else:
            QMessageBox.warning(self, "Not Available", "The dashboard cannot load this recording.")

    def load_patients_from_database(self):
        """Load patients from the database."""
        patients = self.db_manager.get_all_patients()

        self.patients_table.setRowCount(len(patients))
        for row, patient in enumerate(patients):
            self.patients_table.setItem(row, 0, QTableWidgetItem(patient['last_name'] or ""))
            self.patients_table.setItem(row, 1, QTableWidgetItem(patient['first_name'] or ""))
            self.patients_table.setItem(row, 2, QTableWidgetItem(patient['dob'] or ""))
            self.patients_table.setRowHeight(row, 40)
            # Store the patient ID in the row for later retrieval
            self.patients_table.item(row, 0).setData(Qt.UserRole, patient['id'])
            # Each row gets its own Edit button
            self.patients_table.setCellWidget(row, 3, self.create_edit_button())

        # Clear the Records table for now
        self.records_table.setRowCount(0)
        self.reports_table.setRowCount(0)

        # Keep whichever patient was selected before highlighted, so
        # reopening the Patient Database - which recreates this whole
        # dialog - doesn't leave you hunting for who you were looking at.
        self._restore_last_selected_patient_row()

    def _restore_last_selected_patient_row(self):
        """Re-select and re-highlight the last-selected patient's row.

        The "last selected" id lives on the parent (main dashboard) window,
        not on self, because self (this DatabaseWindow) is destroyed and
        rebuilt from scratch each time the dialog is closed and reopened -
        see on_patient_selection_changed() where it's saved, and
        dashboard.py's open_database() for why a fresh instance happens so
        often (e.g. right after loading a recording via double-click).
        """
        parent = self.parent()
        last_patient_id = getattr(parent, "_last_selected_database_patient_id", None) if parent else None
        if last_patient_id is None:
            return

        for row in range(self.patients_table.rowCount()):
            if self.patients_table.isRowHidden(row):
                continue
            name_item = self.patients_table.item(row, 0)
            if name_item is not None and name_item.data(Qt.UserRole) == last_patient_id:
                self.patients_table.selectRow(row)
                self.patients_table.setCurrentCell(row, 0)
                self.on_patient_selection_changed()
                break

    def create_edit_button(self):
        """Create an Edit button centred inside its table cell."""
        cell_container = QWidget()
        cell_container.setStyleSheet("background: transparent;")
        cell_layout = QHBoxLayout(cell_container)
        cell_layout.setContentsMargins(0, 0, 0, 0)
        cell_layout.setSpacing(0)

        button = StrictClickButton("Edit")
        button.setProperty("patientEditButton", True)
        button.installEventFilter(self)
        button.setCursor(Qt.PointingHandCursor)
        button.setFixedSize(90, 26)
        button.setStyleSheet("""
            QPushButton {
                background-color: #f8fbfd;
                color: #1e3a5f;
                border-top: 1px solid #3498db;
                border-right: 1px solid #3498db;
                border-bottom: 1px solid #3498db;
                border-left: 1px solid #3498db;
                border-radius: 4px;
                padding: 0px 10px;
                font-weight: 700;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e3f2fd;
                border-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #d6eaf8;
            }
        """)
        cell_layout.addWidget(button, 0, Qt.AlignCenter)

        # Resolve the row from the cell container at click time so sorting does
        # not leave a captured row number pointing at a different patient.
        button.clicked.connect(
            lambda checked=False, container=cell_container: self.handle_edit_patient(container)
        )
        return cell_container

    def _set_patient_hover_row(self, row):
        """Highlight one patient row, excluding its Edit-button column."""
        row = int(row) if row is not None else -1
        if row == self._patient_hover_row:
            return

        previous_row = self._patient_hover_row
        self._patient_hover_row = row

        if 0 <= previous_row < self.patients_table.rowCount():
            for column in range(3):
                item = self.patients_table.item(previous_row, column)
                if item is not None:
                    item.setBackground(QBrush())

        if 0 <= row < self.patients_table.rowCount():
            hover_brush = QBrush(QColor("#edf7fe"))
            for column in range(3):
                item = self.patients_table.item(row, column)
                if item is not None:
                    item.setBackground(hover_brush)

        self.patients_table.viewport().update()

    def _set_table_hover_row(
        self,
        table,
        row,
        row_attribute,
        backgrounds_attribute,
        excluded_columns=(),
    ):
        """Highlight a complete table row while preserving its base colours."""
        row = int(row) if row is not None else -1
        previous_row = getattr(self, row_attribute)
        if row == previous_row:
            return

        previous_backgrounds = getattr(self, backgrounds_attribute)
        if 0 <= previous_row < table.rowCount():
            for column, background in previous_backgrounds.items():
                item = table.item(previous_row, column)
                if item is not None:
                    item.setBackground(background)

        setattr(self, row_attribute, row)
        setattr(self, backgrounds_attribute, {})

        if 0 <= row < table.rowCount():
            excluded = set(excluded_columns)
            saved_backgrounds = {}
            hover_brush = QBrush(QColor("#edf7fe"))
            for column in range(table.columnCount()):
                if column in excluded:
                    continue
                item = table.item(row, column)
                if item is not None:
                    saved_backgrounds[column] = QBrush(item.background())
                    item.setBackground(hover_brush)
            setattr(self, backgrounds_attribute, saved_backgrounds)

        table.viewport().update()

    def _set_record_hover_row(self, row):
        """Highlight a Records row except its +/- action column."""
        self._set_table_hover_row(
            self.records_table,
            row,
            "_record_hover_row",
            "_record_hover_backgrounds",
            excluded_columns=(0,),
        )

    def _set_report_hover_row(self, row):
        """Highlight the complete Reports row."""
        self._set_table_hover_row(
            self.reports_table,
            row,
            "_report_hover_row",
            "_report_hover_backgrounds",
        )

    def eventFilter(self, watched, event):
        """Drive full-row hover while keeping action buttons independent."""
        patients_table = getattr(self, "patients_table", None)
        if patients_table is not None:
            if watched is patients_table.viewport():
                if event.type() == QEvent.MouseMove:
                    index = patients_table.indexAt(event.pos())
                    hover_row = index.row() if index.isValid() and index.column() < 3 else -1
                    self._set_patient_hover_row(hover_row)
                elif event.type() == QEvent.Leave:
                    self._set_patient_hover_row(-1)
            elif (
                event.type() == QEvent.Enter
                and bool(watched.property("patientEditButton"))
            ):
                self._set_patient_hover_row(-1)

        records_table = getattr(self, "records_table", None)
        if records_table is not None:
            if watched is records_table.viewport():
                if event.type() == QEvent.MouseMove:
                    index = records_table.indexAt(event.pos())
                    hover_row = index.row() if index.isValid() and index.column() > 0 else -1
                    self._set_record_hover_row(hover_row)
                elif event.type() == QEvent.Leave:
                    self._set_record_hover_row(-1)
            elif (
                event.type() == QEvent.Enter
                and bool(watched.property("recordExpandButton"))
            ):
                self._set_record_hover_row(-1)

        reports_table = getattr(self, "reports_table", None)
        if reports_table is not None and watched is reports_table.viewport():
            if event.type() == QEvent.MouseMove:
                index = reports_table.indexAt(event.pos())
                self._set_report_hover_row(index.row() if index.isValid() else -1)
            elif event.type() == QEvent.Leave:
                self._set_report_hover_row(-1)

        return super().eventFilter(watched, event)

    def verify_edit_password(self, action="editing"):
        """Ask for the password before a protected action.

        `action` only changes the wording, e.g. "editing" or
        "deleting this patient". Returns True only if the password matches.
        """
        password_dialog = QInputDialog(self)
        password_dialog.setWindowFlags(
            password_dialog.windowFlags() & ~Qt.WindowContextHelpButtonHint
        )
        password_dialog.setWindowTitle("Password Required")
        password_dialog.setInputMode(QInputDialog.TextInput)
        password_dialog.setLabelText(f"Please enter the password before {action}:")
        password_dialog.setTextEchoMode(QLineEdit.Password)
        password_dialog.setOkButtonText("OK")
        password_dialog.setCancelButtonText("Cancel")
        password_dialog.setMinimumWidth(360)

        button_box = password_dialog.findChild(QDialogButtonBox)
        if button_box is not None:
            ok_button = button_box.button(QDialogButtonBox.Ok)
            cancel_button = button_box.button(QDialogButtonBox.Cancel)
            if ok_button is not None:
                ok_button.setMinimumSize(76, 30)
                ok_button.setStyleSheet("""
                    QPushButton {
                        background-color: #2563eb;
                        color: white;
                        border: 1px solid #1d4ed8;
                        border-radius: 5px;
                        padding: 5px 14px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background-color: #1d4ed8;
                        border-color: #1e40af;
                    }
                    QPushButton:pressed {
                        background-color: #1e3a8a;
                    }
                """)
            if cancel_button is not None:
                cancel_button.setMinimumSize(76, 30)
                cancel_button.setStyleSheet("""
                    QPushButton {
                        background-color: #ef4444;
                        color: white;
                        border: 1px solid #dc2626;
                        border-radius: 5px;
                        padding: 5px 14px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background-color: #dc2626;
                        border-color: #b91c1c;
                    }
                    QPushButton:pressed {
                        background-color: #991b1b;
                    }
                """)

        if password_dialog.exec_() != QDialog.Accepted:
            return False
        password = password_dialog.textValue()

        entered_hash = hashlib.sha256((password or "").encode("utf-8")).hexdigest()
        if entered_hash != EDIT_PASSWORD_HASH:
            QMessageBox.warning(
                self,
                "Wrong Password",
                "The password is incorrect. Cannot continue.",
            )
            return False

        return True

    def _count_patient_data(self, patient_db_id):
        """How many recordings and reports are attached to this patient."""
        session_count = 0
        report_count = 0

        try:
            patient = self.db_manager.get_patient_by_id(patient_db_id)
            if patient:
                sessions = list_sessions(
                    patient_id=(patient.get('patient_id') or None),
                    patient_db_id=patient.get('id'),
                )
                session_count = len(sessions or [])
        except Exception as error:
            print(f"Could not count sessions for patient {patient_db_id}: {error}")

        try:
            reports = self.db_manager.get_patient_reports(patient_db_id)
            report_count = len(reports or [])
        except Exception as error:
            print(f"Could not count reports for patient {patient_db_id}: {error}")

        return session_count, report_count

    def _clear_dashboard_if_showing(self, deleted_patient_db_id):
        """Clear the dashboard if it is still showing the patient we deleted."""
        parent = self.parent()
        if parent is None:
            return

        if getattr(parent, "_last_selected_database_patient_id", None) == deleted_patient_db_id:
            parent._last_selected_database_patient_id = None

        if getattr(parent, "current_patient_db_id", None) == deleted_patient_db_id:
            if hasattr(parent, "clear_current_patient"):
                parent.clear_current_patient()

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
                pass
                
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
            msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
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
            pass
        else:
            pass
            
    def _get_selected_patient_rows(self):
        """Return visible patient rows selected for a delete operation."""
        return sorted({
            item.row()
            for item in self.patients_table.selectedItems()
            if not self.patients_table.isRowHidden(item.row())
        })

    @staticmethod
    def _get_selected_rows(table):
        """Return selected visible rows from a database table."""
        return sorted({
            item.row()
            for item in table.selectedItems()
            if not table.isRowHidden(item.row())
        })

    @staticmethod
    def _row_db_id(table, row):
        """Return the DB id (Qt.UserRole + 1) stored on any cell of this row."""
        for col in range(table.columnCount()):
            item = table.item(row, col)
            if item is None:
                continue
            value = item.data(Qt.UserRole + 1)
            if value is not None:
                return value
        return None

    def _delete_selected_records_or_reports(self):
        """Delete only explicitly selected Records or Reports rows."""
        record_rows = self._get_selected_rows(self.records_table)
        report_rows = self._get_selected_rows(self.reports_table)

        if not record_rows and not report_rows:
            return False

        if record_rows and report_rows:
            if self._last_child_table is self.reports_table:
                record_rows = []
            else:
                report_rows = []

        is_records = bool(record_rows)
        table = self.records_table if is_records else self.reports_table
        rows = record_rows if is_records else report_rows
        item_label = "record" if is_records else "report"
        item_ids = []
        for row in rows:
            db_id = self._row_db_id(table, row)
            if db_id is not None:
                item_ids.append(db_id)

        pass

        if not item_ids:
            QMessageBox.warning(
                self,
                "Cannot Delete",
                f"The selected {item_label} row has no database id.\n"
                "Please click the patient again, reselect the row and retry.",
            )
            table.clearSelection()
            return True

        count_label = f"{len(item_ids)} {item_label}{'' if len(item_ids) == 1 else 's'}"
        if not self.verify_edit_password(f"deleting the selected {item_label}"):
            return True

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the selected {count_label}?\n\nThe patient will not be deleted.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            pass
            return True

        success = (
            self.db_manager.delete_sessions(item_ids)
            if is_records
            else self.db_manager.delete_reports(item_ids)
        )
        if not success:
            QMessageBox.critical(
                self,
                "Delete Failed",
                f"Could not delete the selected {count_label}. Check the console for details.",
            )
            return True

        pass

        patient = self.get_selected_patient()
        if patient:
            if is_records:
                self.load_records_for_patient(patient)
            else:
                self.load_reports_from_database(patient)
        else:
            for row in sorted(rows, reverse=True):
                table.removeRow(row)
            if is_records:
                self._record_group_rows = {}

        table.clearSelection()
        self._last_child_table = None
        return True

    def handle_delete(self):
        """Delete all patients selected with Shift (in one DB transaction)."""
        pass

        # A selected Record/Report row takes priority over the still-highlighted
        # patient row. This ensures Delete removes only the chosen child item.
        if self._delete_selected_records_or_reports():
            return

        rows = self._get_selected_patient_rows()
        if not rows:
            msg_box = QMessageBox(self)
            msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
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
            
        patients = []
        for row in rows:
            id_item = self.patients_table.item(row, 0)
            if id_item is None:
                continue
            patients.append({
                "id": id_item.data(Qt.UserRole),
                "name": f"{self.patients_table.item(row, 0).text()} "
                        f"{self.patients_table.item(row, 1).text()}".strip(),
            })
        if not patients:
            return

        # Deleting a patient is far more destructive than editing one, so it
        # asks for the same password the Edit button already asks for.
        action_text = "deleting this patient" if len(patients) == 1 else "deleting these patients"
        if not self.verify_edit_password(action_text):
            return

        if len(patients) == 1:
            confirm_lines = [f'Are you sure you want to delete patient "{patients[0]["name"]}"?']
        else:
            names = "\n".join(f'  • {patient["name"]}' for patient in patients)
            confirm_lines = [
                f"Are you sure you want to delete these {len(patients)} patients?",
                "",
                names,
            ]
        confirm_lines.append("")
        confirm_lines.append("This cannot be undone.")

        # Confirm deletion
        msg_box = QMessageBox(self)
        msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        msg_box.setWindowTitle("Confirm Delete")
        msg_box.setText("\n".join(confirm_lines))
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
            yes_button.setAutoDefault(True)
            yes_button.setDefault(True)
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
            no_button.setDefault(False)
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
            patient_ids = [patient["id"] for patient in patients]
            success = self.db_manager.delete_patients(patient_ids)
            if success:
                pass
                for patient_db_id in patient_ids:
                    self._clear_dashboard_if_showing(patient_db_id)
                self.load_patients_from_database()
            else:
                print("Failed to delete patient")
        else:
            pass
    
    def load_reports_from_database(self, patient=None):
        """Load reports. If a patient is provided, show only that patient's reports."""
        self._set_report_hover_row(-1)
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
            print(f"Internal PDF viewer failed: {error}")
            QMessageBox.critical(
                self,
                "Cannot Open Report",
                f"The report could not be displayed inside the application.\n\n{error}",
            )
