


"""
Sleep Monitor Chart Widget - Sleep Monitoring Chart Component
"""

import os
import sys
import json
import math
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from scipy.signal import find_peaks
from src.utils.db_utils import (
    get_db_path,
    save_raw_csv_session,
)
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QMessageBox, QMenu, QAction, QScrollArea, QSizePolicy, QSlider, QFileDialog, QApplication, QDialog, QStyle, QShortcut
)
from PyQt5.QtCore import Qt, QTimer, QTime, QThread, pyqtSignal, QPoint, QRect, QMimeData, QPointF, QElapsedTimer
import sip
from PyQt5.QtGui import QPixmap, QScreen, QKeySequence
from PyQt5.QtGui import QFont, QIcon, QPixmap, QDrag, QPainter, QPen, QColor, QRegion
import pyqtgraph as pg
from .custom_viewbox import CustomViewBox
from .amplitude_axis_properties_dialog import AmplitudeAxisPropertiesDialog
from .airflow_display_processing import enhance_airflow_for_graph_and_detection
from ..utils.report_metrics_calculator import (
    calculate_hypoxic_burden_metrics,
    calculate_sleep_metrics,
    save_sleep_metrics_json,
)
from ..utils.event_labels import canonical_event_label
from ..utils.runtime_config import get_configured_path
from ..utils.dialog_helpers import show_styled_warning

APP_ROOT = Path(__file__).resolve().parents[2]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from .plot_psg_data import (  # noqa: E402
    SAMPLE_RATE_HZ as EXTERNAL_ARRAY_SAMPLE_RATE_HZ,
    CHART_SIGNAL_MAPPING,
    BODY_POSITION_TICKS,
    BODY_POSITION_LABEL_TO_CODE,
    signal_key_for_chart,
)

ACTIVE_SIGNAL_CONFIGS = [
    ("Body Position", "#3b82f6", 0.5, 10, 50, 0, 5),
    ("Airflow", "#8b5cf6", 0.3, 15, 50, 0, 1500),
    ("Snoring", "#ef4444", 1.0, 8, 50, 0, 1000),
    ("Thorax", "#f59e0b", 0.2, 5, 50, 0, 4095),
    # ("Abdomen", "#10b981", 0.1, 2, 90, 0, 80),
    ("SpO2", "#06b6d4", 1.5, 12, 50, 60, 110),
    ("Pulse", "#f97316", 0.0, 0, 30, 40, 140),
    ("Body Movement", "#8b5cf6", 0.1, 5, 20, 0, 100),
]
ACTIVE_SIGNAL_NAMES = tuple(name for name, *_rest in ACTIVE_SIGNAL_CONFIGS)
SIGNAL_Y_RANGES = {
    name: (y_min, y_max)
    for name, _color, _freq, _amp, _offset, y_min, y_max in ACTIVE_SIGNAL_CONFIGS
}
PLOTTED_SIGNAL_NAMES = set(ACTIVE_SIGNAL_NAMES)
CHANNEL_COLORS = {name: color for name, color, *_rest in ACTIVE_SIGNAL_CONFIGS}
AUTO_RANGE_SIGNAL_NAMES = {"Airflow", "Thorax"}
# How far (in IQRs from the median) a sample may sit before it is treated as an
# outlier for Y-axis auto-scaling. Thorax often has a large settling transient
# at the start of a recording. Without trimming, that spike can own the whole
# Y range and make the real breathing waveform look flat on long windows.
AUTO_RANGE_OUTLIER_IQR_FACTOR = 3.0
# Never discard more than this fraction of the samples. If the "outliers" are
# actually the real signal, fall back to the raw data instead.
AUTO_RANGE_MIN_KEEP_FRACTION = 0.5

# --- SpO2 value labels -----------------------------------------------------
# Which selected time windows (in seconds, exactly as the dropdown sets them)
# get SpO2 numbers on the trace. Every other window shows no labels at all.
#   RAW  -> one label per sample, the original 10s reading view
#   AVG  -> the window is split into buckets and each bucket's MEAN is labelled
SPO2_RAW_LABEL_WINDOWS_SEC = (10,)
SPO2_AVG_LABEL_WINDOWS_SEC = (120, 300)
# Safety net: never draw per-sample labels for more points than this.
SPO2_LABEL_MAX_RAW_POINTS = 400
# Roughly how many averaged labels to spread across the plot in AVG mode. The
# real bucket length is snapped to one of the round values below so the label
# grid is a FIXED grid in recording time - that is what makes each number stay
# glued to its own piece of the waveform and scroll right-to-left with it
# during playback, instead of sitting at a fixed screen slot and changing value.
SPO2_LABEL_TARGET_COUNT = 24
SPO2_LABEL_BUCKET_STEPS_SEC = (1, 2, 5, 10, 15, 20, 30, 60)
# Optional: a bucket mean can hide a short desaturation. Set this above 0 to
# also label the bucket's lowest sample when it is that many % below the mean.
# Kept at 0 by default - the extra number sits off the plateau and reads as if
# the label has fallen off the trace. Labels are NEVER drawn below the line.
SPO2_LABEL_MARK_NADIR_DROP = 0.0

# Physiologically possible range per channel. Anything outside is a sensor
# dropout or a probe artifact, NOT a reading - the oximeter writes 0 when it
# has no signal, and plotted as 0 that looks like a fall to 0% SpO2. Values
# outside the range become gaps in the trace instead.
SIGNAL_VALID_RANGES = {
    "spo2": (50.0, 100.0),
    "pulse": (25.0, 250.0),
}
# Channels whose dropouts must NOT be interpolated across. Linear interpolation
# would invent readings the oximeter never took; a blank is the honest display.
SIGNAL_NO_GAP_FILL = ("spo2", "pulse")

# Deleted auto events are matched by geometry, not exact keys, so a small
# parameter change during re-analysis does not resurrect the same event.
DELETED_EVENT_EDGE_TOLERANCE_SEC = 1.0
DELETED_EVENT_MIN_OVERLAP_RATIO = 0.7

AIRFLOW_DROP_MIN_DURATION_SEC = 2.0
AIRFLOW_EVENT_MAX_DURATION_SEC = None
AIRFLOW_BASELINE_MIN_OCCURRENCE = 30

# ---------------------------------------------------------------------------
# PERF: debug logging is opt-in.
#
# The playback path used to emit ~20 print() calls per frame. At a 50 ms timer
# that is ~400 writes/second to stdout; on macOS (Terminal / PyCharm console)
# each write is synchronous and costs 0.1-1 ms, so printing alone could eat
# more time than the actual plotting.
#
# Run with  PSG_DEBUG=1 python dashboard.py  to get the old chatter back.
# ---------------------------------------------------------------------------
PERF_DEBUG = os.environ.get("PSG_DEBUG", "0") not in ("0", "", "false", "False")


def dbg(*args, **kwargs):
    """No-op logger used on the per-frame hot path."""
    if PERF_DEBUG:
        print(*args, **kwargs)

# Playback advances 0.1 s of data per 50 ms tick, i.e. 2x wall-clock at "1.0x".
PLAYBACK_TIME_SCALE = 2.0

DETECTION_IMPORT_ERROR = None
try:
    from ai_models.sleep_apnea.detect_apnea_from_airflow import detect_apnea_events_from_csv
    from ai_models.sleep_apnea import detect_apnea_from_airflow as _apnea_rules
except Exception as import_error:
    detect_apnea_events_from_csv = None
    _apnea_rules = None
    DETECTION_IMPORT_ERROR = str(import_error)

CSV_IMPORT_ERROR = None
try:
    from ai_models.sleep_apnea.hybrid_pipeline_common import CSV_SIGNAL_NAMES, load_sleep_csv
except Exception as import_error:
    CSV_SIGNAL_NAMES = ()
    load_sleep_csv = None
    CSV_IMPORT_ERROR = str(import_error)

class SleepMonitorChart(QWidget):
    """Sleep Monitoring Chart Widget"""
    raw_data_saved = pyqtSignal(str, str)  # file_path, timestamp_iso
    time_position_updated = pyqtSignal()  # Signal when time position changes
    time_window_mode_changed = pyqtSignal(bool)  # True when All PSG mode is active
    apnea_events_updated = pyqtSignal(object)  # list[dict]

    class _SaveWorker(QThread):
        """
        Keep saving in a background thread so the UI does not freeze.
        """
        done = pyqtSignal(int, str, str)  # session_id, saved_at, copied_csv_path
        failed = pyqtSignal(str)  # error message

        def __init__(self, patient_id, source_csv_path, parent_session_id=None, parent=None):
            super().__init__(parent)
            self.patient_id = patient_id
            self.source_csv_path = source_csv_path
            self.parent_session_id = parent_session_id

        def run(self):
            try:
                session_id, saved_at, copied_csv_path = save_raw_csv_session(
                    self.patient_id,
                    self.source_csv_path,
                    parent_session_id=self.parent_session_id,
                )
                self.done.emit(session_id, saved_at, copied_csv_path)
            except Exception as e:
                self.failed.emit(str(e))
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.current_time = QTime.currentTime()
        self.patient_id = "--------"
        self.current_time_window = 60  # Default to 60 seconds
        # When True, a window larger than the remaining recording is shrunk to
        # the data that actually exists so the plot always fills the full width.
        self.fit_window_to_data = True
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
        self.psg_full_data = None  # Store full PSG data for all signals
        self.current_psg_data = None  # Report-friendly full-channel PSG payload
        self.current_time_offset = 0  # Current starting time for window
        self.all_psg_mode = False  # When True, render the entire recording in one view
        self.current_csv_path = None
        self.analysis_results = None
        self.analysis_json_path = None
        self._save_in_progress = False
        self._worker = None
        # Which saved session (if any) is currently loaded, and the root
        # session it belongs to. Set via set_current_session() when a Records
        # row is opened. A Re-analyze -> "New report" save uses
        # current_session_root_id as its parent, so reanalyzed versions of
        # the same recording stay nested under the original in the Records
        # table instead of appearing as unrelated rows.
        self.current_session_id = None
        self.current_session_root_id = None
        
                
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
        self.loaded_csv_path = None
        self.auto_rule_ai_result = None
        self.manual_label_overrides = {}
        self.deleted_auto_event_keys = set()
        self._deleted_span_cache = None
        self._pending_label_change = None
        self.auto_focus_applied = False
        self.skip_next_auto_playback = False
        self.last_detection_error = None
        self.last_click_time = 0  # Debounce duplicate clicks
        self._rendering_selections = False
        self._selection_render_scheduled = False
        
        # PERF: whole-recording caches (see _invalidate_signal_caches)
        self._body_position_cache = None
        self._airflow_axis_range_cache = None
        self._auto_axis_range_cache = {}
        self._last_events_signature = None
        self._last_detection_summary_text = None
        self._playback_busy = False
        self._playback_clock = QElapsedTimer()
        
        # Apnea events storage
        self.apnea_events = []  # Store apnea event data
        self.event_plot_items = {}  # Store plot items for apnea events
        self.airflow_event_items = []  # Store automatic airflow drop event boxes
        self.airflow_detected_events = []  # Full-timeline airflow events for navigation
        self.current_window_airflow_events = []  # Visible-window airflow events fallback
        
        # Timer for detecting selection completion
        self.selection_timer = QTimer(self)
        self.selection_timer.setSingleShot(True)
        self.selection_timer.timeout.connect(self.finish_selection)
        self._keyboard_shortcuts = []
        self.init_ui()
        self.init_charts()
        self._init_keyboard_shortcuts()
        
        # Timer for updating time
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        # Don't start timer initially - wait for user to press play

    def _init_keyboard_shortcuts(self):
        """Register playback and time-navigation keyboard shortcuts."""
        shortcut_specs = (
            (Qt.Key_Space, self.toggle_playback),
            (Qt.Key_Left, self._keyboard_navigate_backward),
            (Qt.Key_Right, self._keyboard_navigate_forward),
        )
        for key, handler in shortcut_specs:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.WidgetWithChildrenShortcut)
            shortcut.activated.connect(handler)
            self._keyboard_shortcuts.append(shortcut)

    def _keyboard_navigate_backward(self):
        if self.is_playing:
            self.pause_playback()
        self.navigate_backward()

    def _keyboard_navigate_forward(self):
        if self.is_playing:
            self.pause_playback()
        self.navigate_forward()

    def _normalize_body_position_signal(self, values):
        """Convert body position data into the canonical 0..4 categorical codes.

        PERF: this used to run a per-sample Python loop over the WHOLE
        recording, and it was called on every playback frame. On a 2h50m file
        that is ~537 ms per frame; on an 8h file ~1.6 s per frame. Both paths
        below are fully vectorised, and the result is cached by
        _get_body_position_signal() so it is computed once per loaded file.
        """
        array = np.asarray(values)
        if array.size == 0:
            return np.asarray([], dtype=float)

        if array.dtype.kind in "iuf":
            # Fast path: the CSV loader already produced numbers.
            numeric = array.astype(float).reshape(-1)
            codes = np.clip(np.rint(numeric), 0, 4)
            codes[~np.isfinite(numeric)] = np.nan
        else:
            # Mixed / label data: still vectorised, no Python loop.
            text = pd.Series(array.reshape(-1)).astype(str).str.strip().str.lower()
            mapped = text.map(BODY_POSITION_LABEL_TO_CODE)
            numeric = pd.to_numeric(text, errors="coerce")
            codes = mapped.astype(float).fillna(numeric).to_numpy(dtype=float)
            codes = np.clip(np.rint(codes), 0, 4)

        series = pd.Series(codes)
        series = series.interpolate(limit_direction="both").ffill().bfill().fillna(4.0)
        return series.to_numpy(dtype=float)

    def _get_body_position_signal(self):
        """Return the normalised body-position channel, computed once per file."""
        cached = getattr(self, "_body_position_cache", None)
        if cached is not None:
            return cached

        signals = (self.psg_full_data or {}).get("signals", {})
        raw = signals.get("body_position")
        if raw is None:
            return np.asarray([], dtype=float)

        cached = self._normalize_body_position_signal(raw)
        self._body_position_cache = cached
        return cached

    def _invalidate_signal_caches(self):
        """Drop every whole-recording derived value. Call this after loading."""
        self._body_position_cache = None
        self._airflow_axis_range_cache = None
        self._auto_axis_range_cache = {}
        self._last_events_signature = None
        self._last_detection_summary_text = None

    def _get_full_signal_for_auto_range(self, chart_name):
        """Return the full-recording array backing an auto-range chart (Airflow/Thorax)."""
        if self.psg_full_data is None or "signals" not in self.psg_full_data:
            return np.array([])

        signals = self.psg_full_data["signals"]
        signal_col = CHART_SIGNAL_MAPPING.get(chart_name)
        if signal_col is None:
            clean_name = str(chart_name).strip().rstrip(")")
            signal_col = signal_key_for_chart(clean_name)

        if signal_col not in signals:
            return np.array([])

        if signal_col == "airflow":
            return self._get_airflow_signal_variant("display")
        if signal_col == "thorax":
            return self._get_thorax_signal_variant("display")
        if signal_col == "body_position":
            return self._get_body_position_signal()
        return np.asarray(signals[signal_col], dtype=float)

    def _configure_body_position_axis(self, plot_widget):
        """Apply categorical ticks so body position is readable on the dashboard."""
        left_axis = plot_widget.getAxis("left")
        try:
            left_axis.setTicks([BODY_POSITION_TICKS])
        except Exception:
            pass
        plot_widget.setYRange(0, 4, padding=0)

    def scroll_chart_container_into_view(self, container):
        """Move the chart scrollbar so the clicked chart comes into view."""
        if hasattr(self, "scroll_area"):
            scrollbar = self.scroll_area.verticalScrollBar()
            target_value = max(0, min(scrollbar.maximum(), int(container.y() - 10)))
            scrollbar.setValue(target_value)

    def _build_body_position_step_data(self, x_data, y_data):
        """Build step-ready x coordinates for categorical body position data."""
        x_data = np.asarray(x_data, dtype=float).reshape(-1)
        y_data = np.asarray(y_data, dtype=float).reshape(-1)
        point_count = min(len(x_data), len(y_data))
        if point_count == 0:
            return np.asarray([]), np.asarray([])

        x_data = x_data[:point_count]
        y_data = y_data[:point_count]
        x_diffs = np.diff(x_data[np.isfinite(x_data)])
        step = float(np.nanmedian(x_diffs)) if len(x_diffs) > 0 else (1.0 / EXTERNAL_ARRAY_SAMPLE_RATE_HZ)
        if not np.isfinite(step) or step <= 0:
            step = 1.0 / EXTERNAL_ARRAY_SAMPLE_RATE_HZ

        step_x = np.append(x_data, x_data[-1] + step)
        return step_x, y_data

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
        chart_layout.setSpacing(4)
        
        # Time labels overlay
        time_overlay = QWidget()
        time_overlay.setFixedHeight(8)
        time_layout = QHBoxLayout(time_overlay)
        time_layout.setContentsMargins(0, 0, 0, 0)
        
        # self.start_time_label = QLabel("Start: ----")
        # self.start_time_label.setObjectName("timeLabelStart")
        # time_layout.addWidget(self.start_time_label)
        # time_layout.addStretch()
        
                
        chart_layout.addWidget(time_overlay)
        
        # Charts container with functional scrollbar only
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("chartsScrollArea")
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
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
                min-height: 24px;
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
        self.charts_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.charts_layout = QVBoxLayout(self.charts_widget)
        self.charts_layout.setContentsMargins(0, 0, 0, 0)
        self.charts_layout.setSpacing(6)
        
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
        self.top_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.bottom_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        
        self.scroll_area.setWidget(self.charts_widget)
        chart_layout.addWidget(self.scroll_area, stretch=1)
        
                
        # Status Bar
        status_bar = self.create_status_bar()
        chart_layout.addWidget(status_bar)
        
        main_layout.addWidget(chart_container)
        
    
    def set_patient_id(self, patient_id: str):
        self.patient_id = patient_id or "--------"

    def set_current_session(self, session_id, parent_session_id=None):
        """Record which saved session is currently loaded."""
        self.current_session_id = session_id
        self.current_session_root_id = parent_session_id or session_id
    
    def set_dashboard_controls(self, time_window_dropdown, hidden_graphs_dropdown):
        """Set reference to dashboard controls for synchronization"""
        self.dashboard_time_window_dropdown = time_window_dropdown
        self.dashboard_hidden_graphs_dropdown = hidden_graphs_dropdown

    def confirm_and_save_raw_data(self):
        """
        Copy the raw CSV and save it.
        """
        if not hasattr(self, "patient_id") or self.patient_id in ("", "--------", None):
            msg_box = QMessageBox(self)
            msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            msg_box.setWindowTitle("No Patient Selected")
            msg_box.setText("Please select a Patient ID before saving.")
            msg_box.setIconPixmap(self._patient_id_icon_pixmap())
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #f8fbff;
                }
                QMessageBox QLabel {
                    color: #111827;
                    font-size: 13px;
                    font-weight: 500;
                }
                QMessageBox QPushButton {
                    min-width: 54px;
                    min-height: 22px;
                    padding: 4px 12px;
                    border-radius: 6px;
                    border: 1px solid #1d4ed8;
                    background-color: #2563eb;
                    color: white;
                    font-size: 11px;
                    font-weight: 700;
                }
                QMessageBox QPushButton:hover {
                    background-color: #3b82f6;
                    border: 1px solid #1e40af;
                }
                QMessageBox QPushButton:pressed {
                    background-color: #1e40af;
                    border: 1px solid #1e3a8a;
                }
            """)
            ok_button = msg_box.button(QMessageBox.Ok)
            if ok_button is not None:
                ok_button.setAutoDefault(False)
                ok_button.setDefault(True)
                ok_button.setStyleSheet("""
                    QPushButton {
                        min-width: 54px;
                        min-height: 22px;
                        padding: 4px 12px;
                        border-radius: 6px;
                        border: 1px solid #1d4ed8;
                        background-color: #2563eb;
                        color: white;
                        font-size: 11px;
                        font-weight: 700;
                    }
                    QPushButton:hover {
                        background-color: #3b82f6;
                        border: 1px solid #1e40af;
                    }
                    QPushButton:pressed {
                        background-color: #1e40af;
                        border: 1px solid #1e3a8a;
                    }
                """)
            msg_box.exec_()
            return

        if not getattr(self, "loaded_csv_path", None):
            QMessageBox.warning(
                self,
                "No CSV Loaded",
                "Please upload a CSV/TXT file before saving raw data.",
            )
            return

        if getattr(self, "_save_in_progress", False):
            QMessageBox.information(self, "Please Wait",
                                    "Previous save is still running...")
            return
        
        msg_box = QMessageBox(self)
        msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        msg_box.setWindowTitle("Confirm Save")
        msg_box.setText(f"Save raw data for patient {self.patient_id}?")
        msg_box.setIconPixmap(self.style().standardIcon(QStyle.SP_DialogSaveButton).pixmap(48, 48))
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.No)
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #f8fbff;
            }
            QMessageBox QLabel {
                color: #1e3a5f;
                font-size: 13px;
                font-weight: 600;
            }
            QMessageBox QPushButton {
                min-width: 86px;
                min-height: 32px;
                padding: 6px 16px;
                border-radius: 8px;
                border: 1px solid #1d4ed8;
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #3b82f6,
                    stop: 0.5 #2563eb,
                    stop: 1 #1d4ed8
                );
                color: white;
                font-weight: 700;
                font-size: 12px;
            }
            QMessageBox QPushButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #60a5fa,
                    stop: 0.5 #3b82f6,
                    stop: 1 #2563eb
                );
            }
            QMessageBox QPushButton:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #1d4ed8,
                    stop: 0.5 #1e40af,
                    stop: 1 #1e3a8a
                );
            }
        """)

        yes_button = msg_box.button(QMessageBox.Yes)
        no_button = msg_box.button(QMessageBox.No)
        if yes_button is not None:
            yes_button.setText("Yes")
            yes_button.setMinimumSize(44, 18)
            yes_button.setAutoDefault(False)
            yes_button.setDefault(False)
            yes_button.setStyleSheet("""
                QPushButton {
                    min-width: 44px;
                    min-height: 18px;
                    padding: 3px 10px;
                    border-radius: 6px;
                    border: 1px solid #1d4ed8;
                    background-color: #2563eb;
                    color: white;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #3b82f6;
                    border: 1px solid #1e40af;
                }
                QPushButton:pressed {
                    background-color: #1e40af;
                    border: 1px solid #1e3a8a;
                }
            """)
        if no_button is not None:
            no_button.setText("No")
            no_button.setMinimumSize(44, 18)
            no_button.setAutoDefault(False)
            no_button.setDefault(True)
            no_button.setStyleSheet("""
                QPushButton {
                    min-width: 44px;
                    min-height: 18px;
                    padding: 3px 10px;
                    border-radius: 6px;
                    border: 1px solid #cbd5e1;
                    background-color: #f8fafc;
                    color: #1e3a5f;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #e2e8f0;
                    border: 1px solid #94a3b8;
                }
                QPushButton:pressed {
                    background-color: #cbd5e1;
                    border: 1px solid #64748b;
                }
            """)

        if msg_box.exec_() == QMessageBox.Yes:
            self._do_save_async()
    
    def take_screenshot(self):
        """Take a screenshot of the sleep monitor chart, or delegate to the dashboard flow."""
        try:
            parent_window = self.window()
            if parent_window is not None and parent_window is not self and hasattr(parent_window, "take_screenshot"):
                parent_window.take_screenshot()
                return

            if not getattr(self, "loaded_csv_path", None):
                show_styled_warning(
                    self,
                    "No Data Uploaded",
                    "Please upload the data first before taking a screenshot.",
                )
                return

            self.repaint()
            QApplication.processEvents()

            from datetime import datetime
            source_pixmap = self.grab()
            if source_pixmap.isNull():
                raise RuntimeError("Could not capture the chart area.")

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sleep_monitor_screenshot_{timestamp}.png"
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Screenshot",
                filename,
                "PNG Files (*.png);;All Files (*)"
            )

            if file_path and not source_pixmap.save(file_path, "PNG"):
                raise RuntimeError("Failed to save screenshot image.")
            if file_path:
                QMessageBox.information(self, "Screenshot Saved", f"Screenshot saved to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Screenshot Error", 
                               f"Failed to take screenshot:\n{str(e)}")

    def _do_save_async(self):
        """
        SQLite me patient/time save hota hai aur uploaded raw CSV copy hoti hai.
        """
        self._save_in_progress = True

        self._worker = self._SaveWorker(
            self.patient_id,
            self.loaded_csv_path,
            parent_session_id=self.current_session_root_id,
            parent=self,
        )
        self._worker.done.connect(self._on_save_done)
        self._worker.failed.connect(self._on_save_failed)
        self._worker.start()

    def _on_save_done(self, session_id: int, saved_at: str, copied_csv_path: str):
        self._save_in_progress = False
        # Remember this save as the currently-loaded session. The first save
        # in a chain (no root yet) becomes the root that later re-analyzed
        # saves of the same recording will nest under.
        self.current_session_id = session_id
        if not self.current_session_root_id:
            self.current_session_root_id = session_id
        # Keep whatever manual events exist on this recording right now
        # attached to the archived copy, so reopening that saved session
        # later still shows them - even though the live session's view
        # gets reloaded right after this (this save flow is exclusively
        # used by Re-analyze -> "New report" - see button_functions.py).
        self._archive_manual_label_overrides_snapshot(copied_csv_path)

        # Reload the original sidecar from disk and re-apply the current
        # overlays. This keeps the original recording's persisted manual
        # state intact instead of replacing it with an empty in-memory
        # version that could later be written back to disk.
        self._load_manual_label_overrides()
        self._refresh_auto_rule_ai_views()
        label = f"Session #{session_id} - {self.patient_id}"
        self.raw_data_saved.emit(copied_csv_path, saved_at)
        db_path = get_db_path()
        msg_box = QMessageBox(self)
        msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        msg_box.setWindowTitle("Saved")
        msg_box.setTextFormat(Qt.RichText)
        msg_box.setIconPixmap(self.style().standardIcon(QStyle.SP_DialogApplyButton).pixmap(48, 48))
        msg_box.setText(
            '<span style="color:#16a34a; font-weight:700;">Data saved successfully!</span><br><br>'
            f'<span style="color:#111827; font-weight:700;">Patient</span>'
            f'<span style="color:#6b7280;"> : {self.patient_id}</span><br>'
            f'<span style="color:#111827; font-weight:700;">Session</span>'
            f'<span style="color:#6b7280;"> : #{session_id}</span><br>'
            f'<span style="color:#111827; font-weight:700;">Time</span>'
            f'<span style="color:#6b7280;"> : {saved_at}</span><br><br>'
            f'<span style="color:#111827; font-weight:700;">Database</span>'
            f'<span style="color:#6b7280;"> : {db_path}</span><br>'
            f'<span style="color:#111827; font-weight:700;">CSV copy</span>'
            f'<span style="color:#6b7280;"> : {copied_csv_path}</span>'
        )
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #f8fbff;
            }
            QMessageBox QLabel {
                color: #111827;
                font-size: 13px;
                font-weight: 500;
            }
            QMessageBox QPushButton {
                min-width: 44px;
                min-height: 18px;
                padding: 3px 10px;
                border-radius: 6px;
                border: 1px solid #1d4ed8;
                background-color: #2563eb;
                color: white;
                font-size: 11px;
                font-weight: 700;
            }
            QMessageBox QPushButton:hover {
                background-color: #3b82f6;
                border: 1px solid #1e40af;
            }
            QMessageBox QPushButton:pressed {
                background-color: #1e40af;
                border: 1px solid #1e3a8a;
            }
        """)
        ok_button = msg_box.button(QMessageBox.Ok)
        if ok_button is not None:
            ok_button.setMinimumSize(54, 22)
            ok_button.setAutoDefault(False)
            ok_button.setDefault(True)
            ok_button.setStyleSheet("""
                QPushButton {
                    min-width: 54px;
                    min-height: 22px;
                    padding: 4px 12px;
                    border-radius: 6px;
                    border: 1px solid #1d4ed8;
                    background-color: #2563eb;
                    color: white;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background-color: #3b82f6;
                    border: 1px solid #1e40af;
                }
                QPushButton:pressed {
                    background-color: #1e40af;
                    border: 1px solid #1e3a8a;
                }
            """)
        msg_box.exec_()

    def _on_save_failed(self, error_msg: str):
        self._save_in_progress = False
        QMessageBox.critical(self, "Save Failed", f"Could not save data:\n{error_msg}")

    def _archive_manual_label_overrides_snapshot(self, copied_csv_path: str) -> None:
        """Copy the current manual-label overrides next to an archived CSV copy.

        Manual events live in a sidecar "<csv-name>_manual_labels.json" file
        next to whichever CSV is loaded (see _manual_label_overrides_path()).
        A Re-analyze -> "New report" save archives a *copy* of the CSV under
        a new file name, and then clears the live session's manual overrides
        so the new analysis starts clean. Without this, that clear would
        wipe out the manual events for good, since the archived copy would
        have no overrides file of its own to fall back on. Writing a copy of
        the current overrides here means: reopen the archived recording
        later and its manual events are exactly as they were.
        """
        manual_selections = self._collect_manual_selections_for_save()
        deleted_auto_events = self._collect_deleted_auto_events_for_save()
        # A recording whose only manual change is "user removed some
        # auto-detected events" still has state worth archiving.
        if (
            not self.manual_label_overrides
            and not manual_selections
            and not deleted_auto_events
        ):
            return
        try:
            dest_overrides_path = Path(copied_csv_path).with_name(
                f"{Path(copied_csv_path).stem}_manual_labels.json"
            )
            dest_overrides_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "label_overrides": self.manual_label_overrides,
                "manual_selections": manual_selections,
                "deleted_auto_events": deleted_auto_events,
            }
            dest_overrides_path.write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
        except Exception as error:
            print(f"⚠️ Could not archive manual label overrides for the saved copy: {error}")

    def _patient_id_icon_pixmap(self):
        """Create a blue patient-ID style icon for warning dialogs."""
        pixmap = QPixmap(48, 48)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#3b82f6"))
        painter.drawRoundedRect(6, 6, 36, 36, 10, 10)

        painter.setBrush(QColor("white"))
        painter.drawRoundedRect(13, 11, 22, 26, 4, 4)
        painter.setBrush(QColor("#3b82f6"))
        painter.drawEllipse(19, 15, 10, 10)
        painter.drawRect(17, 27, 14, 2)
        painter.drawRect(17, 31, 14, 2)
        painter.end()
        return pixmap

    def on_time_window_changed(self, index):
        """Handle time window dropdown change"""
        # Use dashboard controls if available, otherwise use local controls
        dropdown = getattr(self, 'dashboard_time_window_dropdown', None) or getattr(self, 'time_window_dropdown', None)
        if dropdown:
            # Get the value from dropdown item data
            seconds = dropdown.itemData(index)
            print(f"Debug: on_time_window_changed called with index {index}, seconds {seconds}")
            self.set_time_window(seconds)

    def _get_playback_sample_count(self):
        """Return sample count from the loaded timeline, regardless of signal source."""
        if not self.psg_full_data or "time" not in self.psg_full_data:
            return 0

        time_values = np.asarray(self.psg_full_data.get("time", []))
        if len(time_values) > 0:
            return len(time_values)

        signals = self.psg_full_data.get("signals", {})
        for values in signals.values():
            signal_values = np.asarray(values)
            if len(signal_values) > 0:
                return len(signal_values)

        return 0

    def _get_playback_max_duration(self):
        """Return playback duration in seconds for any loaded dataset."""
        sample_count = self._get_playback_sample_count()
        if sample_count <= 0:
            return 0.0
        return sample_count / float(EXTERNAL_ARRAY_SAMPLE_RATE_HZ)

    def _get_playback_max_offset(self):
        """Return the last offset that still keeps the final window visible on screen."""
        max_duration = self._get_playback_max_duration()
        if max_duration <= 0:
            return 0.0
        return max(0.0, max_duration - float(self.current_time_window))

    def is_all_psg_mode(self):
        """Return True when the chart is showing the full PSG recording."""
        return bool(getattr(self, "all_psg_mode", False))

    def get_effective_time_window_seconds(self):
        """Return a positive visible window size for plotting and navigation.

        The visible window is never allowed to run past the end of the loaded
        recording. If the user picks a 1 hour window but only 20 minutes of
        data exist, the x-axis is shrunk to those 20 minutes so the signal
        fills the full width of the plot instead of leaving empty space.
        """
        max_duration = self._get_playback_max_duration()

        if self.is_all_psg_mode() or float(self.current_time_window) <= 0:
            if max_duration > 0:
                return max(1.0, float(max_duration))
        try:
            window = max(1.0, float(self.current_time_window))
        except Exception:
            window = 60.0

        # Fit the window to the data that is actually available from the
        # current offset onwards (no trailing blank area on the chart).
        if getattr(self, "fit_window_to_data", True) and max_duration > 0:
            try:
                offset = max(0.0, float(self.current_time_offset))
            except Exception:
                offset = 0.0
            remaining = float(max_duration) - offset
            if remaining > 0:
                window = min(window, remaining)

        return max(1.0, float(window))

    def navigate_backward(self):
        """Navigate backward in time"""
        if self.block_if_selection_active():
            return
        
        max_duration = self._get_playback_max_duration()
        if max_duration > 0:
            # Calculate maximum possible time based on data length
            # Move back by the current time window
            self.current_time_offset = max(0, self.current_time_offset - self.current_time_window)
            self.refresh_charts()
            self.update_time_position_label()
            dbg(f"Navigated backward to: {self.current_time_offset}s (max: {max_duration:.1f}s)")
    
    def navigate_forward(self):
        """Navigate forward in time"""
        if self.block_if_selection_active():
            return
        
        max_duration = self._get_playback_max_duration()
        if max_duration > 0:
            max_offset = self._get_playback_max_offset()
            new_offset = self.current_time_offset + self.current_time_window
            self.current_time_offset = min(max_offset, new_offset)
            self.refresh_charts()
            self.update_time_position_label()
            dbg(f"Navigated forward to: {self.current_time_offset}s (max: {max_duration:.1f}s, max_offset: {max_offset:.1f}s)")
    
    def start_playback(self):
        """Start movie-like playback of recorded data"""
        sample_count = self._get_playback_sample_count()
        dbg(f"🎬 start_playback called - active sample count: {sample_count}")
        
        if self.block_if_selection_active():
            dbg("🎬 Blocked by selection active")
            return
        
        if sample_count == 0:
            dbg("No data available for playback")
            return

        self.current_time_offset = min(self.current_time_offset, self._get_playback_max_offset())
        
        self.is_playing = True
        self._playback_busy = False
        self._playback_clock.start()
        dbg(f"🎬 Timer starting... is_playing: {self.is_playing}")
        self.playback_timer.start(50)  
        dbg(f"🎬 Timer started - Timer active: {self.playback_timer.isActive()}")
        dbg("▶️ Playback started")
        
        # Update button if it exists
        if self.play_pause_btn:
            self.play_pause_btn.setText("⏸ Pause")
    
    def pause_playback(self):
        """Pause the playback"""
        self.is_playing = False
        self._playback_busy = False
        self._playback_clock.invalidate()
        self.playback_timer.stop()
        dbg("⏸ Playback paused")
        
        # Update button if it exists
        if self.play_pause_btn:
            self.play_pause_btn.setText("▶ Play")
    
    def update_playback(self):
        """Main playback logic - auto-scroll data like a movie.

        PERF, two changes:

        1. Re-entrancy guard. The timer fires every 50 ms. If one frame takes
           longer than that, Qt keeps queueing timeouts and the event loop can
           never catch up - that is what "hang" looks like to the user. We now
           drop a tick instead of stacking it.
        2. Wall-clock stepping. The offset advances by the time that actually
           elapsed, not by a fixed 0.1 s per tick. Playback therefore keeps the
           correct speed on a slow machine (it drops frames) instead of
           silently running in slow motion.
        """
        if not self.is_playing:
            return
        if self._playback_busy:
            return

        self._playback_busy = True
        try:
            max_time = self._get_playback_max_duration()
            if max_time <= 0:
                self.pause_playback()
                return

            max_offset = self._get_playback_max_offset()

            # Move forward by the real elapsed time, scaled to keep the old feel.
            if self._playback_clock.isValid():
                elapsed_sec = self._playback_clock.restart() / 1000.0
            else:
                self._playback_clock.start()
                elapsed_sec = 0.05
            # Guard against a huge jump after the app was blocked/minimised.
            elapsed_sec = min(elapsed_sec, 0.5)
            self.current_time_offset += elapsed_sec * PLAYBACK_TIME_SCALE * self.playback_speed

            # Stop on the last full visible window instead of sliding past the final samples.
            if self.current_time_offset >= max_offset:
                self.current_time_offset = max_offset
                self.refresh_charts()
                self.update_time_position_label()
                self.pause_playback()
                dbg(f"🎬 Playback completed: offset={max_offset:.1f}s, duration={max_time:.1f}s")
                return

            self.refresh_charts()
            self.update_time_position_label()
        finally:
            self._playback_busy = False
    
    def toggle_playback(self):
        """Toggle between play and pause states"""
        if self.is_playing:
            self.pause_playback()
        else:
            self.start_playback()
    
    def change_playback_speed(self, speed_value):
        """Change playback speed from the slider or a legacy text value."""
        speed_map = {
            "0.5x": 0.5,
            "1.0x": 1.0,
            "2.0x": 2.0,
            "4.0x": 4.0,
        }

        if isinstance(speed_value, (int, float)):
            self.playback_speed = float(speed_value) / 2.0
        else:
            self.playback_speed = speed_map.get(str(speed_value), 1.0)
            if hasattr(self, "slider_speed"):
                target_value = int(round(self.playback_speed * 2.0))
                if self.slider_speed.value() != target_value:
                    self.slider_speed.blockSignals(True)
                    self.slider_speed.setValue(target_value)
                    self.slider_speed.blockSignals(False)

        if hasattr(self, "lbl_speed_val"):
            self.lbl_speed_val.setText(f"{self.playback_speed:.1f}x")

        print(f"?? Playback speed changed to {self.playback_speed}x")
    
    def update_time_position_label(self):
        """Show the visible time range and the complete recording duration."""
        total_duration = self._get_playback_max_duration()
        def format_time(value):
            hours = int(value // 3600)
            minutes = int((value % 3600) // 60)
            seconds = int(value % 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        visible_end = min(
            self.current_time_offset + self.current_time_window,
            total_duration,
        )
        displayed_time = (
            total_duration
            if visible_end >= total_duration
            else self.current_time_offset
        )
        self.time_position_label.setText(format_time(displayed_time))
        
        # Emit signal to update dashboard slider
        self.time_position_updated.emit()
    
    def refresh_charts_minimal(self):
        """Refresh charts during playback without overlay rendering to prevent crashes"""
        window_seconds = self.get_effective_time_window_seconds()
        dbg(f"Debug: refresh_charts_minimal called with time_window={window_seconds}s, offset={self.current_time_offset}s")
        
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            if container and hasattr(container, 'plot_widget'):
                plot_widget = container.plot_widget
                chart_name = plot_widget.chart_name
                container.setVisible(True)
                
                # Update time window limits on CustomViewBox to fixed range
                vb = plot_widget.getViewBox()
                if hasattr(vb, 'set_time_window_limits'):
                    vb.set_time_window_limits(0, window_seconds)
                    dbg(f"Debug: ViewBox limits set to 0 → {window_seconds}, offset={self.current_time_offset}")
                
                # Force X-axis range to be fixed (prevent any sliding)
                plot_widget.setXRange(0, window_seconds, padding=0)
                
                # Update bottom axis to show correct time ticks for new window
                bottom_axis = plot_widget.getAxis('bottom')
                bottom_axis.setRange(0, window_seconds)
                
                # Double-enforce X-axis range to prevent any sliding
                vb = plot_widget.getViewBox()
                if hasattr(vb, 'setLimits'):
                    vb.setLimits(xMin=0, xMax=window_seconds, 
                                yMin=None, yMax=None)

    def _apply_all_psg_mode_range_fixup(self, plot_widget, vb, x, window_seconds):
        """Clamp all-PSG charts to the last finite sample on every axis."""
        finite_x = x[np.isfinite(x)] if len(x) else np.array([])
        plot_end = float(finite_x[-1]) if len(finite_x) > 0 else float(window_seconds)
        plot_widget.setXRange(0, plot_end, padding=0)
        bottom_axis = plot_widget.getAxis('bottom')
        bottom_axis.setRange(0, plot_end)
        if hasattr(vb, 'set_time_window_limits'):
            vb.set_time_window_limits(0, plot_end)
        if hasattr(vb, 'setRange'):
            try:
                vb.setRange(x=[0, plot_end], padding=0)
            except Exception:
                plot_widget.setXRange(0, plot_end, padding=0)
        plot_widget.fixed_range = [0, plot_end]

    def refresh_charts(self):
        """Refresh all charts with current time window and offset."""
        window_seconds = self.get_effective_time_window_seconds()
        dbg(f"Debug: refresh_charts called with time_window={window_seconds}s, offset={self.current_time_offset}s")

        self.setUpdatesEnabled(False)
        try:
            for i in range(self.charts_layout.count()):
                container = self.charts_layout.itemAt(i).widget()
                if not (container and hasattr(container, 'plot_widget')):
                    continue

                try:
                    plot_widget = container.plot_widget
                    chart_name = plot_widget.chart_name

                    vb = plot_widget.getViewBox()
                    if hasattr(vb, 'set_time_window_limits'):
                        vb.set_time_window_limits(0, window_seconds)
                        dbg(f"Debug: ViewBox limits set to 0 -> {window_seconds}, offset={self.current_time_offset}")

                    # Store current Y-axis range to preserve zoom settings
                    if not hasattr(plot_widget, 'zoom_y_range'):
                        plot_widget.zoom_y_range = None

                    self.remove_stale_plot_curves(plot_widget)

                    if not self.is_all_psg_mode():
                        plot_widget.setXRange(0, window_seconds, padding=0)
                        bottom_axis = plot_widget.getAxis('bottom')
                        bottom_axis.setRange(0, window_seconds)

                        if hasattr(vb, 'setRange'):
                            try:
                                # Force the exact range with no padding
                                vb.setRange(x=[0, window_seconds], padding=0)
                            except Exception:
                                plot_widget.setXRange(0, window_seconds, padding=0)

                        plot_widget.fixed_range = [0, window_seconds]

                    if chart_name.strip() == "SpO2":
                        x, y = self.get_spo2_data_for_window(window_seconds, self.current_time_offset)
                        if len(x) > 0 and len(y) > 0:
                            # Update normal line plot
                            plot_widget.plot_curve.setData(x, y, connect='finite')
                            plot_widget.plot_curve.opts['fill'] = None

                            if self.is_all_psg_mode():
                                self._apply_all_psg_mode_range_fixup(plot_widget, vb, x, window_seconds)

                            if hasattr(plot_widget, 'axis_properties'):
                                properties = plot_widget.axis_properties
                                low_value = properties.get('low_value', 35.0)
                                high_value = properties.get('high_value', 100.0)
                                finite_spo2 = y[np.isfinite(y)]
                                has_zero_dropout = bool(
                                    finite_spo2.size and np.nanmin(finite_spo2) <= 0.0
                                )
                                if has_zero_dropout:
                                    low_value = 0.0
                                    high_value = max(float(high_value), 100.0)
                                try:
                                    plot_widget.setYRange(low_value, high_value, padding=0)
                                except TypeError:
                                    plot_widget.setRange(yRange=[low_value, high_value], padding=0)
                                if has_zero_dropout:
                                    try:
                                        plot_widget.setLimits(yMin=0.0, yMax=high_value)
                                    except TypeError:
                                        plot_widget.setLimits(yMin=0.0, yMax=high_value)
                            else:
                                self._apply_dropout_axis(plot_widget, "SpO2", y)

                            # Labels on every window - raw samples on short ones,
                            # bucket averages on long ones.
                            dbg(f"Creating/Updating SpO2 value labels for {window_seconds}s time window")
                            self.create_spo2_markers_and_labels(plot_widget, x, y)
                            dbg(f"Updated SpO2 value labels with {len(x)} points for time offset {self.current_time_offset}s")
                        else:
                            plot_widget.plot_curve.setData([], [])
                            # The curve is empty here, but SpO2 labels are
                            # separate TextItems. Clearing them here keeps the
                            # previous recording's numbers from staying painted
                            # over a file that has no SpO2 channel.
                            self.create_spo2_markers_and_labels(plot_widget, [], [])
                    else:
                        x, y = self.get_signal_data_for_window(chart_name, window_seconds, self.current_time_offset)
                        
                        if len(x) > 0 and len(y) > 0:
                            if self.is_all_psg_mode():
                                self._apply_all_psg_mode_range_fixup(plot_widget, vb, x, window_seconds)
                            # Use real data from CSV
                            if chart_name.strip() == "Body Position":
                                self._configure_body_position_axis(plot_widget)
                                x_step, y_step = self._build_body_position_step_data(x, y)
                                plot_widget.plot_curve.setData(x_step, y_step, connect='finite', stepMode=True)
                            else:
                                plot_widget.plot_curve.setData(x, y, connect='finite')
                            dbg(f"Updated {chart_name} with real data: {len(x)} points")
                        else:
                            plot_widget.plot_curve.setData([], [])
                            dbg(f"Left {chart_name} blank because no active signal data is mapped")

                        if hasattr(plot_widget, 'axis_properties'):
                            properties = plot_widget.axis_properties
                            low_value = properties.get('low_value', 35.0)
                            high_value = properties.get('high_value', 100.0)
                            try:
                                plot_widget.setYRange(low_value, high_value, padding=0)
                            except TypeError:
                                plot_widget.setRange(yRange=[low_value, high_value], padding=0)
                        elif chart_name.strip() == "Pulse":
                            self._apply_dropout_axis(plot_widget, "Pulse", y)
                        elif chart_name.strip() == "Airflow":
                            self._apply_windowed_auto_axis(plot_widget, chart_name.strip(), y)
                            _event_x, detection_y = self.get_airflow_detection_data_for_window(
                                window_seconds,
                                self.current_time_offset,
                            )
                            self.mark_airflow_drop_events(
                                plot_widget,
                                x,
                                y,
                                detection_y_data=detection_y,
                            )
                        elif chart_name.strip() == "Thorax":
                            self._apply_windowed_auto_axis(plot_widget, chart_name.strip(), y)
                        elif chart_name.strip() in AUTO_RANGE_SIGNAL_NAMES:
                            auto_y_min, auto_y_max = self.get_signal_auto_axis_range(
                                chart_name.strip()
                            )
                            hard_min, hard_max = self._finite_min_max(y)
                            self._lock_auto_axis(
                                plot_widget, auto_y_min, auto_y_max, hard_min, hard_max
                            )
                except Exception as chart_error:
                    dbg(f"⚠️ {chart_name if 'chart_name' in locals() else 'unknown chart'} refresh failed: {chart_error}")
                    continue

            self.render_dynamic_selections()
            self.update_apnea_events_display()
        finally:
            self.setUpdatesEnabled(True)
            self.update()

    def remove_stale_plot_curves(self, plot_widget):
        """Keep only the primary signal curve so refreshes cannot leave duplicate traces."""
        primary_curve = getattr(plot_widget, "plot_curve", None)
        try:
            for data_item in list(plot_widget.listDataItems()):
                if primary_curve is not None and data_item is primary_curve:
                    continue
                plot_widget.removeItem(data_item)
        except Exception:
            pass
    
    def set_time_window(self, seconds):
        """Set the time window for the sleep monitoring chart (legacy method for compatibility)"""
        print(f"🔍 DEBUG: set_time_window({seconds}) called in sleep_monitor_chart.py")
        previous_window = self.get_effective_time_window_seconds()
        previous_visible_end = self.current_time_offset + previous_window
        # Normalize "All PSG" into a real duration so the plot never receives a negative range.
        self.all_psg_mode = float(seconds) <= 0 if seconds is not None else False
        if self.all_psg_mode:
            effective_window = self._get_playback_max_duration()
            self.current_time_window = max(1.0, float(effective_window) if effective_window > 0 else 60.0)
            self.current_time_offset = 0
        else:
            self.current_time_window = seconds
            max_duration = self._get_playback_max_duration()
            if max_duration > 0:
                max_offset = self._get_playback_max_offset()
                # Keep the visible window anchored to the same right-edge timestamp
                # so switching from 1h -> 10m still shows the last 10 minutes when
                # the slider is already at the end.
                desired_offset = max(0.0, previous_visible_end - float(self.current_time_window))
                self.current_time_offset = min(max_offset, desired_offset)
        
        # Changing the time window means a different stretch of signal, with a
        # different amplitude - so any held zoom/axis state from the previous
        # window is stale.
        for chart_index in range(self.charts_layout.count()):
            chart_container = self.charts_layout.itemAt(chart_index).widget()
            if chart_container is None or not hasattr(chart_container, "plot_widget"):
                continue
            chart_container.plot_widget.zoom_y_range = None
            chart_container.plot_widget.stable_y_range = None

        # Use dashboard controls if available, otherwise use local controls
        dropdown = getattr(self, 'dashboard_time_window_dropdown', None) or getattr(self, 'time_window_dropdown', None)
        if dropdown:
            # Block signals to prevent recursive calls when setting dropdown index
            dropdown.blockSignals(True)
            # Find matching dropdown item and set it
            for i in range(dropdown.count()):
                if dropdown.itemData(i) == seconds:
                    dropdown.setCurrentIndex(i)
                    break
            dropdown.blockSignals(False)
            
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

            # Keep dashboard slider and time label in sync with the new window.
            self.update_time_position_label()
            self.time_window_mode_changed.emit(self.is_all_psg_mode())
            
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
        # Adjust frequency based on time window (longer window = lower frequency for visibility)
        frequency_factor = max(0.1, 10.0 / (seconds / 10.0))
        
        for position, (name, color, base_freq, amp, offset, y_min, y_max) in enumerate(ACTIVE_SIGNAL_CONFIGS):
            adjusted_freq = base_freq * frequency_factor
            chart = self.create_signal_chart(name, color, adjusted_freq, amp, offset, y_min, y_max)
            self.charts_layout.addWidget(chart, stretch=1)
          
            self.graph_order.append(name)
        
            
    def create_status_bar(self):
        """Create bottom playback bar with sectioned controls."""
        frame = QFrame()
        frame.setObjectName("statusBar")
        frame.setMinimumHeight(56)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 4, 16, 4)
        layout.setSpacing(0)

        controls_container = QFrame()
        controls_container.setObjectName("playbackControlsContainer")
        controls_container.setMinimumHeight(44)
        controls_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        controls_container.setStyleSheet("""
            QFrame#playbackControlsContainer {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                padding: 2px;
            }
        """)

        controls_layout = QHBoxLayout(controls_container)
        controls_layout.setContentsMargins(8, 3, 8, 3)
        controls_layout.setSpacing(0)
        controls_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        section_title_style = "font-size: 10px; color: #374151; font-weight: 700; letter-spacing: 1px;"

        self.lbl_pos_title = QLabel("POSITION")
        self.lbl_pos_title.setStyleSheet(section_title_style)
        controls_layout.addWidget(self.lbl_pos_title)
        controls_layout.addSpacing(10)

        self.time_position_label = QLabel("00:00:00")
        self.time_position_label.setObjectName("timePositionLabel")
        self.time_position_label.setFixedHeight(21)
        self.time_position_label.setFixedWidth(84)
        self.time_position_label.setStyleSheet("""
            QLabel#timePositionLabel {
                background-color: #f8fafc;
                color: #374151;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 1px 5px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: 700;
                font-size: 10px;
            }
        """)
        controls_layout.addWidget(self.time_position_label)
        controls_layout.addSpacing(10)

        self.play_pause_btn = QPushButton(" Play")
        self.play_pause_btn.setObjectName("playbackPlayButton")
        self.play_pause_btn.clicked.connect(self.toggle_playback)
        self.play_pause_btn.setFixedHeight(23)
        self.play_pause_btn.setCursor(Qt.PointingHandCursor)
        self.play_pause_btn.setStyleSheet("""
            QPushButton#playbackPlayButton {
                background-color: #2563eb;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: 500;
                min-width: 80px;
            }
            QPushButton#playbackPlayButton:hover { background-color: #1d4ed8; }
            QPushButton#playbackPlayButton:pressed { background-color: #1e40af; }
        """)
        
        # Add all controls to container
        controls_layout.addWidget(self.play_pause_btn)
        
        controls_layout.addWidget(self._divider())

        self.lbl_speed_title = QLabel("SPEED")
        self.lbl_speed_title.setStyleSheet(section_title_style)
        controls_layout.addWidget(self.lbl_speed_title)
        controls_layout.addSpacing(10)

        self.slider_speed = QSlider(Qt.Horizontal)
        self.slider_speed.setObjectName("speedSlider")
        self.slider_speed.setMinimum(1)
        self.slider_speed.setMaximum(8)
        self.slider_speed.setValue(2)
        self.slider_speed.setFixedWidth(84)
        self.slider_speed.setCursor(Qt.PointingHandCursor)
        self.slider_speed.valueChanged.connect(self.change_playback_speed)
        self.slider_speed.setStyleSheet("""
            QSlider#speedSlider::groove:horizontal {
                height: 4px;
                background: #e2e8f0;
                border-radius: 2px;
            }
            QSlider#speedSlider::sub-page:horizontal {
                background: #2563eb;
                border-radius: 2px;
            }
            QSlider#speedSlider::handle:horizontal {
                width: 9px;
                height: 9px;
                margin: -3px 0;
                background: #2563eb;
                border-radius: 7px;
            }
        """)
        controls_layout.addWidget(self.slider_speed)
        controls_layout.addSpacing(6)

        self.lbl_speed_val = QLabel("1.0x")
        self.lbl_speed_val.setFixedWidth(28)
        self.lbl_speed_val.setStyleSheet("font-size: 13px; font-weight: 500; color: #374151;")
        controls_layout.addWidget(self.lbl_speed_val)

        controls_layout.addWidget(self._divider())

        self.lbl_events_title = QLabel("EVENTS")
        self.lbl_events_title.setStyleSheet(section_title_style)
        controls_layout.addWidget(self.lbl_events_title)
        controls_layout.addSpacing(10)

        self.detection_summary_label = QLabel("Events: --")
        self.detection_summary_label.setObjectName("detectionSummaryLabel")
        self.detection_summary_label.setStyleSheet("""
            QLabel#detectionSummaryLabel {
                background-color: #fffbeb;
                color: #92400e;
                border: 1px solid #fcd34d;
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: 500;
            }
        """)
        controls_layout.addWidget(self.detection_summary_label)
        controls_layout.addStretch()

        layout.addWidget(controls_container, 1)
        return frame

    def _divider(self):
        """Create a thin vertical divider for the playback bar."""
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFixedHeight(24)
        line.setStyleSheet("""
            QFrame {
                background-color: #e2e8f0;
                color: #e2e8f0;
                max-width: 1px;
                min-width: 1px;
            }
        """)
        wrapper = QWidget()
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(8, 0, 8, 0)
        wrapper_layout.addWidget(line)
        return wrapper

    def init_charts(self):
        """Initialize only the active respiratory charts."""
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        pg.setConfigOptions(antialias=True)

        for position, (name, color, freq, amp, offset, y_min, y_max) in enumerate(ACTIVE_SIGNAL_CONFIGS):
            dbg(f"DEBUG: Creating chart for {name} with range {y_min}-{y_max}")
            chart = self.create_signal_chart(name, color, freq, amp, offset, y_min, y_max)
            self.charts_layout.addWidget(chart, stretch=1)
            # Track the original order
            self.graph_order.append(name)
        
        dbg("DEBUG: All charts created in init_charts")
        # INITIAL VIEWBOX SYNC (Fix first-time rendering)
        QTimer.singleShot(150, self._initial_viewbox_sync)
    
    def _initial_viewbox_sync(self):
        """Initial ViewBox synchronization to fix first-time rendering issue"""
        dbg("Debug: _initial_viewbox_sync called - fixing first-time rendering")
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            if hasattr(container, 'plot_widget'):
                pw = container.plot_widget
                
                # Force X-axis range update
                start = 0
                end = self.get_effective_time_window_seconds()
                pw.setXRange(start, end, padding=0)
                
                # Force redraw
                pw.getViewBox().update()
                pw.repaint()
                dbg(f"Initial ViewBox sync for {pw.chart_name}: {start} → {end}")

    def _prepare_external_array_signal(
        self,
        values,
        sample_rate_hz=EXTERNAL_ARRAY_SAMPLE_RATE_HZ,
        valid_range=None,
        fill_gaps=True,
    ):
        """Clean samples; chhote gaps bharo, bade gaps NaN rehne do.

        valid_range: (low, high) of physiologically possible values. Samples
        outside it are sensor dropouts, not readings, and become NaN so the
        curve breaks there instead of diving to 0.
        fill_gaps: False for channels where interpolating across a dropout
        would invent readings that were never taken (SpO2, pulse).
        """
        signal = np.asarray(values, dtype=float).reshape(-1)
        if len(signal) == 0:
            return signal

        signal = np.where(np.isfinite(signal), signal, np.nan)

        if valid_range is not None:
            low, high = float(valid_range[0]), float(valid_range[1])
            with np.errstate(invalid="ignore"):
                signal = np.where((signal >= low) & (signal <= high), signal, np.nan)

        if not fill_gaps:
            # Keep the trace anchored at 0 for plotting, but preserve interior
            # NaN gaps so sensor dropouts still show as breaks.
            valid_mask = np.isfinite(signal)
            return signal

        # Keep the gap-fill window tied to the actual sample rate so the
        # "max ~5 second gap" behavior stays correct for non-10 Hz data.
        fill_limit = max(1, int(round(float(sample_rate_hz) * 5.0)))
        series = pd.Series(signal).replace([np.inf, -np.inf], np.nan)
        series = series.interpolate(
            method="linear",
            limit_direction="both",
            limit=fill_limit,
        )  # sample_rate_hz par max ~5 second ka gap bharega
        return series.to_numpy(dtype=float)

    def _load_uploaded_psg_signals(self, csv_path):
        """Load chart signals directly from an uploaded PSG CSV."""
        if load_sleep_csv is None:
            raise RuntimeError(
                "CSV loader import failed."
                + (f" {CSV_IMPORT_ERROR}" if CSV_IMPORT_ERROR else "")
            )

        signal_df = load_sleep_csv(csv_path)
        if signal_df.empty:
            raise ValueError("Uploaded CSV did not contain any usable rows.")

        time_data = signal_df["time_sec"].to_numpy(dtype=float)
        signals = {}
        for signal_name in CSV_SIGNAL_NAMES:
            if signal_name not in signal_df.columns:
                continue
            prepared_signal = self._prepare_external_array_signal(
                signal_df[signal_name].to_numpy(dtype=float),
                valid_range=SIGNAL_VALID_RANGES.get(signal_name),
                fill_gaps=signal_name not in SIGNAL_NO_GAP_FILL,
            )
            signals[signal_name] = prepared_signal

            if signal_name == "airflow":
                raw_airflow = np.asarray(prepared_signal, dtype=float)
                enhanced_airflow = enhance_airflow_for_graph_and_detection(
                    raw_airflow,
                    amplitude=1.10,
                    max_limit=None,
                    spike_threshold=15.0,
                    kernel_size=11,
                    low_protect_margin=2.0,
                    keep_integer=False,
                    savgol_window=11,
                    savgol_order=3,
                )
                signals["airflow_raw"] = raw_airflow
                signals["airflow_enhanced"] = enhanced_airflow
                signals["airflow_display"] = enhanced_airflow
                signals["airflow_detection"] = enhanced_airflow
            elif signal_name == "thorax":
                raw_thorax = np.asarray(prepared_signal, dtype=float)
                smoothed_thorax = self.smooth_data(
                    np.arange(len(raw_thorax), dtype=float),
                    raw_thorax,
                    window_size=11,
                )
                signals["thorax_raw"] = raw_thorax
                signals["thorax_smoothed"] = smoothed_thorax
                signals["thorax_display"] = smoothed_thorax

        return time_data, signals

    def _get_airflow_signal_variant(self, variant="raw"):
        """Return the preferred airflow series for raw or enhanced airflow use."""
        if self.psg_full_data is None or "signals" not in self.psg_full_data:
            return np.array([])

        signals = self.psg_full_data["signals"]
        variant_map = {
            "raw": signals.get("airflow_raw"),
            "enhanced": signals.get("airflow_enhanced"),
            "display": signals.get("airflow_display", signals.get("airflow_enhanced")),
            "detection": signals.get("airflow_enhanced", signals.get("airflow_detection")),
        }
        selected = variant_map.get(variant)
        if selected is None:
            selected = signals.get("airflow", np.array([]))
        return np.asarray(selected, dtype=float)

    def _get_thorax_signal_variant(self, variant="display"):
        """Return the preferred thorax series for raw or smoothed thorax use."""
        if self.psg_full_data is None or "signals" not in self.psg_full_data:
            return np.array([])

        signals = self.psg_full_data["signals"]
        variant_map = {
            "raw": signals.get("thorax_raw"),
            "smoothed": signals.get("thorax_smoothed"),
            "display": signals.get("thorax_smoothed", signals.get("thorax_display")),
        }
        selected = variant_map.get(variant)
        if selected is None:
            selected = signals.get("thorax", np.array([]))
        return np.asarray(selected, dtype=float)

    def save_airflow_smoothing_debug_report(self, csv_path, raw_airflow, enhanced_airflow):
        """Write a text report showing how the shared enhanced airflow differs from raw data."""
        try:
            report_dir = get_configured_path("debug_reports_dir")
            report_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            source_name = Path(csv_path).stem if csv_path else "airflow"
            report_path = report_dir / f"{source_name}_airflow_debug_{timestamp}.txt"

            raw_airflow = np.asarray(raw_airflow, dtype=float).reshape(-1)
            enhanced_airflow = np.asarray(enhanced_airflow, dtype=float).reshape(-1)

            point_count = min(len(raw_airflow), len(enhanced_airflow))
            raw_airflow = raw_airflow[:point_count]
            enhanced_airflow = enhanced_airflow[:point_count]

            enhanced_diff = np.abs(enhanced_airflow - raw_airflow)
            enhanced_changed = not np.allclose(raw_airflow, enhanced_airflow) if point_count else False
            enhanced_mean = float(np.mean(enhanced_diff)) if point_count else 0.0
            enhanced_max = float(np.max(enhanced_diff)) if point_count else 0.0

            lines = [
                "AIRFLOW DEBUG REPORT",
                "====================",
                "",
                "SECTION 1: FILE INFO",
                "--------------------",
                f"Source CSV: {csv_path}",
                f"Generated: {datetime.now().isoformat()}",
                f"Samples compared: {point_count}",
                f"Sample rate used for timestamps: {EXTERNAL_ARRAY_SAMPLE_RATE_HZ} Hz",
                "",
                "SECTION 2: QUICK ANSWER",
                "-----------------------",
                f"Enhanced changed vs raw? {'YES' if enhanced_changed else 'NO'}",
                "",
                "SECTION 3: RAW VS ENHANCED",
                "--------------------------",
                f"Enhanced mean abs diff: {enhanced_mean:.6f}",
                f"Enhanced max abs diff: {enhanced_max:.6f}",
                "",
                "SECTION 4: TOP 20 BIGGEST ENHANCED CHANGES",
                "-------------------------------------------",
                "Rank | Index | Time (sec) | Raw | Enhanced | Abs Diff",
            ]

            if point_count:
                enhanced_top_indices = np.argsort(enhanced_diff)[-20:][::-1]
                for rank, index in enumerate(enhanced_top_indices, start=1):
                    time_sec = index / float(EXTERNAL_ARRAY_SAMPLE_RATE_HZ)
                    lines.append(
                        f"{rank:02d} | {index:05d} | {time_sec:8.2f} | "
                        f"{raw_airflow[index]:.6f} | {enhanced_airflow[index]:.6f} | {enhanced_diff[index]:.6f}"
                    )
            else:
                lines.append("No samples available.")

            lines.extend([
                "",
                "SECTION 5: FIRST 120 SAMPLE PREVIEW",
                "-----------------------------------",
                "Index | Time (sec) | Raw | Enhanced | |Enhanced-Raw|",
            ])

            preview_count = min(120, point_count)
            for index in range(preview_count):
                time_sec = index / float(EXTERNAL_ARRAY_SAMPLE_RATE_HZ)
                lines.append(
                    f"{index:05d} | {time_sec:8.2f} | "
                    f"{raw_airflow[index]:.6f} | "
                    f"{enhanced_airflow[index]:.6f} | "
                    f"{enhanced_diff[index]:.6f}"
                )

            report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print(f"📝 Airflow debug report saved: {report_path}")
        except Exception as error:
            print(f"⚠️ Could not save airflow debug report: {error}")

    def _slice_signal_for_window(self, signal_values, time_window_seconds, time_offset=0):
        """Slice a full signal into the requested fixed-duration time window."""
        signal_values = np.asarray(signal_values, dtype=float)
        samples_per_second = EXTERNAL_ARRAY_SAMPLE_RATE_HZ
        expected_samples = int(round(time_window_seconds * samples_per_second))

        if expected_samples == 0:
            return np.array([]), np.array([])

        if len(signal_values) == 0:
            return np.arange(expected_samples) / samples_per_second, np.full(expected_samples, np.nan)

        start_sample = max(0, int(round(time_offset * samples_per_second)))
        end_sample = min(len(signal_values), start_sample + expected_samples)

        window_signal = signal_values[start_sample:end_sample]
        if len(window_signal) < expected_samples:
            pad = np.full(expected_samples - len(window_signal), np.nan)
            window_signal = np.concatenate([window_signal, pad])

        window_time = np.arange(expected_samples) / samples_per_second
        return window_time, window_signal

    def _smart_downsample(self, time_data, signal_data, max_points=2500):
        """
        Aggressively downsample large time-series data using bin averages.

        This keeps the overall shape of the signal while reducing the number of
        points sent to pyqtgraph, which is the main bottleneck for large PSG
        recordings shown in a single view.
        """
        time_data = np.asarray(time_data, dtype=float).reshape(-1)
        signal_data = np.asarray(signal_data, dtype=float).reshape(-1)

        sample_count = min(len(time_data), len(signal_data))
        if sample_count <= max_points:
            return time_data[:sample_count], signal_data[:sample_count]

        time_data = time_data[:sample_count]
        signal_data = signal_data[:sample_count]

        bin_size = int(np.ceil(sample_count / float(max_points)))
        if bin_size <= 1:
            return time_data, signal_data

        usable_count = (sample_count // bin_size) * bin_size
        if usable_count < bin_size:
            return time_data, signal_data

        trimmed_time = time_data[:usable_count]
        trimmed_signal = signal_data[:usable_count]

        with np.errstate(invalid="ignore"):
            binned_signal = np.nanmean(trimmed_signal.reshape(-1, bin_size), axis=1)
            binned_time = np.nanmean(trimmed_time.reshape(-1, bin_size), axis=1)

        if usable_count < sample_count:
            remainder_time = time_data[usable_count:]
            remainder_signal = signal_data[usable_count:]
            with np.errstate(invalid="ignore"):
                binned_time = np.concatenate([binned_time, [np.nanmean(remainder_time)]])
                binned_signal = np.concatenate([binned_signal, [np.nanmean(remainder_signal)]])

        dbg(
            f"🔽 Downsampled plot data {sample_count} → {len(binned_signal)} "
            f"(bin_size={bin_size}, max_points={max_points})"
        )
        return binned_time, binned_signal

    def _prepare_plot_data_for_window(self, time_data, signal_data, time_window_seconds):
        """Normalize, trim, and downsample window data before plotting."""
        time_data = np.asarray(time_data, dtype=float).reshape(-1)
        signal_data = np.asarray(signal_data, dtype=float).reshape(-1)

        sample_count = min(len(time_data), len(signal_data))
        if sample_count == 0:
            return np.array([]), np.array([])

        if len(time_data) != len(signal_data):
            time_data = time_data[:sample_count]
            signal_data = signal_data[:sample_count]

        # Full-recording views are the expensive case; keep them compact enough
        # to render smoothly even for multi-hour CSV files.
        if self.is_all_psg_mode():
            return self._smart_downsample(time_data, signal_data, max_points=2500)

        # Normal windows stay untouched unless they become unusually large.
        if sample_count > 5000 or float(time_window_seconds) >= 300:
            return self._smart_downsample(time_data, signal_data, max_points=5000)

        return time_data, signal_data

    def _extend_edge_signal_values(self, time_data, signal_data):
        """Fill invalid edge samples with the nearest real value for display only."""
        time_data = np.asarray(time_data, dtype=float).reshape(-1)
        signal_data = np.asarray(signal_data, dtype=float).reshape(-1)
        sample_count = min(len(time_data), len(signal_data))
        if sample_count == 0:
            return np.array([]), np.array([])

        time_data = time_data[:sample_count]
        signal_data = signal_data[:sample_count]

        finite_mask = np.isfinite(signal_data)
        if not finite_mask.any():
            return np.array([]), np.array([])

        first_valid = int(np.argmax(finite_mask))
        last_valid = int(len(signal_data) - 1 - np.argmax(finite_mask[::-1]))

        display_signal = signal_data.copy()
        if first_valid > 0:
            display_signal[:first_valid] = signal_data[first_valid]
        if last_valid + 1 < len(display_signal):
            display_signal[last_valid + 1 :] = signal_data[last_valid]

        return time_data, display_signal

    def _smooth_display_signal(self, signal_data, window_size=5):
        """Apply a small display-only median filter within contiguous finite segments."""
        signal = np.asarray(signal_data, dtype=float).reshape(-1)
        if signal.size < 3 or int(window_size) < 3:
            return signal

        smoothed = signal.copy()
        finite_idx = np.flatnonzero(np.isfinite(signal))
        if finite_idx.size == 0:
            return smoothed

        splits = np.where(np.diff(finite_idx) > 1)[0] + 1
        for segment in np.split(finite_idx, splits):
            if segment.size < 3:
                continue
            segment_values = signal[segment]
            segment_smoothed = (
                pd.Series(segment_values)
                .rolling(window=int(window_size), center=True, min_periods=1)
                .median()
                .to_numpy(dtype=float)
            )
            smoothed[segment] = segment_smoothed

        return smoothed

    def _fill_display_gaps(self, signal_data, window_size=5, gap_limit=None):
        """Display-only fill for NaN gaps so step-like signals stay continuous."""
        signal = np.asarray(signal_data, dtype=float).reshape(-1)
        if signal.size == 0:
            return signal

        series = pd.Series(signal).replace([np.inf, -np.inf], np.nan)
        interpolate_kwargs = {"method": "linear", "limit_direction": "both"}
        if gap_limit is not None:
            interpolate_kwargs["limit"] = int(gap_limit)
        series = series.interpolate(**interpolate_kwargs)

        # Keep the display stable by lightly smoothing the interpolated line.
        if int(window_size) >= 3:
            series = series.rolling(window=int(window_size), center=True, min_periods=1).median()

        return series.to_numpy(dtype=float)

    def get_airflow_detection_data_for_window(self, time_window_seconds, time_offset=0):
        """Return the airflow window reserved for event detection."""
        return self._slice_signal_for_window(
            self._get_airflow_signal_variant("detection"),
            time_window_seconds,
            time_offset,
        )

    def get_airflow_event_baseline(self, airflow, min_occurrence=AIRFLOW_BASELINE_MIN_OCCURRENCE):
        """Pick the most frequent peak value as the airflow event baseline.

        PERF: identical result to the previous pandas version, but numpy-only
        (no Series construction / value_counts / Python-level sort). Roughly
        2x faster, and it is called on every frame for the visible window.
        """
        signal = np.asarray(airflow, dtype=float).reshape(-1)
        signal = signal[np.isfinite(signal)]
        if signal.size == 0:
            return 0.0, 0

        peak_indices, _ = find_peaks(signal)
        pool = np.round(signal[peak_indices] if peak_indices.size else signal, 2)
        if pool.size == 0:
            return 0.0, 0

        values, counts = np.unique(pool, return_counts=True)
        eligible = counts >= int(min_occurrence)
        if eligible.any():
            # Highest count wins; ties broken by the larger value.
            candidate_values = values[eligible]
            candidate_counts = counts[eligible]
            best = np.lexsort((candidate_values, candidate_counts))[-1]
            return float(candidate_values[best]), int(candidate_counts[best])

        best = int(np.argmax(counts))
        return float(values[best]), int(counts[best])

    def get_airflow_display_axis_range(self, airflow):
        """Return an airflow graph range centered on the actual signal excursion.

        Previously this always started at 0, which meant a normal breathing
        signal (baseline ~800-950) got squashed into the top ~15% of the
        plot. Center it the same way the Thorax chart does, using a padded
        percentile range around the observed values instead of a fixed floor.
        """
        airflow = np.asarray(airflow, dtype=float).reshape(-1)
        finite_airflow = airflow[np.isfinite(airflow)]
        if finite_airflow.size == 0:
            return 0.0, 100.0

        return self._auto_axis_range_from_values(finite_airflow, 0.0, 100.0)

    def _lock_auto_axis(self, plot_widget, y_min, y_max, hard_min=None, hard_max=None):
        """Lock an auto-range chart to a data-driven range with limited headroom.

        The lock should move with the data, not disappear entirely. That keeps
        zoom/pan bounded while still allowing the visible range to follow the
        current signal window.

        hard_min/hard_max (optional): the TRUE min/max of the signal actually
        drawn in the current time window (before percentile-trimming). When
        given, they set a floor under how far the "-" zoom-in button/wheel can
        shrink the view, so a real peak or trough in the window can never end
        up clipped outside the visible plot area.
        """
        y_min = float(y_min)
        y_max = float(y_max)
        span = max(y_max - y_min, 1e-6)
        chart_name = getattr(plot_widget, "chart_name", "").strip()
        default_min, default_max = SIGNAL_Y_RANGES.get(chart_name, (y_min, y_max))
        default_span = max(float(default_max) - float(default_min), span)
        headroom = max(span * 0.5, default_span * 0.15)

        # ADC signals (0..4095) cannot go negative, so keep the zoom-out floor
        # clamped at 0 to prevent the chart from drifting below zero.
        limit_min = max(min(y_min, float(default_min)) - headroom, 0.0)
        limit_max = max(y_max, float(default_max)) + headroom

        try:
            plot_widget.setYRange(y_min, y_max, padding=0)
        except TypeError:
            plot_widget.setRange(yRange=[y_min, y_max], padding=0)

        try:
            plot_widget.setLimits(yMin=limit_min, yMax=limit_max)
        except TypeError:
            plot_widget.setLimits(yMin=limit_min, yMax=limit_max)

        plot_widget.original_y_min = y_min
        plot_widget.original_y_max = y_max
        plot_widget.zoom_y_min_limit = limit_min
        plot_widget.zoom_y_max_limit = limit_max
        # FIX: this used to be span * 0.1, letting "-" zoom-in shrink the view
        # to a tenth of the auto-fit range with nothing stopping it. Any peak
        # or trough in the window wider than that tiny span would then draw
        # past the top/bottom of the plot and get clipped at the container's
        # border. When we know the window's true (untrimmed) min/max, use
        # that as the floor instead - the view can never get tighter than
        # what's needed to show every real sample in this window.
        if hard_min is not None and hard_max is not None:
            true_span = max(float(hard_max) - float(hard_min), 1e-6)
            floor_span = max(true_span * 1.05, span)
        else:
            floor_span = span
        plot_widget.zoom_y_min_span = max(floor_span / self.AXIS_MAX_ZOOM_IN, 1e-3)
        # Cap zoom-out to a few multiples of the actual data span so
        # auto-range charts cannot be blown up until they look flat again.
        plot_widget.zoom_y_max_span = min(limit_max - limit_min, span * 6.0)

    def _robust_core_values(self, values):
        """Return finite samples with far-out outliers removed.

        Long recordings can contain a brief settling transient or movement
        spike that is hundreds of units away from the breathing band. If we
        use raw min/max or raw percentiles, that transient can dominate the
        whole plot range on long windows. Trimming to the median core keeps the
        chart readable while still falling back to the raw series if trimming
        would remove too much data.
        """
        series = np.asarray(values, dtype=float).reshape(-1)
        series = series[np.isfinite(series)]
        if series.size == 0:
            return series

        q1, q3 = np.percentile(series, [25.0, 75.0])
        iqr = float(q3) - float(q1)
        if iqr <= 0:
            median = float(np.median(series))
            mad = float(np.median(np.abs(series - median)))
            if mad <= 0:
                return series
            iqr = mad * 1.349

        median = float(np.median(series))
        limit = AUTO_RANGE_OUTLIER_IQR_FACTOR * iqr
        keep = np.abs(series - median) <= limit
        kept = int(np.count_nonzero(keep))
        if kept < max(10, int(series.size * AUTO_RANGE_MIN_KEEP_FRACTION)):
            return series
        return series[keep]

    def _auto_axis_range_from_values(self, values, default_min=0.0, default_max=100.0):
        """Return a padded percentile range for the provided signal values."""
        series = self._robust_core_values(values)
        if series.size == 0 or float(series.min()) == float(series.max()):
            return float(default_min), float(default_max)

        low, high = np.percentile(series, [0.5, 99.5])
        if high <= low:
            low, high = float(series.min()), float(series.max())
        pad = max((float(high) - float(low)) * 0.15, 1.0)
        return float(low) - pad, float(high) + pad

    def _finite_min_max(self, values):
        """Return the min/max of the core samples, or (None, None) if none."""
        series = self._robust_core_values(values)
        if series.size == 0:
            return None, None
        return float(series.min()), float(series.max())

    # ---- Y-axis stability -------------------------------------------------
    # Playback refreshes happen frequently, so raw percentile ranges can cause
    # visible axis flicker. These helpers snap to round ranges and keep the
    # current span stable unless the data genuinely needs a change.
    AXIS_TARGET_DIVISIONS = 5
    AXIS_BREATHING_PAD = 0.05
    AXIS_SHRINK_THRESHOLD = 0.55
    # An artifact happens once in a window. Real breathing peaks happen over
    # and over. Count separate excursions instead of raw samples so sharp,
    # narrow peaks do not get mistaken for outliers.
    AXIS_MIN_RECURRING_EXCURSIONS = 4
    AXIS_MAX_ZOOM_IN = 1.5
    AXIS_FIT_PAD = 0.08

    def _nice_axis_step(self, span, divisions=None):
        """Round a raw span to a 1/2/5/10 x 10^n gridline step."""
        divisions = divisions or self.AXIS_TARGET_DIVISIONS
        raw = max(float(span), 1e-9) / max(divisions, 1)
        magnitude = 10.0 ** math.floor(math.log10(raw))
        ratio = raw / magnitude
        if ratio < 1.5:
            step = 1.0
        elif ratio < 3.0:
            step = 2.0
        elif ratio < 7.0:
            step = 5.0
        else:
            step = 10.0
        return step * magnitude

    def _quantize_axis_range(self, y_min, y_max):
        """Snap a raw range outward to whole multiples of a nice step."""
        y_min = float(y_min)
        y_max = float(y_max)
        if y_max <= y_min:
            y_max = y_min + 1.0
        step = self._nice_axis_step(y_max - y_min)
        low = math.floor(y_min / step) * step
        high = math.ceil(y_max / step) * step
        if high - low < step:
            high = low + step
        return round(low, 6), round(high, 6)

    def _windowed_axis_range_from_values(self, values, default_min=0.0, default_max=100.0):
        """Range for the current window: fit real breathing, skip clear artifacts.

        A fixed percentile cut always removes the same share of every window.
        That is bad for signals with sharp peaks because it can clip real
        waveform extrema and make the trace jump outside its box. This version
        trims only clear outliers around the median, then expands to include
        everything that still looks like signal.
        """
        series = np.asarray(values, dtype=float).reshape(-1)
        series = series[np.isfinite(series)]
        if series.size == 0 or float(series.min()) == float(series.max()):
            return float(default_min), float(default_max)

        core = self._robust_core_values(series)
        if core.size == 0:
            core = series

        low = float(core.min())
        high = float(core.max())

        # Count separate runs outside the trimmed range. One artifact usually
        # appears as one or two excursions; recurring breathing peaks repeat
        # many times and should therefore be fit instead of clipped.
        outside = (series < low) | (series > high)
        if outside.any():
            flags = outside.astype(np.int8)
            excursions = int(np.count_nonzero(np.diff(flags) == 1)) + int(flags[0] == 1)
            if excursions >= self.AXIS_MIN_RECURRING_EXCURSIONS:
                low, high = float(np.nanmin(series)), float(np.nanmax(series))

        if high <= low:
            low, high = float(series.min()), float(series.max())

        pad = max((high - low) * self.AXIS_FIT_PAD, 1e-6)
        return low - pad, high + pad

    def _stable_axis_range(self, plot_widget, raw_min, raw_max):
        """Return a stable axis range that only moves when necessary.

        NOTE: this deliberately works off the trimmed range only. Forcing the
        window's true min/max in here lets a single movement artifact set the
        scale for the whole window, which flattens real breathing.
        """
        pad = max((float(raw_max) - float(raw_min)) * self.AXIS_BREATHING_PAD, 1e-9)
        target = self._quantize_axis_range(raw_min - pad, raw_max + pad)

        current = getattr(plot_widget, "stable_y_range", None)
        if current is None:
            return target

        current_low, current_high = current
        current_span = current_high - current_low
        if current_span <= 0:
            return target

        # The trimmed signal no longer fits inside what is on screen.
        if target[0] < current_low or target[1] > current_high:
            return target

        if (target[1] - target[0]) < current_span * self.AXIS_SHRINK_THRESHOLD:
            return target

        return current

    def _pin_axis_tick_spacing(self, plot_widget, y_min, y_max):
        """Fix gridline spacing so tick density does not flip between refreshes."""
        try:
            axis = plot_widget.getAxis('left')
        except Exception:
            return
        step = self._nice_axis_step(float(y_max) - float(y_min))
        try:
            axis.setTickSpacing(major=step, minor=step / 2.0)
        except Exception:
            pass

    def _apply_dropout_axis(self, plot_widget, chart_name, y_values):
        """Show zero-valued SpO2/Pulse dropouts without hiding them below limits."""
        default_min, default_max = SIGNAL_Y_RANGES.get(chart_name, (0.0, 100.0))
        values = np.asarray(y_values, dtype=float).reshape(-1)
        finite = values[np.isfinite(values)]
        has_zero_dropout = bool(finite.size and np.nanmin(finite) <= 0.0)

        limit_min = 0.0 if has_zero_dropout else float(default_min)
        limit_max = float(default_max)
        edge_margin = max(limit_max - limit_min, 1e-6) * 0.06
        limit_min -= edge_margin
        limit_max += edge_margin
        try:
            plot_widget.setLimits(yMin=limit_min, yMax=limit_max)
        except TypeError:
            plot_widget.setLimits(yMin=limit_min, yMax=limit_max)

        zoom_range = getattr(plot_widget, "zoom_y_range", None)
        if zoom_range is not None:
            y_min, y_max = float(zoom_range[0]), float(zoom_range[1])
            dbg(f"Preserving zoom range during playback: {y_min} - {y_max}")
            if has_zero_dropout and y_min > 0.0:
                y_min = limit_min
        else:
            y_min, y_max = limit_min, limit_max

        try:
            plot_widget.setYRange(y_min, y_max, padding=0)
        except TypeError:
            plot_widget.setRange(yRange=[y_min, y_max], padding=0)

    def _apply_windowed_auto_axis(self, plot_widget, chart_name, y_values):
        """Data-driven Y-axis for one chart, held steady between refreshes."""
        if hasattr(plot_widget, "axis_properties"):
            return

        zoom_y_range = getattr(plot_widget, "zoom_y_range", None)
        if zoom_y_range is not None:
            return

        fallback_min, fallback_max = SIGNAL_Y_RANGES.get(chart_name, (0.0, 100.0))
        raw_min, raw_max = self._windowed_axis_range_from_values(
            y_values, fallback_min, fallback_max
        )
        y_min, y_max = self._stable_axis_range(plot_widget, raw_min, raw_max)

        if getattr(plot_widget, "stable_y_range", None) == (y_min, y_max):
            return

        dbg(
            f"AXIS {chart_name}: n={len(y_values)} "
            f"data {float(np.nanmin(y_values)):.1f}..{float(np.nanmax(y_values)):.1f} | "
            f"raw {raw_min:.1f}..{raw_max:.1f} | axis {y_min:g}..{y_max:g}"
        )
        plot_widget.stable_y_range = (y_min, y_max)
        # Do not pass hard_min/hard_max here: a one-off artifact would turn
        # them into the zoom floor and make zoom-in much less useful.
        self._lock_auto_axis(plot_widget, y_min, y_max)
        self._pin_axis_tick_spacing(plot_widget, y_min, y_max)

    def get_signal_auto_axis_range(self, chart_name):
        """Return the data-driven default Y-axis range for a chart."""
        name = str(chart_name).strip()

        # Before data loads, show the mapping-based range instead of hardcoded
        # 0-100. That keeps startup charts aligned with the configured scale.
        if self.psg_full_data is None or "signals" not in self.psg_full_data:
            return SIGNAL_Y_RANGES.get(name, (0.0, 100.0))

        if name in AUTO_RANGE_SIGNAL_NAMES:
            cached = self._auto_axis_range_cache.get(name)
            if cached is None:
                fallback_min, fallback_max = SIGNAL_Y_RANGES.get(name, (0.0, 100.0))
                full_signal = self._get_full_signal_for_auto_range(name)
                cached = self._auto_axis_range_from_values(
                    full_signal,
                    fallback_min,
                    fallback_max,
                )
                self._auto_axis_range_cache[name] = cached
            return cached

        return SIGNAL_Y_RANGES.get(name, (0.0, 100.0))

    def apply_auto_signal_axis_range(self, plot_widget):
        """Apply auto Y-axis range when no manual override exists."""
        chart_name = getattr(plot_widget, "chart_name", "").strip()
        if chart_name not in AUTO_RANGE_SIGNAL_NAMES:
            return

        if hasattr(plot_widget, "axis_properties"):
            return

        if getattr(plot_widget, "zoom_y_range", None) is not None:
            return

        y_min, y_max = self.get_signal_auto_axis_range(chart_name)
        self._lock_auto_axis(plot_widget, y_min, y_max)
        dbg(f"Applied {chart_name} auto axis range: {y_min} - {y_max}")

        
    def load_psg_data(self, csv_path):
        """Reload the chart from the provided PSG CSV file."""
        try:
            previous_time_window = getattr(self, "current_time_window", 60)
            if self.is_playing:
                self.pause_playback()

            # _clear_auto_detected_selections() below deliberately KEEPS
            # manually-drawn events (source == "manual") so a same-file
            # refresh (e.g. after Re-analyze) doesn't wipe them. But when
            # this call is loading a genuinely different recording, those
            # leftover manual markers must not carry over onto the new
            # file's chart - the old file's data is gone, the old manual
            # events should go with it.
            previous_csv_path = getattr(self, "loaded_csv_path", None)
            is_different_file = previous_csv_path is not None and str(csv_path) != str(previous_csv_path)
            if is_different_file:
                self.dynamic_selections = {}
                self.selection_labels = {}

            self.current_time_offset = 0
            self.auto_focus_applied = False
            self._clear_auto_detected_selections()

            time_data, signals = self._load_uploaded_psg_signals(csv_path)
            if len(time_data) == 0 or not signals:
                raise ValueError("Uploaded PSG CSV data could not be loaded.")

            self.psg_full_data = {"time": time_data, "signals": signals}
            self.current_psg_data = self.psg_full_data
            self.spo2_full_data = (
                np.asarray(time_data, dtype=float),
                np.asarray(signals.get("spo2", []), dtype=float),
            )
            self.loaded_csv_path = str(csv_path)
            self.current_csv_path = str(csv_path)
            # A fresh load resets session tracking; if this CSV came from a
            # Records row, database_window.py calls set_current_session()
            # right after this returns to re-link it.
            self.current_session_id = None
            self.current_session_root_id = None
            self._load_manual_label_overrides()
            self.all_psg_mode = False
            # Preserve the user's chosen window across file loads. The visible
            # span can still clamp to the new recording length later, but the
            # selected window itself should not silently snap back to 60 s.
            try:
                self.current_time_window = max(1.0, float(previous_time_window))
            except (TypeError, ValueError):
                self.current_time_window = 60.0
            self.auto_rule_ai_result = None
            self.last_detection_error = None
            self._invalidate_signal_caches()
            for i in range(self.charts_layout.count()):
                container = self.charts_layout.itemAt(i).widget()
                if not container or not hasattr(container, "plot_widget"):
                    continue
                plot_widget = container.plot_widget
                if hasattr(plot_widget, "axis_properties"):
                    delattr(plot_widget, "axis_properties")
                plot_widget.zoom_y_range = None
                # Different recording, different amplitude - do not hold the
                # previous file's axis range.
                plot_widget.stable_y_range = None
            enhanced_airflow = signals.get("airflow_enhanced", signals.get("airflow", []))
            sleep_mask = None
            for mask_key in ("sleep_mask", "sleep_staging", "staging_mask", "staging", "sleep_stage_mask"):
                if mask_key in signals and signals[mask_key] is not None:
                    sleep_mask = signals[mask_key]
                    break
            self.save_airflow_smoothing_debug_report(
                csv_path=csv_path,
                raw_airflow=signals.get("airflow_raw", signals.get("airflow", [])),
                enhanced_airflow=enhanced_airflow,
            )
            try:
                self.analysis_results = calculate_sleep_metrics(
                    time_data,
                    signals,
                    sleep_mask=sleep_mask,
                    sample_rate_hz=EXTERNAL_ARRAY_SAMPLE_RATE_HZ,
                )
                self.analysis_json_path = save_sleep_metrics_json(
                    self.analysis_results,
                    source_csv=csv_path,
                )
                dbg(f"📝 Analysis JSON saved: {self.analysis_json_path}")
            except Exception as analysis_error:
                self.analysis_results = None
                self.analysis_json_path = None
                dbg(f"⚠️ Could not calculate/save PSG metrics JSON: {analysis_error}")

            global_events = self._build_airflow_navigation_events(enhanced_airflow)
            windowed_events = self._build_windowed_airflow_navigation_events(
                enhanced_airflow,
                window_seconds=max(1.0, float(self.current_time_window)),
            )
            self.airflow_detected_events = (
                windowed_events if len(windowed_events) >= len(global_events) else global_events
            )
            self.current_window_airflow_events = []
            self.emit_detected_events_panel()
            self.update_detection_summary_label()
            dbg(
                "✅ Loaded respiratory graph data from uploaded CSV "
                f"{csv_path}"
            )
            dbg(f"   Duration: {time_data[-1]/60:.1f} minutes")
            return time_data, signals
            
        except Exception as e:
            dbg(f"❌ Error loading PSG data: {e}")
            import traceback
            traceback.print_exc()
            # Return empty data if loading fails
            self._invalidate_signal_caches()
            self.psg_full_data = None
            self.current_psg_data = None
            self.spo2_full_data = (np.array([]), np.array([]))
            self.loaded_csv_path = None
            self.current_session_id = None
            self.current_session_root_id = None
            self.auto_rule_ai_result = None
            self.manual_label_overrides = {}
            self.deleted_auto_event_keys = set()
            self.airflow_detected_events = []
            self.current_window_airflow_events = []
            self.analysis_results = None
            self.analysis_json_path = None
            return np.array([]), {}

    def load_psg_data_and_detect(
        self,
        csv_path,
        padding_seconds: float = 30.0,
        focus_first_event: bool = False,
    ):
        """Load uploaded PSG data, run rule-based detection, and optionally jump to the first event."""
        time_data, signals = self.load_psg_data(csv_path)
        if len(time_data) == 0 or not signals:
            return time_data, signals, False

        self.run_rule_ai_apnea_detection()
        jumped = False
        if focus_first_event:
            jumped = self.focus_on_first_detected_event(padding_seconds=padding_seconds)

        if not jumped:
            self.current_time_offset = 0
            self.refresh_charts()
        self.time_position_updated.emit()
        return time_data, signals, jumped

    def emit_current_navigation_events(self):
        """Emit whichever event source is currently available to the side panel."""
        self.apnea_events_updated.emit(self.get_available_navigation_events())

    def _normalize_detected_panel_event(self, event: dict, source_hint: str | None = None) -> dict | None:
        """Convert stored selection data into the side-panel event shape."""
        if not isinstance(event, dict):
            return None

        try:
            start_sec = float(event.get("start_sec", event.get("start_time", event.get("start", 0.0))))
            end_sec = float(event.get("end_sec", event.get("end_time", event.get("end", start_sec))))
        except (TypeError, ValueError):
            return None

        final_label = canonical_event_label(
            event.get("final_label")
            or event.get("rule_label")
            or event.get("label")
            or "REVIEW"
        )

        duration_sec = event.get("duration_sec")
        try:
            duration_sec = float(duration_sec) if duration_sec is not None else max(0.0, end_sec - start_sec)
        except (TypeError, ValueError):
            duration_sec = max(0.0, end_sec - start_sec)

        normalized = dict(event)
        normalized["start_sec"] = start_sec
        normalized["end_sec"] = end_sec
        normalized["duration_sec"] = duration_sec
        normalized["final_label"] = final_label
        normalized["rule_label"] = str(event.get("rule_label") or final_label)
        normalized["source"] = str(event.get("source") or source_hint or "")
        return normalized

    def _get_panel_detected_events(self):
        """Return the live event list used by the Detected Events side panel."""
        if "Airflow" in self.selection_labels:
            events = []
            for selection in self.selection_labels.get("Airflow", []):
                normalized = self._normalize_detected_panel_event(selection, source_hint="selection_labels")
                if normalized is not None:
                    events.append(normalized)
            return events

        if self.auto_rule_ai_result is not None:
            events = []
            for event in self.auto_rule_ai_result.get("events", []):
                normalized = self._normalize_detected_panel_event(event, source_hint="auto_rule_ai")
                if normalized is not None:
                    events.append(normalized)
            return events

        airflow_events = list(getattr(self, "airflow_detected_events", []))
        if airflow_events:
            return [
                normalized
                for normalized in (
                    self._normalize_detected_panel_event(event, source_hint="airflow_detected_events")
                    for event in airflow_events
                )
                if normalized is not None
            ]

        window_events = list(getattr(self, "current_window_airflow_events", []))
        return [
            normalized
            for normalized in (
                self._normalize_detected_panel_event(event, source_hint="current_window_airflow_events")
                for event in window_events
            )
            if normalized is not None
        ]

    def get_all_detected_events(self):
        """Return the full-dataset event list for stable counts and side-panel display."""
        return self._get_panel_detected_events()

    def emit_detected_events_panel(self):
        """Emit the full detected-event list for the side panel.

        PERF: this was fired from mark_airflow_drop_events() on EVERY frame,
        so the side panel rebuilt its whole QListWidget ~20 times a second even
        though the event set almost never changes. Emit only on real changes.
        """
        events = self._get_panel_detected_events()
        signature = (
            len(events),
            tuple(
                (
                    round(float(event.get("start_sec", 0.0)), 3),
                    round(float(event.get("end_sec", 0.0)), 3),
                    str(event.get("final_label") or event.get("label") or ""),
                )
                for event in events
            ),
        )
        if signature == getattr(self, "_last_events_signature", None):
            return
        self._last_events_signature = signature
        self.apnea_events_updated.emit(events)

    def _manual_label_overrides_path(self) -> Path | None:
        if not getattr(self, "loaded_csv_path", None):
            return None
        csv_path = Path(self.loaded_csv_path)
        return csv_path.with_name(f"{csv_path.stem}_manual_labels.json")

    def _selection_time_key(self, start_sec: float, end_sec: float) -> str:
        return f"{float(start_sec):.2f}_{float(end_sec):.2f}"

    @staticmethod
    def _first_number(selection: dict, keys: tuple[str, ...]) -> float | None:
        for key in keys:
            value = selection.get(key)
            if value is None:
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return None

    def _selection_time_key_from_selection(self, selection: dict) -> str | None:
        start_sec = self._first_number(selection, ("start_time", "start", "start_sec"))
        end_sec = self._first_number(selection, ("end_time", "end", "end_sec"))
        if start_sec is None or end_sec is None:
            return None
        return self._selection_time_key(start_sec, end_sec)

    def _load_manual_label_overrides(self):
        self.manual_label_overrides = {}
        self.deleted_auto_event_keys = set()
        self._deleted_span_cache = None
        overrides_path = self._manual_label_overrides_path()
        if overrides_path is None or not overrides_path.exists():
            return

        try:
            raw_data = json.loads(overrides_path.read_text(encoding="utf-8"))
        except Exception as error:
            print(f"⚠️ Could not load manual label overrides: {error}")
            return

        if not isinstance(raw_data, dict):
            return

        # New sidecar files are {"label_overrides": {...}, "manual_selections": {...}}.
        # "deleted_auto_events" stores auto-detected time keys the user
        # removed so those events stay removed across re-analysis.
        # Old files are just the flat {time_key: label} dict - treat that whole
        # dict as label_overrides for backward compatibility.
        if "label_overrides" in raw_data or "manual_selections" in raw_data:
            label_overrides_raw = raw_data.get("label_overrides") or {}
            manual_selections_raw = raw_data.get("manual_selections") or {}
            deleted_auto_events_raw = raw_data.get("deleted_auto_events") or []
        else:
            label_overrides_raw = raw_data
            manual_selections_raw = {}
            deleted_auto_events_raw = []

        normalized = {}
        for key, value in label_overrides_raw.items():
            if isinstance(value, str):
                normalized[str(key)] = {
                    "label": value,
                    "original_label": None,
                    "edited_at": None,
                }
            elif isinstance(value, dict) and value.get("label"):
                normalized[str(key)] = {
                    "label": str(value.get("label")),
                    "original_label": value.get("original_label"),
                    "edited_at": value.get("edited_at"),
                }

        self.manual_label_overrides = normalized
        self._load_deleted_auto_events_from_raw(deleted_auto_events_raw)
        self._load_manual_selections_from_raw(manual_selections_raw)

    def _load_deleted_auto_events_from_raw(self, deleted_auto_events_raw):
        """Restore deleted auto-event keys from the sidecar JSON."""
        deleted_keys = set()

        if isinstance(deleted_auto_events_raw, dict):
            deleted_auto_events_raw = list(deleted_auto_events_raw.keys())

        if not isinstance(deleted_auto_events_raw, (list, tuple, set)):
            self.deleted_auto_event_keys = deleted_keys
            return

        for entry in deleted_auto_events_raw:
            if isinstance(entry, dict):
                key = self._selection_time_key_from_selection(entry)
                if key is None:
                    key = entry.get("key")
                if key is not None:
                    deleted_keys.add(str(key))
            elif entry is not None:
                deleted_keys.add(str(entry))

        self.deleted_auto_event_keys = deleted_keys

    def _load_manual_selections_from_raw(self, manual_selections_raw):
        """Rebuild freely-drawn (Type 2) manual selection boxes from the
        sidecar JSON's "manual_selections" payload.

        Any manual entries already sitting in memory for a chart are
        dropped first, so re-loading (e.g. a same-file refresh, where
        _clear_auto_detected_selections() left the old manual entries in
        place) doesn't duplicate them - the file on disk is the source
        of truth for what gets loaded back in.
        """
        if not isinstance(manual_selections_raw, dict):
            manual_selections_raw = {}

        for chart_name in list(self.selection_labels.keys()):
            self.selection_labels[chart_name] = [
                sel for sel in self.selection_labels[chart_name]
                if not (isinstance(sel, dict) and sel.get("source") == "manual")
            ]
        for chart_name in list(self.dynamic_selections.keys()):
            self.dynamic_selections[chart_name] = [
                sel for sel in self.dynamic_selections[chart_name]
                if not (isinstance(sel, dict) and sel.get("source") == "manual")
            ]

        for chart_name, entries in manual_selections_raw.items():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                try:
                    start_time = float(entry.get("start_time", entry.get("start", 0.0)))
                    end_time = float(entry.get("end_time", entry.get("end", 0.0)))
                except (TypeError, ValueError):
                    continue
                label = entry.get("label")
                if not label:
                    continue

                color = entry.get("color") or self.get_label_color(label)
                selection_data = {
                    "label": label,
                    "start": start_time,
                    "end": end_time,
                    "start_time": start_time,
                    "end_time": end_time,
                    "color": color,
                    "source": "manual",
                }
                dynamic_selection_data = {
                    "label": label,
                    "start_time": start_time,
                    "end_time": end_time,
                    "color": color,
                    "spo2_info": entry.get("spo2_info", ""),
                    "source": "manual",
                }

                self.selection_labels.setdefault(chart_name, []).append(selection_data)
                self.dynamic_selections.setdefault(chart_name, []).append(dynamic_selection_data)

    def _collect_manual_selections_for_save(self):
        """Pull just the freely-drawn (Type 2) manual boxes out of
        dynamic_selections, keyed by chart name, ready to write to the
        sidecar JSON. Auto-detected entries (source == "auto_rule_ai")
        are excluded.
        """
        manual_selections = {}
        for chart_name, entries in self.dynamic_selections.items():
            manual_entries = [
                dict(entry) for entry in entries
                if isinstance(entry, dict) and entry.get("source") == "manual"
            ]
            if manual_entries:
                manual_selections[chart_name] = manual_entries
        return manual_selections

    def _collect_deleted_auto_events_for_save(self):
        """Return deleted auto-event keys in a JSON-friendly form."""
        return sorted(self.deleted_auto_event_keys)

    def _save_manual_label_overrides(self):
        overrides_path = self._manual_label_overrides_path()
        if overrides_path is None:
            return

        try:
            overrides_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "label_overrides": self.manual_label_overrides,
                "manual_selections": self._collect_manual_selections_for_save(),
                "deleted_auto_events": self._collect_deleted_auto_events_for_save(),
            }
            overrides_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception as error:
            print(f"⚠️ Could not save manual label overrides: {error}")

    def _selection_is_deleted_auto_event(self, selection: dict) -> bool:
        if not isinstance(selection, dict):
            return False
        if not self.deleted_auto_event_keys:
            return False

        # A re-analysis with changed parameters can shift an event's edges
        # by a fraction of a second. Exact "start_end" key matching missed
        # that, so a removed event came back looking brand new. Match on
        # geometry instead: near-identical edges, or a large time overlap.
        key = self._selection_time_key_from_selection(selection)
        if key and key in self.deleted_auto_event_keys:
            return True

        start_sec = self._first_number(selection, ("start_time", "start", "start_sec"))
        end_sec = self._first_number(selection, ("end_time", "end", "end_sec"))
        if start_sec is None or end_sec is None:
            return False

        start_sec, end_sec = self._ordered_span(start_sec, end_sec)
        duration = end_sec - start_sec

        for deleted_start, deleted_end in self._deleted_auto_event_spans():
            # Same event, edges nudged slightly by new parameters.
            if (
                abs(start_sec - deleted_start) <= DELETED_EVENT_EDGE_TOLERANCE_SEC
                and abs(end_sec - deleted_end) <= DELETED_EVENT_EDGE_TOLERANCE_SEC
            ):
                return True

            # Or: mostly the same stretch of time, whatever the edges.
            overlap = min(end_sec, deleted_end) - max(start_sec, deleted_start)
            if overlap <= 0:
                continue
            # Here the question is: how much of the NEW event lies inside the
            # deleted stretch we already know about?
            if duration <= 0:
                continue
            if (overlap / duration) >= DELETED_EVENT_MIN_OVERLAP_RATIO:
                return True

        return False

    @staticmethod
    def _ordered_span(start_sec, end_sec) -> tuple[float, float]:
        start_sec = float(start_sec)
        end_sec = float(end_sec)
        if end_sec < start_sec:
            start_sec, end_sec = end_sec, start_sec
        return start_sec, end_sec

    def _deleted_auto_event_spans(self):
        """Parse deleted keys ("123.00_145.50") into (start, end) spans."""
        keys = frozenset(self.deleted_auto_event_keys)
        cached = getattr(self, "_deleted_span_cache", None)
        if cached is not None and cached[0] == keys:
            return cached[1]

        spans = []
        for key in keys:
            parts = str(key).split("_")
            if len(parts) != 2:
                continue
            try:
                spans.append(self._ordered_span(parts[0], parts[1]))
            except (TypeError, ValueError):
                continue

        self._deleted_span_cache = (keys, spans)
        return spans

    def _mark_deleted_auto_event(self, selection: dict) -> bool:
        """Persist an auto-detected event removal so it stays removed."""
        if not isinstance(selection, dict):
            return False
        if str(selection.get("source", "")) != "auto_rule_ai":
            return False

        key = self._selection_time_key_from_selection(selection)
        if key is None:
            return False

        self.deleted_auto_event_keys.add(key)
        # A deleted auto-event should not keep a stale label override.
        self.manual_label_overrides.pop(key, None)
        return True

    def _mark_overlapping_auto_events_for_manual_selection(self, chart_name: str, start_sec: float, end_sec: float) -> bool:
        """Mark overlapping auto-detected events as deleted for the active chart."""
        if not self.auto_rule_ai_result:
            return False

        try:
            selection_start, selection_end = self._ordered_span(start_sec, end_sec)
        except Exception:
            return False

        changed = False
        if chart_name == "Airflow":
            for event in self.auto_rule_ai_result.get("events", []) or []:
                try:
                    event_start = float(event.get("start_sec", 0.0))
                    event_end = float(event.get("end_sec", event_start))
                except (TypeError, ValueError):
                    continue

                event_start, event_end = self._ordered_span(event_start, event_end)
                overlap = min(selection_end, event_end) - max(selection_start, event_start)
                if overlap <= 0:
                    continue

                if self._mark_deleted_auto_event({
                    "source": "auto_rule_ai",
                    "start_sec": event_start,
                    "end_sec": event_end,
                }):
                    changed = True

        elif chart_name == "SpO2":
            for desat in self.auto_rule_ai_result.get("desaturations", []) or []:
                try:
                    desat_start = float(desat.get("start_sec", 0.0))
                    desat_end = float(desat.get("end_sec", desat_start))
                except (TypeError, ValueError):
                    continue

                desat_start, desat_end = self._ordered_span(desat_start, desat_end)
                overlap = min(selection_end, desat_end) - max(selection_start, desat_start)
                if overlap <= 0:
                    continue

                if self._mark_deleted_auto_event({
                    "source": "auto_rule_ai",
                    "start_sec": desat_start,
                    "end_sec": desat_end,
                }):
                    changed = True

        return changed

    def _apply_deleted_auto_event_filters_to_auto_result(self) -> bool:
        """Drop deleted auto events from the current detector result."""
        result = getattr(self, "auto_rule_ai_result", None)
        if not result:
            return False

        events = result.get("events", [])
        if not events:
            return False

        filtered_events = []
        changed = False
        for event in events:
            if self._selection_is_deleted_auto_event(event):
                changed = True
                continue
            filtered_events.append(event)

        if changed:
            result["events"] = filtered_events
        return changed

    def _apply_manual_label_overrides_to_auto_result(self) -> bool:
        result = getattr(self, "auto_rule_ai_result", None)
        if not result:
            return False

        events = result.get("events", [])
        if not events:
            return False

        changed = False
        for event in events:
            try:
                start_sec = float(event.get("start_sec", 0.0))
                end_sec = float(event.get("end_sec", start_sec))
            except (TypeError, ValueError):
                continue

            key = self._selection_time_key(start_sec, end_sec)
            override = self.manual_label_overrides.get(key)
            if not override:
                if event.get("is_manually_edited"):
                    restored = event.get("original_label") or event.get("rule_label")
                    if restored:
                        event["final_label"] = restored
                    event["is_manually_edited"] = False
                    event.pop("manual_label_override", None)
                    event.pop("original_label", None)
                continue

            original_label = override.get("original_label")
            if not original_label:
                original_label = event.get("rule_label") or event.get("final_label") or "REVIEW"

            event["original_label"] = original_label
            event["manual_label_override"] = override.get("label")
            event["final_label"] = override.get("label")
            event["is_manually_edited"] = True
            changed = True

        return changed

    def _set_manual_label_override_for_selection(self, selection: dict, label_type: str) -> bool:
        key = self._selection_time_key_from_selection(selection)
        if key is None:
            return False

        original_label = (
            selection.get("original_label")
            or selection.get("final_label")
            or selection.get("rule_label")
            or selection.get("label")
            or "REVIEW"
        )
        self.manual_label_overrides[key] = {
            "label": str(label_type),
            "original_label": str(original_label),
            "edited_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._save_manual_label_overrides()
        self._apply_manual_label_overrides_to_auto_result()
        return True

    def set_manual_label_for_event(self, event: dict, label_type: str) -> bool:
        """Persist a manual label override for a detected auto event."""
        if not isinstance(event, dict):
            return False
        return self._set_manual_label_override_for_selection(event, label_type)

    def reset_manual_label_for_event(self, event: dict) -> bool:
        """Remove a manual label override for a detected auto event."""
        if not isinstance(event, dict):
            return False
        return self._reset_manual_label_override_for_selection(event)

    def _reset_manual_label_override_for_selection(self, selection: dict) -> bool:
        key = self._selection_time_key_from_selection(selection)
        if key is None or key not in self.manual_label_overrides:
            return False

        self.manual_label_overrides.pop(key, None)
        self._save_manual_label_overrides()
        self._apply_manual_label_overrides_to_auto_result()
        return True

    def clear_all_manual_label_overrides(self):
        """Clear ALL manual events before a fresh, clean re-analysis - both
        relabeled auto-events (Type 1, manual_label_overrides) and freely
        -drawn selection boxes (Type 2, selection_labels/dynamic_selections
        entries with source == "manual").
        """
        self.manual_label_overrides = {}
        self.deleted_auto_event_keys = set()
        for chart_name in list(self.selection_labels.keys()):
            self.selection_labels[chart_name] = [
                sel for sel in self.selection_labels[chart_name]
                if not (isinstance(sel, dict) and sel.get("source") == "manual")
            ]
        for chart_name in list(self.dynamic_selections.keys()):
            self.dynamic_selections[chart_name] = [
                sel for sel in self.dynamic_selections[chart_name]
                if not (isinstance(sel, dict) and sel.get("source") == "manual")
            ]
        self._save_manual_label_overrides()
        self._apply_manual_label_overrides_to_auto_result()
        self.render_dynamic_selections()
        self.emit_detected_events_panel()
        self.update_detection_summary_label()

    def _clear_manual_events_in_memory(self):
        """Wipe manual events from the LIVE view only - never touches the
        sidecar JSON on disk for whatever file is currently loaded.

        This exists specifically for the Re-analyze -> "New report" flow:
        - Before save (only when the user picked "delete manual events"):
          clearing here first means the fresh detection pass has nothing
          to reapply, and _archive_manual_label_overrides_snapshot() then
          has nothing to write onto the new copy - a clean new report.
        - After save (always, called from _on_save_done once the archive
          snapshot has already been written): the manual events that
          existed at save time are now the new saved report's concern,
          not the live screen's - the working view goes back to showing
          just the fresh auto-detected events.

        Using clear_all_manual_label_overrides() for either of the above
        would be wrong: that method also SAVES the (now empty) state to
        the sidecar of whichever file is currently open - which, in this
        flow, is still the ORIGINAL recording. That would silently wipe
        the original's own manual events from disk, breaking the
        "Current report manual events are always permanent" rule.
        """
        self.manual_label_overrides = {}
        # Removing an auto-detected event IS a manual change, so the
        # "delete the manual events for this new report" choice has to
        # drop these too - otherwise the "fresh auto-detected events
        # only" report stays silently filtered and the event count shown
        # after re-analysis is wrong.
        self.deleted_auto_event_keys = set()
        for chart_name in list(self.selection_labels.keys()):
            self.selection_labels[chart_name] = [
                sel for sel in self.selection_labels[chart_name]
                if not (isinstance(sel, dict) and sel.get("source") == "manual")
            ]
        for chart_name in list(self.dynamic_selections.keys()):
            self.dynamic_selections[chart_name] = [
                sel for sel in self.dynamic_selections[chart_name]
                if not (isinstance(sel, dict) and sel.get("source") == "manual")
            ]
        self._apply_deleted_auto_event_filters_to_auto_result()
        self._apply_manual_label_overrides_to_auto_result()
        self.render_dynamic_selections()
        self.emit_detected_events_panel()
        self.update_detection_summary_label()

    def has_any_manual_events(self) -> bool:
        """True if this recording currently has any manual events - either
        a relabeled auto-detected event (Type 1) or a freely-drawn
        selection box (Type 2). Used to decide whether the New-report
        "delete manual events?" prompt needs to be shown at all.
        """
        if self.manual_label_overrides:
            return True
        if self.deleted_auto_event_keys:
            return True
        for entries in self.selection_labels.values():
            if any(isinstance(entry, dict) and entry.get("source") == "manual" for entry in entries):
                return True
        return False

    def _refresh_auto_rule_ai_views(self):
        self._apply_deleted_auto_event_filters_to_auto_result()
        self._apply_manual_label_overrides_to_auto_result()
        self._sync_auto_detected_selections_into_overlays()
        self.render_dynamic_selections()
        self.emit_detected_events_panel()
        self.update_detection_summary_label()

    def run_rule_ai_apnea_detection(self):
        """Run airflow baseline rule detection on the loaded CSV."""
        if not self.loaded_csv_path:
            self.last_detection_error = "CSV path missing for detection."
            self.auto_rule_ai_result = None
            self.emit_detected_events_panel()
            self.update_detection_summary_label()
            return

        if detect_apnea_events_from_csv is None:
            self.last_detection_error = (
                "Detector import failed."
                + (f" {DETECTION_IMPORT_ERROR}" if DETECTION_IMPORT_ERROR else "")
            )
            self.auto_rule_ai_result = None
            self.emit_detected_events_panel()
            self.update_detection_summary_label()
            return

        try:
            output_dir = APP_ROOT / "ai_models" / "sleep_apnea" / "hybrid_pipeline_output" / "chart_auto_events"
            self.auto_rule_ai_result = detect_apnea_events_from_csv(
                csv_path=self.loaded_csv_path,
                output_dir=output_dir,
                enable_ai=False,
            )
            self._apply_deleted_auto_event_filters_to_auto_result()
            self._apply_manual_label_overrides_to_auto_result()
            self.auto_focus_applied = False
            self.last_detection_error = None
            print(
                f"✅ Auto rule-only apnea detection complete: "
                f"{len(self.auto_rule_ai_result.get('events', []))} events"
            )
            self._apply_sensor_off_masking_after_detection()
            self.refresh_charts()
            self._sync_auto_detected_selections_into_overlays()
            self.render_dynamic_selections()
            self.emit_detected_events_panel()
            self.update_detection_summary_label()
        except Exception as error:
            print(f"⚠️ Auto rule-only apnea detection failed: {error}")
            try:
                output_dir = APP_ROOT / "ai_models" / "sleep_apnea" / "hybrid_pipeline_output" / "chart_auto_events"
                self.auto_rule_ai_result = detect_apnea_events_from_csv(
                    csv_path=self.loaded_csv_path,
                    output_dir=output_dir,
                    enable_ai=False,
                )
                self._apply_deleted_auto_event_filters_to_auto_result()
                self._apply_manual_label_overrides_to_auto_result()
                self.auto_focus_applied = False
                self.last_detection_error = None
                print(
                    f"✅ Fallback rule-only apnea detection complete: "
                    f"{len(self.auto_rule_ai_result.get('events', []))} events"
                )
                self._apply_sensor_off_masking_after_detection()
                self.refresh_charts()
                self._sync_auto_detected_selections_into_overlays()
                self.render_dynamic_selections()
                self.emit_detected_events_panel()
                self.update_detection_summary_label()
            except Exception as fallback_error:
                self.auto_rule_ai_result = None
                self.auto_focus_applied = False
                self.last_detection_error = f"Rule-only failed: {error} | Fallback failed: {fallback_error}"
                self.emit_detected_events_panel()
                self.update_detection_summary_label()
                print(f"❌ Rule-only fallback detection also failed: {fallback_error}")

    def _clear_auto_detected_selections(self):
        """Remove previously inserted automatic overlays while preserving manual labels."""
        for chart_name in list(self.selection_labels.keys()):
            self.selection_labels[chart_name] = [
                selection
                for selection in self.selection_labels[chart_name]
                if selection.get("source") != "auto_rule_ai"
            ]
            if not self.selection_labels[chart_name]:
                self.selection_labels.pop(chart_name, None)

        for chart_name in list(self.dynamic_selections.keys()):
            self.dynamic_selections[chart_name] = [
                selection
                for selection in self.dynamic_selections[chart_name]
                if selection.get("source") != "auto_rule_ai"
            ]
            if not self.dynamic_selections[chart_name]:
                self.dynamic_selections.pop(chart_name, None)

    def _sync_auto_detected_selections_into_overlays(self):
        """Map automatic rule+AI events into the same overlay structure as manual drag labels."""
        self._clear_auto_detected_selections()
        if not self.auto_rule_ai_result:
            return

        events = self.auto_rule_ai_result.get("events", [])
        # Desaturations are scored by the detector alongside the airflow events
        # (AASM reports them as ODI). They belong on the SpO2 trace, so a
        # recording with SpO2 dips but no airflow event must still reach the
        # loop below instead of returning early.
        desaturations = self.auto_rule_ai_result.get("desaturations", []) or []
        if not events and not desaturations:
            return

        target_charts = ["Airflow"] if events else []

        for chart_name in target_charts:
            self.selection_labels.setdefault(chart_name, [])
            self.dynamic_selections.setdefault(chart_name, [])

            for event in events:
                final_label = canonical_event_label(event.get("final_label") or event.get("rule_label") or "REVIEW")
                if final_label == "REVIEW":
                    continue
                start_time = float(event["start_sec"])
                end_time = float(event["end_sec"])
                selection_data = {
                    "label": final_label,
                    "start": start_time,
                    "end": end_time,
                    "start_time": start_time,
                    "end_time": end_time,
                    "color": self.get_label_color(final_label),
                    "source": "auto_rule_ai",
                    "is_manually_edited": bool(event.get("is_manually_edited")),
                    "original_label": event.get("original_label"),
                    "evidence": list(event.get("evidence") or []),
                }
                dynamic_data = {
                    "label": final_label,
                    "start_time": start_time,
                    "end_time": end_time,
                    "color": self.get_label_color(final_label),
                    "source": "auto_rule_ai",
                    "is_manually_edited": bool(event.get("is_manually_edited")),
                    "original_label": event.get("original_label"),
                    "evidence": list(event.get("evidence") or []),
                }
                self.selection_labels[chart_name].append(selection_data)
                self.dynamic_selections[chart_name].append(dynamic_data)

        # Desaturations go on the SpO2 chart, through the SAME overlay
        # structure the manual "Desaturation" right-click menu writes to, so
        # they render with the identical teal shading and are cleared by
        # _clear_auto_detected_selections along with the airflow events.
        if desaturations:
            self.selection_labels.setdefault("SpO2", [])
            self.dynamic_selections.setdefault("SpO2", [])

            for desat in desaturations:
                try:
                    start_time = float(desat["start_sec"])
                    end_time = float(desat["end_sec"])
                except (KeyError, TypeError, ValueError):
                    continue
                if not (end_time > start_time):
                    continue

                if self._selection_time_key(start_time, end_time) in self.deleted_auto_event_keys:
                    continue

                desat_color = self.get_label_color("DE-SATURATION")
                baseline_spo2 = desat.get("baseline_spo2")
                nadir_spo2 = desat.get("nadir_spo2")
                spo2_info = ""
                if baseline_spo2 is not None and nadir_spo2 is not None:
                    try:
                        spo2_info = (
                            f"{int(round(float(baseline_spo2)))} → {int(round(float(nadir_spo2)))} "
                            f"(↓ {float(desat.get('drop_percent', 0.0)):.1f})"
                        )
                    except (TypeError, ValueError):
                        spo2_info = ""
                self.selection_labels["SpO2"].append({
                    "label": "DE-SATURATION",
                    "start": start_time,
                    "end": end_time,
                    "start_time": start_time,
                    "end_time": end_time,
                    "color": desat_color,
                    "source": "auto_rule_ai",
                    "spo2_info": spo2_info,
                })
                self.dynamic_selections["SpO2"].append({
                    "label": "DE-SATURATION",
                    "start_time": start_time,
                    "end_time": end_time,
                    "color": desat_color,
                    "source": "auto_rule_ai",
                    "spo2_info": spo2_info,
                })

    def get_first_detected_event(self):
        """Return the earliest automatically detected event."""
        events = self.get_available_navigation_events()
        if not events:
            return None
        return min(events, key=lambda event: float(event.get("start_sec", 0.0)))

    def focus_on_first_detected_event(self, padding_seconds: float = 30.0) -> bool:
        """Jump the chart window to the first detected event."""
        first_event = self.get_first_detected_event()
        if not first_event:
            return False

        max_offset = self._get_playback_max_offset()
        requested_offset = max(0.0, float(first_event["start_sec"]) - float(padding_seconds))
        self.current_time_offset = min(max_offset, requested_offset)
        self.auto_focus_applied = True
        self.refresh_charts()
        self.update_time_position_label()
        self.update_detection_summary_label()
        return True

    def focus_on_event(self, event_data, padding_seconds: float = 30.0) -> bool:
        """Jump the chart window to a specific event dictionary."""
        if not event_data:
            return False
        max_offset = self._get_playback_max_offset()
        requested_offset = max(0.0, float(event_data["start_sec"]) - float(padding_seconds))
        self.current_time_offset = min(max_offset, requested_offset)
        self.auto_focus_applied = True
        self.refresh_charts()
        self.update_time_position_label()
        self.update_detection_summary_label()
        return True

    def focus_on_next_event(self) -> bool:
        """Jump to the next event after the current window center."""
        events = sorted(self.get_available_navigation_events(), key=lambda event: float(event["start_sec"]))
        if not events:
            return False
        center_time = self.current_time_offset + (self.get_effective_time_window_seconds() / 2.0)
        for event in events:
            if float(event["start_sec"]) > center_time:
                return self.focus_on_event(event)
        return self.focus_on_event(events[-1])

    def focus_on_previous_event(self) -> bool:
        """Jump to the previous event before the current window center."""
        events = sorted(self.get_available_navigation_events(), key=lambda event: float(event["start_sec"]))
        if not events:
            return False
        center_time = self.current_time_offset + (self.get_effective_time_window_seconds() / 2.0)
        for event in reversed(events):
            if float(event["start_sec"]) < center_time:
                return self.focus_on_event(event)
        return self.focus_on_event(events[0])

    def update_detection_summary_label(self):
        """Show event detection summary in the control bar."""
        if not hasattr(self, "detection_summary_label"):
            return

        events = self.get_available_navigation_events()
        if not events:
            if self.last_detection_error:
                error_text = str(self.last_detection_error).replace("\n", " ")
                if len(error_text) > 120:
                    error_text = error_text[:117] + "..."
                self.detection_summary_label.setText(f"Detection failed | {error_text}")
            else:
                self.detection_summary_label.setText("Events: --")
            if hasattr(self, "jump_to_event_btn"):
                self.jump_to_event_btn.setEnabled(False)
            if hasattr(self, "prev_event_btn"):
                self.prev_event_btn.setEnabled(False)
            if hasattr(self, "next_event_btn"):
                self.next_event_btn.setEnabled(False)
            return

        counts = {}
        for event in events:
            label = canonical_event_label(event.get("final_label") or event.get("rule_label") or "REVIEW")
            counts[label] = counts.get(label, 0) + 1

        first_event = self.get_first_detected_event()
        first_time = self.format_timestamp(float(first_event["start_sec"])) if first_event else "--:--:--"
        counts_text = " | ".join(f"{label}:{count}" for label, count in sorted(counts.items()))
        status = "focused" if self.auto_focus_applied else "detected"
        summary_text = f"Events: {len(events)} | First: {first_time} | {counts_text} | {status}"
        if summary_text != getattr(self, "_last_detection_summary_text", None):
            self._last_detection_summary_text = summary_text
            self.detection_summary_label.setText(summary_text)
        if hasattr(self, "jump_to_event_btn"):
            self.jump_to_event_btn.setEnabled(True)
        if hasattr(self, "prev_event_btn"):
            self.prev_event_btn.setEnabled(True)
        if hasattr(self, "next_event_btn"):
            self.next_event_btn.setEnabled(True)
 
    def generate_realistic_snoring(self, raw_snoring, airflow):
        """Generate realistic snoring vibration waveforms from single-point values
        
        Parameters:
        - raw_snoring: Single-point snoring intensity values from CSV
        - airflow: Airflow signal for synchronization
        
        Returns:
        - Realistic snoring waveform with vibration packets
        """
        sampling_rate = EXTERNAL_ARRAY_SAMPLE_RATE_HZ
        snoring_waveform = np.zeros_like(raw_snoring, dtype=np.float64)
        
        # Find snoring events (values above threshold)
        snoring_threshold = 5
        snoring_indices = np.where(raw_snoring > snoring_threshold)[0]
        
        if len(snoring_indices) == 0:
            return snoring_waveform
        
        # Group consecutive indices into snoring events
        events = []
        current_event = [snoring_indices[0]]
        
        for idx in snoring_indices[1:]:
            if idx - current_event[-1] <= 2:  # Consecutive within 2 samples
                current_event.append(idx)
            else:
                events.append(current_event)
                current_event = [idx]
        
        if current_event:
            events.append(current_event)
        
        # Generate vibration waveform for each snoring event
        for event in events:
            if len(event) < 1:
                continue
            
            start_idx = event[0]
            intensity = raw_snoring[start_idx]
            
            # Calculate burst duration based on intensity (0.5-2 seconds)
            duration_samples = int(np.clip(intensity / 20.0, 0.5, 2.0) * sampling_rate)
            
            # Frequency based on intensity (8-25 Hz)
            frequency = np.clip(8 + (intensity / 100.0) * 17, 8, 25)
            
            # Amplitude based on intensity (5-40)
            amplitude = np.clip(intensity / 2.0, 5, 40)
            
            # Generate vibration burst
            t = np.linspace(0, duration_samples / sampling_rate, duration_samples)
            
            # Create sine wave with multiple oscillations
            vibration = np.sin(2 * np.pi * frequency * t)
            
            # Apply Hanning envelope for natural fade-in/fade-out
            envelope = np.hanning(len(vibration))
            vibration *= envelope
            
            # Scale by amplitude
            vibration *= amplitude
            
            # Add noise for realism
            noise = np.random.normal(0, amplitude * 0.1, len(vibration))
            vibration += noise
            
            # Synchronize with airflow (boost during airflow peaks)
            if start_idx + duration_samples < len(airflow):
                airflow_segment = airflow[start_idx:start_idx + duration_samples]
                if len(airflow_segment) > 0:
                    airflow_normalized = (airflow_segment - np.mean(airflow_segment)) / (np.std(airflow_segment) + 1e-6)
                    vibration *= (1 + 0.3 * airflow_normalized)
            
            # Place the burst in the waveform
            end_idx = min(start_idx + duration_samples, len(snoring_waveform))
            actual_duration = end_idx - start_idx
            if actual_duration > 0:
                snoring_waveform[start_idx:end_idx] += vibration[:actual_duration]
        
        return snoring_waveform

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
                
                # Pad the smoothed data to match original length using original edge values.
                # Split the padding cleanly so even window sizes do not lose a sample.
                pad_total = len(y_data) - len(y_smooth_valid)
                pad_left = pad_total // 2
                pad_right = pad_total - pad_left
                left_part = y_data[:pad_left] if pad_left > 0 else y_data[:0]
                right_part = y_data[-pad_right:] if pad_right > 0 else y_data[:0]
                y_smooth = np.concatenate([left_part, y_smooth_valid, right_part])
                
                return y_smooth
            else:
                return y_data
        except Exception:
            # Fallback to original data if smoothing fails
            return y_data
    
    def get_signal_data_for_window(self, signal_name, time_window_seconds, time_offset=0):
        """Get signal data filtered for specific time window"""
        if self.psg_full_data is None or 'signals' not in self.psg_full_data:
            return np.array([]), np.array([])
        
        signals = self.psg_full_data['signals']
        
        if str(signal_name).strip() not in PLOTTED_SIGNAL_NAMES:
            return np.array([]), np.array([])
        
        # Resolve the actual signal column name using the shared chart mapping.
        signal_col = CHART_SIGNAL_MAPPING.get(signal_name)
        if signal_col is None:
            clean_name = signal_name.strip().rstrip(')')
            signal_col = signal_key_for_chart(clean_name)
        
        if signal_col not in signals:
            dbg(f"Warning: Signal {signal_name} (mapped to {signal_col}) not found in loaded data")
            return np.array([]), np.array([])
        
        if signal_col == "airflow":
            full_signal = self._get_airflow_signal_variant("display")
        elif signal_col == "thorax":
            full_signal = self._get_thorax_signal_variant("display")
        elif signal_col == "body_position":
            full_signal = self._get_body_position_signal()
        else:
            full_signal = signals[signal_col]

        if self.is_all_psg_mode():
            full_time = np.asarray(self.psg_full_data.get("time", []), dtype=float)
            sample_count = min(len(full_time), len(full_signal))
            if sample_count == 0:
                return np.array([]), np.array([])
            window_time, window_signal = self._smart_downsample(
                full_time[:sample_count],
                full_signal[:sample_count],
                max_points=2500,
            )
        else:
            window_time, window_signal = self._slice_signal_for_window(
                full_signal,
                time_window_seconds,
                time_offset,
            )

            window_time, window_signal = self._prepare_plot_data_for_window(
                window_time,
                window_signal,
                time_window_seconds,
            )

        if signal_col in SIGNAL_NO_GAP_FILL:
            # Sensor dropout: show the raw zero reading. Do not edge-fill;
            # edge filling would paint the dropout with the last real value.
            window_signal = np.where(np.isfinite(window_signal), window_signal, 0.0)

        if len(window_signal) == 0:
            return np.array([]), np.array([])

        num_samples = len(window_signal)
        expected_samples = int(round(time_window_seconds * EXTERNAL_ARRAY_SAMPLE_RATE_HZ))

        if signal_col == "airflow":
            nan_count = int(np.count_nonzero(~np.isfinite(window_signal)))
            zero_count = int(np.count_nonzero(window_signal == 0.0))
            dbg(
                f"DEBUG Airflow window offset={time_offset}s samples={num_samples}/{expected_samples} "
                f"nan={nan_count} zero={zero_count} "
                f"start={window_signal[:5]!r} end={window_signal[-5:]!r}"
            )
        
        dbg(f"{signal_name} window: {time_window_seconds}s, Samples: {num_samples}, Expected: {expected_samples}")
        
        return window_time, window_signal
    
    def get_spo2_data_for_window(self, time_window_seconds, time_offset=0):
        """Get SpO2 data filtered for specific time window"""
        if "SpO2" not in PLOTTED_SIGNAL_NAMES:
            return np.array([]), np.array([])

        if self.spo2_full_data is None or len(self.spo2_full_data[0]) == 0:
            return np.array([]), np.array([])
        
        full_time, full_spo2 = self.spo2_full_data

        if self.is_all_psg_mode():
            sample_count = min(len(full_time), len(full_spo2))
            if sample_count == 0:
                return np.array([]), np.array([])
            expected_samples = sample_count
            window_time, window_spo2 = self._smart_downsample(
                np.asarray(full_time[:sample_count], dtype=float),
                np.asarray(full_spo2[:sample_count], dtype=float),
                max_points=2500,
            )
        else:
            # Keep every window endpoint-exclusive: 60s at 10Hz must be exactly 600 samples.
            samples_per_second = EXTERNAL_ARRAY_SAMPLE_RATE_HZ
            expected_samples = int(round(time_window_seconds * samples_per_second))
            start_sample = int(round(time_offset * samples_per_second))
            end_sample = start_sample + expected_samples

            # Ensure we don't exceed data bounds
            start_sample = max(0, start_sample)
            end_sample = min(len(full_spo2), end_sample)

            # Extract the data for this window
            window_spo2 = full_spo2[start_sample:end_sample]

            num_samples = len(window_spo2)
            if num_samples == 0:
                return np.array([]), np.array([])

            # Calculate SpO2 statistics for this window
            self.calculate_spo2_statistics(window_spo2)

            # Generate time points: 0, 0.1, 0.2, ... up to time_window_seconds
            samples_per_second = EXTERNAL_ARRAY_SAMPLE_RATE_HZ
            expected_samples = int(round(time_window_seconds * samples_per_second))
            window_time = np.arange(num_samples) / samples_per_second

            window_time, window_spo2 = self._prepare_plot_data_for_window(
                window_time,
                window_spo2,
                time_window_seconds,
            )

            # Sensor dropout: show the raw zero reading. Do not edge-fill;
            # edge filling would paint the dropout with the last real value.
            window_spo2 = np.where(np.isfinite(window_spo2), window_spo2, 0.0)

        num_samples = len(window_spo2)
        if num_samples == 0:
            return np.array([]), np.array([])

        dbg(f"SpO2 window: {time_window_seconds}s, Samples: {num_samples}, Expected: {expected_samples}")
        
        return window_time, window_spo2

    def clear_airflow_event_items(self, plot_widget=None):
        """Remove automatic airflow drop boxes from the current Airflow plot."""
        remaining_items = []
        for item, owner_plot in getattr(self, "airflow_event_items", []):
            if plot_widget is not None and owner_plot is not plot_widget:
                remaining_items.append((item, owner_plot))
                continue
            try:
                if isinstance(item, pg.LinearRegionItem):
                    if hasattr(owner_plot, "removeItem"):
                        owner_plot.removeItem(item)
                elif isinstance(item, QLabel):
                    if not sip.isdeleted(item):
                        item.hide()
                        item.setGeometry(-1000, -1000, 1, 1)
                elif hasattr(item, "hide"):
                    item.hide()
                    item.setParent(None)
                    item.deleteLater()
            except Exception:
                pass

        self.airflow_event_items = remaining_items

    def calculate_airflow_event_drop(self, airflow, start_idx, end_idx, baseline_airflow):
        """Calculate drop ratio for an event, excluding the recovery sample at end_idx."""
        airflow = np.asarray(airflow, dtype=float)
        event_airflow = airflow[start_idx:end_idx]
        event_airflow = event_airflow[np.isfinite(event_airflow)]

        if len(event_airflow) == 0 or baseline_airflow <= 0:
            return 0.0

        event_mean = float(np.mean(event_airflow))
        drop_ratio = (float(baseline_airflow) - event_mean) / float(baseline_airflow)
        return max(0.0, drop_ratio)

    def classify_airflow_event(self, drop_ratio, duration_sec):
        """Classify an airflow event using the main detector's rules.

        The rules (10s minimum, HSA/OSA/CSA drop ranges, max duration) live in
        ONE place only: detect_apnea_from_airflow.py. If that module is not
        available, no events are classified at all - no local rule copies.
        """
        if _apnea_rules is None:
            return "NO_EVENT"
        try:
            return _apnea_rules.classify_rule_event(
                drop_ratio=float(drop_ratio),
                spo2_drop=0.0,
                snoring_mean=0.0,
                movement_mean=0.0,
                variability_score=0.0,
                duration_sec=float(duration_sec) if duration_sec is not None else None,
            )
        except Exception as classify_error:
            dbg(f"classify_airflow_event failed, defaulting to NO_EVENT: {classify_error}")
            return "NO_EVENT"

    def _build_airflow_navigation_events(self, airflow, fs=EXTERNAL_ARRAY_SAMPLE_RATE_HZ):
        """Build a reusable event list from the full airflow signal for navigation."""
        airflow = np.asarray(airflow, dtype=float)
        if len(airflow) == 0:
            return []

        baseline_airflow, baseline_occurrence = self.get_airflow_event_baseline(airflow)
        threshold = baseline_airflow
        min_samples = max(1, int(round(AIRFLOW_DROP_MIN_DURATION_SEC * fs)))
        events = []
        in_event = False
        start_index = None

        for index, value in enumerate(airflow):
            if not np.isfinite(value):
                continue

            if value < threshold:
                if not in_event:
                    in_event = True
                    start_index = index
            elif in_event:
                events.append((start_index, index))
                in_event = False
                start_index = None

        if in_event and start_index is not None:
            events.append((start_index, len(airflow) - 1))

        navigation_events = []
        for event_start, event_end in events:
            if event_end - event_start + 1 < min_samples:
                continue

            duration_sec = (event_end - event_start) / float(fs)
            drop_ratio = self.calculate_airflow_event_drop(
                airflow=airflow,
                start_idx=event_start,
                end_idx=event_end,
                baseline_airflow=baseline_airflow,
            )
            event_label = self.classify_airflow_event(drop_ratio, duration_sec)
            if event_label == "NO_EVENT":
                continue

            start_sec = event_start / float(fs)
            end_sec = min(len(airflow) / float(fs), (event_end + 1) / float(fs))
            display_label = canonical_event_label(event_label)
            navigation_events.append({
                "start_sec": start_sec,
                "end_sec": end_sec,
                "duration_sec": max(0.0, end_sec - start_sec),
                "final_label": display_label,
                "rule_label": event_label,
                "source": "airflow_threshold",
                "baseline_airflow": baseline_airflow,
                "baseline_occurrence": baseline_occurrence,
                "drop_percent": drop_ratio * 100.0,
            })

        return navigation_events

    def _build_windowed_airflow_navigation_events(
        self,
        airflow,
        fs=EXTERNAL_ARRAY_SAMPLE_RATE_HZ,
        window_seconds=60.0,
    ):
        """Build full-data events using the same local-window baseline style as visible markers."""
        airflow = np.asarray(airflow, dtype=float)
        if len(airflow) == 0:
            return []

        window_samples = max(1, int(round(float(window_seconds) * float(fs))))
        total_events = []

        for window_start in range(0, len(airflow), window_samples):
            window_end = min(len(airflow), window_start + window_samples)
            window_signal = airflow[window_start:window_end]
            if len(window_signal) == 0:
                continue

            baseline_airflow, baseline_occurrence = self.get_airflow_event_baseline(window_signal)
            threshold = baseline_airflow
            min_samples = max(1, int(round(AIRFLOW_DROP_MIN_DURATION_SEC * fs)))
            events = []
            in_event = False
            start_index = None

            for index, value in enumerate(window_signal):
                if not np.isfinite(value):
                    continue

                if value < threshold:
                    if not in_event:
                        in_event = True
                        start_index = index
                elif in_event:
                    events.append((start_index, index))
                    in_event = False
                    start_index = None

            if in_event and start_index is not None:
                events.append((start_index, len(window_signal) - 1))

            for event_start, event_end in events:
                if event_end - event_start + 1 < min_samples:
                    continue

                duration_sec = (event_end - event_start) / float(fs)
                drop_ratio = self.calculate_airflow_event_drop(
                    airflow=window_signal,
                    start_idx=event_start,
                    end_idx=event_end,
                    baseline_airflow=baseline_airflow,
                )
                event_label = self.classify_airflow_event(drop_ratio, duration_sec)
                if event_label == "NO_EVENT":
                    continue

                abs_start = (window_start + event_start) / float(fs)
                abs_end = min(len(airflow) / float(fs), (window_start + event_end + 1) / float(fs))
                display_label = canonical_event_label(event_label)
                total_events.append({
                    "start_sec": abs_start,
                    "end_sec": abs_end,
                    "duration_sec": max(0.0, abs_end - abs_start),
                    "final_label": display_label,
                    "rule_label": event_label,
                    "source": "airflow_window_threshold",
                    "baseline_airflow": baseline_airflow,
                    "baseline_occurrence": baseline_occurrence,
                    "drop_percent": drop_ratio * 100.0,
                })

        return total_events

    def get_available_navigation_events(self):
        """Return whichever event source is currently available for navigation."""
        return self._get_panel_detected_events()

    def mark_airflow_drop_events(
        self,
        plot_widget,
        x_data,
        y_data,
        detection_y_data=None,
        min_duration_sec=AIRFLOW_DROP_MIN_DURATION_SEC,
        fs=EXTERNAL_ARRAY_SAMPLE_RATE_HZ,
    ):
        """Mark Airflow events from below threshold until the next recovery threshold."""
        self.clear_airflow_event_items(plot_widget)
        if self.auto_rule_ai_result is not None:
            self.current_window_airflow_events = []
            self.emit_detected_events_panel()
            return

        x_data = np.asarray(x_data, dtype=float)
        y_data = np.asarray(y_data, dtype=float)
        if detection_y_data is None:
            detection_y_data = y_data
        detection_y_data = np.asarray(detection_y_data, dtype=float)
        self.current_window_airflow_events = []

        if len(x_data) == 0 or len(y_data) == 0 or len(detection_y_data) == 0:
            return

        point_count = min(len(x_data), len(y_data), len(detection_y_data))
        x_data = x_data[:point_count]
        y_data = y_data[:point_count]
        detection_y_data = detection_y_data[:point_count]
        min_samples = max(1, int(round(min_duration_sec * fs)))
        x_diffs = np.diff(x_data[np.isfinite(x_data)])
        plot_step = float(np.nanmedian(x_diffs)) if len(x_diffs) > 0 else (1.0 / float(fs))
        if not np.isfinite(plot_step) or plot_step <= 0:
            plot_step = 1.0 / float(fs)
        baseline_airflow, _ = self.get_airflow_event_baseline(detection_y_data)
        threshold = baseline_airflow

        events = []
        in_event = False
        start_index = None

        for index, value in enumerate(detection_y_data):
            if not np.isfinite(value):
                continue

            if value < threshold:
                if not in_event:
                    in_event = True
                    start_index = index
            elif in_event:
                events.append((start_index, index))
                in_event = False
                start_index = None

        if in_event and start_index is not None:
            events.append((start_index, point_count - 1))

        # Avoid drawing tiny one-sample regions if the trace starts just below threshold.
        events = [
            (event_start, event_end)
            for event_start, event_end in events
            if event_end - event_start + 1 >= min_samples
        ]

        for event_start, event_end in events:
            duration_sec = (event_end - event_start) / float(fs)
            drop_ratio = self.calculate_airflow_event_drop(
                airflow=detection_y_data,
                start_idx=event_start,
                end_idx=event_end,
                baseline_airflow=baseline_airflow,
            )
            event_label = self.classify_airflow_event(drop_ratio, duration_sec)
            if event_label == "NO_EVENT":
                continue

            if self.is_all_psg_mode():
                start_time_abs = float(x_data[event_start])
                end_time_abs = min(
                    float(x_data[point_count - 1]),
                    float(x_data[event_end]) + plot_step,
                )
            else:
                start_time_abs = self.current_time_offset + (event_start / float(fs))
                end_time_abs = min(
                    self.current_time_offset + (point_count / float(fs)),
                    self.current_time_offset + ((event_end + 1) / float(fs)),
                )
            selection_data = {
                "start_sec": start_time_abs,
                "end_sec": end_time_abs,
                "duration_sec": max(0.0, end_time_abs - start_time_abs),
                "final_label": canonical_event_label(event_label),
                "rule_label": event_label,
                "source": "airflow_window_threshold",
                "baseline_airflow": baseline_airflow,
                "drop_percent": drop_ratio * 100.0,
                "label": canonical_event_label(event_label),
                "start_time": start_time_abs,
                "end_time": end_time_abs,
            }
            self.current_window_airflow_events.append(selection_data)

            x1 = float(x_data[event_start])
            x2 = float(x_data[event_end]) + plot_step
            x2 = min(x2, float(self.get_effective_time_window_seconds()))
            if x2 <= x1:
                x2 = x1 + plot_step

            # Use a single color source so the same event type is not rendered
            # with different colors in different places.
            display_label = canonical_event_label(event_label)
            red, green, blue = self.get_label_rgb(display_label)
            alpha = 89

            region = pg.LinearRegionItem(
                values=[x1, x2],
                orientation="vertical",
                movable=False,
                brush=pg.mkBrush(red, green, blue, alpha),
            )
            region.setZValue(-10)
            plot_widget.addItem(region)

            self.airflow_event_items.append((region, plot_widget))

            view_box = plot_widget.getViewBox()
            if view_box is None:
                continue

            start_widget = plot_widget.mapFromScene(view_box.mapViewToScene(QPointF(x1, 0)))
            end_widget = plot_widget.mapFromScene(view_box.mapViewToScene(QPointF(x2, 0)))
            block = None
            for existing in plot_widget.selection_overlays:
                if existing and not sip.isdeleted(existing) and not existing.isVisible():
                    block = existing
                    break
            if block is None:
                block = QLabel(plot_widget)
                plot_widget.selection_overlays.append(block)

            block.setAlignment(Qt.AlignCenter)
            block.setText(display_label)
            block.setToolTip(
                f"{display_label}  |  {self.format_timestamp(start_time_abs)} → "
                f"{self.format_timestamp(end_time_abs)}  |  {self.format_duration(duration_sec)}"
            )
            block_style = f"""
                background-color: rgba({red}, {green}, {blue}, 0.35);
                border: none;
                border-radius: 0px;
                color: #1a1a1a;
                font-size: 9px;
                font-weight: 800;
                letter-spacing: 0.4px;
                padding: 0px 2px;
            """
            if getattr(block, "_applied_style", None) != block_style:
                block._applied_style = block_style
                block.setStyleSheet(block_style)
            block.selection_id = self._get_selection_id(selection_data)
            block.mousePressEvent = lambda event, ov=block, cn=getattr(plot_widget, "chart_name", "Airflow"): self.handle_overlay_click(event, ov, cn)
            block.mouseDoubleClickEvent = lambda event, ov=block, cn=getattr(plot_widget, "chart_name", "Airflow"): self.handle_overlay_double_click(event, ov, cn)
            placed = self._place_overlay_in_plot_area(
                plot_widget,
                block,
                start_widget.x(),
                end_widget.x(),
                fixed_height=15,
                min_width=24,
            )
            if not placed:
                continue
            block.raise_()
            block.show()

            self.airflow_event_items.append((block, plot_widget))

        # Keep the side-panel event list tied to the full detected dataset.
        self.emit_detected_events_panel()
    
    def calculate_spo2_statistics(self, spo2_data):
        """Calculate medical-grade SpO2 statistics"""
        if len(spo2_data) == 0:
            return

        spo2_array = np.asarray(spo2_data, dtype=float).reshape(-1)
        finite_mask = np.isfinite(spo2_array)
        if not np.any(finite_mask):
            self.spo2_statistics = {
                "mean": np.nan,
                "min": np.nan,
                "max": np.nan,
                "std": np.nan,
                "desaturation_events": 0,
                "total_points": len(spo2_array),
            }
            return

        self.spo2_statistics = {
            "mean": np.nanmean(spo2_array),
            "min": np.nanmin(spo2_array),
            "max": np.nanmax(spo2_array),
            "std": np.nanstd(spo2_array),
            "desaturation_events": int(np.sum(np.isfinite(spo2_array) & (spo2_array < 95))),
            "total_points": len(spo2_array),
        }
    
    def _channel_label_stylesheet(self, name, color, hidden=False):
        """Return a compact label stylesheet with a colored left border."""
        border_color = "#9ca3af" if hidden else (color or CHANNEL_COLORS.get(name, "#888888"))
        text_color = "#6b7280" if hidden else "#1e293b"
        bg_start = "#f9fafb" if hidden else "#ffffff"
        bg_mid = "#f8fafc" if hidden else "#f8fafc"
        bg_end = "#eef2ff" if hidden else "#f1f5f9"
        return f"""
            QLabel#chartSideLabel {{
                font-size: 10px;
                font-weight: 700;
                color: {text_color};
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 {bg_start},
                    stop: 0.5 {bg_mid},
                    stop: 1 {bg_end}
                );
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 5px 6px 5px 8px;
                text-align: center;
            }}
            QLabel#chartSideLabel:hover {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #dbeafe,
                    stop: 1 #bfdbfe
                );
                border: 1px solid #3b82f6;
                color: #1e40af;
            }}
        """

    def create_signal_chart(self, name, color, frequency, amplitude, offset, y_min=None, y_max=None):
        """Create a single signal trace chart with side label"""
        
        container = QWidget()
        container.setObjectName("signalChartContainer")
        container.setMinimumHeight(128)
        container.setMaximumHeight(128)
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
            }
        """)
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)  # Remove extra outer padding so plots start right under the card
        container_layout.setSpacing(0)  # Keep rows tight for better axis readability
        
        # Side Label
        label_frame = QFrame()
        label_frame.setFixedWidth(112) # Wider label box so longer names fit fully
        label_frame.setObjectName("labelFrame")
        # Apply professional styling to label frame
        label_frame.setStyleSheet(f"""
            QFrame#labelFrame {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #f8fafc,
                    stop: 0.5 #ffffff,
                    stop: 1 #f1f5f9
                );
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                margin: 2px;
                border-left: 2px solid {CHANNEL_COLORS.get(name, color)};
            }}
        """)
        label_h_layout = QHBoxLayout(label_frame)
        label_h_layout.setContentsMargins(0, 2, 0, 2)
        label_h_layout.setSpacing(0)
        
        label = QLabel(name)
        label.setObjectName("chartSideLabel")
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignCenter)
        # Make label clickable
        label.setCursor(Qt.PointingHandCursor)
        label.setStyleSheet(self._channel_label_stylesheet(name, color))
        # COMPLETELY REMOVE click event handler - labels should never hide graphs

        def scroll_to_chart(event=None, c=container):
            self.scroll_chart_container_into_view(c)
            if event is not None:
                event.accept()

        label_frame.mousePressEvent = scroll_to_chart
        label.mousePressEvent = scroll_to_chart

        label_h_layout.addWidget(label, stretch=1)

        zoom_col = QWidget()
        zoom_col_layout = QVBoxLayout(zoom_col)
        zoom_col_layout.setContentsMargins(0, 0, 0, 0)
        zoom_col_layout.setSpacing(2)
        zoom_col_layout.setAlignment(Qt.AlignVCenter | Qt.AlignHCenter)

        zoom_in_btn = QPushButton("+")
        zoom_out_btn = QPushButton("-")
        reset_btn = QPushButton("R")

        for btn in (zoom_in_btn, zoom_out_btn, reset_btn):
            btn.setFixedSize(22, 20)
            btn.setStyleSheet("""
                QPushButton {
                    background: #f1f5f9;
                    border: 1px solid #cbd5e1;
                    border-radius: 3px;
                    color: #475569;
                    font-size: 11px;
                    font-weight: 700;
                }
                QPushButton:hover {
                    background: #dbeafe;
                    border: 1px solid #3b82f6;
                    color: #1e40af;
                }
                QPushButton:pressed {
                    background: #93c5fd;
                    border: 1px solid #1d4ed8;
                    color: #1e3a8a;
                }
            """)
            btn.setCursor(Qt.PointingHandCursor)

        zoom_col_layout.addWidget(zoom_in_btn)
        zoom_col_layout.addWidget(zoom_out_btn)
        zoom_col_layout.addWidget(reset_btn)
        label_h_layout.addWidget(zoom_col, stretch=0)

        container_layout.addWidget(label_frame)

        # Plot Container
        plot_container = QWidget()
        plot_container.setObjectName("plotContainer")
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
                margin: 0px;
            }
        """)
        plot_container_layout = QVBoxLayout(plot_container)
        plot_container_layout.setContentsMargins(0, 0, 0, 0)
        plot_container_layout.setSpacing(0)

        # Resize grip sits as a direct child of the container, not inside a
        # layout, so labels and buttons cannot steal its mouse events.
        container.drag_graph_name = name
        container.is_resizing = False
        container.resize_start_height = None
        container.resize_start_y = None

        GRIP_HEIGHT = 12
        GRIP_WIDTH = 84
        # Double-click compact mode should match the normal startup height.
        MIN_HEIGHT = 128
        MAX_HEIGHT = 220

        resize_grip = QWidget(container)
        resize_grip.setObjectName("resizeGrip")
        resize_grip.setCursor(Qt.SizeVerCursor)
        resize_grip.setMouseTracking(True)
        resize_grip.hover_active = False
        resize_grip.setToolTip("Drag to change height • Double-click to compact/expand")
        container.resize_grip = resize_grip

        def _position_grip():
            """Reposition the grip on the container's bottom edge."""
            grip_width = GRIP_WIDTH if GRIP_WIDTH > 0 else container.width()
            resize_grip.setGeometry(
                3,
                max(0, container.height() - GRIP_HEIGHT - 3),
                max(40, grip_width),
                GRIP_HEIGHT,
            )
            resize_grip.raise_()

        container._position_resize_grip = _position_grip

        def _apply_container_height(delta_y):
            """Clamp and apply a new container height."""
            new_height = container.resize_start_height + delta_y
            new_height = max(MIN_HEIGHT, min(MAX_HEIGHT, new_height))
            container.setMinimumHeight(new_height)
            container.setMaximumHeight(new_height)
            container.updateGeometry()
            self.charts_widget.updateGeometry()

        def grip_mouse_press(event):
            if event.button() == Qt.LeftButton:
                container.is_resizing = True
                container.resize_start_height = container.height()
                container.resize_start_y = event.globalY()
                resize_grip.update()
                event.accept()

        def grip_mouse_move(event):
            if container.is_resizing and event.buttons() == Qt.LeftButton:
                _apply_container_height(event.globalY() - container.resize_start_y)
                event.accept()

        def grip_mouse_release(event):
            if container.is_resizing:
                container.is_resizing = False
                resize_grip.update()
                event.accept()

        def grip_double_click(event):
            """Double-click toggles between compact and expanded height."""
            if event.button() != Qt.LeftButton:
                return
            midpoint = (MIN_HEIGHT + MAX_HEIGHT) // 2
            target = MAX_HEIGHT if container.height() < midpoint else MIN_HEIGHT
            container.setMinimumHeight(target)
            container.setMaximumHeight(target)
            container.updateGeometry()
            self.charts_widget.updateGeometry()
            event.accept()

        def grip_enter(event):
            resize_grip.hover_active = True
            resize_grip.update()

        def grip_leave(event):
            resize_grip.hover_active = False
            resize_grip.update()

        def grip_paint(event):
            painter = QPainter(resize_grip)
            painter.setRenderHint(QPainter.Antialiasing)
            grip_w = resize_grip.width()
            grip_h = resize_grip.height()
            center_y = grip_h // 2
            center_x = grip_w // 2
            is_active = resize_grip.hover_active or container.is_resizing

            if is_active:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(59, 130, 246, 30))
                painter.drawRoundedRect(0, 0, grip_w, grip_h, 4, 4)

            line_color = QColor(37, 99, 235, 235) if is_active else QColor(100, 116, 139, 120)
            grip_pen = QPen(line_color)
            grip_pen.setWidth(2)
            grip_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(grip_pen)
            for offset_y in (-3, 0, 3):
                painter.drawLine(center_x - 13, center_y + offset_y,
                                 center_x + 13, center_y + offset_y)

            painter.end()

        resize_grip.mousePressEvent = grip_mouse_press
        resize_grip.mouseMoveEvent = grip_mouse_move
        resize_grip.mouseReleaseEvent = grip_mouse_release
        resize_grip.mouseDoubleClickEvent = grip_double_click
        resize_grip.enterEvent = grip_enter
        resize_grip.leaveEvent = grip_leave
        resize_grip.paintEvent = grip_paint
        _position_grip()
        
        # Plot Widget with custom ViewBox
        plot_widget = pg.PlotWidget(viewBox=CustomViewBox())
        plot_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        plot_widget.setAlignment(Qt.AlignCenter)
        # Grid: identical across all charts - only vertical time lines.
        # No horizontal lines, so every container looks the same.
        # Time lines matter because apnea/hypopnea rules are >=10 seconds
        # and the scorer needs an easy visual reference for duration.
        plot_widget.showGrid(x=False, y=False)
        plot_widget.getAxis('bottom').setGrid(56)     # ~22% - vertical time lines
        plot_widget.getAxis('left').setGrid(False)    # horizontal lines off
        
        # Disable all auto-range and auto-visibility for stable PSG monitor behavior
        plot_widget.enableAutoRange(False)
        plot_widget.setAutoVisible(y=False)
        
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
        
        signal_name = name.strip()
        is_auto_range_chart = signal_name in AUTO_RANGE_SIGNAL_NAMES

        # Use passed medical range parameters if provided, otherwise use defaults.
        # Auto-range charts must not be clamped to these values.
        if y_min is not None and y_max is not None:
            initial_y_min, initial_y_max = y_min, y_max
        else:
            initial_y_min, initial_y_max = SIGNAL_Y_RANGES.get(signal_name, (0, 100))

        # Restrict zoom to Y-axis only (amplitude zoom) - disable X-axis to prevent sliding
        plot_widget.setMouseEnabled(x=False, y=True)

        # Disable auto-range and set fixed limits
        plot_widget.enableAutoRange(axis='y', enable=False)
        if is_auto_range_chart:
            # Start with a lock on the initial range, then relock to data once
            # the chart's actual signal values are loaded.
            self._lock_auto_axis(plot_widget, initial_y_min, initial_y_max)
        else:
            # Fixed medical range: give the chart a small breathing room so the
            # top and bottom tick labels do not get clipped at the border.
            fixed_span = max(float(initial_y_max) - float(initial_y_min), 1e-6)
            edge_margin = fixed_span * 0.06
            visible_y_min = float(initial_y_min) - edge_margin
            visible_y_max = float(initial_y_max) + edge_margin
            try:
                plot_widget.setYRange(visible_y_min, visible_y_max, padding=0)
            except TypeError:
                plot_widget.setRange(yRange=[visible_y_min, visible_y_max], padding=0)
            try:
                plot_widget.setLimits(yMin=visible_y_min, yMax=visible_y_max)
            except TypeError:
                # Try alternative method for older pyqtgraph versions
                plot_widget.setLimits(yMin=visible_y_min, yMax=visible_y_max)

        plot_widget.original_y_min = initial_y_min
        plot_widget.original_y_max = initial_y_max
        if is_auto_range_chart:
            plot_widget.zoom_y_min_limit = initial_y_min
            plot_widget.zoom_y_max_limit = initial_y_max
            plot_widget.zoom_y_min_span = max(float(initial_y_max) - float(initial_y_min), 1e-6) * 0.1
            plot_widget.zoom_y_max_span = max(float(initial_y_max) - float(initial_y_min), 1e-6) * 2.0
        else:
            plot_widget.zoom_y_min_limit = initial_y_min
            plot_widget.zoom_y_max_limit = initial_y_max
            base_y_span = max(float(initial_y_max) - float(initial_y_min), 1e-6)
            plot_widget.zoom_y_min_span = max(base_y_span * 0.5, 1.0)
            plot_widget.zoom_y_max_span = base_y_span
            
        # Set X-axis to show time values based on current time window
        bottom_axis = plot_widget.getAxis('bottom')
        bottom_axis.setStyle(showValues=True)  # Show time values
        bottom_axis.setHeight(20)  # Keep the axis compact so it hugs the bottom edge
        
        left_axis = plot_widget.getAxis('left')
        left_axis.setStyle(showValues=True)   # Show Y-axis values
        
        # Reduce font size of axis tick labels
        from PyQt5.QtGui import QFont
        small_font = QFont()
        small_font.setPointSize(7)  # Compact tick labels with slightly better readability
        bottom_axis.setTickFont(small_font)  # X-axis numbers
        left_axis.setTickFont(small_font)    # Y-axis numbers
        
        axis_width = 28
        left_axis.setWidth(axis_width)
        
        # Ensure axis ticks are visible
        bottom_axis.setPen('k')  # Black color for visibility
        left_axis.setPen('k')    # Black color for visibility
        bottom_axis.setTextPen('k')  # Black text for visibility
        left_axis.setTextPen('k')    # Black text for visibility

        # Remove any extra internal plot padding so the x-axis sits flush at the bottom
        try:
            plot_item = plot_widget.getPlotItem()
            if hasattr(plot_item, 'layout') and plot_item.layout is not None:
                plot_item.layout.setContentsMargins(0, 0, 0, 0)
                if hasattr(plot_item.layout, 'setHorizontalSpacing'):
                    plot_item.layout.setHorizontalSpacing(0)
                if hasattr(plot_item.layout, 'setVerticalSpacing'):
                    plot_item.layout.setVerticalSpacing(0)
        except Exception:
            pass
        
        # Set X-axis range to the visible window (clamped to available data)
        visible_window = self.get_effective_time_window_seconds()
        plot_widget.setXRange(0, visible_window, padding=0)
        
        # Set time window limits on CustomViewBox to enforce zoom constraints
        vb = plot_widget.getViewBox()
        if hasattr(vb, "owner_plot_widget"):
            vb.owner_plot_widget = plot_widget
        if hasattr(vb, 'set_time_window_limits'):
            vb.set_time_window_limits(0, visible_window)
        
        plot_widget.setMouseEnabled(x=False, y=True)
        plot_widget.hideButtons()  # Hide the 'A' button
        zoom_in_btn.clicked.connect(lambda: self.zoom_vertical(plot_widget, 0.8))
        zoom_out_btn.clicked.connect(lambda: self.zoom_vertical(plot_widget, 1.2))
        reset_btn.clicked.connect(lambda: self.reset_zoom(plot_widget))

        container.wheelEvent = lambda event, pw=plot_widget: self.handle_container_wheel_zoom(event, pw)
        label_frame.wheelEvent = lambda event, pw=plot_widget: self.handle_container_wheel_zoom(event, pw)
        label.wheelEvent = lambda event, pw=plot_widget: self.handle_container_wheel_zoom(event, pw)
        zoom_col.wheelEvent = lambda event, pw=plot_widget: self.handle_container_wheel_zoom(event, pw)
        plot_container.wheelEvent = lambda event, pw=plot_widget: self.handle_container_wheel_zoom(event, pw)
        
        # Keep the plot anchored to the top so the signal begins immediately under the card
        plot_container_layout.setAlignment(plot_widget, Qt.AlignTop)
        
        # Generate signal data
        if name.strip() == "SpO2":
            # Get SpO2 data for current time window
            # Get filtered data for current time window
            x, y = self.get_spo2_data_for_window(visible_window, self.current_time_offset)

            if len(x) > 0 and len(y) > 0:
                # Use real SpO2 data as-is (no artificial baseline correction)
                print(f"Using real SpO2 data: {len(y)} points, range: {np.min(y):.1f}-{np.max(y):.1f}")
        else:
            x, y = self.get_signal_data_for_window(name, visible_window, self.current_time_offset)
            if len(x) > 0 and len(y) > 0:
                print(f"Using real {name} data: {len(y)} points, range: {np.min(y):.1f}-{np.max(y):.1f}")
        
        # Plot the signal and store reference for line visibility control
        pen = pg.mkPen(color=color, width=1.5)
        
        # Plot all graphs as normal line plots (no step ladder, no fill)
        # Use connect='finite' so NaN gaps do not draw as vertical connector lines.
        if name.strip() == "Body Position":
            self._configure_body_position_axis(plot_widget)
            x_step, y_step = self._build_body_position_step_data(x, y)
            plot_curve = plot_widget.plot(x_step, y_step, pen=pen, fill=None, connect='finite', stepMode=True)
        else:
            plot_curve = plot_widget.plot(x, y, pen=pen, fill=None, connect='finite')

        if name.strip() in AUTO_RANGE_SIGNAL_NAMES:
            fallback_min, fallback_max = SIGNAL_Y_RANGES.get(name.strip(), (0.0, 100.0))
            auto_y_min, auto_y_max = self._auto_axis_range_from_values(y, fallback_min, fallback_max)
            self._lock_auto_axis(plot_widget, auto_y_min, auto_y_max)
        if name.strip() == "Airflow":
            _event_x, detection_y = self.get_airflow_detection_data_for_window(
                visible_window,
                self.current_time_offset,
            )
            self.mark_airflow_drop_events(
                plot_widget,
                x,
                y,
                detection_y_data=detection_y,
            )

        # SpO2 labels must be refreshed even when the new file has no SpO2
        # samples. add_spo2_value_labels() is also the only place that removes
        # the previous frame's TextItems, so skipping the call would leave old
        # numbers floating over recordings that no longer have an SpO2 trace.
        if name.strip() == "SpO2":
            self.add_spo2_value_labels(plot_widget, x, y, visible_window)
            if len(x) > 0 and len(y) > 0:
                print(f"SpO2 value labels drawn for {visible_window}s time window")

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
        plot_widget.mouseDoubleClickEvent = lambda event, pw=plot_widget: self.custom_mouse_double_click(event, pw)
        
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

            if original_resize:
                original_resize(event)
            if hasattr(container, '_position_resize_grip'):
                container._position_resize_grip()
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
                font-size: 10px;
                font-weight: bold;
                padding: 4px 8px;
                text-align: center;
            }
        """)
        selection_overlay.setVisible(False)
        # This is only a visual preview; it must not intercept mouse events.
        selection_overlay.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        
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
        }
        
        # Hide the container
        container.hide()
        
        # Update label to show it's hidden
        label.setText(f"{graph_name} (Hidden)")
        label.setStyleSheet("""
            QLabel#chartSideLabel {
                font-size: 10px;
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
            label.setStyleSheet(self._channel_label_stylesheet(graph_name, graph_data.get("color", "#9ca3af"), hidden=True))
        
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
                    font-size: 10px;
                    font-weight: bold;
                    color: #4b5563;
                    background-color: #f9fafb;
                    border: 1px solid #e5e7eb;
                    border-radius: 4px;
                    padding: 2px;
                }
            """)
            print(f"Graph line '{chart_name}' shown")
        else:
            # Hide the line
            plot_curve.setVisible(False)
            plot_curve._is_hidden = True
            label.setStyleSheet("""
                QLabel#chartSideLabel {
                    font-size: 10px;
                    font-weight: bold;
                    color: #9ca3af;
                    background-color: #f8fafc;
                    border: 1px solid #d1d5db;
                    border-radius: 4px;
                    padding: 2px;
                }
            """)
            print(f"Graph line '{chart_name}' hidden")
    
    def zoom_vertical(self, plot_widget, zoom_factor):
        """Zoom in/out vertically on the plot"""
        # Get current Y range
        current_range = plot_widget.getViewBox().viewRange()
        y_min, y_max = current_range[1]
        
        # Anchor zoom around the visible waveform strip instead of empty space.
        center = (y_min + y_max) / 2
        if hasattr(plot_widget, 'plot_curve'):
            x_data, y_data = plot_widget.plot_curve.getData()
            if x_data is not None and y_data is not None:
                x_values = np.asarray(x_data, dtype=float)
                y_values = np.asarray(y_data, dtype=float)
                min_len = min(len(x_values), len(y_values))
                x_values = x_values[:min_len]
                y_values = y_values[:min_len]
                x_min, x_max = current_range[0]
                visible_mask = (
                    np.isfinite(x_values)
                    & np.isfinite(y_values)
                    & (x_values >= x_min)
                    & (x_values <= x_max)
                )
                visible_y = y_values[visible_mask]
                if visible_y.size > 0:
                    center = float(np.median(visible_y))
        current_range_size = y_max - y_min
        
        # Calculate new range size
        new_range_size = current_range_size * zoom_factor
        
        # Calculate new bounds
        new_y_min = center - new_range_size / 2
        new_y_max = center + new_range_size / 2
        
        # Get chart name to apply proper limits
        chart_name = getattr(plot_widget, 'chart_name', '')
        y_min_limit, y_max_limit = SIGNAL_Y_RANGES.get(chart_name.strip(), (0, 100))
        
        new_y_min, new_y_max = self._clamp_y_zoom_range(
            plot_widget,
            new_y_min,
            new_y_max,
            y_min_limit,
            y_max_limit,
        )
            
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

    def zoom_vertical_at_ratio(self, plot_widget, zoom_factor, anchor_ratio):
        """Zoom vertically while keeping the chosen relative Y position visually anchored."""
        current_range = plot_widget.getViewBox().viewRange()
        y_min, y_max = current_range[1]
        current_range_size = y_max - y_min
        if current_range_size <= 0:
            return

        anchor_ratio = max(0.0, min(1.0, float(anchor_ratio)))
        anchor_y = y_max - (current_range_size * anchor_ratio)
        new_y_min = anchor_y - ((anchor_y - y_min) * zoom_factor)
        new_y_max = anchor_y + ((y_max - anchor_y) * zoom_factor)

        chart_name = getattr(plot_widget, 'chart_name', '')
        y_min_limit, y_max_limit = SIGNAL_Y_RANGES.get(chart_name.strip(), (0, 100))

        new_y_min, new_y_max = self._clamp_y_zoom_range(
            plot_widget,
            new_y_min,
            new_y_max,
            y_min_limit,
            y_max_limit,
        )

        try:
            plot_widget.setYRange(new_y_min, new_y_max)
        except TypeError:
            plot_widget.setRange(yRange=[new_y_min, new_y_max])

        plot_widget.zoom_y_range = (new_y_min, new_y_max)
        print(f"Stored anchored zoom range for {chart_name}: {new_y_min} - {new_y_max}")

    def handle_container_wheel_zoom(self, event, plot_widget):
        """Route wheel zoom from non-plot container areas into centered graph zoom."""
        delta = event.angleDelta().y() if hasattr(event, "angleDelta") else event.delta()
        zoom_factor = 0.96 if delta > 0 else 1.04
        self.zoom_vertical_at_ratio(plot_widget, zoom_factor, 0.5)
        event.accept()

    def _clamp_y_zoom_range(self, plot_widget, new_y_min, new_y_max, fallback_min, fallback_max):
        """Keep Y zoom within the graph's intended medical display bounds."""
        y_min_limit = getattr(plot_widget, "zoom_y_min_limit", fallback_min)
        y_max_limit = getattr(plot_widget, "zoom_y_max_limit", fallback_max)
        if y_max_limit <= y_min_limit:
            return new_y_min, new_y_max

        base_span = max(float(y_max_limit) - float(y_min_limit), 1e-6)
        min_span = float(getattr(plot_widget, "zoom_y_min_span", base_span * 0.5))
        max_span = float(getattr(plot_widget, "zoom_y_max_span", base_span))
        min_span = max(1e-6, min(min_span, base_span))
        max_span = max(min_span, min(max_span, base_span))

        current_span = max(float(new_y_max) - float(new_y_min), 1e-6)
        target_span = min(max(current_span, min_span), max_span)
        center = (float(new_y_min) + float(new_y_max)) / 2.0
        new_y_min = center - target_span / 2.0
        new_y_max = center + target_span / 2.0

        if new_y_min < y_min_limit:
            shift = y_min_limit - new_y_min
            new_y_min += shift
            new_y_max += shift
        if new_y_max > y_max_limit:
            shift = new_y_max - y_max_limit
            new_y_min -= shift
            new_y_max -= shift

        if new_y_min < y_min_limit:
            new_y_min = y_min_limit
        if new_y_max > y_max_limit:
            new_y_max = y_max_limit

        if new_y_max - new_y_min < min_span:
            new_y_max = min(y_max_limit, new_y_min + min_span)
            new_y_min = max(y_min_limit, new_y_max - min_span)

        return new_y_min, new_y_max
    
    def reset_zoom(self, plot_widget):
        """Reset zoom to original medical standard range"""
        # Get the chart name from the plot widget
        chart_name = getattr(plot_widget, 'chart_name', '')
        clean_name = chart_name.strip()
        if clean_name in AUTO_RANGE_SIGNAL_NAMES:
            # FIX: this used to call get_signal_auto_axis_range(), which
            # returns the WHOLE-RECORDING cached range - not the tight
            # per-window range the redraw loop now uses. Pressing Reset would
            # therefore snap Thorax/Airflow back to the old too-wide range
            # (looking flat) until the next scroll/redraw recomputed it.
            # Recompute from the currently visible window instead, same as
            # the redraw path, so Reset matches what's actually on screen.
            _reset_x, reset_y = self.get_signal_data_for_window(
                clean_name, self.get_effective_time_window_seconds(), self.current_time_offset
            )
            fallback_min, fallback_max = SIGNAL_Y_RANGES.get(clean_name, (0.0, 100.0))
            raw_min, raw_max = self._windowed_axis_range_from_values(
                reset_y, fallback_min, fallback_max
            )
            # Reset means "forget the held range and re-fit from scratch".
            plot_widget.stable_y_range = None
            y_min, y_max = self._stable_axis_range(plot_widget, raw_min, raw_max)
            plot_widget.stable_y_range = (y_min, y_max)
            self._lock_auto_axis(plot_widget, y_min, y_max)
            self._pin_axis_tick_spacing(plot_widget, y_min, y_max)
        else:
            y_min, y_max = SIGNAL_Y_RANGES.get(clean_name, (0, 100))

        try:
            plot_widget.setYRange(y_min, y_max)
       
            plot_widget.zoom_y_range = None
            print(f"Reset zoom range for {chart_name}")
        except TypeError:
          
            plot_widget.setRange(yRange=[y_min, y_max])
           
            plot_widget.zoom_y_range = None
            print(f"Reset zoom range for {chart_name}")
    
    def forward_playback(self):
        """Fast forward playback"""
        print(f"Forward button clicked - Playing: {self.is_playing}")
        if self.is_playing:
            # Jump forward by current time window
            self.current_time = self.current_time.addSecs(self.current_time_window)
            
            #  UPDATE OFFSET (never scroll past the end of the recording)
            self.current_time_offset = min(
                self._get_playback_max_offset(),
                self.current_time_offset + self.current_time_window,
            )

            #  FORCE VIEWBOX UPDATE AND PLOT REDRAW
            end = self.get_effective_time_window_seconds()
            for i in range(self.charts_layout.count()):
                container = self.charts_layout.itemAt(i).widget()
                if hasattr(container, 'plot_widget'):
                    pw = container.plot_widget
                    
                    # Force X-axis range update
                    start = 0
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
        dbg(f"DEBUG: create_spo2_markers_and_labels called with {len(x_data)} points")
        
        # Add value labels on the graph (positioned exactly on data points)
        self.add_spo2_value_labels(plot_widget, x_data, y_data, self.get_effective_time_window_seconds())
        
        dbg(f"Created SpO2 value labels for {self.current_time_window}s time window")
    
    def _spo2_label_mode(self):
        """Return "raw", "avg" or "none" for the CURRENTLY SELECTED window.

        The mode is decided from self.current_time_window (the value the Time
        Window dropdown set), not from the visible span. Near the end of a
        recording the visible span gets clamped to the data that is left, and
        the labels must not switch off just because the last window is short.
        """
        if self.is_all_psg_mode():
            return "none"
        try:
            selected = int(round(float(self.current_time_window)))
        except Exception:
            return "none"
        if selected in SPO2_RAW_LABEL_WINDOWS_SEC:
            return "raw"
        if selected in SPO2_AVG_LABEL_WINDOWS_SEC:
            return "avg"
        return "none"

    def _spo2_label_bucket_seconds(self):
        """Length of one averaging bucket, in seconds of the recording.

        Derived from the selected window and then snapped to a round value so
        the grid never shifts when the visible span gets clamped near the end
        of the recording.
        """
        try:
            window = float(self.current_time_window)
        except Exception:
            window = 120.0
        target = max(1e-6, window / float(max(1, int(SPO2_LABEL_TARGET_COUNT))))
        return float(min(SPO2_LABEL_BUCKET_STEPS_SEC, key=lambda step: abs(step - target)))

    def _spo2_label_time_offset(self):
        """Absolute recording time of x = 0 in the current view."""
        try:
            return max(0.0, float(self.current_time_offset))
        except Exception:
            return 0.0

    def _spo2_label_points(self, x_displayed, y_displayed, y_values, time_window):
        """Return [(x_pos, y_pos, text), ...] for the SpO2 value labels.

        Every label sits ON the trace and moves with it - nothing is ever drawn
        below the line, which read as if the numbers had fallen off the graph.

        "raw" mode labels every sample (the 10s reading view, unchanged).
        "avg" mode splits the window into equal time buckets and labels each
        bucket with its MEAN SpO2, anchored to a real point on the curve.
        """
        mode = self._spo2_label_mode()
        if mode == "none":
            return []

        n = min(len(x_displayed), len(y_displayed), len(y_values))
        if n == 0:
            return []

        x_displayed = np.asarray(x_displayed, dtype=float)[:n]
        y_displayed = np.asarray(y_displayed, dtype=float)[:n]
        y_values = np.asarray(y_values, dtype=float)[:n]
        # Zero is the oximeter's no-signal value, not a measured SpO2 reading.
        spo2_floor = float(SIGNAL_VALID_RANGES.get("spo2", (50.0, 100.0))[0])

        # --- raw per-sample labels ------------------------------------------
        if mode == "raw":
            if n > SPO2_LABEL_MAX_RAW_POINTS:
                return []
            points = []
            for i in range(n):
                if not (np.isfinite(y_values[i]) and np.isfinite(y_displayed[i])
                        and np.isfinite(x_displayed[i])):
                    continue
                points.append((
                    float(x_displayed[i]),
                    float(y_displayed[i]),
                    f"{int(round(float(y_values[i])))}",
                ))
            return points

        # --- averaged labels on a FIXED recording-time grid --------------------
        # The buckets are pinned to absolute seconds of the recording, not to
        # slots inside the visible window. A label therefore belongs to one
        # fixed stretch of the signal: while playback scrolls, it keeps its
        # value and travels right-to-left with the waveform it describes,
        # exactly like the annotations in a clinical PSG viewer. Slot-based
        # buckets did the opposite - the numbers stood still and their values
        # changed under you.
        bucket_seconds = self._spo2_label_bucket_seconds()
        offset = self._spo2_label_time_offset()
        absolute_times = x_displayed + offset

        first_bucket = int(np.floor(absolute_times[0] / bucket_seconds))
        last_bucket = int(np.floor(absolute_times[-1] / bucket_seconds))

        points = []
        for bucket in range(first_bucket, last_bucket + 1):
            low = bucket * bucket_seconds
            high = low + bucket_seconds

            # Only label buckets that are fully on screen. A half-visible bucket
            # would average a shrinking slice and its number would drift as it
            # scrolled in - the very flicker we are removing.
            if low < absolute_times[0] - 1e-9 or high > absolute_times[-1] + 1e-9:
                continue

            start = int(np.searchsorted(absolute_times, low, side="left"))
            end = int(np.searchsorted(absolute_times, high, side="left"))
            if end <= start:
                continue

            values = y_values[start:end]
            drawn = y_displayed[start:end]
            times = x_displayed[start:end]
            usable = np.isfinite(values) & np.isfinite(drawn) & np.isfinite(times)
            if not usable.any():
                continue

            values = values[usable]
            drawn = drawn[usable]
            times = times[usable]

            # Average real readings only, so a bucket straddling a dropout edge
            # shows its real value rather than a mixed value. An all-dropout
            # bucket is labelled 0, the honest no-signal reading.
            real = values >= spo2_floor
            if not real.any():
                middle = int((values.size - 1) // 2)
                points.append((float(times[middle]), float(drawn[middle]), "0"))
                continue
            values = values[real]
            drawn = drawn[real]
            times = times[real]

            mean_value = float(np.mean(values))

            # Anchor the number to a REAL point on the trace instead of to the
            # bucket's mean position. When a bucket straddles a step (SpO2 is a
            # staircase, not a smooth curve) the mean level sits in the gap
            # between two plateaus and the label looks like it has dropped off
            # the line. Pick the sample whose level is closest to the mean, and
            # among equally close ones the one nearest the middle of the bucket,
            # so the label always rides the curve.
            distance = np.abs(values - mean_value)
            closest = float(np.min(distance))
            candidates = np.flatnonzero(distance <= closest + 1e-9)
            middle = (values.size - 1) / 2.0
            anchor = int(candidates[int(np.argmin(np.abs(candidates - middle)))])

            points.append((
                float(times[anchor]),
                float(drawn[anchor]),
                f"{int(round(mean_value))}",
            ))

            # Optional nadir label - still placed ON the trace, never below it.
            if SPO2_LABEL_MARK_NADIR_DROP > 0:
                lowest = int(np.argmin(values))
                if mean_value - float(values[lowest]) >= SPO2_LABEL_MARK_NADIR_DROP:
                    points.append((
                        float(times[lowest]),
                        float(drawn[lowest]),
                        f"{int(round(float(values[lowest])))}",
                    ))

        return points

    def add_spo2_value_labels(self, plot_widget, x_data, y_data, time_window):
        """Draw the SpO2 value labels for the current window.

        Playback re-draws this ~20 times a second, so the TextItems are reused
        (moved and re-texted) instead of being destroyed and rebuilt every
        frame. That is what lets the numbers glide with the trace rather than
        blink in place.
        """
        if not hasattr(plot_widget, 'value_labels'):
            plot_widget.value_labels = []

        # If this window has no usable SpO2 samples, clear any old labels and
        # stop. The previous recording's curve object can still exist briefly,
        # so we must decide from the fresh x/y data first instead of consulting
        # plot_curve here.
        x_displayed = np.asarray(x_data, dtype=float).reshape(-1)
        y_displayed = np.asarray(y_data, dtype=float).reshape(-1)
        if x_displayed.size == 0 or y_displayed.size == 0 or not np.isfinite(y_displayed).any():
            while plot_widget.value_labels:
                stale = plot_widget.value_labels.pop()
                try:
                    plot_widget.removeItem(stale)
                except Exception:
                    pass
            return

        # Get the actual displayed data (scaled if axis properties are applied).
        # When the current curve matches the fresh window data, use it; otherwise
        # fall back to the raw x/y data for this frame.
        if hasattr(plot_widget, 'axis_properties') and hasattr(plot_widget, 'plot_curve'):
            try:
                current_data = plot_widget.plot_curve.getData()
                if (
                    current_data[0] is not None
                    and current_data[1] is not None
                    and len(current_data[0]) == x_displayed.size
                ):
                    x_displayed = np.asarray(current_data[0], dtype=float).reshape(-1)
                    y_displayed = np.asarray(current_data[1], dtype=float).reshape(-1)
            except Exception:
                pass
        label_points = self._spo2_label_points(x_displayed, y_displayed, y_data, time_window)

        # Drop any surplus items from the previous frame.
        while len(plot_widget.value_labels) > len(label_points):
            stale = plot_widget.value_labels.pop()
            try:
                plot_widget.removeItem(stale)
            except Exception:
                pass

        if not label_points:
            return

        from PyQt5.QtGui import QFont
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)

        # Every number sits just above the trace and moves with it.
        offset_above = 0.35

        for index, (x_pos, y_pos, label_text) in enumerate(label_points):
            if index < len(plot_widget.value_labels):
                text_item = plot_widget.value_labels[index]
                text_item.setText(label_text)
            else:
                text_item = pg.TextItem(
                    text=label_text,
                    color=(122, 29, 29),
                    anchor=(0.5, 1.0),
                    border=pg.mkPen((255, 255, 255, 0)),
                    # Keep the trace visible underneath the label.
                    fill=pg.mkBrush(255, 255, 255, 0),
                )
                
                # Set font for better visibility while maintaining positioning
                from PyQt5.QtGui import QFont
                font = QFont()
                font.setPointSize(12)
                font.setBold(True)
                text_item.setFont(font)
                text_item.setAnchor((0.5, 1.0))
                text_item.setZValue(1000)
                plot_widget.addItem(text_item)
                plot_widget.value_labels.append(text_item)
            text_item.setPos(x_pos, y_pos + offset_above)
    
    
    def on_mouse_clicked(self, event, plot_widget):
        """Handle mouse click for area selection and label removal"""
        self.clear_viewbox_rubber_band(plot_widget)
        chart_name = plot_widget.chart_name.strip() if hasattr(plot_widget, "chart_name") else ""
        if not self._selection_allowed_for_chart(chart_name):
            if hasattr(event, "accept"):
                event.accept()
            return
        if event.button() == Qt.LeftButton:
            widget_pos = event.pos()
            widget_rect = plot_widget.rect()
            if not widget_rect.contains(widget_pos):
                if hasattr(event, "accept"):
                    event.accept()
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
        if hasattr(event, "accept"):
            event.accept()
    
    def custom_mouse_press(self, event, plot_widget):
        """Custom mouse press handler for better selection handling"""
        self.clear_viewbox_rubber_band(plot_widget)
        # Handle right mouse button for y-axis context menu on all charts
        if event.button() == Qt.RightButton:
            self.handle_right_click(event, plot_widget)
            if hasattr(event, "accept"):
                event.accept()
            return

        chart_name = plot_widget.chart_name.strip() if hasattr(plot_widget, "chart_name") else ""
        if not self._selection_allowed_for_chart(chart_name):
            if hasattr(event, "accept"):
                event.accept()
            return
            
        # Only handle left mouse button for area selection
        if event.button() != Qt.LeftButton:
            if hasattr(event, "accept"):
                event.accept()
            return
            
        # Prevent new selection only if a menu is genuinely open.
        # A stale reference used to block LEFT clicks forever while RIGHT clicks
        # still worked because they were handled before this guard.
        open_menu = getattr(self, "active_context_menu", None)
        if open_menu is not None:
            try:
                if open_menu.isVisible():
                    if hasattr(event, "accept"):
                        event.accept()
                    return
            except RuntimeError:
                pass
            self.active_context_menu = None
            
        # Handle left click directly
        widget_pos = event.pos()
        widget_rect = plot_widget.rect()
        if not widget_rect.contains(widget_pos):
            if hasattr(event, "accept"):
                event.accept()
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
        if hasattr(event, "accept"):
            event.accept()

    def custom_mouse_double_click(self, event, plot_widget):
        """Suppress double-click behavior so pyqtgraph does not leave a rubber band behind."""
        self.clear_viewbox_rubber_band(plot_widget)
        if hasattr(event, "accept"):
            event.accept()
    
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

        # Amplitude Axis Properties action removed
        # amplitude_properties_action = QAction("Amplitude Axis Properties", self)
        # amplitude_properties_action.triggered.connect(lambda: self.show_amplitude_axis_properties(plot_widget))
        # menu.addAction(amplitude_properties_action)
        
        # Show the menu at the cursor position
        self.active_context_menu = menu
        menu.exec_(global_pos)
        self.active_context_menu = None
    
    # def show_amplitude_axis_properties(self, plot_widget):
    #     """Show amplitude axis properties dialog for the specific graph"""
    #     try:
    #         # Get current axis properties from the plot widget
    #         current_properties = self.get_current_axis_properties(plot_widget)
    #
    #         # Create and show the dialog
    #         dialog = AmplitudeAxisPropertiesDialog(self, current_properties)
    #         dialog.properties_changed.connect(lambda props: self.apply_axis_properties(plot_widget, props))
    #
    #         result = dialog.exec_()
    #         if result == QDialog.Accepted:
    #             print(f"Amplitude axis properties applied for {plot_widget.chart_name}")
    #
    #     except Exception as e:
    #         QMessageBox.critical(self, "Properties Error",
    #                            f"Failed to open amplitude axis properties:\n{str(e)}")
    #
    # def get_current_axis_properties(self, plot_widget):
    #     """Get current axis properties from the plot widget"""
    #     try:
    #         # Get the current Y-axis range
    #         view_range = plot_widget.getViewBox().viewRange()
    #         y_min, y_max = view_range[1]
    #
    #         # Get the original Y-axis range if stored
    #         original_y_min = getattr(plot_widget, 'original_y_min', y_min)
    #         original_y_max = getattr(plot_widget, 'original_y_max', y_max)
    #
    #         properties = {
    #             'low_value': float(y_min),
    #             'high_value': float(y_max),
    #             'limit_axis_range': False,
    #             'limit_low_value': float(original_y_min),
    #             'limit_high_value': float(original_y_max),
    #             'auto_adjust': 'scale_to_fit'
    #         }
    #
    #         return properties
    #
    #     except Exception as e:
    #         print(f"Error getting current axis properties: {e}")
    #         # Return default properties
    #         return {
    #             'low_value': 35.0,
    #             'high_value': 100.0,
    #             'limit_axis_range': False,
    #             'limit_low_value': 85.0,
    #             'limit_high_value': 100.0,
    #             'auto_adjust': 'scale_to_fit'
    #         }
    #
    # def apply_axis_properties(self, plot_widget, properties):
    #     """Apply the axis properties to the plot widget"""
    #     try:
    #         # Get the view box
    #         vb = plot_widget.getViewBox()
    #
    #         # Apply new Y-axis range
    #         low_value = properties.get('low_value', 35.0)
    #         high_value = properties.get('high_value', 100.0)
    #
    #         # Force the Y-axis range to exactly match the specified values without
    #         # modifying the plotted signal values.
    #         try:
    #             plot_widget.setYRange(low_value, high_value, padding=0)
    #         except TypeError:
    #             # Try alternative method for older pyqtgraph versions
    #             plot_widget.setRange(yRange=[low_value, high_value], padding=0)
    #
    #         # Apply manual range setting to override any auto-scaling
    #         vb.setRange(yRange=[low_value, high_value], padding=0)
    #
    #         # Handle limit axis range
    #         if properties.get('limit_axis_range', False):
    #             limit_low = properties.get('limit_low_value', low_value)
    #             limit_high = properties.get('limit_high_value', high_value)
    #
    #             # Set strict limits on the view box to prevent zooming beyond range
    #             try:
    #                 vb.setLimits(yMin=limit_low, yMax=limit_high)
    #             except TypeError:
    #                 # Try alternative method
    #                 vb.setLimits(yMin=limit_low, yMax=limit_high)
    #         else:
    #             # Set limits to match the current range to prevent unwanted scaling
    #             try:
    #                 vb.setLimits(yMin=low_value, yMax=high_value)
    #             except TypeError:
    #                 vb.setLimits(yMin=low_value, yMax=high_value)
    #
    #         # Disable auto-range completely to maintain manual control
    #         auto_adjust = properties.get('auto_adjust', 'scale_to_fit')
    #         if auto_adjust == 'disabled':
    #             plot_widget.enableAutoRange(axis='y', enable=False)
    #             vb.enableAutoRange(axis='y', enable=False)
    #         elif auto_adjust == 'center':
    #             plot_widget.enableAutoRange(axis='y', enable=False)
    #             vb.enableAutoRange(axis='y', enable=False)
    #         else:
    #             plot_widget.enableAutoRange(axis='y', enable=False)
    #             vb.enableAutoRange(axis='y', enable=False)
    #
    #         # Store the properties in the plot widget for future reference
    #         plot_widget.axis_properties = properties
    #
    #         # Force immediate update of the display
    #         plot_widget.update()
    #         vb.updateAutoRange()
    #         vb.updateViewRange()
    #
    #         print(f"Applied axis properties to {plot_widget.chart_name}:")
    #         print(f"  Range: {low_value} - {high_value}")
    #         print(f"  Limit: {properties.get('limit_axis_range', False)}")
    #         print(f"  Auto-adjust: {auto_adjust}")
    #
    #         # Update SpO2 value labels to match the new scaled data
    #         if plot_widget.chart_name.strip() == "SpO2" and hasattr(plot_widget, 'plot_curve'):
    #             current_data = plot_widget.plot_curve.getData()
    #             if current_data[0] is not None and len(current_data[0]) > 0:
    #                 x_data, y_data = current_data
    #                 # Recreate value labels with the scaled data positions
    #                 self.create_spo2_markers_and_labels(plot_widget, x_data, y_data)
    #                 print(f"Updated SpO2 value labels for new axis range: {low_value} - {high_value}")
    #
    #         from PyQt5.QtCore import QTimer
    #         QTimer.singleShot(100, lambda: self.force_range_update(plot_widget, low_value, high_value))
    #
    #     except Exception as e:
    #         print(f"Error applying axis properties: {e}")
    #         QMessageBox.critical(self, "Apply Error",
    #                            f"Failed to apply axis properties:\n{str(e)}")
    #
    # def force_range_update(self, plot_widget, low_value, high_value):
    #     """Force the range update to ensure it sticks"""
    #     try:
    #         vb = plot_widget.getViewBox()
    #         vb.setRange(yRange=[low_value, high_value], padding=0)
    #         plot_widget.setYRange(low_value, high_value, padding=0)
    #         plot_widget.update()
    #
    #         if plot_widget.chart_name.strip() == "SpO2" and hasattr(plot_widget, 'plot_curve'):
    #             current_data = plot_widget.plot_curve.getData()
    #             if current_data[0] is not None and len(current_data[0]) > 0:
    #                 x_data, y_data = current_data
    #                 self.create_spo2_markers_and_labels(plot_widget, x_data, y_data)
    #                 print(f"Force updated SpO2 value labels for range: {low_value} - {high_value}")
    #
    #         print(f"Force updated range for {plot_widget.chart_name}: {low_value} - {high_value}")
    #     except Exception as e:
    #         print(f"Error in force range update: {e}")
    
    def custom_mouse_release(self, event, plot_widget):
        """Custom mouse release handler for reliable selection completion"""
        self.clear_viewbox_rubber_band(plot_widget)
        if event.button() == Qt.LeftButton:
            self.on_mouse_released(event, plot_widget)
        if hasattr(event, "accept"):
            event.accept()
    
    def on_container_resized(self, container):
        """Handle container resize to update overlay positions."""
        if hasattr(container, 'plot_widget'):
            self.schedule_selection_render()
    
    def on_plot_resized(self, plot_widget):
        """Handle plot widget resize/pan/zoom to update overlay positions."""
        self.schedule_selection_render()
    
    def on_mouse_released(self, event, plot_widget):
        """Finish selection on mouse release"""
        chart_name = plot_widget.chart_name.strip() if hasattr(plot_widget, "chart_name") else ""
        if not self._selection_allowed_for_chart(chart_name):
            self.clear_selection()
            return
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
            chart_name = self.current_selection_chart.chart_name.strip()
            if not self._selection_allowed_for_chart(chart_name):
                self.clear_selection()
                return
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
        
        print(f"View range: {vb.viewRange()}")
        print(f"update_selection_overlay - Chart: {self.current_selection_chart.chart_name}")
        print(f"update_selection_overlay - Data coords: start={start_x}, end={end_x}")
        print(
            f"update_selection_overlay - Widget coords: x_min={min(start_widget.x(), end_widget.x()):.1f}, "
            f"x_max={max(start_widget.x(), end_widget.x()):.1f}"
        )

        if not self._place_overlay_in_plot_area(
            self.current_selection_chart,
            overlay,
            start_widget.x(),
            end_widget.x(),
        ):
            return
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
                font-size: 10px;
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

    def _selection_allowed_for_chart(self, chart_name):
        """Allow manual selection only on supported charts after data upload."""
        return chart_name in {"Airflow", "SpO2"} and bool(getattr(self, "loaded_csv_path", None))

    def clear_viewbox_rubber_band(self, plot_widget):
        """Hide any stuck pyqtgraph rubber-band zoom box and reset drag state."""
        if not plot_widget or not hasattr(plot_widget, "getViewBox"):
            return

        vb = plot_widget.getViewBox()
        if vb is None:
            return

        if hasattr(vb, "clear_rubber_band_state"):
            vb.clear_rubber_band_state()
            return

        box = getattr(vb, "_rbScaleBox", None)
        if box is None:
            box = getattr(vb, "rbScaleBox", None)
        if box is not None:
            try:
                box.hide()
            except Exception:
                pass

        if hasattr(vb, "clickEvents") and isinstance(vb.clickEvents, list):
            vb.clickEvents.clear()
        for attr_name, value in (("dragButtons", []), ("dragItem", None), ("lastDrag", None)):
            if hasattr(vb, attr_name):
                try:
                    setattr(vb, attr_name, value)
                except Exception:
                    pass

    def show_selection_menu(self):
        """Show dropdown menu with different options based on chart type"""
        print("show_selection_menu called!")
        if not self.current_selection_chart:
            print("No current_selection_chart, returning")
            return
        chart_name = self.current_selection_chart.chart_name.strip()
        if not self._selection_allowed_for_chart(chart_name):
            print(f"Selection menu blocked for chart: {chart_name}")
            self.clear_selection()
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
                }
            """)
            
        # Create context menu
        print("Creating context menu...")
        menu = QMenu(self)
        menu.setTitle("Select Sleep Event Type")
        
        # Check if this is SpO2 chart
        if "SpO2" in chart_name:
            menu.setTitle("Select Event")
            
            # No temporary SpO2 values during dragging - only show after selection is saved
            
            # Check if there's a recent label for this chart and show it
            current_label = self.get_most_recent_label(chart_name)
            if current_label:
                label_action = QAction(f"Applied: {current_label}", self)
                label_action.setEnabled(False)  # Make it non-clickable info text
                label_font = label_action.font()
                label_font.setBold(True)
                label_action.setFont(label_font)
                menu.addAction(label_action)
                menu.addSeparator()
            
            # Add simple desaturation option for SpO2
            saturation_action = QAction("Desaturation", self)
            saturation_action.triggered.connect(lambda: self.apply_selection_label("DE-SATURATION"))
            menu.addAction(saturation_action)
        elif chart_name == "Airflow":
            # For Airflow chart ONLY, show sleep apnea options
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
        else:
            # Other charts - no event selection, clear and return
            self.clear_selection()
            return
        
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
        
        # Menu closed without choosing a label (X / Esc / outside click) ->
        # clear the dragged area instead of preserving a stale preview overlay.
        if self.selection_active:
            print("Menu dismissed - clearing pending selection")
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
        pending_change = getattr(self, "_pending_label_change", None)
        pending_selection = None
        pending_source = None
        if pending_change and pending_change.get("chart_name") == chart_name:
            pending_selection = pending_change.get("selection")
            pending_source = pending_change.get("source")

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
            'color': self.get_label_color(label_type),
            'source': 'manual',
        }

        if pending_change and pending_change.get("chart_name") == chart_name:
            p = pending_change.get("selection") or {}
            try:
                p_start = float(p.get("start", p.get("start_time", 0.0)))
                p_end = float(p.get("end", p.get("end_time", 0.0)))
            except (TypeError, ValueError):
                p_start = p_end = None
            if p_start is not None and p_end is not None:
                if abs(p_start - start_time_abs) < 0.5 and abs(p_end - end_time_abs) < 0.5:
                    pending_selection = p
                    pending_source = pending_change.get("source")
                else:
                    self._pending_label_change = None
                    pending_selection = None
                    pending_source = None
            else:
                self._pending_label_change = None
                pending_selection = None
                pending_source = None

        if pending_selection and pending_source == "auto_rule_ai":
            self._pending_label_change = None
            self._set_manual_label_override_for_selection(pending_selection, label_type)
            self.clear_selection()
            self._refresh_auto_rule_ai_views()
            print(f"Label '{label_type}' applied to auto-detected event (manual override saved)")
            return

        if pending_selection and pending_source != "auto_rule_ai":
            self._pending_label_change = None

        # Calculate SpO2 info for SpO2 chart only
        spo2_info = ""
        if "SpO2" in chart_name and self.spo2_full_data:
            try:
                # Get SpO2 data
                time_data, spo2_data = self.spo2_full_data
                
                # Calculate indices
                sampling_rate = EXTERNAL_ARRAY_SAMPLE_RATE_HZ
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
            'spo2_info': spo2_info,
            'source': 'manual',
        }

        self.selection_labels[chart_name].append(selection_data)
        self.dynamic_selections[chart_name].append(dynamic_selection_data)

        auto_overlap_deleted = self._mark_overlapping_auto_events_for_manual_selection(
            chart_name,
            start_time_abs,
            end_time_abs,
        )

        # Persist this freely-drawn manual box to the sidecar JSON right
        # away, same as a relabeled auto-event does - so it survives a
        # Current-report re-analyze and is available to archive if this
        # session is later saved as a New report.
        self._save_manual_label_overrides()

        if hasattr(plot_widget, 'selection_overlay'):
            plot_widget.selection_overlay.setVisible(False)

        if auto_overlap_deleted:
            self._refresh_auto_rule_ai_views()
        else:
            self.render_dynamic_selections()
            self.emit_detected_events_panel()
            self.update_detection_summary_label()

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
            selection_data = self.selection_labels[chart_name][label_index]
            if selection_data.get("is_manually_edited"):
                menu.addSeparator()
                reset_action = QAction("Reset to auto label", self)
                reset_action.triggered.connect(lambda: self.reset_overlay_label_to_auto(chart_name, label_index))
                menu.addAction(reset_action)

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

    def reset_overlay_label_to_auto(self, chart_name, label_index):
        """Remove a manual override and restore the detector label."""
        if chart_name not in self.selection_labels or not (0 <= label_index < len(self.selection_labels[chart_name])):
            return

        selection = self.selection_labels[chart_name][label_index]
        if not self.reset_manual_label_for_event(selection):
            return

        self._refresh_auto_rule_ai_views()
        print(f"Reset auto label for {chart_name} selection at index {label_index}")
    
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
        if not self._is_valid_overlay(overlay):
            print("Warning: Overlay already deleted or invalid")
            self._remove_overlay_reference(overlay)
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
            self._remove_overlay_reference(overlay)
        except RuntimeError as e:
            print(f"Warning: Overlay already deleted - {e}")
            self._remove_overlay_reference(overlay)
            return

        # Remove from data using the unique identifier
        removed_selection = None
        removed_count = 0
        if chart_name in self.selection_labels:
            # Find and remove matching selection by comparing start/end times or label
            kept_selections = []
            for sel in self.selection_labels[chart_name]:
                if self._get_selection_id(sel) == overlay_id:
                    removed_selection = sel
                    continue
                kept_selections.append(sel)
            self.selection_labels[chart_name] = kept_selections
            removed_count = len(self.selection_labels[chart_name])
        
        if chart_name in self.dynamic_selections:
            # Find and remove matching dynamic selection
            self.dynamic_selections[chart_name] = [
                sel for sel in self.dynamic_selections[chart_name]
                if self._get_selection_id(sel) != overlay_id
            ]

        self._mark_deleted_auto_event(removed_selection)

        # Keep the sidecar JSON in sync so a deleted manual box doesn't
        # reappear next time this file is loaded.
        self._save_manual_label_overrides()

        # Re-render selections to update positions
        self.render_dynamic_selections()
        self.emit_detected_events_panel()
        self.update_detection_summary_label()
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
        """Continuously enforce fixed X-axis ranges on all charts."""
        if self.is_playing:
            return
        if self.is_all_psg_mode():
            fixed_end = self._get_playback_max_duration()
        else:
            fixed_end = self.get_effective_time_window_seconds()
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            if container and hasattr(container, 'plot_widget'):
                plot_widget = container.plot_widget
                if hasattr(plot_widget, 'fixed_range'):
                    if self.is_all_psg_mode():
                        plot_widget.fixed_range = [0, fixed_end]
                    # Force the X-axis range to be exactly what we want
                    try:
                        current_range = plot_widget.getViewBox().viewRange()
                        # Only print if range is not what we want 
                        if (
                            abs(current_range[0][0] - plot_widget.fixed_range[0]) > 1e-3
                            or abs(current_range[0][1] - plot_widget.fixed_range[1]) > 1e-3
                        ):
                            dbg(f"🔧 FIXING ViewBox {plot_widget.chart_name}: {current_range[0]} → {plot_widget.fixed_range}")
                        plot_widget.setXRange(plot_widget.fixed_range[0], plot_widget.fixed_range[1], padding=0)
                    except:
                        pass  
    
    def get_label_color(self, label_type):
        """Fill color used by selection overlays and event labels."""
        red, green, blue = self.get_label_rgb(label_type)
        return f'rgba({red}, {green}, {blue}, 0.35)'

    def get_label_rgb(self, label_type):
        """Get a single RGB palette for event shading and blocks.

        strip().upper() is required so values like 'osa' or 'OSA ' resolve
        correctly. Unknown labels stay neutral grey instead of looking like
        apnea events.
        """
        normalized_label = str(label_type).strip().upper()
        colors = {
            'OSA': (190, 52, 68),
            'CSA': (30, 110, 140),
            'MSA': (92, 78, 158),
            'HSA': (176, 124, 42),
            'POSSIBLE_OSA': (190, 52, 68),
            'POSSIBLE_CSA': (30, 110, 140),
            'POSSIBLE_MSA': (92, 78, 158),
            'DE-SATURATION': (0, 131, 143),
            'SATURATION': (0, 131, 143),
            'APNEA_REVIEW': (107, 114, 128),
        }
        return colors.get(normalized_label, (107, 114, 128))

    def check_label_click(self, plot_widget, scene_pos):
        """Check if click is on an existing label and show remove option"""
        chart_name = plot_widget.chart_name
        if chart_name not in self.selection_labels or not self.selection_labels[chart_name]:
            return False
        
        widget_pos = plot_widget.mapFromScene(scene_pos)
        
        # Use overlay geometry for precise click detection
        if hasattr(plot_widget, 'selection_overlays'):
            plot_widget.selection_overlays = [
                overlay for overlay in plot_widget.selection_overlays
                if self._is_valid_overlay(overlay)
            ]
            overlays = plot_widget.selection_overlays
            for i, overlay in enumerate(overlays):
                # Check if overlay still exists (not deleted)
                try:
                    if (self._is_valid_overlay(overlay) and
                        not overlay.isHidden() and
                        overlay.geometry().contains(widget_pos) and
                        i < len(self.selection_labels[chart_name])):
                        selection_data = self.selection_labels[chart_name][i]
                        self.show_remove_menu(plot_widget, chart_name, i, selection_data, scene_pos)
                        return True
                except RuntimeError:
                    # Overlay has been deleted, skip it
                    continue
        
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
        try:
            if chart_name in self.selection_labels and 0 <= label_index < len(self.selection_labels[chart_name]):
                removed_label = self.selection_labels[chart_name].pop(label_index)
                print(f"Removed label '{removed_label['label']}' from {chart_name}")
                self._mark_deleted_auto_event(removed_label)
                
                # Also remove from dynamic_selections to prevent overlay issues
                if chart_name in self.dynamic_selections:
                    # Find and remove the corresponding dynamic selection
                    removed_id = self._get_selection_id(removed_label)
                    self.dynamic_selections[chart_name] = [
                        sel for sel in self.dynamic_selections[chart_name]
                        if self._get_selection_id(sel) != removed_id
                    ]
                
                # Keep the sidecar JSON in sync so a deleted manual box
                # doesn't reappear next time this file is loaded.
                self._save_manual_label_overrides()

                # Re-render selections to update overlays with error handling
                try:
                    self.render_dynamic_selections()
                except Exception as e:
                    print(f"Error rendering selections after removal: {e}")
                self.emit_detected_events_panel()
                self.update_detection_summary_label()
                
                # Hide overlay if no more labels
                if not self.selection_labels[chart_name]:
                    # Find the plot widget and hide overlay
                    try:
                        for i in range(self.charts_layout.count()):
                            container = self.charts_layout.itemAt(i).widget()
                            if container and hasattr(container, 'findChildren'):
                                plots = container.findChildren(pg.PlotWidget)
                                if plots and plots[0].chart_name == chart_name:
                                    if hasattr(plots[0], 'selection_overlay'):
                                        plots[0].selection_overlay.setVisible(False)
                                    break
                    except Exception as e:
                        print(f"Error hiding overlay: {e}")
        except Exception as e:
            print(f"Error in remove_label: {e}")
            # Re-render selections to maintain consistency even if error occurs
            try:
                self.render_dynamic_selections()
            except:
                pass
        
    def change_label(self, chart_name, label_index):
        """Change an existing label by opening the event selection menu"""
        if chart_name in self.selection_labels and 0 <= label_index < len(self.selection_labels[chart_name]):
            old_selection = self.selection_labels[chart_name][label_index]
            selection_source = old_selection.get("source", "manual")
            self.remove_label(chart_name, label_index)
            
            # Keep the original absolute time range and let the label menu reuse it.
            from PyQt5.QtCore import QPointF
            start_point = QPointF(float(old_selection.get('start', old_selection.get('start_time', 0.0))) - float(self.current_time_offset), 0)
            end_point = QPointF(float(old_selection.get('end', old_selection.get('end_time', 0.0))) - float(self.current_time_offset), 0)

            self.selection_start = start_point
            self.selection_end = end_point
            self.current_selection = {
                "start": start_point,
                "end": end_point
            }
            self._pending_label_change = {
                "chart_name": chart_name,
                "label_index": label_index,
                "selection": dict(old_selection),
                "source": selection_source,
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
    
    def hide_all_preview_overlays(self):
        """Hide every chart's temporary preview overlay."""
        for index in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(index).widget()
            if not container or not hasattr(container, 'findChildren'):
                continue
            for plot_widget in container.findChildren(pg.PlotWidget):
                overlay = getattr(plot_widget, 'selection_overlay', None)
                if overlay is None:
                    continue
                try:
                    overlay.setVisible(False)
                except RuntimeError:
                    continue

    def clear_selection(self):
        """Clear the current selection but keep persistent overlays"""
        # Clear selection active flag since selection is cleared
        self.selection_active = False
        
        # Close the context menu if it's still open
        if hasattr(self, 'active_context_menu') and self.active_context_menu is not None:
            self.active_context_menu.close()
            self.active_context_menu = None

        self.hide_all_preview_overlays()
        
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
                    font-size: 10px;
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
        self._pending_label_change = None
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
    
    def _is_valid_overlay(self, overlay):
        """Return True when a Qt overlay wrapper still points to a live widget."""
        try:
            return overlay is not None and hasattr(overlay, 'setVisible') and not sip.isdeleted(overlay)
        except RuntimeError:
            return False

    def _remove_overlay_reference(self, overlay):
        """Remove deleted/stale overlay widgets from every plot overlay list."""
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            if not container or not hasattr(container, 'findChildren'):
                continue
            for plot_widget in container.findChildren(pg.PlotWidget):
                if hasattr(plot_widget, 'selection_overlays'):
                    plot_widget.selection_overlays = [
                        existing_overlay for existing_overlay in plot_widget.selection_overlays
                        if existing_overlay is not overlay and self._is_valid_overlay(existing_overlay)
                    ]

    def _plot_area_rect(self, plot_widget):
        """Return the plot area's bounds in plot-widget coordinates."""
        try:
            view_box = plot_widget.getViewBox()
            if view_box is None:
                raise ValueError("missing view box")
            scene_rect = view_box.sceneBoundingRect()
            top_left = plot_widget.mapFromScene(scene_rect.topLeft())
            bottom_right = plot_widget.mapFromScene(scene_rect.bottomRight())
            left = float(top_left.x())
            top = float(top_left.y())
            right = float(bottom_right.x())
            bottom = float(bottom_right.y())
            if right > left and bottom > top:
                return left, top, right, bottom
        except Exception as error:
            dbg(f"Could not resolve plot area rect: {error}")
        return 0.0, 0.0, float(plot_widget.width()), float(plot_widget.height())

    def _place_overlay_in_plot_area(
        self,
        plot_widget,
        overlay,
        x_min,
        x_max,
        top_offset=0.0,
        fixed_height=None,
        min_width=30.0,
    ):
        """Place an overlay at its real x-position and mask it to the plot area.

        The overlay keeps its full width and keeps sliding smoothly as data
        changes. Only the visible part inside the plotting area is shown.
        """
        left, top, right, bottom = self._plot_area_rect(plot_widget)

        low = float(min(x_min, x_max))
        high = float(max(x_min, x_max))
        if high - low < float(min_width):
            high = low + float(min_width)

        overlay_top = top + float(top_offset)
        if fixed_height is not None:
            overlay_height = float(fixed_height)
        else:
            overlay_height = bottom - overlay_top
        overlay_height = max(1.0, min(overlay_height, bottom - overlay_top))

        visible_left = max(low, left)
        visible_right = min(high, right)
        if visible_right - visible_left < 1.0:
            overlay.hide()
            overlay.clearMask()
            return False

        overlay.setGeometry(
            int(round(low)),
            int(round(overlay_top)),
            int(round(max(1.0, high - low))),
            int(round(overlay_height)),
        )

        if visible_left <= low + 0.5 and visible_right >= high - 0.5:
            overlay.clearMask()
        else:
            overlay.setMask(
                QRegion(
                    int(round(visible_left - low)),
                    0,
                    int(round(visible_right - visible_left)),
                    int(round(overlay_height)),
                )
            )
        return True
    
    def render_dynamic_selections(self):
        """Render selection overlays based on current time window and offset.

        RE-ENTRANCY GUARD is necessary: overlay.setGeometry() / show() can
        trigger layout changes, which fire resizeEvent again and re-enter this
        function. The outer pass would then hide overlays drawn by the inner
        pass, which is why events disappeared during resize.
        """
        if getattr(self, "_rendering_selections", False):
            return
        self._rendering_selections = True
        try:
            for i in range(self.charts_layout.count()):
                container = self.charts_layout.itemAt(i).widget()
                if not (container and hasattr(container, 'findChildren')):
                    continue

                plot_widget = getattr(container, 'plot_widget', None)
                if plot_widget is None:
                    plots = container.findChildren(pg.PlotWidget)
                    if not plots:
                        continue
                    plot_widget = plots[0]
                if not hasattr(plot_widget, 'chart_name'):
                    continue
                chart_name = plot_widget.chart_name

                # Clear existing overlays safely - REUSE INSTEAD OF DELETE
                if hasattr(plot_widget, 'selection_overlays'):
                    for overlay in plot_widget.selection_overlays:
                        try:
                            if overlay and hasattr(overlay, 'hide') and not sip.isdeleted(overlay):
                                overlay.hide()
                                overlay.setGeometry(-1000, -1000, 1, 1)
                        except Exception as e:
                            dbg(f"Warning: Could not hide overlay: {e}")
                            continue

                if chart_name not in self.dynamic_selections:
                    continue

                for selection_data in self.dynamic_selections[chart_name]:
                    try:
                        start_time_abs = selection_data['start_time']
                        end_time_abs = selection_data['end_time']
                        if self.is_all_psg_mode():
                            start_time_rel = start_time_abs
                            end_time_rel = end_time_abs
                            visible_start = 0.0
                            visible_end = self._get_playback_max_duration()
                        else:
                            start_time_rel = start_time_abs - self.current_time_offset
                            end_time_rel = end_time_abs - self.current_time_offset
                            visible_start = 0.0
                            visible_end = self.get_effective_time_window_seconds()

                        if not (end_time_rel >= visible_start and start_time_rel <= visible_end):
                            continue

                        start_time_clamped = max(visible_start, start_time_rel)
                        end_time_clamped = min(visible_end, end_time_rel)

                        overlay = None
                        if hasattr(plot_widget, 'selection_overlays'):
                            for existing_overlay in plot_widget.selection_overlays:
                                if (
                                    existing_overlay
                                    and not sip.isdeleted(existing_overlay)
                                    and hasattr(existing_overlay, 'isVisible')
                                    and not existing_overlay.isVisible()
                                ):
                                    overlay = existing_overlay
                                    break

                        if overlay is None:
                            overlay = QLabel(plot_widget)
                            overlay.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
                            if not hasattr(plot_widget, 'selection_overlays'):
                                plot_widget.selection_overlays = []
                            plot_widget.selection_overlays.append(overlay)
                        else:
                            overlay.setAlignment(Qt.AlignHCenter | Qt.AlignTop)

                        duration = end_time_abs - start_time_abs
                        start_str = self.format_timestamp(start_time_abs)
                        duration_str = self.format_duration(duration)

                        display_label = str(selection_data['label'])
                        if selection_data.get("is_manually_edited"):
                            display_label = f"{display_label} *"
                        if display_label.strip().upper() == "SENSOR_OFF":
                            # Sensor-off is not a scored AASM event; show the
                            # flattened trace without an event badge.
                            overlay.hide()
                            overlay.setGeometry(-1000, -1000, 1, 1)
                            continue
                        elif 'spo2_info' in selection_data and selection_data['spo2_info']:
                            full_text = f"""
{display_label}

{start_str}
{duration_str}

{selection_data['spo2_info']}
"""
                        else:
                            full_text = f"{display_label}\n{start_str}\n{duration_str}"
                        overlay.setText(full_text)
                        overlay_style = f"""
                            background-color: {selection_data['color']};
                            border: 1px solid rgba(0, 0, 0, 0.25);
                            border-radius: 6px;
                            color: #1a1a1a;
                            font-size: 10px;
                            font-weight: bold;
                            padding: 4px 2px 2px 2px;
                        """
                        if getattr(overlay, "_applied_style", None) != overlay_style:
                            overlay._applied_style = overlay_style
                            overlay.setStyleSheet(overlay_style)

                        overlay.mousePressEvent = lambda event, ov=overlay, cn=chart_name: self.handle_overlay_click(event, ov, cn)
                        overlay.mouseDoubleClickEvent = lambda event, ov=overlay, cn=chart_name: self.handle_overlay_double_click(event, ov, cn)

                        vb = plot_widget.getViewBox()
                        if vb:
                            start_scene = vb.mapViewToScene(QPointF(start_time_rel, 0))
                            end_scene = vb.mapViewToScene(QPointF(end_time_rel, 0))

                            start_widget = plot_widget.mapFromScene(start_scene)
                            end_widget = plot_widget.mapFromScene(end_scene)

                            overlay.selection_id = self._get_selection_id(selection_data)
                            placed = self._place_overlay_in_plot_area(
                                plot_widget,
                                overlay,
                                start_widget.x(),
                                end_widget.x(),
                            )
                            if not placed:
                                continue
                            overlay.show()

                            dbg(
                                f"Rendered selection '{selection_data['label']}' on {chart_name} "
                                f"at {start_time_clamped:.1f}s-{end_time_clamped:.1f}s"
                            )
                    except Exception as e:
                        dbg(f"Error rendering selection overlay: {e}")
                        continue
        except Exception as e:
            dbg(f"Error in render_dynamic_selections: {e}")
        finally:
            self._rendering_selections = False

    def schedule_selection_render(self):
        """Render on the next event-loop turn, once per burst of resize events."""
        if getattr(self, "_selection_render_scheduled", False):
            return
        self._selection_render_scheduled = True
        QTimer.singleShot(0, self._run_scheduled_selection_render)

    def _run_scheduled_selection_render(self):
        self._selection_render_scheduled = False
        self.render_dynamic_selections()

    def update_apnea_events_display(self):
        """Refresh only the event summary; overlays are rendered elsewhere."""
        self.update_detection_summary_label()
    
    def update_all_overlays_on_resize(self):
        """Refresh selection overlays on resize using the existing render path."""
        self.schedule_selection_render()
    
        
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
HB: {self.spo2_statistics['hypoxic_burden']:.2f} %-min
Longest <95: {self.spo2_statistics['longest_duration_sec']:.1f}s
Events <=92: {self.spo2_statistics['desaturation_events']}
        """.strip()
        
        stats_label = QLabel(container)
        stats_label.setText(stats_text)
        stats_label.setStyleSheet(f"""
            QLabel#signalLabel {{
                background-color: rgba(0, 0, 0, 0.8);
                color: white;
                font-size: 9px;
                font-weight: 700;
                padding: 2px;
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

    def _get_analysis_json_path(self):
        """Find the analysis JSON file for the current session."""
        try:
            csv_path = getattr(self, "current_csv_path", None) or getattr(
                self, "loaded_csv_path", None
            )
            if not csv_path:
                return None

            csv_filename = os.path.basename(csv_path)
            csv_base = os.path.splitext(csv_filename)[0]
            import glob
            analysis_dirs = [
                Path(csv_path).parent.parent / "analysis_json",
                get_configured_path("analysis_json_dir"),
            ]
            files = []
            for analysis_dir in analysis_dirs:
                if analysis_dir.exists():
                    files.extend(glob.glob(str(analysis_dir / f"{csv_base}_analysis_*.json")))
            if files:
                return max(set(files), key=os.path.getctime)
            return None
        except Exception as error:
            dbg(f"Error finding analysis JSON: {error}")
            return None

    def _load_sensor_off_segments(self, analysis_json_path):
        """Load sensor-off segments from an analysis results JSON file."""
        try:
            if not analysis_json_path or not os.path.exists(analysis_json_path):
                return []

            with open(analysis_json_path, "r", encoding="utf-8") as file_handle:
                analysis_data = json.load(file_handle)
            return analysis_data.get("sensor_off_segments", []) or []
        except Exception as error:
            dbg(f"Error loading sensor_off_segments: {error}")
            return []

    def _mask_airflow_during_sensor_off(self, airflow, time_array, sensor_off_segments):
        """Replace sensor-off airflow samples with a flat baseline for display."""
        if not sensor_off_segments or len(airflow) == 0:
            return airflow

        masked_airflow = np.array(airflow, dtype=float, copy=True)
        baseline_end = max(1, int(len(masked_airflow) * 0.1))
        baseline = float(np.nanmedian(masked_airflow[:baseline_end]))
        if np.isnan(baseline) or baseline == 0:
            baseline = float(np.nanmean(masked_airflow))
        if np.isnan(baseline):
            baseline = 0.0

        time_values = np.asarray(time_array, dtype=float)
        if time_values.size:
            dbg(
                f"Sensor-off masking time range: min={float(np.nanmin(time_values)):.1f}s, "
                f"max={float(np.nanmax(time_values)):.1f}s, len={len(time_values)}"
            )
            dbg(f"Airflow samples available for masking: len={len(masked_airflow)}")

        for segment in sensor_off_segments:
            start_sec = float(segment.get("start_sec", 0.0))
            end_sec = float(segment.get("end_sec", 0.0))
            if not time_values.size:
                continue

            direct_mask = (time_values >= start_sec) & (time_values <= end_sec)
            if np.any(direct_mask):
                masked_airflow[direct_mask] = baseline
                dbg(
                    f"Mask segment {start_sec:.1f}s-{end_sec:.1f}s -> "
                    f"{int(np.count_nonzero(direct_mask))} samples (direct)"
                )
                continue

            # If the supplied time array is offset from the segment clock,
            # fall back to a zero-based view for debugging and masking.
            shifted_time_values = time_values - float(time_values[0])
            shifted_mask = (shifted_time_values >= start_sec) & (shifted_time_values <= end_sec)
            if np.any(shifted_mask):
                masked_airflow[shifted_mask] = baseline
                dbg(
                    f"Mask segment {start_sec:.1f}s-{end_sec:.1f}s -> "
                    f"{int(np.count_nonzero(shifted_mask))} samples (shifted by "
                    f"{float(time_values[0]):.1f}s)"
                )
            else:
                dbg(
                    f"Mask segment {start_sec:.1f}s-{end_sec:.1f}s -> 0 samples "
                    f"(direct and shifted)"
                )
        return masked_airflow

    def _detect_breathing_stopped_periods(self, min_duration_sec=60):
        """Return detected apnea/hypopnea events that are long enough to flatten."""
        segments = []
        try:
            result = getattr(self, "auto_rule_ai_result", None)
            events = (result.get("events", []) if result else []) or []
            for event in events:
                try:
                    start_sec = float(event.get("start_sec"))
                    end_sec = float(event.get("end_sec"))
                except (TypeError, ValueError):
                    continue
                if not (end_sec > start_sec):
                    continue

                label = canonical_event_label(
                    event.get("final_label") or event.get("rule_label") or "REVIEW"
                )
                if label in ("REVIEW", "DE-SATURATION", "SATURATION"):
                    continue

                duration = end_sec - start_sec
                if duration < min_duration_sec:
                    continue

                segments.append({
                    "start_sec": start_sec,
                    "end_sec": end_sec,
                    "duration_sec": duration,
                    "reason": f"breathing_stopped ({label})",
                })
                dbg(
                    f"Breathing stopped [{label}]: {start_sec:.0f}s-{end_sec:.0f}s "
                    f"({duration:.0f}s)"
                )
            dbg(f"TOTAL breathing-stopped periods found: {len(segments)}")
        except Exception as error:
            dbg(f"Breathing-stopped detection error: {error}")
        return segments

    def _apply_sensor_off_masking_after_detection(self):
        """Apply sensor-off and breathing-stopped ranges to the airflow display."""
        try:
            result = getattr(self, "auto_rule_ai_result", None)
            sensor_off_segments = result.get("sensor_off_segments", []) if result else []
            breathing_stopped_segments = self._detect_breathing_stopped_periods(
                min_duration_sec=60,
            )
            all_segments = sensor_off_segments + breathing_stopped_segments

            dbg("\n" + "=" * 60)
            dbg("AIRFLOW MASKING DEBUG:")
            dbg(f"  Sensor-off segments: {len(sensor_off_segments)}")
            dbg(f"  Breathing-stopped: {len(breathing_stopped_segments)}")
            dbg(f"  TOTAL to mask: {len(all_segments)}")
            for index, segment in enumerate(sensor_off_segments[:5]):
                start_value = float(segment.get("start_sec", 0.0))
                end_value = float(segment.get("end_sec", 0.0))
                duration_value = float(
                    segment.get("duration_sec", end_value - start_value)
                )
                start_min, start_rem = divmod(int(start_value), 60)
                end_min, end_rem = divmod(int(end_value), 60)
                dbg(
                    f"  Sensor-off [{index}] {start_min}:{start_rem:02d} - "
                    f"{end_min}:{end_rem:02d} "
                    f"(Duration: {duration_value:.0f}s)"
                )
            dbg("=" * 60 + "\n")

            if not all_segments:
                return

            current_psg_data = getattr(self, "current_psg_data", None)
            if not isinstance(current_psg_data, dict):
                return

            time_data = current_psg_data.get("time", [])
            signals = current_psg_data.get("signals", {})
            if "airflow_display" not in signals or len(signals["airflow_display"]) == 0:
                return

            # Always start from the enhanced signal so repeated detection does
            # not calculate a new baseline from an already masked trace.
            display_source = signals.get("airflow_enhanced", signals["airflow_display"])
            original_length = len(display_source)
            signals["airflow_display"] = self._mask_airflow_during_sensor_off(
                display_source, time_data, all_segments
            )
            dbg(
                f"Applied masking: {len(sensor_off_segments)} sensor-off + "
                f"{len(breathing_stopped_segments)} breathing-stopped = "
                f"{len(all_segments)} total, airflow length: {original_length}"
            )
        except Exception as error:
            dbg(f"Error applying sensor-off masking: {error}")
