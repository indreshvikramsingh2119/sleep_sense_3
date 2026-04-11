"""
Sleep Sense Dashboard - Medical Grade PyQt5 Application
Professional Sleep Monitoring System
"""

import sys
import os
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
        
        # Content Widget
        content = QWidget()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(16)
        
        # Patient ID Section
        patient_frame = QFrame()
        patient_frame.setObjectName("patientSection")
        patient_layout = QVBoxLayout(patient_frame)
        patient_layout.setSpacing(8)
        
        patient_label = QLabel("Patient Information")
        patient_label.setObjectName("sectionHeader")
        patient_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #111827;")
        patient_layout.addWidget(patient_label)
        
        # Patient ID input
        id_layout = QHBoxLayout()
        id_layout.setSpacing(8)
        
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
        
        # Weekly Summary Section
        summary_frame = QFrame()
        summary_frame.setObjectName("summarySection")
        summary_layout = QVBoxLayout(summary_frame)
        summary_layout.setSpacing(8)
        
        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel(" Weekly Summary")
        header_label.setObjectName("sectionHeader")
        header_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #111827;")
        header_layout.addWidget(header_label)
        header_layout.addStretch()
        
        summary_layout.addLayout(header_layout)
        
        # Stats Grid
        stats_grid = QGridLayout()
        stats_grid.setSpacing(8)
        
        # Create stat cards
        stats = [
            ("Total Sessions", "12", "sessions"),
            ("Avg Duration", "7.5", "hours"),
            ("OSA Events", "45", "events"),
            ("CSA Events", "8", "events"),
            ("MSA Events", "23", "events"),
            ("HSA Events", "67", "events")
        ]
        
        for i, (label, value, unit) in enumerate(stats):
            card = self.create_stat_card(label, value, unit)
            row, col = i // 3, i % 3
            stats_grid.addWidget(card, row, col)
        
        summary_layout.addLayout(stats_grid)
        content_layout.addWidget(summary_frame)
        
        # Raw Data Section
        raw_frame = QFrame()
        raw_frame.setObjectName("rawDataSection")
        raw_layout = QVBoxLayout(raw_frame)
        raw_layout.setSpacing(8)
        
        raw_header = QLabel("Raw Data Files")
        raw_header.setObjectName("sectionHeader")
        raw_header.setStyleSheet("font-size: 14px; font-weight: bold; color: #111827;")
        raw_layout.addWidget(raw_header)
        
        # File List
        self.file_list = QListWidget()
        self.file_list.setObjectName("fileList")
        self.file_list.setMaximumHeight(120)
        raw_layout.addWidget(self.file_list)
        
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
    
    def create_stat_card(self, label, value, unit):
        """Create a statistics card"""
        card = QFrame()
        card.setObjectName("statCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(4)
        
        value_label = QLabel(f"{value} {unit}")
        value_label.setObjectName("statValue")
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e293b;")
        card_layout.addWidget(value_label)
        
        label_widget = QLabel(label)
        label_widget.setObjectName("statLabel")
        label_widget.setAlignment(Qt.AlignCenter)
        label_widget.setStyleSheet("font-size: 11px; color: #6b7280;")
        card_layout.addWidget(label_widget)
        
        return card
    
    def on_patient_id_changed(self, text):
        """Handle patient ID change"""
        if self.monitor_chart:
            self.monitor_chart.set_patient_id(text)
    
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
    
    def add_saved_raw_file(self, file_path, timestamp_iso):
        """Add saved raw file to the list"""
        filename = os.path.basename(file_path)
        timestamp_str = timestamp_iso.replace("T", " ").replace("-", ":").split(":")
        timestamp_str = f"{timestamp_str[2]}-{timestamp_str[1]}-{timestamp_str[0]} {timestamp_str[3]}:{timestamp_str[4]}:{timestamp_str[5]}"
        
        item = QListWidgetItem(f"{timestamp_str} - {filename}")
        item.setData(Qt.UserRole, {"path": file_path, "timestamp": timestamp_iso, "filename": filename})
        self.file_list.addItem(item)
        self.saved_raw_files.append({"timestamp": timestamp_iso, "path": file_path, "filename": filename})


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
