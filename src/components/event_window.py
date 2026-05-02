"""
Event Window - Sleep Sense Application
Exact replica of the event window interface shown in the reference image
"""

from PyQt5.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QSplitter, QGroupBox, QLineEdit, QCheckBox,
    QTableWidget, QTableWidgetItem, QPushButton, QHeaderView,
    QToolBar, QSizePolicy, QTreeWidget, QTreeWidgetItem, QComboBox, QMessageBox
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont
import pyqtgraph as pg
import numpy as np
from src.utils.database_manager import DatabaseManager
from datetime import datetime


class EventWindow(QDialog):
    """Event Window matching the reference image design exactly"""
    
    def __init__(self, parent=None, patient_data=None):
        super().__init__(parent)
        self.setModal(False)
        self.setWindowTitle("Event Window")
        self.setFixedSize(1200, 800)
        self.monitor_chart = None
        self.patient_data = patient_data
        self.db_manager = DatabaseManager()
        self.init_ui()
        self.connect_to_main_data()
        self.load_patient_events()
        self.setup_real_time_updates()
        
    def init_ui(self):
        # Apply medical theme matching the image
        self.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                color: #2c3e50;
            }
        """)
        
        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)
        
        # Create main content area with splitter
        content_splitter = QSplitter(Qt.Horizontal)
        
        # Left side - Event tree
        left_widget = self.create_event_tree_section()
        content_splitter.addWidget(left_widget)
        
        # Right side container
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)
        
        # Event list section (top right)
        event_list_widget = self.create_event_list_section()
        right_layout.addWidget(event_list_widget)
        
        # Flow graph section (bottom right)
        flow_graph_widget = self.create_flow_graph_section()
        right_layout.addWidget(flow_graph_widget)
        
        content_splitter.addWidget(right_widget)
        content_splitter.setSizes([300, 900])
        
        main_layout.addWidget(content_splitter)
        
    def create_event_tree_section(self):
        """Create the Event tree section (left side)"""
        group = QGroupBox("Event tree")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        layout = QVBoxLayout(group)
        layout.setSpacing(5)
        
        # Event tree widget
        self.event_tree = QTreeWidget()
        self.event_tree.setHeaderLabels(["Events"])
        self.event_tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #d1e3f4;
                border-radius: 6px;
                background-color: #ffffff;
                selection-background-color: #e3f2fd;
                selection-color: #1565c0;
                font-size: 12px;
            }
            QTreeWidget::item {
                padding: 5px;
                border-bottom: 1px solid #e8f4f8;
            }
            QTreeWidget::item:selected {
                background-color: #e3f2fd;
                color: #1565c0;
            }
            QTreeWidget::item:hover {
                background-color: #f5f9fc;
            }
            QHeaderView::section {
                background-color: #f8fbfd;
                color: #1e3a5f;
                font-weight: 600;
                font-size: 12px;
                padding: 8px 5px;
                border: 1px solid #d1e3f4;
                border-bottom: 2px solid #3498db;
            }
        """)
        
        # Set tree properties
        self.event_tree.setAlternatingRowColors(True)
        self.event_tree.setSortingEnabled(False)
        self.event_tree.setAnimated(True)
        
        layout.addWidget(self.event_tree)
        
        return group
        
    def create_event_list_section(self):
        """Create the Event list section (right side)"""
        group = QGroupBox("Event list")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        layout = QVBoxLayout(group)
        layout.setSpacing(5)
        
        # Add time window dropdown above the table
        time_window_layout = QHBoxLayout()
        
        time_window_label = QLabel("Time Window:")
        time_window_label.setStyleSheet("""
            QLabel {
                font-weight: 600;
                color: #34495e;
                font-size: 12px;
                padding: 5px;
            }
        """)
        
        self.time_window_combo = QComboBox()
        self.time_window_options = ["10 sec", "30 sec", "60 sec", "120 sec", "300 sec"]
        self.time_window_combo.addItems(self.time_window_options)
        self.time_window_combo.setCurrentText("60 sec")  # Default to 60 seconds
        self.time_window_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #d1e3f4;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 12px;
                background-color: #ffffff;
                min-width: 100px;
            }
            QComboBox:focus {
                border-color: #3498db;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTAiIGhlaWdodD0iNiIgdmlld0JveD0iMCAwIDEwIDYiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PHBhdGggZD0iTTEgMUw1TDVMOSAxIiBzdHJva2U9IiMzNDk4ZGIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPjwvc3ZnPg==);
            }
        """)
        
        # Connect time window change
        self.time_window_combo.currentTextChanged.connect(self.on_time_window_changed)
        
        time_window_layout.addWidget(time_window_label)
        time_window_layout.addWidget(self.time_window_combo)
        time_window_layout.addStretch()
        
        layout.addLayout(time_window_layout)
        
        # Event list table
        self.event_list_table = QTableWidget()
        self.event_list_table.setColumnCount(5)
        self.event_list_table.setHorizontalHeaderLabels([
            "Event", "Start time", "Stop time", "Duration", "Parameter"
        ])
        
        # Professional medical table styling
        self.event_list_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #d1e3f4;
                border-radius: 6px;
                background-color: #ffffff;
                gridline-color: #e8f4f8;
                selection-background-color: #e3f2fd;
                selection-color: #1565c0;
            }
            QTableWidget::item {
                padding: 6px;
                border-bottom: 1px solid #e8f4f8;
                font-size: 12px;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: #1565c0;
            }
            QTableWidget::item:hover {
                background-color: #f5f9fc;
            }
            QHeaderView::section {
                background-color: #f8fbfd;
                color: #1e3a5f;
                font-weight: 600;
                font-size: 12px;
                padding: 8px 5px;
                border: 1px solid #d1e3f4;
                border-right: none;
                border-bottom: 2px solid #3498db;
            }
            QHeaderView::section:last {
                border-right: 1px solid #d1e3f4;
            }
        """)
        
        # Set table properties
        header = self.event_list_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.event_list_table.setAlternatingRowColors(True)
        self.event_list_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.event_list_table.setShowGrid(True)
        self.event_list_table.verticalHeader().setVisible(False)
        self.event_list_table.setSortingEnabled(True)
        
        layout.addWidget(self.event_list_table)
        
        return group
        
    def create_flow_graph_section(self):
        """Create the Flow graph section (bottom right)"""
        # Store reference to group for dynamic title updates
        self.graph_group = QGroupBox("Airflow (Zoom 0.5x)")
        self.graph_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        
        layout = QVBoxLayout(self.graph_group)
        layout.setSpacing(5)
        
        # Top controls row
        controls_layout = QHBoxLayout()
        
        # Dropdown for graph selection (all 9 available graphs)
        self.event_type_combo = QComboBox()
        self.graph_types = [
            "Body Position",
            "Airflow", 
            "Snoring",
            "Thorex",
            "Abdomen",
            "SpO2",
            "Pulse",
            "Body Movement",
            "PR/HR"
        ]
        self.event_type_combo.addItems(self.graph_types)
        self.event_type_combo.setCurrentText("Airflow")  
        self.event_type_combo.setStyleSheet("""
            QComboBox {
                border: 2px solid #d1e3f4;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 12px;
                background-color: #ffffff;
                min-width: 120px;
            }
            QComboBox:focus {
                border-color: #3498db;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0;
                height: 0;
            }
        """)
        
        # Dynamic time label that updates based on dropdown selection
        self.time_label = QLabel("60 sec.")
        self.time_label.setStyleSheet("QLabel { font-weight: 600; color: #34495e; font-size: 12px; padding: 5px; }")
        
        controls_layout.addWidget(self.event_type_combo)
        controls_layout.addStretch()
        controls_layout.addWidget(self.time_label)
        
        layout.addLayout(controls_layout)
        
        # Create plot widget
        self.flow_plot = pg.PlotWidget()
        self.flow_plot.setMenuEnabled(False)
        self.flow_plot.setMouseEnabled(False, False)
        self.flow_plot.showGrid(x=True, y=True, alpha=0.3)
        self.flow_plot.setBackground('#ffffff')
        self.flow_plot.setMinimumHeight(200)
        
        # Style the plot
        self.flow_plot.getAxis('left').setPen('#34495e')
        self.flow_plot.getAxis('bottom').setPen('#34495e')
        self.flow_plot.getAxis('left').setStyle(tickFont=QFont('Segoe UI', 10))
        self.flow_plot.getAxis('bottom').setStyle(tickFont=QFont('Segoe UI', 10))
        
        layout.addWidget(self.flow_plot)
        
        return self.graph_group
        
    def connect_to_main_data(self):
        """Connect to the main dashboard's monitor chart for real-time data"""
        if self.parent():
            # Get the main dashboard instance
            dashboard = self.parent()
            if hasattr(dashboard, 'monitor_chart'):
                self.monitor_chart = dashboard.monitor_chart
                print("Event window connected to main monitor chart")
            else:

                
                print("Monitor chart not found in parent")
                
    def setup_real_time_updates(self):
        """Setup real-time updates for event window"""
        if self.monitor_chart:
            # Connect to time position updates
            if hasattr(self.monitor_chart, 'time_position_updated'):
                self.monitor_chart.time_position_updated.connect(self.update_time_display)
                
    def update_time_display(self):
        """Update event window display based on current time position"""
        if self.monitor_chart:
            # Update flow graph with current data
            self.update_flow_graph_real_time()
            # Update event list with current events
            self.update_event_list_real_time()
            
    def update_flow_graph_real_time(self):
        """Update graph with real-time data from main chart for selected graph type"""
        if not self.monitor_chart:
            return
            
        # Get current time window and offset
        time_window = getattr(self.monitor_chart, 'current_time_window', 60)
        time_offset = getattr(self.monitor_chart, 'current_time_offset', 0)
        
        # Get selected graph type
        selected_graph = self.event_type_combo.currentText()
        
        # Update graph title
        self.graph_group.setTitle(f"{selected_graph} (Zoom 0.5x)")
        
        # Generate time points for current window
        time_points = np.linspace(0, time_window, int(time_window * 10))
        
        # Get data for selected graph type
        graph_data = self.get_graph_data(selected_graph, time_points, time_window, time_offset)
        
        # Clear and update plot
        self.flow_plot.clear()
        
        # Get color for selected graph
        graph_color = self.get_graph_color(selected_graph)
        
        # Plot the signal
        self.flow_plot.plot(time_points, graph_data, pen=pg.mkPen(graph_color, width=2), name=selected_graph)
        
        # Add event markers based on current time window and graph type
        self.add_graph_event_markers(time_points, graph_data, time_offset, selected_graph)
        
        # Update axis labels based on graph type
        y_label, y_units = self.get_graph_axis_labels(selected_graph)
        self.flow_plot.setLabel('left', y_label, units=y_units)
        self.flow_plot.setLabel('bottom', 'Time', units='s')
        
        # Format time axis to show actual time
        self.format_time_axis(time_offset)
        
    def generate_realistic_flow_data(self, time_points):
        """Generate realistic flow data matching breathing patterns"""
        # Base breathing pattern (0.2 Hz = 12 breaths per minute)
        base_flow = 0.5 * np.sin(2 * np.pi * 0.2 * time_points)
        
        # Add some variability and noise
        noise = np.random.normal(0, 0.05, len(time_points))
        
        # Add occasional flow limitations
        flow_limitations = np.zeros_like(time_points)
        for i in range(len(time_points)):
            if np.random.random() < 0.05:  # 5% chance of flow limitation
                start_idx = max(0, i - 5)
                end_idx = min(len(time_points), i + 5)
                flow_limitations[start_idx:end_idx] = -0.2
        
        # Combine all components
        flow_data = base_flow + noise + flow_limitations + 0.5
        
        return flow_data
        
    def get_graph_data(self, graph_type, time_points, time_window, time_offset):
        """Get real-time data for the selected graph type"""
        # Graph parameters from main dashboard
        graph_params = {
            "Body Position": {"freq": 0.5, "amp": 10, "offset": 50, "color": "#3b82f6"},
            "Airflow": {"freq": 0.3, "amp": 15, "offset": 50, "color": "#8b5cf6"},
            "Snoring": {"freq": 1.0, "amp": 8, "offset": 50, "color": "#ef4444"},
            "Thorex": {"freq": 0.2, "amp": 5, "offset": 50, "color": "#f59e0b"},
            "Abdomen": {"freq": 0.1, "amp": 2, "offset": 90, "color": "#10b981"},
            "SpO2": {"freq": 1.5, "amp": 12, "offset": 50, "color": "#06b6d4"},
            "Pulse": {"freq": 0.0, "amp": 0, "offset": 30, "color": "#f97316"},
            "Body Movement": {"freq": 0.1, "amp": 5, "offset": 20, "color": "#8b5cf6"},
            "PR/HR": {"freq": 0.1, "amp": 5, "offset": 20, "color": "#5c61f6"}
        }
        
        params = graph_params.get(graph_type, graph_params["Airflow"])
        
        # Special handling for SpO2 - try to get real data
        if graph_type == "SpO2" and self.monitor_chart:
            try:
                x_data, y_data = self.monitor_chart.get_spo2_data_for_window(time_window, time_offset)
                if len(x_data) > 0 and len(y_data) > 0:
                    return y_data
            except:
                pass  # Fall back to simulated data
        
        # Special handling for Pulse - try to get real data
        if graph_type == "Pulse" and self.monitor_chart:
            try:
                if hasattr(self.monitor_chart, 'get_pulse_data_for_window'):
                    x_data, y_data = self.monitor_chart.get_pulse_data_for_window(time_window, time_offset)
                    if len(x_data) > 0 and len(y_data) > 0:
                        return y_data
            except:
                pass  # Fall back to simulated data
        
        # Generate simulated data with realistic characteristics
        if graph_type == "Body Position":
            # Discrete positions (0=supine, 1=left, 2=right, 3=prone)
            np.random.seed(int(time_offset) % 1000)
            positions = np.random.choice([0, 1, 2, 3], len(time_points))
            # Add smooth transitions
            smoothed = np.convolve(positions, np.ones(5)/5, mode='same')
            return smoothed * params["amp"] + params["offset"]
            
        elif graph_type == "Airflow":
            # Breathing pattern with occasional flow limitations
            base_flow = params["amp"] * np.sin(2 * np.pi * params["freq"] * time_points)
            noise = np.random.normal(0, params["amp"] * 0.05, len(time_points))
            # Add flow limitations
            flow_limitations = np.zeros_like(time_points)
            for i in range(len(time_points)):
                if np.random.random() < 0.05:  # 5% chance
                    start_idx = max(0, i - 5)
                    end_idx = min(len(time_points), i + 5)
                    flow_limitations[start_idx:end_idx] = -params["amp"] * 0.3
            return base_flow + noise + flow_limitations + params["offset"]
            
        elif graph_type == "Snoring":
            # Intermittent snoring events
            base_data = np.ones_like(time_points) * params["offset"]
            np.random.seed(int(time_offset) % 1000)
            for i in range(len(time_points)):
                if np.random.random() < 0.1:  # 10% chance of snoring
                    start_idx = max(0, i - 3)
                    end_idx = min(len(time_points), i + 3)
                    base_data[start_idx:end_idx] = params["offset"] + params["amp"] * np.random.random()
            return base_data
            
        elif graph_type == "Thorex":
            # Thoracic effort pattern
            return params["amp"] * np.sin(2 * np.pi * params["freq"] * time_points) + params["offset"]
            
        elif graph_type == "Abdomen":
            # Abdominal effort pattern
            return params["amp"] * np.sin(2 * np.pi * params["freq"] * time_points) + params["offset"]
            
        elif graph_type == "SpO2":
            # SpO2 with desaturation events
            base_spo2 = params["amp"] * np.sin(2 * np.pi * params["freq"] * time_points) + params["offset"]
            np.random.seed(int(time_offset) % 1000)
            # Add desaturation events
            for i in range(len(time_points)):
                if np.random.random() < 0.03:  
                    start_idx = max(0, i - 10)
                    end_idx = min(len(time_points), i + 10)
                    base_spo2[start_idx:end_idx] -= np.random.uniform(5, 15)  # 5-15% drop
            return np.clip(base_spo2, 70, 100)  # Keep within physiological range
            
        elif graph_type == "Pulse":
            # Heart rate with variability
            base_hr = 60 + params["offset"] 
            hr_variability = 5 * np.sin(2 * np.pi * 0.1 * time_points)  
            noise = np.random.normal(0, 2, len(time_points))
            return base_hr + hr_variability + noise
            
        elif graph_type == "Body Movement":
            # Movement detection
            base_data = np.ones_like(time_points) * params["offset"]
            np.random.seed(int(time_offset) % 1000)
            for i in range(len(time_points)):
                if np.random.random() < 0.08:  # 8% chance of movement
                    start_idx = max(0, i - 2)
                    end_idx = min(len(time_points), i + 2)
                    base_data[start_idx:end_idx] = params["offset"] + params["amp"] * np.random.random()
            return base_data
            
        elif graph_type == "PR/HR":
            # Pulse rate / Heart rate
            base_pr = params["offset"]
            pr_variability = 3 * np.sin(2 * np.pi * 0.1 * time_points)
            noise = np.random.normal(0, 1, len(time_points))
            return base_pr + pr_variability + noise
            
        else:
            # Default sinusoidal pattern
            return params["amp"] * np.sin(2 * np.pi * params["freq"] * time_points) + params["offset"]
    
    def get_graph_color(self, graph_type):
        """Get the color for the selected graph type"""
        color_map = {
            "Body Position": "#3b82f6",
            "Airflow": "#8b5cf6",
            "Snoring": "#ef4444",
            "Thorex": "#f59e0b",
            "Abdomen": "#10b981",
            "SpO2": "#06b6d4",
            "Pulse": "#f97316",
            "Body Movement": "#8b5cf6",
            "PR/HR": "#5c61f6"
        }
        return color_map.get(graph_type, "#3498db")
    
    def get_graph_axis_labels(self, graph_type):
        """Get appropriate axis labels for the selected graph type"""
        label_map = {
            "Body Position": ("Position", "state"),
            "Airflow": ("Flow", "L/s"),
            "Snoring": ("Snoring", "AU"),
            "Thorex": ("Effort", "AU"),
            "Abdomen": ("Effort", "AU"),
            "SpO2": ("SpO2", "%"),
            "Pulse": ("Pulse", "bpm"),
            "Body Movement": ("Movement", "AU"),
            "PR/HR": ("Heart Rate", "bpm")
        }
        return label_map.get(graph_type, ("Signal", "AU"))
        
    def add_graph_event_markers(self, time_points, data, time_offset, graph_type):
        """Add event markers to the graph based on graph type"""
        event_segments = []
        
        # Different event detection for different graph types
        if graph_type == "Airflow":
            # Detect flow limitations (low flow periods)
            threshold = 35  # Flow threshold for events
            event_mask = data < threshold
            
        elif graph_type == "SpO2":
            # Detect desaturation events
            threshold = 85  # SpO2 threshold for events
            event_mask = data < threshold
            
        elif graph_type == "Snoring":
            # Detect snoring events (high amplitude)
            threshold = 55  # Snoring threshold for events
            event_mask = data > threshold
            
        elif graph_type == "Body Movement":
            # Detect movement events
            threshold = 22  # Movement threshold for events
            event_mask = data > threshold
            
        elif graph_type == "Pulse" or graph_type == "PR/HR":
            # Detect bradycardia/tachycardia events
            threshold_low = 50
            threshold_high = 100
            event_mask = (data < threshold_low) | (data > threshold_high)
            
        else:
            # Default event detection
            threshold = np.mean(data) - np.std(data)
            event_mask = data < threshold
        
        if np.any(event_mask):
            # Find continuous segments of events
            in_event = False
            start_idx = 0
            
            for i, is_event in enumerate(event_mask):
                if is_event and not in_event:
                    in_event = True
                    start_idx = i
                elif not is_event and in_event:
                    in_event = False
                    end_idx = i
                    if end_idx - start_idx > 2:  # Minimum duration
                        event_segments.append((start_idx, end_idx))
            
            # Add last event if we're still in it
            if in_event and len(time_points) - start_idx > 2:
                event_segments.append((start_idx, len(time_points)))
            
            # Shade event regions
            for start_idx, end_idx in event_segments:
                event_x = time_points[start_idx:end_idx]
                event_y = data[start_idx:end_idx]
                self.flow_plot.plot(event_x, event_y, pen=pg.mkPen('#27ae60', width=2), 
                                  fillLevel=0, brush='#27ae6040')
                
    def format_time_axis(self, time_offset):
        """Format time axis to show actual time from data"""
        # Calculate actual time
        total_seconds = int(time_offset)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        # Create time labels
        ax = self.flow_plot.getAxis('bottom')
        time_window = getattr(self.monitor_chart, 'current_time_window', 60)
        
        # Generate time labels for the current window
        labels = []
        for i in range(0, int(time_window) + 1, max(1, int(time_window) // 5)):
            current_time = time_offset + i
            current_hours = int(current_time // 3600)
            current_minutes = int((current_time % 3600) // 60)
            current_seconds = int(current_time % 60)
            labels.append((i, f"{current_hours:02d}:{current_minutes:02d}:{current_seconds:02d}"))
        
        ax.setTicks([labels])
        
    def update_event_list_real_time(self):
        """Update event list with real-time events"""
        if not self.monitor_chart:
            return
            
        # Get current time window
        time_window = getattr(self.monitor_chart, 'current_time_window', 60)
        time_offset = getattr(self.monitor_chart, 'current_time_offset', 0)
        
        # Generate events based on current time window
        events = self.detect_current_events(time_window, time_offset)
        
        # Update event list table
        self.event_list_table.setRowCount(len(events))
        for row, (event, start, stop, duration, param) in enumerate(events):
            self.event_list_table.setItem(row, 0, QTableWidgetItem(event))
            self.event_list_table.setItem(row, 1, QTableWidgetItem(start))
            self.event_list_table.setItem(row, 2, QTableWidgetItem(stop))
            self.event_list_table.setItem(row, 3, QTableWidgetItem(duration))
            self.event_list_table.setItem(row, 4, QTableWidgetItem(param))
            
    def detect_current_events(self, time_window, time_offset):
        """Detect events in current time window based on selected graph type"""
        events = []
        
        # Get selected graph type
        selected_graph = self.event_type_combo.currentText()
        
        # Add start time event
        start_time = self.format_time(time_offset)
        events.append(("Start of evaluation", start_time, start_time, "0:00:00", ""))
        
        # Simulate detecting various events based on time window and graph type
        current_time = time_offset
        
        # Add random events within the time window
        np.random.seed(int(time_offset) % 1000)  # Seed for consistency
        
        # Graph-specific event types
        graph_events = {
            "Body Position": [
                ("Position change", "Position"),
                ("Supine position", "Position"),
                ("Left position", "Position"),
                ("Right position", "Position"),
                ("Prone position", "Position")
            ],
            "Airflow": [
                ("Flow limitation", "Flow"),
                ("Apnea", "Flow"),
                ("Hypopnea", "Flow"),
                ("Normal breathing", "Flow"),
                ("Obstruction", "Flow")
            ],
            "Snoring": [
                ("Snoring event", "Flow"),
                ("Heavy snoring", "Flow"),
                ("Light snoring", "Flow"),
                ("No snoring", "Flow")
            ],
            "Thorex": [
                ("Thoracic effort", "Effort"),
                ("Reduced effort", "Effort"),
                ("Normal effort", "Effort"),
                ("Increased effort", "Effort")
            ],
            "Abdomen": [
                ("Abdominal effort", "Effort"),
                ("Reduced effort", "Effort"),
                ("Normal effort", "Effort"),
                ("Paradoxical breathing", "Effort")
            ],
            "SpO2": [
                ("Desaturation", "SpO2"),
                ("Baseline Saturation", "SpO2"),
                ("Oxygen drop", "SpO2"),
                ("Recovery", "SpO2"),
                ("Hypoxemia", "SpO2")
            ],
            "Pulse": [
                ("Bradycardia", "Pulse"),
                ("Tachycardia", "Pulse"),
                ("Normal pulse", "Pulse"),
                ("Arrhythmia", "Pulse"),
                ("Signal too small", "Pulse"),
                ("Invalid data pulse", "Pulse")
            ],
            "Body Movement": [
                ("Body movement", "Movement"),
                ("No movement", "Movement"),
                ("Restlessness", "Movement"),
                ("Periodic movement", "Movement")
            ],
            "PR/HR": [
                ("Bradycardia", "PR/HR"),
                ("Tachycardia", "PR/HR"),
                ("Normal HR", "PR/HR"),
                ("Arrhythmia", "PR/HR"),
                ("HR variability", "PR/HR")
            ]
        }
        
        event_types = graph_events.get(selected_graph, graph_events["Airflow"])
        
        # Generate 1-3 events
        num_events = np.random.randint(1, min(4, len(event_types)))
        for i in range(num_events):
            event_time = current_time + np.random.uniform(0, time_window)
            event_start = self.format_time(event_time)
            event_end = self.format_time(event_time + np.random.uniform(0, 10))
            duration = self.format_duration(np.random.uniform(0, 10))
            
            event_type, param = event_types[i % len(event_types)]
            events.append((event_type, event_start, event_end, duration, param))
        
        return events
        
    def format_time(self, seconds):
        """Format time in seconds to HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        
    def format_duration(self, seconds):
        """Format duration to H:MM:SS"""
        if seconds < 60:
            return f"0:00:{int(seconds):02d}"
        else:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"0:{minutes:02d}:{secs:02d}"
        
    def load_patient_events(self):
        """Load events from database for the current patient"""
        # Event tree data
        self.populate_event_tree()
        
        # Load patient-specific events from database
        if self.patient_data:
            patient_id = self.patient_data.get('id')
            if patient_id:
                self.db_events = self.db_manager.get_events_by_patient(patient_id)
                print(f"Loaded {len(self.db_events)} events for patient {patient_id}")
            else:
                self.db_events = []
                print("No patient ID found, using sample data")
        else:
            self.db_events = []
            print("No patient data provided, using sample data")
        
        # Initialize with real-time data
        self.update_time_display()
        
        # Connect tree selection to event list
        self.event_tree.itemClicked.connect(self.on_tree_item_clicked)
        
        # Connect dropdown to update graph
        self.event_type_combo.currentTextChanged.connect(self.on_event_type_changed)
        
    def populate_event_tree(self):
        """Populate the event tree with hierarchical structure"""
        # Root items
        all_events = QTreeWidgetItem(["All events"])
        general = QTreeWidgetItem(["General"])
        osa = QTreeWidgetItem(["OSA"])
        oximetry = QTreeWidgetItem(["Oximetry"])
        event_group1 = QTreeWidgetItem(["Event group (new)"])
        event_group2 = QTreeWidgetItem(["Event group (new)"])
        
        # Add to tree
        self.event_tree.addTopLevelItem(all_events)
        self.event_tree.addTopLevelItem(general)
        self.event_tree.addTopLevelItem(osa)
        self.event_tree.addTopLevelItem(oximetry)
        self.event_tree.addTopLevelItem(event_group1)
        self.event_tree.addTopLevelItem(event_group2)
        
        # Expand all items by default
        all_events.setExpanded(True)
        general.setExpanded(True)
        osa.setExpanded(True)
        oximetry.setExpanded(True)
        event_group1.setExpanded(True)
        event_group2.setExpanded(True)
        
    def on_event_type_changed(self, event_type):
        """Handle event type dropdown change"""
        print(f"Event type changed to: {event_type}")
        # Update the flow graph based on selected event type
        self.update_flow_graph_real_time()
        
    def on_time_window_changed(self, time_window_text):
        """Handle time window dropdown change"""
        print(f"Time window changed to: {time_window_text}")
        
        # Convert time window text to seconds
        time_window_map = {
            "10 sec": 10,
            "30 sec": 30,
            "60 sec": 60,
            "120 sec": 120,
            "300 sec": 300
        }
        
        new_time_window = time_window_map.get(time_window_text, 60)
        
        # Update monitor chart time window if available
        if self.monitor_chart:
            self.monitor_chart.current_time_window = new_time_window
            self.monitor_chart.refresh_charts()
        
        # Update time label in graph section
        self.time_label.setText(time_window_text)
        
        # Update event window display
        self.update_time_display()
        
    def on_tree_item_clicked(self, item, column):
        """Handle tree item selection"""
        selected_item = item.text(column)
        print(f"Selected: {selected_item}")
        
        # Filter event list based on selected tree item
        if self.monitor_chart:
            self.filter_events_by_type(selected_item)
            
    def filter_events_by_type(self, event_type):
        """Filter events in the list based on selected tree item"""
        # Use database events first, fallback to simulated events
        if hasattr(self, 'db_events') and self.db_events:
            all_events = []
            for event in self.db_events:
                # Convert database event to table format
                all_events.append([
                    event.get('event_name', 'Unknown'),
                    event.get('start_time', ''),
                    event.get('end_time', ''),
                    event.get('duration', ''),
                    event.get('parameter', '')
                ])
        else:
            # Fallback to simulated events
            time_window = getattr(self.monitor_chart, 'current_time_window', 60)
            time_offset = getattr(self.monitor_chart, 'current_time_offset', 0)
            all_events = self.detect_current_events(time_window, time_offset)
        
        # Filter based on selection
        filtered_events = []
        if event_type == "All events":
            filtered_events = all_events
        elif event_type == "General":
            filtered_events = [e for e in all_events if e[0] in ["Start of evaluation"]]
        elif event_type == "OSA":
            filtered_events = [e for e in all_events if e[0] in ["Flow limitation", "Snoring"]]
        elif event_type == "Oximetry":
            filtered_events = [e for e in all_events if e[4] in ["SpO2", "Pulse"]]
        else:
            # For event groups, show a subset
            filtered_events = all_events[:3]  # Show first 3 events
            
        # Update event list table
        self.event_list_table.setRowCount(len(filtered_events))
        for row, (event, start, stop, duration, param) in enumerate(filtered_events):
            self.event_list_table.setItem(row, 0, QTableWidgetItem(event))
            self.event_list_table.setItem(row, 1, QTableWidgetItem(start))
            self.event_list_table.setItem(row, 2, QTableWidgetItem(stop))
            self.event_list_table.setItem(row, 3, QTableWidgetItem(duration))
            self.event_list_table.setItem(row, 4, QTableWidgetItem(param))
    
    def detect_events_from_device_data(self, device_data):
        """Detect events from real device data"""
        detected_events = []
        
        if not device_data or not self.patient_data:
            return detected_events
        
        patient_id = self.patient_data.get('id')
        current_time = datetime.now().strftime('%H:%M:%S')
        recording_date = datetime.now().strftime('%Y-%m-%d')
        
        # Example event detection algorithms for real device data
        try:
            # Apnea detection from airflow data
            if 'airflow' in device_data:
                airflow_data = device_data['airflow']
                if self.detect_apnea_event(airflow_data):
                    event_data = {
                        'patient_id': patient_id,
                        'event_type': 'OSA',
                        'event_name': 'Apnea Event',
                        'start_time': current_time,
                        'end_time': current_time,
                        'duration': '10s',
                        'parameter': 'Airflow',
                        'recording_date': recording_date
                    }
                    detected_events.append(event_data)
                    # Save to database
                    self.db_manager.save_event(event_data)
            
            # SpO2 desaturation detection
            if 'spo2' in device_data:
                spo2_data = device_data['spo2']
                if self.detect_desaturation_event(spo2_data):
                    event_data = {
                        'patient_id': patient_id,
                        'event_type': 'Oximetry',
                        'event_name': 'SpO2 Desaturation',
                        'start_time': current_time,
                        'end_time': current_time,
                        'duration': '15s',
                        'parameter': 'SpO2',
                        'recording_date': recording_date
                    }
                    detected_events.append(event_data)
                    # Save to database
                    self.db_manager.save_event(event_data)
            
            # Pulse rate anomaly detection
            if 'pulse' in device_data:
                pulse_data = device_data['pulse']
                if self.detect_pulse_anomaly(pulse_data):
                    event_data = {
                        'patient_id': patient_id,
                        'event_type': 'Oximetry',
                        'event_name': 'Pulse Anomaly',
                        'start_time': current_time,
                        'end_time': current_time,
                        'duration': '8s',
                        'parameter': 'Pulse',
                        'recording_date': recording_date
                    }
                    detected_events.append(event_data)
                    # Save to database
                    self.db_manager.save_event(event_data)
            
            # Refresh events list if new events detected
            if detected_events:
                self.load_patient_events()
                print(f"Detected and saved {len(detected_events)} new events from device data")
                
        except Exception as e:
            print(f"Error detecting events from device data: {e}")
        
        return detected_events
    
    def detect_apnea_event(self, airflow_data):
        """Simple apnea detection from airflow data"""
        if not airflow_data or len(airflow_data) < 10:
            return False
        
        # Check for prolonged low airflow (apnea)
        threshold = 0.2  # 20% of normal airflow
        recent_data = airflow_data[-10:]  # Last 10 data points
        
        low_airflow_count = sum(1 for value in recent_data if value < threshold)
        
        # Apnea if 80% of recent readings are below threshold
        return low_airflow_count >= 8
    
    def detect_desaturation_event(self, spo2_data):
        """Detect SpO2 desaturation events"""
        if not spo2_data or len(spo2_data) < 5:
            return False
        
        # Check for SpO2 drop below 90%
        recent_data = spo2_data[-5:]
        avg_spo2 = sum(recent_data) / len(recent_data)
        
        return avg_spo2 < 90.0
    
    def detect_pulse_anomaly(self, pulse_data):
        """Detect pulse rate anomalies"""
        if not pulse_data or len(pulse_data) < 5:
            return False
        
        recent_data = pulse_data[-5:]
        avg_pulse = sum(recent_data) / len(recent_data)
        
        # Detect bradycardia (<50) or tachycardia (>120)
        return avg_pulse < 50 or avg_pulse > 120
    
    def connect_to_device_stream(self):
        """Interface for connecting to real device data stream"""
        # This method would connect to actual device hardware
        # For now, it's a placeholder for future implementation
        print("Device stream connection - ready for real device integration")
        
        # Example of how it would work:
        # device_stream = DeviceDataStream(port="/dev/ttyUSB0")
        # device_stream.data_received.connect(self.detect_events_from_device_data)
        # device_stream.start()
        
        return True
            
    def showEvent(self, event):
        """Override show event to update data when window is shown"""
        super().showEvent(event)
        # Update with current data when window is shown
        self.update_time_display()
