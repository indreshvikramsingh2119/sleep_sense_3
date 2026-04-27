"""
Sleep Sense Dashboard - Main Dashboard Component
"""

import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QSplitter, QSizePolicy, QScrollArea,
    QSlider, QPushButton, QMenuBar, QMenu, QAction, QComboBox, QToolBar
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QPixmap

from .patient_info_widget import PatientInfoWidget
from .sleep_monitor_chart import SleepMonitorChart
from .database_window import DatabaseWindow
from .archive_window import ArchiveWindow
from ..utils.toolbar_utils import create_toolbar_button, get_icon_definitions, get_toolbar_qss_styles
from src.utils.button_functions import ButtonFunctions


class SleepSenseDashboard(QMainWindow):
    
    """Main Sleep Sense Dashboard Window"""
    
    def __init__(self):
        super().__init__()
        self.logo_frame = None
        self.logo_label = None
        # create ButtonFunctions helper and attach to dashboard
        self.button_functions = ButtonFunctions(self)
        self.init_ui()
        self.load_stylesheet()
        
    def init_ui(self):
        self.setWindowTitle("")
        
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
        menu_container.setMinimumHeight(50)
        menu_container.setMaximumHeight(55)
        menu_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        menu_layout = QHBoxLayout(menu_container)
        menu_layout.setContentsMargins(8, 8, 8, 8)
        menu_layout.setSpacing(4)
        
        # Create custom menu buttons
        self.button_functions.create_custom_menu_buttons(menu_layout)
        
        main_layout.addWidget(menu_container)
        
        # Create a horizontal layout for toolbar and controls
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)
        
        # Professional Icon Toolbar
        toolbar = self.create_professional_toolbar()
        top_layout.addWidget(toolbar)
        
        # Add spacer to push controls to the right
        top_layout.addStretch()
        
        # Controls Container (Time Window, Hidden Graphs) - Right Side
        controls_container = self.create_controls_container()
        top_layout.addWidget(controls_container)
        
        # Add the top layout to main layout
        main_layout.addLayout(top_layout)
        
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
        
        # Set dashboard controls reference in chart
        self.monitor_chart.set_dashboard_controls(self.time_window_dropdown, self.hidden_graphs_dropdown)
        
        # Connect dashboard controls to chart functionality
        self.time_window_dropdown.currentIndexChanged.connect(self.on_time_window_changed)
        self.hidden_graphs_dropdown.currentIndexChanged.connect(self.restore_hidden_graph)
        
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
        
    def create_controls_container(self):
        """Create controls container with Time Window and Hidden Graphs"""
        controls_container = QFrame()
        controls_container.setObjectName("controlsContainer")
        controls_container.setStyleSheet("""
            QFrame#controlsContainer {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 4px;
                margin: 4px 8px;
            }
        """)
        controls_layout = QHBoxLayout(controls_container)
        controls_layout.setContentsMargins(8, 4, 8, 4)
        controls_layout.setSpacing(8)
        
        # Time Window Dropdown
        time_window_label = QLabel("Time Window:")
        time_window_label.setStyleSheet("font-size: 11px; font-weight: 600; color: #374151;")
        controls_layout.addWidget(time_window_label)
        
        self.time_window_dropdown = QComboBox()
        self.time_window_dropdown.setObjectName("timeWindowDropdown")
        self.time_window_dropdown.setFixedHeight(22)
        self.time_window_dropdown.setMinimumWidth(60)
        
        # Add time window options (in seconds)
        time_windows = [
            ("10s", 10),
            ("30s", 30), 
            ("1m", 60),
            ("2m", 120),
            ("5m", 300),
            ("10m", 600),
        ]
        
        for label, value in time_windows:
            self.time_window_dropdown.addItem(label, value)
        
        # Set default selection to 1m (index 2)
        self.time_window_dropdown.setCurrentIndex(2)
        
        controls_layout.addWidget(self.time_window_dropdown)
        
        # Add vertical divider line
        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setFrameShadow(QFrame.Sunken)
        divider.setStyleSheet("""
            QFrame {
                background-color: #d1d5db;
                color: #d1d5db;
                border: none;
                margin: 0 4px;
            }
        """)
        divider.setFixedWidth(1)
        controls_layout.addWidget(divider)
        
        # Hidden Graphs Dropdown
        hidden_graphs_label = QLabel("Hidden Graphs:")
        hidden_graphs_label.setStyleSheet("font-size: 11px; font-weight: 600; color: #374151;")
        controls_layout.addWidget(hidden_graphs_label)
        
        self.hidden_graphs_dropdown = QComboBox()
        self.hidden_graphs_dropdown.setObjectName("hiddenGraphsDropdown")
        self.hidden_graphs_dropdown.setFixedHeight(22)
        self.hidden_graphs_dropdown.setMinimumWidth(90)
        self.hidden_graphs_dropdown.addItem("Select to restore...")
        self.hidden_graphs_dropdown.setEnabled(False)
        
        controls_layout.addWidget(self.hidden_graphs_dropdown)
        
        controls_layout.addStretch()
        
        return controls_container
    
        
    def on_time_window_changed(self, index):
        """Handle time window dropdown change"""
        if hasattr(self, 'monitor_chart') and self.monitor_chart:
            # Get the value from dropdown item data
            seconds = self.time_window_dropdown.itemData(index)
            print(f"Dashboard: Time window changed to: {self.time_window_dropdown.itemText(index)} ({seconds} seconds)")
            
            # Update the chart's time window
            self.monitor_chart.set_time_window(seconds)
    
    def restore_hidden_graph(self, index):
        """Handle hidden graphs dropdown change"""
        if hasattr(self, 'monitor_chart') and self.monitor_chart:
            # Get the graph name from dropdown
            graph_name = self.hidden_graphs_dropdown.itemText(index)
            
            # Check if graph exists in hidden graphs
            if graph_name not in self.monitor_chart.hidden_graphs:
                print(f"Dashboard: Graph '{graph_name}' not found in hidden graphs")
                return
            
            print(f"Dashboard: Restoring hidden graph '{graph_name}'")
            
            # Call the chart's restore method
            self.monitor_chart.restore_hidden_graph(index)
    
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
            # Calculate maximum time based on data length
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
                
                # Block signals to prevent recursive calls
                self.time_slider.blockSignals(True)
                self.time_slider.setValue(slider_value)
                self.time_slider.blockSignals(False)
        
        # Update slider time label with HH:MM:SS format (always execute)
        hours = int(self.monitor_chart.current_time_offset // 3600)
        minutes = int((self.monitor_chart.current_time_offset % 3600) // 60)
        seconds = int(self.monitor_chart.current_time_offset % 60)
        time_text = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        self.slider_time_label.setText(time_text)
    
    def load_stylesheet(self):
        """Load QSS stylesheet"""
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        qss_file = os.path.join(script_dir, "sleep_sense_medical_white.qss")
        
        # Start with toolbar styles
        stylesheet = get_toolbar_qss_styles()
        
        # Add existing stylesheet if it exists
        if os.path.exists(qss_file):
            with open(qss_file, 'r') as f:
                stylesheet += f.read()
        else:
            print(f"Warning: Stylesheet file '{qss_file}' not found!")
        
        self.setStyleSheet(stylesheet)
    
        
    def create_professional_toolbar(self):
        """Create professional icon toolbar with grouped buttons"""
        toolbar = QToolBar("MainToolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(32, 32))
        toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        toolbar.setMinimumHeight(50)
        
        # Get icon definitions
        icons = get_icon_definitions()
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Navigation Group: Previous / Next
        self.btn_previous = create_toolbar_button(
            os.path.join(script_dir, icons[0]["icon"]),
            icons[0]["tooltip"],
            icons[0]["status_tip"],
            self.go_to_previous
        )
        toolbar.addWidget(self.btn_previous)
        
        self.btn_next = create_toolbar_button(
            os.path.join(script_dir, icons[1]["icon"]),
            icons[1]["tooltip"],
            icons[1]["status_tip"],
            self.go_to_next
        )
        toolbar.addWidget(self.btn_next)
        
        toolbar.addSeparator()
        
        # Device Group: Prepare / Download
        self.btn_prepare_device = create_toolbar_button(
            os.path.join(script_dir, icons[2]["icon"]),
            icons[2]["tooltip"],
            icons[2]["status_tip"],
            self.prepare_device
        )
        toolbar.addWidget(self.btn_prepare_device)
        
        self.btn_download_data = create_toolbar_button(
            os.path.join(script_dir, icons[3]["icon"]),
            icons[3]["tooltip"],
            icons[3]["status_tip"],
            self.download_data
        )
        self.btn_download_data.setEnabled(False)  # Disabled until device connected
        toolbar.addWidget(self.btn_download_data)
        
        toolbar.addSeparator()
        
        # Views Group: Signal / Report
        self.btn_signal_view = create_toolbar_button(
            os.path.join(script_dir, icons[6]["icon"]),
            icons[6]["tooltip"],
            icons[6]["status_tip"],
            self.open_signal_view
        )
        toolbar.addWidget(self.btn_signal_view)
        
        self.btn_report_view = create_toolbar_button(
            os.path.join(script_dir, icons[5]["icon"]),
            icons[5]["tooltip"],
            icons[5]["status_tip"],
            self.open_report_view
        )
        toolbar.addWidget(self.btn_report_view)
        
        toolbar.addSeparator()
        
        # Data Group: Database / Archive
        self.btn_database = create_toolbar_button(
            os.path.join(script_dir, icons[4]["icon"]),
            icons[4]["tooltip"],
            icons[4]["status_tip"],
            self.open_database
        )
        toolbar.addWidget(self.btn_database)
        
        self.btn_archive = create_toolbar_button(
            os.path.join(script_dir, icons[8]["icon"]),
            icons[8]["tooltip"],
            icons[8]["status_tip"],
            self.open_archive
        )
        toolbar.addWidget(self.btn_archive)
        
        toolbar.addSeparator()
        
        # Event List
        self.btn_event_list = create_toolbar_button(
            os.path.join(script_dir, icons[7]["icon"]),
            icons[7]["tooltip"],
            icons[7]["status_tip"],
            self.open_event_list
        )
        toolbar.addWidget(self.btn_event_list)
        
        return toolbar
    
    # Toolbar Button Callback Methods
    def go_to_previous(self):
        """Go to previous record/page"""
        print("Previous button clicked")
        # TODO: Implement navigation to previous record
    
    def go_to_next(self):
        """Go to next record/page"""
        print("Next button clicked")
        # TODO: Implement navigation to next record
    
    def prepare_device(self):
        """Initialize and connect device"""
        print("Prepare Device button clicked")
        # TODO: Implement device preparation logic
        # Enable download button after device is prepared
        self.btn_download_data.setEnabled(True)
    
    def download_data(self):
        """Download data from device"""
        print("Download Data button clicked")
        # TODO: Implement data download logic
    
    def open_database(self):
        """Open patient database as modal dialog"""
        print("Database button clicked")
        self.database_window = DatabaseWindow(self)
        self.database_window.exec_()  # Modal dialog
    
    def open_report_view(self):
        """View ECG/Sleep reports - Opens Patient Record Form as modal dialog"""
        print("Report View button clicked")
        # Import the patient record form
        from .patient_record_form import PatientRecordForm
        
        # Create and show the patient record form as modal dialog
        self.patient_record_form = PatientRecordForm(self)
        self.patient_record_form.exec_()  # Modal dialog
    
    def open_signal_view(self):
        """View live physiological signals"""
        print("Signal View button clicked")
        # TODO: Implement signal view logic
    
    def open_event_list(self):
        """View detected events"""
        print("Event List button clicked")
        # TODO: Implement event list logic
    
    def open_archive(self):
        """Access archived records as modal dialog"""
        print("Archive button clicked")
        self.archive_window = ArchiveWindow(self)
        self.archive_window.exec_()  # Modal dialog
    
    def create_menubar(self):
        """Create menubar with File and View menus"""
        menubar = self.menuBar()
        menubar.setObjectName("mainMenuBar")
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        # View menu and wire to handlers in button_functions
        view_menu = menubar.addMenu('View')

        fullscreen_action = QAction('Fullscreen', self)
        fullscreen_action.setCheckable(True)
        fullscreen_action.setStatusTip('Toggle fullscreen')
        fullscreen_action.triggered.connect(self.button_functions.view_fullscreen)
        view_menu.addAction(fullscreen_action)

        view_menu.addSeparator()

        zoom_in_action = QAction('Zoom In', self)
        zoom_in_action.setShortcut('Ctrl++')
        zoom_in_action.triggered.connect(self.button_functions.view_zoom_in)
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction('Zoom Out', self)
        zoom_out_action.setShortcut('Ctrl+-')
        zoom_out_action.triggered.connect(self.button_functions.view_zoom_out)
        view_menu.addAction(zoom_out_action)

        reset_zoom_action = QAction('Reset Zoom', self)
        reset_zoom_action.setShortcut('Ctrl+0')
        reset_zoom_action.triggered.connect(self.button_functions.view_reset_zoom)
        view_menu.addAction(reset_zoom_action)

        view_menu.addSeparator()

        report_view_action = QAction('Report view', self)
        report_view_action.triggered.connect(self.button_functions.view_report_view)
        view_menu.addAction(report_view_action)

        signal_view_action = QAction('Signal view', self)
        signal_view_action.triggered.connect(self.button_functions.view_signal_view)
        view_menu.addAction(signal_view_action)

        event_list_action = QAction('Event list', self)
        event_list_action.triggered.connect(self.button_functions.view_event_list)
        view_menu.addAction(event_list_action)

        quick_start_action = QAction('Quick start', self)
        quick_start_action.triggered.connect(self.button_functions.view_quick_start)
        view_menu.addAction(quick_start_action)
        
        return menubar


