"""
Sleep Sense Dashboard - Main Dashboard Component
"""

import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QSplitter, QSizePolicy, QScrollArea,
    QSlider, QPushButton, QMenuBar, QMenu, QAction
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap

from .patient_info_widget import PatientInfoWidget
from .sleep_monitor_chart import SleepMonitorChart
from .button_functions import ButtonFunctions


class SleepSenseDashboard(QMainWindow):
    
    """Main Sleep Sense Dashboard Window"""
    
    def __init__(self):
        super().__init__()
        self.logo_frame = None
        self.logo_label = None
        # Initialize button functions
        self.button_functions = ButtonFunctions(self)
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
        
        # Menu Bar Container - Custom menu bar positioned below system menu bar
        menu_container = QFrame()
        menu_container.setObjectName("menuContainer")
        menu_container.setMinimumHeight(30)
        menu_container.setMaximumHeight(35)
        menu_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        menu_layout = QHBoxLayout(menu_container)
        menu_layout.setContentsMargins(8, 2, 8, 2)
        menu_layout.setSpacing(4)
        
        # Create simple menu buttons
        self.file_btn = QPushButton('File')
        self.file_btn.setObjectName("menuButton")
        self.file_btn.setMinimumWidth(60)
        self.file_btn.clicked.connect(lambda: self.show_file_menu())
        menu_layout.addWidget(self.file_btn)
        
        self.edit_btn = QPushButton('Edit')
        self.edit_btn.setObjectName("menuButton")
        self.edit_btn.setMinimumWidth(60)
        self.edit_btn.clicked.connect(lambda: self.show_edit_menu())
        menu_layout.addWidget(self.edit_btn)
        
        self.view_btn = QPushButton('View')
        self.view_btn.setObjectName("menuButton")
        self.view_btn.setMinimumWidth(60)
        self.view_btn.clicked.connect(lambda: self.show_view_menu())
        menu_layout.addWidget(self.view_btn)
        
        self.help_btn = QPushButton('Help')
        self.help_btn.setObjectName("menuButton")
        self.help_btn.setMinimumWidth(60)
        self.help_btn.clicked.connect(lambda: self.show_help_menu())
        menu_layout.addWidget(self.help_btn)
        
        menu_layout.addStretch()
        
        main_layout.addWidget(menu_container)
        
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
        
        # Right Panel - Monitor Chart with Time Navigation
        chart_panel = QFrame()
        chart_panel.setObjectName("chartPanel")
        chart_layout = QVBoxLayout(chart_panel)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        
        self.monitor_chart = SleepMonitorChart()
        self.monitor_chart.set_patient_id("--------")
        self.monitor_chart.raw_data_saved.connect(self.patient_info.add_saved_raw_file)
        
        # Connect monitor chart reference to patient info for save functionality
        self.patient_info.monitor_chart = self.monitor_chart
        
        # Connect dashboard slider to chart navigation updates
        self.monitor_chart.time_position_updated.connect(self.update_slider_position)
        
        chart_layout.addWidget(self.monitor_chart)
        
        # Add Time Navigation in chart panel (same size as graph containers)
        time_slider_bar = self.create_time_slider_bar()
        chart_layout.addWidget(time_slider_bar)
        
        splitter.addWidget(chart_panel)
        splitter.setSizes([300, 1000]) # Initial sizes, will be adjusted by policies
        splitter.setStretchFactor(0, 0) # Left panel takes its preferred size, doesn't stretch
        splitter.setStretchFactor(1, 1) # Right panel takes all available extra space
        
        content_layout.addWidget(splitter)
        
        # Set content widget to scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # Time Slider Navigation Bar at Bottom - REMOVED (moved to chart panel)
        
        # Remove margins from main layout to allow full width
        main_layout.setContentsMargins(0, 0, 0, 0)
        
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
        self.logo_frame = QFrame()
        self.logo_frame.setObjectName("logoContainer")
        self.update_logo_size()  # Set initial size based on current window
        
        # Load DECK MOUNT logo image
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignCenter)
        
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        logo_path = os.path.join(script_dir, "assets", "images", "deck_mount_logo.png")
        
        # Store logo path for dynamic updates
        self.logo_path = logo_path
        
        # Load logo with current size
        self.update_logo_content()
        
        logo_layout_inner = QVBoxLayout(self.logo_frame)
        logo_layout_inner.setContentsMargins(0, 0, 0, 0)
        logo_layout_inner.addWidget(self.logo_label)
        logo_layout.addWidget(self.logo_frame)
        
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
        
        status_value = QLabel("...")
        status_value.setObjectName("statusValue")
        status_value.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(status_value)
        
        layout.addWidget(status_badge)
        
        return header
    
    def show_file_menu(self):
        """Show File menu popup"""
        from PyQt5.QtWidgets import QMenu, QApplication
        
        menu = QMenu(self)
        menu.addAction('Database', self.button_functions.file_database)
        menu.addAction('Archive', self.button_functions.file_archive)
        menu.addSeparator()
        menu.addAction('Save report locally', self.button_functions.file_save_report_locally, 'Ctrl+S')
        menu.addAction('Print report', self.button_functions.file_print_report, 'Ctrl+P')
        menu.addAction('Print patient instructions', self.button_functions.file_print_patient_instructions)
        menu.addSeparator()
        menu.addAction('View external data', self.button_functions.file_view_external_data)
        menu.addAction('Duplicate', self.button_functions.file_duplicate, 'Ctrl+D')
        menu.addSeparator()
        menu.addAction('Export', self.button_functions.file_export, 'Ctrl+E')
        menu.addAction('Import recording', self.button_functions.file_import_recording, 'Ctrl+I')
        menu.addSeparator()
        menu.addAction('Send report by email', self.button_functions.file_send_report_by_email)
        menu.addSeparator()
        menu.addAction('Exit', self.close, 'Ctrl+Q')
        
        # Show menu below button
        button_rect = self.file_btn.geometry()
        menu_pos = self.file_btn.mapToGlobal(button_rect.bottomLeft())
        menu.exec_(menu_pos)
    
    def show_edit_menu(self):
        """Show Edit menu popup"""
        from PyQt5.QtWidgets import QMenu
        
        menu = QMenu(self)
        menu.addAction('Undo', self.button_functions.edit_undo, 'Ctrl+Z')
        
        # Show menu below button
        button_rect = self.edit_btn.geometry()
        menu_pos = self.edit_btn.mapToGlobal(button_rect.bottomLeft())
        menu.exec_(menu_pos)
    
    def show_view_menu(self):
        """Show View menu popup"""
        from PyQt5.QtWidgets import QMenu
        
        menu = QMenu(self)
        menu.addAction('Report view', self.button_functions.view_report_view)
        menu.addAction('Signal view', self.button_functions.view_signal_view)
        menu.addAction('Event list', self.button_functions.view_event_list)
        menu.addAction('Quick start', self.button_functions.view_quick_start)
        menu.addSeparator()
        menu.addAction('Fullscreen', self.button_functions.view_fullscreen, 'F11')
        menu.addSeparator()
        menu.addAction('Zoom In', self.button_functions.view_zoom_in, 'Ctrl++')
        menu.addAction('Zoom Out', self.button_functions.view_zoom_out, 'Ctrl+-')
        menu.addAction('Reset Zoom', self.button_functions.view_reset_zoom, 'Ctrl+0')
        
        # Show menu below button
        button_rect = view_btn.geometry()
        menu_pos = view_btn.mapToGlobal(button_rect.bottomLeft())
        menu.exec_(menu_pos)
    
    def show_help_menu(self):
        """Show Help menu popup"""
        from PyQt5.QtWidgets import QMenu
        
        menu = QMenu(self)
        menu.addAction('Clinical Guide', self.button_functions.help_clinical_guide)
        menu.addAction('Patient instructions', self.button_functions.help_patient_instructions)
        menu.addAction('Program info', self.button_functions.help_program_info)
        menu.addAction('Recording info', self.button_functions.help_recording_info)
        menu.addAction('Device info', self.button_functions.help_device_info)
        menu.addSeparator()
        menu.addAction('Documentation', self.button_functions.help_documentation, 'F1')
        menu.addAction('About', self.button_functions.help_about)
        
        # Show menu below button
        button_rect = help_btn.geometry()
        menu_pos = help_btn.mapToGlobal(button_rect.bottomLeft())
        menu.exec_(menu_pos)
    
    def create_time_slider_bar(self):
        """Create time slider navigation bar with professional styling - same size as graph containers"""
        # Main container with same styling as graph containers
        main_container = QWidget()
        main_container.setObjectName("signalChartContainer")
        main_container.setMinimumHeight(35)  # Slightly bigger
        main_container.setMaximumHeight(35)  # Slightly bigger
        main_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # Apply professional double-shaded medical styling to container
        main_container.setStyleSheet("""
            QWidget#signalChartContainer {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.45 #f8fafc,
                    stop: 0.55 #f1f5f9,
                    stop: 1 #e2e8f0
                );
                border: 2px solid #cbd5e1;
                border-radius: 8px;
                margin: 2px;
            }
            QWidget#signalChartContainer:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.45 #f0f9ff,
                    stop: 0.55 #e0f2fe,
                    stop: 1 #bae6fd
                );
                border: 2px solid #3b82f6;
                box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
            }
        """)
        
        # Inner layout for the container
        container_layout = QHBoxLayout(main_container)
        container_layout.setContentsMargins(4, 3, 4, 3)  # Slightly bigger margins
        container_layout.setSpacing(6) # Good spacing
        
        # Time Position Label - smaller font
        time_label = QLabel("Time Nav:")
        time_label.setStyleSheet("font-size: 10px; font-weight: 700; color: #1e293b;")
        container_layout.addWidget(time_label)
        
        # Left navigation button - with clear arrow
        self.slider_left_btn = QPushButton("◀")
        self.slider_left_btn.setObjectName("sliderNavButton")
        self.slider_left_btn.setFixedHeight(20)  # Slightly bigger
        self.slider_left_btn.setFixedWidth(28)   # Slightly bigger
        # Apply clear arrow styling
        self.slider_left_btn.setStyleSheet("""
            QPushButton#sliderNavButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #dbeafe,
                    stop: 1 #bfdbfe
                );
                border: 2px solid #3b82f6;
                border-radius: 4px;
                color: #1e40af;
                font-size: 14px;
                font-weight: bold;
                text-align: center;
            }
            QPushButton#sliderNavButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #bfdbfe,
                    stop: 1 #93c5fd
                );
                border: 2px solid #2563eb;
                color: #1e3a8a;
            }
            QPushButton#sliderNavButton:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #dbeafe,
                    stop: 0.5 #93c5fd,
                    stop: 1 #60a5fa
                );
                border: 2px solid #1d4ed8;
                color: #1e3a8a;
            }
        """)
        self.slider_left_btn.clicked.connect(self.slider_navigate_backward)
        container_layout.addWidget(self.slider_left_btn)
        
        # Time slider - make it expand to fill available space
        self.time_slider = QSlider(Qt.Horizontal)
        self.time_slider.setObjectName("timeSlider")
        self.time_slider.setMinimum(0)
        self.time_slider.setMaximum(100)
        self.time_slider.setValue(0)
        self.time_slider.setFixedHeight(20)  # Slightly bigger height
        self.time_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # Apply custom styling to slider
        self.time_slider.setStyleSheet("""
            QSlider#timeSlider::groove:horizontal {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f1f5f9,
                    stop: 0.5 #e2e8f0,
                    stop: 1 #cbd5e1
                );
                border: 1px solid #94a3b8;
                border-radius: 4px;
                height: 8px;
                margin: 2px 0;
            }
            QSlider#timeSlider::handle:horizontal {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #3b82f6,
                    stop: 1 #1d4ed8
                );
                border: 1px solid #1e40af;
                border-radius: 6px;
                width: 16px;
                margin: -4px 0;
            }
            QSlider#timeSlider::handle:horizontal:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #dbeafe,
                    stop: 0.5 #60a5fa,
                    stop: 1 #2563eb
                );
                border: 1px solid #1e40af;
            }
            QSlider#timeSlider::handle:horizontal:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #93c5fd,
                    stop: 0.5 #3b82f6,
                    stop: 1 #1d4ed8
                );
                border: 1px solid #1e3a8a;
            }
        """)
        
        self.time_slider.valueChanged.connect(self.on_slider_changed)
        container_layout.addWidget(self.time_slider, stretch=1)  # Add stretch factor
        
        # Right navigation button - with clear arrow
        self.slider_right_btn = QPushButton("▶")
        self.slider_right_btn.setObjectName("sliderNavButton")
        self.slider_right_btn.setFixedHeight(20)  # Slightly bigger
        self.slider_right_btn.setFixedWidth(28)   # Slightly bigger
        # Apply clear arrow styling
        self.slider_right_btn.setStyleSheet("""
            QPushButton#sliderNavButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #dbeafe,
                    stop: 1 #bfdbfe
                );
                border: 2px solid #3b82f6;
                border-radius: 4px;
                color: #1e40af;
                font-size: 14px;
                font-weight: bold;
                text-align: center;
            }
            QPushButton#sliderNavButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #bfdbfe,
                    stop: 1 #93c5fd
                );
                border: 2px solid #2563eb;
                color: #1e3a8a;
            }
            QPushButton#sliderNavButton:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #dbeafe,
                    stop: 0.5 #93c5fd,
                    stop: 1 #60a5fa
                );
                border: 2px solid #1d4ed8;
                color: #1e3a8a;
            }
        """)
        self.slider_right_btn.clicked.connect(self.slider_navigate_forward)
        container_layout.addWidget(self.slider_right_btn)
        
        # Current time display - smaller
        self.slider_time_label = QLabel("0:00")
        self.slider_time_label.setObjectName("sliderTimeLabel")
        self.slider_time_label.setStyleSheet("""
            QLabel#sliderTimeLabel {
                background-color: #eff6ff;
                color: #1e40af;
                border: 1px solid #3b82f6;
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 10px;
                min-width: 40px;
            }
        """)
        self.slider_time_label.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(self.slider_time_label)
        
        # Add stretch to push everything to the left
        container_layout.addStretch()
        
        return main_container
    
    def slider_navigate_backward(self):
        """Navigate backward using slider buttons"""
        if hasattr(self.monitor_chart, 'spo2_full_data') and self.monitor_chart.spo2_full_data and len(self.monitor_chart.spo2_full_data[1]) > 0:
            # Step size equals the current time window size
            step_size = self.monitor_chart.current_time_window  # Move by exact time window size
            max_duration = len(self.monitor_chart.spo2_full_data[1]) / 10.0  # 10 samples per second
            
            # Move backward by step size
            self.monitor_chart.current_time_offset = max(0, self.monitor_chart.current_time_offset - step_size)
            self.monitor_chart.refresh_charts()
            self.update_slider_position()
            
            print(f"Dashboard slider backward to: {self.monitor_chart.current_time_offset:.1f}s (step: {step_size:.1f}s)")
    
    def slider_navigate_forward(self):
        """Navigate forward using slider buttons"""
        if hasattr(self.monitor_chart, 'spo2_full_data') and self.monitor_chart.spo2_full_data and len(self.monitor_chart.spo2_full_data[1]) > 0:
            # Step size equals the current time window size
            step_size = self.monitor_chart.current_time_window  # Move by exact time window size
            max_duration = len(self.monitor_chart.spo2_full_data[1]) / 10.0  # 10 samples per second
            max_offset = max_duration - self.monitor_chart.current_time_window
            
            # Move forward by step size
            self.monitor_chart.current_time_offset = min(max_offset, self.monitor_chart.current_time_offset + step_size)
            self.monitor_chart.refresh_charts()
            self.update_slider_position()
            
            print(f"Dashboard slider forward to: {self.monitor_chart.current_time_offset:.1f}s (step: {step_size:.1f}s)")
    
    def on_slider_changed(self, value):
        """Handle slider value change"""
        if hasattr(self.monitor_chart, 'spo2_full_data') and self.monitor_chart.spo2_full_data and len(self.monitor_chart.spo2_full_data[1]) > 0:
            # Calculate maximum possible time based on data length
            max_duration = len(self.monitor_chart.spo2_full_data[1]) / 10.0  # 10 samples per second
            
            if max_duration > self.monitor_chart.current_time_window:
                # Calculate time offset from slider value (0-100)
                slider_progress = value / 100.0
                max_offset = max_duration - self.monitor_chart.current_time_window
                self.monitor_chart.current_time_offset = slider_progress * max_offset
                
                # Refresh charts and update labels
                self.monitor_chart.refresh_charts()
                self.update_slider_position()
                print(f"Dashboard slider changed to: {value}% (time: {self.monitor_chart.current_time_offset:.1f}s)")
    
    def update_slider_position(self):
        """Update slider position based on current time offset"""
        if self.time_slider and hasattr(self.monitor_chart, 'spo2_full_data') and self.monitor_chart.spo2_full_data and len(self.monitor_chart.spo2_full_data[1]) > 0:
            # Calculate maximum possible time based on data length
            max_duration = len(self.monitor_chart.spo2_full_data[1]) / 10.0  # 10 samples per second
            
            # Calculate slider value (0-100) based on current position
            if max_duration > self.monitor_chart.current_time_window:
                max_offset = max_duration - self.monitor_chart.current_time_window
                slider_progress = self.monitor_chart.current_time_offset / max_offset
                slider_value = int(slider_progress * 100)
                slider_value = max(0, min(100, slider_value))  # Clamp between 0-100
                
                print(f"Debug: time_offset={self.monitor_chart.current_time_offset:.1f}s, max_duration={max_duration:.1f}s, max_offset={max_offset:.1f}s, progress={slider_progress:.3f}, slider_value={slider_value}")
                
                # Block signals to prevent recursive calls
                self.time_slider.blockSignals(True)
                self.time_slider.setValue(slider_value)
                self.time_slider.blockSignals(False)
                
                print(f"Slider position updated: {slider_value}% (time: {self.monitor_chart.current_time_offset:.1f}s)")
            
            # Update slider time label with HH:MM:SS format
            hours = int(self.monitor_chart.current_time_offset // 3600)
            minutes = int((self.monitor_chart.current_time_offset % 3600) // 60)
            seconds = int(self.monitor_chart.current_time_offset % 60)
            self.slider_time_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
    
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
    
    def update_logo_size(self):
        """Update logo size based on window dimensions"""
        if not self.logo_frame:
            return
            
        # Calculate logo size based on window width (adaptive scaling)
        window_width = self.width()
        base_size = 64  # Base size for 1200px window
        
        # Scale factor: larger windows get larger logos
        if window_width >= 1600:
            scale_factor = 1.5  # 50% larger for wide screens
        elif window_width >= 1400:
            scale_factor = 1.3  # 30% larger
        elif window_width >= 1200:
            scale_factor = 1.1  # 10% larger
        elif window_width >= 1000:
            scale_factor = 1.0  # Base size
        else:
            scale_factor = 0.8  # Smaller for compact windows
        
        
        # Calculate new size
        new_size = int(base_size * scale_factor)
        new_size = max(40, min(new_size, 100))  # Clamp between 40px and 100px
        
        # Apply new size
        self.logo_frame.setFixedSize(new_size, new_size)
        
        # Update font size for text fallback
        font_size = int(new_size * 0.8)  # Font size 80% of container size
        self.current_font_size = font_size
        
        print(f"Logo size updated to: {new_size}x{new_size}px (font: {font_size}px)")
    
    def update_logo_content(self):
        """Update logo content (image or text) with current size"""
        if not self.logo_label or not hasattr(self, 'current_font_size'):
            return
            
        # Try to load the logo image
        if os.path.exists(self.logo_path):
            pixmap = QPixmap(self.logo_path)
            if not pixmap.isNull():
                # Scale image to fit current logo frame size
                frame_size = self.logo_frame.width()
                image_size = int(frame_size * 0.9)  # 90% of frame size
                scaled_pixmap = pixmap.scaled(image_size, image_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.logo_label.setPixmap(scaled_pixmap)
                self.logo_label.setText("")  # Clear any text
                return
        
        # Fallback to text if image doesn't exist or fails to load
        self.logo_label.setText("SS")
        font_size = getattr(self, 'current_font_size', 52)
        self.logo_label.setStyleSheet(f"font-size: {font_size}px; font-weight: bold; color: #111827;")
    
    def resizeEvent(self, event):
        """Handle window resize event to update logo size"""
        super().resizeEvent(event)
        
        # Update logo size on window resize
        if self.logo_frame:
            self.update_logo_size()
            self.update_logo_content()
