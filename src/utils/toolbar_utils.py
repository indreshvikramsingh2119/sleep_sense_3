"""
Toolbar Utils Module - Professional Icon Toolbar for Sleep Sense
Contains reusable functions for creating consistent toolbar buttons
"""

import os
from PyQt5.QtWidgets import QPushButton, QToolBar
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QSize


def create_toolbar_button(icon_path, tooltip, status_tip, callback):
    """
    Create a consistent toolbar button with uniform styling
    
    Args:
        icon_path (str): Path to the icon file
        tooltip (str): Tooltip text for the button
        status_tip (str): Status bar text for the button
        callback (function): Function to call when button is clicked
    
    Returns:
        QPushButton: Configured toolbar button
    """
    btn = QPushButton()
    
    # Set icon if exists, otherwise use text fallback
    if os.path.exists(icon_path):
        icon = QIcon(icon_path)
        btn.setIcon(icon)
        btn.setIconSize(QSize(24, 24))  # Set icon size
    else:
        # Fallback to text if icon doesn't exist
        btn.setText(tooltip.split()[0])  # Use first word of tooltip
    
    btn.setToolTip(tooltip)
    btn.setStatusTip(status_tip)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setMouseTracking(True)  # Enable mouse tracking for tooltips
    btn.clicked.connect(callback)
    btn.setFixedSize(40, 40)  # uniform size
    
    # Set tooltip duration to ensure it shows
    btn.setToolTipDuration(3000)  # Show for 3 seconds
    
    return btn


def create_professional_toolbar(parent, toolbar_name="MainToolbar"):
    """
    Create a professional toolbar with grouped icons
    
    Args:
        parent: Parent window/widget
        toolbar_name (str): Name of the toolbar
    
    Returns:
        QToolBar: Configured toolbar
    """
    toolbar = QToolBar(toolbar_name)
    toolbar.setMovable(False)
    toolbar.setIconSize(QSize(32, 32))
    toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
    
    return toolbar


def get_icon_definitions():
    """
    Get icon definitions for all toolbar buttons
    
    Returns:
        list: List of icon definition dictionaries
    """
    return [
        {
            "name": "previous",
            "icon": "icons/previous.svg",
            "tooltip": "Previous",
            "status_tip": "Go to previous record/page",
            "callback_name": "go_to_previous"
        },
        {
            "name": "next",
            "icon": "icons/next.svg", 
            "tooltip": "Next",
            "status_tip": "Go to next record/page",
            "callback_name": "go_to_next"
        },
        {
            "name": "prepare_device",
            "icon": "icons/prepare_device.svg",
            "tooltip": "Prepare Device",
            "status_tip": "Initialize and connect device",
            "callback_name": "prepare_device"
        },
        {
            "name": "download_data",
            "icon": "icons/download_data.svg",
            "tooltip": "Download Data",
            "status_tip": "Download data from device",
            "callback_name": "download_data"
        },
        {
            "name": "database",
            "icon": "icons/database.svg",
            "tooltip": "Database",
            "status_tip": "Open patient database",
            "callback_name": "open_database"
        },
        {
            "name": "report_view",
            "icon": "icons/report_view.svg",
            "tooltip": "Report View",
            "status_tip": "View ECG/Sleep reports",
            "callback_name": "open_report_view"
        },
        {
            "name": "signal_view",
            "icon": "icons/signal_view.svg",
            "tooltip": "Signal View",
            "status_tip": "View live physiological signals",
            "callback_name": "open_signal_view"
        },
        {
            "name": "event_list",
            "icon": "icons/event_list.svg",
            "tooltip": "Event List",
            "status_tip": "View detected events",
            "callback_name": "open_event_list"
        },
        {
            "name": "archive",
            "icon": "icons/archive.svg",
            "tooltip": "Archive",
            "status_tip": "Access archived records",
            "callback_name": "open_archive"
        }
    ]


def get_toolbar_qss_styles():
    """
    Get QSS styles for professional toolbar styling
    
    Returns:
        str: QSS styles for toolbar buttons and tooltips
    """
    return """
    /* Toolbar Button Styles */
    QPushButton {
        border: none;
        background-color: transparent;
        border-radius: 6px;
        padding: 4px;
    }

    QPushButton:hover {
        background-color: #E6F0FF;   /* light medical blue */
        border-radius: 6px;
    }

    QPushButton:pressed {
        background-color: #CCE0FF;
    }

    /* Tooltip Styling - Medical Look */
    QToolTip {
        background-color: #2E3A46;
        color: white;
        border: 1px solid #1a2332;
        padding: 6px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: normal;
    }

    /* Toolbar Styles */
    QToolBar {
        background-color: #ffffff;
        border-bottom: 1px solid #e5e7eb;
        spacing: 2px;
        padding: 4px;
    }

    QToolBar::separator {
        background-color: #d1d5db;
        width: 1px;
        margin: 4px 8px;
    }
    """
