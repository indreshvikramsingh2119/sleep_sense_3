"""
Patient Information Widget - Patient Info Panel Component
"""

import os
import json
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QFileDialog, QListWidget, QListWidgetItem,
    QMessageBox, QSizePolicy
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class PatientInfoWidget(QWidget):
    """Patient Information Panel"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.saved_raw_files = []  # list[dict]: {timestamp, path, filename}
        self.monitor_chart = None  # Reference to main chart for save functionality
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        # Single panel (Raw Data tab removed as requested)
        info_tab = self.create_info_tab()
        main_layout.addWidget(info_tab)
        
    def create_info_tab(self):
        """Create patient information tab with professional container"""
        widget = QWidget()
        widget.setObjectName("infoTab")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0) # Remove outer margins
        layout.setSpacing(0) # Control spacing within scroll area
        
        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff) # Disable horizontal scroll
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        scroll_content = QWidget()
        scroll_content.setObjectName("scrollContent")
        scroll_content.setContentsMargins(8, 16, 8, 16) # Reduced left margin for more left shift
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(16) # Adjusted spacing between sections
        
        # Main Professional Container
        main_container = QFrame()
        main_container.setObjectName("patientMainContainer")
        main_container.setMinimumHeight(1170)  
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
                padding: 4px;
                margin: 2px;
            }
            QFrame#patientMainContainer:hover {
                border: 2px solid #3b82f6;
                box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
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
        
        # Age/Gender Card
        age_card = self.create_info_card("", "Age / Gender", "-- / ---", "light blue")
        details_layout.addWidget(age_card)
        
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
        
        # Raw Data File Section (inline, under patient details)
        raw_section = self.create_raw_data_section()
        raw_container_layout.addWidget(raw_section)
        
        container_layout.addWidget(raw_container)
        
        container_layout.addStretch()
        scroll_layout.addWidget(main_container)
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        return widget

    def create_action_buttons(self):
        """Create save and upload action buttons"""
        frame = QFrame()
        frame.setObjectName("actionButtonsSection")
        frame.setMinimumHeight(100)  # Increased container height
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(8, 8, 8, 8)  # Added margins for clear visibility
        frame_layout.setSpacing(12)  # Increased spacing

        # Save Button
        save_btn = QPushButton(" Save Data")
        save_btn.setObjectName("actionButton")
        save_btn.setMinimumHeight(42)  # Increased button height
        save_btn.setStyleSheet("""
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
                font-size: 13px;
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
        """)
        save_btn.clicked.connect(self.save_data)
        frame_layout.addWidget(save_btn)

        # Upload Button 
        upload_btn = QPushButton(" Upload Data")
        upload_btn.setObjectName("actionButton")
        upload_btn.setMinimumHeight(42)  # Increased button height
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
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Data Files to Upload",
            "",
            "Data Files (*.csv *.edf *.txt *.json);;All Files (*)"
        )
        if files:
            print(f"Uploading files: {files}")

    def create_raw_data_section(self):
        """Inline raw-data file list shown under patient details."""
        frame = QFrame()
        frame.setObjectName("rawDataSection")
        frame.setMinimumHeight(250)  # Further increased container height
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # Changed to Expanding for more space
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(12, 12, 12, 12)  # Increased margins for more space
        frame_layout.setSpacing(16)  # Further increased spacing

        header = QHBoxLayout()
        title = QLabel("Save file List")
        title.setStyleSheet("font-weight: 700; color: #111827;")
        header.addWidget(title)
        header.addStretch()

        self.raw_count_label = QLabel("0")
        self.raw_count_label.setStyleSheet("font-weight: 700; color: #2563eb;")
        header.addWidget(self.raw_count_label)
        frame_layout.addLayout(header)

        self.raw_hint_label = QLabel("Press Save -> Yes to generate raw data with a timestamp.")
        self.raw_hint_label.setStyleSheet("font-size: 11px; color: #6b7280;")
        self.raw_hint_label.setWordWrap(True)
        frame_layout.addWidget(self.raw_hint_label)

        self.raw_file_list = QListWidget()
        self.raw_file_list.setObjectName("Saved file List")
        self.raw_file_list.setMinimumHeight(220)  # Increased list height for more items
        self.raw_file_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # Allow expansion
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
                bord
                er-radius: 4px;
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
        frame_layout.addWidget(self.raw_file_list)

        return frame

    def add_saved_raw_file(self, file_path: str, timestamp_iso: str):
        """Append a saved raw-data file to the inline list UI."""
        filename = os.path.basename(file_path)
        self.saved_raw_files.insert(0, {"timestamp": timestamp_iso, "path": file_path, "filename": filename})

        self.raw_count_label.setText(str(len(self.saved_raw_files)))
        self.raw_hint_label.setVisible(len(self.saved_raw_files) == 0)
        self.raw_file_list.setVisible(len(self.saved_raw_files) > 0)

        # Render newest on top
        item_text = f"{filename}\n{timestamp_iso}"
        item = QListWidgetItem(item_text)
        item.setToolTip(file_path)
        self.raw_file_list.insertItem(0, item)

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
        name_label = QLabel("Patient Name")
        name_label.setObjectName("patientName")
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #111827;")
        layout.addWidget(name_label)
        
        # Patient ID
        id_label = QLabel("ID: --------")
        id_label.setObjectName("patientId")
        id_label.setAlignment(Qt.AlignCenter)
        id_label.setStyleSheet("font-size: 12px; color: #6b7280; background: transparent; border: none;")
        layout.addWidget(id_label)
        
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
        label.setStyleSheet("font-size: 11px; color: #6b7280; font-weight: 500;")
        text_layout.addWidget(label)
        
        value = QLabel(value_text)
        value.setObjectName("infoValue")
        value.setStyleSheet("font-size: 14px; font-weight: bold; color: #111827;")
        text_layout.addWidget(value)
        
        layout.addLayout(text_layout)
        layout.addStretch()
        
        return frame
