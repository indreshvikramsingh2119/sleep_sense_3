"""
Amplitude Axis Properties Dialog - Exact replica of the axis properties dialog
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QGroupBox, QLabel, QLineEdit, QCheckBox, QRadioButton,
    QButtonGroup, QPushButton, QDialogButtonBox, QGridLayout, QFormLayout
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QDoubleValidator, QFont


class AmplitudeAxisPropertiesDialog(QDialog):
    """Amplitude Axis Properties Dialog - Exact replica of the image"""
    
    # Signal to emit when properties are applied
    properties_changed = pyqtSignal(dict)
    
    def __init__(self, parent=None, current_properties=None):
        super().__init__(parent)
        self.setWindowTitle("Amplitude Axis Properties")
        self.setModal(True)
        self.resize(400, 350)
        
        # Store current properties
        if current_properties:
            self.properties = current_properties.copy()
        else:
            self.properties = {
                'low_value': 35.0,
                'high_value': 100.0,
                'limit_axis_range': False,
                'limit_low_value': 85.0,
                'limit_high_value': 100.0,
                'auto_adjust': 'scale_to_fit'  # 'disabled', 'center', 'scale_to_fit'
            }
        self.init_ui()
        self.load_current_properties()
    
    def init_ui(self):
        """Initialize the UI exactly as shown in the image"""
        main_layout = QVBoxLayout(self)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Create Scale tab (the main one we need)
        self.scale_tab = self.create_scale_tab()
        self.tab_widget.addTab(self.scale_tab, "Scale")
        
        # Create View tab (placeholder for now)
        self.view_tab = QWidget()
        self.tab_widget.addTab(self.view_tab, "View")
        
        # Create Format tab (placeholder for now)
        self.format_tab = QWidget()
        self.tab_widget.addTab(self.format_tab, "Format")
        
        main_layout.addWidget(self.tab_widget)
        
        # Create OK and Cancel buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept_changes)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
    
    def create_scale_tab(self):
        """Create the Scale tab with exact layout as shown in image"""
        scale_widget = QWidget()
        scale_layout = QVBoxLayout(scale_widget)
        scale_layout.setSpacing(15)
        scale_layout.setContentsMargins(10, 10, 10, 10)
        
        # Scale group
        scale_group = QGroupBox("Scale")
        scale_group_layout = QGridLayout(scale_group)
        scale_group_layout.setSpacing(10)
        
        # Low value input
        self.low_value_label = QLabel("Low value:")
        self.low_value_input = QLineEdit()
        self.low_value_input.setFixedWidth(80)
        self.low_value_input.setAlignment(Qt.AlignRight)
        self.low_value_input.setValidator(QDoubleValidator(0.0, 999.99, 2))
        
        self.low_value_percent_label = QLabel("%")
        
        scale_group_layout.addWidget(self.low_value_label, 0, 0)
        scale_group_layout.addWidget(self.low_value_input, 0, 1)
        scale_group_layout.addWidget(self.low_value_percent_label, 0, 2)
        
        # High value input
        self.high_value_label = QLabel("High value:")
        self.high_value_input = QLineEdit()
        self.high_value_input.setFixedWidth(80)
        self.high_value_input.setAlignment(Qt.AlignRight)
        self.high_value_input.setValidator(QDoubleValidator(0.0, 999.99, 2))
        
        self.high_value_percent_label = QLabel("%")
        
        scale_group_layout.addWidget(self.high_value_label, 1, 0)
        scale_group_layout.addWidget(self.high_value_input, 1, 1)
        scale_group_layout.addWidget(self.high_value_percent_label, 1, 2)
        
        scale_layout.addWidget(scale_group)
        
        # Limit Axis Range group
        limit_group = QGroupBox("Limit Axis Range")
        limit_group_layout = QGridLayout(limit_group)
        limit_group_layout.setSpacing(10)
        
        self.limit_axis_range_checkbox = QCheckBox()
        limit_group_layout.addWidget(self.limit_axis_range_checkbox, 0, 0, 1, 3)
        
        # Limit low value
        self.limit_low_value_label = QLabel("Low value:")
        self.limit_low_value_input = QLineEdit()
        self.limit_low_value_input.setFixedWidth(80)
        self.limit_low_value_input.setAlignment(Qt.AlignRight)
        self.limit_low_value_input.setValidator(QDoubleValidator(0.0, 999.99, 2))
        self.limit_low_value_input.setEnabled(False)
        
        self.limit_low_value_percent_label = QLabel("%")
        
        limit_group_layout.addWidget(self.limit_low_value_label, 1, 0)
        limit_group_layout.addWidget(self.limit_low_value_input, 1, 1)
        limit_group_layout.addWidget(self.limit_low_value_percent_label, 1, 2)
        
        # Limit high value
        self.limit_high_value_label = QLabel("High value:")
        self.limit_high_value_input = QLineEdit()
        self.limit_high_value_input.setFixedWidth(80)
        self.limit_high_value_input.setAlignment(Qt.AlignRight)
        self.limit_high_value_input.setValidator(QDoubleValidator(0.0, 999.99, 2))
        self.limit_high_value_input.setEnabled(False)
        
        self.limit_high_value_percent_label = QLabel("%")
        
        limit_group_layout.addWidget(self.limit_high_value_label, 2, 0)
        limit_group_layout.addWidget(self.limit_high_value_input, 2, 1)
        limit_group_layout.addWidget(self.limit_high_value_percent_label, 2, 2)
        
        scale_layout.addWidget(limit_group)
        
        # Auto-Adjust group
        auto_adjust_group = QGroupBox("Auto-Adjust")
        auto_adjust_layout = QVBoxLayout(auto_adjust_group)
        auto_adjust_layout.setSpacing(8)
        
        # Create button group for radio buttons
        self.auto_adjust_button_group = QButtonGroup()
        
        # Disabled radio button
        self.disabled_radio = QRadioButton("Disabled")
        self.auto_adjust_button_group.addButton(self.disabled_radio, 0)
        auto_adjust_layout.addWidget(self.disabled_radio)
        auto_adjust_layout.addWidget(self.auto_adjust_button_group)
        
        # Center radio button
        self.center_radio = QRadioButton("Center")
        self.auto_adjust_button_group.addButton(self.center_radio, 1)
        auto_adjust_layout.addWidget(self.center_radio)
        
        # Scale to fit radio button
        self.scale_to_fit_radio = QRadioButton("Scale to fit")
        self.auto_adjust_button_group.addButton(self.scale_to_fit_radio, 2)
        auto_adjust_layout.addWidget(self.scale_to_fit_radio)
        
        scale_layout.addWidget(auto_adjust_group)
        
        # Add stretch to push everything to the top
        scale_layout.addStretch()
        
        # Connect checkbox to enable/disable limit inputs
        self.limit_axis_range_checkbox.toggled.connect(self.toggle_limit_inputs)
        
        return scale_widget
    
    def toggle_limit_inputs(self, checked):
        """Enable/disable limit value inputs based on checkbox state"""
        self.limit_low_value_input.setEnabled(checked)
        self.limit_high_value_input.setEnabled(checked)
    
    def load_current_properties(self):
        """Load current properties into the UI"""
        # Load scale values
        self.low_value_input.setText(f"{self.properties.get('low_value', 35.0):.2f}")
        self.high_value_input.setText(f"{self.properties.get('high_value', 100.0):.2f}")
        
        # Load limit axis range
        limit_checked = self.properties.get('limit_axis_range', False)
        self.limit_axis_range_checkbox.setChecked(limit_checked)
        self.limit_low_value_input.setText(f"{self.properties.get('limit_low_value', 85.0):.2f}")
        self.limit_high_value_input.setText(f"{self.properties.get('limit_high_value', 100.0):.2f}")
       
        
        # Load auto-adjust
        auto_adjust = self.properties.get('auto_adjust', 'scale_to_fit')
        if auto_adjust == 'disabled':
            self.disabled_radio.setChecked(True)
        elif auto_adjust == 'center':
            self.center_radio.setChecked(True)
        else:  # scale_to_fit
            self.scale_to_fit_radio.setChecked(True)
    
    def get_properties(self):
        """Get current properties from the UI"""

         
        properties = {
            'low_value': float(self.low_value_input.text() or 75.0),
            'high_value': float(self.high_value_input.text() or 100.0),
            'limit_axis_range': self.limit_axis_range_checkbox.isChecked(),
            'limit_low_value': float(self.limit_low_value_input.text() or 75.0),
            'limit_high_value': float(self.limit_high_value_input.text() or 100.0),
        }
        
        # Get auto-adjust selection
        if self.disabled_radio.isChecked():
            properties['auto_adjust'] = 'disabled'
        elif self.center_radio.isChecked():
            properties['auto_adjust'] = 'center'
        else:
            properties['auto_adjust'] = 'scale_to_fit'
        
        return properties
    
    def accept_changes(self):
        """Handle OK button click"""
        self.properties = self.get_properties()
        self.properties_changed.emit(self.properties)
        self.accept()
    
    def get_current_properties(self):
        """Get the current properties"""
        return self.properties.copy()
