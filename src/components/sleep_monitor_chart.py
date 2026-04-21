


"""
Sleep Monitor Chart Widget - Sleep Monitoring Chart Component
"""

import os
import json
import numpy as np
import pandas as pd
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QMessageBox, QMenu, QAction, QScrollArea, QSizePolicy, QSlider
)
from PyQt5.QtCore import Qt, QTimer, QTime, pyqtSignal, QPoint, QRect, QMimeData
from PyQt5.QtGui import QFont, QIcon, QPixmap, QDrag, QPainter, QPen
import pyqtgraph as pg
from .custom_viewbox import CustomViewBox


class SleepMonitorChart(QWidget):
    """Sleep Monitoring Chart Widget"""
    raw_data_saved = pyqtSignal(str, str)  # file_path, timestamp_iso
    time_position_updated = pyqtSignal()  # Signal when time position changes
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_time = QTime.currentTime()
        self.patient_id = "--------"
        self.current_time_window = 60  # Default to 60 seconds
        self.is_playing = False
        self.playback_speed = 1.0
        self.play_pause_btn = None  # Initialize button reference
        self.hidden_graphs_dropdown = None  # Initialize dropdown reference
        self.hidden_graphs = {}  # Store hidden graph data: {name: {container, plot_curve, color, frequency, amplitude, offset, position}}
        self.graph_order = []  # Track original order of graphs: [name1, name2, ...]
        self.dragged_graph = None  # Track currently dragged graph
        self.manual_drag_container = None  # Track manually dragging container
        self.manual_drag_graph_name = None  # Track manually dragging graph name
        self.manual_drag_start_height = None  # Store original height during manual drag
        self.manual_drag_start_y = None  # Store starting Y position during manual drag
        
        # Time window data management
        self.spo2_full_data = None  # Store full SpO2 data (time, spo2)
        self.current_time_offset = 0  # Current starting time for window
        
        # Expanded states management
        self.expanded_states = {}  # Store expanded states of charts
        
        # SpO2 specific medical thresholds and statistics
        self.spo2_thresholds = {
            'normal': 95,    # Normal SpO2 level
            'mild': 90,      # Mild hypoxemia
            'moderate': 85,  # Moderate hypoxemia
            'severe': 80     # Severe hypoxemia
        }
        self.spo2_statistics = {}  # Store calculated statistics
        
        # Area selection variables
        self.selection_start = None
        self.selection_end = None
        self.selection_start_scene = None  # Store scene pos for pixel distance
        self.selection_end_scene = None
        self.is_selecting = False
        self.current_selection_chart = None
        self.selection_labels = {}  # Store selection labels for each chart
        self.last_click_time = 0  # Debounce duplicate clicks
        
        # Timer for detecting selection completion
        self.selection_timer = QTimer(self)
        self.selection_timer.setSingleShot(True)
        self.selection_timer.timeout.connect(self.finish_selection)
        self.init_ui()
        self.init_charts()
        
        # Timer for updating time
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        # Don't start timer initially - wait for user to press play
        
    def scroll_up(self):
        """Scroll up by a fixed amount"""
        if hasattr(self, 'scroll_area'):
            scrollbar = self.scroll_area.verticalScrollBar()
            current_value = scrollbar.value()
            new_value = max(0, current_value - 100)  # Scroll up by 100 pixels
            scrollbar.setValue(new_value)
    
    def scroll_down(self):
        """Scroll down by a fixed amount"""
        if hasattr(self, 'scroll_area'):
            scrollbar = self.scroll_area.verticalScrollBar() 
            current_value = scrollbar.value()
            max_value = scrollbar.maximum()
            new_value = min(max_value, current_value + 100)  # Scroll down by 100 pixels
            scrollbar.setValue(new_value)
    
    def keyPressEvent(self, event):
        """Handle keyboard events for arrow key scrolling"""
        if event.key() == Qt.Key_Up:
            # Scroll up with UP arrow key
            self.scroll_up()
            event.accept()
        elif event.key() == Qt.Key_Down:
            # Scroll down with DOWN arrow key
            self.scroll_down()
            event.accept()
        else:
            # Let other key events be handled normally
            super().keyPressEvent(event)
    
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
        
        # Charts container with functional scrollbar only
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("chartsScrollArea")
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Enable functional scrollbar with proper styling
        self.scroll_area.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical {
                background: #f3f4f6;
                width: 12px;
                border-radius: 6px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #9ca3af;
                min-height: 20px;
                border-radius: 6px;
                border: 1px solid #6b7280;
            }
            QScrollBar::handle:vertical:hover {
                background: #6b7280;
                border: 1px solid #4b5563;
            }
            QScrollBar::handle:vertical:pressed {
                background: #4b5563;
                border: 1px solid #374151;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                width: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        
        # Add horizontal scrollbar styling
        self.scroll_area.horizontalScrollBar().setStyleSheet("""
            QScrollBar:horizontal {
                background: #f3f4f6;
                height: 12px;
                border-radius: 6px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:horizontal {
                background: #9ca3af;
                min-width: 20px;
                border-radius: 6px;
                border: 1px solid #6b7280;
            }
            QScrollBar::handle:horizontal:hover {
                background: #6b7280;
                border: 1px solid #4b5563;
            }
            QScrollBar::handle:horizontal:pressed {
                background: #4b5563;
                border: 1px solid #374151;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                height: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        """)
        
        self.charts_widget = QWidget()
        self.charts_widget.setObjectName("chartsContainer")
        self.charts_widget.setMinimumWidth(1500)  # Force minimum width to trigger horizontal scrollbar
        self.charts_layout = QVBoxLayout(self.charts_widget)
        self.charts_layout.setContentsMargins(0, 0, 0, 0)
        self.charts_layout.setSpacing(8)
        
        # Add resize event handler to update overlays when window is resized
        original_charts_resize = self.charts_widget.resizeEvent
        def charts_resize_event(event):
            if original_charts_resize:
                original_charts_resize(event)
            # Update all overlays when charts widget is resized
            self.update_all_overlays_on_resize()
        self.charts_widget.resizeEvent = charts_resize_event
        
        # Add stretch items to help with centering
        self.top_spacer = QWidget()
        self.bottom_spacer = QWidget()
        self.top_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.bottom_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        self.scroll_area.setWidget(self.charts_widget)
        chart_layout.addWidget(self.scroll_area, stretch=1)
        
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

        backward_btn = QPushButton("◀◀")
        backward_btn.setObjectName("controlButton")
        backward_btn.setFixedHeight(28) 
        backward_btn.setMinimumWidth(60)
        backward_btn.clicked.connect(self.backward_playback)
        controls_layout.addWidget(backward_btn)

        # Start/Pause button (toggles between play and pause)
        self.play_pause_btn = QPushButton("▶")
        self.play_pause_btn.setObjectName("controlButton")
        self.play_pause_btn.setFixedHeight(28)
        self.play_pause_btn.setMinimumWidth(60)
        self.play_pause_btn.clicked.connect(self.toggle_playback)
        controls_layout.addWidget(self.play_pause_btn)

    
        forward_btn = QPushButton("▶▶")
        forward_btn.setObjectName("controlButton")
        forward_btn.setFixedHeight(28)
        forward_btn.setMinimumWidth(60)
        forward_btn.clicked.connect(self.forward_playback)
        controls_layout.addWidget(forward_btn)

        controls_container.setLayout(controls_layout)
        layout.addWidget(controls_container)

        # --- Report Selector ---
        report_label = QLabel("Sleep Monitoring Report")
        report_label.setObjectName("reportLabel")
        report_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #1e293b; margin-left: 12px; margin-right: 12px;")
        layout.addWidget(report_label)

        # --- Time Window Dropdown ---
        time_window_label = QLabel("Time Window:")
        time_window_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #1e293b;")
        layout.addWidget(time_window_label)
        
        # Create dropdown for time window selection
        self.time_window_dropdown = QComboBox()
        self.time_window_dropdown.setObjectName("timeWindowDropdown")
        self.time_window_dropdown.setFixedHeight(30)
        self.time_window_dropdown.setMinimumWidth(80)
        
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
        
        # Set default selection to 2m (index 2)
        self.time_window_dropdown.setCurrentIndex(2)
        self.current_time_window = 60
        
        # Connect dropdown to time window function
        self.time_window_dropdown.currentIndexChanged.connect(self.on_time_window_changed)
        
        layout.addWidget(self.time_window_dropdown)

        # --- Time Navigation Controls ---
        nav_container = QFrame()
        nav_layout = QHBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(4)

        # Backward navigation button
        nav_backward_btn = QPushButton("<")
        nav_backward_btn.setObjectName("controlButton")
        nav_backward_btn.setFixedSize(50, 28)  # Fixed size for better visibility
        nav_backward_btn.setStyleSheet("""
            QPushButton#controlButton {
                background-color: #3b82f6;
                color: white;
                border: 1px solid #2563eb;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
                padding: 2px 8px;
            }
            QPushButton#controlButton:hover {
                background-color: #2563eb;
                border-color: #1d4ed8;
            }
            QPushButton#controlButton:pressed {
                background-color: #1d4ed8;
                border-color: #1e3a8a;
            }
        """)
        nav_backward_btn.clicked.connect(self.navigate_backward)
        nav_layout.addWidget(nav_backward_btn)

        # Time position label
        self.time_position_label = QLabel("0:00")
        self.time_position_label.setObjectName("timePositionLabel")
        self.time_position_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #1e293b; min-width: 40px;")
        self.time_position_label.setAlignment(Qt.AlignCenter)
        nav_layout.addWidget(self.time_position_label)

        # Forward navigation button
        nav_forward_btn = QPushButton(">")
        nav_forward_btn.setObjectName("controlButton")
        nav_forward_btn.setFixedSize(50, 28)  # Fixed size for better visibility
        nav_forward_btn.setStyleSheet("""
            QPushButton#controlButton {
                background-color: #3b82f6;
                color: white;
                border: 1px solid #2563eb;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
                padding: 2px 8px;
            }
            QPushButton#controlButton:hover {
                background-color: #2563eb;
                border-color: #1d4ed8;
            }
            QPushButton#controlButton:pressed {
                background-color: #1d4ed8;
                border-color: #1e3a8a;
            }
        """)
        nav_forward_btn.clicked.connect(self.navigate_forward)
        nav_layout.addWidget(nav_forward_btn)

        layout.addWidget(nav_container)

        # --- Hidden Graphs Dropdown ---
        hidden_graphs_label = QLabel("Hidden Graphs:")
        hidden_graphs_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #1e293b;")
        layout.addWidget(hidden_graphs_label)
        
        # Create dropdown for hidden graphs
        self.hidden_graphs_dropdown = QComboBox()
        self.hidden_graphs_dropdown.setObjectName("hiddenGraphsDropdown")
        self.hidden_graphs_dropdown.setFixedHeight(30)
        self.hidden_graphs_dropdown.setMinimumWidth(120)
        self.hidden_graphs_dropdown.addItem("Select to restore...")  # Placeholder item
        self.hidden_graphs_dropdown.setEnabled(False)  # Disable until graphs are hidden
        
        # Connect dropdown to restore function
        self.hidden_graphs_dropdown.currentIndexChanged.connect(self.restore_hidden_graph)
        
        layout.addWidget(self.hidden_graphs_dropdown)

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

    def on_time_window_changed(self, index):
        """Handle time window dropdown change"""
        # Get the value from dropdown item data
        seconds = self.time_window_dropdown.itemData(index)
        print(f"Debug: on_time_window_changed called with index {index}, seconds {seconds}")
        self.current_time_window = seconds
        
        # Reset time offset when changing window size
        self.current_time_offset = 0
        
        # Update charts with new time window
        print(f"Debug: About to call update_charts_for_time_window with {seconds} seconds")
        self.update_charts_for_time_window(seconds)
        self.restore_all_selections()
        self.update_time_position_label()
        print(f"Time window changed to: {self.time_window_dropdown.itemText(index)} ({seconds} seconds)")
    
    def navigate_backward(self):
        """Navigate backward in time"""
        if self.spo2_full_data and len(self.spo2_full_data[1]) > 0:
            # Calculate maximum possible time based on data length
            max_duration = len(self.spo2_full_data[1]) / 10.0  # 10 samples per second
            # Move back by the current time window
            self.current_time_offset = max(0, self.current_time_offset - self.current_time_window)
            self.refresh_charts()
            self.update_time_position_label()
            print(f"Navigated backward to: {self.current_time_offset}s (max: {max_duration:.1f}s)")
    
    def navigate_forward(self):
        """Navigate forward in time"""
        if self.spo2_full_data and len(self.spo2_full_data[1]) > 0:
            # Calculate maximum possible time based on data length
            max_duration = len(self.spo2_full_data[1]) / 10.0  # 10 samples per second
            # Move forward by the current time window
            new_offset = self.current_time_offset + self.current_time_window
            if new_offset < max_duration:
                self.current_time_offset = new_offset
                self.refresh_charts()
                self.update_time_position_label()
                print(f"Navigated forward to: {self.current_time_offset}s (max: {max_duration:.1f}s)")
    
    def update_time_position_label(self):
        """Update the time position label"""
        hours = int(self.current_time_offset // 3600)
        minutes = int((self.current_time_offset % 3600) // 60)
        seconds = int(self.current_time_offset % 60)
        self.time_position_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        
        # Emit signal to update dashboard slider
        self.time_position_updated.emit()
    
    def refresh_charts(self):
        """Refresh all charts with current time window and offset"""
        print(f"Debug: refresh_charts called with time_window={self.current_time_window}s, offset={self.current_time_offset}s")
        
        # Save expanded states before refreshing
        self.expanded_states = {}
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            if container and hasattr(container, 'plot_widget'):
                chart_name = container.plot_widget.chart_name
                current_height = container.height()
                max_height = container.maximumHeight()
                print(f"Debug: Chart '{chart_name}' - Height: {current_height}, MaxHeight: {max_height}")
                # Check if container is expanded (height > 120 or max_height is very large)
                if current_height > 120 or max_height > 1000:
                    self.expanded_states[chart_name] = current_height
                    print(f"Debug: Saved expanded state for '{chart_name}' with height {current_height}")
        
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            if container and hasattr(container, 'plot_widget'):
                plot_widget = container.plot_widget
                chart_name = plot_widget.chart_name
                
                # Update time window limits on CustomViewBox with offset
                vb = plot_widget.getViewBox()
                if hasattr(vb, 'set_time_window_limits'):
                    vb.set_time_window_limits(self.current_time_offset, self.current_time_offset + self.current_time_window)
                
                # Update data for each chart
                if chart_name.strip() == "SpO2":
                    x, y = self.get_spo2_data_for_window(self.current_time_window, self.current_time_offset)
                    if len(x) > 0 and len(y) > 0:
                        # Update normal line plot
                        plot_widget.plot_curve.setData(x, y)
                        
                        # Update scatter plot markers if they exist (only in 10s-30s time window)
                        if (hasattr(plot_widget, 'scatter_item') and 
                            plot_widget.scatter_item is not None and
                            10 <= self.current_time_window <= 30):
                            # Update scatter plot with new data
                            plot_widget.scatter_item.setData(x, y)
                            
                            # Update hover data with new values
                            plot_widget.hover_data = {'x': x, 'y': y}
                             
                            print(f"Updated SpO2 markers with {len(x)} points for time offset {self.current_time_offset}s")
                else:
                    # Update simulated data for ALL other signals
                    time_points = int(self.current_time_window * 10)
                    x = np.linspace(0, self.current_time_window, time_points)
                    freq = plot_widget.graph_frequency
                    amp = plot_widget.graph_amplitude
                    offset = plot_widget.graph_offset
                    y = np.sin(x * freq * 2 * np.pi) * amp + offset + (np.random.rand(time_points) - 0.5) * amp * 0.1
                    plot_widget.plot_curve.setData(x, y)
                    
                    print(f"Updated {chart_name} with {time_points} points for {self.current_time_window}s window")
        
        # Restore expanded states after refreshing
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            if container and hasattr(container, 'plot_widget'):
                chart_name = container.plot_widget.chart_name
                if chart_name in self.expanded_states:
                    # Restore expanded state
                    saved_height = self.expanded_states[chart_name]
                    container.setMinimumHeight(saved_height)
                    container.setMaximumHeight(16777215)  # Very large number (effectively no limit)
                    container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    print(f"Debug: Restored expanded state for '{chart_name}' with height {saved_height}")
    
    def set_time_window(self, seconds):
        """Set the time window for the sleep monitoring chart (legacy method for compatibility)"""
        # Find matching dropdown item and set it
        for i in range(self.time_window_dropdown.count()):
            if self.time_window_dropdown.itemData(i) == seconds:
                self.time_window_dropdown.setCurrentIndex(i)
                break
        
        # Update charts with new time window
        self.update_charts_for_time_window(seconds)
        self.restore_all_selections()
        print(f"Time window set to: {seconds} seconds")
    
    def update_charts_for_time_window(self, seconds):
        """Update chart data based on time window selection"""
        print(f"Debug: update_charts_for_time_window called with {seconds} seconds")
        # Save expanded states before clearing
        self.expanded_states = {}
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            if container and hasattr(container, 'plot_widget'):
                chart_name = container.plot_widget.chart_name
                current_height = container.height()
                max_height = container.maximumHeight()
                print(f"Debug: Chart '{chart_name}' - Height: {current_height}, MaxHeight: {max_height}")
                # Check if container is expanded (height > 120 or max_height is very large)
                if current_height > 120 or max_height > 1000:
                    self.expanded_states[chart_name] = current_height
                    print(f"Debug: Saved expanded state for '{chart_name}' with height {current_height}")
        
        # Clear existing charts
        for i in reversed(range(self.charts_layout.count())):
            child = self.charts_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
        
        # Clear hidden graphs and dropdown when time window changes
        self.hidden_graphs.clear()
        self.hidden_graphs_dropdown.clear()
        self.hidden_graphs_dropdown.addItem("Select to restore...")
        self.hidden_graphs_dropdown.setEnabled(False)
        
        # Reset graph order
        self.graph_order.clear()
        self.dragged_graph = None
                
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
        
        for position, (name, color, base_freq, amp, offset) in enumerate(signals):
            adjusted_freq = base_freq * frequency_factor
            chart = self.create_signal_chart(name, color, adjusted_freq, amp, offset)
            self.charts_layout.addWidget(chart, stretch=1)
            # Track the original order
            self.graph_order.append(name)
        
        # Restore expanded states immediately after charts are created
        self._delayed_restore_expanded_states()
    
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
            ("Pulse ", "#f97316", 0.0, 0, 30),  
            ("Body Movement", "#8b5cf6", 0.1, 5, 20),
            ("PR/HR)", "#5c61f6", 0.1, 5, 20),
        ]
        
        for position, (name, color, freq, amp, offset) in enumerate(signals):
            chart = self.create_signal_chart(name, color, freq, amp, offset)
            self.charts_layout.addWidget(chart, stretch=1)
            # Track the original order
            self.graph_order.append(name)
        
        # Restore expanded states after charts are created with a delay
        QTimer.singleShot(100, self._delayed_restore_expanded_states)
    
    def _delayed_restore_expanded_states(self):
        """Restore expanded states for charts after they are created"""
        print("Debug: _delayed_restore_expanded_states called")
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            if container and hasattr(container, 'plot_widget'):
                chart_name = container.plot_widget.chart_name
                if chart_name in self.expanded_states:
                    # Restore expanded state
                    saved_height = self.expanded_states[chart_name]
                    container.setMinimumHeight(saved_height)
                    container.setMaximumHeight(16777215)  # Very large number (effectively no limit)
                    container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    print(f"Debug: Restored expanded state for '{chart_name}' with height {saved_height}")
    
    def load_spo2_data(self, csv_path):
        """Load SpO2 data from CSV file and store full data for time window filtering"""
        try:
            # Read CSV file directly using pandas
            df = pd.read_csv(csv_path)
            
            # Convert timestamp to datetime and calculate relative time in seconds
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            start_time = df['timestamp'].iloc[0]
            df['time_seconds'] = (df['timestamp'] - start_time).dt.total_seconds()
            
            # Extract time and SpO2 values
            time_data = df['time_seconds'].values
            spo2_data = df['spo2'].values
            
            # Validate SpO2 data range (should be reasonable values)
            invalid_spo2 = np.sum((spo2_data < 0) | (spo2_data > 100))
            if invalid_spo2 > 0:
                QMessageBox.warning(self, "Data Warning", 
                    f"Found {invalid_spo2} invalid SpO2 values (outside 0-100% range)")
            
            # Store full data for time window filtering
            self.spo2_full_data = (time_data, spo2_data)
            
            print(f"Loaded SpO2 data: {len(time_data)} data points from {csv_path}")
            return time_data, spo2_data
            
        except Exception as e:
            print(f"Error loading SpO2 data: {e}")
            # Return empty arrays if loading fails
            self.spo2_full_data = (np.array([]), np.array([]))
            return np.array([]), np.array([])
    
    def load_spo2_data_from_file(self):
        """Load SpO2 data using file dialog - can be called from UI"""
        time_data, spo2_data = self.load_spo2_data()
        if len(time_data) > 0:
            # Refresh charts to display new data
            self.refresh_charts()
            QMessageBox.information(self, "Success", 
                f"SpO2 data loaded successfully!\n"
                f"Data points: {len(time_data)}\n"
                f"Duration: {time_data[-1]/3600:.1f} hours")
    
    def get_spo2_data_for_window(self, time_window_seconds, time_offset=0):
        """Get SpO2 data filtered for specific time window"""
        if self.spo2_full_data is None or len(self.spo2_full_data[0]) == 0:
            return np.array([]), np.array([])
        
        full_time, full_spo2 = self.spo2_full_data
        
        # Calculate sample indices based on 10Hz sampling rate (10 samples per second)
        samples_per_second = 10
        start_sample = int(time_offset * samples_per_second)
        end_sample = int((time_offset + time_window_seconds) * samples_per_second)
        
        # Ensure we don't exceed data bounds
        start_sample = max(0, start_sample)
        end_sample = min(len(full_spo2), end_sample)
        
        # Extract the data for this window
        window_spo2 = full_spo2[start_sample:end_sample]
        
        # Create proper time axis based on 10Hz sampling (0, 0.1, 0.2, 0.3...)
        num_samples = len(window_spo2)
        if num_samples == 0:
            return np.array([]), np.array([])
        
        # Generate time points: 0, 0.1, 0.2, ... up to time_window_seconds
        window_time = np.arange(num_samples) / samples_per_second
        
        # Calculate SpO2 statistics for this window
        self.calculate_spo2_statistics(window_spo2)
        
        print(f"SpO2 window: {time_window_seconds}s, Samples: {num_samples}, Expected: {time_window_seconds * samples_per_second}")
        
        return window_time, window_spo2
    
    def calculate_spo2_statistics(self, spo2_data):
        """Calculate medical-grade SpO2 statistics"""
        if len(spo2_data) == 0:
            return
        
        self.spo2_statistics = {
            'mean': np.mean(spo2_data),
            'min': np.min(spo2_data),
            'max': np.max(spo2_data),
            'std': np.std(spo2_data),
            'desaturation_events': np.sum(spo2_data < self.spo2_thresholds['normal']),
            'mild_events': np.sum(spo2_data < self.spo2_thresholds['mild']),
            'moderate_events': np.sum(spo2_data < self.spo2_thresholds['moderate']),
            'severe_events': np.sum(spo2_data < self.spo2_thresholds['severe']),
            'total_points': len(spo2_data)
        }
    
    def create_signal_chart(self, name, color, frequency, amplitude, offset):
        """Create a single signal trace chart with side label"""
        print(f"Debug: create_signal_chart called for '{name}' - creating new container with 120px height")
        
        container = QWidget()
        container.setObjectName("signalChartContainer")
        container.setMinimumHeight(120)  # Set default minimum height
        container.setMaximumHeight(120)  # Set default maximum height to maintain exact size
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
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
        plot_container.setObjectName("plotContainer")
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
        
        # Zoom In button
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setObjectName("zoomButton")
        zoom_in_btn.setFixedSize(24, 20)
        
        def on_zoom_in():
            print(f"ZOOM IN BUTTON CLICKED for {name}")
            self.zoom_vertical(plot_widget, 0.8)
        
        zoom_in_btn.clicked.connect(on_zoom_in)
        zoom_layout.addWidget(zoom_in_btn)
        
        # Zoom Out button
        zoom_out_btn = QPushButton("-")
        zoom_out_btn.setObjectName("zoomButton")
        zoom_out_btn.setFixedSize(24, 20)
        
        def on_zoom_out():
            print(f"ZOOM OUT BUTTON CLICKED for {name}")
            self.zoom_vertical(plot_widget, 1.2)
        
        zoom_out_btn.clicked.connect(on_zoom_out)
        zoom_layout.addWidget(zoom_out_btn)
        
        # Reset button
        reset_btn = QPushButton("R")
        reset_btn.setObjectName("zoomButton")
        reset_btn.setFixedSize(24, 20)
        
        def on_reset():
            print(f"RESET BUTTON CLICKED for {name}")
            self.reset_zoom(plot_widget)
        
        reset_btn.clicked.connect(on_reset)
        zoom_layout.addWidget(reset_btn)
        
        zoom_layout.addStretch()
        plot_container_layout.addWidget(zoom_frame)
        
        drag_btn = QPushButton("Expand")
        drag_btn.setObjectName("dragButton")
        drag_btn.setFixedSize(48, 22)  # Increased size for better visibility
        drag_btn.setStyleSheet("""
            QPushButton#dragButton {
                background-color: #dbeafe;
                border: 2px solid #3b82f6;
                border-radius: 6px;
                color: #1d4ed8;
                font-size: 11px;
                font-weight: bold;
                padding: 2px;
            }
            QPushButton#dragButton:hover {
                background-color: #bfdbfe;
                border-color: #2563eb;
                color: #1e40af;
            }
            QPushButton#dragButton:pressed {
                background-color: #93c5fd;
                border-color: #1d4ed8;
                color: #1e3a8a;
                
            }
        """)
        drag_btn.clicked.connect(lambda: self.start_manual_drag(name, container))
        plot_container_layout.addWidget(drag_btn)
        
        # Plot Widget with custom ViewBox
        plot_widget = pg.PlotWidget(viewBox=CustomViewBox())
        plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        plot_widget.setAlignment(Qt.AlignCenter)
        # Remove all grid lines for clean white background
        plot_widget.showGrid(x=False, y=False)
        
        # Define medical standard Y-axis ranges for each signal type
        y_axis_ranges = {
            "Body Position": (-100, 100),
            "Airflow": (-100, 100),
            "Snoring": (0, 100),
            "Thorex": (-100, 100),
            "Abdomen": (-100, 100),
            "SpO2": (85, 100),  # Medical SpO2 range (85-100%)
            "Pulse": (40, 200),   # Pulse rate in BPM
            "Body Movement": (-100, 100),
            "PR/HR": (40, 200)   # Pulse/Heart Rate in BPM
        }
        
        # Get the appropriate Y-axis range for this signal
        signal_name = name.strip()
        y_min, y_max = y_axis_ranges.get(signal_name, (0, 100))  # Default to 0-100 if not found
        
        # Set fixed Y-axis range based on medical standards
        try:
            plot_widget.setYRange(y_min, y_max)
        except TypeError:
            # Try alternative method for older pyqtgraph versions
            plot_widget.setRange(yRange=[y_min, y_max])
        
        # Restrict zoom to X-axis only (time-based zoom)
        plot_widget.setMouseEnabled(x=True, y=False)
        
        # Disable auto-range and set fixed limits
        plot_widget.enableAutoRange(axis='y', enable=False)
        try:
            plot_widget.setLimits(yMin=y_min, yMax=y_max)
        except TypeError:
            # Try alternative method for older pyqtgraph versions
            plot_widget.setLimits(yMin=y_min, yMax=y_max)
            
        # Set X-axis to show time values based on current time window
        plot_widget.getAxis('bottom').setStyle(showValues=True)  # Show time values
        plot_widget.getAxis('left').setStyle(showValues=True)   # Show Y-axis values
        
        # Set X-axis range to match time window with offset
        plot_widget.setXRange(self.current_time_offset, self.current_time_offset + self.current_time_window)
        
        # Set time window limits on CustomViewBox to enforce zoom constraints
        vb = plot_widget.getViewBox()
        if hasattr(vb, 'set_time_window_limits'):
            vb.set_time_window_limits(self.current_time_offset, self.current_time_offset + self.current_time_window)
        
        plot_widget.setMouseEnabled(x=True, y=False)
        plot_widget.hideButtons()  # Hide the 'A' button
        
        # Center the plot widget in its container
        plot_container_layout.setAlignment(plot_widget, Qt.AlignCenter)
        
        # Generate signal data
        if name.strip() == "SpO2":
            # Get SpO2 data for current time window
            if self.spo2_full_data is None:
                # Load data if not already loaded
                base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                csv_path = os.path.join(base_dir, "extracted_data", "spo2_6hr_10Hz_data (1).csv")
                print(f"Loading SpO2 data from: {csv_path}")
                
                self.load_spo2_data(csv_path)
            
            # Get filtered data for current time window
            x, y = self.get_spo2_data_for_window(self.current_time_window, self.current_time_offset)
            
            # If no data available, fallback to simulated data
            if len(x) == 0:
                print("Falling back to simulated SpO2 data")
                time_points = 1000
                x = np.linspace(self.current_time_offset, self.current_time_offset + self.current_time_window, time_points)
                y = np.sin(x * frequency * 2 * np.pi) * amplitude + offset + (np.random.rand(time_points) - 0.5) * amplitude * 0.1
            else:
                # Center the SpO2 data around mean (baseline correction)
                y_mean = np.mean(y)
                y_centered = y - y_mean
                y = y_centered + 90  # Center around 90% (medical baseline)
        else:
            # Generate simulated data for other signals based on time window
            time_points = int(self.current_time_window * 10)  # 10 Hz sampling rate
            x = np.linspace(self.current_time_offset, self.current_time_offset + self.current_time_window, time_points)
            y = np.sin(x * frequency * 2 * np.pi) * amplitude + offset + (np.random.rand(time_points) - 0.5) * amplitude * 0.1
        
        # Plot the signal and store reference for line visibility control
        pen = pg.mkPen(color=color, width=1.5)
        
        # Plot all graphs as normal line plots (no step ladder)
        plot_curve = plot_widget.plot(x, y, pen=pen)

        # Add hover functionality for SpO2 graph - only in 10s-30s time window
        if name.strip() == "SpO2" and len(x) > 0 and len(y) > 0:
            # Check if current time window is between 10s and 30s
            if 10 <= self.current_time_window <= 30:
                # Create scatter plot for data points
                scatter = pg.ScatterPlotItem(
                    x=x, y=y, 
                    size=8,  # Size of the dots
                    brush=pg.mkBrush(color=color),  # Same color as the line
                    pen=pg.mkPen(color=color, width=1)
                )
                plot_widget.addItem(scatter)
                
                # Store scatter item for hover detection
                plot_widget.scatter_item = scatter
                
                # Create tooltip label for hover display
                tooltip_label = pg.TextItem(
                    text="", 
                    color='white',
                    fill=(0, 0, 0, 180)  # Semi-transparent black background
                )
                plot_widget.addItem(tooltip_label)
                tooltip_label.setVisible(False)
                plot_widget.tooltip_label = tooltip_label
                
                # Store data for hover calculations
                plot_widget.hover_data = {'x': x, 'y': y}
                
                # Connect hover event
                plot_widget.scene().sigMouseMoved.connect(lambda pos, pw=plot_widget: self.on_sp02_hover(pos, pw))
                
                print(f"SpO2 markers enabled for {self.current_time_window}s time window")
            else:
                # Time window is outside 10s-30s range, no markers
                plot_widget.scatter_item = None
                plot_widget.tooltip_label = None
                plot_widget.hover_data = None
                print(f"SpO2 markers disabled for {self.current_time_window}s time window")

        plot_widget.graph_name = name
        plot_widget.graph_color = color
        plot_widget.graph_frequency = frequency
        plot_widget.graph_amplitude = amplitude
        plot_widget.graph_offset = offset
        
        # Store chart name and plot widget for selection handling
        plot_widget.chart_name = name
        plot_widget.plot_curve = plot_curve
        
        # Enable mouse tracking for area selection
        plot_widget.setMouseEnabled(x=True, y=True)
        plot_widget.scene().sigMouseMoved.connect(lambda pos, pw=plot_widget: self.on_mouse_moved(pos, pw))
        plot_widget.mousePressEvent = lambda event, pw=plot_widget: self.custom_mouse_press(event, pw)
        plot_widget.mouseReleaseEvent = lambda event, pw=plot_widget: self.custom_mouse_release(event, pw)
        
        # Connect resize event to update overlay positions
        vb = plot_widget.getViewBox()
        vb.sigResized.connect(lambda pw=plot_widget: self.on_plot_resized(pw))
        
        # Add click event handler to label for line visibility
        label.mousePressEvent = lambda event: self.toggle_graph_visibility(label, name, plot_curve, container, plot_widget)
                
        # Enable drag and drop for entire container (only for reordering)
        container.setAcceptDrops(True)
        container.mousePressEvent = lambda event: self.start_drag(event, name, container)
        container.mouseMoveEvent = lambda event: self.continue_drag(event, name)
        container.mouseReleaseEvent = lambda event: self.end_drag(event, name)
        
        # Store plot widget reference in container for resize handling
        container.plot_widget = plot_widget
        
        # Override container resize event
        original_resize = container.resizeEvent
        def container_resize_event(event):
            if hasattr(container, 'plot_widget'):
                chart_name = container.plot_widget.chart_name
                new_height = event.size().height()
                print(f"Debug: Container resize event for {chart_name} - New size: {new_height}px")
                
                # Completely prevent any resize attempts on expanded containers
                current_max_height = container.maximumHeight()
                current_min_height = container.minimumHeight()
                current_height = container.height()
                
                # Check if this is an expanded container (max height is very large or min height > 120)
                is_expanded = current_max_height > 1000 or current_min_height > 120 or current_height > 120
                
                if is_expanded:
                    print(f"Debug: Blocking resize of expanded container '{chart_name}' (current: {current_height}px, attempted: {new_height}px)")
                    # Completely block the resize event for expanded containers
                    return
                
            if original_resize:
                original_resize(event)
            # Update overlays when container resizes
            self.on_container_resized(container)
        container.resizeEvent = container_resize_event
        
        # Initialize multiple overlays list
        plot_widget.selection_overlays = []
        
        # Create temporary selection overlay for preview (initially hidden)
        selection_overlay = QLabel(plot_widget)  # Parent to plot widget
        selection_overlay.setObjectName("selectionOverlay")
        selection_overlay.setAlignment(Qt.AlignCenter)
        selection_overlay.setStyleSheet("""
            QLabel#selectionOverlay {
                background-color: rgba(59, 130, 246, 0.25);
                border: 2px solid #3b82f6;
                border-radius: 4px;
                color: white;
                font-size: 12px;
                font-weight: bold;
                padding: 4px 8px;
                text-align: center;
                text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.5);
            }
        """)
        selection_overlay.setVisible(False)
        
        # Store temporary overlay reference for preview only
        plot_widget.selection_overlay = selection_overlay
        
        plot_container_layout.addWidget(plot_widget)
        container_layout.addWidget(plot_container)
        
        return container
    
    def start_manual_drag(self, graph_name, container):
        """Toggle manual drag resizing when drag button is clicked"""
        # Check if this container is already in manual drag mode
        if self.manual_drag_container == container:
            # Toggle back to original size
            self.reset_to_original_size(container, graph_name)
        else:
            # Start manual drag mode
            # Remove maximum height constraint to allow resizing
            container.setMaximumHeight(16777215)  # Very large number (effectively no limit)
            container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            
            # Set up manual drag tracking
            self.manual_drag_container = container
            self.manual_drag_graph_name = graph_name
            self.manual_drag_start_height = container.height()
            
            # Enable mouse tracking for manual drag
            container.setMouseTracking(True)
            container.mousePressEvent = lambda event: self.manual_drag_mouse_press(event, graph_name, container)
            container.mouseMoveEvent = lambda event: self.manual_drag_mouse_move(event, graph_name)
            container.mouseReleaseEvent = lambda event: self.manual_drag_mouse_release(event, graph_name)
            
            print(f"Manual drag mode enabled for graph '{graph_name}'")
    
    def reset_to_original_size(self, container, graph_name):
        """Reset container to original size (120px)"""
        # Reset to original size
        container.setMinimumHeight(120)
        container.setMaximumHeight(120)
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
        # Clear manual drag mode
        if self.manual_drag_container == container:
            container.setMouseTracking(False)
            container.mousePressEvent = lambda event: self.start_drag(event, graph_name, container)
            container.mouseMoveEvent = lambda event: self.continue_drag(event, graph_name)
            container.mouseReleaseEvent = lambda event: self.end_drag(event, graph_name)
            
            # Clear manual drag tracking
            self.manual_drag_container = None
            self.manual_drag_graph_name = None
            self.manual_drag_start_height = None
            self.manual_drag_start_y = None
        
        print(f"Graph '{graph_name}' reset to original size (120px)")
    
    def manual_drag_mouse_press(self, event, graph_name, container):
        """Handle mouse press during manual drag"""
        if event.button() == Qt.LeftButton and self.manual_drag_container == container:
            self.manual_drag_start_y = event.globalY()
            container.setCursor(Qt.SizeVerCursor)
            print(f"Started manual dragging graph '{graph_name}' from height {self.manual_drag_start_height}")
    
    def manual_drag_mouse_move(self, event, graph_name):
        """Handle mouse move during manual drag"""
        if self.manual_drag_container and event.buttons() == Qt.LeftButton and self.manual_drag_start_y is not None:
            # Calculate new height
            delta_y = event.globalY() - self.manual_drag_start_y
            new_height = self.manual_drag_start_height + delta_y
            
            # Set minimum height constraint
            min_height = 80
            new_height = max(min_height, new_height)
            
            # Apply exact manual size
            self.manual_drag_container.setMinimumHeight(new_height)
            self.manual_drag_container.setMaximumHeight(new_height)
            
            # Force layout update
            self.manual_drag_container.updateGeometry()
            self.charts_widget.updateGeometry()
    
    def manual_drag_mouse_release(self, event, graph_name):
        """Handle mouse release during manual drag"""
        if self.manual_drag_container:
            self.manual_drag_container.setCursor(Qt.ArrowCursor)
            final_height = self.manual_drag_container.height()
            print(f"Finished manual dragging graph '{graph_name}' to height {final_height}")
            
            # Reset to normal mouse events
            self.manual_drag_container.setMouseTracking(False)
            self.manual_drag_container.mousePressEvent = lambda event: self.start_drag(event, graph_name, self.manual_drag_container)
            self.manual_drag_container.mouseMoveEvent = lambda event: self.continue_drag(event, graph_name)
            self.manual_drag_container.mouseReleaseEvent = lambda event: self.end_drag(event, graph_name)
            
            # Clear manual drag tracking
            self.manual_drag_container = None
            self.manual_drag_graph_name = None
            self.manual_drag_start_height = None
            self.manual_drag_start_y = None
    
    def start_drag(self, event, graph_name, container):
        """Start drag operation"""
        if event.button() == Qt.LeftButton:
            self.dragged_graph = container
            self.dragged_graph_name = graph_name
            self.drag_start_pos = event.pos()
            # No revert button functionality
    
    def continue_drag(self, event, graph_name):
        """Continue drag operation"""
        if self.dragged_graph and event.buttons() == Qt.LeftButton:
            # Calculate drag distance
            drag_distance = event.pos().y() - self.drag_start_pos.y()
            
            # If dragged down enough, just track the drag without removing from layout
            if abs(drag_distance) > 20:
                if not hasattr(self.dragged_graph, '_is_dragging'):
                    self.dragged_graph._is_dragging = True
                    # Don't remove from layout, just track drag state
    
    def end_drag(self, event, graph_name):
        """End drag operation"""
        if self.dragged_graph:
            # No revert button to hide
            
            # If was being dragged, find new position and reinsert
            if hasattr(self.dragged_graph, '_is_dragging'):
                delattr(self.dragged_graph, '_is_dragging')
                
                # Find drop position based on mouse
                drop_pos = event.pos()
                
                # Find which position to insert at
                insert_index = self.find_drop_position(drop_pos)
                
                # Reinsert at new position
                self.dragged_graph.setParent(self.charts_widget)
                self.charts_layout.insertWidget(insert_index, self.dragged_graph)
                
                print(f"Graph '{graph_name}' moved to position {insert_index}")
            
            self.dragged_graph = None
    
    def find_drop_position(self, drop_pos):
        """Find the correct position to insert dragged graph"""
        for i in range(self.charts_layout.count()):
            widget = self.charts_layout.itemAt(i).widget()
            if widget:
                widget_rect = widget.geometry()
                if drop_pos.y() < widget_rect.center().y():
                    return i
        
        # If below all, insert at end
        return self.charts_layout.count()
    
    def toggle_graph_visibility(self, label, chart_name, plot_curve, container, plot_widget):
        """Toggle visibility of entire graph row when label is clicked"""
        # Check if the graph is currently hidden
        if chart_name in self.hidden_graphs:
            # Graph is already hidden, this shouldn't happen normally
            return
        
        # Hide the entire graph row and store its data
        print(f"Hiding graph '{chart_name}'")
        
        # Find the original position of this graph
        original_position = self.graph_order.index(chart_name)
        
        # Store graph data for restoration
        self.hidden_graphs[chart_name] = {
            'container': container,
            'plot_curve': plot_curve,
            'color': plot_widget.graph_color,
            'frequency': plot_widget.graph_frequency,
            'amplitude': plot_widget.graph_amplitude,
            'offset': plot_widget.graph_offset,
            'position': original_position
        }
        
        # Remove the container from the layout safely
        self.charts_layout.removeWidget(container)
        container.setParent(None)
        container.setVisible(False)
        
        # Add to dropdown
        self.hidden_graphs_dropdown.addItem(chart_name)
        self.hidden_graphs_dropdown.setEnabled(True)
        
        # Reset dropdown to placeholder if this was the first hidden graph
        if len(self.hidden_graphs) == 1:
            self.hidden_graphs_dropdown.setCurrentIndex(0)
        
        print(f"Graph '{chart_name}' hidden and added to dropdown")
    
    def restore_hidden_graph(self, index):
        """Restore a hidden graph when selected from dropdown"""
        # Ignore the placeholder item (index 0)
        if index == 0:
            return
        
        # Get the graph name from dropdown
        graph_name = self.hidden_graphs_dropdown.itemText(index)
        
        # Check if graph exists in hidden graphs
        if graph_name not in self.hidden_graphs:
            print(f"Graph '{graph_name}' not found in hidden graphs")
            return
        
        # Block signals to prevent multiple calls
        self.hidden_graphs_dropdown.blockSignals(True)
        
        try:
            # Get stored graph data
            graph_data = self.hidden_graphs[graph_name]
            old_container = graph_data['container']
            
            # Create a completely fresh container with same properties as new graphs
            new_container = self.create_signal_chart(
                graph_name,
                graph_data['color'],
                graph_data['frequency'],
                graph_data['amplitude'],
                graph_data['offset']
            )
            
            # Find the plot widget in the new container and replace it with the stored one
            old_plot_widget = None
            for i in range(new_container.layout().count()):
                widget = new_container.layout().itemAt(i).widget()
                if isinstance(widget, pg.PlotWidget):
                    old_plot_widget = widget
                    break
            
            # Find the stored plot widget in the old container
            stored_plot_widget = None
            for i in range(old_container.layout().count()):
                widget = old_container.layout().itemAt(i).widget()
                if isinstance(widget, pg.PlotWidget):
                    stored_plot_widget = widget
                    break
            
            # If we found both plot widgets, replace the new one with the stored one
            if old_plot_widget and stored_plot_widget:
                # Copy properties from stored plot widget
                old_plot_widget.graph_name = stored_plot_widget.graph_name
                old_plot_widget.graph_color = stored_plot_widget.graph_color
                old_plot_widget.graph_frequency = stored_plot_widget.graph_frequency
                old_plot_widget.graph_amplitude = stored_plot_widget.graph_amplitude
                old_plot_widget.graph_offset = stored_plot_widget.graph_offset
                
                # Copy plot data
                old_plot_widget.clear()
                for item in stored_plot_widget.listDataItems():
                    old_plot_widget.addItem(item)
            
            # Remove from hidden graphs dictionary first
            del self.hidden_graphs[graph_name]
            
            # Remove from dropdown
            self.hidden_graphs_dropdown.removeItem(index)
            
            # Find the correct position to insert this graph
            insert_position = graph_data['position']
            
            # Count how many visible graphs come before this position
            visible_before = 0
            for i in range(insert_position):
                if self.graph_order[i] not in self.hidden_graphs:
                    visible_before += 1
            
            # Insert the fresh container at the correct position with stretch factor
            self.charts_layout.insertWidget(visible_before, new_container, stretch=1)
            
            # Reconnect mouse event handlers for drag functionality
            new_container.setAcceptDrops(True)
            new_container.mousePressEvent = lambda event: self.start_drag(event, graph_name, new_container)
            new_container.mouseMoveEvent = lambda event: self.continue_drag(event, graph_name)
            new_container.mouseReleaseEvent = lambda event: self.end_drag(event, graph_name)
            
            # Disable dropdown if no more hidden graphs
            if len(self.hidden_graphs) == 0:
                self.hidden_graphs_dropdown.setEnabled(False)
            else:
                # Reset to placeholder
                self.hidden_graphs_dropdown.setCurrentIndex(0)
            
            print(f"Graph '{graph_name}' restored")
        
        finally:
            # Unblock signals
            self.hidden_graphs_dropdown.blockSignals(False)
    
    def toggle_line_visibility(self, label, chart_name, plot_curve):
        """Toggle visibility of graph line when label is clicked"""
        # Check if the line is currently hidden
        if hasattr(plot_curve, '_is_hidden') and plot_curve._is_hidden:
            # Show the line
            plot_curve.setVisible(True)
            plot_curve._is_hidden = False
            label.setStyleSheet("""
                QLabel#chartSideLabel {
                    font-size: 12px;
                    font-weight: bold;
                    color: #4b5563;
                    background-color: #f9fafb;
                    border: 1px solid #e5e7eb;
                    border-radius: 4px;
                    padding: 6px;
                }
            """)
            print(f"Graph line '{chart_name}' shown")
        else:
            # Hide the line
            plot_curve.setVisible(False)
            plot_curve._is_hidden = True
            label.setStyleSheet("""
                QLabel#chartSideLabel {
                    font-size: 12px;
                    font-weight: bold;
                    color: #9ca3af;
                    background-color: #f8fafc;
                    border: 1px solid #d1d5db;
                    border-radius: 4px;
                    padding: 6px;
                }
            """)
            print(f"Graph line '{chart_name}' hidden")
    
    def zoom_vertical(self, plot_widget, zoom_factor):
        """Zoom in/out vertically on the plot"""
        # Get current Y range
        current_range = plot_widget.getViewBox().viewRange()
        y_min, y_max = current_range[1]
        
        # Calculate center point
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
            
        try:
            plot_widget.setYRange(new_y_min, new_y_max)
        except TypeError:
            # Try alternative method for older pyqtgraph versions
            plot_widget.setRange(yRange=[new_y_min, new_y_max])
    
    def reset_zoom(self, plot_widget):
        """Reset zoom to original medical standard range"""
        # Define medical standard Y-axis ranges
        y_axis_ranges = {
            "Body Position": (-100, 100),
            "Airflow": (-100, 100),
            "Snoring": (0, 100),
            "Thorex": (-100, 100),
            "Abdomen": (-100, 100),
            "SpO2": (85, 100),
            "Pulse": (40, 200),
            "Body Movement": (-100, 100),
            "PR/HR": (40, 200)
        }
        
        # Get the chart name from the plot widget
        chart_name = getattr(plot_widget, 'chart_name', '')
        y_min, y_max = y_axis_ranges.get(chart_name.strip(), (0, 100))
        
        try:
            plot_widget.setYRange(y_min, y_max)
        except TypeError:
            # Try alternative method for older pyqtgraph versions
            plot_widget.setRange(yRange=[y_min, y_max])
    
    def toggle_playback(self):
        """Toggle between play and pause"""
        print(f"Toggle playback - Current state: {self.is_playing}")
        if self.is_playing:
            self.pause_playback()
        else:
            self.start_playback()
    
    def start_playback(self):
        """Start playback"""
        print("Starting playback")
        self.is_playing = True
        self.play_pause_btn.setText("⏸")
        # Start timer
        self.timer.start(1000)
        print(f"Playback started - Timer active: {self.timer.isActive()}")
    
    def pause_playback(self):
        """Pause playback"""
        print("Pausing playback")
        self.is_playing = False
        self.play_pause_btn.setText("▶")
        # Stop timer
        self.timer.stop()
        print(f"Playback paused - Timer active: {self.timer.isActive()}")
    
    def forward_playback(self):
        """Fast forward playback"""
        print(f"Forward button clicked - Playing: {self.is_playing}")
        if self.is_playing:
            # Jump forward by current time window
            self.current_time = self.current_time.addSecs(self.current_time_window)
            self.update_time_display()
            print(f"Jumped forward to: {self.current_time.toString('HH:mm:ss')}")
    
    def backward_playback(self):
        """Rewind playback"""
        print(f"Backward button clicked - Playing: {self.is_playing}")
        if self.is_playing:
            # Jump backward by current time window
            self.current_time = self.current_time.addSecs(-self.current_time_window)
            self.update_time_display()
            print(f"Jumped backward to: {self.current_time.toString('HH:mm:ss')}")
    
    def update_time_display(self):
        """Update time display without adding seconds"""
        self.current_time_label.setText(f"Current: {self.current_time.toString('HH:mm:ss')}")
    
    def update_time(self):
        """Update current time display"""
        if self.is_playing:
            self.current_time = self.current_time.addSecs(1)
        self.update_time_display()

    def on_mouse_moved(self, scene_pos, plot_widget):
        """Handle mouse move for area selection"""
        if not self.is_selecting or not self.selection_start:
            return
        if plot_widget != self.current_selection_chart:
            return  # Only process for current chart
        vb = plot_widget.getViewBox()
        mouse_point = vb.mapSceneToView(scene_pos)
        self.selection_end = mouse_point
        self.selection_end_scene = scene_pos
        self.update_selection_overlay(self.selection_start, self.selection_end)
    
    def on_sp02_hover(self, scene_pos, plot_widget):
        """Handle hover over SpO2 data points to show values"""
        # Check if hover data exists (markers are enabled)
        if not hasattr(plot_widget, 'hover_data') or plot_widget.hover_data is None:
            return
            
        # Convert scene position to view coordinates
        vb = plot_widget.getViewBox()
        mouse_point = vb.mapSceneToView(scene_pos)
        mouse_x = mouse_point.x()
        mouse_y = mouse_point.y()
        
        # Find the nearest data point
        hover_data = plot_widget.hover_data
        x_data = hover_data['x']
        y_data = hover_data['y']
        
        # Calculate distance to each point and find the closest one
        min_distance = float('inf')
        closest_index = -1
        closest_x = 0
        closest_y = 0
        
        for i in range(len(x_data)):
            distance = np.sqrt((x_data[i] - mouse_x)**2 + (y_data[i] - mouse_y)**2)
            if distance < min_distance:
                min_distance = distance
                closest_index = i
                closest_x = x_data[i]
                closest_y = y_data[i]
        
        # Show tooltip if mouse is close enough to a data point (within 0.5 units)
        hover_threshold = 0.5
        if min_distance < hover_threshold and closest_index >= 0:
            # Update tooltip position and text
            plot_widget.tooltip_label.setText(f"SpO2: {int(y_data[closest_index])}%")
            plot_widget.tooltip_label.setPos(closest_x, closest_y + 2)  # Position above the point
            plot_widget.tooltip_label.setVisible(True)
            
            # Highlight the data point by making it slightly larger
            if hasattr(plot_widget, 'scatter_item'):
                sizes = [8] * len(x_data)
                sizes[closest_index] = 12  # Make the hovered point larger
                plot_widget.scatter_item.setSize(sizes)
        else:
            # Hide tooltip when not hovering over a point
            plot_widget.tooltip_label.setVisible(False)
            
            # Reset all points to normal size
            if hasattr(plot_widget, 'scatter_item'):
                plot_widget.scatter_item.setSize([8] * len(x_data))
    
    
    def on_mouse_clicked(self, event, plot_widget):
        """Handle mouse click for area selection and label removal"""
        if event.button() == Qt.LeftButton:
            scene_pos = event.scenePos()
            widget_rect = plot_widget.rect()
            widget_pos = plot_widget.mapFromScene(scene_pos)
            if not widget_rect.contains(widget_pos):
                return
            # Debounce - prevent duplicate clicks
            import time
            current_time = time.time()
            if current_time - self.last_click_time < 0.1:
                return
            self.last_click_time = current_time
            if self.check_label_click(plot_widget, scene_pos):
                return
            vb = plot_widget.getViewBox()
            mouse_point = vb.mapSceneToView(scene_pos)
            self.is_selecting = True
            self.current_selection_chart = plot_widget
            self.selection_start = mouse_point
            self.selection_start_scene = scene_pos
            self.selection_end = None
            self.selection_end_scene = None
            # Keep preview overlay hidden, don't touch persistent overlays
            print(f"Started selection on {plot_widget.chart_name}")
        elif event.button() == Qt.RightButton:
            # RIGHT CLICK logic
            if self.selection_start and self.selection_end:
                print("Right click detected -> opening menu")
                self.show_selection_menu()
    
    def custom_mouse_press(self, event, plot_widget):
        """Custom mouse press handler for better selection handling"""
        # Only handle left mouse button for area selection
        if event.button() != Qt.LeftButton:
            return
            
        # Handle left click directly without converting to scene event
        widget_pos = event.pos()
        widget_rect = plot_widget.rect()
        if not widget_rect.contains(widget_pos):
            return
        
        # Debounce - prevent duplicate clicks
        import time
        current_time = time.time()
        if current_time - self.last_click_time < 0.1:
            return
        self.last_click_time = current_time
        
        # Convert to scene position for existing logic
        scene_pos = plot_widget.mapToScene(widget_pos)
        
        # Check for label click
        if self.check_label_click(plot_widget, scene_pos):
            return
        
        # Start selection
        vb = plot_widget.getViewBox()
        mouse_point = vb.mapSceneToView(scene_pos)
        self.is_selecting = True
        self.current_selection_chart = plot_widget
        self.selection_start = mouse_point
        self.selection_start_scene = scene_pos
        self.selection_end = None
        self.selection_end_scene = None
        # Keep preview overlay hidden, don't touch persistent overlays
        print(f"Started selection on {plot_widget.chart_name}")
    
    def custom_mouse_release(self, event, plot_widget):
        """Custom mouse release handler for reliable selection completion"""
        if event.button() == Qt.LeftButton:
            self.on_mouse_released(event, plot_widget)
    
    def on_container_resized(self, container):
        """Handle container resize to update overlay positions"""
        if not hasattr(container, 'plot_widget'):
            return
            
        plot_widget = container.plot_widget
        print(f"Container resized for {plot_widget.chart_name}")
        
        # Update persistent overlays for this chart
        if hasattr(plot_widget, 'selection_overlays'):
            chart_name = plot_widget.chart_name
            if chart_name in self.selection_labels:
                overlays = plot_widget.selection_overlays
                labels_data = self.selection_labels[chart_name]
                
                # Update each overlay position based on stored data
                for i, overlay in enumerate(overlays):
                    if i < len(labels_data):
                        selection_data = labels_data[i]
                        vb = plot_widget.getViewBox()
                        
                        # Get current view range to calculate proportional position
                        view_range = vb.viewRange()
                        x_min_range, x_max_range = view_range[0]
                        
                        # Calculate proportional positions based on data coordinates
                        start_x = selection_data['start'].x()
                        end_x = selection_data['end'].x()
                        
                        # Map data coordinates to view coordinates proportionally
                        total_range = x_max_range - x_min_range
                        if total_range > 0:
                            start_prop = (start_x - x_min_range) / total_range
                            end_prop = (end_x - x_min_range) / total_range
                        else:
                            start_prop = 0
                            end_prop = 1
                            
                        if start_prop > 1: 
                            end_prop = 2
                        
                        if total_range < 100:
                            end_prop = start_prop + 100 / total_range
                             
                        if total_range > 1000:
                            end_prop = start_prop + 1000 / tatal_
                    
                         
                        # Convert to widget coordinates
                        widget_width = plot_widget.width()
                        x_min = max(0, min(start_prop, end_prop) * widget_width)
                        x_max = min(widget_width, max(start_prop, end_prop) * widget_width)
                        
                        print(f"Overlay {i} - Chart: {chart_name}")
                        print(f"Overlay {i} - Data coords: start={start_x}, end={end_x}")
                        print(f"Overlay {i} - View range: {x_min_range} to {x_max_range}")
                        print(f"Overlay {i} - Proportions: start={start_prop:.3f}, end={end_prop:.3f}")
                        print(f"Overlay {i} - Widget coords: x_min={x_min:.1f}, x_max={x_max:.1f}, width={x_max-x_min:.1f}")
                        
                        overlay.setGeometry(int(x_min), 0, int(x_max - x_min), plot_widget.height())
                        print(f"Overlay {i} - Final geometry: {overlay.geometry()}")
        
        # Update current selection overlay if active
        if (self.current_selection_chart == plot_widget and 
            hasattr(plot_widget, 'selection_overlay') and
            self.selection_start and self.selection_end):
            self.update_selection_overlay(self.selection_start, self.selection_end)
            
            # Check if overlay is in "Choose Label" state and update accordingly
            overlay = plot_widget.selection_overlay
            if overlay and "Choose Label" in overlay.text():
                overlay.setText("Choose Label...")
                overlay.setStyleSheet("""
                    QLabel#selectionOverlay {
                        background-color: rgba(251, 146, 60, 0.4);
                        border: 2px solid #f97316;
                        border-radius: 6px;
                        color: white;
                        font-size: 14px;
                        font-weight: bold;
                        padding: 6px 10px;
                        text-align: center;
                        text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.7);
                    }
                """)
    
    def on_plot_resized(self, plot_widget):
        """Handle plot widget resize/pan/zoom to update overlay positions"""
        # Update persistent overlays for this chart
        if hasattr(plot_widget, 'selection_overlays'):
            chart_name = plot_widget.chart_name
            if chart_name in self.selection_labels:
                overlays = plot_widget.selection_overlays
                labels_data = self.selection_labels[chart_name]
                
                # Update each overlay position based on stored data
                for i, overlay in enumerate(overlays):
                    if i < len(labels_data):
                        selection_data = labels_data[i]
                        vb = plot_widget.getViewBox()
                        p1 = vb.mapViewToScene(selection_data['start'])
                        p2 = vb.mapViewToScene(selection_data['end'])
                        w1 = plot_widget.mapFromScene(p1)
                        w2 = plot_widget.mapFromScene(p2)
                        
                        x_min = min(w1.x(), w2.x())
                        x_max = max(w1.x(), w2.x())
                        
                        print(f"Overlay {i} - original start: {selection_data['start']}, end: {selection_data['end']}")
                        print(f"Overlay {i} - w1: {w1}, w2: {w2}")
                        print(f"Overlay {i} - x_min: {x_min}, x_max: {x_max}, width: {int(x_max - x_min)}, height: {plot_widget.height()}")
                        overlay.setGeometry(int(x_min), 0, int(x_max - x_min), plot_widget.height())
                        print(f"Overlay {i} - new geometry: {overlay.geometry()}")
        
        # Update current selection overlay if active
        if (self.current_selection_chart == plot_widget and 
            hasattr(plot_widget, 'selection_overlay') and
            self.selection_start and self.selection_end):
            self.update_selection_overlay(self.selection_start, self.selection_end)
    
    def on_mouse_released(self, event, plot_widget):
        """Finish selection on mouse release"""
        if not self.is_selecting or plot_widget != self.current_selection_chart:
            return

        self.is_selecting = False

        if self.selection_start_scene and self.selection_end_scene:
            distance = abs(self.selection_end_scene.x() - self.selection_start_scene.x())

            if distance > 10:
                print("Selection finished properly")

                #  IMPORTANT: ensure end point set
                vb = plot_widget.getViewBox()
                mouse_point = vb.mapSceneToView(self.selection_end_scene)
                self.selection_end = mouse_point

                # FORCE MENU OPEN
                self.show_selection_menu()

            else:
                self.clear_selection()
        else:
            self.clear_selection()
    
    def find_plot_widget_at_position(self, scene_pos):
        """Find which plot widget contains the given scene position"""
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            if hasattr(container, 'findChildren'):
                plots = container.findChildren(pg.PlotWidget)
                if plots:
                    plot_widget = plots[0]
                    # Check if click is within this plot widget's bounds
                    widget_rect = plot_widget.rect()
                    widget_pos = plot_widget.mapFromScene(scene_pos)
                    if widget_rect.contains(widget_pos):
                        return plot_widget
        return None
    
    def finish_selection(self):
        """Finish selection and show dropdown menu (timer-based mouse release detection)"""
        if self.is_selecting and self.current_selection_chart and self.selection_start:
            self.is_selecting = False
            
            if self.selection_start_scene and self.selection_end_scene:
                # Calculate PIXEL distance using scene coordinates
                distance = abs(self.selection_end_scene.x() - self.selection_start_scene.x())
                
                if distance > 10:  # Minimum 10 pixels for valid selection
                    print(f"Selection finished: {distance} pixels")
                    self.show_selection_menu()
                else:
                    # Selection too small, clear it
                    print("Selection too small, clearing")
                    self.clear_selection()
            else:
                # No proper selection made
                self.clear_selection()
    
    def update_selection_overlay(self, start_pos, end_pos):
        """Update the visual selection overlay using proportional coordinate mapping"""
        if not self.current_selection_chart:
            return
        # Hide overlays of all other charts
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            if hasattr(container, 'findChildren'):
                plots = container.findChildren(pg.PlotWidget)
                if plots and plots[0] != self.current_selection_chart:
                    if hasattr(plots[0], 'selection_overlay'):
                        plots[0].selection_overlay.setVisible(False)
        overlay = self.current_selection_chart.selection_overlay
        if not overlay:
            return
        vb = self.current_selection_chart.getViewBox()
        
        # Get current view range to calculate proportional position
        view_range = vb.viewRange()
        x_min_range, x_max_range = view_range[0]
        
        # Calculate proportional positions based on data coordinates
        start_x = start_pos.x()
        end_x = end_pos.x()
        
        # Map data coordinates to view coordinates proportionally
        total_range = x_max_range - x_min_range
        if total_range > 0:
            start_prop = (start_x - x_min_range) / total_range
            end_prop = (end_x - x_min_range) / total_range
        else:
            start_prop = 0
            end_prop = 1
        
        # Convert to widget coordinates
        widget_width = self.current_selection_chart.width()
        x_min = max(0, min(start_prop, end_prop) * widget_width)
        x_max = min(widget_width, max(start_prop, end_prop) * widget_width)
        width = x_max - x_min
        
        # Ensure minimum width
        if width < 30:
            width = 30
        
        print(f"update_selection_overlay - Chart: {self.current_selection_chart.chart_name}")
        print(f"update_selection_overlay - Data coords: start={start_x}, end={end_x}")
        print(f"update_selection_overlay - View range: {x_min_range} to {x_max_range}")
        print(f"update_selection_overlay - Proportions: start={start_prop:.3f}, end={end_prop:.3f}")
        print(f"update_selection_overlay - Widget coords: x_min={x_min:.1f}, x_max={x_max:.1f}, width={width:.1f}")
        
        overlay.setGeometry(int(x_min), 0, int(width), self.current_selection_chart.height())
        overlay.setVisible(True)
        overlay.setText("Selecting...")
        overlay.raise_()
        overlay.setStyleSheet("""
            QLabel#selectionOverlay {
                background-color: rgba(59, 130, 246, 0.3);
                border: 2px solid #3b82f6;
                border-radius: 4px;
                color: white;
                font-size: 12px;
                font-weight: bold;
                padding: 4px 6px;
                text-align: center;
            }
        """)
    
    def show_selection_menu(self):
        """Show dropdown menu with OSA, CSA, MSA, HSA options"""
        print("show_selection_menu called!")
        if not self.current_selection_chart:
            print("No current_selection_chart, returning")
            return
        print(f"Current selection chart: {self.current_selection_chart.chart_name}")
            
        # Update overlay to show waiting state
        overlay = self.current_selection_chart.selection_overlay
        if overlay and self.selection_start and self.selection_end:
            self.update_selection_overlay(self.selection_start, self.selection_end)
            overlay.setText("Choose Label...")
            overlay.setStyleSheet("""
                QLabel#selectionOverlay {
                    background-color: rgba(251, 146, 60, 0.4);₹
                    border: 2px solid #f97316;
                    border-radius: 6px;
                    color: white;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 6px 10px;
                    text-align: center;
                    text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.7);
                }
            """)
            
        # Create context menu
        print("Creating context menu...")
        menu = QMenu(self)
        menu.setTitle("Select Sleep Event Type")
        
        # Add actions for each sleep event type
        osa_action = QAction("OSA - Obstructive Sleep Apnea", self)
        osa_action.triggered.connect(lambda: self.apply_selection_label("OSA"))
        menu.addAction(osa_action)
        
        csa_action = QAction("CSA - Central Sleep Apnea", self)
        csa_action.triggered.connect(lambda: self.apply_selection_label("CSA"))
        menu.addAction(csa_action)
        
        msa_action = QAction("MSA - Mixed Sleep Apnea", self)
        msa_action.triggered.connect(lambda: self.apply_selection_label("MSA"))
        menu.addAction(msa_action)
        
        hsa_action = QAction("HSA - Hypopnea Sleep Apnea", self)
        hsa_action.triggered.connect(lambda: self.apply_selection_label("HSA"))
        menu.addAction(hsa_action)

        
        
        # Add separator and clear option
        menu.addSeparator()
        clear_action = QAction("Clear Selection", self)
        clear_action.triggered.connect(self.clear_selection)
        menu.addAction(clear_action)
        
        # Show menu at cursor position
        print("Getting cursor position...")
        from PyQt5.QtGui import QCursor
        global_cursor_pos = QCursor.pos()
        print(f"Cursor position: {global_cursor_pos}")
        print("Showing menu...")
        menu.exec_(global_cursor_pos)
        print("Menu exec called!")
    
    def apply_selection_label(self, label_type):
        """Apply the selected label to the area"""
        if not self.current_selection_chart or not self.selection_start or not self.selection_end:
            return

        plot_widget = self.current_selection_chart
        chart_name = plot_widget.chart_name

        if chart_name not in self.selection_labels:
            self.selection_labels[chart_name] = []

        selection_data = {
            'label': label_type,
            'start': self.selection_start,
            'end': self.selection_end,
            'color': self.get_label_color(label_type)
        }

        self.selection_labels[chart_name].append(selection_data)

        # CREATE NEW OVERLAY (instead of reusing one)
        overlay = QLabel(plot_widget)
        overlay.setAlignment(Qt.AlignCenter)
        # Calculate timestamp information
        start_time = self.selection_start.x()
        end_time = self.selection_end.x()
        duration = end_time - start_time
        
        # Format timestamp display
        start_str = self.format_timestamp(start_time)
        duration_str = self.format_duration(duration)
        
        overlay.setText(f"{label_type}\n{start_str}\n{duration_str}")
        overlay.setStyleSheet(f"""
            background-color: {selection_data['color']};
            border: 2px solid {selection_data['color'].replace('0.2', '0.8')};
            border-radius: 6px;
            color: white;
            font-size: 11px;
            font-weight: bold;
            padding: 4px;
        """)
        
        # Make overlay clickable
        overlay.mousePressEvent = lambda event, ov=overlay, cn=chart_name: self.handle_overlay_click(event, ov, cn)
        overlay.mouseDoubleClickEvent = lambda event, ov=overlay, cn=chart_name: self.handle_overlay_double_click(event, ov, cn)

        # Position overlay
        vb = plot_widget.getViewBox()
        p1 = vb.mapViewToScene(selection_data['start'])
        p2 = vb.mapViewToScene(selection_data['end'])
        w1 = plot_widget.mapFromScene(p1)
        w2 = plot_widget.mapFromScene(p2)

        x_min = min(w1.x(), w2.x())
        x_max = max(w1.x(), w2.x())

        overlay.setGeometry(int(x_min), 0, int(x_max - x_min), plot_widget.height())
        overlay.show()

        # Hide the temporary "Choose Label" overlay
        if hasattr(plot_widget, 'selection_overlay'):
            plot_widget.selection_overlay.setVisible(False)

        # store overlay
        plot_widget.selection_overlays.append(overlay)

        print(f"Label '{label_type}' added (persistent)")

        # clear temp selection
        self.selection_start = None
        self.selection_end = None
        self.selection_start_scene = None
        self.selection_end_scene = None
        self.current_selection_chart = None
    
    def handle_overlay_click(self, event, overlay, chart_name):
        """Handle right click on overlay"""
        if event.button() == Qt.RightButton:
            self.show_overlay_menu(event.globalPos(), overlay, chart_name)
    
    def handle_overlay_double_click(self, event, overlay, chart_name):
        """Double click = quick remove option"""
        self.show_overlay_menu(event.globalPos(), overlay, chart_name)
    
    def show_overlay_menu(self, global_pos, overlay, chart_name):
        """Show remove menu for overlay"""
        menu = QMenu(self)

        remove_action = QAction("Remove Selection", self)
        remove_action.triggered.connect(lambda: self.delete_overlay(overlay, chart_name))
        menu.addAction(remove_action)

        menu.exec_(global_pos)
    
    def delete_overlay(self, overlay, chart_name):
        """Delete selected overlay with data sync"""
        overlay.hide()
        overlay.deleteLater()

        # Remove from overlay list and data
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            plots = container.findChildren(pg.PlotWidget)

            if plots and plots[0].chart_name == chart_name:
                pw = plots[0]

                if overlay in pw.selection_overlays:
                    index = pw.selection_overlays.index(overlay)
                    pw.selection_overlays.remove(overlay)

                    # remove from data also
                    if chart_name in self.selection_labels and index < len(self.selection_labels[chart_name]):
                        self.selection_labels[chart_name].pop(index)

        print("Overlay + data deleted")
    
    def get_label_color(self, label_type):
        """Get color for label type"""
        colors = {
            'OSA': 'rgba(239, 68, 68, 0.2)',    # Red
            'CSA': 'rgba(59, 130, 246, 0.2)',   # Blue
            'MSA': 'rgba(245, 158, 11, 0.2)',   # Yellow
            'HSA': 'rgba(16, 185, 129, 0.2)'   # Green
        }
        return colors.get(label_type, 'rgba(107, 114, 128, 0.2)')
    
    def check_label_click(self, plot_widget, scene_pos):
        """Check if click is on an existing label and show remove option"""
        chart_name = plot_widget.chart_name
        if chart_name not in self.selection_labels or not self.selection_labels[chart_name]:
            return False
        vb = plot_widget.getViewBox()
        widget_pos = plot_widget.mapFromScene(scene_pos)
        for i, selection_data in enumerate(self.selection_labels[chart_name]):
            p1 = vb.mapViewToScene(selection_data['start'])
            p2 = vb.mapViewToScene(selection_data['end'])
            label_start = plot_widget.mapFromScene(p1)
            label_end = plot_widget.mapFromScene(p2)
            if (min(label_start.x(), label_end.x()) <= widget_pos.x() <= max(label_start.x(), label_end.x())):
                self.show_remove_menu(plot_widget, chart_name, i, selection_data, scene_pos)
                return True
        return False
    
    def show_remove_menu(self, plot_widget, chart_name, label_index, selection_data, scene_pos):
        """Show menu to remove or modify existing label"""
        menu = QMenu(self)
        menu.setTitle(f"Label: {selection_data['label']}")
        
        # Remove action
        remove_action = QAction(f"Remove '{selection_data['label']}'", self)
        remove_action.triggered.connect(lambda: self.remove_label(chart_name, label_index))
        menu.addAction(remove_action)
        
        # Change label action
        menu.addSeparator()
        change_action = QAction("Change Label...", self)
        change_action.triggered.connect(lambda: self.change_label(chart_name, label_index))
        menu.addAction(change_action)
        
        # Show menu at click position
        widget_pos = plot_widget.mapFromScene(scene_pos)
        global_pos = plot_widget.mapToGlobal(widget_pos)
        menu.popup(global_pos)
    
    def remove_label(self, chart_name, label_index):
        """Remove a specific label"""
        if chart_name in self.selection_labels and 0 <= label_index < len(self.selection_labels[chart_name]):
            removed_label = self.selection_labels[chart_name].pop(label_index)
            print(f"Removed label '{removed_label['label']}' from {chart_name}")
            
            # Hide overlay if no more labels
            if not self.selection_labels[chart_name]:
                # Find the plot widget and hide overlay
                for i in range(self.charts_layout.count()):
                    container = self.charts_layout.itemAt(i).widget()
                    if hasattr(container, 'findChildren'):
                        plots = container.findChildren(pg.PlotWidget)
                        if plots and plots[0].chart_name == chart_name:
                            if hasattr(plots[0], 'selection_overlay'):
                                plots[0].selection_overlay.setVisible(False)
                            break
    
    def change_label(self, chart_name, label_index):
        """Change an existing label to a different type"""
        if chart_name in self.selection_labels and 0 <= label_index < len(self.selection_labels[chart_name]):
            # Store the selection data for re-application
            old_selection = self.selection_labels[chart_name][label_index]
            
            # Remove the old label
            self.remove_label(chart_name, label_index)
            
            # Set up for new label selection
            self.selection_start = old_selection['start']
            self.selection_end = old_selection['end']
            
            # Find the plot widget
            for i in range(self.charts_layout.count()):
                container = self.charts_layout.itemAt(i).widget()
                if hasattr(container, 'findChildren'):
                    plots = container.findChildren(pg.PlotWidget)
                    if plots and plots[0].chart_name == chart_name:
                        self.current_selection_chart = plots[0]
                        # Show selection menu for new label
                        self.show_selection_menu()
                        break
    
    def clear_selection(self):
        """Clear the current selection but keep persistent overlays"""
        if self.current_selection_chart and hasattr(self.current_selection_chart, 'selection_overlay'):
            self.current_selection_chart.selection_overlay.setVisible(False)
            # Reset overlay text and style for next use
            self.current_selection_chart.selection_overlay.setText("Selecting...")
            self.current_selection_chart.selection_overlay.setStyleSheet("""
                QLabel#selectionOverlay {
                    background-color: rgba(59, 130, 246, 0.3);
                    border: 2px solid #3b82f6;
                    border-radius: 4px;
                    color: white;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 4px 6px;
                    text-align: center;
                }
            """)
        self.selection_start = None
        self.selection_end = None
        self.selection_start_scene = None
        self.selection_end_scene = None
        self.current_selection_chart = None
        self.is_selecting = False
        print("Selection cleared")
    
    def restore_all_selections(self):
        """Restore all selection overlays when charts are recreated"""
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            plots = container.findChildren(pg.PlotWidget)

            if not plots:
                continue

            plot_widget = plots[0]
            chart_name = plot_widget.chart_name

            if chart_name not in self.selection_labels:
                continue

            # Clear existing overlays
            if hasattr(plot_widget, 'selection_overlays'):
                plot_widget.selection_overlays.clear()

            for selection in self.selection_labels[chart_name]:
                overlay = QLabel(plot_widget)
                
                # Calculate timestamp information
                start_time = selection['start'].x()
                end_time = selection['end'].x()
                duration = end_time - start_time
                
                # Format timestamp display
                start_str = self.format_timestamp(start_time)
                duration_str = self.format_duration(duration)
                
                overlay.setText(f"{selection['label']}\n{start_str}\n{duration_str}")
                overlay.setStyleSheet(f"""
                    background-color: {selection['color']};
                    border: 2px solid {selection['color'].replace('0.2', '0.8')};
                    border-radius: 6px;
                    color: white;
                    font-size: 11px;
                    font-weight: bold;
                    padding: 4px;
                """)

                # Make overlay clickable
                overlay.mousePressEvent = lambda event, ov=overlay, cn=chart_name: self.handle_overlay_click(event, ov, cn)
                overlay.mouseDoubleClickEvent = lambda event, ov=overlay, cn=chart_name: self.handle_overlay_double_click(event, ov, cn)

                # Position overlay correctly
                self.update_overlay_position(plot_widget, overlay, selection['start'], selection['end'])
                overlay.show()
                
                # Store overlay
                if not hasattr(plot_widget, 'selection_overlays'):
                    plot_widget.selection_overlays = []
                plot_widget.selection_overlays.append(overlay)
    
    def format_timestamp(self, time_seconds):
        """Format time in seconds to readable timestamp"""
        hours = int(time_seconds // 3600)
        minutes = int((time_seconds % 3600) // 60)
        seconds = int(time_seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def format_duration(self, duration_seconds):
        """Format duration to readable string"""
        if duration_seconds < 60:
            return f"{duration_seconds:.1f}s"
        else:
            minutes = int(duration_seconds // 60)
            seconds = int(duration_seconds % 60)
            return f"{minutes}m {seconds}s"
    
    def update_overlay_position(self, plot_widget, overlay, start_pos, end_pos):
        """Update overlay position based on current view"""
        vb = plot_widget.getViewBox()
        p1 = vb.mapViewToScene(start_pos)
        p2 = vb.mapViewToScene(end_pos)
        w1 = plot_widget.mapFromScene(p1)
        w2 = plot_widget.mapFromScene(p2)

        x_min = min(w1.x(), w2.x())
        x_max = max(w1.x(), w2.x())
        
        # Use large overlay height for persistent selections
        plot_height = plot_widget.height()
        overlay_height = max(60, plot_height)  # Minimum 60px or full plot height
        y_position = 0  # Start from top for large appearance

        overlay.setGeometry(int(x_min), y_position, int(x_max - x_min), int(overlay_height))
    
    def update_all_overlays_on_resize(self):
        """Update all overlay positions when window is resized"""
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            if hasattr(container, 'findChildren'):
                plots = container.findChildren(pg.PlotWidget)
                if plots and hasattr(plots[0], 'selection_overlays'):
                    plot_widget = plots[0]
                    chart_name = plot_widget.chart_name
                    
                    if chart_name in self.selection_labels:
                        for j, overlay in enumerate(plot_widget.selection_overlays):
                            if j < len(self.selection_labels[chart_name]):
                                selection_data = self.selection_labels[chart_name][j]
                                self.update_overlay_position(plot_widget, overlay, selection_data['start'], selection_data['end'])
    
    def add_spo2_threshold_lines(self, plot_widget):
        """Add medical threshold lines for SpO2 monitoring"""
        thresholds = self.spo2_thresholds
        
        # Define threshold colors and styles
        threshold_configs = [
            (thresholds['severe'], '#ef4444', 'Severe (<80%)', 2, Qt.DashLine),    # Red - Severe
            (thresholds['moderate'], '#f59e0b', 'Moderate (<85%)', 1.5, Qt.DashLine), # Orange - Moderate  
            (thresholds['mild'], '#eab308', 'Mild (<90%)', 1, Qt.DashLine),          # Yellow - Mild
            (thresholds['normal'], '#22c55e', 'Normal (≥95%)', 1, Qt.DotLine),       # Green - Normal
        ]
        
        for threshold, color, label, width, style in threshold_configs:
            # Create infinite horizontal line at threshold level
            line = pg.InfiniteLine(pos=threshold, angle=0, pen=pg.mkPen(color=color, width=width, style=style))
            plot_widget.addItem(line)
            
            # Add label for the threshold
            label_text = pg.TextItem(text=label, color=color, anchor=(0, 1))
            label_text.setPos(0, threshold)
            plot_widget.addItem(label_text)
    
    def add_spo2_statistics_overlay(self, plot_widget, container):
        """Add SpO2 statistics overlay to the plot container"""
        if not self.spo2_statistics:
            return
        
        # Create statistics label
        stats_text = f"""
SpO2 Statistics:
Mean: {self.spo2_statistics['mean']:.1f}%
Min: {self.spo2_statistics['min']:.1f}%
Max: {self.spo2_statistics['max']:.1f}%
Desaturations: {self.spo2_statistics['desaturation_events']}
Mild Events: {self.spo2_statistics['mild_events']}
Moderate Events: {self.spo2_statistics['moderate_events']}
Severe Events: {self.spo2_statistics['severe_events']}
        """.strip()
        
        stats_label = QLabel(container)
        stats_label.setText(stats_text)
        stats_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 0.8);
                color: white;
                font-size: 10px;
                font-family: 'Courier New', monospace;
                padding: 8px;
                border-radius: 6px;
                border: 1px solid #06b6d4;
            }
        """)
        stats_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        stats_label.setObjectName("spo2StatisticsLabel")
        
        # Position the overlay in top-right corner
        stats_label.move(container.width() - 200, 10)
        stats_label.resize(190, 120)
        stats_label.show()
        
        # Store reference for updates
        plot_widget.stats_label = stats_label
        
        # Update position when container resizes
        def update_stats_position():
            if hasattr(plot_widget, 'stats_label') and plot_widget.stats_label:
                plot_widget.stats_label.move(container.width() - 200, 10)
        
        # Connect resize event
        container.stats_update_func = update_stats_position
    
    def update_spo2_statistics_overlay(self, plot_widget, container):
        """Update SpO2 statistics overlay with current data - DISABLED"""
        # Statistics overlay disabled - no longer creating overlay
        pass
    
    def resizeEvent(self, event):
        """Handle resize for watermark centering"""
        super().resizeEvent(event)
        if hasattr(self, 'watermark'):
            self.watermark.setGeometry(self.charts_widget.rect())
