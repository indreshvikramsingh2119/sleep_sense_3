"""
Sleep Sense Dashboard - Medical Grade PyQt5 Application
Professional Sleep Monitoring System
"""

import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTabWidget, QFileDialog, QScrollArea,
    QFrame, QGridLayout, QComboBox, QListWidget, QListWidgetItem,
    QSplitter, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, QTime, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QPixmap
import pyqtgraph as pg
import numpy as np


class PatientInfoWidget(QWidget):
    """Patient Information Panel"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.uploaded_files = [
            "sleep_data_2026-04-01.csv",
            "sleep_data_2026-04-02.csv",
            "sleep_data_2026-04-03.csv"
        ]
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)
        
        # Tab Buttons Container
        tabs_container = QWidget()
        tabs_layout = QHBoxLayout(tabs_container)
        tabs_layout.setContentsMargins(0, 0, 0, 0)
        tabs_layout.setSpacing(8)
        
        self.btn_patient_info = QPushButton("Patient Info")
        self.btn_patient_info.setObjectName("tabButtonActive")
        self.btn_patient_info.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        self.btn_raw_data = QPushButton("Raw Data")
        self.btn_raw_data.setObjectName("tabButtonInactive")
        self.btn_raw_data.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        tabs_layout.addWidget(self.btn_patient_info)
        tabs_layout.addWidget(self.btn_raw_data)
        main_layout.addWidget(tabs_container)
        
        # Stacked Widget for content
        from PyQt5.QtWidgets import QStackedWidget
        self.stack = QStackedWidget()
        
        # Patient Info Tab
        info_tab = self.create_info_tab()
        self.stack.addWidget(info_tab)
        
        # Raw Data Tab
        data_tab = self.create_data_tab()
        self.stack.addWidget(data_tab)
        
        main_layout.addWidget(self.stack)
        
        # Connect signals
        self.btn_patient_info.clicked.connect(lambda: self.switch_tab(0))
        self.btn_raw_data.clicked.connect(lambda: self.switch_tab(1))
        
    def switch_tab(self, index):
        self.stack.setCurrentIndex(index)
        if index == 0:
            self.btn_patient_info.setObjectName("tabButtonActive")
            self.btn_raw_data.setObjectName("tabButtonInactive")
        else:
            self.btn_patient_info.setObjectName("tabButtonInactive")
            self.btn_raw_data.setObjectName("tabButtonActive")
        
        # Force style update
        self.btn_patient_info.style().unpolish(self.btn_patient_info)
        self.btn_patient_info.style().polish(self.btn_patient_info)
        self.btn_raw_data.style().unpolish(self.btn_raw_data)
        self.btn_raw_data.style().polish(self.btn_raw_data)
        
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
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
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
        age_card = self.create_info_card("👤", "Age / Gender", "34 years / Female", "infoCardBlue")
        details_layout.addWidget(age_card)
        
        # Last Visit Card
        visit_card = self.create_info_card("📅", "Last Visit", "April 4, 2026", "infoCardIndigo")
        details_layout.addWidget(visit_card)
        
        # Sleep Duration Card
        sleep_card = self.create_info_card("🌙", "Avg Sleep Duration", "7.2 hours/night", "infoCardPurple")
        details_layout.addWidget(sleep_card)
        
        # Sleep Quality Card
        quality_card = self.create_info_card("❤️", "Sleep Quality", "Good", "infoCardGreen")
        details_layout.addWidget(quality_card)
        
        scroll_layout.addLayout(details_layout)
        
        # Weekly Summary Section
        summary_section = self.create_summary_section()
        scroll_layout.addWidget(summary_section)
        
        scroll_layout.addStretch()
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        return widget
    
    def create_avatar_section(self):
        """Create patient avatar and name section"""
        frame = QFrame()
        frame.setObjectName("avatarSection")
        layout = QVBoxLayout(frame)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)
        
        # Avatar container with circular border
        avatar_container = QFrame()
        avatar_container.setFixedSize(90, 90)
        avatar_container.setStyleSheet("""
            QFrame {
                background-color: #f3f4f6;
                border: 2px solid #e5e7eb;
                border-radius: 45px;
            }
        """)
        
        avatar_layout = QVBoxLayout(avatar_container)
        avatar_layout.setContentsMargins(0, 0, 0, 0)
        
        # Avatar label (SJ for Sarah Johnson)
        avatar_label = QLabel("SJ")
        avatar_label.setAlignment(Qt.AlignCenter)
        avatar_label.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                            stop:0 #2563eb, stop:1 #1d4ed8);
                color: white;
                font-size: 28px;
                font-weight: bold;
                border-radius: 43px;
            }
        """)
        avatar_layout.addWidget(avatar_label)
        
        layout.addWidget(avatar_container, alignment=Qt.AlignCenter)
        
        # Patient Name
        name_label = QLabel("Sarah Johnson")
        name_label.setObjectName("patientName")
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #111827;")
        layout.addWidget(name_label)
        
        # Patient ID
        id_label = QLabel("ID: SS-2024-1847")
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
    
    def create_summary_section(self):
        """Create weekly summary section"""
        frame = QFrame()
        frame.setObjectName("summarySection")
        layout = QVBoxLayout(frame)
        layout.setSpacing(12)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel("📈 Weekly Summary")
        header_label.setObjectName("sectionHeader")
        header_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #111827;")
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        lightning_label = QLabel("⚡")
        lightning_label.setStyleSheet("color: #f59e0b;")
        header_layout.addWidget(lightning_label)
        layout.addLayout(header_layout)
        
        # Stats Grid
        grid = QGridLayout()
        grid.setSpacing(8)
        
        # Total Sleep
        total_card = self.create_stat_card("Total Sleep", "48.5", "hrs", "statCardBlue")
        grid.addWidget(total_card, 0, 0)
        
        # Deep Sleep
        deep_card = self.create_stat_card("Deep Sleep", "12.3", "hrs", "statCardPurple")
        grid.addWidget(deep_card, 0, 1)
        
        # REM Sleep
        rem_card = self.create_stat_card("REM Sleep", "10.8", "hrs", "statCardIndigo")
        grid.addWidget(rem_card, 1, 0)
        
        # Efficiency
        eff_card = self.create_stat_card("Efficiency", "87", "%", "statCardGreen")
        grid.addWidget(eff_card, 1, 1)
        
        layout.addLayout(grid)
        
        return frame
    
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
        """Create raw data tab"""
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
        files_label = QLabel(f"Uploaded Files ({len(self.uploaded_files)})")
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
        self.file_list = QListWidget()
        self.file_list.setObjectName("fileList")
        self.populate_file_list()
        layout.addWidget(self.file_list)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        layout.addWidget(separator)
        
        # Download All Button
        download_all_main = QPushButton("⬇ Download All as ZIP")
        download_all_main.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        download_all_main.setMinimumHeight(40)
        download_all_main.clicked.connect(self.download_all)
        layout.addWidget(download_all_main)
        
        return widget
    
    def populate_file_list(self):
        """Populate file list"""
        self.file_list.clear()
        for filename in self.uploaded_files:
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(12, 8, 12, 8)
            
            # File icon
            icon_label = QLabel("📄")
            icon_label.setStyleSheet("font-size: 20px;")
            item_layout.addWidget(icon_label)
            
            # File name
            name_label = QLabel(filename)
            name_label.setStyleSheet("color: #374151; font-size: 12px;")
            item_layout.addWidget(name_label)
            item_layout.addStretch()
            
            # Download button
            download_btn = QPushButton("⬇")
            download_btn.setObjectName("ghostButton")
            download_btn.setMinimumSize(24, 24)
            download_btn.setMaximumSize(32, 32)
            download_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            download_btn.clicked.connect(lambda checked, f=filename: self.download_file(f))
            item_layout.addWidget(download_btn)
            
            item = QListWidgetItem(self.file_list)
            item.setSizeHint(item_widget.sizeHint())
            self.file_list.addItem(item)
            self.file_list.setItemWidget(item, item_widget)
    
    def upload_files(self):
        """Handle file upload"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files to Upload",
            "",
            "Data Files (*.csv *.edf *.txt);;All Files (*)"
        )
        if files:
            for file in files:
                filename = os.path.basename(file)
                if filename not in self.uploaded_files:
                    self.uploaded_files.append(filename)
            self.populate_file_list()
    
    def download_file(self, filename):
        """Download single file"""
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save File",
            filename,
            "All Files (*)"
        )
        if save_path:
            print(f"Downloading: {filename} to {save_path}")
    
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


class SleepMonitorChart(QWidget):
    """Sleep Monitoring Chart Widget"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_time = QTime.currentTime()
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
        
        self.start_time_label = QLabel("Start: 22:04:00")
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
        
        # Add Watermark
        self.watermark = QLabel("60S", self.charts_widget)
        self.watermark.setObjectName("chartWatermark")
        self.watermark.setAlignment(Qt.AlignCenter)
        self.watermark.setStyleSheet("""
            QLabel#chartWatermark {
                color: rgba(37, 99, 235, 0.05);
                font-size: 200px;
                font-weight: bold;
            }
        """)
        
        chart_layout.addWidget(self.charts_widget, stretch=1)
        
        # Status Bar
        status_bar = self.create_status_bar()
        chart_layout.addWidget(status_bar)
        
        main_layout.addWidget(chart_container)
        
    def create_control_bar(self):
        """Create control bar with playback controls"""
        frame = QFrame()
        frame.setObjectName("chartControlBar")
        frame.setMinimumHeight(64)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(16, 4, 16, 4)
        layout.setSpacing(12)
        
        # Playback controls container
        controls_container = QFrame()
        controls_container.setObjectName("playbackControls")
        controls_layout = QHBoxLayout(controls_container)
        controls_layout.setSpacing(6)
        controls_layout.setContentsMargins(6, 6, 6, 6)
        
        # Increased button sizes for better visibility
        skip_back_btn = QPushButton("⏮")
        skip_back_btn.setObjectName("controlButton")
        skip_back_btn.setFixedSize(40, 40)
        skip_back_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        controls_layout.addWidget(skip_back_btn)
        
        play_btn = QPushButton("▶")
        play_btn.setObjectName("playButtonMain")
        play_btn.setFixedSize(40, 40)
        play_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        controls_layout.addWidget(play_btn)
        
        skip_forward_btn = QPushButton("⏭")
        skip_forward_btn.setObjectName("controlButton")
        skip_forward_btn.setFixedSize(40, 40)
        skip_forward_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        controls_layout.addWidget(skip_forward_btn)
        
        layout.addWidget(controls_container)
        
        # Report selector
        self.report_combo = QComboBox()
        self.report_combo.addItems([
            "Sleep Monitoring Report",
            "Detailed Analysis",
            "Event Summary"
        ])
        self.report_combo.setMinimumWidth(180) # Adjusted minimum width
        self.report_combo.setMinimumHeight(38)
        self.report_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(self.report_combo)
        
        layout.addStretch()
        
        # Action buttons
        settings_btn = QPushButton("⚙ Settings")
        settings_btn.setObjectName("actionButton")
        settings_btn.setMinimumHeight(38)
        settings_btn.setMinimumWidth(100)
        settings_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(settings_btn)
        
        export_btn = QPushButton("⬇ Export")
        export_btn.setObjectName("actionButton")
        export_btn.setMinimumHeight(38)
        export_btn.setMinimumWidth(100)
        export_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(export_btn)
        
        maximize_btn = QPushButton("⛶")
        maximize_btn.setObjectName("actionButton")
        maximize_btn.setFixedSize(38, 38)
        maximize_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(maximize_btn)
        
        return frame
    
    def create_status_bar(self):
        """Create bottom status bar"""
        frame = QFrame()
        frame.setObjectName("statusBar")
        frame.setMinimumHeight(44)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(15)
        
        # Recording status
        recording_frame = QFrame()
        recording_frame.setObjectName("recordingBadge")
        recording_layout = QHBoxLayout(recording_frame)
        recording_layout.setContentsMargins(10, 4, 10, 4)
        recording_layout.setSpacing(8)
        
        rec_dot = QLabel("●")
        rec_dot.setStyleSheet("color: #10b981; font-size: 12px;")
        recording_layout.addWidget(rec_dot)
        
        rec_label = QLabel("Recording")
        rec_label.setStyleSheet("font-size: 12px; font-weight: 700; color: #065f46;")
        recording_layout.addWidget(rec_label)
        layout.addWidget(recording_frame)
        
        # Status labels with better visibility
        status_font = "font-size: 12px; color: #64748b; font-weight: 500;"
        
        self.stage_label = QLabel("Stage: 1")
        self.stage_label.setStyleSheet(status_font)
        layout.addWidget(self.stage_label)
        
        self.date_label = QLabel("2025-05-03 23:04:00")
        self.date_label.setStyleSheet(status_font)
        layout.addWidget(self.date_label)
        
        layout.addStretch()
        
        # Duration info
        self.duration_label = QLabel("Duration: 08:19")
        self.duration_label.setStyleSheet(status_font)
        layout.addWidget(self.duration_label)
        
        self.tracing_label = QLabel("Tracing: 1/2")
        self.tracing_label.setStyleSheet(status_font)
        layout.addWidget(self.tracing_label)
        
        self.seconds_label = QLabel("Seconds: 1/7140")
        self.seconds_label.setStyleSheet(status_font)
        layout.addWidget(self.seconds_label)
        
        return frame
    
    def init_charts(self):
        """Initialize signal trace charts"""
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        
        signals = [
            ("Abdominal Move", "#3b82f6", 0.5, 10, 50),
            ("Body Move", "#8b5cf6", 0.3, 15, 50),
            ("Snoring", "#ef4444", 1.0, 8, 50),
            ("Apnea", "#f59e0b", 0.2, 5, 50),
            ("SpO2", "#10b981", 0.1, 2, 90),
            ("Pulse Wave", "#06b6d4", 1.5, 12, 50),
            ("Body Pos", "#f97316", 0.0, 0, 30),  # Flat line for position
            ("CPAP Press", "#8b5cf6", 0.1, 5, 20),
        ]
        
        for name, color, freq, amp, offset in signals:
            chart = self.create_signal_chart(name, color, freq, amp, offset)
            self.charts_layout.addWidget(chart)
    
    def create_signal_chart(self, name, color, frequency, amplitude, offset):
        """Create a single signal trace chart with side label"""
        container = QWidget()
        container.setMinimumHeight(70)
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
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
        
        container_layout.addWidget(plot_widget)
        
        return container
    
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
        
        patient_info = PatientInfoWidget()
        patient_layout.addWidget(patient_info)
        
        splitter.addWidget(patient_panel)
        
        # Right Panel - Monitor Chart
        chart_panel = QFrame()
        chart_panel.setObjectName("chartPanel")
        chart_layout = QVBoxLayout(chart_panel)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        
        monitor_chart = SleepMonitorChart()
        chart_layout.addWidget(monitor_chart)
        
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
        logo_label = QLabel("🩺")
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
        
        live_time = QLabel("23:45:12")
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
        
        status_value = QLabel("● Active")
        status_value.setObjectName("statusValue")
        status_value.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(status_value)
        
        layout.addWidget(status_badge)
        
        return header
    
    def load_stylesheet(self):
        """Load QSS stylesheet"""
        qss_file = "sleep_sense_medical_white.qss"
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
