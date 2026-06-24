#!/usr/bin/env python3
"""
Unified Signal Mapping Configuration

This module provides a single source of truth for:
- CSV column indices
- Signal display names (for both monitor chart and candidate images)
- Colors (consistent across all visualizations)
- Y-axis ranges (medical/physiological appropriate ranges)
- Display order (for consistent layout)

Used by:
- sleep_monitor_chart.py (real-time monitoring)
- Other visualization modules
"""

from __future__ import annotations

# ============================================================================
# CSV Column Mapping
# ============================================================================
# The raw PSG CSV (human.data.csv) has this structure:
# Column 0: empty
# Column 1: timestamp (milliseconds)
# Column 2: body_position
# Column 3: pulse
# Column 4: spo2
# Column 5: body_movement
# Column 6: airflow
# Column 7: null
# Column 8: snoring
# Column 9-10: null

CSV_COLUMNS = {
    'timestamp': 1,
    'body_position': 2,
    'pulse': 3,
    'spo2': 4,
    'body_movement': 5,
    'airflow': 6,
    'snoring': 8,
}

# ============================================================================
# Signal Display Configuration
# ============================================================================
# Format: {
#     'key': {
#         'display_name': str,          # Label shown in UI
#         'color': str,                 # Hex color for plots
#         'csv_column': int,            # Column index in CSV
#         'y_min': float,               # Medical range minimum
#         'y_max': float,               # Medical range maximum
#         'unit': str,                  # Display unit (optional)
#         'description': str,           # Description for tooltips
#     }
# }

SIGNAL_CONFIG = {
    'airflow': {
        'display_name': 'Airflow',
        'color': '#7c3aed',  # Purple (used in OSA images)
        'csv_column': 6,
        'y_min': -100,
        'y_max': 100,
        'unit': 'arbitrary',
        'description': 'Respiratory airflow signal',
    },
    'spo2': {
        'display_name': 'SpO2',
        'color': '#06b6d4',  # Cyan (used in OSA images)
        'csv_column': 4,
        'y_min': 70,
        'y_max': 100,
        'unit': '%',
        'description': 'Oxygen saturation',
    },
    'pulse': {
        'display_name': 'Pulse',
        'color': '#f97316',  # Orange (used in OSA images)
        'csv_column': 3,
        'y_min': 40,
        'y_max': 130,
        'unit': 'bpm',
        'description': 'Heart rate',
    },
    'body_movement': {
        'display_name': 'Body Movement',
        'color': '#10b981',  # Green (used in OSA images)
        'csv_column': 5,
        'y_min': 0,
        'y_max': 100,
        'unit': 'level',
        'description': 'Body movement activity level',
    },
    'snoring': {
        'display_name': 'Snoring',
        'color': '#ef4444',  # Red (used in OSA images)
        'csv_column': 8,
        'y_min': -40,
        'y_max': 40,
        'unit': 'arbitrary',
        'description': 'Snoring sound intensity',
    },
    'body_position': {
        'display_name': 'Body Position',
        'color': '#3b82f6',  # Blue
        'csv_column': 2,
        'y_min': 0,
        'y_max': 4,
        'unit': 'category',
        'description': 'Patient body position (0=supine, 1=prone, 2=left, 3=right, 4=unknown)',
    },
    'thorax': {
        'display_name': 'Thorax',
        'color': '#f59e0b',  # Amber
        'csv_column': None,  # Not available in CSV
        'y_min': -80,
        'y_max': 80,
        'unit': 'arbitrary',
        'description': 'Chest/thorax respiratory effort (not in this CSV)',
    },
    'abdomen': {
        'display_name': 'Abdomen',
        'color': '#10b981',  # Green
        'csv_column': None,  # Not available in CSV
        'y_min': -80,
        'y_max': 80,
        'unit': 'arbitrary',
        'description': 'Abdominal respiratory effort (not in this CSV)',
    },
}

# ============================================================================
# Display Order
# ============================================================================
# This defines the order signals appear in visualizations

# OSA Candidate Image Order (for respiratory event detection)
OSA_IMAGE_ORDER = [
    'body_position',
    'airflow',
    'snoring',
    'thorax',
    'abdomen',
    'spo2',
    'pulse',
    'body_movement',
]

# Full Monitor Chart Order (includes all available signals)
MONITOR_CHART_ORDER = [
    'body_position',
    'airflow',
    'snoring',
    'thorax',
    'abdomen',
    'spo2',
    'pulse',
    'body_movement',
]

# ============================================================================
# Helper Functions
# ============================================================================

def get_signal_config(signal_key: str) -> dict:
    """Get configuration for a specific signal."""
    if signal_key not in SIGNAL_CONFIG:
        raise ValueError(f"Unknown signal: {signal_key}")
    return SIGNAL_CONFIG[signal_key].copy()


def get_signal_by_column(column_index: int) -> str | None:
    """Get signal key by CSV column index."""
    for key, config in SIGNAL_CONFIG.items():
        if config.get('csv_column') == column_index:
            return key
    return None


def get_display_name(signal_key: str) -> str:
    """Get display name for a signal."""
    return SIGNAL_CONFIG[signal_key]['display_name']


def get_color(signal_key: str) -> str:
    """Get color for a signal."""
    return SIGNAL_CONFIG[signal_key]['color']


def get_y_range(signal_key: str) -> tuple[float, float]:
    """Get Y-axis range for a signal."""
    config = SIGNAL_CONFIG[signal_key]
    return (config['y_min'], config['y_max'])


def get_osa_image_signals() -> list[dict]:
    """Get signals to display in OSA candidate images with their configs."""
    return [
        {
            'key': key,
            **get_signal_config(key),
        }
        for key in OSA_IMAGE_ORDER
    ]


def get_monitor_chart_signals() -> list[dict]:
    """Get signals to display in monitor chart with their configs."""
    return [
        {
            'key': key,
            **get_signal_config(key),
        }
        for key in MONITOR_CHART_ORDER
    ]

    


if __name__ == '__main__':
    # Test the configuration
    print("OSA Image Signals:")
    for sig in get_osa_image_signals():
        print(f"  {sig['display_name']:20} | Color: {sig['color']} | Range: {sig['y_min']}-{sig['y_max']}")
    
    print("\nMonitor Chart Signals:")
    for sig in get_monitor_chart_signals():
        print(f"  {sig['display_name']:20} | Color: {sig['color']} | Range: {sig['y_min']}-{sig['y_max']}")
