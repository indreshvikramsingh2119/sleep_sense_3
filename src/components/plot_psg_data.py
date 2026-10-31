"""Shared signal-name mapping for binary SD recordings."""

from __future__ import annotations


# Dashboard chart label -> canonical signal key.
CHART_SIGNAL_MAPPING = {
    "Body Position": "body_position",
    "Airflow": "airflow",
    "Snoring": "snoring",
    "Thorax": "thorax",
    "Abdomen": "abdomen",
    "SpO2": "spo2",
    "Pulse": "pulse",
    "Body Movement": "body_movement",
}
CHART_ORDER = tuple(CHART_SIGNAL_MAPPING)

BODY_POSITION_CODES = {
    "supine": 0, "left": 1, "right": 2, "prone": 3,
    "upright": 4, "unknown": 5,
}
BODY_POSITION_UNKNOWN = 5
BODY_POSITION_TICKS = [(0, "S"), (1, "L"), (2, "R"), (3, "P"), (4, "U")]
BODY_POSITION_NAMES = ["Supine", "Left", "Right", "Prone", "Upright"]
BODY_POSITION_LABEL_TO_CODE = {
    "s": 0,
    "supine": 0,
    "l": 1, "left": 1,
    "r": 2, "right": 2,
    "p": 3, "prone": 3,
    "u": 4,
    "unknown": 5,
    "upright": 4,
}


# Shared dashboard signal configuration and Y-axis settings.
# Tuple format: (name, color, frequency, amplitude, offset, y_axis_min, y_axis_max)
ACTIVE_SIGNAL_CONFIGS = [
    ("Body Position", "#3b82f6", 0.5, 10, 50, 0, 5),  # Y-axis: 0-5
    ("Airflow", "#8b5cf6", 0.3, 15, 50, 0, 4095),  # Y-axis: 0-4095
    ("Snoring", "#ef4444", 1.0, 8, 50, -50, 50),  # Y-axis: -50-50
    ("Thorax", "#f59e0b", 0.2, 5, 50, 0, 4095),  # Y-axis: 0-4095
    # ("Abdomen", "#10b981", 0.1, 2, 90, 0, 80),  # Y-axis: 0-80
    ("SpO2", "#06b6d4", 1.5, 12, 50, 60, 110),  # Y-axis: 60-110
    ("Pulse", "#f97316", 0.0, 0, 30, 40, 140),  # Y-axis: 40-140
    ("Body Movement", "#8b5cf6", 0.1, 5, 20, 0, 100),  # Y-axis: 0-100
]
ACTIVE_SIGNAL_NAMES = tuple(name for name, *_rest in ACTIVE_SIGNAL_CONFIGS)
SIGNAL_Y_RANGES = {
    name: (y_min, y_max)
    for name, _color, _freq, _amp, _offset, y_min, y_max in ACTIVE_SIGNAL_CONFIGS
}
PLOTTED_SIGNAL_NAMES = set(ACTIVE_SIGNAL_NAMES)
CHANNEL_COLORS = {name: color for name, color, *_rest in ACTIVE_SIGNAL_CONFIGS}
AUTO_RANGE_SIGNAL_NAMES = {"Airflow", "Thorax", "Snoring", "SpO2", "Pulse"}
# Remove a chart name from this set in the future to show its Y-axis values again.
HIDDEN_Y_AXIS_VALUE_CHARTS = {"Airflow", "Snoring", "Thorax", "Body Movement"}
AXIS_MIN_SPAN = {"SpO2": 10.0, "Pulse": 12.0, "Snoring": 20.0}
BIPOLAR_SIGNAL_NAMES = {"Snoring"}
AXIS_HARD_LIMITS = {}
AXIS_ALWAYS_REFIT = set()
AXIS_TOP_HEADROOM = {"SpO2": 0.15}
AXIS_TOP_CEILING = {"SpO2": 100.0}
AUTO_RANGE_OUTLIER_IQR_FACTOR = 3.0
AUTO_RANGE_MIN_KEEP_FRACTION = 0.5

# Smooth auto-scaling settings for Airflow and Thorax.
AXIS_SMOOTH_ENABLED = True
AXIS_SMOOTH_CHARTS = {"Airflow", "Thorax"}
AXIS_SMOOTH_MARGIN = 0.08
AXIS_SMOOTH_NORMAL_REACH = 1.5
AXIS_SMOOTH_TYPICAL_PCT = 50.0
AXIS_SMOOTH_ZOOM_OUT_SEC = 4.0
AXIS_SMOOTH_ZOOM_IN_SEC = 12.0
AXIS_SMOOTH_SHIFT_SEC = 3.0
AXIS_SMOOTH_MIN_HALF = 1.0
# "compress" = fold a big movement into the top/bottom band, "edge" = pin it to the chart
# border, anything else (here "clip") = plain fixed-gain clipping: the trace runs off the
# chart and comes back, which reads as "off scale, signal still alive" and never as a
# flat / absent effort.  Same rule is used while playing and while paused.
AXIS_SMOOTH_OVERFLOW = "clip"
AXIS_SMOOTH_BAND = 0.10
AXIS_SMOOTH_COMPRESS_RANGE = 40.0
AXIS_SMOOTH_FLAT_FRACTION = 0.25
AXIS_SMOOTH_DEAD_FRACTION = 0.10
AXIS_SMOOTH_FLAT_HOLD_SEC = 180.0
AXIS_SMOOTH_REFERENCE_SEC = 60.0
THORAX_DISPLAY_LOWPASS_HZ = 1.0

# Fixed/fallback Y-axis settings for the dashboard charts.
BODY_POSITION_VIEW_MIN = -0.5
BODY_POSITION_VIEW_MAX = 4.5
SPO2_FIXED_AXIS = (60.0, 100.0)
SPO2_ARTIFACT_FLOOR = 0.0
SPO2_LABEL_ROOM_FRACTION = 0.18
PULSE_FIXED_AXIS = (40.0, 140.0)


def signal_key_for_chart(chart_name):
    """Return the canonical signal key for a chart label."""
    cleaned = str(chart_name).strip()
    if cleaned in CHART_SIGNAL_MAPPING:
        return CHART_SIGNAL_MAPPING[cleaned]
    return cleaned.lower().replace(" ", "_")
