"""
Sleep Sense Dashboard - Medical Grade PyQt5 Application
Professional Sleep Monitoring System
"""

import sys
import os
import json
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTabWidget, QFileDialog, QScrollArea,
    QFrame, QGridLayout, QComboBox, QListWidget, QListWidgetItem,
    QSplitter, QSizePolicy, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, QTime, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QPixmap
from src.components.sleep_monitor_chart import SleepMonitorChart


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
        """Create patient information tab"""
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
        
        scroll_content = QWidget()
        scroll_content.setObjectName("scrollContent")
        scroll_content.setContentsMargins(16, 16, 16, 16) # Add internal padding
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(16) # Adjusted spacing between sections
        
        # Patient Avatar and Name Section
        avatar_section = self.create_avatar_section()
        scroll_layout.addWidget(avatar_section)
        
        # Patient Details Cards
        details_layout = QVBoxLayout()
        details_layout.setSpacing(10) # Adjusted spacing between info cards
        
        # Age/Gender Card
        age_card = self.create_info_card("", "Age / Gender", "-- / ---", "light green")
        details_layout.addWidget(age_card)
        
        # Action Buttons (Save and Upload)
        action_buttons = self.create_action_buttons()
        details_layout.addWidget(action_buttons)
        
        # Last Visit Card
        #visit_card = self.create_info_card("", "Last Visit", "--", "infoCardIndigo")
        #details_layout.addWidget(visit_card)
        
        # Sleep Duration Card
        #sleep_card = self.create_info_card("", "Avg Sleep Duration", "--", "infoCardPurple")
        #details_layout.addWidget(sleep_card)
        
        # Sleep Quality Card
        
        #quality_card = self.create_info_card("", "Sleep Quality", "--", "infoCardGreen")
        #details_layout.addWidget(quality_card)
        
        scroll_layout.addLayout(details_layout)

        # Raw Data File Section (inline, under patient details)
        raw_section = self.create_raw_data_section()
        scroll_layout.addWidget(raw_section)
        
        # Weekly Summary Section
        # (Optional) enable this once the section is fully wired
        ## summary_section = self.create_summary_section()
        # scroll_layout.addWidget(summary_section)
        
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        return widget

    def create_action_buttons(self):
        """Create save and upload action buttons"""
        frame = QFrame()
        frame.setObjectName("actionButtonsSection")
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(8)

        # Save Button
        save_btn = QPushButton(" Save Data")
        save_btn.setObjectName("actionButton")
        save_btn.setMinimumHeight(36)
        save_btn.clicked.connect(self.save_data)
        frame_layout.addWidget(save_btn)

        # Upload Button 
        upload_btn = QPushButton(" Upload Data")
        upload_btn.setObjectName("actionButton")
        upload_btn.setMinimumHeight(36)
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
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Save file List")
        title.setStyleSheet("font-weight: 700; color: #111827;")
        header.addWidget(title)
        header.addStretch()

        self.raw_count_label = QLabel("0")
        self.raw_count_label.setStyleSheet("font-weight: 700; color: #2563eb;")
        header.addWidget(self.raw_count_label)
        frame_layout.addLayout(header)

        self.raw_hint_label = QLabel("Press Save → Yes to generate raw data with a timestamp.")
        self.raw_hint_label.setStyleSheet("font-size: 11px; color: #6b7280;")
        self.raw_hint_label.setWordWrap(True)
        frame_layout.addWidget(self.raw_hint_label)

        self.raw_file_list = QListWidget()
        self.raw_file_list.setObjectName("Saved file List")
        self.raw_file_list.setVisible(False)
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

    #def create_summary_section(self):
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
        frame.setObjectName("avatarSection")
        layout = QVBoxLayout(frame)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)
        
        # Patient ID Section
        patient_frame = QFrame()
        patient_frame.setObjectName("patientSection")
        patient_layout = QVBoxLayout(patient_frame)
        patient_layout.setSpacing(8)
        
        patient_label = QLabel("Patient Information")
        patient_label.setObjectName("sectionHeader")
        patient_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #111827;")
        patient_layout.addWidget(patient_label)
        
        # Avatar label (SJ for Sarah Johnson)
        avatar_label = QLabel("--")
        avatar_label.setAlignment(Qt.AlignCenter)
        avatar_label.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                            stop:0 #34d399, stop:1 #10b981);
                color: white;
                font-size: 28px;
                font-weight: bold;
                border-radius: 43px;
            }
        """)
        avatar_layout.addWidget(avatar_label)
        
        id_label = QLabel("Patient ID:")
        id_label.setStyleSheet("font-size: 12px; color: #374151;")
        id_layout.addWidget(id_label)
        
        self.patient_id_input = QComboBox()
        self.patient_id_input.setObjectName("patientIdInput")
        self.patient_id_input.setEditable(True)
        self.patient_id_input.setFixedHeight(30)
        self.patient_id_input.addItems(["--------", "PATIENT001", "PATIENT002", "PATIENT003"])
        self.patient_id_input.currentTextChanged.connect(self.on_patient_id_changed)
        id_layout.addWidget(self.patient_id_input)
        
        id_layout.addStretch()
        patient_layout.addLayout(id_layout)
        content_layout.addWidget(patient_frame)
        
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
        frame.setMinimumHeight(60)
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
    
    #def create_summary_section(self):
     #   """Create weekly summary section"""
        frame = QFrame()
        frame.setObjectName("summarySection")
        layout = QVBoxLayout(frame)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel(" Weekly Summary")
        header_label.setObjectName("sectionHeader")
        header_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #111827;")
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        
        summary_layout.addLayout(header_layout)
        
        # Stats Grid
        #grid = QGridLayout()
        #grid.setSpacing(8)
        
        # Total Sleep
        #total_card = self.create_stat_card("Total Sleep", "---", "hrs", "statCardBlue")
        #grid.addWidget(total_card, 0, 0)
        
        # Deep Sleep
        #deep_card = self.create_stat_card("Deep Sleep", "---", "hrs", "statCardPurple")
        #grid.addWidget(deep_card, 0, 1)
        
        # REM Sleep
        #rem_card = self.create_stat_card("REM Sleep", "---", "hrs", "statCardIndigo")
        #grid.addWidget(rem_card, 1, 0)
        
        # Efficiency
        #eff_card = self.create_stat_card("Efficiency", "---", "%", "statCardGreen")
        #grid.addWidget(eff_card, 1, 1)
        
        #layout.addLayout(grid)
        
        #return frame
    
    def create_stat_card(self, label_text, value, unit, object_name):
        """Create a stat card"""
        frame = QFrame()
        frame.setObjectName(object_name)
        frame.setMinimumHeight(70)
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        
        label = QLabel(label_text)
        label.setObjectName("statLabel")
        label.setStyleSheet("font-size: 10px; color: #4b5563; font-weight: 500;")
        layout.addWidget(label)
        
        value_layout = QHBoxLayout()
        value_layout.setSpacing(4)
        value_label = QLabel(value)
        value_label.setObjectName("statValue")
        value_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e3a8a;")
        value_layout.addWidget(value_label)
        
        unit_label = QLabel(unit)
        unit_label.setObjectName("statUnit")
        unit_label.setStyleSheet("font-size: 11px; color: #6366f1; font-weight: 600; padding-top: 4px;")
        value_layout.addWidget(unit_label)
        value_layout.addStretch()
        
        layout.addLayout(value_layout)
        
        return frame
    
    def create_data_tab(self):
        """Create raw data tab (deprecated - tab removed from UI)"""
        widget = QWidget()
        widget.setObjectName("dataTab")
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)
        
        # Upload Area
        upload_frame = QFrame()
        upload_frame.setObjectName("uploadArea")
        upload_layout = QVBoxLayout(upload_frame)
        upload_layout.setAlignment(Qt.AlignCenter)
        upload_layout.setSpacing(12)
        
        upload_icon = QLabel("📤")
        upload_icon.setAlignment(Qt.AlignCenter)
        upload_icon.setStyleSheet("font-size: 48px;")
        upload_layout.addWidget(upload_icon)
        
        upload_title = QLabel("Import Raw Data")
        upload_title.setAlignment(Qt.AlignCenter)
        upload_title.setStyleSheet("font-weight: 600; color: #111827;")
        upload_layout.addWidget(upload_title)
        
        upload_desc = QLabel("Upload CSV, EDF, or TXT files")
        upload_desc.setAlignment(Qt.AlignCenter)
        upload_desc.setStyleSheet("font-size: 11px; color: #6b7280;")
        upload_layout.addWidget(upload_desc)
        
        upload_btn = QPushButton("📤 Choose Files")
        upload_btn.setObjectName("uploadButton")
        upload_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        upload_btn.setMinimumHeight(40)
        upload_btn.clicked.connect(self.upload_files)
        upload_layout.addWidget(upload_btn, alignment=Qt.AlignCenter)
        
        layout.addWidget(upload_frame)
        
        # File List Header
        header_layout = QHBoxLayout()
        files_label = QLabel("Uploaded Files (0)")
        files_label.setStyleSheet("font-weight: 600; color: #111827;")
        header_layout.addWidget(files_label)
        header_layout.addStretch()
        
        download_all_btn = QPushButton("⬇ All")
        download_all_btn.setObjectName("ghostButton")
        download_all_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        download_all_btn.clicked.connect(self.download_all)
        header_layout.addWidget(download_all_btn)
        
        layout.addLayout(header_layout)
        
        # File List
        file_list = QListWidget()
        file_list.setObjectName("fileList")
        layout.addWidget(file_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        save_btn = QPushButton("Save Current")
        save_btn.setObjectName("actionButton")
        save_btn.clicked.connect(self.save_current_data)
        button_layout.addWidget(save_btn)
        
        download_btn = QPushButton("Download All")
        download_btn.setObjectName("actionButton")
        download_btn.clicked.connect(self.download_all)
        button_layout.addWidget(download_btn)
        
        raw_layout.addLayout(button_layout)
        content_layout.addWidget(raw_frame)
        
        content_layout.addStretch()
        
        return widget
    
    def populate_file_list(self):
        """Deprecated (Raw Data tab removed)."""
        return
    
    def upload_files(self):
        """Handle file upload"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files to Upload",
            "",
            "Data Files (*.csv *.edf *.txt);;All Files (*)"
        )
        # Raw Data tab removed from the UI; keep chooser only as no-op.
        if files:
            pass
    
    def save_current_data(self):
        """Save current data"""
        if self.monitor_chart:
            self.monitor_chart.confirm_and_save_raw_data()
    
    def download_all(self):
        """Download all files as ZIP"""
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save ZIP File",
            "sleep_data_all.zip",
            "ZIP Files (*.zip)"
        )
        if save_path:
            print(f"Downloading all files to: {save_path}")


class SleepMonitorChart(QWidget):#
    """Sleep Monitoring Chart Widget"""
    raw_data_saved = pyqtSignal(str, str)  # file_path, timestamp_iso
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_time = QTime.currentTime()
        self.patient_id = "--------"
        self.current_time_window = 60  # Default to 60 seconds
        self.init_ui()
        self.init_charts()
        
        # Timer for updating time
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)  # Update every second
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8) # Increased spacing between control bar and chart container
        
        # Control Bar
        control_bar = self.create_control_bar()
        main_layout.addWidget(control_bar)
        
        # Chart Area
        chart_container = QWidget()
        chart_container.setObjectName("chartBackground")
        chart_layout = QVBoxLayout(chart_container)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.setSpacing(8)
        
        # Time labels overlay
        time_overlay = QWidget()
        time_overlay.setMinimumHeight(40)
        time_layout = QHBoxLayout(time_overlay)
        time_layout.setContentsMargins(16, 8, 16, 8)
        
        self.start_time_label = QLabel("Start: ----")
        self.start_time_label.setObjectName("timeLabelStart")
        time_layout.addWidget(self.start_time_label)
        time_layout.addStretch()
        
        self.current_time_label = QLabel("Current: 23:04:00")
        self.current_time_label.setObjectName("timeLabelCurrent")
        time_layout.addWidget(self.current_time_label)
        
        chart_layout.addWidget(time_overlay)
        
        # Charts container
        self.charts_widget = QWidget()
        self.charts_widget.setObjectName("chartsContainer")
        self.charts_layout = QVBoxLayout(self.charts_widget)
        self.charts_layout.setContentsMargins(0, 0, 0, 0)
        self.charts_layout.setSpacing(8)
        
        chart_layout.addWidget(self.charts_widget, stretch=1)
        
        # Status Bar
        status_bar = self.create_status_bar()
        chart_layout.addWidget(status_bar)
        
        main_layout.addWidget(chart_container)
        
    def create_control_bar(self):
        """Create control bar with playback controls"""
        frame = QFrame()
        frame.setObjectName("chartControlBar")
        frame.setMinimumHeight(80)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(16, 4, 16, 4)
        layout.setSpacing(12)

        # --- Playback Controls ---
        controls_container = QFrame()
        controls_container.setObjectName("playbackControls")
        controls_layout = QHBoxLayout(controls_container)
        controls_layout.setSpacing(6)
        controls_layout.setContentsMargins(0, 0, 0, 0)

        backward_btn = QPushButton("◀")
        backward_btn.setObjectName("controlButton")
        backward_btn.setFixedHeight(35)
        backward_btn.setMinimumWidth(75)
        controls_layout.addWidget(backward_btn)

        pause_btn = QPushButton("||")
        pause_btn.setObjectName("controlButton")
        pause_btn.setFixedHeight(35)
        pause_btn.setMinimumWidth(75)
        controls_layout.addWidget(pause_btn)

    
        forward_btn = QPushButton("▶")
        forward_btn.setObjectName("controlButton")
        forward_btn.setFixedHeight(35)
        forward_btn.setMinimumWidth(75)
        controls_layout.addWidget(forward_btn)

        controls_container.setLayout(controls_layout)
        layout.addWidget(controls_container)

        # --- Report Selector ---
        report_label = QLabel("Sleep Monitoring Report")
        report_label.setObjectName("reportLabel")
        report_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b; margin-left: 12px; margin-right: 12px;")
        layout.addWidget(report_label)

        # --- Time Window Buttons ---
        time_window_frame = QFrame()
        time_window_layout = QHBoxLayout(time_window_frame)
        time_window_layout.setContentsMargins(0, 0, 0, 0)
        time_window_layout.setSpacing(5)
        time_windows = [
            ("10s", 10),
            ("30s", 30),
            ("60s", 60),
            ("2m", 120),
            ("5m", 300),
            ("10m", 600),
        ]
        self.time_window_buttons = []
        for label, value in time_windows:
            btn = QPushButton(label)
            btn.setObjectName("timeWindowButton")
            btn.setFixedHeight(32)
            btn.setMinimumWidth(48)
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, v=value: self.set_time_window(v))
            time_window_layout.addWidget(btn)
            self.time_window_buttons.append(btn)
        self.time_window_buttons[2].setChecked(True)
        layout.addWidget(time_window_frame)

        layout.addStretch()

        return frame

    def set_patient_id(self, patient_id: str):
        self.patient_id = patient_id or "--------"

    def confirm_and_save_raw_data(self):
        reply = QMessageBox.question(
            self,
            "Save raw data",
            "Generate a timestamped raw-data file for the current session?",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return
        file_path, timestamp_iso = self.save_raw_data_file()
        if file_path:
            self.raw_data_saved.emit(file_path, timestamp_iso)

    def save_raw_data_file(self):
        """Write a timestamped raw-data JSON file and return (path, timestamp_iso)."""
        timestamp_iso = datetime.now().isoformat(timespec="seconds")
        safe_ts = timestamp_iso.replace(":", "-")
        out_dir = os.path.join(os.getcwd(), "raw_data")
        os.makedirs(out_dir, exist_ok=True)
        filename = f"raw_data_{self.patient_id}_{safe_ts}.json"
        file_path = os.path.join(out_dir, filename)

        # Generate representative signal arrays similar to the plotted traces
        signals = [
            ("Body Position", "#3b82f6", 0.5, 10, 50),
            ("Airflow", "#8b5cf6", 0.3, 15, 50),
            ("Snoring", "#ef4444", 1.0, 8, 50),
            ("Thorex", "#f59e0b", 0.2, 5, 50),
            ("Abdomen", "#10b981", 0.1, 2, 90),
            ("SpO2", "#06b6d4", 1.5, 12, 50),
            ("Pulse", "#f97316", 0.0, 0, 30),
            ("Body Movement", "#8b5cf6", 0.1, 5, 20),
            ("PR/HR", "#5c61f6", 0.1, 5, 20),
        ]

        time_points = 1000
        x = np.linspace(0, 10, time_points).tolist()
        channels = {}
        for name, color, freq, amp, offset in signals:
            y = (np.sin(np.linspace(0, 10, time_points) * freq * 2 * np.pi) * amp + offset + (np.random.rand(time_points) - 0.5) * amp * 0.1)
            channels[name] = {"x": x, "y": y.tolist(), "color": color}

        payload = {
            "patient_id": self.patient_id,
            "timestamp": timestamp_iso,
            "channels": channels,
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        return file_path, timestamp_iso

    def set_time_window(self, seconds):
        """Set the time window for the sleep monitoring chart"""
        # Update current time window
        self.current_time_window = seconds
        
        # Uncheck all, check only the clicked one
        for btn in self.time_window_buttons:
            btn.setChecked(False)
        sender = self.sender()
        if sender:
            sender.setChecked(True)
        
        # Update charts with new time window
        self.update_charts_for_time_window(seconds)
        print(f"Time window set to: {seconds} seconds")
    
    def update_charts_for_time_window(self, seconds):
        """Update chart data based on time window selection"""
        # Clear existing charts
        for i in reversed(range(self.charts_layout.count())):
            child = self.charts_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
        
        # Generate new data based on time window
        signals = [
            ("Body Position", "#3b82f6", 0.5, 10, 50),
            ("Airflow", "#8b5cf6", 0.3, 15, 50),
            ("Snoring", "#ef4444", 1.0, 8, 50),
            ("Thorex ", "#f59e0b", 0.2, 5, 50),
            ("Abdomen ", "#10b981", 0.1, 2, 90),
            ("SpO2 ", "#06b6d4", 1.5, 12, 50),
            ("Pulse ", "#f97316", 0.0, 0, 30),
            ("Body Movement", "#8b5cf6", 0.1, 5, 20),
            ("PR/HR)", "#5c61f6", 0.1, 5, 20),
        ]
        
        # Adjust frequency based on time window (longer window = lower frequency for visibility)
        frequency_factor = max(0.1, 10.0 / (seconds / 10.0))
        
        for name, color, base_freq, amp, offset in signals:
            adjusted_freq = base_freq * frequency_factor
            chart = self.create_signal_chart(name, color, adjusted_freq, amp, offset)
            self.charts_layout.addWidget(chart)
    
    def create_status_bar(self):
        """Create bottom status bar"""
        frame = QFrame()
        frame.setObjectName("statusBar")
        frame.setMinimumHeight(44)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(15)
        
        return frame
    
    def init_charts(self):
        """Initialize signal trace charts"""
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        
        signals = [
            ("Body Position", "#3b82f6", 0.5, 10, 50),
            ("Airflow", "#8b5cf6", 0.3, 15, 50),
            ("Snoring", "#ef4444", 1.0, 8, 50),
            ("Thorex ", "#f59e0b", 0.2, 5, 50),
            ("Abdomen ", "#10b981", 0.1, 2, 90),
            ("SpO2 ", "#06b6d4", 1.5, 12, 50),
            ("Pulse ", "#f97316", 0.0, 0, 30),  # Flat line for position
            ("Body Movement", "#8b5cf6", 0.1, 5, 20),
            ("PR/HR)", "#5c61f6", 0.1, 5, 20),
        ]
        
        for name, color, freq, amp, offset in signals:
            chart = self.create_signal_chart(name, color, freq, amp, offset)
            self.charts_layout.addWidget(chart)
    
    def create_signal_chart(self, name, color, frequency, amplitude, offset):
        """Create a single signal trace chart with side label"""
        container = QWidget()
        container.setObjectName("signalChartContainer")
        container.setMinimumHeight(70)
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(4, 4, 4, 4)  # Add padding for border visibility
        container_layout.setSpacing(8) # Added spacing between label and plot
        
        # Side Label
        label_frame = QFrame()
        label_frame.setFixedWidth(140) # Further increased width for better label visibility
        label_layout = QVBoxLayout(label_frame)
        label_layout.setContentsMargins(8, 4, 8, 4)
        label_layout.setAlignment(Qt.AlignCenter)
        
        label = QLabel(name)
        label.setObjectName("chartSideLabel")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(f"""
            QLabel#chartSideLabel {{
                font-size: 12px; /* Increased font size */
                font-weight: bold;
                color: #4b5563;
                background-color: #f9fafb;
                border: 1px solid #e5e7eb;
                border-radius: 4px;
                padding: 6px; /* Increased padding */
            }}
        """)
        label_layout.addWidget(label)
        container_layout.addWidget(label_frame)
        
        # Plot Container with Zoom Controls
        plot_container = QWidget()
        plot_container_layout = QVBoxLayout(plot_container)
        plot_container_layout.setContentsMargins(0, 0, 0, 0)
        plot_container_layout.setSpacing(2)
        
        # Zoom Controls
        zoom_frame = QFrame()
        zoom_layout = QHBoxLayout(zoom_frame)
        zoom_layout.setContentsMargins(0, 0, 0, 0)
        zoom_layout.setSpacing(4)
        
        # Store original Y range for zoom calculations
        self.original_y_min = 0
        self.original_y_max = 100
        self.current_y_min = 0
        self.current_y_max = 100
        
        #c
        zoom_layout.addStretch()
        plot_container_layout.addWidget(zoom_frame)
        
        # Plot Widget
        plot_widget = pg.PlotWidget()
        plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        plot_widget.showGrid(x=True, y=True, alpha=0.1)
        plot_widget.setYRange(0, 100)
        plot_widget.getAxis('bottom').setStyle(showValues=False)
        plot_widget.getAxis('left').setStyle(showValues=False)
        plot_widget.setMouseEnabled(x=True, y=False)
        plot_widget.hideButtons()  # Hide the 'A' button
        
        # Generate signal data
        time_points = 1000
        x = np.linspace(0, 10, time_points)
        y = np.sin(x * frequency * 2 * np.pi) * amplitude + offset + (np.random.rand(time_points) - 0.5) * amplitude * 0.1
        
        # Plot the signal
        pen = pg.mkPen(color=color, width=1.5)
        plot_widget.plot(x, y, pen=pen)
        
        plot_container_layout.addWidget(plot_widget)
        container_layout.addWidget(plot_container)
        
        return container
    
    def zoom_vertical(self, plot_widget, zoom_factor):
        """Zoom in/out vertically on the plot"""
        # Get current Y range
        current_range = plot_widget.getViewBox().viewRange()
        y_min, y_max = current_range[1]
        
        # Calculate center poi
        center = (y_min + y_max) / 2
        current_range_size = y_max - y_min
        
        # Calculate new range size
        new_range_size = current_range_size * zoom_factor
        
        # Calculate new bounds
        new_y_min = center - new_range_size / 2
        new_y_max = center + new_range_size / 2
        
        # Apply limits to keep within 0-100 range
        if new_y_min < 0:
            new_y_min = 0
            new_y_max = new_range_size
        elif new_y_max > 100:
            new_y_max = 100
            new_y_min = 100 - new_range_size
            
        plot_widget.setYRange(new_y_min, new_y_max)
    
    def reset_zoom(self, plot_widget):
        """Reset zoom to original range"""
        plot_widget.setYRange(0, 100)
    
    def update_time(self):
        """Update current time display"""
        self.current_time = self.current_time.addSecs(1)
        self.current_time_label.setText(f"Current: {self.current_time.toString('HH:mm:ss')}")

    def resizeEvent(self, event):
        """Handle resize for watermark centering"""
        super().resizeEvent(event)
        if hasattr(self, 'watermark'):
            self.watermark.setGeometry(self.charts_widget.rect())


class SleepSenseDashboard(QMainWindow):
    
    """Main Sleep Sense Dashboard Window"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_stylesheet()
        
    def init_ui(self):
        self.setWindowTitle("Sleep Sense - Medical Sleep Monitoring System")
        self.setGeometry(100, 100, 1600, 900)
        self.setMinimumSize(1200, 700)  # Ensure all buttons and controls are fully visible
        
        # Central Widget
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header
        header = self.create_header()
        main_layout.addWidget(header)
        
        # Main Content Area
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(16)
        
        # Splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        
        # Left Panel - Patient Info
        patient_panel = QFrame()
        patient_panel.setObjectName("patientPanel")
        patient_panel.setMinimumWidth(280)  # Increased minimum width for better visibility
        patient_panel.setMaximumWidth(350) # Set a reasonable maximum width
        patient_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        patient_layout = QVBoxLayout(patient_panel)
        patient_layout.setContentsMargins(0, 0, 0, 0)
        
        self.patient_info = PatientInfoWidget()
        patient_layout.addWidget(self.patient_info)
        
        splitter.addWidget(patient_panel)
        
        # Right Panel - Monitor Chart
        chart_panel = QFrame()
        chart_panel.setObjectName("chartPanel")
        chart_layout = QVBoxLayout(chart_panel)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        
        self.monitor_chart = SleepMonitorChart()
        self.monitor_chart.set_patient_id("--------")
        self.monitor_chart.raw_data_saved.connect(self.patient_info.add_saved_raw_file)
        
        # Connect monitor chart reference to patient info for save functionality
        self.patient_info.monitor_chart = self.monitor_chart
        
        chart_layout.addWidget(self.monitor_chart)
        
        splitter.addWidget(chart_panel)
        splitter.setSizes([300, 1000]) # Initial sizes, will be adjusted by policies
        splitter.setStretchFactor(0, 0) # Left panel takes its preferred size, doesn't stretch
        splitter.setStretchFactor(1, 1) # Right panel takes all available extra space
        
        content_layout.addWidget(splitter)
        main_layout.addWidget(content_widget)
        
    def create_header(self):
        """Create application header"""
        header = QFrame()
        header.setObjectName("headerWidget")
        header.setMinimumHeight(70)
        header.setMaximumHeight(80)
        header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        layout = QHBoxLayout(header)
        layout.setContentsMargins(24, 8, 24, 8)
        layout.setSpacing(12)
        
        # Logo and Title
        logo_layout = QHBoxLayout()
        logo_layout.setSpacing(12)
        
        # Logo
        logo_frame = QFrame()
        logo_frame.setObjectName("logoContainer")
        logo_frame.setFixedSize(44, 44)
        logo_label = QLabel("")
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setStyleSheet("font-size: 22px; color: white;")
        logo_layout_inner = QVBoxLayout(logo_frame)
        logo_layout_inner.setContentsMargins(0, 0, 0, 0)
        logo_layout_inner.addWidget(logo_label)
        logo_layout.addWidget(logo_frame)
        
        # Title and subtitle
        title_layout = QVBoxLayout()
        title_layout.setSpacing(0)
        
        title = QLabel("Sleep Sense")
        title.setObjectName("headerTitle")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #111827;")
        title_layout.addWidget(title)
        
        subtitle = QLabel("Medical Sleep Monitoring System")
        subtitle.setObjectName("headerSubtitle")
        subtitle.setStyleSheet("font-size: 12px; color: #6b7280;")
        title_layout.addWidget(subtitle)
        
        logo_layout.addLayout(title_layout)
        layout.addLayout(logo_layout)
        
        layout.addStretch()
        
        # Status badges
        # Live Session Badge
        live_badge = QFrame()
        live_badge.setObjectName("liveSessionBadge")
        live_badge.setMinimumWidth(120)
        live_layout = QVBoxLayout(live_badge)
        live_layout.setContentsMargins(12, 4, 12, 4)
        live_layout.setSpacing(0)
        
        live_label = QLabel("Live Session")
        live_label.setObjectName("badgeLabel")
        live_label.setAlignment(Qt.AlignCenter)
        live_layout.addWidget(live_label)
        
        live_time = QLabel("----")
        live_time.setObjectName("badgeValue")
        live_time.setAlignment(Qt.AlignCenter)
        live_layout.addWidget(live_time)
        
        layout.addWidget(live_badge)
        
        # Active Status Badge
        status_badge = QFrame()
        status_badge.setObjectName("statusActiveBadge")
        status_badge.setMinimumWidth(100)
        status_layout = QVBoxLayout(status_badge)
        status_layout.setContentsMargins(12, 4, 12, 4)
        status_layout.setSpacing(0)
        
        status_label = QLabel("Status")
        status_label.setObjectName("badgeLabel")
        status_label.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(status_label)
        
        status_value = QLabel(" Active")
        status_value.setObjectName("statusValue")
        status_value.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(status_value)
        
        layout.addWidget(status_badge)
        
        return header
    
    def load_stylesheet(self):
        """Load QSS stylesheet"""
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        qss_file = os.path.join(script_dir, "sleep_sense_medical_white.qss")
        if os.path.exists(qss_file):
            with open(qss_file, 'r') as f:
                self.setStyleSheet(f.read())
        else:
            print(f"Warning: Stylesheet file '{qss_file}' not found!")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Sleep Sense")
    
    # Set default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    window = SleepSenseDashboard()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
