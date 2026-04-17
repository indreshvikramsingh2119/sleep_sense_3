"""
Sleep Sense Dashboard - Main Dashboard Component
"""

import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QSplitter, QSizePolicy, QScrollArea
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from .patient_info_widget import PatientInfoWidget
from .sleep_monitor_chart import SleepMonitorChart


class SleepSenseDashboard(QMainWindow):
    
    """Main Sleep Sense Dashboard Window"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_stylesheet()
        
    def init_ui(self):
        self.setWindowTitle("Sleep Sense - Medical Sleep Monitoring System")
        self.setGeometry(100, 100, 1200, 900)  # Reduced window width to force scrollbar
        self.setMinimumSize(1000, 700)  # Ensure all buttons and controls are fully visible
        
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
        
        # Main Content Area with Scroll
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        content_widget = QWidget()
        content_widget.setMinimumWidth(2000)  # Force minimum width to trigger horizontal scrollbar
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
        
        # Set content widget to scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
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
        logo_label = QLabel("...")
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
        
        status_value = QLabel("... Active")
        status_value.setObjectName("statusValue")
        status_value.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(status_value)
        
        layout.addWidget(status_badge)
        
        return header
    
    def load_stylesheet(self):
        """Load QSS stylesheet"""
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        qss_file = os.path.join(script_dir, "sleep_sense_medical_white.qss")
        if os.path.exists(qss_file):
            with open(qss_file, 'r') as f:
                self.setStyleSheet(f.read())
        else:
            print(f"Warning: Stylesheet file '{qss_file}' not found!")
