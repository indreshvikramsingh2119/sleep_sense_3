"""
Sleep Sense Dashboard - Main Dashboard Component
"""

import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QSplitter, QSizePolicy, QScrollArea,
    QSlider, QPushButton, QMenuBar, QMenu, QAction, QComboBox, QToolBar, QFileDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QPixmap

from .patient_info_widget import PatientInfoWidget
from .sleep_monitor_chart import SleepMonitorChart
from .database_window import DatabaseWindow
from .archive_window import ArchiveWindow
from .event_window import EventWindow
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
        self.toolbar = self.create_professional_toolbar()
        top_layout.addWidget(self.toolbar)
        
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
        patient_panel.setMinimumWidth(380)  # Further increased minimum width
        patient_panel.setMaximumWidth(450) # Further increased maximum width
        patient_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        patient_layout = QVBoxLayout(patient_panel)
        patient_layout.setContentsMargins(2, 2, 2, 2)  # Reduced margins for more left shift
        
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
        
        # Auto-load SpO2 data for playback testing
        self.auto_load_spo2_data()
        
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
        
        # Add vertical divider line
        divider2 = QFrame()
        divider2.setFrameShape(QFrame.VLine)
        divider2.setFrameShadow(QFrame.Sunken)
        divider2.setStyleSheet("""
            QFrame {
                background-color: #d1d5db;
                color: #d1d5db;
                border: none;
                margin: 0 4px;
            }
        """)
        divider2.setFixedWidth(1)
        controls_layout.addWidget(divider2)
        
        # Screenshot Button
        self.btn_screenshot = QPushButton("📷")
        self.btn_screenshot.setObjectName("screenshotButton")
        self.btn_screenshot.setFixedSize(30, 22)
        self.btn_screenshot.setToolTip("Take Screenshot")
        self.btn_screenshot.setStatusTip("Capture entire application window")
        self.btn_screenshot.clicked.connect(self.take_screenshot)
        self.btn_screenshot.setStyleSheet("""
            QPushButton#screenshotButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #f8fafc,
                    stop: 1 #f1f5f9
                );
                border: 1px solid #d1d5db;
                border-radius: 4px;
                color: #374151;
                font-size: 14px;
                font-weight: bold;
                text-align: center;
            }
            QPushButton#screenshotButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #dbeafe,
                    stop: 1 #bfdbfe
                );
                border: 1px solid #3b82f6;
                color: #1e40af;
            }
            QPushButton#screenshotButton:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f8fafc,
                    stop: 0.5 #e2e8f0,
                    stop: 1 #cbd5e1
                );
                border: 1px solid #94a3b8;
                color: #1e293b;
            }
        """)
        controls_layout.addWidget(self.btn_screenshot)
        
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
        # Check if monitor chart has selection active and block if needed
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return
        
        if hasattr(self.monitor_chart, 'spo2_full_data') and self.monitor_chart.spo2_full_data and len(self.monitor_chart.spo2_full_data[1]) > 0:
            # Step size equals the current time window size
            step_size = self.monitor_chart.current_time_window  
            max_duration = len(self.monitor_chart.spo2_full_data[1]) / 10.0 
            
            # Move backward by step size
            self.monitor_chart.current_time_offset = max(0, self.monitor_chart.current_time_offset - step_size)
            self.monitor_chart.refresh_charts()
            self.update_slider_position()
            
            print(f"Dashboard slider backward to: {self.monitor_chart.current_time_offset:.1f}s (step: {step_size:.1f}s)")
    
    def slider_navigate_forward(self):
        """Navigate forward using slider buttons"""
        # Check if monitor chart has selection active and block if needed
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return
        
        if hasattr(self.monitor_chart, 'spo2_full_data') and self.monitor_chart.spo2_full_data and len(self.monitor_chart.spo2_full_data[1]) > 0:
            # Step size equals the current time window size
            step_size = self.monitor_chart.current_time_window  
            max_duration = len(self.monitor_chart.spo2_full_data[1]) / 10.0  
            max_offset = max_duration - self.monitor_chart.current_time_window
            
            # Move forward by step size
            self.monitor_chart.current_time_offset = min(max_offset, self.monitor_chart.current_time_offset + step_size)
            
            # ✅ FORCE VIEWBOX UPDATE AND PLOT REDRAW
            for i in range(self.monitor_chart.charts_layout.count()):
                container = self.monitor_chart.charts_layout.itemAt(i).widget()
                if hasattr(container, 'plot_widget'):
                    pw = container.plot_widget
                    
                    # Force X-axis range update
                    start = 0
                    end = self.monitor_chart.current_time_window
                    pw.setXRange(start, end, padding=0)
                    
                    # Force redraw
                    pw.getViewBox().update()
                    pw.repaint()
                    print(f"Updated ViewBox range to {start} → {end} for {pw.chart_name}")
            
            # ✅ DELAYED OVERLAY RENDER (IMPORTANT)
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, self.monitor_chart.render_dynamic_selections)
            
            self.monitor_chart.refresh_charts()
            self.update_slider_position()
            
            print(f"Dashboard slider forward to: {self.monitor_chart.current_time_offset:.1f}s (step: {step_size:.1f}s)")
    
    def on_slider_changed(self, value):
        """Handle slider value change"""
        if hasattr(self.monitor_chart, 'spo2_full_data') and self.monitor_chart.spo2_full_data and len(self.monitor_chart.spo2_full_data[1]) > 0:
            # Calculate maximum time based on data length
            max_duration = len(self.monitor_chart.spo2_full_data[1]) / 10.0  
            
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
            max_duration = len(self.monitor_chart.spo2_full_data[1]) / 10.0  
            
            # Calculate slider value (0-100) based on current position
            if max_duration > self.monitor_chart.current_time_window:
                max_offset = max_duration - self.monitor_chart.current_time_window
                slider_progress = self.monitor_chart.current_time_offset / max_offset
                slider_value = int(slider_progress * 100)
                slider_value = max(0, min(100, slider_value))  
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
        
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        qss_file = os.path.join(script_dir, "sleep_sense_medical_white.qss")
        
        # Start with toolbar styles
        stylesheet = get_toolbar_qss_styles()
        
        
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
        self.btn_download_data.setEnabled(False)  
        toolbar.addWidget(self.btn_download_data)
        
        
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
        
        # Extended Database Options (initially hidden - using QAction)
        from PyQt5.QtGui import QIcon
        
        self.action_patient_record = QAction(QIcon(os.path.join(script_dir, icons[4]["icon"])), "Patient Record Card", self)
        self.action_patient_record.setToolTip("Patient Record Card")
        self.action_patient_record.setStatusTip("View patient record card")
        self.action_patient_record.triggered.connect(self.open_report_view)
        self.action_patient_record.setVisible(False)
        self.action_patient_record.setEnabled(True)
        toolbar.addAction(self.action_patient_record)
        
        self.action_report_view = QAction(QIcon(os.path.join(script_dir, icons[5]["icon"])), "Report View", self)
        self.action_report_view.setToolTip("Report View")
        self.action_report_view.setStatusTip("View ECG/Sleep reports")
        self.action_report_view.triggered.connect(self.open_report_view)
        self.action_report_view.setVisible(False)
        self.action_report_view.setEnabled(True)
        toolbar.addAction(self.action_report_view)
        
        self.action_event_list = QAction(QIcon(os.path.join(script_dir, icons[7]["icon"])), "Event List", self)
        self.action_event_list.setToolTip("Event List")
        self.action_event_list.setStatusTip("View detected events")
        self.action_event_list.triggered.connect(self.open_event_list)
        self.action_event_list.setVisible(False)
        self.action_event_list.setEnabled(True)
        toolbar.addAction(self.action_event_list)
        
        return toolbar
    
    # Toolbar Button Callback Methods
    def go_to_previous(self):
        """Go to previous time window"""
        print("Previous button clicked")
        self.hide_extended_buttons()
        if hasattr(self.monitor_chart, 'spo2_full_data') and self.monitor_chart.spo2_full_data and len(self.monitor_chart.spo2_full_data[1]) > 0:
            step_size = self.monitor_chart.current_time_window
            self.monitor_chart.current_time_offset = max(0, self.monitor_chart.current_time_offset - step_size)
            self.monitor_chart.refresh_charts()
            self.update_slider_position()
            print(f"Toolbar previous: offset={self.monitor_chart.current_time_offset:.1f}s")
    
    def go_to_next(self):
        """Go to next time window"""
        print("Next button clicked")
        self.hide_extended_buttons()
        if hasattr(self.monitor_chart, 'spo2_full_data') and self.monitor_chart.spo2_full_data and len(self.monitor_chart.spo2_full_data[1]) > 0:
            step_size = self.monitor_chart.current_time_window
            max_duration = len(self.monitor_chart.spo2_full_data[1]) / 10.0
            max_offset = max_duration - self.monitor_chart.current_time_window
            self.monitor_chart.current_time_offset = min(max_offset, self.monitor_chart.current_time_offset + step_size)
            self.monitor_chart.refresh_charts()
            self.update_slider_position()
            print(f"Toolbar next: offset={self.monitor_chart.current_time_offset:.1f}s") 
    
    def prepare_device(self):
        """Initialize and connect device"""
        print("Prepare Device button clicked")
        self.hide_extended_buttons()
        # TODO: Implement device preparation logic
   
        self.btn_download_data.setEnabled(True)
    
    def download_data(self):
        """Download data from device"""
        # Check if monitor chart has selection active and block if needed
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return
        
        print("Download Data button clicked")
        # TODO: Implement data download logic
    
    def open_database(self):
        """Open patient database as modeless window and show extended buttons"""
        # Check if monitor chart has selection active and block if needed
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return
        
        print("Database button clicked")
        # Show extended buttons immediately
        self.action_patient_record.setVisible(True)
        self.action_report_view.setVisible(True)
        self.action_event_list.setVisible(True)
        # Open database window as modeless (non-blocking)
        self.database_window = DatabaseWindow(self)
        self.database_window.show()
    
    def hide_extended_buttons(self):
        """Hide extended database buttons"""
        self.action_patient_record.setVisible(False)
        self.action_report_view.setVisible(False)
        self.action_event_list.setVisible(False)  
    
    def open_archive(self):
        """Access archived records as modal dialog"""
        # Check if monitor chart has selection active and block if needed
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return
        
        print("Archive button clicked")
        self.hide_extended_buttons()
        self.archive_window = ArchiveWindow(self)
        self.archive_window.exec_()  # Modal dialog
    
    def open_report_view(self):
        """View ECG/Sleep reports - Opens Patient Record Form as modal dialog"""
        # Check if monitor chart has selection active and block if needed
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return
        
        print("Report View button clicked")
        # Import the patient record form
        from .patient_record_form import PatientRecordForm
        
        # Create and show the patient record form as modal dialog
        self.patient_record_form = PatientRecordForm(self)
        self.patient_record_form.exec_()  # Modal dialog
    
    def load_patient_data(self, patient_data):
        """Load patient data from database and display in dashboard"""
        print(f"Loading patient data: {patient_data['last_name']} {patient_data['first_name']}")
        
        # Create patient ID string for display
        patient_id_str = patient_data.get('patient_id', str(patient_data.get('id', '--------')))
        
        # Set patient ID in monitor chart
        if hasattr(self, 'monitor_chart'):
            self.monitor_chart.set_patient_id(patient_id_str)
        
        # Update patient info widget
        if hasattr(self, 'patient_info'):
            self.patient_info.set_patient_data({
                'last_name': patient_data.get('last_name', ''),
                'first_name': patient_data.get('first_name', ''),
                'dob': patient_data.get('dob', ''),
                'patient_id': patient_id_str
            })
        
        print(f"Patient data loaded successfully in dashboard")
    
    def open_signal_view(self):
        """View live physiological signals"""
        # Check if monitor chart has selection active and block if needed
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return
        
        print("Signal View button clicked")
        # TODO: Implement signal view logic
    
    def open_event_list(self):
        """View detected events"""
        # Check if monitor chart has selection active and block if needed
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return
        
        print("Event List button clicked")
        self.event_window = EventWindow(self)
        self.event_window.exec_()  # Modal dialog
    
    def take_screenshot(self):
        """Take a screenshot of the entire application"""
        try:
            # Get the main window
            from PyQt5.QtWidgets import QApplication
            from PyQt5.QtGui import QPixmap, QScreen
            from datetime import datetime
            
            # Capture the entire application window
            screen = QApplication.primaryScreen().grabWindow(self.winId())
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sleep_sense_screenshot_{timestamp}.png"
            
            # Save dialog
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Screenshot",
                filename,
                "PNG Files (*.png);;All Files (*)"
            )
            
            if file_path:
                screen.save(file_path, "PNG")
                QMessageBox.information(self, "Screenshot Saved", 
                                   f"Screenshot saved to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Screenshot Error", 
                               f"Failed to take screenshot:\n{str(e)}")
    
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
    
    def auto_load_spo2_data(self):
        """Automatically load SpO2 data for playback testing"""
        import os
        try:
            # Try to load the sample SpO2 data file
            csv_path = os.path.join(os.getcwd(), "extracted_data", "spo2_6hr_10Hz_data (1).csv")
            if os.path.exists(csv_path):
                print(f"🎬 Auto-loading SpO2 data from: {csv_path}")
                self.monitor_chart.load_spo2_data(csv_path)
                print("✅ SpO2 data loaded successfully - Playback ready!")
            else:
                print(f"⚠️ Sample data file not found: {csv_path}")
                print("💡 Playback controls will work but need data to be loaded manually")
        except Exception as e:
            print(f"❌ Error auto-loading SpO2 data: {e}")
            print("💡 Use File → Load Data to load SpO2 data for playback")


