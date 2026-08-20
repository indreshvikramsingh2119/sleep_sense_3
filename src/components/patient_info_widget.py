"""
Patient Information Widget - Patient Info Panel Component
"""

import os
import subprocess
import sys
import json
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QFileDialog, QListWidget, QListWidgetItem, QScrollArea,
    QMessageBox, QSizePolicy, QComboBox, QStyle
)
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QPainter, QPixmap, QColor
from PyQt5.QtGui import QFont
from src.utils.db_utils import get_db_path
try:
    from src.utils.db_utils import get_visible_raw_csv_dir
except ImportError:
    get_visible_raw_csv_dir = None


class PatientInfoWidget(QWidget):
    """Patient Information Panel"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.saved_raw_files = []  # list[dict]: {timestamp, path, filename}
        self.all_detected_events = []
        self.monitor_chart = None  # Reference to main chart for save functionality
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        # Single panel (Raw Data tab removed as requested)
        info_tab = self.create_info_tab()
        main_layout.addWidget(info_tab, 1)
        
    def create_info_tab(self):
        """Create patient information tab with professional container"""
        widget = QWidget()
        widget.setObjectName("infoTab")
        widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 4, 8, 12)
        layout.setSpacing(16)
        
        # Main Professional Container
        main_container = QFrame()
        main_container.setObjectName("patientMainContainer")
        main_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        main_container.setStyleSheet("""
            QFrame#patientMainContainer {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.45 #f8fafc,
                    stop: 0.55 #f1f5f9,
                    stop: 1 #e2e8f0
                );
                border: 2px solid #cbd5e1;
                border-radius: 12px;
                padding: 2px;
                margin: 0px;
            }
            QFrame#patientMainContainer:hover {
                border: 2px solid #3b82f6;
            }
        """)
        
        container_layout = QVBoxLayout(main_container)
        container_layout.setContentsMargins(12, 12, 12, 12)
        container_layout.setSpacing(12)
        
        # Patient Avatar and Name Section
        avatar_section = self.create_avatar_section()
        container_layout.addWidget(avatar_section)
        
        # Patient Details Section Container
        details_container = QFrame()
        details_container.setObjectName("detailsContainer")
        details_container.setStyleSheet("""
            QFrame#detailsContainer {
                background-color: rgba(255, 255, 255, 0.9);
                border: 2px solid #cbd5e1;
                border-radius: 10px;
                padding: 8px;
                margin: 4px;
            }
            QFrame#detailsContainer:hover {
                border: 2px solid #94a3b8;
                background-color: rgba(255, 255, 255, 1.0);
            }
        """)
        
        details_layout = QVBoxLayout(details_container)
        details_layout.setContentsMargins(8, 8, 8, 8)
        details_layout.setSpacing(10) # Adjusted spacing between info cards
        
        # Action Buttons (Save and Upload)
        action_buttons = self.create_action_buttons()
        details_layout.addWidget(action_buttons)
        
        container_layout.addWidget(details_container)

        # Raw Data File Section Container
        raw_container = QFrame()
        raw_container.setObjectName("rawDataContainer")
        raw_container.setStyleSheet("""
            QFrame#rawDataContainer {
                background-color: rgba(255, 255, 255, 0.9);
                border: 2px solid #cbd5e1;
                border-radius: 10px;
                padding: 8px;
                margin: 4px;
            }
            QFrame#rawDataContainer:hover {
                border: 2px solid #94a3b8;
                background-color: rgba(255, 255, 255, 1.0);
            }
        """)
        
        raw_container_layout = QVBoxLayout(raw_container)
        raw_container_layout.setContentsMargins(8, 8, 8, 8)
        raw_container_layout.setSpacing(8)
        
        # Raw Data File Section 
        raw_section = self.create_raw_data_section()
        raw_container_layout.addWidget(raw_section)
        
        container_layout.addWidget(raw_container)

        events_container = QFrame()
        events_container.setObjectName("autoEventsContainer")
        events_container.setStyleSheet("""
            QFrame#autoEventsContainer {
                background-color: rgba(255, 255, 255, 0.9);
                border: 2px solid #cbd5e1;
                border-radius: 10px;
                padding: 8px;
                margin: 4px;
            }
            QFrame#autoEventsContainer:hover {
                border: 2px solid #94a3b8;
                background-color: rgba(255, 255, 255, 1.0);
            }
        """)
        events_layout = QVBoxLayout(events_container)
        events_layout.setContentsMargins(8, 8, 8, 8)
        events_layout.setSpacing(8)
        events_layout.addWidget(self.create_detected_events_section())
        container_layout.addWidget(events_container)
        container_layout.addStretch()
        
        scroll = QScrollArea()
        scroll.setObjectName("patientInfoScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setWidget(main_container)
        layout.addWidget(scroll, 1)
        
        return widget

    def create_action_buttons(self):
        """Create save and upload action buttons"""
        frame = QFrame()
        frame.setObjectName("actionButtonsSection")
        frame.setMinimumHeight(110)  # Increased container height
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(8, 8, 8, 8)  # Added margins for clear visibility
        frame_layout.setSpacing(14)  # Increased spacing

        action_button_style = """
            QPushButton#actionButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #3b82f6,
                    stop: 0.5 #2563eb,
                    stop: 1 #1d4ed8
                );
                border: 1px solid #1e40af;
                border-radius: 8px;
                color: white;
                font-size: 14px;
                font-weight: 600;
                padding: 8px 16px;
            }
            QPushButton#actionButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #60a5fa,
                    stop: 0.5 #3b82f6,
                    stop: 1 #2563eb
                );
                border: 1px solid #1d4ed8;
            }
            QPushButton#actionButton:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #1d4ed8,
                    stop: 0.5 #1e40af,
                    stop: 1 #1e3a8a
                );
            }
            QPushButton#actionButton:disabled {
                background: #cbd5e1;
                border: 1px solid #94a3b8;
                color: #64748b;
            }
        """

        # Save Button
        save_btn = QPushButton(" Save Data")
        save_btn.setObjectName("actionButton")
        save_btn.setMinimumHeight(46)  # Increased button height
        save_btn.setStyleSheet(action_button_style)
        save_btn.clicked.connect(self.save_data)
        frame_layout.addWidget(save_btn)

        # Upload Button 
        upload_btn = QPushButton(" Upload Data")
        upload_btn.setObjectName("actionButton")
        upload_btn.setMinimumHeight(46)  # Increased button height
        upload_btn.setStyleSheet(action_button_style)
        upload_btn.clicked.connect(self.upload_data)
        frame_layout.addWidget(upload_btn)

        return frame

    def save_data(self):
        """Handle save data action - will be connected to main chart"""
        if self.monitor_chart:
            self.monitor_chart.confirm_and_save_raw_data()
        else:
            print("Monitor chart not connected")

    def upload_data(self):
        """Handle upload data action"""
        if not self.monitor_chart or not getattr(self.monitor_chart, "patient_id", None) or self.monitor_chart.patient_id in ("", "--------", None):
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("No Patient Selected")
            msg_box.setText("Please select a patient from the database before uploading data.")
            msg_box.setIconPixmap(self._database_icon_pixmap())
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

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Data Files to Upload",
            "",
            "Data Files (*.csv *.edf *.txt *.json);;All Files (*)"
        )
        if files:
            if not self.monitor_chart:
                QMessageBox.warning(self, "Chart Not Available", "Monitor chart not connected.")
                return

            selected_file = files[0]
            lower_name = selected_file.lower()
            if not lower_name.endswith((".csv", ".txt")):
                QMessageBox.information(
                    self,
                    "Unsupported File",
                    "Only CSV/TXT uploads are currently supported for graph plotting.",
                )
                return

            if getattr(self.monitor_chart, "is_playing", False):
                self.monitor_chart.pause_playback()
            self.monitor_chart.skip_next_auto_playback = True

            time_data, signals, jumped = self.monitor_chart.load_psg_data_and_detect(selected_file)
            if len(time_data) == 0 or not signals:
                QMessageBox.warning(
                    self,
                    "Load Failed",
                    f"The selected file could not be loaded:\n{selected_file}",
                )
                return

            detected_events = []
            if getattr(self.monitor_chart, "auto_rule_ai_result", None):
                detected_events = list(self.monitor_chart.auto_rule_ai_result.get("events", []))
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Upload Complete")
            msg_box.setTextFormat(Qt.RichText)
            msg_box.setIconPixmap(self.style().standardIcon(QStyle.SP_DialogApplyButton).pixmap(48, 48))
            msg_box.setText(
                '<span style="color:#16a34a; font-weight:700;">Data loaded and graphs updated!</span><br><br>'
                f'<span style="color:#111827; font-weight:700;">File</span>'
                f'<span style="color:#6b7280;"> : {os.path.basename(selected_file)}</span><br>'
                + (
                    f'<span style="color:#111827; font-weight:700;">Auto-detection</span>'
                    f'<span style="color:#6b7280;"> : {len(detected_events)} events found.</span><br>'
                    if detected_events
                    else '<span style="color:#111827; font-weight:700;">Auto-detection</span>'
                    '<span style="color:#6b7280;"> : No auto-detected events found.</span><br>'
                )
                + (
                    '<span style="color:#111827; font-weight:700;">Jump</span>'
                    '<span style="color:#6b7280;"> : Jumped to the first detected event.</span>'
                    if jumped
                    else ''
                )
            )
            msg_box.setStandardButtons(QMessageBox.Ok)
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

    def create_raw_data_section(self):
        """Inline raw-data file list shown under patient details."""
        frame = QFrame()
        frame.setObjectName("rawDataSection")
        frame.setMinimumHeight(170)  # Keep the card compact so the dashboard does not grow
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(12, 12, 12, 12)  # Increased margins for more space
        frame_layout.setSpacing(16)  # Further increased spacing

        header = QHBoxLayout()
        title = QLabel("Save file List")
        title.setStyleSheet("font-size: 14px; font-weight: 700; color: #111827;")
        header.addWidget(title)
        header.addStretch()

        self.raw_count_label = QLabel("0")
        self.raw_count_label.setVisible(False)
        self.raw_count_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #2563eb;")
        header.addWidget(self.raw_count_label)
        frame_layout.addLayout(header)

        self.raw_hint_label = QLabel("Press Save -> Yes to copy the loaded raw CSV and store patient/time in DB.")
        self.raw_hint_label.setStyleSheet("font-size: 12px; color: #6b7280;")
        self.raw_hint_label.setWordWrap(True)
        frame_layout.addWidget(self.raw_hint_label)

        self.raw_file_list = QListWidget()
        self.raw_file_list.setObjectName("Saved file List")
        self.raw_file_list.setMinimumHeight(0)
        self.raw_file_list.setMaximumHeight(140)
        self.raw_file_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.raw_file_list.setVisible(False)
        # Reduce item spacing and padding to minimize empty space
        self.raw_file_list.setStyleSheet("""
            QListWidget#Saved file List {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 4px;
                spacing: 2px;
            }
            QListWidget#Saved file List::item {
                background-color: white;
                border: 1px solid #e5e7eb;
                border-radius: 4px;
                padding: 6px 8px;
                margin: 1px;
                min-height: 24px;
            }
            QListWidget#Saved file List::item:selected {
                background-color: #3b82f6;
                color: white;
                border: 1px solid #2563eb;
            }
            QListWidget#Saved file List::item:hover {
                background-color: #f1f5f9;
                border: 1px solid #cbd5e1;
            }
        """)
        self.raw_file_list.itemClicked.connect(self.load_saved_raw_file)
        frame_layout.addWidget(self.raw_file_list)

        open_folder_btn = QPushButton(" Open Data Folder")
        open_folder_btn.setObjectName("actionButton")
        open_folder_btn.setMinimumHeight(42)
        open_folder_btn.setStyleSheet("""
            QPushButton#actionButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #3b82f6,
                    stop: 0.5 #2563eb,
                    stop: 1 #1d4ed8
                );
                border: 1px solid #1d4ed8;
                border-radius: 8px;
                color: #ffffff;
                font-size: 13px;
                font-weight: 700;
                padding: 8px 16px;
            }
            QPushButton#actionButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #60a5fa,
                    stop: 0.5 #3b82f6,
                    stop: 1 #2563eb
                );
                border: 1px solid #1d4ed8;
            }
            QPushButton#actionButton:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #1d4ed8,
                    stop: 0.5 #1e40af,
                    stop: 1 #1e3a8a
                );
            }
        """)
        open_folder_btn.clicked.connect(self.open_data_folder)
        frame_layout.addWidget(open_folder_btn)

        return frame

    def create_detected_events_section(self):
        """Auto detected apnea events list with jump support."""
        frame = QFrame()
        frame.setObjectName("detectedEventsSection")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(12, 12, 12, 12)
        frame_layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Detected Events")
        title.setStyleSheet("font-size: 14px; font-weight: 700; color: #111827;")
        header.addWidget(title)
        header.addStretch()

        self.detected_count_label = QLabel("0")
        self.detected_count_label.setVisible(False)
        self.detected_count_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #dc2626;")
        header.addWidget(self.detected_count_label)
        frame_layout.addLayout(header)

        self.detected_hint_label = QLabel("Upload data to populate automatic apnea events.")
        self.detected_hint_label.setStyleSheet("font-size: 12px; color: #6b7280;")
        self.detected_hint_label.setWordWrap(True)
        frame_layout.addWidget(self.detected_hint_label)

        self.detected_filter_dropdown = QComboBox()
        self.detected_filter_dropdown.addItems(["All", "HSA", "CSA", "OSA", "MSA"])
        self.detected_filter_dropdown.setVisible(False)
        self.detected_filter_dropdown.currentTextChanged.connect(self.apply_detected_events_filter)
        self.detected_filter_dropdown.setStyleSheet("""
            QComboBox {
                background-color: white;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 7px 10px;
                color: #111827;
                font-size: 12px;
            }
            QComboBox:hover {
                border: 1px solid #93c5fd;
            }
            QComboBox:focus {
                border: 1px solid #3b82f6;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
        """)
        frame_layout.addWidget(self.detected_filter_dropdown)

        self.detected_events_list = QListWidget()
        self.detected_events_list.setMinimumHeight(0)
        self.detected_events_list.setMaximumHeight(180)
        self.detected_events_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.detected_events_list.setVisible(False)
        self.detected_events_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.detected_events_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.detected_events_list.setWordWrap(True)
        self.detected_events_list.setTextElideMode(Qt.ElideNone)
        self.detected_events_list.itemClicked.connect(self.jump_to_detected_event)
        self.detected_events_list.setStyleSheet("""
            QListWidget {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 4px;
                spacing: 2px;
            }
            QListWidget::item {
                background-color: white;
                border: 1px solid #e5e7eb;
                border-radius: 4px;
                padding: 6px 8px;
                margin: 1px;
                min-height: 26px;
            }
            QListWidget::item:selected {
                background-color: #eff6ff;
                color: #1e40af;
                border: 1px solid #93c5fd;
            }
            QListWidget::item:hover {
                background-color: #f1f5f9;
                border: 1px solid #cbd5e1;
            }
        """)
        frame_layout.addWidget(self.detected_events_list)
        return frame

    def add_saved_raw_file(self, file_path: str, timestamp_iso: str):
        """Append a saved raw-data file to the inline list UI."""
        filename = os.path.basename(file_path)
        self.saved_raw_files.insert(0, {"timestamp": timestamp_iso, "path": file_path, "filename": filename})

        raw_count = len(self.saved_raw_files)
        self.raw_count_label.setText(str(raw_count))
        self.raw_count_label.setVisible(raw_count > 0)
        self.raw_hint_label.setVisible(raw_count == 0)
        self.raw_file_list.setVisible(raw_count > 0)

        # Render newest on top
        item_text = f"{filename}\n{timestamp_iso}"
        item = QListWidgetItem(item_text)
        item.setData(Qt.UserRole, file_path)
        item.setToolTip(file_path)
        self.raw_file_list.insertItem(0, item)

    def _get_raw_data_dir(self):
        """Raw CSV folder dhundo: helper -> last saved file -> DB folder."""
        if get_visible_raw_csv_dir is not None:
            try:
                folder = get_visible_raw_csv_dir()
                if folder and os.path.isdir(folder):
                    return folder
            except Exception:
                pass

        if self.saved_raw_files:
            folder = os.path.dirname(self.saved_raw_files[0]["path"])
            if os.path.isdir(folder):
                return folder

        return os.path.dirname(get_db_path())

    def open_data_folder(self):
        """
        Open the visible raw-data folder in a picker and load the selected file.

        Explorer/Finder me file click karne se graph auto-plot nahi hota, isliye
        yahan app-level picker se file choose karke direct plot kiya jata hai.
        """
        folder = self._get_raw_data_dir()
        selected_file, _ = QFileDialog.getOpenFileName(
            self,
            "Select Saved Raw Data to Plot",
            folder,
            "Data Files (*.csv *.txt);;All Files (*)"
        )
        if not selected_file:
            return

        lower_name = selected_file.lower()
        if not lower_name.endswith((".csv", ".txt")):
            QMessageBox.information(
                self,
                "Unsupported File",
                "Only CSV/TXT saved raw data can be plotted.",
            )
            return

        temp_item = QListWidgetItem(os.path.basename(selected_file))
        temp_item.setData(Qt.UserRole, selected_file)
        self.load_saved_raw_file(temp_item)

    def load_saved_raw_file(self, item):
        """Reload a saved raw CSV/TXT directly from the visible mirror folder."""
        if not self.monitor_chart:
            QMessageBox.warning(self, "Chart Not Available", "Monitor chart not connected.")
            return

        selected_file = item.data(Qt.UserRole) or item.toolTip()
        if not selected_file or not os.path.exists(selected_file):
            QMessageBox.warning(
                self,
                "File Missing",
                "The selected saved raw file could not be found.",
            )
            return

        if getattr(self.monitor_chart, "is_playing", False):
            self.monitor_chart.pause_playback()
        self.monitor_chart.skip_next_auto_playback = True

        time_data, signals, jumped = self.monitor_chart.load_psg_data_and_detect(selected_file)
        if len(time_data) == 0 or not signals:
            QMessageBox.warning(
                self,
                "Load Failed",
                f"The selected saved file could not be loaded:\n{selected_file}",
            )
            return

        detected_events = []
        if getattr(self.monitor_chart, "auto_rule_ai_result", None):
            detected_events = list(self.monitor_chart.auto_rule_ai_result.get("events", []))

        QMessageBox.information(
            self,
            "Saved Data Loaded",
            (
                f"Data loaded and graphs updated:\n{os.path.basename(selected_file)}"
                + (
                    f"\nAuto-detection complete: {len(detected_events)} events found."
                    if detected_events
                    else "\nNo auto-detected events found."
                )
                + ("\nJumped to the first detected event." if jumped else "")
            ),
        )

    def _database_icon_pixmap(self):
        """Create a blue database-style icon for warning dialogs."""
        pixmap = QPixmap(48, 48)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#3b82f6"))
        painter.drawEllipse(6, 6, 36, 36)

        painter.setBrush(QColor("white"))
        painter.drawEllipse(14, 12, 20, 8)
        painter.drawRect(14, 16, 20, 16)
        painter.drawEllipse(14, 28, 20, 8)

        painter.setBrush(QColor("#3b82f6"))
        painter.drawEllipse(18, 15, 12, 3)
        painter.drawEllipse(18, 23, 12, 3)
        painter.drawEllipse(18, 31, 12, 3)
        painter.end()
        return pixmap

    def update_detected_events_list(self, events):
        """Render automatic detected events and make them clickable."""
        self.all_detected_events = [
            event
            for event in list(events or [])
            if str(event.get("final_label") or event.get("rule_label") or "REVIEW")
            not in {"REVIEW", "APNEA_REVIEW", "NO_EVENT"}
        ]

        if not self.all_detected_events:
            self.detected_count_label.setText("0")
            self.detected_count_label.setVisible(False)
            self.detected_hint_label.setVisible(True)
            self.detected_filter_dropdown.setVisible(False)
            self.detected_events_list.setVisible(False)
            self.detected_events_list.clear()
            self.detected_events_list.setFixedHeight(0)
            self.detected_hint_label.setText("Upload data to populate automatic apnea events.")
            return

        self.detected_hint_label.setText("Click an event to jump the graph to that time.")
        self.detected_hint_label.setVisible(False)
        self.detected_filter_dropdown.setVisible(True)
        self.apply_detected_events_filter()

    def apply_detected_events_filter(self):
        """Filter detected apnea events by selected label."""
        selected_label = self.detected_filter_dropdown.currentText().upper()
        if selected_label == "ALL":
            filtered_events = list(self.all_detected_events)
        else:
            filtered_events = [
                event
                for event in self.all_detected_events
                if str(event.get("final_label") or event.get("rule_label") or "").upper() == selected_label
            ]

        self.detected_count_label.setText(str(len(filtered_events)))
        self.detected_count_label.setVisible(len(filtered_events) > 0)
        self.detected_events_list.setVisible(len(filtered_events) > 0)
        self.detected_events_list.clear()

        if not filtered_events:
            self.detected_events_list.setFixedHeight(0)
            self.detected_hint_label.setText(f"No {selected_label} events found.")
            self.detected_hint_label.setVisible(True)
            return

        self.detected_hint_label.setText("Click an event to jump the graph to that time.")
        self.detected_hint_label.setVisible(False)
        for event in sorted(filtered_events, key=lambda row: float(row.get("start_sec", 0.0))):
            start_text = self._format_timestamp(float(event["start_sec"]))
            end_text = self._format_timestamp(float(event["end_sec"]))
            label = str(event.get("final_label") or event.get("rule_label") or "REVIEW")
            duration = float(event.get("duration_sec", 0.0))
            item = QListWidgetItem(f"{start_text} - {end_text}\n{label} | {duration:.1f}s")
            item.setData(Qt.UserRole, event)
            self.detected_events_list.addItem(item)

        self._resize_detected_events_list()

    def _resize_detected_events_list(self):
        """Expand the list until a practical cap, then let the list scroll internally."""
        item_count = self.detected_events_list.count()
        if item_count == 0:
            self.detected_events_list.setFixedHeight(0)
            self.detected_events_list.setMaximumHeight(180)
            return

        row_height = self.detected_events_list.sizeHintForRow(0)
        if row_height <= 0:
            row_height = 44
        frame_height = (self.detected_events_list.frameWidth() * 2) + 8
        total_height = (row_height * item_count) + frame_height
        max_height = 180
        capped_height = min(total_height, max_height)
        self.detected_events_list.setMaximumHeight(max_height)
        self.detected_events_list.setFixedHeight(capped_height)

    def jump_to_detected_event(self, item):
        """Jump monitor chart to the selected detected event."""
        if not self.monitor_chart:
            return
        event_data = item.data(Qt.UserRole)
        if event_data:
            self.monitor_chart.focus_on_event(event_data)

    def _format_timestamp(self, time_seconds: float) -> str:
        hours = int(time_seconds // 3600)
        minutes = int((time_seconds % 3600) // 60)
        seconds = int(time_seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def create_summary_section(self):
        """Stub summary section to prevent runtime errors if called."""
        frame = QFrame()
        frame.setObjectName("summarySection")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel("Weekly Summary")
        label.setStyleSheet("font-size: 12px; color: #6b7280;")
        layout.addWidget(label)
        return frame
    
    def create_avatar_section(self):
        """Create patient avatar and name section"""
        frame = QFrame()
        frame.setObjectName("")
        layout = QVBoxLayout(frame)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)
        
        # Avatar container with circular border
        avatar_container = QFrame()
        avatar_container.setFixedSize(90, 90)
        avatar_container.setStyleSheet("""
            QFrame {
                border: 2px solid #e5e7eb;
                border-radius: 45px;
            }
        """)
        
        avatar_layout = QVBoxLayout(avatar_container)
        avatar_layout.setContentsMargins(0, 0, 0, 0)
        
        # Avatar label (SJ for Sarah Johnson)
        avatar_label = QLabel("👤")
        avatar_label.setAlignment(Qt.AlignCenter)
        avatar_label.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                            stop:0 #2CA3FA, stop:1 #1E88E5);
                color: white;
                font-size: 28px;
                font-weight: bold;
                border-radius: 43px;
            }
        """)
        avatar_layout.addWidget(avatar_label)
        
        layout.addWidget(avatar_container, alignment=Qt.AlignCenter)
        
        # Patient Name
        self.patient_name_label = QLabel("No Patient Loaded")
        self.patient_name_label.setObjectName("patientName")
        self.patient_name_label.setAlignment(Qt.AlignCenter)
        self.patient_name_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #9ca3af;")
        layout.addWidget(self.patient_name_label)
        
        # Patient ID
        self.patient_id_label = QLabel("ID: --")
        self.patient_id_label.setObjectName("patientId")
        self.patient_id_label.setAlignment(Qt.AlignCenter)
        self.patient_id_label.setStyleSheet("font-size: 13px; color: #9ca3af; background: transparent; border: none;")
        layout.addWidget(self.patient_id_label)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setObjectName("separator")
        layout.addWidget(separator)
        
        return frame
    
    def create_info_card(self, icon, label_text, value_text, object_name):
        """Create an info card with icon, label, and value"""
        frame = QFrame()
        frame.setObjectName(object_name)
        frame.setMinimumHeight(80)  # Increased height from 60 to 80
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)
        
        # Icon container
        icon_frame = QFrame()
        icon_frame.setObjectName("iconBlue" if "Blue" in object_name else 
                                 "iconIndigo" if "Indigo" in object_name else
                                 "iconPurple" if "Purple" in object_name else "iconGreen")
        icon_frame.setFixedSize(42, 42)
        icon_layout = QVBoxLayout(icon_frame)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet("font-size: 18px; color: white;")
        icon_layout.addWidget(icon_label)
        layout.addWidget(icon_frame)
        
        # Text container
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        label = QLabel(label_text)
        label.setObjectName("infoLabel")
        label.setStyleSheet("font-size: 12px; color: #6b7280; font-weight: 500;")
        text_layout.addWidget(label)
        
        value = QLabel(value_text)
        value.setObjectName("infoValue")
        value.setStyleSheet("font-size: 15px; font-weight: bold; color: #111827;")
        text_layout.addWidget(value)
        
        layout.addLayout(text_layout)
        layout.addStretch()
        
        return frame
    
    def set_patient_data(self, patient_data):
        """Update patient information display with selected patient data"""
        if not patient_data:
            self.apply_empty_patient_state()
            return

        # Update patient name
        name_label = self.findChild(QLabel, "patientName")
        if name_label:
            full_name = f"{patient_data.get('first_name', '')} {patient_data.get('last_name', '')}"
            full_name = full_name.strip() or "No Patient Loaded"
            name_label.setText(full_name)
            name_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #111827;")
        
        # Update patient ID
        id_label = self.findChild(QLabel, "patientId")
        if id_label:
            id_text = patient_data.get('patient_id', '--')
            id_label.setText(f"ID: {id_text}")
            id_label.setStyleSheet("font-size: 13px; color: #6b7280; background: transparent; border: none;")

        print(f"Updated patient info: {patient_data}")

    def apply_empty_patient_state(self):
        """Show a clean placeholder state when no patient is loaded."""
        name_label = self.findChild(QLabel, "patientName")
        if name_label:
            name_label.setText("No Patient Loaded")
            name_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #9ca3af;")

        id_label = self.findChild(QLabel, "patientId")
        if id_label:
            id_label.setText("ID: --")
            id_label.setStyleSheet("font-size: 13px; color: #9ca3af; background: transparent; border: none;")
