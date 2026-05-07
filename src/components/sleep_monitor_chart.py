


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
    QFrame, QComboBox, QMessageBox, QMenu, QAction, QScrollArea, QSizePolicy, QSlider, QFileDialog, QApplication, QDialog
)
from PyQt5.QtCore import Qt, QTimer, QTime, pyqtSignal, QPoint, QRect, QMimeData, QPointF
from PyQt5.QtGui import QPixmap, QScreen
from PyQt5.QtGui import QFont, QIcon, QPixmap, QDrag, QPainter, QPen
import pyqtgraph as pg
from .custom_viewbox import CustomViewBox
from .amplitude_axis_properties_dialog import AmplitudeAxisPropertiesDialog



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
        
        # Playback timer for movie-like data scrolling
        self.playback_timer = QTimer()
        self.playback_timer.timeout.connect(self.update_playback)
        self.hidden_graphs_dropdown = None  # Initialize dropdown reference
        self.hidden_graphs = {}  # Store hidden graph data: {name: {container, plot_curve, color, frequency, amplitude, offset, position}}
        self.graph_order = []  # Track original order of graphs: [name1, name2, ...]
        self.dragged_graph = None  # Track currently dragged graph
        
        # Resizing variables for drag handles
        self.resizing_graph = None
        self.resizing_graph_name = None
        self.resize_start_height = None
        self.resize_start_y = None
        
        # Timer to enforce fixed X-axis range
        self.range_enforcement_timer = QTimer()
        self.range_enforcement_timer.timeout.connect(self.enforce_fixed_ranges)
        self.range_enforcement_timer.start(100)  # Check every 100ms
        
        # Time window data management
        self.spo2_full_data = None  # Store full SpO2 data (time, spo2)
        self.current_time_offset = 0  # Current starting time for window
        
                
        # SpO2 specific statistics
        self.spo2_statistics = {}  # Store calculated statistics
        
        # Area selection variables
        self.selection_start = None
        self.selection_end = None
        self.selection_start_scene = None  # Store scene pos for pixel distance
        self.selection_end_scene = None
        self.is_selecting = False
        self.current_selection_chart = None
        self.selection_active = False  # Global flag for modal interaction lock
        self.selection_labels = {}  # Store selection labels for each chart
        # Dynamic selections storage - store selections in absolute time coordinates
        self.dynamic_selections = {}  # {chart_name: [{'label': 'OSA', 'start_time': 123.5, 'end_time': 125.2, 'color': '#red'}]}
        self.last_click_time = 0  # Debounce duplicate clicks
        
        # Apnea events storage
        self.apnea_events = []  # Store apnea event data
        self.event_plot_items = {}  # Store plot items for apnea events
        
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
        main_layout.setSpacing(8) 
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
        
        # self.start_time_label = QLabel("Start: ----")
        # self.start_time_label.setObjectName("timeLabelStart")
        # time_layout.addWidget(self.start_time_label)
        # time_layout.addStretch()
        
                
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
        
    
    def set_patient_id(self, patient_id: str):
        self.patient_id = patient_id or "--------"
    
    def set_dashboard_controls(self, time_window_dropdown, hidden_graphs_dropdown):
        """Set reference to dashboard controls for synchronization"""
        self.dashboard_time_window_dropdown = time_window_dropdown
        self.dashboard_hidden_graphs_dropdown = hidden_graphs_dropdown

    def confirm_and_save_raw_data(self):
        """Prompt user to confirm and save raw data"""
        if not hasattr(self, 'patient_id') or self.patient_id == "--------":
            QMessageBox.warning(self, "No Patient Selected", 
                           "Please select a patient ID before saving data.")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Save",
            f"Save raw data for patient {self.patient_id}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.save_raw_data_file()
    
    def take_screenshot(self):
        """Take a screenshot of the entire sleep monitor chart"""
        try:
            # Get the main window or widget
            parent_widget = self.parent()
            while parent_widget and parent_widget.parent():
                parent_widget = parent_widget.parent()
            
            if parent_widget:
                # Capture the entire window
                screen = QScreen.grabWindow(parent_widget.windowHandle())
            else:
                # Fallback to primary screen
                screen = QApplication.primaryScreen().grabWindow(QApplication.activeWindow())
            
            # Generate filename with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sleep_monitor_screenshot_{timestamp}.png"
            
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

    def save_raw_data_file(self):
        """Write a timestamped raw-data JSON file and return (path, timestamp_iso)."""
        timestamp_iso = datetime.now().isoformat(timespec="seconds")
        safe_ts = timestamp_iso.replace(":", "-")
        out_dir = os.path.join(os.getcwd(), "raw_data")
        os.makedirs(out_dir, exist_ok=True)
        filename = f"raw_data_{self.patient_id}_{safe_ts}.json"
        file_path = os.path.join(out_dir, filename)

        
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
            "channels": channels
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        # Emit signal to update save file list in patient info widget
        self.raw_data_saved.emit(file_path, timestamp_iso)
        
        return file_path, timestamp_iso

    def on_time_window_changed(self, index):
        """Handle time window dropdown change"""
        # Use dashboard controls if available, otherwise use local controls
        dropdown = getattr(self, 'dashboard_time_window_dropdown', None) or getattr(self, 'time_window_dropdown', None)
        if dropdown:
            # Get the value from dropdown item data
            seconds = dropdown.itemData(index)
            print(f"Debug: on_time_window_changed called with index {index}, seconds {seconds}")
            old_time_window = self.current_time_window
            self.current_time_window = seconds
            
            # Only reset time offset if this is the first time window change or if charts don't exist yet
            if self.charts_layout.count() == 0:
                self.current_time_offset = 0
                print(f"Debug: First time window setup, calling update_charts_for_time_window")
                self.update_charts_for_time_window(seconds)
            else:
                # Charts already exist, just refresh them with new time window
                print(f"Debug: Charts exist, calling refresh_charts with new time window")
                self.refresh_charts()
            
            self.restore_all_selections()
            self.update_time_position_label()
            print(f"Time window changed from {old_time_window}s to {seconds}s (playing: {self.is_playing})")
    
    def navigate_backward(self):
        """Navigate backward in time"""
        if self.block_if_selection_active():
            return
        
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
        if self.block_if_selection_active():
            return
        
        if self.spo2_full_data and len(self.spo2_full_data[1]) > 0:
            # Calculate maximum possible time based on data length
            max_duration = len(self.spo2_full_data[1]) / 10.0  
           
            new_offset = self.current_time_offset + self.current_time_window
            if new_offset < max_duration:
                self.current_time_offset = new_offset
                self.refresh_charts()
                self.update_time_position_label()
                print(f"Navigated forward to: {self.current_time_offset}s (max: {max_duration:.1f}s)")
    
    def start_playback(self):
        """Start movie-like playback of recorded data"""
        print(f"🎬 start_playback called - data available: {self.spo2_full_data is not None}")
        
        if self.block_if_selection_active():
            print("🎬 Blocked by selection active")
            return
        
        if not self.spo2_full_data or len(self.spo2_full_data[1]) == 0:
            print("No data available for playback")
            return
        
        self.is_playing = True
        print(f"🎬 Timer starting... is_playing: {self.is_playing}")
        self.playback_timer.start(100)  
        print(f"🎬 Timer started - Timer active: {self.playback_timer.isActive()}")
        print("▶️ Playback started")
        
        # Update button if it exists
        if self.play_pause_btn:
            self.play_pause_btn.setText("⏸ Pause")
    
    def pause_playback(self):
        """Pause the playback"""
        self.is_playing = False
        self.playback_timer.stop()
        print("⏸ Playback paused")
        
        # Update button if it exists
        if self.play_pause_btn:
            self.play_pause_btn.setText("▶ Play")
    
    def update_playback(self):
        """Main playback logic - auto-scroll data like a movie"""
        print(f"🎬 update_playback called - is_playing: {self.is_playing}")
        
        if not self.is_playing:
            return
        
        if not self.spo2_full_data or len(self.spo2_full_data[1]) == 0:
            self.pause_playback()
            return
        
        # Move forward in time 
        self.current_time_offset += 0.1 * self.playback_speed
        
        # Calculate maximum time based on data length
        max_time = len(self.spo2_full_data[1]) / 10.0  
        
        # Check if we've reached the end
        if self.current_time_offset >= max_time:
            self.pause_playback()
            print(f"🎬 Playback completed at {max_time:.1f}s")
            return
            
        # Update all charts with new time position
        self.refresh_charts()
        self.update_time_position_label()
        
        # Print progress for debugging 
        if int(self.current_time_offset * 10) % 10 == 0:
            progress_percent = (self.current_time_offset / max_time) * 100
            print(f"🎬 AUTO-SCROLL: {self.current_time_offset:.1f}s / {max_time:.1f}s ({progress_percent:.1f}%)")
    
    def toggle_playback(self):
        """Toggle between play and pause states"""
        if self.is_playing:
            self.pause_playback()
        else:
            self.start_playback()
    
    def change_playback_speed(self, speed_text):
        """Change playback speed from dropdown"""
        speed_map = {
            "0.5x": 0.5,
            "1.0x": 1.0,
            "2.0x": 2.0,
            "4.0x": 4.0
        }
        self.playback_speed = speed_map.get(speed_text, 1.0)
        print(f"🎬 Playback speed changed to {speed_text} ({self.playback_speed}x)")
    
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
        
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            if container and hasattr(container, 'plot_widget'):
                plot_widget = container.plot_widget
                chart_name = plot_widget.chart_name
                
                # Update time window limits on CustomViewBox to fixed range
                vb = plot_widget.getViewBox()
                if hasattr(vb, 'set_time_window_limits'):
                    vb.set_time_window_limits(0, self.current_time_window)
                    print(f"Debug: ViewBox limits set to 0 → {self.current_time_window}, offset={self.current_time_offset}")
                
                # Force X-axis range to be fixed (prevent any sliding)
                plot_widget.setXRange(0, self.current_time_window, padding=0)
                
                # Update bottom axis to show correct time ticks for new window
                bottom_axis = plot_widget.getAxis('bottom')
                bottom_axis.setRange(0, self.current_time_window)
                
                # Double-enforce the X-axis range to prevent any sliding
                vb = plot_widget.getViewBox()
                if hasattr(vb, 'setRange'):
                    try:
                        # Force the exact range with no padding
                        vb.setRange(x=[0, self.current_time_window], padding=0)
                    except:
                        # Fallback method
                        plot_widget.setXRange(0, self.current_time_window, padding=0)
                
                # Store reference for enforcement timer
                plot_widget.fixed_range = [0, self.current_time_window]
                
                # Store current Y-axis range to preserve zoom settings
                if not hasattr(plot_widget, 'zoom_y_range'):
                    plot_widget.zoom_y_range = None
                
                # Update data for each chart
                if chart_name.strip() == "SpO2":
                    x, y = self.get_spo2_data_for_window(self.current_time_window, self.current_time_offset)
                    if len(x) > 0 and len(y) > 0:
                        # Update normal line plot
                        plot_widget.plot_curve.setData(x, y)
                        # Ensure no fill for SpO2 graph
                        plot_widget.plot_curve.opts['fill'] = None
                        
                        # Check if custom axis properties are set, if yes, use them instead of dynamic adjustment
                        if hasattr(plot_widget, 'axis_properties'):
                            # Apply scaling first, then set the range
                            properties = plot_widget.axis_properties
                            low_value = properties.get('low_value', 35.0)
                            high_value = properties.get('high_value', 100.0)
                            
                            # Scale the data to fit within the custom range
                            y_min_orig = np.min(y)
                            y_max_orig = np.max(y)
                            y_range_orig = y_max_orig - y_min_orig
                            
                            if y_range_orig > 0:
                                y_range_new = high_value - low_value
                                y_scaled = ((y - y_min_orig) / y_range_orig) * y_range_new + low_value
                                plot_widget.plot_curve.setData(x, y_scaled)
                                print(f"Scaled SpO2 data from {y_min_orig:.2f}-{y_max_orig:.2f} to {low_value:.2f}-{high_value:.2f}")
                            
                            # Set the range
                            try:
                                plot_widget.setYRange(low_value, high_value, padding=0)
                            except TypeError:
                                plot_widget.setRange(yRange=[low_value, high_value], padding=0)
                        else:
                          
                            if plot_widget.zoom_y_range is not None:
                                # Use zoomed range during playback
                                new_y_min, new_y_max = plot_widget.zoom_y_range
                                print(f"Preserving zoom range during playback: {new_y_min} - {new_y_max}")
                            else:
                                # Dynamic SpO2 Y-axis adjustment (only if no custom properties)
                                avg_spo2 = np.mean(y)
                                if avg_spo2 > 95:
                                    # Adjust Y-axis to start from 90 when SpO2 is above 95
                                    new_y_min, new_y_max = 90, 100
                                else:
                                    # Use standard medical range
                                    new_y_min, new_y_max = 70, 100
                            
                            try:
                                plot_widget.setYRange(new_y_min, new_y_max)
                            except TypeError:
                                # Try alternative method for older pyqtgraph versions
                                plot_widget.setRange(yRange=[new_y_min, new_y_max])
                        
                        # Handle value labels for SpO2 (only in 10s-30s time window)
                        if 10 <= self.current_time_window <= 30:
                            # Always update value labels dynamically for real-time navigation
                            print(f"Creating/Updating SpO2 value labels for {self.current_time_window}s time window")
                            self.create_spo2_markers_and_labels(plot_widget, x, y)
                            print(f"Updated SpO2 value labels with {len(x)} points for time offset {self.current_time_offset}s")
                        else:
                            # Time window is outside 10s-30s range, remove value labels if they exist
                            if hasattr(plot_widget, 'value_labels'):
                                for label in plot_widget.value_labels:
                                    plot_widget.removeItem(label)
                                plot_widget.value_labels = []
                            print(f"Removed SpO2 value labels for {self.current_time_window}s time window")
                else:
                    # Update simulated data for ALL other signals
                    time_points = int(self.current_time_window * 10)
                    x = np.linspace(0, self.current_time_window, time_points)
                    freq = plot_widget.graph_frequency
                    amp = plot_widget.graph_amplitude
                    offset = plot_widget.graph_offset
                    y = np.sin(x * freq * 2 * np.pi) * amp + offset + (np.random.rand(time_points) - 0.5) * amp * 0.1
                    y = self.smooth_data(x, y, window_size=5)
                    plot_widget.plot_curve.setData(x, y)
                    
                    # Apply custom axis properties if they exist
                    if hasattr(plot_widget, 'axis_properties'):
                        
                        properties = plot_widget.axis_properties
                        low_value = properties.get('low_value', 35.0)
                        high_value = properties.get('high_value', 100.0)
                        y_min_orig = np.min(y)
                        y_max_orig = np.max(y)
                        y_range_orig = y_max_orig - y_min_orig
                        
                        if y_range_orig > 0:
                            y_range_new = high_value - low_value
                            y_scaled = ((y - y_min_orig) / y_range_orig) * y_range_new + low_value
                            plot_widget.plot_curve.setData(x, y_scaled)
                            print(f"Scaled {chart_name} data from {y_min_orig:.2f}-{y_max_orig:.2f} to {low_value:.2f}-{high_value:.2f}")
                        
                        # Set the range
                        try:
                            plot_widget.setYRange(low_value, high_value, padding=0)
                        except TypeError:
                            plot_widget.setRange(yRange=[low_value, high_value], padding=0)
                    
                    print(f"Updated {chart_name} with {time_points} points for {self.current_time_window}s window")
        
                
        # Render dynamic selections for current time window
        self.render_dynamic_selections()
        
        # Update apnea events display for current time window
        self.update_apnea_events_display()
    
    def set_time_window(self, seconds):
        """Set the time window for the sleep monitoring chart (legacy method for compatibility)"""
        print(f"🔍 DEBUG: set_time_window({seconds}) called in sleep_monitor_chart.py")
        # Update current_time_window variable
        self.current_time_window = seconds
        
        # Use dashboard controls if available, otherwise use local controls
        dropdown = getattr(self, 'dashboard_time_window_dropdown', None) or getattr(self, 'time_window_dropdown', None)
        if dropdown:
            # Find matching dropdown item and set it
            for i in range(dropdown.count()):
                if dropdown.itemData(i) == seconds:
                    dropdown.setCurrentIndex(i)
                    break
            
            # Check if charts exist before refreshing
            chart_count = self.charts_layout.count()
            print(f"Debug: set_time_window called with {seconds}s, charts exist: {chart_count > 0}, count: {chart_count}")
            
            # Update charts with new time window (refresh data only, don't recreate charts)
            if chart_count > 0:
                print(f"Debug: Calling refresh_charts from set_time_window")
                self.refresh_charts()
                self.restore_all_selections()
            else:
                print(f"Debug: No charts exist, calling update_charts_for_time_window instead")
                self.update_charts_for_time_window(seconds)
            
            print(f"Time window set to: {seconds} seconds")

    
    def update_charts_for_time_window(self, seconds):
        """Update chart data based on time window selection"""
        print(f"Debug: update_charts_for_time_window called with {seconds} seconds")
        
        # Clear existing charts
        for i in reversed(range(self.charts_layout.count())):
            child = self.charts_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
        
        # Clear hidden graphs and dropdown when time window changes
        self.hidden_graphs.clear()
        hidden_dropdown = getattr(self, 'dashboard_hidden_graphs_dropdown', None) or getattr(self, 'hidden_graphs_dropdown', None)
        if hidden_dropdown:
            hidden_dropdown.clear()
            hidden_dropdown.addItem("Select to restore...")
            hidden_dropdown.setEnabled(False)
        
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
          
            self.graph_order.append(name)
        
            
    def create_status_bar(self):
        """Create bottom status bar with professional playback controls"""
        frame = QFrame()
        frame.setObjectName("statusBar")
        frame.setMinimumHeight(44)
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(15)
        
        # Playback Controls Container - Professional styling like dashboard
        controls_container = QFrame()
        controls_container.setObjectName("playbackControlsContainer")
        controls_container.setStyleSheet("""
            QFrame#playbackControlsContainer {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        
        controls_layout = QHBoxLayout(controls_container)
        controls_layout.setContentsMargins(8, 4, 8, 4)
        controls_layout.setSpacing(8)
        
        
        # Play/Pause Button - Dashboard style
        self.play_pause_btn = QPushButton("▶ Play")
        self.play_pause_btn.setObjectName("playbackPlayButton")
        self.play_pause_btn.clicked.connect(self.toggle_playback)
        self.play_pause_btn.setFixedHeight(24)
        self.play_pause_btn.setMinimumWidth(70)
        self.play_pause_btn.setStyleSheet("""
            QPushButton#playbackPlayButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #3b82f6, stop: 1 #2563eb
                );
                color: white;
                border: 1px solid #1d4ed8;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 8px;
            }
            QPushButton#playbackPlayButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #2563eb, stop: 1 #1d4ed8
                );
                border: 1px solid #1e40af;
            }
            QPushButton#playbackPlayButton:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #1d4ed8, stop: 1 #1e40af
                );
            }
        """)
        
        # Time Label - Dashboard style
        time_label = QLabel("Position:")
        time_label.setStyleSheet("font-size: 11px; font-weight: 600; color: #374151;")
        controls_layout.addWidget(time_label)
        
        # Time Position Display - Clear professional display
        self.time_position_label = QLabel("00:00:00")
        self.time_position_label.setObjectName("timePositionLabel")
        self.time_position_label.setFixedHeight(22)
        self.time_position_label.setMinimumWidth(70)
        self.time_position_label.setStyleSheet("""
            QLabel#timePositionLabel {
                background-color: #f0f9ff;
                color: #1e40af;
                border: 1px solid #93c5fd;
                border-radius: 4px;
                padding: 2px 8px;
                font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
                font-weight: 600;
                font-size: 11px;
            }
        """)
        
        # Speed Label - Dashboard style
        self.speed_label = QLabel("Speed:")
        self.speed_label.setStyleSheet("font-size: 11px; font-weight: 600; color: #374151;")
        
        # Speed Dropdown - Dashboard style
        self.speed_combo = QComboBox()
        self.speed_combo.setObjectName("speedCombo")
        self.speed_combo.addItems(["0.5x", "1.0x", "2.0x", "4.0x"])
        self.speed_combo.setCurrentIndex(1)  
        self.speed_combo.currentTextChanged.connect(self.change_playback_speed)
        self.speed_combo.setFixedHeight(22)
        self.speed_combo.setMinimumWidth(80)  
        self.speed_combo.setStyleSheet("""
            QComboBox {
                background: #ffffff;
                color: #374151;
                border: 1px solid #d1d5db;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 500;
                min-width: 80px;
            }
            QComboBox:hover {
                border: 1px solid #9ca3af;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-top: 3px solid #6b7280;
                margin-right: 4px;
            }
            QComboBox QAbstractItemView {
                background: #ffffff;
                border: 1px solid #d1d5db;
                selection-background-color: #eff6ff;
                selection-color: #1e40af;
                min-width: 80px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QComboBox QAbstractItemView::item {
                padding: 4px 12px;
                min-height: 20px;
                border: none;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #eff6ff;
                color: #1e40af;
            }
        """)
        
        # Add all controls to container
        controls_layout.addWidget(self.play_pause_btn)
        controls_layout.addWidget(self.time_position_label)
        
        # Add divider
        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setFrameShadow(QFrame.Sunken)
        divider.setStyleSheet("""
            QFrame {
                background-color: #d1d5db;
                color: #d1d5db;
                max-width: 1px;
                min-width: 1px;
            }
        """)
        controls_layout.addWidget(divider)
        
        controls_layout.addWidget(self.speed_label)
        controls_layout.addWidget(self.speed_combo)
        
        # Add controls container to main layout
        layout.addWidget(controls_container)
        layout.addStretch()
        
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
            print(f"DEBUG: Creating chart for {name}")
            chart = self.create_signal_chart(name, color, freq, amp, offset)
            self.charts_layout.addWidget(chart, stretch=1)
            # Track the original order
            self.graph_order.append(name)
        
        print("DEBUG: All charts created in init_charts")
        # INITIAL VIEWBOX SYNC (Fix first-time rendering)
        QTimer.singleShot(150, self._initial_viewbox_sync)
    
    def _initial_viewbox_sync(self):
        """Initial ViewBox synchronization to fix first-time rendering issue"""
        print("Debug: _initial_viewbox_sync called - fixing first-time rendering")
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            if hasattr(container, 'plot_widget'):
                pw = container.plot_widget
                
                # Force X-axis range update
                start = 0
                end = self.current_time_window
                pw.setXRange(start, end, padding=0)
                
                # Force redraw
                pw.getViewBox().update()
                pw.repaint()
                print(f"Initial ViewBox sync for {pw.chart_name}: {start} → {end}")

        
    def load_spo2_data(self, csv_path):
        """Load SpO2 data from CSV file and store full data for time window filtering"""
        try:
            # Read CSV file directly using pandas
            df = pd.read_csv(csv_path)
            
            # Handle different column name formats
            if 'Timestamp' in df.columns and 'SpO2 (%)' in df.columns:
                # Use the actual column names from your CSV
                timestamp_col = 'Timestamp'
                spo2_col = 'SpO2 (%)'
            elif 'timestamp' in df.columns and 'spo2' in df.columns:
                # Use lowercase column names
                timestamp_col = 'timestamp'
                spo2_col = 'spo2'
            else:
                # Try to find the columns automatically
                timestamp_col = df.columns[0]  # First column
                spo2_col = df.columns[1]       # Second column
            
            # Convert timestamp to datetime and calculate relative time in seconds
            df['timestamp'] = pd.to_datetime(df[timestamp_col])
            start_time = df['timestamp'].iloc[0]
            df['time_seconds'] = (df['timestamp'] - start_time).dt.total_seconds()
            
            # Extract time and SpO2 values
            time_data = df['time_seconds'].values
            spo2_data = df[spo2_col].values
            
            # Convert SpO2 data to numeric if it's not already
            spo2_data = pd.to_numeric(spo2_data, errors='coerce')
            
       
            nan_count = np.sum(np.isnan(spo2_data))
            if nan_count > 0:
                print(f"Warning: Found {nan_count} NaN values in SpO2 data, removing them")
                valid_indices = ~np.isnan(spo2_data)
                spo2_data = spo2_data[valid_indices]
                time_data = time_data[valid_indices]
            
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
        csv_path = "/Users/ptr/Downloads/spo2_6hr_data.csv"
        time_data, spo2_data = self.load_spo2_data(csv_path)
        if len(time_data) > 0:
            # Refresh charts to display new data
            self.refresh_charts()
            QMessageBox.information(self, "Success", 
                f"SpO2 data loaded successfully!\n"
                f"Data points: {len(time_data)}\n"
                f"Duration: {time_data[-1]/3600:.1f} hours")
    
    def smooth_data(self, x_data, y_data, window_size=5):
        """Apply smoothing to data using moving average for medical-grade smoothness"""
        if len(y_data) < window_size:
            # If data is too short, return original data
            return y_data
        
        try:
            # Use moving average for smooth medical data
            window_size = min(window_size, len(y_data))
            if window_size >= 3:
                # Create weights for weighted moving average (center-weighted)
                weights = np.ones(window_size)
                weights[window_size//2] = 2.0  
                weights = weights / weights.sum()
                
                # Apply convolution with 'valid' mode to prevent edge artifacts, then pad
                y_smooth_valid = np.convolve(y_data, weights, mode='valid')
                
                # Pad the smoothed data to match original length using original edge values
                pad_size = (len(y_data) - len(y_smooth_valid)) // 2
                y_smooth = np.concatenate([
                    y_data[:pad_size],  
                    y_smooth_valid,     
                    y_data[-pad_size:]  
                ])
                
                return y_smooth
            else:
                return y_data
        except:
            # Fallback to original data if smoothing fails
            return y_data
    
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
        
        
        num_samples = len(window_spo2)
        if num_samples == 0:
            return np.array([]), np.array([])
        
        # Generate time points: 0, 0.1, 0.2, ... up to time_window_seconds
        window_time = np.arange(num_samples) / samples_per_second
        
        # Apply gentle smoothing to SpO2 data for better visual appearance while preserving real patterns
        window_spo2 = self.smooth_data(window_time, window_spo2, window_size=5)
        
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
            'desaturation_events': np.sum(spo2_data < 95),  # Normal SpO2 threshold
            'total_points': len(spo2_data)
        }
    
    def create_signal_chart(self, name, color, frequency, amplitude, offset):
        """Create a single signal trace chart with side label"""
        
        container = QWidget()
        container.setObjectName("signalChartContainer")
        container.setMinimumHeight(120)  
        container.setMaximumHeight(120)  
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # Apply professional double-shaded medical styling to container
        container.setStyleSheet("""
            QWidget#signalChartContainer {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.45 #f8fafc,
                    stop: 0.55 #f1f5f9,
                    stop: 1 #e2e8f0
                );
                border: 2px solid #cbd5e1;
                border-bottom: 3px solid #000000;
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
                border-bottom: 3px solid #000000;
                box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
            }
        """)
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(2, 2, 2, 2)  # Reduced padding to increase graph area
        container_layout.setSpacing(4) # Reduced spacing between label and plot
        
        # Side Label
        label_frame = QFrame()
        label_frame.setFixedWidth(120) # Increased width to accommodate longer text
        label_frame.setObjectName("labelFrame")
        # Apply professional styling to label frame
        label_frame.setStyleSheet("""
            QFrame#labelFrame {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #f8fafc,
                    stop: 0.5 #ffffff,
                    stop: 1 #f1f5f9
                );
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                margin: 2px;
            }
        """)
        label_layout = QVBoxLayout(label_frame)
        label_layout.setContentsMargins(4, 2, 4, 2)
        label_layout.setAlignment(Qt.AlignCenter)
        
        label = QLabel(name)
        label.setObjectName("chartSideLabel")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignCenter)
        # Make label clickable
        label.setCursor(Qt.PointingHandCursor)
        label.setStyleSheet("""
            QLabel#chartSideLabel {
                font-size: 11px;
                font-weight: 700;
                color: #1e293b;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #f8fafc,
                    stop: 1 #f1f5f9
                );
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 4px;
                text-align: center;
            }
            QLabel#chartSideLabel:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #dbeafe,
                    stop: 1 #bfdbfe
                );
                border: 1px solid #3b82f6;
                color: #1e40af;
            }
        """)
        # COMPLETELY REMOVE click event handler - labels should never hide graphs
        
        label_layout.addWidget(label)
        
        container_layout.addWidget(label_frame)
        
        # Plot Container with Zoom Controls
        plot_container = QWidget()
        plot_container.setObjectName("plotContainer")
        # Apply professional double-shaded styling to plot container
        plot_container.setStyleSheet("""
            QWidget#plotContainer {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.3 #fafbfc,
                    stop: 0.7 #f8fafc,
                    stop: 1 #f1f5f9
                );
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                margin: 1px;
            }
        """)
        plot_container_layout = QVBoxLayout(plot_container)
        plot_container_layout.setContentsMargins(0, 0, 0, 0)
        plot_container_layout.setSpacing(1)
        
        # Zoom Controls
        zoom_frame = QFrame()
        zoom_frame.setObjectName("zoomControlsFrame")
        # Apply professional styling to zoom controls frame
        zoom_frame.setStyleSheet("""
            QFrame#zoomControlsFrame {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f8fafc,
                    stop: 0.5 #ffffff,
                    stop: 1 #f1f5f9
                );
                border: 1px solid #e2e8f0;
                border-radius: 4px;
                margin: 1px;
            }
        """)
        zoom_layout = QHBoxLayout(zoom_frame)
        zoom_layout.setContentsMargins(2, 1, 2, 1)
        zoom_layout.setSpacing(3)
        
        # Store original Y range for zoom calculations
        self.original_y_min = 0
        self.original_y_max = 100
        self.current_y_min = 0
        self.current_y_max = 100
        
        # Zoom In button
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setObjectName("zoomButton")
        zoom_in_btn.setFixedSize(28, 20)
        # Apply professional styling to zoom buttons
        zoom_in_btn.setStyleSheet("""
            QPushButton#zoomButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #f1f5f9,
                    stop: 1 #e2e8f0
                );
                border: 1px solid #cbd5e1;
                border-radius: 3px;
                color: #475569;
                font-size: 12px;
                font-weight: 700;
                text-align: center;
            }
            QPushButton#zoomButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #dbeafe,
                    stop: 1 #bfdbfe
                );
                border: 1px solid #3b82f6;
                color: #1e40af;
            }
            QPushButton#zoomButton:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #dbeafe,
                    stop: 0.5 #93c5fd,
                    stop: 1 #60a5fa
                );
                border: 1px solid #1d4ed8;
                color: #1e3a8a;
            }
        """)
        print(f"DEBUG: Created zoom in button for {name} with objectName 'zoomButton'")
        
        def on_zoom_in():
            print(f"ZOOM IN BUTTON CLICKED for {name}")
            self.zoom_vertical(plot_widget, 0.8)
        
        zoom_in_btn.clicked.connect(on_zoom_in)
        zoom_layout.addWidget(zoom_in_btn)
        print(f"DEBUG: Added zoom in button to layout for {name}")
        
        # Zoom Out button
        zoom_out_btn = QPushButton("-")
        zoom_out_btn.setObjectName("zoomButton")
        zoom_out_btn.setFixedSize(28, 20)
        # Apply professional styling to zoom buttons
        zoom_out_btn.setStyleSheet("""
            QPushButton#zoomButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #f1f5f9,
                    stop: 1 #e2e8f0
                );
                border: 1px solid #cbd5e1;
                border-radius: 3px;
                color: #475569;
                font-size: 12px;
                font-weight: 700;
                text-align: center;
            }
            QPushButton#zoomButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #dbeafe,
                    stop: 1 #bfdbfe
                );
                border: 1px solid #3b82f6;
                color: #1e40af;
            }
            QPushButton#zoomButton:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #dbeafe,
                    stop: 0.5 #93c5fd,
                    stop: 1 #60a5fa
                );
                border: 1px solid #1d4ed8;
                color: #1e3a8a;
            }
        """)
        print(f"DEBUG: Created zoom out button for {name} with objectName 'zoomButton'")
        
        def on_zoom_out():
            print(f"ZOOM OUT BUTTON CLICKED for {name}")
            self.zoom_vertical(plot_widget, 1.2)
        
        zoom_out_btn.clicked.connect(on_zoom_out)
        zoom_layout.addWidget(zoom_out_btn)
        print(f"DEBUG: Added zoom out button to layout for {name}")
        
        # Reset button
        reset_btn = QPushButton("R")
        reset_btn.setObjectName("zoomButton")
        reset_btn.setFixedSize(28, 20)
        # Apply professional styling to zoom buttons
        reset_btn.setStyleSheet("""
            QPushButton#zoomButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #f1f5f9,
                    stop: 1 #e2e8f0
                );
                border: 1px solid #cbd5e1;
                border-radius: 3px;
                color: #475569;
                font-size: 12px;
                font-weight: 700;
                text-align: center;
            }
            QPushButton#zoomButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #dbeafe,
                    stop: 1 #bfdbfe
                );
                border: 1px solid #3b82f6;
                color: #1e40af;
            }
            QPushButton#zoomButton:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #dbeafe,
                    stop: 0.5 #93c5fd,
                    stop: 1 #60a5fa
                );
                border: 1px solid #1d4ed8;
                color: #1e3a8a;
            }
        """)
        print(f"DEBUG: Created reset button for {name} with objectName 'zoomButton'")
        
        def on_reset():
            print(f"RESET BUTTON CLICKED for {name}")
            self.reset_zoom(plot_widget)
        
        reset_btn.clicked.connect(on_reset)
        zoom_layout.addWidget(reset_btn)
        print(f"DEBUG: Added reset button to layout for {name}")
        
        zoom_layout.addStretch()
        plot_container_layout.addWidget(zoom_frame)
        
        zoom_layout.addStretch()
        plot_container_layout.addWidget(zoom_frame)
        zoom_layout.addStretch()
        plot_container_layout.addWidget(zoom_frame)
        
        # Create horizontal layout for buttons
        buttons_container = QFrame()
        buttons_container.setObjectName("buttonsContainer")
        # Apply professional styling to buttons container
        buttons_container.setStyleSheet("""
            QFrame#buttonsContainer {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.7 #fafbfc,
                    stop: 1 #f8fafc
                );
                border: none;
                border-radius: 4px;
                margin: 0px;
            }
        """)
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(4)
        
        # Add zoom frame (no expand button)
        buttons_layout.addWidget(zoom_frame)
        
        # Add buttons container to plot layout
        plot_container_layout.addWidget(buttons_container)
        print(f"DEBUG: Added zoom frame to buttons container for {name}")
        print(f"DEBUG: Zoom frame size: {zoom_frame.size()}, visible: {zoom_frame.isVisible()}")
        
        # Set up bottom border drag functionality on container
        container.drag_graph_name = name
        container.is_resizing = False
        container.resize_start_height = None
        container.resize_start_y = None
        
        # Enable mouse tracking for container
        container.setMouseTracking(True)
        
        # Override mouse events for container to handle bottom border dragging
        original_mouse_press = container.mousePressEvent
        original_mouse_move = container.mouseMoveEvent
        original_mouse_release = container.mouseReleaseEvent 
        def container_mouse_press(event):
            # Check if mouse is near bottom edge (last 15 pixels for full-width resize area)
            if event.button() == Qt.LeftButton:
                mouse_y = event.pos().y()
                container_height = container.height()
                resize_margin = 15
                bottom_edge = container_height - resize_margin
                
                if mouse_y >= bottom_edge:
                    # Start resizing
                    container.is_resizing = True
                    container.resize_start_height = container_height
                    container.resize_start_y = event.globalY()
                    container.setCursor(Qt.SizeVerCursor)
                    return  # Don't call original handler
                else:
                    # Call original mouse press if not resizing
                    if original_mouse_press:
                        original_mouse_press(event)
        
        def container_mouse_move(event):
            if container.is_resizing and event.buttons() == Qt.LeftButton:
                # Handle resizing
                delta_y = event.globalY() - container.resize_start_y
                new_height = container.resize_start_height + delta_y
                
                # Set constraints
                min_height = 120  # Original height, prevent shrinking below this
                max_height = 400
                new_height = max(min_height, min(max_height, new_height))
                
                # Apply new height
                container.setMinimumHeight(new_height)
                container.setMaximumHeight(new_height)
                container.updateGeometry()
                self.charts_widget.updateGeometry()
            else:
                # Check if mouse is near bottom edge for cursor change
                mouse_y = event.pos().y()
                container_height = container.height()
                resize_margin = 15
                bottom_edge = container_height - resize_margin
                
                if mouse_y >= bottom_edge:
                    container.setCursor(Qt.SizeVerCursor)
                else:
                    container.setCursor(Qt.ArrowCursor)
                
                # Call original mouse move if not resizing
                if original_mouse_move:
                    original_mouse_move(event)
        
        def container_mouse_release(event):
            if container.is_resizing:
                # Finish resizing
                container.is_resizing = False
                container.setCursor(Qt.ArrowCursor)
            else:
                # Call original mouse release if not resizing
                if original_mouse_release:
                    original_mouse_release(event)
        
        # Assign the mouse event handlers to container
        container.mousePressEvent = container_mouse_press
        container.mouseMoveEvent = container_mouse_move
        container.mouseReleaseEvent = container_mouse_release
        
        # Plot Widget with custom ViewBox
        plot_widget = pg.PlotWidget(viewBox=CustomViewBox())
        plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        plot_widget.setAlignment(Qt.AlignCenter)
        # Remove all grid lines for clean white background
        plot_widget.showGrid(x=False, y=False)
        
        # Remove right-click context menu
        
        # Apply professional medical styling to plot widget
        plot_widget.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.95 #ffffff,
                    stop: 1 #f8fafc
                );
                border: 1px solid #e2e8f0;
                border-radius: 4px;
                margin: 2px;
            }
        """)
        
        # Define medical standard Y-axis ranges for each signal type
        y_axis_ranges = {
            "Body Position": (0, 4),     # 0=Supine, 1=Right, 2=Left, 3=Prone, 4=Upright
            "Airflow": (-2, 2),         # Respiratory airflow in normalized units
            "Snoring": (0, 100),        # Snoring intensity percentage
            "Thorax": (-100, 100),      # Chest respiratory effort movement
            "Abdomen": (-100, 100),     # Abdominal respiratory effort movement
            "SpO2": (70, 100),          # Medical SpO2 range (70-100%) - extended for hypoxia
            "Pulse": (30, 250),         # Pulse rate in BPM - extended range
            "Body Movement": (0, 100),   # Movement intensity percentage
            "PR/HR": (30, 250)          # Pulse/Heart Rate in BPM - extended range
        }
        
        # Get the appropriate Y-axis range for this signal
        signal_name = name.strip()
        y_min, y_max = y_axis_ranges.get(signal_name, (0, 100))  # Default to 0-100 if not found
        
        # Dynamic SpO2 Y-axis adjustment for main chart
        if signal_name == "SpO2":
            # For SpO2, we'll set initial range but adjust it dynamically when data is loaded
            initial_y_min, initial_y_max = y_min, y_max
        else:
            initial_y_min, initial_y_max = y_min, y_max
        
        # Set fixed Y-axis range based on medical standards
        try:
            plot_widget.setYRange(initial_y_min, initial_y_max)
        except TypeError:
            # Try alternative method for older pyqtgraph versions
            plot_widget.setRange(yRange=[initial_y_min, initial_y_max])
        
        # Restrict zoom to Y-axis only (amplitude zoom) - disable X-axis to prevent sliding
        plot_widget.setMouseEnabled(x=False, y=True)
        
        # Disable auto-range and set fixed limits
        plot_widget.enableAutoRange(axis='y', enable=False)
        try:
            plot_widget.setLimits(yMin=y_min, yMax=y_max)
        except TypeError:
            # Try alternative method for older pyqtgraph versions
            plot_widget.setLimits(yMin=y_min, yMax=y_max)
            
        # Set X-axis to show time values based on current time window
        bottom_axis = plot_widget.getAxis('bottom')
        bottom_axis.setStyle(showValues=True)  # Show time values
        bottom_axis.setLabel('Time (s)', units='s')  # Add axis label
        bottom_axis.setHeight(30)  # Ensure enough space for labels
        
        left_axis = plot_widget.getAxis('left')
        left_axis.setStyle(showValues=True)   # Show Y-axis values
        
        # Reduce font size of axis tick labels
        from PyQt5.QtGui import QFont
        small_font = QFont()
        small_font.setPointSize(8)  # Smaller font size for axis numbers
        bottom_axis.setTickFont(small_font)  # X-axis numbers
        left_axis.setTickFont(small_font)    # Y-axis numbers
        
        # Ensure axis ticks are visible
        bottom_axis.setPen('k')  # Black color for visibility
        left_axis.setPen('k')    # Black color for visibility
        bottom_axis.setTextPen('k')  # Black text for visibility
        left_axis.setTextPen('k')    # Black text for visibility
        
        # Set X-axis range to show time window from 0 to current_time_window
        plot_widget.setXRange(0, self.current_time_window)
        
        # Set time window limits on CustomViewBox to enforce zoom constraints
        vb = plot_widget.getViewBox()
        if hasattr(vb, 'set_time_window_limits'):
            vb.set_time_window_limits(0, self.current_time_window)
        
        plot_widget.setMouseEnabled(x=False, y=True)
        plot_widget.hideButtons()  # Hide the 'A' button
        
        # Center the plot widget in its container
        plot_container_layout.setAlignment(plot_widget, Qt.AlignCenter)
        
        # Generate signal data
        if name.strip() == "SpO2":
            # Get SpO2 data for current time window
            if self.spo2_full_data is None:
                # Load data from the specific CSV file
                csv_path = "/Users/ptr/Downloads/spo2_6hr_data.csv"
                print(f"Loading SpO2 data from: {csv_path}")
                self.load_spo2_data(csv_path)
            
            # Get filtered data for current time window
            x, y = self.get_spo2_data_for_window(self.current_time_window, self.current_time_offset)
            
            # If no data available, fallback to simulated data
            if len(x) == 0:
                print("Falling back to simulated SpO2 data")
                time_points = 1000
                x = np.linspace(0, self.current_time_window, time_points)
                y = np.sin(x * frequency * 2 * np.pi) * amplitude + offset + (np.random.rand(time_points) - 0.5) * amplitude * 0.1
            else:
                # Use real SpO2 data as-is (no artificial baseline correction)
                print(f"Using real SpO2 data: {len(y)} points, range: {np.min(y):.1f}-{np.max(y):.1f}")
        else:
            # Generate simulated data for other signals based on time window
            time_points = int(self.current_time_window * 10)  # 10 Hz sampling rate
            x = np.linspace(0, self.current_time_window, time_points)
            y = np.sin(x * frequency * 2 * np.pi) * amplitude + offset + (np.random.rand(time_points) - 0.5) * amplitude * 0.1
            
            # Apply smoothing to all graph data for professional appearance
            y = self.smooth_data(x, y, window_size=5)
        
        # Plot the signal andltore reference for line visibility control
        pen = pg.mkPen(color=color, width=1.5)
        
        # Plot all graphs as normal line plots (no step ladder, no fill)
        plot_curve = plot_widget.plot(x, y, pen=pen, fill=None)

        # Add value labels for SpO2 graph - only in 10s-30s time window
        if name.strip() == "SpO2" and len(x) > 0 and len(y) > 0:
            # Check if current time window is between 10s and 30s
            if 10 <= self.current_time_window <= 30:
                # Add value labels on the graph (positioned exactly on data points)
                self.add_spo2_value_labels(plot_widget, x, y, self.current_time_window)
                
                print(f"SpO2 value labels enabled for {self.current_time_window}s time window")
            else:
                # Time window is outside 10s-30s range, no value labels
                # Clear value labels if they exist
                if hasattr(plot_widget, 'value_labels'):
                    for label in plot_widget.value_labels:
                        plot_widget.removeItem(label)
                    plot_widget.value_labels = []
                
                print(f"SpO2 value labels disabled for {self.current_time_window}s time window")

        plot_widget.graph_name = name
        plot_widget.graph_color = color
        plot_widget.graph_frequency = frequency
        plot_widget.graph_amplitude = amplitude
        plot_widget.graph_offset = offset
        
        # Store chart name and plot widget for selection handling
        plot_widget.chart_name = name
        plot_widget.plot_curve = plot_curve
        
        # Enable mouse tracking for area selection (disable X-axis to prevent sliding)
        plot_widget.setMouseEnabled(x=False, y=True)
        plot_widget.scene().sigMouseMoved.connect(lambda pos, pw=plot_widget: self.on_mouse_moved(pos, pw))
        plot_widget.mousePressEvent = lambda event, pw=plot_widget: self.custom_mouse_press(event, pw)
        plot_widget.mouseReleaseEvent = lambda event, pw=plot_widget: self.custom_mouse_release(event, pw)
        
        # Connect resize event to update overlay positions
        vb = plot_widget.getViewBox()
        vb.sigResized.connect(lambda pw=plot_widget: self.on_plot_resized(pw))
        
        # Remove click event handler to prevent graph hiding - disable mouse press on container
        container.setAcceptDrops(True)
        # Remove mouse press event to prevent graph hiding
        # container.mousePressEvent = lambda event: self.start_drag(event, name, container)
        # Don't override mouse events here - resize functionality is already assigned above
        
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
                    print(f"Debug: Allowing resize of expanded container '{chart_name}' (current: {current_height}px, attempted: {new_height}px)")
                    # Allow Qt's normal resize flow even for expanded containers
                    if original_resize:
                        original_resize(event)
                    self.on_container_resized(container)
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
    
        
    def toggle_graph_visibility(self, graph_name, container, label):
        """Toggle graph visibility - hide graph and add to hidden graphs dropdown"""
        if graph_name in self.hidden_graphs:
            # Graph is already hidden, restore it
            self.restore_hidden_graph(graph_name)
        else:
            # Hide the graph and add to hidden graphs
            self.hide_graph(graph_name, container, label)
    
    def hide_graph(self, graph_name, container, label):
        """Hide a graph and store its data for later restoration"""
        # Store graph data before hiding
        plot_widget = container.plot_widget
        
        self.hidden_graphs[graph_name] = {
            'container': container,
            'plot_widget': plot_widget,
            'plot_curve': plot_widget.plot_curve,
            'color': plot_widget.graph_color if hasattr(plot_widget, 'graph_color') else '#000000',
            'frequency': plot_widget.graph_frequency if hasattr(plot_widget, 'graph_frequency') else 1.0,
            'amplitude': plot_widget.graph_amplitude if hasattr(plot_widget, 'graph_amplitude') else 1.0,
            'offset': plot_widget.graph_offset if hasattr(plot_widget, 'graph_offset') else 0,
            'position': self.charts_layout.indexOf(container)
        }
        
        # Hide the container
        container.hide()
        
        # Update label to show it's hidden
        label.setText(f"{graph_name} (Hidden)")
        label.setStyleSheet("""
            QLabel#chartSideLabel {
                font-size: 11px;
                font-weight: 700;
                color: #6b7280;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f9fafb,
                    stop: 0.5 #f3f4f6,
                    stop: 1 #e5e7eb
                );
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 6px 4px;
                text-align: center;
            }
        """)
        
        # Update hidden graphs dropdown
        self.update_hidden_graphs_dropdown()
        
        print(f"Graph '{graph_name}' hidden and added to hidden graphs")
    
    def restore_hidden_graph(self, graph_name):
        """Restore a hidden graph"""
        if graph_name not in self.hidden_graphs:
            return
        
        graph_data = self.hidden_graphs[graph_name]
        container = graph_data['container']
        
        # Show the container
        container.show()
        
        # Find and update the label
        label = container.findChild(QLabel, "chartSideLabel")
        if label:
            label.setText(graph_name)
            label.setStyleSheet("""
                QLabel#chartSideLabel {
                    font-size: 11px;
                    font-weight: 700;
                    color: #1e293b;
                    background: qlineargradient(
                        x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #ffffff,
                        stop: 0.5 #f8fafc,
                        stop: 1 #f1f5f9
                    );
                    border: 1px solid #cbd5e1;
                    border-radius: 6px;
                    padding: 6px 4px;
                    text-align: center;
                }
                QLabel#chartSideLabel:hover {
                    background: qlineargradient(
                        x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #ffffff,
                        stop: 0.5 #dbeafe,
                        stop: 1 #bfdbfe
                    );
                    border: 1px solid #3b82f6;
                    color: #1e40af;
                }
            """)
        
        # Remove from hidden graphs
        del self.hidden_graphs[graph_name]
        
        # Update hidden graphs dropdown
        self.update_hidden_graphs_dropdown()
        
        print(f"Graph '{graph_name}' restored")
    
    def update_hidden_graphs_dropdown(self):
        """Update the hidden graphs dropdown with current hidden graphs"""
        hidden_dropdown = getattr(self, 'dashboard_hidden_graphs_dropdown', None) or getattr(self, 'hidden_graphs_dropdown', None)
        if hidden_dropdown:
            # Clear current items
            hidden_dropdown.clear()
            
            if self.hidden_graphs:
                # Add hidden graphs to dropdown
                hidden_dropdown.addItem("Select to restore...")
                for graph_name in sorted(self.hidden_graphs.keys()):
                    hidden_dropdown.addItem(graph_name)
                hidden_dropdown.setEnabled(True)
            else:
                # No hidden graphs
                hidden_dropdown.addItem("No hidden graphs")
                hidden_dropdown.setEnabled(False)
    
        
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
    
    def restore_hidden_graph_from_dropdown(self, index):
        """Restore a hidden graph when selected from dropdown"""
        # Ignore the placeholder item (index 0)
        if index == 0:
            return
        
        # Get the graph name from dropdown
        hidden_dropdown = getattr(self, 'dashboard_hidden_graphs_dropdown', None) or getattr(self, 'hidden_graphs_dropdown', None)
        if not hidden_dropdown:
            return
            
        graph_name = hidden_dropdown.itemText(index)
        
        # Use the new restore functionality
        self.restore_hidden_graph(graph_name)
        
        # Reset dropdown to placeholder
        hidden_dropdown.setCurrentIndex(0)
                    
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
        
        # Get chart name to apply proper limits
        chart_name = getattr(plot_widget, 'chart_name', '')
        
        # Define medical standard Y-axis ranges for each signal type
        y_axis_ranges = {
            "Body Position": (0, 4),     
            "Airflow": (-2, 2),        
            "Snoring": (0, 100),       
            "Thorax": (-100, 100),     
            "Abdomen": (-100, 100),     
            "SpO2": (70, 100),      
            "Pulse": (30, 250),        
            "Body Movement": (0, 100),   
            "PR/HR": (30, 250)          
        }
        
        # Get proper Y-axis limits for this chart
        y_min_limit, y_max_limit = y_axis_ranges.get(chart_name.strip(), (0, 100))
        
        # Apply chart-specific limits
        if new_y_min < y_min_limit:
            new_y_min = y_min_limit
            new_y_max = new_y_min + new_range_size
        elif new_y_max > y_max_limit:
            new_y_max = y_max_limit
            new_y_min = y_max_limit - new_range_size
            
        try:
            plot_widget.setYRange(new_y_min, new_y_max)
            # Store zoom range to persist during playback
            plot_widget.zoom_y_range = (new_y_min, new_y_max)
            print(f"Stored zoom range for {chart_name}: {new_y_min} - {new_y_max}")
        except TypeError:
            # Try alternative method for older pyqtgraph versions
            plot_widget.setRange(yRange=[new_y_min, new_y_max])
            # Store zoom range to persist during playback
            plot_widget.zoom_y_range = (new_y_min, new_y_max)
            print(f"Stored zoom range for {chart_name}: {new_y_min} - {new_y_max}")
    
    def reset_zoom(self, plot_widget):
        """Reset zoom to original medical standard range"""
        # Define medical standard Y-axis ranges
        y_axis_ranges = {
            "Body Position": (0, 4),   
            "Airflow": (-2, 2),         
            "Snoring": (0, 100),        
            "Thorax": (-100, 100),     
            "Abdomen": (-100, 100),     
            "SpO2": (70, 100),          
            "Pulse": (30, 250),         
            "Body Movement": (0, 100),  
            "PR/HR": (30, 250)          
        }
        
        # Get the chart name from the plot widget
        chart_name = getattr(plot_widget, 'chart_name', '')
        y_min, y_max = y_axis_ranges.get(chart_name.strip(), (0, 100))
        
        try:
            plot_widget.setYRange(y_min, y_max)
       
            plot_widget.zoom_y_range = None
            print(f"Reset zoom range for {chart_name}")
        except TypeError:
          
            plot_widget.setRange(yRange=[y_min, y_max])
           
            plot_widget.zoom_y_range = None
            print(f"Reset zoom range for {chart_name}")
    
    def toggle_playback(self):
        """Toggle between play and pause"""
        print(f"Toggle playback - Current state: {self.is_playing}")
        if self.is_playing:
            self.pause_playback()
        else:
            self.start_playback()
    
        
    def forward_playback(self):
        """Fast forward playback"""
        print(f"Forward button clicked - Playing: {self.is_playing}")
        if self.is_playing:
            # Jump forward by current time window
            self.current_time = self.current_time.addSecs(self.current_time_window)
            
            #  UPDATE OFFSET
            self.current_time_offset += self.current_time_window
            
            #  FORCE VIEWBOX UPDATE AND PLOT REDRAW
            for i in range(self.charts_layout.count()):
                container = self.charts_layout.itemAt(i).widget()
                if hasattr(container, 'plot_widget'):
                    pw = container.plot_widget
                    
                    # Force X-axis range update
                    start = 0
                    end = self.current_time_window
                    pw.setXRange(start, end, padding=0)
                    
                    # Force redraw
                    pw.getViewBox().update()
                    pw.repaint()
                    print(f"Updated ViewBox range to {start} → {end} for {pw.chart_name}")
            
            # DELAYED OVERLAY RENDER (IMPORTANT)
            QTimer.singleShot(0, self.render_dynamic_selections)
            
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
        # Use the time_position_label instead of current_time_label
        if hasattr(self, 'time_position_label'):
            self.time_position_label.setText(f"Current: {self.current_time.toString('HH:mm:ss')}")
    
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
        
        # Prevent selection update if context menu is active
        if hasattr(self, 'active_context_menu') and self.active_context_menu is not None:
            return
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
    
    def create_spo2_markers_and_labels(self, plot_widget, x_data, y_data):
        """Create value labels for SpO2 when they don't exist (no scatter plot dots)"""
        print(f"DEBUG: create_spo2_markers_and_labels called with {len(x_data)} points")
        
        # Add value labels on the graph (positioned exactly on data points)
        self.add_spo2_value_labels(plot_widget, x_data, y_data, self.current_time_window)
        
        print(f"Created SpO2 value labels for {self.current_time_window}s time window")
    
    def add_spo2_value_labels(self, plot_widget, x_data, y_data, time_window):
        """Add value labels on SpO2 graph at regular intervals like in the image"""
        # Clear existing value labels if any
        if hasattr(plot_widget, 'value_labels'):
            for label in plot_widget.value_labels:
                plot_widget.removeItem(label)
        plot_widget.value_labels = []
        
        # Get the actual displayed data (scaled if axis properties are applied)
        if hasattr(plot_widget, 'axis_properties'):
            
            current_data = plot_widget.plot_curve.getData()
            if current_data[0] is not None and len(current_data[0]) > 0:
                x_displayed, y_displayed = current_data
            else:
                x_displayed, y_displayed = x_data, y_data
        else:
            # Use original data when no axis properties
            x_displayed, y_displayed = x_data, y_data
        
        # Show labels on all data points for 10s and 30s windows
        if time_window == 10 or time_window == 30:
            # Add value labels for ALL data points
            for i in range(len(x_displayed)):
                x_pos = x_displayed[i]
                y_pos = y_displayed[i]
                
                # Get the original SpO2 value for display (not the scaled value)
                original_y = y_data[min(i, len(y_data)-1)]
                
                # Create text item with value
                text_item = pg.TextItem(
                    text=f"{int(original_y)}",  
                    color=(255, 0, 0), 
                    anchor=(0.5, 1.0)  
                )
                
                # Set font for better visibility while maintaining positioning
                from PyQt5.QtGui import QFont
                font = QFont()
                font.setPointSize(6)  
                font.setBold(True)
                text_item.setFont(font)
                
                # Position the text slightly above the displayed data point to sit on top
                offset_above = 0.2  
                text_item.setPos(x_pos, y_pos + offset_above)
                
                # Set anchor to bottom center to position on top of the line
                text_item.setAnchor((0.5, 1.0))  
                
                # Add to plot and store reference
                plot_widget.addItem(text_item)
                plot_widget.value_labels.append(text_item)
    
    
    def on_mouse_clicked(self, event, plot_widget):
        """Handle mouse click for area selection and label removal"""
        if event.button() == Qt.LeftButton:
            widget_pos = event.pos()
            widget_rect = plot_widget.rect()
            if not widget_rect.contains(widget_pos):
                return
            scene_pos = plot_widget.mapToScene(widget_pos)
            
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
        # Handle right mouse button for y-axis context menu
        if event.button() == Qt.RightButton:
            self.handle_right_click(event, plot_widget)
            return
            
        # Only handle left mouse button for area selection
        if event.button() != Qt.LeftButton:
            return
            
        # Prevent new selection if context menu is active
        if hasattr(self, 'active_context_menu') and self.active_context_menu is not None:
            return
            
        # Handle left click directly
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
        
        # Convert widget position to scene position
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
    
    def handle_right_click(self, event, plot_widget):
        """Handle right-click events on y-axis to show image options context menu"""
        widget_pos = event.pos()
        widget_rect = plot_widget.rect()
        
        if not widget_rect.contains(widget_pos):
            return
        
        # Check if click is on y-axis area (left side of the plot)
        y_axis_width = 60  
        if widget_pos.x() <= y_axis_width:
            self.show_graph_image_menu(event.globalPos(), plot_widget)
            print(f"Right-click on y-axis detected for {plot_widget.chart_name}")
    
    def show_graph_image_menu(self, global_pos, plot_widget):
        """Show context menu with image options for the specific graph"""
        menu = QMenu(self)
        menu.setTitle(f"Image Options - {plot_widget.chart_name}")
        
        # Save as PNG action
        save_png_action = QAction("Save as PNG", self)
        save_png_action.triggered.connect(lambda: self.save_graph_as_image(plot_widget, "PNG"))
        menu.addAction(save_png_action)
        
        # Save as JPG action
        save_jpg_action = QAction("Save as JPG", self)
        save_jpg_action.triggered.connect(lambda: self.save_graph_as_image(plot_widget, "JPG"))
        menu.addAction(save_jpg_action)
        
        # Copy to clipboard action
        copy_clipboard_action = QAction("Copy to Clipboard", self)
        copy_clipboard_action.triggered.connect(lambda: self.copy_graph_to_clipboard(plot_widget))
        menu.addAction(copy_clipboard_action)
        
        menu.addSeparator()
        
        # Export with high resolution action
        export_hd_action = QAction("Export High Resolution", self)
        export_hd_action.triggered.connect(lambda: self.export_graph_hd(plot_widget))
        menu.addAction(export_hd_action)
        
        menu.addSeparator()
        
        # Amplitude Axis Properties action
        amplitude_properties_action = QAction("Amplitude Axis Properties", self)
        amplitude_properties_action.triggered.connect(lambda: self.show_amplitude_axis_properties(plot_widget))
        menu.addAction(amplitude_properties_action)
        
        # Show the menu at the cursor position
        self.active_context_menu = menu
        menu.exec_(global_pos)
        self.active_context_menu = None
    
    def save_graph_as_image(self, plot_widget, format_type):
        """Save individual graph as image"""
        try:
            
            vb = plot_widget.getViewBox()
            
            
            exporter = pg.exporters.ImageExporter(vb)
            
            # Generate filename with timestamp and graph name
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_graph_name = plot_widget.chart_name.strip().replace(" ", "_").replace("/", "_")
            filename = f"{safe_graph_name}_{timestamp}.{format_type.lower()}"
            
            # Show save dialog
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                f"Save {plot_widget.chart_name} as {format_type}",
                filename,
                f"{format_type} Files (*.{format_type.lower()});;All Files (*)"
            )
            
            if file_path:
                exporter.export(file_path)
                QMessageBox.information(self, "Image Saved", 
                                   f"{plot_widget.chart_name} saved as:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", 
                               f"Failed to save {plot_widget.chart_name}:\n{str(e)}")
    
    def copy_graph_to_clipboard(self, plot_widget):
        """Copy graph to clipboard"""
        try:
            # Get the plot widget's view box
            vb = plot_widget.getViewBox()
            
            # Export the plot to an image in memory
            exporter = pg.exporters.ImageExporter(vb)
            
            # Get the image as QPixmap
            pixmap = exporter.export(toBytes=True)
            
            # Copy to clipboard
            clipboard = QApplication.clipboard()
            clipboard.setPixmap(QPixmap(pixmap))
            
            QMessageBox.information(self, "Copied to Clipboard", 
                               f"{plot_widget.chart_name} copied to clipboard!")
        except Exception as e:
            QMessageBox.critical(self, "Copy Error", 
                               f"Failed to copy {plot_widget.chart_name}:\n{str(e)}")
    
    def export_graph_hd(self, plot_widget):
        """Export graph in high resolution"""
        try:
            
            vb = plot_widget.getViewBox()
            
            exporter = pg.exporters.ImageExporter(vb)
            
            exporter.parameters()['width'] = 1920  
            exporter.parameters()['height'] = 1080  
            
            # Generate filename
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_graph_name = plot_widget.chart_name.strip().replace(" ", "_").replace("/", "_")
            filename = f"{safe_graph_name}_HD_{timestamp}.png"
            
            # Show save dialog
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                f"Export {plot_widget.chart_name} in High Resolution",
                filename,
                "PNG Files (*.png);;All Files (*)"
            )
            
            if file_path:
                exporter.export(file_path)
                QMessageBox.information(self, "HD Image Exported", 
                                   f"{plot_widget.chart_name} exported in HD:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", 
                               f"Failed to export {plot_widget.chart_name} in HD:\n{str(e)}")
    
    def show_amplitude_axis_properties(self, plot_widget):
        """Show amplitude axis properties dialog for the specific graph"""
        try:
            # Get current axis properties from the plot widget
            current_properties = self.get_current_axis_properties(plot_widget)
            
            # Create and show the dialog
            dialog = AmplitudeAxisPropertiesDialog(self, current_properties)
            dialog.properties_changed.connect(lambda props: self.apply_axis_properties(plot_widget, props))
            
            result = dialog.exec_()
            if result == QDialog.Accepted:
                print(f"Amplitude axis properties applied for {plot_widget.chart_name}")
            
        except Exception as e:
            QMessageBox.critical(self, "Properties Error", 
                               f"Failed to open amplitude axis properties:\n{str(e)}")
    
    def get_current_axis_properties(self, plot_widget):
        """Get current axis properties from the plot widget"""
        try:
            # Get the current Y-axis range
            view_range = plot_widget.getViewBox().viewRange()
            y_min, y_max = view_range[1]
            
            # Get the original Y-axis range if stored
            original_y_min = getattr(plot_widget, 'original_y_min', y_min)
            original_y_max = getattr(plot_widget, 'original_y_max', y_max)
            
            properties = {
                'low_value': float(y_min),
                'high_value': float(y_max),
                'limit_axis_range': False,  
                'limit_low_value': float(original_y_min),
                'limit_high_value': float(original_y_max),
                'auto_adjust': 'scale_to_fit'  
            }
            
            return properties
            
        except Exception as e:
            print(f"Error getting current axis properties: {e}")
            # Return default properties
            return {
                'low_value': 35.0,
                'high_value': 100.0,
                'limit_axis_range': False,
                'limit_low_value': 85.0,
                'limit_high_value': 100.0,
                'auto_adjust': 'scale_to_fit'
            }
    
    def apply_axis_properties(self, plot_widget, properties):
        """Apply the axis properties to the plot widget"""
        try:
            # Get the view box
            vb = plot_widget.getViewBox()
            
            # Apply new Y-axis range
            low_value = properties.get('low_value', 35.0)
            high_value = properties.get('high_value', 100.0)
            
            # Get current data and transform it to fit within the new range
            if hasattr(plot_widget, 'plot_curve') and plot_widget.plot_curve:
                current_data = plot_widget.plot_curve.getData()
                if current_data[0] is not None and len(current_data[0]) > 0:
                    x_data, y_data = current_data
                    
                    # Calculate the original data range
                    y_min_orig = np.min(y_data)
                    y_max_orig = np.max(y_data)
                    y_range_orig = y_max_orig - y_min_orig
                    
                    if y_range_orig > 0:
                        # Scale the data to fit within the new range
                        y_range_new = high_value - low_value
                        
                        # Transform data: map original range to new range
                        y_scaled = ((y_data - y_min_orig) / y_range_orig) * y_range_new + low_value
                        
                        # Update the plot with scaled data
                        plot_widget.plot_curve.setData(x_data, y_scaled)
                        
                        print(f"Scaled data from {y_min_orig:.2f}-{y_max_orig:.2f} to {low_value:.2f}-{high_value:.2f}")
            
            # Force the Y-axis range to exactly match the specified values
            try:
                plot_widget.setYRange(low_value, high_value, padding=0)
            except TypeError:
                # Try alternative method for older pyqtgraph versions
                plot_widget.setRange(yRange=[low_value, high_value], padding=0)
            
            # Apply manual range setting to override any auto-scaling
            vb.setRange(yRange=[low_value, high_value], padding=0)
            
            # Handle limit axis range
            if properties.get('limit_axis_range', False):
                limit_low = properties.get('limit_low_value', low_value)
                limit_high = properties.get('limit_high_value', high_value)
                
                # Set strict limits on the view box to prevent zooming beyond range
                try:
                    vb.setLimits(yMin=limit_low, yMax=limit_high)
                except TypeError:
                    # Try alternative method
                    vb.setLimits(yMin=limit_low, yMax=limit_high)
            else:
                # Set limits to match the current range to prevent unwanted scaling
                try:
                    vb.setLimits(yMin=low_value, yMax=high_value)
                except TypeError:
                    vb.setLimits(yMin=low_value, yMax=high_value)
            
            # Disable auto-range completely to maintain manual control
            auto_adjust = properties.get('auto_adjust', 'scale_to_fit')
            if auto_adjust == 'disabled':
              
                plot_widget.enableAutoRange(axis='y', enable=False)
                vb.enableAutoRange(axis='y', enable=False)
            elif auto_adjust == 'center':
              
                plot_widget.enableAutoRange(axis='y', enable=False)
                vb.enableAutoRange(axis='y', enable=False)
            else:  
               
                plot_widget.enableAutoRange(axis='y', enable=False)
                vb.enableAutoRange(axis='y', enable=False)
            
            # Store the properties in the plot widget for future reference
            plot_widget.axis_properties = properties
            
            # Force immediate update of the display
            plot_widget.update()
            vb.updateAutoRange()
            vb.updateViewRange()
            
            print(f"Applied axis properties to {plot_widget.chart_name}:")
            print(f"  Range: {low_value} - {high_value}")
            print(f"  Limit: {properties.get('limit_axis_range', False)}")
            print(f"  Auto-adjust: {auto_adjust}")
            
            # Update SpO2 value labels to match the new scaled data
            if plot_widget.chart_name.strip() == "SpO2" and hasattr(plot_widget, 'plot_curve'):
                current_data = plot_widget.plot_curve.getData()
                if current_data[0] is not None and len(current_data[0]) > 0:
                    x_data, y_data = current_data
                    # Recreate value labels with the scaled data positions
                    self.create_spo2_markers_and_labels(plot_widget, x_data, y_data)
                    print(f"Updated SpO2 value labels for new axis range: {low_value} - {high_value}")
            
            
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(100, lambda: self.force_range_update(plot_widget, low_value, high_value))
            
        except Exception as e:
            print(f"Error applying axis properties: {e}")
            QMessageBox.critical(self, "Apply Error", 
                               f"Failed to apply axis properties:\n{str(e)}")
    
    def force_range_update(self, plot_widget, low_value, high_value):
        """Force the range update to ensure it sticks"""
        try:
            vb = plot_widget.getViewBox()
            vb.setRange(yRange=[low_value, high_value], padding=0)
            plot_widget.setYRange(low_value, high_value, padding=0)
            plot_widget.update()
            
            
            if plot_widget.chart_name.strip() == "SpO2" and hasattr(plot_widget, 'plot_curve'):
                current_data = plot_widget.plot_curve.getData()
                if current_data[0] is not None and len(current_data[0]) > 0:
                    x_data, y_data = current_data
                 
                    self.create_spo2_markers_and_labels(plot_widget, x_data, y_data)
                    print(f"Force updated SpO2 value labels for range: {low_value} - {high_value}")
            
            print(f"Force updated range for {plot_widget.chart_name}: {low_value} - {high_value}")
        except Exception as e:
            print(f"Error in force range update: {e}")
    
    def custom_mouse_release(self, event, plot_widget):
        """Custom mouse release handler for reliable selection completion"""
        if event.button() == Qt.LeftButton:
            self.on_mouse_released(event, plot_widget)
    
    def on_container_resized(self, container):
        """Handle container resize to update overlay positions"""
        if hasattr(container, 'plot_widget'):
            # Simply re-render all overlays from absolute time data
            self.render_dynamic_selections()
    
    def on_plot_resized(self, plot_widget):
        """Handle plot widget resize/pan/zoom to update overlay positions"""
        # Simply re-render all overlays from absolute time data
        self.render_dynamic_selections()
    
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

                # Set selection active flag for modal interaction lock
                self.selection_active = True

                #  FORCE MENU OPEN
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
                
                    print("Selection too small, clearing")
                    self.clear_selection()
            else:
                # No proper selection made
                self.clear_selection()
    
    def update_selection_overlay(self, start_pos, end_pos):
        """Update the visual selection overlay using proper ViewBox transformation"""
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
        
        # Get data coordinates
        start_x = start_pos.x()
        end_x = end_pos.x()
        
        # Create data points
        start_point = QPointF(start_x, 0)
        end_point = QPointF(end_x, 0)
        
        # Convert data → scene
        start_scene = vb.mapViewToScene(start_point)
        end_scene = vb.mapViewToScene(end_point)
        
        # Convert scene → widget
        start_widget = self.current_selection_chart.mapFromScene(start_scene)
        end_widget = self.current_selection_chart.mapFromScene(end_scene)
        
        x_min = min(start_widget.x(), end_widget.x())
        x_max = max(start_widget.x(), end_widget.x())
        width = x_max - x_min
        
        # Ensure minimum width
        if width < 30:
            width = 30
        
        print(f"View range: {vb.viewRange()}")
        print(f"update_selection_overlay - Chart: {self.current_selection_chart.chart_name}")
        print(f"update_selection_overlay - Data coords: start={start_x}, end={end_x}")
        print(f"update_selection_overlay - Widget coords: x_min={x_min:.1f}, x_max={x_max:.1f}, width={width:.1f}")
        
        overlay.setGeometry(int(x_min), 0, int(width), self.current_selection_chart.height())
        overlay.setVisible(True)
        overlay.raise_()  
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
    
    def get_spo2_selection_info(self):
        """Get SpO2 values at selection start and end positions"""
        if not self.spo2_full_data or len(self.spo2_full_data[0]) == 0:
            return None
        
        if not self.selection_start or not self.selection_end:
            return None
        
        try:
            # Get SpO2 data
            time_data, spo2_data = self.spo2_full_data
            
            # Convert selection positions to time values (QPointF objects)
            start_time = self.selection_start.x()  
            end_time = self.selection_end.x()     
            
            # Add current time offset to get absolute time
            start_absolute_time = start_time + self.current_time_offset
            end_absolute_time = end_time + self.current_time_offset
            
            # Find closest data points
            start_idx = np.argmin(np.abs(time_data - start_absolute_time))
            end_idx = np.argmin(np.abs(time_data - end_absolute_time))
            
            # Get SpO2 values at those positions
            start_spo2 = spo2_data[start_idx]
            end_spo2 = spo2_data[end_idx]
            
            # Calculate difference
            difference = end_spo2 - start_spo2
            
            return {
                'start_value': start_spo2,
                'end_value': end_spo2,
                'difference': difference,
                'start_time': start_absolute_time,
                'end_time': end_absolute_time,
                'point_difference': abs(end_idx - start_idx)
            }
            
        except Exception as e:
            print(f"Error calculating SpO2 selection info: {e}")
            return None
    
    def get_most_recent_label(self, chart_name):
        """Get the most recently applied label for a chart"""
        if chart_name not in self.selection_labels or not self.selection_labels[chart_name]:
            return None
        
        # Get the last (most recent) label
        recent_selection = self.selection_labels[chart_name][-1]
        return recent_selection.get('label', None)
    
    def show_selection_menu(self):
        """Show dropdown menu with different options based on chart type"""
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
            
        # Create context menu
        print("Creating context menu...")
        menu = QMenu(self)
        menu.setTitle("Select Sleep Event Type")
        
        # Check if this is SpO2 chart
        chart_name = self.current_selection_chart.chart_name.strip()
        if "SpO2" in chart_name:
            menu.setTitle("Select Event")
            
            # No temporary SpO2 values during dragging - only show after selection is saved
            
            # Check if there's a recent label for this chart and show it
            current_label = self.get_most_recent_label(chart_name)
            if current_label:
                label_action = QAction(f"Applied: {current_label}", self)
                label_action.setEnabled(False)  # Make it non-clickable info text
                # Style it differently to show it's the current label
                label_action.setStyleSheet("color: #2563eb; font-weight: bold;")
                menu.addAction(label_action)
                menu.addSeparator()
            
            # Add simple desaturation option for SpO2
            saturation_action = QAction("Desaturation", self)
            saturation_action.triggered.connect(lambda: self.apply_selection_label("DE-SATURATION"))
            menu.addAction(saturation_action)
        else:
            # For other charts, show sleep apnea options
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
        
      
        menu.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint | Qt.WindowStaysOnTopHint)
        menu.setFixedSize(menu.sizeHint())  
        menu.setWindowModality(Qt.ApplicationModal)
        
        # Store menu reference to prevent garbage collection
        self.active_context_menu = menu
        
        menu.exec_(global_cursor_pos)
        print("Menu exec called!")
        
        # Clear menu reference after it's closed
        self.active_context_menu = None
        
        # Clear selection if no label was applied (menu cancelled)
        if self.selection_active:
            print("Menu cancelled - clearing selection")
            self.clear_selection()
    
    def apply_selection_label(self, label_type):
        """Apply the selected label to the area"""
        # Clear selection active flag since selection is complete
        self.selection_active = False
        
        # Close the context menu if it's still open
        if hasattr(self, 'active_context_menu') and self.active_context_menu is not None:
            self.active_context_menu.close()
            self.active_context_menu = None
        
        if not self.current_selection_chart or not self.selection_start or not self.selection_end:
            return

        plot_widget = self.current_selection_chart
        chart_name = plot_widget.chart_name

        if chart_name not in self.selection_labels:
            self.selection_labels[chart_name] = []
        
        # Initialize dynamic selections for this chart if needed
        if chart_name not in self.dynamic_selections:
            self.dynamic_selections[chart_name] = []

        # Convert pixel coordinates to absolute time coordinates
        start_time_abs = self.selection_start.x() + self.current_time_offset
        end_time_abs = self.selection_end.x() + self.current_time_offset

        selection_data = {
            'label': label_type,
            'start': start_time_abs,
            'end': end_time_abs,
            'start_time': start_time_abs,
            'end_time': end_time_abs,
            'color': self.get_label_color(label_type)
        }

        # Calculate SpO2 info for SpO2 chart only
        spo2_info = ""
        if "SpO2" in chart_name and self.spo2_full_data:
            try:
                # Get SpO2 data
                time_data, spo2_data = self.spo2_full_data
                
                # Calculate indices
                sampling_rate = 10
                start_index = int(start_time_abs * sampling_rate)
                end_index = int(end_time_abs * sampling_rate)
                
                # Safety checks
                start_index = max(0, start_index)
                end_index = min(len(spo2_data) - 1, end_index)
                
                if start_index > end_index:
                    start_index, end_index = end_index, start_index
                
                # Get values
                start_val = spo2_data[start_index]
                end_val = spo2_data[end_index]
                diff = end_val - start_val
                
                # Prepare SpO2 text in exact format requested
                arrow = "↓" if diff < 0 else "↑" if diff > 0 else "→"
                spo2_info = f"{int(start_val)} → {int(end_val)} ({arrow} {abs(diff)})"
                
            except Exception as e:
                print(f"Error calculating SpO2 info: {e}")
                spo2_info = ""

        # Store in dynamic selections with absolute time coordinates
        dynamic_selection_data = {
            'label': label_type,
            'start_time': start_time_abs,
            'end_time': end_time_abs,
            'color': self.get_label_color(label_type),
            'spo2_info': spo2_info  
        }

        self.selection_labels[chart_name].append(selection_data)
        self.dynamic_selections[chart_name].append(dynamic_selection_data)

     
        if hasattr(plot_widget, 'selection_overlay'):
            plot_widget.selection_overlay.setVisible(False)

       
        self.render_dynamic_selections()

        print(f"Label '{label_type}' added (persistent)")

        # clear temp selection
        self.selection_start = None
        self.selection_end = None
        self.selection_start_scene = None
        self.selection_end_scene = None
        self.current_selection_chart = None
    
    def handle_overlay_click(self, event, overlay, chart_name):
        """Handle right click on overlay"""
        print(f"handle_overlay_click called - button: {event.button()}, chart: {chart_name}")
        if event.button() == Qt.RightButton:
            print("Right button detected, showing overlay menu")
            self.show_overlay_menu(event.globalPos(), overlay, chart_name)
        else:
            print(f"Left button clicked on overlay for {chart_name}")
    
    def handle_overlay_double_click(self, event, overlay, chart_name):
        """Double click = quick remove option"""
        self.show_overlay_menu(event.globalPos(), overlay, chart_name)
    
    def show_overlay_menu(self, global_pos, overlay, chart_name):
        """Show remove menu for overlay"""
        print(f"show_overlay_menu called for chart: {chart_name}")
        menu = QMenu(self)

        remove_action = QAction("Remove Selection", self)
        remove_action.triggered.connect(lambda: self.delete_overlay(overlay, chart_name))
        menu.addAction(remove_action)
        
        # Find the label index for this overlay
        label_index = self._find_label_index_for_overlay(overlay, chart_name)
        print(f"Found label_index: {label_index} for overlay")
        if label_index is not None:
            # Add Change Label option
            print("Adding Change Label option to menu")
            menu.addSeparator()
            change_action = QAction("Change Label...", self)
            change_action.triggered.connect(lambda: self.change_label(chart_name, label_index))
            menu.addAction(change_action)
        else:
            print("No label_index found, not adding Change Label option")

        print(f"Showing menu with {len(menu.actions())} actions")
        menu.exec_(global_pos)
    
    def _find_label_index_for_overlay(self, overlay, chart_name):
        """Find the label index for a given overlay"""
        overlay_id = getattr(overlay, 'selection_id', None)
        print(f"Overlay selection_id: {overlay_id}")
        if overlay_id is None:
            print("Overlay has no selection_id")
            return None
            
        if chart_name not in self.selection_labels:
            print(f"No selections found for chart: {chart_name}")
            return None
            
        print(f"Checking {len(self.selection_labels[chart_name])} selections for {chart_name}")
        for i, selection_data in enumerate(self.selection_labels[chart_name]):
            selection_id = self._get_selection_id(selection_data)
            print(f"  Selection {i}: {selection_id}")
            if selection_id == overlay_id:
                print(f"  MATCH found at index {i}")
                return i
        print("No matching selection found")
        return None
    
    def delete_overlay(self, overlay, chart_name):
        """Delete selected overlay with data sync"""
        # Check if overlay still exists before accessing it
        if overlay is None or not hasattr(overlay, 'hide'):
            print("Warning: Overlay already deleted or invalid")
            return
            
        # Get the overlay's unique identifier (stored in overlay's objectName or userData)
        overlay_id = getattr(overlay, 'selection_id', None)
        if overlay_id is None:
            # Fallback: try to find matching selection by position/label
            overlay_id = self._find_overlay_id_by_position(overlay, chart_name)
        
        if overlay_id is None:
            print("Warning: Could not identify overlay for deletion")
            return

        try:
            overlay.hide()
            overlay.deleteLater()
        except RuntimeError as e:
            print(f"Warning: Overlay already deleted - {e}")
            return

        # Remove from data using the unique identifier
        removed_count = 0
        if chart_name in self.selection_labels:
            # Find and remove matching selection by comparing start/end times or label
            self.selection_labels[chart_name] = [
                sel for sel in self.selection_labels[chart_name] 
                if self._get_selection_id(sel) != overlay_id
            ]
            removed_count = len(self.selection_labels[chart_name])
        
        if chart_name in self.dynamic_selections:
            # Find and remove matching dynamic selection
            self.dynamic_selections[chart_name] = [
                sel for sel in self.dynamic_selections[chart_name] 
                if self._get_selection_id(sel) != overlay_id
            ]

        # Re-render selections to update positions
        self.render_dynamic_selections()
        print(f"Overlay + data deleted (ID: {overlay_id})")
    
    def _find_overlay_id_by_position(self, overlay, chart_name):
        """Find selection ID by matching overlay position with stored selection data"""
        if chart_name not in self.selection_labels:
            return None
        
        overlay_geometry = overlay.geometry()
        for selection in self.selection_labels[chart_name]:
            # Create a unique identifier based on selection properties
            selection_id = self._get_selection_id(selection)
            return selection_id
        return None
    
    def _get_selection_id(self, selection):
        """Generate unique identifier for a selection"""
        if isinstance(selection, dict):
            # Use a combination of label, start, and end times to create unique ID
            start_time = selection.get('start_time', selection.get('start', 0))
            end_time = selection.get('end_time', selection.get('end', 0))
            label = selection.get('label', '')
            if hasattr(start_time, 'x'):
                start_time = start_time.x()
            if hasattr(end_time, 'x'):
                end_time = end_time.x()
            return f"{label}_{start_time}_{end_time}"
        return str(selection)
    
    def enforce_fixed_ranges(self):
        """Continuously enforce fixed X-axis ranges on all charts"""
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            if container and hasattr(container, 'plot_widget'):
                plot_widget = container.plot_widget
                if hasattr(plot_widget, 'fixed_range'):
                    # Force the X-axis range to be exactly what we want
                    try:
                        current_range = plot_widget.getViewBox().viewRange()
                        # Only print if range is not what we want 
                        if current_range[0][0] != plot_widget.fixed_range[0] or current_range[0][1] != plot_widget.fixed_range[1]:
                            print(f"🔧 FIXING ViewBox {plot_widget.chart_name}: {current_range[0]} → {plot_widget.fixed_range}")
                        plot_widget.setXRange(plot_widget.fixed_range[0], plot_widget.fixed_range[1], padding=0)
                    except:
                        pass  
    
    def get_label_color(self, label_type):
        """Get color for label type"""
        colors = {
            'OSA': 'rgba(239, 68, 68, 0.2)',    
            'CSA': 'rgba(59, 130, 246, 0.2)', 
            'MSA': 'rgba(245, 158, 11, 0.2)',  
            'HSA': 'rgba(16, 185, 129, 0.2)',   
            'SATURATION': 'rgba(239, 68, 68, 0.2)'  
        }
        return colors.get(label_type, 'rgba(107, 114, 128, 0.2)')
    
    def check_label_click(self, plot_widget, scene_pos):
        """Check if click is on an existing label and show remove option"""
        chart_name = plot_widget.chart_name
        if chart_name not in self.selection_labels or not self.selection_labels[chart_name]:
            return False
        
        widget_pos = plot_widget.mapFromScene(scene_pos)
        
        # Use overlay geometry for precise click detection
        if hasattr(plot_widget, 'selection_overlays'):
            overlays = plot_widget.selection_overlays
            for i, overlay in enumerate(overlays):
                if overlay.geometry().contains(widget_pos):
                    selection_data = self.selection_labels[chart_name][i]
                    self.show_remove_menu(plot_widget, chart_name, i, selection_data, scene_pos)
                    return True
        
        return False
    
    def show_remove_menu(self, plot_widget, chart_name, label_index, selection_data, scene_pos):
        """Show menu to remove existing label"""
        menu = QMenu(self)
        menu.setTitle(f"Label: {selection_data['label']}")
        
        # Remove action
        remove_action = QAction(f"Remove '{selection_data['label']}'", self)
        remove_action.triggered.connect(lambda: self.remove_label(chart_name, label_index))
        menu.addAction(remove_action)
        
        # Show menu at click position
        widget_pos = plot_widget.mapFromScene(scene_pos)
        global_pos = plot_widget.mapToGlobal(widget_pos)
        menu.popup(global_pos)
    
    def remove_label(self, chart_name, label_index):
        """Remove a specific label"""
        if chart_name in self.selection_labels and 0 <= label_index < len(self.selection_labels[chart_name]):
            removed_label = self.selection_labels[chart_name].pop(label_index)
            print(f"Removed label '{removed_label['label']}' from {chart_name}")
            
            # Also remove from dynamic_selections to prevent overlay issues
            if chart_name in self.dynamic_selections:
                # Find and remove the corresponding dynamic selection
                removed_id = self._get_selection_id(removed_label)
                self.dynamic_selections[chart_name] = [
                    sel for sel in self.dynamic_selections[chart_name] 
                    if self._get_selection_id(sel) != removed_id
                ]
            
            # Re-render selections to update overlays
            self.render_dynamic_selections()
            
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
        """Change an existing label by opening the event selection menu"""
        if chart_name in self.selection_labels and 0 <= label_index < len(self.selection_labels[chart_name]):
            # Store the selection data for re-application
            old_selection = self.selection_labels[chart_name][label_index]
            
            # Convert float coordinates back to QPointF objects
            from PyQt5.QtCore import QPointF
            start_point = QPointF(old_selection['start'], 0)  # y=0 for time coordinate
            end_point = QPointF(old_selection['end'], 0)
            
            # Preserve selection data BEFORE removing the old label
            self.selection_start = start_point
            self.selection_end = end_point
            
            # Remove the old label
            self.remove_label(chart_name, label_index)
            
            # Restore selection for new label
            self.current_selection = {
                "start": start_point,
                "end": end_point
            }
            
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
        # Clear selection active flag since selection is cleared
        self.selection_active = False
        
        # Close the context menu if it's still open
        if hasattr(self, 'active_context_menu') and self.active_context_menu is not None:
            self.active_context_menu.close()
            self.active_context_menu = None
        
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
        # Simply call render_dynamic_selections which handles everything
        self.render_dynamic_selections()
    
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
        from PyQt5.QtCore import QPointF
        # Convert float time values to QPointF for mapping
        start_point = QPointF(start_pos, 0)
        end_point = QPointF(end_pos, 0)
        p1 = vb.mapViewToScene(start_point)
        p2 = vb.mapViewToScene(end_point)
        w1 = plot_widget.mapFromScene(p1)
        w2 = plot_widget.mapFromScene(p2)

        # Ensure x_min and x_max are within the visible bounds of the plot_widget
        # This prevents the overlay from being drawn outside the chart area
        plot_width = plot_widget.width()
        x_min = max(0, min(w1.x(), w2.x()))
        x_max = min(plot_width, max(w1.x(), w2.x()))
        
        # Use large overlay height for persistent selections
        plot_height = plot_widget.height()
        overlay_height = max(60, plot_height)
        y_position = 0  

        # Only set geometry and make visible if the overlay has a valid width
        if x_max > x_min:
            overlay.setGeometry(int(x_min), int(y_position), int(x_max - x_min), int(overlay_height))
            overlay.setVisible(True)
        else:
            overlay.setVisible(False)  # Hide if width is invalid
    
    def render_dynamic_selections(self):
        """Render selection overlays based on current time window and offset"""
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            if hasattr(container, 'findChildren'):
                plots = container.findChildren(pg.PlotWidget)
                if plots:
                    plot_widget = plots[0]
                    chart_name = plot_widget.chart_name
                    
                    # Clear existing overlays
                    if hasattr(plot_widget, 'selection_overlays'):
                        for overlay in plot_widget.selection_overlays:
                            overlay.hide()
                            overlay.deleteLater()
                        plot_widget.selection_overlays.clear()
                    
                    # Check if this chart has dynamic selections
                    if chart_name in self.dynamic_selections:
                        for selection_data in self.dynamic_selections[chart_name]:
                            # Calculate relative position within current time window
                            start_time_abs = selection_data['start_time']
                            end_time_abs = selection_data['end_time']
                            
                            # Convert absolute time to relative time within current window
                            start_time_rel = start_time_abs - self.current_time_offset
                            end_time_rel = end_time_abs - self.current_time_offset
                            
                            # Only render if selection is within current time window
                            if (end_time_rel >= 0 and start_time_rel <= self.current_time_window):
                                # Clamp to window bounds
                                start_time_clamped = max(0, start_time_rel)
                                end_time_clamped = min(self.current_time_window, end_time_rel)
                                
                                # Create overlay
                                overlay = QLabel(plot_widget)
                                overlay.setAlignment(Qt.AlignCenter)
                                
                                # Calculate duration and format display
                                duration = end_time_abs - start_time_abs
                                start_str = self.format_timestamp(start_time_abs)
                                duration_str = self.format_duration(duration)
                                
                                # Prepare full text with SpO2 info if available
                                full_text = f"{selection_data['label']}\n{start_str}\n{duration_str}"
                                
                                # Add SpO2 info if available (only for SpO2 chart)
                                if 'spo2_info' in selection_data and selection_data['spo2_info']:
                                    full_text = f"""
{selection_data['label']}

{start_str}
{duration_str}

{selection_data['spo2_info']}
"""
                                overlay.setText(full_text)
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
                                
                                # Position overlay using direct absolute time mapping
                                vb = plot_widget.getViewBox()
                                
                                # Convert relative time → scene → widget directly
                                start_scene = vb.mapViewToScene(QPointF(start_time_rel, 0))
                                end_scene = vb.mapViewToScene(QPointF(end_time_rel, 0))
                                
                                start_widget = plot_widget.mapFromScene(start_scene)
                                end_widget = plot_widget.mapFromScene(end_scene)
                                
                                x_min = min(start_widget.x(), end_widget.x())
                                x_max = max(start_widget.x(), end_widget.x())
                                width = x_max - x_min
                                
                                if width < 30:
                                    width = 30
                                
                                # Use full plot height for overlay
                                plot_height = plot_widget.height()
                                overlay_height = max(60, plot_height)
                                y_position = 0
                                
                                overlay.setGeometry(int(x_min), y_position, int(width), int(overlay_height))
                                
                                # Store unique identifier in overlay for deletion tracking
                                overlay.selection_id = self._get_selection_id(selection_data)
                                
                                overlay.show()
                                
                                # Store overlay
                                if not hasattr(plot_widget, 'selection_overlays'):
                                    plot_widget.selection_overlays = []
                                plot_widget.selection_overlays.append(overlay)
                                
                                print(f"Rendered selection '{selection_data['label']}' on {chart_name} at {start_time_clamped:.1f}s-{end_time_clamped:.1f}s")

    def update_apnea_events_display(self):
        """Update apnea events display for current time window (placeholder method)"""
        # This method is called during refresh_charts but doesn't need to do anything
        # unless apnea events functionality is implemented
        pass
    
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
    
        
    def add_spo2_statistics_overlay(self, plot_widget, container):
        """Add SpO2 statistics overlay to the plot container"""
        if not self.spo2_statistics:
            return
        
        # Create statistics label - only show desaturation events for SpO2
        stats_text = f"""
SpO2 Statistics:
Mean: {self.spo2_statistics['mean']:.1f}%
Min: {self.spo2_statistics['min']:.1f}%
Max: {self.spo2_statistics['max']:.1f}%
Desaturations: {self.spo2_statistics['desaturation_events']}
        """.strip()
        
        stats_label = QLabel(container)
        stats_label.setText(stats_text)
        stats_label.setStyleSheet(f"""
            QLabel#signalLabel {{
                background-color: rgba(0, 0, 0, 0.8);
                color: white;
                font-size: 9px;
                font-weight: 700;
                padding: 4px;
                border-radius: 3px;
            }}
        """)
        stats_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        stats_label.setObjectName("spo2StatisticsLabel")
        
        # Position the overlay in top-right corner
        stats_label.move(container.width() - 200, 10)
        stats_label.resize(190, 90)  # Reduced height due to fewer lines
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
    
    def show_selection_warning(self):
        """Show warning popup when user tries to interact during active selection"""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Selection Required")
        msg.setText("Please select an event (OSA/CSA/MSA/HSA) or clear the selection.")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
    
    def block_if_selection_active(self):
        """Check if selection is active and show warning if needed"""
        if hasattr(self, 'selection_active') and self.selection_active:
            self.show_selection_warning()
            return True 
        return False      
    
    def resizeEvent(self, event):
        """Handle resize for watermark centering"""
        super().resizeEvent(event)
        if hasattr(self, 'watermark'):
            self.watermark.setGeometry(self.charts_widget.rect())
