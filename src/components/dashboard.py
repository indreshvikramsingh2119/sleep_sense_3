"""
Sleep Sense Dashboard - Main Dashboard Component
"""

import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QSplitter, QSizePolicy, QScrollArea,
    QSlider, QPushButton
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap

from .patient_info_widget import PatientInfoWidget
from .sleep_monitor_chart import SleepMonitorChart


class SleepSenseDashboard(QMainWindow):
    
    """Main Sleep Sense Dashboard Window"""
    
    def __init__(self):
        super().__init__()
        self.logo_frame = None
        self.logo_label = None
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
        
        # Connect dashboard slider to chart navigation updates
        self.monitor_chart.time_position_updated.connect(self.update_slider_position)
        
        chart_layout.addWidget(self.monitor_chart)
        
        splitter.addWidget(chart_panel)
        splitter.setSizes([300, 1000]) # Initial sizes, will be adjusted by policies
        splitter.setStretchFactor(0, 0) # Left panel takes its preferred size, doesn't stretch
        splitter.setStretchFactor(1, 1) # Right panel takes all available extra space
        
        content_layout.addWidget(splitter)
        
        # Set content widget to scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # Time Slider Navigation Bar at Bottom
        time_slider_bar = self.create_time_slider_bar()
        main_layout.addWidget(time_slider_bar)
        
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
    
    def create_time_slider_bar(self):
        """Create time slider navigation bar with professional styling"""
        slider_container = QFrame()
        slider_container.setObjectName("timeSliderContainer")
        slider_container.setMinimumHeight(60)
        slider_container.setMaximumHeight(70)
        slider_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        layout = QHBoxLayout(slider_container)
        layout.setContentsMargins(8, 8, 8, 8)  # Reduced margins for more width
        layout.setSpacing(12)
        
        # Time Position Label
        time_label = QLabel("Time Navigation:")
        time_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #1e293b;")
        layout.addWidget(time_label)
        
        # Left navigation button
        self.slider_left_btn = QPushButton("◀")
        self.slider_left_btn.setObjectName("sliderNavButton")
        self.slider_left_btn.setFixedHeight(32)
        self.slider_left_btn.setFixedWidth(40)
        self.slider_left_btn.clicked.connect(self.slider_navigate_backward)
        layout.addWidget(self.slider_left_btn)
        
        # Time slider - make it expand to fill available space
        self.time_slider = QSlider(Qt.Horizontal)
        self.time_slider.setObjectName("timeSlider")
        self.time_slider.setMinimum(0)
        self.time_slider.setMaximum(100)
        self.time_slider.setValue(0)
        self.time_slider.setFixedHeight(28)
        self.time_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.time_slider.valueChanged.connect(self.on_slider_changed)
        layout.addWidget(self.time_slider, stretch=1)  # Add stretch factor
        
        # Right navigation button
        self.slider_right_btn = QPushButton("▶")
        self.slider_right_btn.setObjectName("sliderNavButton")
        self.slider_right_btn.setFixedHeight(32)
        self.slider_right_btn.setFixedWidth(40)
        self.slider_right_btn.clicked.connect(self.slider_navigate_forward)
        layout.addWidget(self.slider_right_btn)
        
        # Current time display
        self.slider_time_label = QLabel("0:00")
        self.slider_time_label.setObjectName("sliderTimeLabel")
        self.slider_time_label.setStyleSheet("""
            QLabel#sliderTimeLabel {
                background-color: #eff6ff;
                color: #1e40af;
                border: 1px solid #3b82f6;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 13px;
                min-width: 60px;
            }
        """)
        self.slider_time_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.slider_time_label)
        
        # Add stretch to push everything to the left
        layout.addStretch()
        
        return slider_container
    
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
