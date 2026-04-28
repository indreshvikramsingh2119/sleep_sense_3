"""
Analysis Parameters Dialog - Comprehensive Sleep Analysis Configuration
Creates dialog for configuring apnea detection and analysis parameters
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QPushButton, QSlider, QSpinBox, QDoubleSpinBox, QGroupBox,
    QCheckBox, QComboBox, QFrame, QScrollArea, QWidget
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPalette

class AnalysisParametersDialog(QDialog):
    """Analysis Parameters Configuration Dialog"""
    
    # Signal to emit when parameters are applied
    parameters_changed = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Analysis Parameters")
        self.setModal(True)
        self.setFixedSize(800, 600)
        
        # Initialize parameter values
        self.parameters = {
            'apnea_detection': True,
            'apnea_type': 'All Types',
            'central_apnea_threshold': 3.0,
            'obstructive_apnea_threshold': 10.0,
            'hypopnea_threshold': 8.0,
            'desaturation_threshold': 3.0,
            'flow_limitation': False,
            'rera_detection': False,
            'event_duration_min': 10.0,
            'baseline_calculation': 'moving_average',
            'smoothing_factor': 0.8,
            'analysis_algorithm': 'auto',
            'real_time_processing': True,
            'auto_update': True
        }
        
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # Create tab buttons at the top
        tab_buttons_layout = QHBoxLayout()
        tab_buttons_layout.setSpacing(5)
        
        # Tab buttons
        self.apnea_btn = QPushButton("Apnea")
        self.apnea_btn.setCheckable(True)
        self.apnea_btn.setChecked(True)
        self.apnea_btn.clicked.connect(lambda: self.show_tab('apnea'))
        
        self.hypoapnea_btn = QPushButton("Hypoapnea")
        self.hypoapnea_btn.setCheckable(True)
        self.hypoapnea_btn.clicked.connect(lambda: self.show_tab('hypoapnea'))
        
        self.snoring_btn = QPushButton("Snoring")
        self.snoring_btn.setCheckable(True)
        self.snoring_btn.clicked.connect(lambda: self.show_tab('snoring'))
        
        self.desaturation_btn = QPushButton("Desaturation")
        self.desaturation_btn.setCheckable(True)
        self.desaturation_btn.clicked.connect(lambda: self.show_tab('desaturation'))
        
        self.csr_btn = QPushButton("CSR")
        self.csr_btn.setCheckable(True)
        self.csr_btn.clicked.connect(lambda: self.show_tab('csr'))
        
        # Style tab buttons
        tab_button_style = """
            QPushButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #e2e8f0, stop: 1 #cbd5e1
                );
                color: #1e293b;
                border: 1px solid #94a3b8;
                border-radius: 6px;
                padding: 12px 20px;
                font-weight: 600;
                font-size: 14px;
                min-width: 120px;
                min-height: 40px;
            }
            QPushButton:checked {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #3b82f6, stop: 1 #2563eb
                );
                color: white;
                border: 1px solid #2563eb;
            }
            QPushButton:hover:!checked {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #cbd5e1, stop: 1 #94a3b8
                );
            }
        """
        
        self.apnea_btn.setStyleSheet(tab_button_style)
        self.hypoapnea_btn.setStyleSheet(tab_button_style)
        self.snoring_btn.setStyleSheet(tab_button_style)
        self.desaturation_btn.setStyleSheet(tab_button_style)
        self.csr_btn.setStyleSheet(tab_button_style)
        
        # Add buttons to layout
        tab_buttons_layout.addWidget(self.apnea_btn)
        tab_buttons_layout.addWidget(self.hypoapnea_btn)
        tab_buttons_layout.addWidget(self.snoring_btn)
        tab_buttons_layout.addWidget(self.desaturation_btn)
        tab_buttons_layout.addWidget(self.csr_btn)
        tab_buttons_layout.addStretch()
        
        main_layout.addLayout(tab_buttons_layout)
        
        # Create content area for tabs
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        self.content_layout.setSpacing(15)
        
        # Create all tab content (initially hidden except first)
        self.apnea_content = self.create_apnea_content()
        self.hypoapnea_content = self.create_hypoapnea_content()
        self.snoring_content = self.create_snoring_content()
        self.desaturation_content = self.create_desaturation_content()
        self.csr_content = self.create_csr_content()
        
        # Add all content to layout (only show first initially)
        self.content_layout.addWidget(self.apnea_content)
        self.content_layout.addWidget(self.hypoapnea_content)
        self.content_layout.addWidget(self.snoring_content)
        self.content_layout.addWidget(self.desaturation_content)
        self.content_layout.addWidget(self.csr_content)
        
        # Initially hide all except apnea
        self.hypoapnea_content.hide()
        self.snoring_content.hide()
        self.desaturation_content.hide()
        self.csr_content.hide()
        
        main_layout.addWidget(self.content_area)
        
        # Bottom buttons
        button_frame = self.create_button_layout()
        main_layout.addWidget(button_frame)
        
    def show_tab(self, tab_name):
        """Switch between tabs"""
        # Uncheck all buttons
        self.apnea_btn.setChecked(False)
        self.hypoapnea_btn.setChecked(False)
        self.snoring_btn.setChecked(False)
        self.desaturation_btn.setChecked(False)
        self.csr_btn.setChecked(False)
        
        # Hide all content
        self.apnea_content.hide()
        self.hypoapnea_content.hide()
        self.snoring_content.hide()
        self.desaturation_content.hide()
        self.csr_content.hide()
        
        # Show selected tab and check button
        if tab_name == 'apnea':
            self.apnea_content.show()
            self.apnea_btn.setChecked(True)
        elif tab_name == 'hypoapnea':
            self.hypoapnea_content.show()
            self.hypoapnea_btn.setChecked(True)
        elif tab_name == 'snoring':
            self.snoring_content.show()
            self.snoring_btn.setChecked(True)
        elif tab_name == 'desaturation':
            self.desaturation_content.show()
            self.desaturation_btn.setChecked(True)
        elif tab_name == 'csr':
            self.csr_content.show()
            self.csr_btn.setChecked(True)
    
    def create_apnea_content(self):
        """Create apnea tab content"""
        return self.create_apnea_section()
    
    def create_hypoapnea_content(self):
        """Create hypoapnea tab content"""
        return self.create_hypoapnea_section()
    
    def create_snoring_content(self):
        """Create snoring tab content"""
        group = QGroupBox("Snoring Detection")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #2c3e50;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f8fafc, stop: 1 #f3f4f5
                );
            }
        """)
        layout = QGridLayout()
        layout.setSpacing(10)
        
        # Enable Snoring Detection
        self.snoring_enabled = QCheckBox("Enable Snoring Detection")
        self.snoring_enabled.setChecked(True)
        self.snoring_enabled.stateChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.snoring_enabled, 0, 0, 1, 2)
        
        # Snoring Threshold
        layout.addWidget(QLabel("Snoring Threshold:"), 1, 0, 1, 1)
        self.snoring_threshold = QDoubleSpinBox()
        self.snoring_threshold.setRange(20.0, 100.0)
        self.snoring_threshold.setSingleStep(1.0)
        self.snoring_threshold.setDecimals(0)
        self.snoring_threshold.setValue(50.0)
        self.snoring_threshold.setSuffix(" dB")
        self.snoring_threshold.valueChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.snoring_threshold, 1, 1, 1, 1)
        
        # Duration Threshold
        layout.addWidget(QLabel("Duration Threshold:"), 2, 0, 1, 1)
        self.snoring_duration = QDoubleSpinBox()
        self.snoring_duration.setRange(0.1, 10.0)
        self.snoring_duration.setSingleStep(0.1)
        self.snoring_duration.setDecimals(1)
        self.snoring_duration.setValue(2.0)
        self.snoring_duration.setSuffix(" seconds")
        self.snoring_duration.valueChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.snoring_duration, 2, 1, 1, 1)
        
        # Frequency Analysis
        self.snoring_frequency_enabled = QCheckBox("Enable Frequency Analysis")
        self.snoring_frequency_enabled.setChecked(False)
        self.snoring_frequency_enabled.stateChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.snoring_frequency_enabled, 3, 0, 1, 2)
        
        # Snoring Index
        layout.addWidget(QLabel("Snoring Index:"), 4, 0, 1, 1)
        self.snoring_index_label = QLabel("0.0 events/hour")
        self.snoring_index_label.setStyleSheet("font-weight: bold; color: #2563eb;")
        layout.addWidget(self.snoring_index_label, 4, 1, 1, 1)
        
        group.setLayout(layout)
        return group
    
    def create_desaturation_content(self):
        """Create desaturation tab content"""
        group = QGroupBox("Desaturation Detection")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #2c3e50;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f8fafc, stop: 1 #f3f4f5
                );
            }
        """)
        layout = QGridLayout()
        layout.setSpacing(10)
        
        # Enable Desaturation Detection
        self.desaturation_enabled = QCheckBox("Enable Desaturation Detection")
        self.desaturation_enabled.setChecked(True)
        self.desaturation_enabled.stateChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.desaturation_enabled, 0, 0, 1, 2)
        
        # Desaturation Threshold
        layout.addWidget(QLabel("Desaturation Threshold:"), 1, 0, 1, 1)
        self.desaturation_level = QDoubleSpinBox()
        self.desaturation_level.setRange(1.0, 10.0)
        self.desaturation_level.setSingleStep(0.1)
        self.desaturation_level.setDecimals(1)
        self.desaturation_level.setValue(3.0)
        self.desaturation_level.setSuffix(" %")
        self.desaturation_level.valueChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.desaturation_level, 1, 1, 1, 1)
        
        # Duration Threshold
        layout.addWidget(QLabel("Duration Threshold:"), 2, 0, 1, 1)
        self.desaturation_duration = QDoubleSpinBox()
        self.desaturation_duration.setRange(5.0, 60.0)
        self.desaturation_duration.setSingleStep(1.0)
        self.desaturation_duration.setDecimals(0)
        self.desaturation_duration.setValue(10.0)
        self.desaturation_duration.setSuffix(" seconds")
        self.desaturation_duration.valueChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.desaturation_duration, 2, 1, 1, 1)
        
        # Baseline Calculation
        layout.addWidget(QLabel("Baseline Period:"), 3, 0, 1, 1)
        self.desaturation_baseline = QSpinBox()
        self.desaturation_baseline.setRange(30, 300)
        self.desaturation_baseline.setSingleStep(10)
        self.desaturation_baseline.setValue(60)
        self.desaturation_baseline.setSuffix(" seconds")
        self.desaturation_baseline.valueChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.desaturation_baseline, 3, 1, 1, 1)
        
        # Desaturation Index
        layout.addWidget(QLabel("Desaturation Index:"), 4, 0, 1, 1)
        self.desaturation_index_label = QLabel("0.0 events/hour")
        self.desaturation_index_label.setStyleSheet("font-weight: bold; color: #2563eb;")
        layout.addWidget(self.desaturation_index_label, 4, 1, 1, 1)
        
        group.setLayout(layout)
        return group
    
    def create_csr_content(self):
        """Create CSR (Cheyne-Stokes Respiration) tab content"""
        group = QGroupBox("CSR Detection")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #2c3e50;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f8fafc, stop: 1 #f3f4f5
                );  
            }
        """)
        layout = QGridLayout()
        layout.setSpacing(10)
        
        # Enable CSR Detection
        self.csr_enabled = QCheckBox("Enable CSR Detection")
        self.csr_enabled.setChecked(False)
        self.csr_enabled.stateChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.csr_enabled, 0, 0, 1, 2)
        
        # Cycle Duration
        layout.addWidget(QLabel("Cycle Duration:"), 1, 0, 1, 1)
        self.csr_cycle_duration = QDoubleSpinBox()
        self.csr_cycle_duration.setRange(20.0, 120.0)
        self.csr_cycle_duration.setSingleStep(5.0)
        self.csr_cycle_duration.setDecimals(0)
        self.csr_cycle_duration.setValue(45.0)
        self.csr_cycle_duration.setSuffix(" seconds")
        self.csr_cycle_duration.valueChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.csr_cycle_duration, 1, 1, 1, 1)
        
        # Amplitude Threshold
        layout.addWidget(QLabel("Amplitude Threshold:"), 2, 0, 1, 1)
        self.csr_amplitude = QDoubleSpinBox()
        self.csr_amplitude.setRange(10.0, 100.0)
        self.csr_amplitude.setSingleStep(5.0)
        self.csr_amplitude.setDecimals(0)
        self.csr_amplitude.setValue(30.0)
        self.csr_amplitude.setSuffix(" %")
        self.csr_amplitude.valueChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.csr_amplitude, 2, 1, 1, 1)
        
        # Minimum Cycles
        layout.addWidget(QLabel("Minimum Cycles:"), 3, 0, 1, 1)
        self.csr_min_cycles = QSpinBox()
        self.csr_min_cycles.setRange(3, 20)
        self.csr_min_cycles.setSingleStep(1)
        self.csr_min_cycles.setValue(5)
        self.csr_min_cycles.setSuffix(" cycles")
        self.csr_min_cycles.valueChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.csr_min_cycles, 3, 1, 1, 1)
        
        # CSR Index
        layout.addWidget(QLabel("CSR Index:"), 4, 0, 1, 1)
        self.csr_index_label = QLabel("0.0 events/hour")
        self.csr_index_label.setStyleSheet("font-weight: bold; color: #2563eb;")
        layout.addWidget(self.csr_index_label, 4, 1, 1, 1)
        
        group.setLayout(layout)
        return group
        
    def create_apnea_section(self):
        """Create apnea detection parameters section"""
        group = QGroupBox("Apnea Detection")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #2c3e50;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f8fafc, stop: 1 #f3f4f5
                );
            }
        """)
        layout = QGridLayout()
        layout.setSpacing(10)
        
        # Enable Apnea Detection
        self.apnea_enabled = QCheckBox("Enable Apnea Detection")
        self.apnea_enabled.setChecked(self.parameters['apnea_detection'])
        self.apnea_enabled.stateChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.apnea_enabled, 0, 0, 1, 2)
        
        # Central Apnea Threshold
        layout.addWidget(QLabel("Central Apnea Threshold:"), 1, 0, 1, 1)
        self.central_threshold = QDoubleSpinBox()
        self.central_threshold.setRange(0.0, 10.0)
        self.central_threshold.setSingleStep(0.1)
        self.central_threshold.setDecimals(1)
        self.central_threshold.setValue(self.parameters['central_apnea_threshold'])
        self.central_threshold.setSuffix(" seconds")
        self.central_threshold.valueChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.central_threshold, 1, 1, 1, 1)
        
        # Obstructive Apnea Threshold
        layout.addWidget(QLabel("Obstructive Apnea Threshold:"), 2, 0, 1, 1)
        self.obstructive_threshold = QDoubleSpinBox()
        self.obstructive_threshold.setRange(0.0, 20.0)
        self.obstructive_threshold.setSingleStep(0.1)
        self.obstructive_threshold.setDecimals(1)
        self.obstructive_threshold.setValue(self.parameters['obstructive_apnea_threshold'])
        self.obstructive_threshold.setSuffix(" seconds")
        self.obstructive_threshold.valueChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.obstructive_threshold, 2, 1, 1, 1)
        
        # Hypopnea Threshold
        layout.addWidget(QLabel("Hypopnea Threshold:"), 3, 0, 1, 1)
        self.hypopnea_threshold = QDoubleSpinBox()
        self.hypopnea_threshold.setRange(0.0, 15.0)
        self.hypopnea_threshold.setSingleStep(0.1)
        self.hypopnea_threshold.setDecimals(1)
        self.hypopnea_threshold.setValue(self.parameters['hypopnea_threshold'])
        self.hypopnea_threshold.setSuffix(" seconds")
        self.hypopnea_threshold.valueChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.hypopnea_threshold, 3, 1, 1, 1)
        
        # Desaturation Threshold
        layout.addWidget(QLabel("Desaturation Threshold:"), 4, 0, 1, 1)
        self.desaturation_threshold = QDoubleSpinBox()
        self.desaturation_threshold.setRange(1.0, 10.0)
        self.desaturation_threshold.setSingleStep(0.1)
        self.desaturation_threshold.setDecimals(1)
        self.desaturation_threshold.setValue(self.parameters['desaturation_threshold'])
        self.desaturation_threshold.setSuffix(" %")
        self.desaturation_threshold.valueChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.desaturation_threshold, 4, 1, 1, 1)
        
        # Apnea Index Calculation
        layout.addWidget(QLabel("Apnea Index:"), 5, 0, 1, 1)
        self.apnea_index_label = QLabel("0.0 events/hour")
        self.apnea_index_label.setStyleSheet("font-weight: bold; color: #2563eb;")
        layout.addWidget(self.apnea_index_label, 5, 1, 1, 1)
        
        group.setLayout(layout)
        return group
        
    def create_hypoapnea_section(self):
        """Create hypoapnea detection parameters section"""
        group = QGroupBox("Hypoapnea")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #2c3e50;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f8fafc, stop: 1 #f3f4f5
                );
            }
        """)
        layout = QGridLayout()
        layout.setSpacing(10)
        
        # Enable Hypoapnea Detection
        self.hypoapnea_enabled = QCheckBox("Enable Hypoapnea Detection")
        self.hypoapnea_enabled.setChecked(True)
        self.hypoapnea_enabled.stateChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.hypoapnea_enabled, 0, 0, 1, 2)
        
        # Hypoapnea Duration Threshold
        layout.addWidget(QLabel("Duration Threshold:"), 1, 0, 1, 1)
        self.hypoapnea_duration = QDoubleSpinBox()
        self.hypoapnea_duration.setRange(0.0, 30.0)
        self.hypoapnea_duration.setSingleStep(0.1)
        self.hypoapnea_duration.setDecimals(1)
        self.hypoapnea_duration.setValue(8.0)
        self.hypoapnea_duration.setSuffix(" seconds")
        self.hypoapnea_duration.valueChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.hypoapnea_duration, 1, 1, 1, 1)
        
        # Airflow Reduction Threshold
        layout.addWidget(QLabel("Airflow Reduction:"), 2, 0, 1, 1)
        self.airflow_reduction = QDoubleSpinBox()
        self.airflow_reduction.setRange(10.0, 90.0)
        self.airflow_reduction.setSingleStep(1.0)
        self.airflow_reduction.setDecimals(0)
        self.airflow_reduction.setValue(30.0)
        self.airflow_reduction.setSuffix(" %")
        self.airflow_reduction.valueChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.airflow_reduction, 2, 1, 1, 1)
        
        # Oxygen Desaturation
        layout.addWidget(QLabel("Oxygen Desaturation:"), 3, 0, 1, 1)
        self.oxygen_desaturation = QDoubleSpinBox()
        self.oxygen_desaturation.setRange(1.0, 10.0)
        self.oxygen_desaturation.setSingleStep(0.1)
        self.oxygen_desaturation.setDecimals(1)
        self.oxygen_desaturation.setValue(3.0)
        self.oxygen_desaturation.setSuffix(" %")
        self.oxygen_desaturation.valueChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.oxygen_desaturation, 3, 1, 1, 1)
        
        # Hypoapnea Index Calculation
        layout.addWidget(QLabel("Hypoapnea Index:"), 4, 0, 1, 1)
        self.hypoapnea_index_label = QLabel("0.0 events/hour")
        self.hypoapnea_index_label.setStyleSheet("font-weight: bold; color: #2563eb;")
        layout.addWidget(self.hypoapnea_index_label, 4, 1, 1, 1)
        
        group.setLayout(layout)
        return group
        
    def create_signal_processing_section(self):
        """Create signal processing parameters section"""
        group = QGroupBox("Signal Processing")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #2c3e50;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f8fafc, stop: 1 #f3f4f5
                );
            }
        """)
        layout = QGridLayout()
        layout.setSpacing(10)
        
        # Baseline Calculation
        layout.addWidget(QLabel("Baseline Calculation:"), 0, 0, 1, 1)
        self.baseline_combo = QComboBox()
        self.baseline_combo.addItems(["Moving Average", "Exponential", "Linear", "None"])
        self.baseline_combo.setCurrentText(self.parameters['baseline_calculation'])
        self.baseline_combo.currentTextChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.baseline_combo, 0, 1, 1, 1)
        
        # Smoothing Factor
        layout.addWidget(QLabel("Smoothing Factor:"), 1, 0, 1, 1)
        self.smoothing_slider = QSlider(Qt.Horizontal)
        self.smoothing_slider.setRange(0, 100)
        self.smoothing_slider.setValue(int(self.parameters['smoothing_factor'] * 100))
        self.smoothing_slider.valueChanged.connect(self.on_smoothing_changed)
        layout.addWidget(self.smoothing_slider, 1, 1, 1, 1)
        
        self.smoothing_label = QLabel(f"{self.parameters['smoothing_factor']:.2f}")
        layout.addWidget(self.smoothing_label, 1, 2, 1, 1)
        
        group.setLayout(layout)
        return group
        
    def create_event_detection_section(self):
        """Create event detection parameters section"""
        group = QGroupBox("Event Detection")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #2c3e50;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f8fafc, stop: 1 #f3f4f5
                );
            }
        """)
        layout = QGridLayout()
        layout.setSpacing(10)
        
        # Minimum Event Duration
        layout.addWidget(QLabel("Minimum Event Duration:"), 0, 0, 1, 1)
        self.event_duration_min = QDoubleSpinBox()
        self.event_duration_min.setRange(1.0, 60.0)
        self.event_duration_min.setSingleStep(0.1)
        self.event_duration_min.setDecimals(1)
        self.event_duration_min.setValue(self.parameters['event_duration_min'])
        self.event_duration_min.setSuffix(" seconds")
        self.event_duration_min.valueChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.event_duration_min, 0, 1, 1, 1)
        
        # Sensitivity
        layout.addWidget(QLabel("Detection Sensitivity:"), 1, 0, 1, 1)
        self.sensitivity_slider = QSlider(Qt.Horizontal)
        self.sensitivity_slider.setRange(1, 10)
        self.sensitivity_slider.setValue(5)  # Default medium sensitivity
        self.sensitivity_slider.valueChanged.connect(self.on_sensitivity_changed)
        layout.addWidget(self.sensitivity_slider, 1, 1, 1, 1)
        
        self.sensitivity_label = QLabel("Medium")
        layout.addWidget(self.sensitivity_label, 1, 2, 1, 1)
        
        group.setLayout(layout)
        return group
        
    def create_algorithm_section(self):
        """Create analysis algorithm section"""
        group = QGroupBox("Analysis Algorithm")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #2c3e50;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f8fafc, stop: 1 #f3f4f5
                );
            }
        """)
        layout = QGridLayout()
        layout.setSpacing(10)
        
        # Analysis Algorithm
        layout.addWidget(QLabel("Algorithm:"), 0, 0, 1, 1)
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems(["Auto", "AASM Manual", "Custom", "ML Enhanced"])
        self.algorithm_combo.setCurrentText(self.parameters['analysis_algorithm'])
        self.algorithm_combo.currentTextChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.algorithm_combo, 0, 1, 1, 1)
        
        # Update Frequency
        layout.addWidget(QLabel("Update Frequency:"), 1, 0, 1, 1)
        self.update_frequency = QSpinBox()
        self.update_frequency.setRange(1, 60)
        self.update_frequency.setValue(10)  # Default 10 Hz
        self.update_frequency.setSuffix(" Hz")
        self.update_frequency.valueChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.update_frequency, 1, 1, 1, 1)
        
        group.setLayout(layout)
        return group
        
    def create_realtime_section(self):
        """Create real-time processing section"""
        group = QGroupBox("Real-time Processing")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                color: #2c3e50;
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f8fafc, stop: 1 #f3f4f5
                );
            }
        """)
        layout = QGridLayout()
        layout.setSpacing(10)
        
        # Real-time Processing
        self.realtime_enabled = QCheckBox("Enable Real-time Processing")
        self.realtime_enabled.setChecked(self.parameters['real_time_processing'])
        self.realtime_enabled.stateChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.realtime_enabled, 0, 0, 1, 1)
        
        # Auto Update
        self.auto_update_enabled = QCheckBox("Auto Update Parameters")
        self.auto_update_enabled.setChecked(self.parameters['auto_update'])
        self.auto_update_enabled.stateChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.auto_update_enabled, 0, 1, 1, 1)
        
        # Processing Delay
        layout.addWidget(QLabel("Processing Delay:"), 1, 0, 1, 1)
        self.processing_delay = QSpinBox()
        self.processing_delay.setRange(0, 1000)
        self.processing_delay.setValue(100)  # Default 100ms
        self.processing_delay.setSuffix(" ms")
        self.processing_delay.valueChanged.connect(self.on_parameter_changed)
        layout.addWidget(self.processing_delay, 1, 1, 1, 1)
        
        group.setLayout(layout)
        return group
        
    def create_button_layout(self):
        """Create bottom button layout"""
        button_frame = QFrame()
        button_layout = QHBoxLayout(button_frame)
        button_layout.setSpacing(10)
        
        # Apply button
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #10b981, stop: 1 #059669
                );
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #059669, stop: 1 #047857
                );
            }
            QPushButton:pressed {
                background: #047857;
            }
        """)
        self.apply_btn.clicked.connect(self.apply_parameters)
        button_layout.addWidget(self.apply_btn)
        
        # Reset button
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ef4444, stop: 1 #dc2626
                );
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #dc2626, stop: 1 #b91c1c
                );
            }
            QPushButton:pressed {
                background: #b91c1c;
            }
        """)
        self.reset_btn.clicked.connect(self.reset_parameters)
        button_layout.addWidget(self.reset_btn)
        
        button_layout.addStretch()
        
        button_frame.setLayout(button_layout)
        return button_frame
        
    def on_parameter_changed(self):
        """Handle parameter changes"""
        self.update_apnea_index()
        self.parameters_changed.emit(self.get_current_parameters())
    
    def update_apnea_index(self):
        """Calculate and display real-time apnea index"""
        if self.apnea_enabled.isChecked():
            # Simulate apnea index calculation based on thresholds
            central_events = 10.0 / self.central_threshold.value() if self.central_threshold.value() > 0 else 0
            obstructive_events = 15.0 / self.obstructive_threshold.value() if self.obstructive_threshold.value() > 0 else 0
            hypopnea_events = 8.0 / self.hypopnea_threshold.value() if self.hypopnea_threshold.value() > 0 else 0
            
            # Calculate total events per hour (simplified calculation)
            total_events = central_events + obstructive_events + hypopnea_events
            apnea_index = total_events * 0.8  # Adjust for sleep efficiency
            
            self.apnea_index_label.setText(f"{apnea_index:.1f} events/hour")
            
            # Color code based on severity
            if apnea_index < 5:
                color = "#10b981"  # Green - Normal
            elif apnea_index < 15:
                color = "#f59e0b"  # Yellow - Mild
            elif apnea_index < 30:
                color = "#ef4444"  # Orange - Moderate
            else:
                color = "#dc2626"  # Red - Severe
            
            self.apnea_index_label.setStyleSheet(f"font-weight: bold; color: {color};")
        else:
            self.apnea_index_label.setText("0.0 events/hour")
            self.apnea_index_label.setStyleSheet("font-weight: bold; color: #6b7280;")
        
        # Update hypoapnea index
        if self.hypoapnea_enabled.isChecked():
            # Simulate hypoapnea index calculation
            duration_factor = 8.0 / self.hypoapnea_duration.value() if self.hypoapnea_duration.value() > 0 else 0
            airflow_factor = 30.0 / self.airflow_reduction.value() if self.airflow_reduction.value() > 0 else 0
            desaturation_factor = 3.0 / self.oxygen_desaturation.value() if self.oxygen_desaturation.value() > 0 else 0
            
            total_hypoapnea_events = duration_factor + airflow_factor + desaturation_factor
            hypoapnea_index = total_hypoapnea_events * 0.6  # Adjust for sleep efficiency
            
            self.hypoapnea_index_label.setText(f"{hypoapnea_index:.1f} events/hour")
            
            # Color code based on severity
            if hypoapnea_index < 5:
                color = "#10b981"  # Green - Normal
            elif hypoapnea_index < 15:
                color = "#f59e0b"  # Yellow - Mild
            elif hypoapnea_index < 30:
                color = "#ef4444"  # Orange - Moderate
            else:
                color = "#dc2626"  # Red - Severe
            
            self.hypoapnea_index_label.setStyleSheet(f"font-weight: bold; color: {color};")
        else:
            self.hypoapnea_index_label.setText("0.0 events/hour")
            self.hypoapnea_index_label.setStyleSheet("font-weight: bold; color: #6b7280;")
        
    def on_smoothing_changed(self, value):
        """Handle smoothing slider change"""
        smoothing_factor = value / 100.0
        self.parameters['smoothing_factor'] = smoothing_factor
        self.smoothing_label.setText(f"{smoothing_factor:.2f}")
        self.on_parameter_changed()
        
    def on_sensitivity_changed(self, value):
        """Handle sensitivity slider change"""
        sensitivity_labels = ["Very Low", "Low", "Medium", "High", "Very High"]
        self.sensitivity_label.setText(sensitivity_labels[value - 1])
        self.on_parameter_changed()
        
    def get_current_parameters(self):
        """Get current parameter values"""
        return {
            'apnea_detection': self.apnea_enabled.isChecked(),
            'central_apnea_threshold': self.central_threshold.value(),
            'obstructive_apnea_threshold': self.obstructive_threshold.value(),
            'hypopnea_threshold': self.hypopnea_threshold.value(),
            'desaturation_threshold': self.desaturation_threshold.value(),
            'hypoapnea_detection': self.hypoapnea_enabled.isChecked(),
            'hypoapnea_duration': self.hypoapnea_duration.value(),
            'airflow_reduction': self.airflow_reduction.value(),
            'oxygen_desaturation': self.oxygen_desaturation.value(),
            'snoring_detection': self.snoring_enabled.isChecked(),
            'snoring_threshold': self.snoring_threshold.value(),
            'snoring_duration': self.snoring_duration.value(),
            'snoring_frequency': self.snoring_frequency_enabled.isChecked(),
            'desaturation_detection': self.desaturation_enabled.isChecked(),
            'desaturation_level': self.desaturation_level.value(),
            'desaturation_duration': self.desaturation_duration.value(),
            'desaturation_baseline': self.desaturation_baseline.value(),
            'csr_detection': self.csr_enabled.isChecked(),
            'csr_cycle_duration': self.csr_cycle_duration.value(),
            'csr_amplitude': self.csr_amplitude.value(),
            'csr_min_cycles': self.csr_min_cycles.value(),
            'event_duration_min': self.event_duration_min.value(),
            'baseline_calculation': self.baseline_combo.currentText(),
            'smoothing_factor': self.smoothing_slider.value() / 100.0,
            'analysis_algorithm': self.algorithm_combo.currentText(),
            'real_time_processing': self.realtime_enabled.isChecked(),
            'auto_update': self.auto_update_enabled.isChecked(),
            'sensitivity': self.sensitivity_slider.value(),
            'update_frequency': self.update_frequency.value(),
            'processing_delay': self.processing_delay.value()
        }
        
    def apply_parameters(self):
        """Apply parameters and close dialog"""
        current_params = self.get_current_parameters()
        print(f"Applied analysis parameters: {current_params}")
        
        # Emit signal with parameters
        self.parameters_changed.emit(current_params)
        
        # Close dialog
        self.accept()
        
    def reset_parameters(self):
        """Reset all parameters to defaults"""
        self.apnea_enabled.setChecked(True)
        self.central_threshold.setValue(3.0)
        self.obstructive_threshold.setValue(10.0)
        self.hypopnea_threshold.setValue(8.0)
        self.desaturation_threshold.setValue(3.0)
        self.event_duration_min.setValue(10.0)
        self.baseline_combo.setCurrentText("Moving Average")
        self.smoothing_slider.setValue(80)
        self.sensitivity_slider.setValue(5)
        self.algorithm_combo.setCurrentText("Auto")
        self.realtime_enabled.setChecked(True)
        self.auto_update_enabled.setChecked(True)
        self.update_frequency.setValue(10)
        self.processing_delay.setValue(100)
        
        print("Parameters reset to defaults")
        self.on_parameter_changed()
