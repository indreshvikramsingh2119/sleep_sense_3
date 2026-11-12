


"""
Sleep Monitor Chart Widget - Sleep Monitoring Chart Component
"""

import os
import sys
import json
import math
import time
import ctypes
import hmac
import hashlib
from html import escape as html_escape
import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path
from scipy.signal import find_peaks
from src.utils.db_utils import (
    get_db_path,
    save_raw_recording_session,
)
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QComboBox, QMessageBox, QMenu, QAction, QScrollArea, QSizePolicy, QSlider, QFileDialog, QApplication, QDialog, QStyle, QShortcut, QOpenGLWidget
)
from PyQt5.QtCore import Qt, QTimer, QTime, QThread, pyqtSignal, QPoint, QRect, QMimeData, QPointF, QElapsedTimer, QEvent, QEventLoop, QRectF, QSize
from PyQt5 import sip
from PyQt5.QtGui import QPixmap, QScreen, QKeySequence
from PyQt5.QtGui import QFont, QIcon, QPixmap, QDrag, QPainter, QPen, QColor, QRegion, QSurfaceFormat
import pyqtgraph as pg
from .custom_viewbox import CustomViewBox
from .amplitude_axis_properties_dialog import AmplitudeAxisPropertiesDialog
from .airflow_display_processing import (
    enhance_airflow_for_graph_and_detection,
    add_snore_texture_to_airflow_display,
    orient_airflow_for_display,
)
from ..utils.report_metrics_calculator import (
    calculate_hypoxic_burden_metrics,
    calculate_sleep_metrics,
    save_sleep_metrics_json,
)
from ..utils.event_labels import canonical_event_label
from ..utils.runtime_config import get_configured_path
from ..utils.dialog_helpers import show_styled_warning
from ..utils.recording_exclusions import exclusion_summary, overlaps_exclusion

CLASSIC_PLOT_LOGIC = True   # True = Airflow/Thorax plotted exactly like the old file; False = newer display + smooth axis
# True: the whole-night flow-limitation (FL) analysis runs in a worker thread, so the graphs appear first
# and the FL markers are added a moment later.  False: old behaviour (analysis inside the first draw).
FL_COMPUTE_IN_BACKGROUND = True

APP_ROOT = Path(__file__).resolve().parents[2]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))


# --- Sidecar storage: app-data location + integrity signature ---------------
_SIDECAR_HMAC_KEY = hashlib.sha256(b"sleepsense-manual-overrides-v1").digest()


def _app_data_root() -> Path:
    """Return the per-user application-data directory for session state."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    root = base / "SleepSense" / "session_state"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _sidecar_path_for(source_path) -> Path:
    """Return an opaque, recording-specific path in the app-data directory."""
    digest = hashlib.sha256(str(Path(source_path).resolve()).encode("utf-8")).hexdigest()
    return _app_data_root() / f"{digest}.dat"


def _write_signed_json(path: Path, data: dict) -> None:
    payload = json.dumps(data, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(_SIDECAR_HMAC_KEY, payload, hashlib.sha256).digest()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(signature)
        handle.write(payload)


def _read_signed_json(path: Path):
    if not path.exists():
        return None
    try:
        raw = path.read_bytes()
        if len(raw) < 32:
            return None
        signature, payload = raw[:32], raw[32:]
        expected = hmac.new(_SIDECAR_HMAC_KEY, payload, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            print("⚠️ Manual label sidecar failed integrity check - ignoring file.")
            return None
        return json.loads(payload.decode("utf-8"))
    except Exception as error:
        print(f"⚠️ Could not read manual label sidecar: {error}")
        return None

from .plot_psg_data import (  # noqa: E402
    ACTIVE_SIGNAL_CONFIGS,
    ACTIVE_SIGNAL_NAMES,
    SIGNAL_Y_RANGES,
    PLOTTED_SIGNAL_NAMES,
    CHANNEL_COLORS,
    AUTO_RANGE_SIGNAL_NAMES,
    HIDDEN_Y_AXIS_VALUE_CHARTS,
    AXIS_MIN_SPAN,
    BIPOLAR_SIGNAL_NAMES,
    AXIS_HARD_LIMITS,
    AXIS_ALWAYS_REFIT,
    AXIS_TOP_HEADROOM,
    AXIS_TOP_CEILING,
    AUTO_RANGE_OUTLIER_IQR_FACTOR,
    AUTO_RANGE_MIN_KEEP_FRACTION,
    AXIS_SMOOTH_ENABLED,
    AXIS_SMOOTH_CHARTS,
    AXIS_SMOOTH_MARGIN,
    AXIS_SMOOTH_NORMAL_REACH,
    AXIS_SMOOTH_TYPICAL_PCT,
    AXIS_SMOOTH_ZOOM_OUT_SEC,
    AXIS_SMOOTH_ZOOM_IN_SEC,
    AXIS_SMOOTH_SHIFT_SEC,
    AXIS_SMOOTH_MIN_HALF,
    AXIS_SMOOTH_OVERFLOW,
    AXIS_SMOOTH_BAND,
    AXIS_SMOOTH_COMPRESS_RANGE,
    AXIS_SMOOTH_FLAT_FRACTION,
    AXIS_SMOOTH_DEAD_FRACTION,
    AXIS_SMOOTH_FLAT_HOLD_SEC,
    AXIS_SMOOTH_REFERENCE_SEC,
    THORAX_DISPLAY_LOWPASS_HZ,
    BODY_POSITION_VIEW_MIN,
    BODY_POSITION_VIEW_MAX,
    SPO2_FIXED_AXIS,
    SPO2_ARTIFACT_FLOOR,
    SPO2_LABEL_ROOM_FRACTION,
    PULSE_FIXED_AXIS,
    CHART_SIGNAL_MAPPING,
    BODY_POSITION_TICKS,
    BODY_POSITION_LABEL_TO_CODE,
    BODY_POSITION_UNKNOWN,
    signal_key_for_chart,
)
from ..utils.sample_rate import (  # noqa: E402
    CHANNEL_SAMPLE_RATES,
    DETECTION_SAMPLE_RATE_HZ,
    channel_sample_rate,
)
from ..utils.sd_record_reader import (  # noqa: E402
    INSPIRATION_IS_LOW_AIRFLOW,
    THORAX_BASELINE_REMOVE,
    remove_slow_baseline,
)

# Binary SD recordings provide native rates per channel. This is only the
# display/resampling fallback when a rate is absent from recording metadata.
EXTERNAL_ARRAY_SAMPLE_RATE_HZ = DETECTION_SAMPLE_RATE_HZ

# How far above the typical peak (in typical amplitudes) still counts as NORMAL breathing
# for a chart. Anything beyond is treated as a movement and is squeezed into the compress
# band at the top/bottom of the chart (it then looks flat-topped). Airflow gets a larger
# value than the global AXIS_SMOOTH_NORMAL_REACH because the large recovery breaths after
# an apnea (2-4x the amplitude of the breaths around them) are real breathing and must keep
# their natural shape. Only the charts listed here also measure "normal" against the typical
# amplitude of the whole recording and look ahead (AXIS_SMOOTH_LOOKAHEAD_SEC); the others
# (Thorax) keep treating a big swing as a movement. They use AXIS_SMOOTH_NORMAL_REACH.
AXIS_SMOOTH_NORMAL_REACH_BY_CHART = {"Airflow": 2.5}

# Thorax: a 6-10 s chunk whose peak-to-peak swing is more than this many times the typical
# breathing amplitude of the WHOLE recording is body movement, not breathing.  Such chunks
# are left out when the window's "typical" breathing level is measured.  Without this, a
# movement that fills ~45 % or more of the window drags the median (the "typical" level)
# into the movement, the axis zooms out to hold it and the real breathing is drawn flat.
AXIS_MOVEMENT_AMPLITUDE_FACTOR_BY_CHART = {"Thorax": 4.0}

# The axis looks this many seconds of DATA beyond the right edge of the window (times the
# playback speed, so it is the same number of real seconds on screen) and starts to widen
# BEFORE a big breath scrolls in. 0 = off. Not used in All-PSG mode.
AXIS_SMOOTH_LOOKAHEAD_SEC = 4.0

# --- Snoring Y scale ---------------------------------------------------------
# Snoring is a burst channel: long silence + short vibration packets. With a
# per-window auto-fit the SAME spike changed height whenever a bigger spike
# entered or left the 60 s view: Play held the Play-start scale (new big spike
# drawn huge / clipped), Pause refit to the biggest spike (everything shrank).
# True = one fixed scale for the whole recording (like a PSG viewer's channel
# gain), so a spike always has the same height - paused, playing, any window.
SNORING_FIXED_AXIS_FROM_RECORDING = True
# Scale = this percentile of the snore-packet amplitudes of the whole night, so
# one rare artifact cannot squash every other spike (it is clipped instead).
SNORING_AXIS_PERCENTILE = 99.5
# > 1.0 = spikes drawn bigger (e.g. 1.5), < 1.0 = smaller. Same for whole file.
SNORING_AXIS_GAIN = 1.0

# --- Airflow DISPLAY filter (AASM) ------------------------------------------
# The drawn airflow uses an AASM-style 0.1-15 Hz band-pass from the raw signal.
# Detection continues to use the enhanced copy below.
AIRFLOW_AASM_FILTER_ENABLED = True
AIRFLOW_AASM_LOW_HZ = 0.1
AIRFLOW_AASM_HIGH_HZ = 15.0

# Print diagnostics about repeated flat-topped breaths when debugging clipping.
AIRFLOW_DEBUG_FLAT_TOPS = False

# PERF (upload): the "<file>_airflow_debug_<time>.txt" report used to be
# written on EVERY upload (argsort over the whole airflow signal + disk write
# on the GUI thread). Off by default now; turn on with:
#   $env:PSG_AIRFLOW_DEBUG_REPORT="1"
AIRFLOW_DEBUG_REPORT_ON_UPLOAD = os.environ.get(
    "PSG_AIRFLOW_DEBUG_REPORT", "0"
) not in ("0", "", "false", "False")

# --- SpO2 value labels -----------------------------------------------------
# Which selected time windows (in seconds, exactly as the dropdown sets them)
# get SpO2 numbers on the trace. Every other window shows no labels at all.
#   RAW  -> one label per sample, the original 10s reading view
#   AVG  -> the window is split into buckets and each bucket's MEAN is labelled
SPO2_RAW_LABEL_WINDOWS_SEC = ()
SPO2_AVG_LABEL_WINDOWS_SEC = (10,30,60,120, 300)
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

# What one averaged label shows: "mean" = the true average of the readings in that
# bucket, "median" = the middle reading (the old SpO2 behaviour). They only differ
# when a bucket holds 3+ readings and they are not all the same (e.g. it straddles a
# step). SpO2 and Pulse labels use exactly the same rules; only the numbers differ.
SPO2_LABEL_STAT = "mean"
PULSE_LABEL_STAT = "mean"
# A bucket that straddles a step must show a value that was actually recorded,
# rather than a mix of the upper and lower plateaus.
LABEL_STEP_SHOWS_REAL_VALUE = True
# Where the SpO2 / Pulse numbers sit:
#   "trace" = just above the line, so they move up and down with it
#   "row"   = one straight row at a constant height at the top of the plot
SPO2_LABEL_POSITION = "trace"
PULSE_LABEL_POSITION = "trace"
# SpO2 +/-: keep the top anchored at 100%, and move the floor in these steps.
SPO2_ZOOM_FLOORS = (90, 80, 70, 60, 50, 40, 30, 20, 10, 0)
# Keep this much room below the lowest visible SpO2 sample.
SPO2_FLOOR_MARGIN = 3.0
# None uses the height of a bold 12pt value label plus 2px.
TOP_GAP_PX = None
# Pulse: keep this much room below its lowest visible value.
PULSE_FLOOR_MARGIN = 3.0
# When enabled, a DE-SATURATION box is reduced to only its start and nadir values.
# Disabled so averaged readings remain visible throughout the dip.
DESAT_BOX_TWO_LABELS = False
# Number of seconds around a level change in which labels are suppressed. Zero keeps
# the actual averaged value visible at the edge and inside a dip.
LABEL_STEP_CLEARANCE_SEC = 0.0
# Only a clinically visible dip/rise triggers the clearance rule. Small 1–2 point
# SpO2 fluctuations remain labelled normally.
LABEL_STEP_MIN_CHANGE = 5.0
# The detector marks every stretch where the cannula delivered no breathing signal
# (grey shading on Airflow), but until now only apnea CANDIDATES that fell inside
# such a stretch were listed as SENSOR_OFF events, so a 2.5 h cannula-out showed up
# as one 110 s event. With this on, every detected sensor-off stretch is itself
# listed as a SENSOR_OFF event with its full duration, and the short reassigned
# candidates inside it are folded into it.
SENSOR_OFF_SEGMENTS_AS_EVENTS = True
SENSOR_OFF_EVENT_MIN_SEC = 60.0
SPO2_LABEL_STEP_TOLERANCE = 1.0
PULSE_LABEL_STEP_TOLERANCE = 2.0
# Pulse value labels on the Pulse chart (same windows / buckets as SpO2).
PULSE_LABELS_ENABLED = True
PULSE_LABEL_COLOR = (154, 52, 18)

# Display-only SpO2 artifact handling: short zero/missing runs are bridged;
# longer zero runs remain visible as a drop to 0. Analysis data is unchanged.
SPO2_DISPLAY_BRIDGE_MAX_SECONDS = 60.0
# Recreate the removed SpO2 smoothing in software for the displayed trace.
SPO2_DISPLAY_MEDIAN_WINDOW_SEC = 20.0
# A SpO2 zero run is labeled Sensor off only when it lasts longer than 60 s.
# Runs up to 60 s are bridged in the display and receive no sensor-off label.
SPO2_SENSOR_OFF_LABEL_MIN_SEC = 60.0
ARTIFACT_MIN_SECONDS = SPO2_SENSOR_OFF_LABEL_MIN_SEC
# Warm-up readings below this threshold are replaced once at the start of the
# recording, never separately for each visible window.
SPO2_DISPLAY_WARMUP_MIN = 50.0

# Flow limitation (FL) is a flattening of the INSPIRATORY part of the breath.
# plateau_breaths() treats the upward part of the array it is given as
# inspiration and looks for a flat top there. This recording/export reads HIGH
# on inhale, so no SD inversion is applied.
FL_DETECT_ON_INHALE_SIDE = True

# Snoring chart: red = inhale (main trace), these two are drawn on top.
SNORE_EXHALE_COLOR = "#ef4444"
SNORE_REVIEW_COLOR = "#ef4444"
# Same-color phase overlays add no visual information, so skip their extra
# per-frame drawing by default. Set True to draw them again.
SNORE_PHASE_OVERLAYS_ENABLED = False

# Keep high-rate waveform rendering responsive while preserving peaks.
HIGH_RATE_CHART_NAMES = ("Airflow", "Snoring", "Thorax")
HIGH_RATE_PEAK_DOWNSAMPLING = False
SNORE_PHASE_EXHALE_CODE = 2
SNORE_PHASE_ISOLATED_CODE = 3

# Physiologically possible range per channel. Anything outside is a sensor
# dropout or a probe artifact, NOT a physiological reading. SpO2=0 is kept as
# a recorded no-signal marker so the chart can visibly dip to zero; it is still
# excluded from report/medical calculations.
SIGNAL_VALID_RANGES = {
    "spo2": (50.0, 100.0),
    "pulse": (25.0, 250.0),
}
# SpO2/Pulse dropouts are not interpolated: inventing a reading between two
# oximeter samples can look like a false fluctuation. Display smoothing below
# removes isolated spikes without changing the stored/analysis data.
SIGNAL_NO_GAP_FILL = ("spo2", "pulse")

# ---------------------------------------------------------------------------
# PSG-style desaturation post-processing (AASM + Noxturnal/Profusion/ABOSA)
# One SpO2 drop is one event. A short SpO2/Pulse=0 artifact does not split it.
# ---------------------------------------------------------------------------
DESAT_POSTPROCESS_ENABLED = True
DESAT_SPO2_VALID_RANGE = (50.0, 100.0)
DESAT_ARTIFACT_BRIDGE_SEC = 10.0
DESAT_RECOVERY_RISE = 2.0
DESAT_MAX_FALL_RATE = 4.0
DESAT_MAX_DURATION_SEC = 180.0
# Display only: extend a desaturation box back to the first visible sample
# below its baseline.  The detector's start/duration and all report metrics
# remain untouched.
DESAT_DISPLAY_ONSET_LOOKBACK_SEC = 60.0
DESAT_DISPLAY_BASELINE_TOLERANCE = 0.25


def _desat_valid_mask(values):
    values = np.asarray(values, dtype=float)
    low, high = DESAT_SPO2_VALID_RANGE
    return np.isfinite(values) & (values >= low) & (values <= high)


def _desat_index(times, seconds):
    return int(np.searchsorted(times, float(seconds), side="left"))


def merge_split_desaturations(
    desaturations,
    times,
    spo2,
    max_gap_sec=DESAT_ARTIFACT_BRIDGE_SEC,
    recovery_rise=DESAT_RECOVERY_RISE,
):
    """Merge adjacent desaturations when SpO2 did not recover between them."""
    if not desaturations:
        return []

    times = np.asarray(times, dtype=float)
    spo2 = np.asarray(spo2, dtype=float)
    items = sorted(
        (dict(desaturation) for desaturation in desaturations),
        key=lambda desaturation: float(desaturation["start_sec"]),
    )
    merged = [items[0]]

    for next_desaturation in items[1:]:
        current = merged[-1]
        gap = float(next_desaturation["start_sec"]) - float(current["end_sec"])
        start_index = _desat_index(times, current["end_sec"])
        end_index = min(
            len(spo2),
            _desat_index(times, next_desaturation["start_sec"]) + 1,
        )
        gap_values = spo2[start_index:end_index]
        gap_values = gap_values[_desat_valid_mask(gap_values)]

        try:
            current_nadir = float(current.get("nadir_spo2"))
        except (TypeError, ValueError):
            current_nadir = float("nan")

        no_recovery = (
            gap_values.size == 0
            or not np.isfinite(current_nadir)
            or float(gap_values.max()) < current_nadir + float(recovery_rise)
        )
        if gap <= float(max_gap_sec) and no_recovery:
            current["end_sec"] = max(
                float(current["end_sec"]),
                float(next_desaturation["end_sec"]),
            )
            try:
                next_nadir = float(next_desaturation.get("nadir_spo2"))
            except (TypeError, ValueError):
                next_nadir = current_nadir
            nadirs = [
                value
                for value in (current_nadir, next_nadir)
                if np.isfinite(value)
            ]
            if nadirs:
                current["nadir_spo2"] = min(nadirs)
                try:
                    current["drop_percent"] = (
                        float(current.get("baseline_spo2")) - current["nadir_spo2"]
                    )
                except (TypeError, ValueError):
                    pass
            current["duration_sec"] = (
                current["end_sec"] - float(current["start_sec"])
            )
            current["merged_parts"] = int(current.get("merged_parts", 1)) + 1
        else:
            merged.append(next_desaturation)

    return merged


def flag_desat_quality(
    desaturations,
    times,
    spo2,
    max_fall_rate=DESAT_MAX_FALL_RATE,
    max_duration_sec=DESAT_MAX_DURATION_SEC,
):
    """Flag unusually fast (>4%/s) or unusually long desaturations for review."""
    times = np.asarray(times, dtype=float)
    spo2 = np.asarray(spo2, dtype=float)

    for desaturation in desaturations:
        start_index = _desat_index(times, float(desaturation["start_sec"]) - 5.0)
        end_index = min(
            len(spo2),
            _desat_index(times, desaturation["end_sec"]) + 1,
        )
        segment = spo2[start_index:end_index]
        segment_times = times[start_index:end_index]
        valid_indices = np.flatnonzero(_desat_valid_mask(segment))
        flags = []

        if valid_indices.size >= 2:
            inside = valid_indices[
                segment_times[valid_indices] >= float(desaturation["start_sec"])
            ]
            nadir_index = (
                inside[np.argmin(segment[inside])]
                if inside.size
                else valid_indices[-1]
            )
            before = valid_indices[valid_indices < nadir_index]
            if before.size:
                peak_value = segment[before].max()
                fall_start = before[segment[before] >= peak_value].max()
                fall_seconds = max(
                    float(segment_times[nadir_index] - segment_times[fall_start]),
                    1e-3,
                )
                fall_rate = (
                    float(segment[fall_start] - segment[nadir_index]) / fall_seconds
                )
                desaturation["fall_rate_pct_per_sec"] = round(fall_rate, 2)
                if fall_rate > float(max_fall_rate):
                    flags.append("fall_rate_too_fast")

        if (
            float(desaturation["end_sec"]) - float(desaturation["start_sec"])
            > float(max_duration_sec)
        ):
            flags.append("too_long")

        desaturation["quality_flags"] = flags
        desaturation["needs_review"] = bool(flags)

    return desaturations

# Body Position processing settings.
BODY_POSITION_BRIDGE_SEC = 10.0    # unknown stretches up to this long are bridged (0 = old)
BODY_POSITION_DEFLICKER_SEC = 0.0  # 1.0 = remove position flips shorter than ~1 s

# Room above every plot, in pixels. The top tick label of each chart (1400, 15,
# 2600, 100, 110 ...) is centred on the top edge of the plot, so with the plot
# layout margins at 0 its upper half fell outside the widget and was clipped.
# The bottom stays flush so the time axis still hugs the container edge.
PLOT_TOP_MARGIN_PX = 6

# Deleted auto events are matched by geometry, not exact keys, so a small
# parameter change during re-analysis does not resurrect the same event.
DELETED_EVENT_EDGE_TOLERANCE_SEC = 1.0
DELETED_EVENT_MIN_OVERLAP_RATIO = 0.7

AIRFLOW_DROP_MIN_DURATION_SEC = 2.0
AIRFLOW_EVENT_MAX_DURATION_SEC = None
AIRFLOW_BASELINE_MIN_OCCURRENCE = 30

# Prints one line per frame with the time each chart took to refresh. Turn off
# after diagnosing playback stutter.
PERF_FRAME_PROFILE = False
# One summary line per second of playback (no per-frame printing, no repaint, so it
# does not disturb the thing being measured). Enable WITHOUT editing code:
#   PowerShell:  $env:PSG_PROFILE=1 ; python main.py
PERF_SUMMARY = os.environ.get("PSG_PROFILE", "0") not in ("0", "", "false", "False")
# While playing or scrubbing the Y scale is held (no per-frame "breathing"). After a jump
# of more than half a window (event click, slider, arrows) the held scale belongs to a
# different part of the night: Effort looks flat, Snoring clips. True = refit those two
# channels once on such a page turn (and once per ~30 s of normal playback).
# False = previous behaviour (scale held until pause / seek release).
AXIS_REFIT_ON_JUMP = True

def _physical_screen_width():
    """Real pixel width of the primary display on Windows (0 if unknown).

    GetSystemMetrics(SM_CXSCREEN) returns the DPI-VIRTUALISED width for a process
    that is not DPI-aware yet.  This module is imported before QApplication exists,
    so a 1920x1080 laptop at 150 % scaling reports 1280 and was wrongly treated as an
    old <=1366 px screen (strip playback switched off).  DESKTOPHORZRES is the real
    pixel width regardless of DPI awareness.
    """
    if os.name != "nt":
        return 0
    try:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        user32.GetDC.restype = ctypes.c_void_p
        user32.GetDC.argtypes = [ctypes.c_void_p]
        user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        gdi32.GetDeviceCaps.argtypes = [ctypes.c_void_p, ctypes.c_int]
        hdc = user32.GetDC(None)
        if not hdc:
            return 0
        try:
            return int(gdi32.GetDeviceCaps(hdc, 118))      # DESKTOPHORZRES
        finally:
            user32.ReleaseDC(None, hdc)
    except Exception:
        return 0


def _is_legacy_display():
    """True on an old / compact screen (<=1366 physical px wide on Windows) where a
    full bitmap-tile capture per page cannot keep up with playback. Shared by the
    strip-mode default below and by _playback_frame_interval_ms() further down,
    so both react the same way to the same machine."""
    override = os.environ.get("PSG_LEGACY_DISPLAY", "").strip()
    if override:
        return override not in ("0", "", "false", "False")
    try:
        if os.name == "nt":
            width = _physical_screen_width() or int(ctypes.windll.user32.GetSystemMetrics(0))
            if width and width <= 1366:
                return True
    except Exception:
        pass
    return False


def _psg_playback_log(message):
    """Append one line to <temp>/sleep_sense_playback.log.

    The playback code swallows exceptions on purpose (a UI must never crash while
    scrolling), which also hides WHY the smooth strip path was dropped for the
    slower translate path.  This leaves a trace on the user's machine / in the .exe.
    """
    try:
        import tempfile
        path = Path(tempfile.gettempdir()) / "sleep_sense_playback.log"
        if path.exists() and path.stat().st_size > 256 * 1024:
            path.unlink()
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(time.strftime("%Y-%m-%d %H:%M:%S ") + str(message) + "\n")
    except Exception:
        pass


# Playback strip (YouTube-style): while playing, the plot areas are covered by a canvas that only
# scrolls pre-captured bitmap tiles of the live charts. This is the system the Effort-autoscale
# work elsewhere in this file (hysteresis, robust fit, attack/release) was built and tuned for, and
# it is what makes playback smooth on a normal machine - so it stays ON by default there.
# On an old / compact display (_is_legacy_display()) capturing seven tiles per page can fall behind,
# which shows as the strip "rebuffering": playback stalls as if stuck loading from the right edge.
# There it falls back automatically to the lighter translate-based path instead.
# Set PSG_STRIP=1 / 0 to force it on/off on any machine regardless of the above.
_PSG_STRIP_ENV = os.environ.get("PSG_STRIP", "").strip()
if _PSG_STRIP_ENV:
    PLAYBACK_STRIP_MODE = _PSG_STRIP_ENV not in ("0", "", "false", "False")
else:
    PLAYBACK_STRIP_MODE = not _is_legacy_display()
try:
    from .live_capture_strip import LiveCaptureStrip
except Exception:                      # module not installed -> strip mode is simply unavailable
    LiveCaptureStrip = None


class _PlaybackPerf:
    """Collects playback timings and prints one health line per second.

    When the playing widget is passed as `owner`, the same line is also shown in a
    small overlay on the charts, so a screen recording carries the numbers with it.
    """

    def __init__(self):
        self._hud = None
        self._last_line = "[PERF] -"
        self._reset(time.perf_counter())

    def _reset(self, now):
        self.t0 = now
        self.gaps = []
        self.work = []
        self.translate = []
        self.refreshes = []
        self.drops = 0

    def add_drop(self):
        self.drops += 1

    def add_refresh(self, total_ms, parts):
        try:
            self.refreshes.append((float(total_ms), dict(parts)))
        except Exception:
            pass

    def _show_hud(self, owner, line):
        self._last_line = line
        hud = self._hud
        if hud is None or sip.isdeleted(hud):
            hud = QLabel(owner)
            hud.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            hud.setStyleSheet(
                "background: rgba(0, 0, 0, 190); color: #7CFC00;"
                " font: 9pt 'Consolas'; padding: 2px 6px;"
            )
            hud.move(70, 2)
            self._hud = hud
            # F8 = one-off paint breakdown (see _perf_paint_breakdown).
            shortcut = QShortcut(QKeySequence("F8"), owner)
            shortcut.setContext(Qt.ApplicationShortcut)
            shortcut.activated.connect(owner._perf_paint_breakdown)
            self._f8 = shortcut
        if owner.__dict__.get("_dwm_worker") is not None:
            pacer = "DWM vsync"
        else:
            pacer = "QTimer"
        if owner.__dict__.get("_strip") is not None:
            pacer += "+STRIP"
        speed = owner.__dict__.get("playback_speed", 1.0)
        text = f"pacer={pacer} speed={speed:g}x | " + line.replace("[PERF] ", "", 1)
        note = owner.__dict__.get("_perf_note")
        if note and time.monotonic() < note[1]:
            text += "\n" + note[0]
        hud.setText(text)
        hud.adjustSize()
        hud.raise_()
        hud.show()

    def add_tick(self, gap_ms, work_ms, parts, owner=None):
        # The profiler must never be able to break playback, whatever happens here.
        try:
            # A gap this long is a Pause -> Play resume, not a stall: skip it.
            if gap_ms < 1500.0:
                self.gaps.append(float(gap_ms))
            self.work.append(float(work_ms))
            if "translate" in parts:
                self.translate.append(float(parts["translate"]))
            now = time.perf_counter()
            if now - self.t0 < 1.0:
                return
            if not self.gaps or not self.work:
                self._reset(now)
                return
            gaps = np.asarray(self.gaps, dtype=float)
            work = np.asarray(self.work, dtype=float)
            line = (
                f"[PERF] ticks={len(gaps)} dropped={self.drops} | "
                f"gap ms avg={gaps.mean():.1f} p95={np.percentile(gaps, 95):.1f} max={gaps.max():.0f} | "
                f"update_playback ms avg={work.mean():.1f} max={work.max():.0f}"
            )
            if self.translate:
                tr = np.asarray(self.translate, dtype=float)
                line += f" | translate avg={tr.mean():.1f} max={tr.max():.1f}"
            if self.refreshes:
                worst = max(self.refreshes, key=lambda item: item[0])
                detail = " ".join(f"{k}={v:.0f}" for k, v in worst[1].items() if v >= 1.0)
                line += f" | refresh x{len(self.refreshes)} worst={worst[0]:.0f}ms [{detail}]"
            pass
            if owner is not None:
                self._show_hud(owner, line)
            self._reset(now)
        except Exception:
            try:
                self._reset(time.perf_counter())
            except Exception:
                pass


_PERF = _PlaybackPerf()


class _DwmVsyncThread(QThread):
    """Emit at most one queued GUI tick per Windows compositor refresh."""

    frame_ready = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, parent=None, flush_func=None):
        super().__init__(parent)
        self._flush_func = flush_func
        self._tick_pending = False

    def acknowledge_tick(self):
        # Python bool access is atomic under the GIL. Keeping this tiny avoids
        # putting a lock in the once-per-frame hot path.
        self._tick_pending = False

    @staticmethod
    def _windows_flush():
        if os.name != "nt":
            raise OSError("DwmFlush is available only on Windows")
        flush = ctypes.WinDLL("dwmapi", use_last_error=True).DwmFlush
        flush.argtypes = []
        flush.restype = ctypes.c_long
        return flush

    def run(self):
        try:
            flush = self._flush_func or self._windows_flush()
        except Exception as error:
            self.failed.emit(str(error))
            return

        while not self.isInterruptionRequested():
            started = time.perf_counter()
            try:
                result = int(flush())
            except Exception as error:
                self.failed.emit(str(error))
                return
            if result != 0:
                self.failed.emit(f"DwmFlush HRESULT 0x{result & 0xffffffff:08X}")
                return

            elapsed = time.perf_counter() - started
            # A healthy DwmFlush blocks until the compositor boundary. If it
            # returns immediately, cap the loop so a driver anomaly cannot
            # consume a CPU core or flood Qt's event queue.
            if elapsed < 0.002:
                self.msleep(max(1, int(round((1.0 / 60.0 - elapsed) * 1000.0))))

            if self.isInterruptionRequested():
                return
            if not self._tick_pending:
                self._tick_pending = True
                self.frame_ready.emit()
            elif PERF_SUMMARY:
                # The GUI has not consumed the previous compositor boundary.
                # Count it, but never enqueue it for catch-up playback.
                _PERF.add_drop()


PLAYBACK_LEAN_REPAINT = True
OVERLAY_FORCE_REPAINT = True

# Keep antialiasing enabled during playback. At 1x the trace moves by less than
# one physical pixel per captured frame; disabling AA quantizes that motion into
# repeated frames followed by one-pixel jumps, which looks like jitter.
PLAYBACK_DISABLE_ANTIALIAS = False


# Playback advances in real time at the displayed 1.0x speed.
PLAYBACK_TIME_SCALE = 1.0
# Target 60 Hz on normal displays and 30 Hz on compact screens.  The latter
# halves GUI paint pressure on older 1366x768 machines while the wall-clock
# playback calculation below keeps the signal position and speed exact.
def _playback_frame_interval_ms():
    override = os.environ.get("PSG_FRAME_MS", "").strip()
    if override:
        try:
            return max(16, min(100, int(override)))
        except (TypeError, ValueError):
            pass
    if _is_legacy_display():
        return 33
    return 16


PLAYBACK_FRAME_INTERVAL_MS = _playback_frame_interval_ms()
# Keep the pre-rendered playback tiles over a Pause so the next Play starts at once instead of
# re-rendering three pages first.  Set the environment variable PSG_STRIP_REUSE=0 to switch it off.
PLAYBACK_STRIP_REUSE = os.environ.get("PSG_STRIP_REUSE", "1").strip() not in ("0", "", "false", "False")
STRIP_REUSE_MAX_AGE_SEC = 300.0
PLAYBACK_DECORATION_UPDATE_HZ = 12
# Rebuilding seven paths (plus labels/events) is substantially more expensive
# than moving paths that are already on screen. Re-slice the source data once
# a second; between those refreshes translate the existing graphics at
# the timer cadence. The result remains data-accurate but no longer advances
# in visible chunks when one full refresh takes longer than a video frame.
PLAYBACK_DATA_REFRESH_SEC = 1.0
# --- Adaptive source-data refresh (fixes the right-edge stall on old PCs) ----------------------
# During playback most frames only TRANSLATE the existing paths (cheap). Once
# every PLAYBACK_DATA_REFRESH_SEC the seven paths are fully rebuilt from source
# (expensive). On a slow machine that single rebuild tick takes far longer than
# one video frame, so the window freezes for a moment and the right edge appears
# to "load"/stutter. We therefore let the interval GROW when a rebuild is
# measured to be expensive (fewer, better-hidden hitches) and stay short when it
# is cheap (tighter tail on a fast machine). The off-screen tail that the cheap
# frames scroll into view is sized from the interval ACTUALLY used, so it never
# runs dry between rebuilds and no blank strip can appear at the right.
# Timing/position are wall-clock based and unaffected by this.
PLAYBACK_REFRESH_ADAPTIVE = os.environ.get("PSG_ADAPTIVE_REFRESH", "1") not in ("0", "", "false", "False")
PLAYBACK_REFRESH_MIN_SEC = 0.8      # fastest full-rebuild cadence (fast machine)
PLAYBACK_REFRESH_MAX_SEC = 2.5      # slowest (very slow machine) - longer tail covers it
PLAYBACK_REFRESH_COST_SMOOTHING = 0.25   # EMA weight for the measured rebuild cost
# A rebuild is "expensive" when it eats more than this fraction of the interval;
# the interval is then stretched so the hitch is a smaller share of each cycle.
PLAYBACK_REFRESH_COST_BUDGET = 0.35
PLAYBACK_DT_SMOOTHING = 0.12
PLAYBACK_SMOOTHING_MAX_FRAME_SEC = 0.024
PLAYBACK_SLIDER_UPDATE_HZ = 10
PLAYBACK_DRIFT_CORRECTION = 0.05
PLAYBACK_RESYNC_SEC = 0.5
PLAYBACK_SEGMENTED_LINES = False
PLAYBACK_THIN_LINES = False
PLAYBACK_LINE_WIDTH = 1.0   # keep <= 1.0, above 1.0 the speed-up is lost
PLAYBACK_USE_OPENGL = False
# Opt-in A/B test: synchronize raster playback ticks to Windows DWM instead
# of asking a 16 ms QTimer (62.5 Hz) to feed a 60 Hz compositor.
PLAYBACK_USE_DWM_VSYNC = (
    os.name == "nt"
    and os.environ.get("PSG_VSYNC", "0") not in ("0", "", "false", "False")
)


def configure_opengl_for_playback():
    """Call ONCE before QApplication is created."""
    if not PLAYBACK_USE_OPENGL:
        return
    fmt = QSurfaceFormat()
    fmt.setSwapInterval(1)        # wait for vsync on every swap
    fmt.setSamples(4)             # GPU antialiasing
    QSurfaceFormat.setDefaultFormat(fmt)
    pg.setConfigOptions(useOpenGL=True, enableExperimental=True)


OVERLAY_AXIS_INSET_PX = 1.5

DETECTION_IMPORT_ERROR = None
try:
    from ai_models.sleep_apnea.detect_apnea_from_airflow import detect_apnea_events_from_recording
    from ai_models.sleep_apnea import detect_apnea_from_airflow as _apnea_rules
except Exception as import_error:
    detect_apnea_events_from_recording = None
    _apnea_rules = None
    DETECTION_IMPORT_ERROR = str(import_error)

RECORDING_IMPORT_ERROR = None
try:
    from ai_models.sleep_apnea.hybrid_pipeline_common import (
        MIN_RECORDING_SECONDS,
        load_sleep_recording,
        require_minimum_recording,
        trim_recording_edges,
    )
except Exception as import_error:
    MIN_RECORDING_SECONDS = 60.0 * 60.0
    load_sleep_recording = None
    require_minimum_recording = None
    trim_recording_edges = None
    RECORDING_IMPORT_ERROR = str(import_error)

# Sensor readings are unstable immediately after setup and just before removal.
# These edges are excluded from charts, navigation, detection and all metrics.
RECORDING_EDGE_TRIM_SECONDS = 5.0 * 60.0
# Effort belt "not connected" check, kept aligned with the detector threshold.
THORAX_MIN_VALID_SWING_COUNTS = 4.0
# Airflow "cannula not connected" display threshold.
AIRFLOW_MIN_VALID_SWING_COUNTS = 10.0

# --- Loading spinner (round rotating circle) -------------------------------
class LoadingSpinner(QWidget):
    """Small rotating arc, drawn with QPainter (no image files needed)."""

    def __init__(self, parent=None, size=28, line_width=3, color="#2563EB"):
        super().__init__(parent)
        self._angle = 0
        self._line_width = line_width
        self._color = QColor(color)
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._rotate)
        self.hide()

    def start(self):
        self.show()
        if not self._timer.isActive():
            self._timer.start()

    def stop(self):
        self._timer.stop()
        self.hide()

    def _rotate(self):
        self._angle = (self._angle + 8) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        m = self._line_width
        rect = QRectF(m, m, self.width() - 2 * m, self.height() - 2 * m)
        track = QColor(self._color)
        track.setAlpha(45)
        pen = QPen(track, self._line_width)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawEllipse(rect)
        pen.setColor(self._color)
        painter.setPen(pen)
        # Qt angles are in 1/16 degree, counter-clockwise; minus = clockwise.
        painter.drawArc(rect, int(-self._angle * 16), int(100 * 16))
        painter.end()


class BusyOverlay(QWidget):
    """Semi-transparent cover with a centred spinner + message over `target`."""

    def __init__(self, target, message="Loading...", spinner_size=42):
        super().__init__(target)
        self._target = target
        self.setObjectName("BusyOverlay")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "QWidget#BusyOverlay { background-color: rgba(255, 255, 255, 190);"
            " border-radius: 8px; }"
        )
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(10)
        self.spinner = LoadingSpinner(self, size=spinner_size, line_width=4)
        self.label = QLabel(message, self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setStyleSheet(
            "background: transparent; color: #1e3a8a; font-size: 12px; font-weight: 600;"
        )
        layout.addWidget(self.spinner, 0, Qt.AlignHCenter)
        layout.addWidget(self.label, 0, Qt.AlignHCenter)
        target.installEventFilter(self)
        # Panels may add new child widgets while we are shown; keep on top.
        self._raise_timer = QTimer(self)
        self._raise_timer.setInterval(300)
        self._raise_timer.timeout.connect(self.raise_)
        self.hide()

    def eventFilter(self, obj, event):
        if obj is self._target and event.type() in (QEvent.Resize, QEvent.Show):
            self.setGeometry(self._target.rect())
        return False

    def start(self, message=None):
        if message is not None:
            self.label.setText(message)
        self.setGeometry(self._target.rect())
        self.show()
        self.raise_()
        self.spinner.start()
        self._raise_timer.start()

    def stop(self):
        self._raise_timer.stop()
        self.spinner.stop()
        self.hide()

    def set_message(self, message):
        self.label.setText(message)

    # Swallow clicks so nothing underneath is pressed while busy.
    def mousePressEvent(self, event):
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()

    def wheelEvent(self, event):
        event.accept()


class SpeedSelector(QWidget):
    """Segmented playback-speed selector: [1x | 2x | 3x | 4x].  Click = exactly that speed.

    It replaces the drag slider.  A QSlider moves by its pageStep (10) when its groove is
    clicked, so on a 1..4 range every click landed on 4x (or back on 1x) instead of on the
    clicked position.  Preset buttons are also what media / review tools use for discrete
    speeds.  Same tiny API as QSlider (value / setValue / valueChanged, blockSignals) so the
    rest of the code does not change.
    """

    valueChanged = pyqtSignal(int)

    _STYLE = """
        QPushButton {
            background-color: #ffffff;
            color: #475569;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 0px;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 10px;
            font-weight: 600;
        }
        QPushButton:hover { background-color: #eff6ff; color: #1d4ed8; }
        QPushButton:checked {
            background-color: #2563eb;
            color: #ffffff;
            border-color: #2563eb;
        }
        QPushButton#speedSegFirst {
            border-top-left-radius: 8px;
            border-bottom-left-radius: 8px;
        }
        QPushButton#speedSegLast {
            border-top-right-radius: 8px;
            border-bottom-right-radius: 8px;
        }
    """

    def __init__(self, values=(1, 2, 3, 4), parent=None):
        super().__init__(parent)
        self.setObjectName("speedSelector")
        self._values = tuple(int(v) for v in values)
        self._value = self._values[0]
        self._buttons = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        gap = 3
        layout.setSpacing(gap)
        last = len(self._values) - 1
        for index, speed in enumerate(self._values):
            button = QPushButton("%dx" % speed)
            button.setCheckable(True)
            button.setFixedSize(30, 23)
            button.setFocusPolicy(Qt.NoFocus)          # Space must keep toggling Play
            button.setCursor(Qt.PointingHandCursor)
            button.setToolTip("Playback speed %dx" % speed)
            button.setObjectName(
                "speedSegFirst" if index == 0 else "speedSegLast" if index == last else "speedSegMid"
            )
            button.clicked.connect(lambda _checked=False, value=speed: self.setValue(value))
            layout.addWidget(button)
            self._buttons[speed] = button
        self.setFixedSize(30 * len(self._values) + gap * (len(self._values) - 1), 23)
        self.setStyleSheet(self._STYLE)
        self._show_checked()

    def _show_checked(self):
        for speed, button in self._buttons.items():
            button.setChecked(speed == self._value)

    def value(self):
        return self._value

    def setValue(self, value):
        value = min(self._values, key=lambda candidate: abs(candidate - float(value)))
        changed = value != self._value
        self._value = value
        self._show_checked()                        # also re-checks a button that was clicked twice
        if changed:
            self.valueChanged.emit(value)


class PlayPauseButton(QPushButton):
    """Play / Pause transport button with DRAWN symbols instead of text / emoji glyphs.

    The old button showed "▶ Play" (a plain text glyph) and "⏸ Pause" (an emoji-font glyph that
    Windows paints as a coloured square), so the two states did not look like one control.
    Both states now use the same white, drawn symbol (triangle / two bars), the same label
    style, the same width and height.  The rest of the code keeps calling
    setText("▶ Play") / setText("⏸ Pause") / setText("Detecting..."): setText maps those to
    the right state, so no other call site has to change.

    The symbol is drawn at the screen's real pixel ratio, so Qt never has to rescale it
    (a scaled bitmap made the triangle's slanted edges look jagged).
    """

    _ICON_SIZE = 12

    def __init__(self, parent=None):
        super().__init__(parent)
        self._icons = {}
        self._state = None
        self.setIconSize(QSize(self._ICON_SIZE, self._ICON_SIZE))
        self.setText("Play")

    def _symbol(self, kind):
        from PyQt5.QtGui import QPolygonF
        ratio = max(1.0, float(self.devicePixelRatioF()))
        key = (kind, round(ratio, 2))
        icon = self._icons.get(key)
        if icon is None:
            side = self._ICON_SIZE
            pixels = max(side, int(round(side * ratio)))
            pixmap = QPixmap(pixels, pixels)
            pixmap.fill(Qt.transparent)
            pixmap.setDevicePixelRatio(pixels / float(side))   # logical size stays exactly 12 x 12
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#ffffff"))
            if kind == "play":
                painter.drawPolygon(QPolygonF([QPointF(3.0, 1.0), QPointF(10.8, 6.0), QPointF(3.0, 11.0)]))
            else:
                painter.drawRoundedRect(QRectF(2.0, 1.0, 3.0, 10.0), 0.8, 0.8)
                painter.drawRoundedRect(QRectF(7.0, 1.0, 3.0, 10.0), 0.8, 0.8)
            painter.end()
            icon = QIcon(pixmap)
            self._icons[key] = icon
        return icon

    def setText(self, text):
        label = str(text)
        if "Pause" in label:
            self._state = "pause"
            super().setText("Pause")
            self.setIcon(self._symbol("pause"))
        elif "Play" in label:
            self._state = "play"
            super().setText("Play")
            self.setIcon(self._symbol("play"))
        else:                                           # e.g. "Detecting..." (button disabled)
            self._state = None
            super().setText(label)
            self.setIcon(QIcon())

    def showEvent(self, event):
        # The screen (and so the pixel ratio) is only known once the button is shown / moved.
        if self._state:
            self.setIcon(self._symbol(self._state))
        super().showEvent(event)


from PyQt5.QtCore import QObject as _QObject


class _StripReuseGuard(_QObject):
    """Watches the whole application, but ONLY while the tiles of a paused Play are being kept for the next Play.

    A click, key press (except Space) or wheel turn anywhere other than the Play button and the speed buttons
    could change what the charts show (an event edited or deleted, a Y zoom, a setting).  The first such input
    marks the kept tiles as dirty and the next Play builds them again from scratch.
    """

    _WATCHED = (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick, QEvent.Wheel, QEvent.KeyPress)

    def __init__(self, owner):
        super().__init__(owner)
        self._owner = owner

    def eventFilter(self, obj, event):
        try:
            kind = event.type()
            if kind in self._WATCHED and not (kind == QEvent.KeyPress and event.key() == Qt.Key_Space):
                if not self._owner._strip_reuse_source_ok(obj):
                    self._owner._strip_cache_dirty = True
        except Exception:
            self._owner._strip_cache_dirty = True
        return False


class SleepMonitorChart(QWidget):
    """Sleep Monitoring Chart Widget"""
    raw_data_saved = pyqtSignal(str, str)  # file_path, timestamp_iso
    time_position_updated = pyqtSignal()  # Signal when time position changes
    time_window_mode_changed = pyqtSignal(bool)  # True when All PSG mode is active
    apnea_events_updated = pyqtSignal(object)  # list[dict]
    detection_busy_changed = pyqtSignal(bool)  # True while events are being detected
    _fl_ready = pyqtSignal(object)  # (airflow array, flow-limited breaths) from the background FL analysis

    class _SaveWorker(QThread):
        """
        Keep saving in a background thread so the UI does not freeze.
        """
        done = pyqtSignal(int, str, str)  # session_id, saved_at, copied_recording_path
        failed = pyqtSignal(str)  # error message

        def __init__(self, patient_id, source_recording_path, parent_session_id=None, parent=None):
            super().__init__(parent)
            self.patient_id = patient_id
            self.source_recording_path = source_recording_path
            self.parent_session_id = parent_session_id

        def run(self):
            try:
                session_id, saved_at, copied_recording_path = save_raw_recording_session(
                    self.patient_id,
                    self.source_recording_path,
                    parent_session_id=self.parent_session_id,
                )
                self.done.emit(session_id, saved_at, copied_recording_path)
            except Exception as e:
                self.failed.emit(str(e))

    class _DetectWorker(QThread):
        """Run the apnea detector off the UI thread."""
        done = pyqtSignal(object, str)
        failed = pyqtSignal(str, str)

        def __init__(self, recording_path, output_dir, trim_seconds=0.0, parent=None):
            super().__init__(parent)
            self.recording_path = str(recording_path)
            self.output_dir = output_dir
            self.trim_seconds = float(trim_seconds)

        def run(self):
            try:
                _t_detect = time.perf_counter()
                result = detect_apnea_events_from_recording(
                    recording_path=self.recording_path, output_dir=self.output_dir, enable_ai=False,
                    trim_start_seconds=self.trim_seconds,
                    trim_end_seconds=self.trim_seconds,
                )
                _psg_playback_log("detector worker: %.0f ms" % ((time.perf_counter() - _t_detect) * 1000.0))
                self.done.emit(result, self.recording_path)
            except Exception as error:
                import traceback
                full_traceback = traceback.format_exc()
                # Full traceback on the console for debugging.
                print(full_traceback, file=sys.stderr)
                # Also keep a log file next to the detector output.
                try:
                    log_dir = Path(self.output_dir)
                    log_dir.mkdir(parents=True, exist_ok=True)
                    with open(log_dir / "detection_error.log", "a", encoding="utf-8") as log_file:
                        log_file.write(
                            f"\n===== {datetime.now():%Y-%m-%d %H:%M:%S} | {self.recording_path} =====\n"
                            f"{full_traceback}"
                        )
                except Exception:
                    pass
                # Short message for the UI that includes where it failed.
                location = ""
                frames = traceback.extract_tb(error.__traceback__)
                if frames:
                    last_frame = frames[-1]
                    location = f" (at {os.path.basename(last_frame.filename)}:{last_frame.lineno})"
                self.failed.emit(f"{error}{location}", self.recording_path)

    class _CallWorker(QThread):
        """Run one plain-Python function in a thread (used for file parsing)."""

        def __init__(self, fn, args, parent=None):
            super().__init__(parent)
            self.fn = fn
            self.args = args
            self.result = None
            self.error = None

        def run(self):
            try:
                self.result = self.fn(*self.args)
            except Exception as error:
                import traceback
                traceback.print_exc()
                self.error = error

    class _MetricsWorker(QThread):
        """PERF (upload): calculate_sleep_metrics + JSON save off the UI thread."""
        done = pyqtSignal(object, object, str)  # results, json_path, recording_path
        failed = pyqtSignal(str, str)

        def __init__(self, recording_path, time_data, signals, sleep_mask, master_rate,
                     channel_rates, channel_times, parent=None):
            super().__init__(parent)
            self.recording_path = str(recording_path)
            self.time_data = time_data
            # Shallow copy: GUI thread may swap entries while this runs.
            self.signals = dict(signals)
            self.sleep_mask = sleep_mask
            self.master_rate = master_rate
            self.channel_rates = dict(channel_rates)
            self.channel_times = dict(channel_times)

        def run(self):
            try:
                try:
                    results = calculate_sleep_metrics(
                        self.time_data, self.signals, sleep_mask=self.sleep_mask,
                        sample_rate_hz=self.master_rate,
                        sample_rates=self.channel_rates, channel_times=self.channel_times,
                    )
                except TypeError:
                    results = calculate_sleep_metrics(
                        self.time_data, self.signals, sleep_mask=self.sleep_mask,
                        sample_rate_hz=self.master_rate,
                    )
                json_path = save_sleep_metrics_json(
                    results, source_recording=self.recording_path,
                )
                self.done.emit(results, json_path, self.recording_path)
            except Exception as error:
                self.failed.emit(str(error), self.recording_path)
    
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
        self.playback_timer.setTimerType(Qt.PreciseTimer)
        self.playback_timer.timeout.connect(self.update_playback)
        self._dwm_worker = None
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._stop_playback_pacer)
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
        self._spo2_display_cache = None
        self.psg_full_data = None  # Store full PSG data for all signals
        self.current_psg_data = None  # Report-friendly full-channel PSG payload
        self.current_time_offset = 0  # Current starting time for window
        self.all_psg_mode = False  # When True, render the entire recording in one view
        self.current_recording_path = None
        self.analysis_results = None
        self.analysis_json_path = None
        self._save_in_progress = False
        self._worker = None
        self._detect_worker = None
        self._detection_running = False
        self._metrics_worker = None
        self._pending_focus_first_event = None
        self._upload_loading_path = None
        self._pending_detection_result = None
        self._upload_overlay = None
        self._events_panel_overlay = None
        self._events_panel_widget = None
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
        self.loaded_recording_path = None
        self.auto_rule_ai_result = None
        self.sensor_off_shade_segments = []  # airflow sensor-off ranges drawn on the chart
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
        self._snoring_axis_cache = None
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
        """Convert body position data into canonical 0..4 codes; 5 is a gap."""
        array = np.asarray(values)
        if array.size == 0:
            return np.asarray([], dtype=float)

        if array.dtype.kind in "iuf":
            # Fast path: the loader already produced numbers.
            numeric = array.astype(float).reshape(-1)
            codes = np.rint(numeric)
            codes[~np.isfinite(numeric)] = np.nan
        else:
            # Mixed / label data: still vectorised, no Python loop.
            text = pd.Series(array.reshape(-1)).astype(str).str.strip().str.lower()
            mapped = text.map(BODY_POSITION_LABEL_TO_CODE)
            numeric = pd.to_numeric(text, errors="coerce")
            codes = mapped.astype(float).fillna(numeric).to_numpy(dtype=float)
            codes = np.rint(codes)

        unknown_mask = ~np.isfinite(codes) | (codes >= BODY_POSITION_UNKNOWN) | (codes < 0)
        codes = np.where(unknown_mask, np.nan, codes)
        codes = np.clip(codes, 0, 4)
        series = pd.Series(codes)
        series = series.interpolate(limit_direction="both").ffill().bfill()
        result = np.array(series.to_numpy(dtype=float), dtype=float, copy=True)
        result[unknown_mask] = np.nan
        return self._finish_body_position_display(result, unknown_mask, codes)

    def _finish_body_position_display(self, result, unknown_mask, codes):
        """Bridge short unknown stretches and (optionally) de-flicker, display only."""
        try:
            rate = float(self.channel_rate("body_position"))
        except Exception:
            rate = float(EXTERNAL_ARRAY_SAMPLE_RATE_HZ)
        if not np.isfinite(rate) or rate <= 0.0:
            return result

        bridge_samples = int(round(float(BODY_POSITION_BRIDGE_SEC) * rate))
        if bridge_samples > 0 and unknown_mask.any():
            held = pd.Series(np.where(unknown_mask, np.nan, codes)).ffill().to_numpy(dtype=float)
            unknown_idx = np.flatnonzero(unknown_mask)
            for run in np.split(unknown_idx, np.where(np.diff(unknown_idx) > 1)[0] + 1):
                if not run.size or run.size > bridge_samples:
                    continue
                if np.isfinite(held[run[0]]):
                    result[run] = held[run]
                elif run[0] == 0:
                    # The recording starts with unknown samples (the position sensor is
                    # still warming up), so there is no earlier position to hold. Draw the
                    # first known position back to t=0 instead of leaving the chart blank.
                    following = run[-1] + 1
                    if following < codes.size and np.isfinite(codes[following]):
                        result[run] = codes[following]

        window = int(round(float(BODY_POSITION_DEFLICKER_SEC) * rate))
        if window >= 3:
            window |= 1
            finite = np.isfinite(result)
            if finite.any():
                filtered = (
                    pd.Series(result)
                    .rolling(window=window, center=True, min_periods=1)
                    .median()
                    .to_numpy(dtype=float)
                )
                result = np.where(finite, np.rint(filtered), np.nan)
        return result

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
        self._spo2_display_cache = None
        self._slow_display_cache = {}
        self._airflow_axis_range_cache = None
        self._auto_axis_range_cache = {}
        self._snoring_axis_cache = None
        self._last_events_signature = None
        self._last_detection_summary_text = None
        self._exclusion_cache = None

    def get_recording_exclusions(self):
        data = self.psg_full_data or {}
        if getattr(self, "_exclusion_cache", None) is None or getattr(self, "_exclusion_data", None) is not data:
            self._exclusion_data = data
            summary = exclusion_summary(
                self.channel_time("spo2"), data.get("signals", {}).get("spo2", []),
                self.channel_rate("spo2"),
            )
            if ARTIFACT_MIN_SECONDS > 0:
                summary = dict(summary)
                summary["excluded_segments"] = [
                    segment for segment in summary.get("excluded_segments", [])
                    if float(segment.get("duration_sec", 0.0)) > float(ARTIFACT_MIN_SECONDS)
                ]
            self._exclusion_cache = summary
        return self._exclusion_cache

    def _render_recording_exclusions(self, plot_widget):
        """Mark analysis exclusions behind the original displayed waveforms."""
        for item in getattr(plot_widget, "exclusion_items", []):
            plot_widget.removeItem(item)
        plot_widget.exclusion_items = []
        plot_widget.exclusion_labels = []
        offset = 0.0 if self.is_all_psg_mode() else float(self.current_time_offset)
        width = self.get_effective_time_window_seconds()
        for segment in self.get_recording_exclusions()["excluded_segments"]:
            start = max(0.0, segment["start_sec"] - offset)
            end = min(width, segment["end_sec"] - offset)
            if end <= start:
                continue
            region = pg.LinearRegionItem(
                values=(start, end), movable=False,
                brush=pg.mkBrush(239, 68, 68, 35),
                pen=pg.mkPen(239, 68, 68, 100, width=1),
            )
            region.setZValue(-5)
            region.setAcceptedMouseButtons(Qt.NoButton)
            region._playback_span = (
                float(segment["start_sec"]),
                float(segment["end_sec"]),
            )
            duration = segment["duration_sec"]
            label = pg.TextItem(f"Sensor off | {duration:g} sec", color="#b91c1c",
                                fill=pg.mkBrush(255, 241, 242, 240), anchor=(0.5, 0))
            label.setFont(QFont("Segoe UI", 8))
            label.setZValue(20)
            label.setAcceptedMouseButtons(Qt.NoButton)
            label._playback_abs_x = (
                float(segment["start_sec"]) + float(segment["end_sec"])
            ) / 2.0
            tooltip = (f"SpO2 sensor off | {segment['start_sec']:g}-{segment['end_sec']:g} sec\n"
                       "All channels excluded from analysis; raw data retained.")
            region.setToolTip(tooltip)
            label.setToolTip(tooltip)
            plot_widget.addItem(region, ignoreBounds=True)
            plot_widget.addItem(label, ignoreBounds=True)
            plot_widget.exclusion_items.extend((region, label))
            plot_widget.exclusion_labels.append((label, (start + end) / 2))
        if not getattr(plot_widget, "_exclusion_range_connected", False):
            plot_widget.getViewBox().sigRangeChanged.connect(
                lambda *_: self._position_exclusion_labels(plot_widget)
            )
            plot_widget._exclusion_range_connected = True
        self._position_exclusion_labels(plot_widget)

    @staticmethod
    def _position_exclusion_labels(plot_widget):
        low, high = plot_widget.getViewBox().viewRange()[1]
        for label, midpoint in getattr(plot_widget, "exclusion_labels", []):
            label.setPos(midpoint, high - (high - low) * 0.015)

    def _render_sensor_off_segments(self, plot_widget):
        """Grey out airflow stretches classified as sensor-off."""
        for item in getattr(plot_widget, "sensor_off_items", []):
            plot_widget.removeItem(item)
        plot_widget.sensor_off_items = []
        segments = getattr(self, "sensor_off_shade_segments", None) or []
        if not segments:
            return
        offset = 0.0 if self.is_all_psg_mode() else float(self.current_time_offset)
        width = self.get_effective_time_window_seconds()
        for segment in segments:
            try:
                seg_start = float(segment.get("start_sec", 0.0))
                seg_end = float(segment.get("end_sec", seg_start))
            except (TypeError, ValueError):
                continue
            start = max(0.0, seg_start - offset)
            end = min(width, seg_end - offset)
            if end <= start:
                continue
            region = pg.LinearRegionItem(
                values=(start, end), movable=False,
                brush=pg.mkBrush(107, 114, 128, 40),
                pen=pg.mkPen(107, 114, 128, 120, width=1),
            )
            region.setZValue(-6)
            region.setAcceptedMouseButtons(Qt.NoButton)
            region._playback_span = (seg_start, seg_end)
            duration = seg_end - seg_start
            region.setToolTip(
                f"Airflow sensor off / cannula out | {seg_start:g}-{seg_end:g} sec "
                f"({duration:.0f} sec)\n"
                f"{segment.get('reason', 'airflow dead while thorax effort continues')}"
            )
            plot_widget.addItem(region, ignoreBounds=True)
            plot_widget.sensor_off_items.append(region)

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
        position_font = QFont("Arial")
        position_font.setPointSize(9)
        position_font.setBold(True)
        left_axis.setTickFont(position_font)
        left_axis.setTextPen("#000000")
        left_axis.setPen("#000000")
        left_axis.setWidth(32)
        try:
            left_axis.setTicks([BODY_POSITION_TICKS])
        except Exception:
            pass
        # The categories sit at 0 (S) ... 4 (U). A view of exactly 0..4 put S on
        # the bottom frame line (its trace was half hidden) and cut the U label
        # in half at the top edge, so leave half a step of room on both sides.
        plot_widget.setYRange(BODY_POSITION_VIEW_MIN, BODY_POSITION_VIEW_MAX, padding=0)

    def _set_y_view(self, plot_widget, y_min, y_max):
        """Set an exact Y view without pyqtgraph's default padding."""
        try:
            plot_widget.setYRange(y_min, y_max, padding=0)
        except TypeError:
            plot_widget.setRange(yRange=[y_min, y_max], padding=0)

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
        step = float(np.nanmedian(x_diffs)) if len(x_diffs) > 0 else (1.0 / self.channel_rate("body_position"))
        if not np.isfinite(step) or step <= 0:
            step = 1.0 / self.channel_rate("body_position")

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
        Copy the raw recording and save it.
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

        if not getattr(self, "loaded_recording_path", None):
            QMessageBox.warning(
                self,
                "No Recording Loaded",
                "Please upload an SD-card binary recording before saving raw data.",
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

            if not getattr(self, "loaded_recording_path", None):
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
        SQLite me patient/time save hota hai aur uploaded raw recording copy hoti hai.
        """
        self._save_in_progress = True

        self._worker = self._SaveWorker(
            self.patient_id,
            self.loaded_recording_path,
            parent_session_id=self.current_session_root_id,
            parent=self,
        )
        self._worker.done.connect(self._on_save_done)
        self._worker.failed.connect(self._on_save_failed)
        self._worker.start()

    def _on_save_done(self, session_id: int, saved_at: str, copied_recording_path: str):
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
        self._archive_manual_label_overrides_snapshot(copied_recording_path)

        # Reload the original sidecar from disk and re-apply the current
        # overlays. This keeps the original recording's persisted manual
        # state intact instead of replacing it with an empty in-memory
        # version that could later be written back to disk.
        self._load_manual_label_overrides()
        self._refresh_auto_rule_ai_views()
        label = f"Session #{session_id} - {self.patient_id}"
        self.raw_data_saved.emit(copied_recording_path, saved_at)
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
            f'<span style="color:#111827; font-weight:700;">Recording copy</span>'
            f'<span style="color:#6b7280;"> : {copied_recording_path}</span>'
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

    def _archive_manual_label_overrides_snapshot(self, copied_recording_path: str) -> None:
        """Copy current manual-label overrides next to an archived recording.

        Manual events live in an opaque, signed sidecar in the per-user
        application-data directory (see _manual_label_overrides_path()).
        A Re-analyze -> "New report" save archives a recording copy under
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
            dest_overrides_path = _sidecar_path_for(copied_recording_path)
            payload = {
                "label_overrides": self.manual_label_overrides,
                "manual_selections": manual_selections,
                "deleted_auto_events": deleted_auto_events,
            }
            _write_signed_json(dest_overrides_path, payload)
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
            pass
            self.set_time_window(seconds)

    # Per-channel sample rates and native time axes.
    def channel_rate(self, channel_name):
        """Return a loaded channel's native sample rate."""
        rates = (self.psg_full_data or {}).get("sample_rates") or {}
        key = signal_key_for_chart(channel_name)
        return channel_sample_rate(
            key,
            rates,
            default=CHANNEL_SAMPLE_RATES.get(key, EXTERNAL_ARRAY_SAMPLE_RATE_HZ),
        )

    def channel_time(self, channel_name):
        """Return the elapsed-seconds axis for a loaded channel."""
        data = self.psg_full_data or {}
        times = data.get("times") or {}
        key = signal_key_for_chart(channel_name)
        if key in times:
            return np.asarray(times[key], dtype=float)
        return np.asarray(data.get("time", []), dtype=float)

    def master_rate(self):
        data = self.psg_full_data or {}
        return self.channel_rate(data.get("master_channel", "airflow"))

    # Channels slower than this are drawn sample-and-hold (see _hold_for_display).
    DISPLAY_HOLD_BELOW_HZ = 5.0
    # Seconds over which a slow-channel step is drawn as a slope (0 = sharp step).
    SLOW_CHANNEL_DISPLAY_RAMP_SEC = 1.0

    def _hold_for_display(self, window_time, window_signal, source_rate_hz,
                          target_rate_hz=EXTERNAL_ARRAY_SAMPLE_RATE_HZ):
        """Resample slow channels smoothly for plotting only.

        SD SpO2/Pulse readings arrive at 1 Hz.  The raw values remain
        unchanged, but connecting them directly as steps makes every change
        look like a sudden jump.  Interpolate only between adjacent finite
        readings on a display grid; invalid gaps are kept as gaps.
        """
        window_time = np.asarray(window_time, dtype=float).reshape(-1)
        window_signal = np.asarray(window_signal, dtype=float).reshape(-1)
        count = min(window_time.size, window_signal.size)
        if count == 0 or not source_rate_hz or source_rate_hz >= self.DISPLAY_HOLD_BELOW_HZ:
            return window_time[:count], window_signal[:count]
        source_time = window_time[:count]
        source_signal = window_signal[:count]
        finite_time = np.isfinite(source_time)
        if not finite_time.any():
            return source_time, source_signal

        finite_source_time = source_time[finite_time]
        if finite_source_time.size > 1:
            source_step = float(np.nanmedian(np.diff(finite_source_time)))
        else:
            source_step = 1.0 / float(source_rate_hz)
        if not np.isfinite(source_step) or source_step <= 0.0:
            source_step = 1.0 / float(source_rate_hz)

        sub_step = 1.0 / float(target_rate_hz)
        start = float(source_time[0])
        end = float(source_time[-1]) + source_step
        display_time = np.arange(start, end + sub_step * 0.5, sub_step)
        display_signal = np.full(display_time.shape, np.nan, dtype=float)

        finite_signal = np.isfinite(source_signal) & finite_time
        valid_indices = np.flatnonzero(finite_signal)
        if valid_indices.size == 0:
            return display_time, display_signal

        # Interpolate each contiguous finite segment independently. This
        # prevents a sensor-off gap from becoming a fake diagonal reading.
        splits = np.where(np.diff(valid_indices) > 1)[0] + 1
        for segment in np.split(valid_indices, splits):
            if segment.size == 0:
                continue
            segment_time = source_time[segment]
            segment_signal = source_signal[segment]
            segment_end = float(segment_time[-1]) + source_step
            in_segment = (
                (display_time >= float(segment_time[0]))
                & (display_time <= segment_end + sub_step * 0.5)
            )
            interp_time = np.concatenate([segment_time, [segment_end]])
            interp_signal = np.concatenate([segment_signal, [segment_signal[-1]]])
            display_signal[in_segment] = np.interp(
                display_time[in_segment], interp_time, interp_signal
            )

        return display_time, display_signal

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
        """Return cached playback duration in seconds for the loaded dataset."""
        sample_count = self._get_playback_sample_count()
        if sample_count <= 0:
            return 0.0
        time_ref = (self.psg_full_data or {}).get("time")
        rate = float(self.master_rate())
        cached = self.__dict__.get("_playback_duration_cache")
        if (
            cached is not None
            and cached[0] is time_ref
            and cached[1] == sample_count
            and cached[2] == rate
        ):
            return cached[3]
        value = None
        time_values = np.asarray([] if time_ref is None else time_ref, dtype=float)
        if time_values.size:
            finite = np.flatnonzero(np.isfinite(time_values))
            if finite.size:
                value = float(time_values[finite[-1]] - time_values[finite[0]]) + 1.0 / rate
        if value is None:
            value = sample_count / rate
        self._playback_duration_cache = (time_ref, sample_count, rate, value)
        return value

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
            pass
    
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
            pass
    
    def _set_playback_antialias(self, enabled):
        """Turn curve antialiasing on/off for every chart (display only)."""
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            plot_widget = getattr(container, "plot_widget", None)
            curve = getattr(plot_widget, "plot_curve", None)
            opts = getattr(curve, "opts", None)
            if isinstance(opts, dict):
                opts["antialias"] = bool(enabled)

    def _find_vsync_widget(self):
        if not PLAYBACK_USE_OPENGL:
            return None
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            plot_widget = getattr(container, "plot_widget", None)
            if plot_widget is None:
                continue
            try:
                vp = plot_widget.viewport()
            except Exception:
                continue
            if isinstance(vp, QOpenGLWidget) and vp.isVisible():
                return vp
        return None

    def _start_playback_pacer(self):
        self.playback_timer.stop()
        self._playback_vsync_widget = None
        self._playback_tick_pending = False

        if PLAYBACK_USE_DWM_VSYNC:
            worker = _DwmVsyncThread(parent=self)
            worker.frame_ready.connect(self._on_dwm_frame)
            worker.failed.connect(
                lambda message, active=worker: self._on_dwm_failed(active, message)
            )
            worker.finished.connect(worker.deleteLater)
            self._dwm_worker = worker
            worker.start()
            if PERF_SUMMARY:
                pass
            return

        vp = self._find_vsync_widget()
        if vp is not None:
            try:
                vp.frameSwapped.connect(self._on_frame_swapped)
                self._playback_vsync_widget = vp
                QTimer.singleShot(0, self.update_playback)
                if PERF_SUMMARY:
                    pass
                return
            except Exception:
                self._playback_vsync_widget = None
        self._start_qtimer_pacer()

    def _perf_paint_breakdown(self):
        """F8 while profiling: how long one full paint of the charts takes, and how
        much of it disappears without antialiasing / overlay boxes / digit labels /
        curves. One-off (stalls the UI for about a second); shown in the HUD for 25 s."""
        try:
            plots = []
            for i in range(self.charts_layout.count()):
                container = self.charts_layout.itemAt(i).widget()
                plot_widget = getattr(container, "plot_widget", None)
                if plot_widget is not None:
                    plots.append(plot_widget)
            target = getattr(self, "charts_widget", None) or self

            def grab_ms(widget, repeats=3):
                times = []
                for _ in range(repeats):
                    t0 = time.perf_counter()
                    widget.grab()
                    times.append((time.perf_counter() - t0) * 1000.0)
                return float(np.median(times))

            def with_hidden(items):
                saved = []
                for item in items:
                    try:
                        saved.append((item, item.isVisible()))
                        item.setVisible(False)
                    except Exception:
                        pass
                try:
                    return grab_ms(target)
                finally:
                    for item, was_visible in saved:
                        try:
                            item.setVisible(was_visible)
                        except Exception:
                            pass

            total = grab_ms(target)
            per_chart = " ".join(
                f"{str(getattr(pw, 'chart_name', '?')).strip()[:7]}={grab_ms(pw):.0f}"
                for pw in plots
            )
            self._set_playback_antialias(False)
            try:
                no_aa = grab_ms(target)
            finally:
                self._set_playback_antialias(True)
            overlays = [o for pw in plots for o in (getattr(pw, "selection_overlays", None) or ())]
            digits = [
                t
                for pw in plots
                for attr in ("value_labels", "pulse_value_labels")
                for t in (getattr(pw, attr, None) or ())
            ]
            no_overlays = with_hidden(overlays)
            no_digits = with_hidden(digits)
            no_curves = with_hidden(list(self._iter_chart_curves()))
            text = (
                f"PAINT (one full render, ms): total={total:.0f} | no-AA={no_aa:.0f} "
                f"no-boxes={no_overlays:.0f} no-digits={no_digits:.0f} no-curves={no_curves:.0f}"
                f"\nper chart: {per_chart}  (boxes={len(overlays)} digits={len(digits)})"
            )
            pass
            self._perf_note = (text, time.monotonic() + 25.0)
            _PERF._show_hud(self, _PERF._last_line)
        except Exception:
            pass

    # ---- Playback strip (opt-in: PSG_STRIP=1) -------------------------------------------------
    def _strip_panels(self):
        """[(plot_widget, geometry)] for every chart; geometry() = (x_origin, width, y, height) of the ViewBox
        pixels that show the [0, window] range, in the plot widget's own coordinates."""
        window = float(self.get_effective_time_window_seconds())
        panels = []
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            pw = getattr(container, "plot_widget", None)
            if pw is None or not pw.isVisible():
                continue

            def geom(pw=pw):
                if not pw.isVisible():
                    return (0, 0.0, 0, 0)
                vb = pw.getViewBox()
                vp = pw.viewport()
                s0 = vb.mapViewToScene(QPointF(0.0, 0.0)).x()
                s1 = vb.mapViewToScene(QPointF(window, 0.0)).x()
                box = vb.sceneBoundingRect()
                origin = vp.mapTo(pw, pw.mapFromScene(QPointF(s0, box.top())))
                return (origin.x(), s1 - s0, origin.y(), int(round(box.height())))

            panels.append((pw, geom))
        return panels

    def _strip_hold_y_ranges(self):
        """Strip pages are fitted one by one, but two neighbouring pages drawn with different Y ranges make the curve
        jump at their join (a visible cut). Keep the previous page's range unless the new fit is clearly different:
        the data would not fit into the held range, or the trace would be drawn much smaller than it could be."""
        held = self.__dict__.setdefault("_strip_y_held", {})
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            plot_widget = getattr(container, "plot_widget", None)
            if plot_widget is None or not plot_widget.isVisible():
                continue
            try:
                view_box = plot_widget.getViewBox()
                low, high = (float(value) for value in view_box.viewRange()[1])
                key = plot_widget.chart_name
                previous = held.get(key)
                if previous is not None:
                    held_low, held_high = previous
                    span = held_high - held_low
                    # Waveform tiles must all use one identical transform. Letting a
                    # later page choose a "better" fit changes the Y coordinate of
                    # the same sample on the two sides of a tile boundary, which is
                    # seen as a broken peak while playing.  The range remembered at
                    # Play start is exactly the range visible in the paused chart.
                    if str(key).strip() in ("Airflow", "Thorax", "Snoring") and span > 0:
                        view_box.setYRange(held_low, held_high, padding=0)
                        continue
                    contained = low >= held_low - 0.05 * span and high <= held_high + 0.05 * span
                    similar = (high - low) >= 0.7 * span
                    if span > 0 and contained and similar:
                        view_box.setYRange(held_low, held_high, padding=0)
                        continue
                if previous is not None and PERF_SUMMARY:
                    pass
                held[key] = (low, high)
            except Exception:
                pass

    def _strip_drive(self, offset):
        """Make the live charts show a strip page using the same fitted Y scale as the paused/live view."""
        self.current_time_offset = float(offset)
        self._last_playback_decoration_update = 0.0      # draw digits / boxes for this page
        self._strip_force_axis_fit = True
        try:
            self.refresh_charts()
        finally:
            self._strip_force_axis_fit = False
        self._strip_hold_y_ranges()

    def _log_strip_session(self, strip):
        """One log line per Play: where the start-up time went (see _psg_playback_log)."""
        def average(values):
            return sum(values) / len(values) if values else 0.0
        startup = strip.buffer_ms[0] if strip.buffer_ms else -1.0
        _psg_playback_log(
            "strip session: start-up buffering %.0f ms (first pages: drive %.0f ms + tile grabs %.0f ms each), "
            "rebuffers=%d (%.0f ms), seeks=%d"
            % (startup, average(strip.drive_ms[:3]), average(strip.grab_ms[:3]),
               strip.rebuffers, strip.rebuffer_ms, strip.seeks)
        )

    def _strip_cache_watch(self, on):
        """Install / remove the application-wide watcher that notices clicks, keys and wheel turns."""
        app = QApplication.instance()
        if app is None:
            return
        guard = self.__dict__.get("_strip_reuse_guard")
        if on:
            if guard is None:
                guard = _StripReuseGuard(self)
                self._strip_reuse_guard = guard
                for signal in (self.apnea_events_updated, self.detection_busy_changed, self.time_window_mode_changed):
                    try:
                        signal.connect(self._strip_cache_mark_dirty)
                    except Exception:
                        pass
            app.installEventFilter(guard)
        elif guard is not None:
            app.removeEventFilter(guard)

    def _strip_cache_mark_dirty(self, *_args):
        self._strip_cache_dirty = True

    def _strip_reuse_source_ok(self, obj):
        """True when an input event came from the Play button or the speed buttons (they cannot change the charts)."""
        allowed = [w for w in (self.__dict__.get("play_pause_btn"), self.__dict__.get("slider_speed")) if w is not None]
        node, depth = obj, 0
        while node is not None and depth < 10:
            if any(node is widget for widget in allowed):
                return True
            node = node.parent() if hasattr(node, "parent") else None
            depth += 1
        return False

    def _strip_held_signature(self):
        held = self.__dict__.get("_strip_y_held") or {}
        return {str(key).strip(): (float(value[0]), float(value[1])) for key, value in held.items() if value is not None}

    def _strip_cache_clear(self):
        self._strip_cache = None
        self._strip_cache_watch(False)

    def _strip_cache_store(self, strip):
        """Remember the tiles of a strip that is being released because of a Pause."""
        if not PLAYBACK_STRIP_REUSE or not hasattr(strip, "export_tiles"):
            return
        exported = strip.export_tiles()
        if not exported["tiles"]:
            return
        self._strip_cache = {
            "export": exported,
            "ranges": self._strip_held_signature(),
            "names": [str(getattr(widget, "chart_name", "")).strip() for widget, _geom in strip.panels],
            "data": id(self.psg_full_data),
            "time": time.monotonic(),
        }
        self._strip_cache_dirty = False
        self._strip_cache_watch(True)

    def _strip_try_reuse(self, strip):
        """Right after strip.start(): take over the tiles of the previous Pause if nothing could have changed.

        Layers, each of which makes the next Play build everything again when it fails: no click / key / event
        signal since the Pause, same recording, same charts, same Y ranges, same window and layout, and finally the
        picture the tiles would show must match the live snapshot of what is on screen now.
        Returns a short text for the log.
        """
        cache = self.__dict__.get("_strip_cache")
        self._strip_cache = None
        self._strip_cache_watch(False)
        if not PLAYBACK_STRIP_REUSE:
            return "reuse off"
        if cache is None:
            return "no kept tiles"
        try:
            if self.__dict__.get("_strip_cache_dirty", False):
                return "not reused: something was clicked / changed since the Pause"
            if time.monotonic() - cache["time"] > STRIP_REUSE_MAX_AGE_SEC:
                return "not reused: paused too long"
            if cache["data"] != id(self.psg_full_data):
                return "not reused: another recording"
            names = [str(getattr(widget, "chart_name", "")).strip() for widget, _geom in strip.panels]
            if names != cache["names"]:
                return "not reused: charts changed"
            now, before = self._strip_held_signature(), cache["ranges"]
            if set(now) != set(before) or any(
                abs(now[key][0] - before[key][0]) > 1e-6 * (abs(before[key][0]) + 1.0)
                or abs(now[key][1] - before[key][1]) > 1e-6 * (abs(before[key][1]) + 1.0)
                for key in now
            ):
                return "not reused: Y ranges differ"
            taken = strip.adopt(cache["export"])
            if not taken:
                return "not reused: window / layout differ"
            ok, miss_global, miss_local = strip.verify_reuse()
            if ok:
                return "REUSED %d kept tile pages (picture check %.3f / %.3f)" % (taken, miss_global, miss_local)
            return "not reused: kept tiles do not match the screen (%.3f / %.3f)" % (miss_global, miss_local)
        except Exception as error:
            try:
                strip.tiles.clear()
                strip.tile_left_margin.clear()
            except Exception:
                pass
            return "not reused: %r" % (error,)

    def _strip_release(self, keep_tiles=False):
        strip = self.__dict__.get("_strip")
        self._strip = None
        self._strip_pending_release = False
        if strip is not None:
            try:
                self._log_strip_session(strip)
            except Exception:
                pass
            if keep_tiles:
                try:
                    self._strip_cache_store(strip)
                except Exception:
                    self._strip_cache_clear()
            else:
                self._strip_cache_clear()
            try:
                strip.release()
            except Exception:
                pass

    def _strip_begin(self):
        """Called from start_playback. The live charts are showing the paused view at current_time_offset."""
        if self.__dict__.get("_strip_pending_release"):
            # Paused and resumed within one event-loop turn: make the live charts exact before covering them again.
            self._strip_release(keep_tiles=True)
            was_playing = self.is_playing
            self.is_playing = False
            try:
                self.refresh_charts()
            finally:
                self.is_playing = was_playing
        self._strip_release()
        if not PLAYBACK_STRIP_MODE or LiveCaptureStrip is None or self.is_all_psg_mode():
            _psg_playback_log(
                "strip OFF at play start: PLAYBACK_STRIP_MODE=%s LiveCaptureStrip_imported=%s "
                "all_psg_mode=%s legacy_display=%s physical_width=%s"
                % (PLAYBACK_STRIP_MODE, LiveCaptureStrip is not None, self.is_all_psg_mode(),
                   _is_legacy_display(), _physical_screen_width())
            )
            return
        try:
            # A page refresh can change an AxisItem's preferred width (for
            # example when Airflow ticks settle from the startup range).  That
            # changes the ViewBox width by a few pixels.  Building the strip
            # before this layout pass makes its seconds-per-pixel differ from
            # every subsequently captured page, so the same sample lands 1-2
            # pixels apart at tile joins.  Settle the exact playback ranges and
            # pending layout requests first, then measure the panels once.
            _t_begin = time.perf_counter()
            self._strip_y_held = {}
            self._strip_hold_y_ranges()
            self._strip_force_axis_fit = True
            try:
                self.refresh_charts()
            finally:
                self._strip_force_axis_fit = False
            QApplication.sendPostedEvents()
            QApplication.processEvents()
            _t_refresh = (time.perf_counter() - _t_begin) * 1000.0
            panels = self._strip_panels()
            if not panels:
                return
            strip = LiveCaptureStrip(
                panels,
                self._strip_drive,
                float(self.get_effective_time_window_seconds()),
                max_offset=float(self._get_playback_max_offset()),
                budget_ms=7.0,
                # Integer tile motion avoids the half-pixel sampling seam that
                # SmoothPixmapTransform can introduce between two transparent
                # pixmaps.  Source margins still preserve the full curve at joins.
                smooth=False,
            )
            strip.clock.speed = float(self.playback_speed)
            strip.start(float(self.current_time_offset))
            _reuse_note = self._strip_try_reuse(strip)
            _t_total = (time.perf_counter() - _t_begin) * 1000.0
            self._strip = strip
            self._strip_last_pos = float(self.current_time_offset)
            _psg_playback_log(
                "strip ON (window=%ss speed=%sx): before the first page %.0f ms "
                "(forced refresh %.0f ms, strip.start + tiles %.0f ms); %s"
                % (strip.window_s, self.playback_speed, _t_total, _t_refresh, _t_total - _t_refresh, _reuse_note)
            )
        except Exception:
            import traceback
            _psg_playback_log("strip could not start -> translate fallback:\n" + traceback.format_exc())
            self._strip_release()

    def _strip_fallback(self, error=None):
        """Anything unexpected: drop the strip and carry on with the normal live playback path."""
        _psg_playback_log("strip dropped during playback: %r" % (error,))
        strip = self.__dict__.get("_strip")
        pos = float(self.current_time_offset)
        if strip is not None:
            try:
                pos = float(strip.position())
            except Exception:
                pass
        self._strip_release()
        try:
            self.current_time_offset = pos
            self._reset_playback_transforms()
            self.refresh_charts()
            self._capture_playback_anchor()
            self._last_playback_data_refresh = time.perf_counter()
            self._reset_playback_pacing()
            self._playback_clock.start()
        except Exception:
            pass

    def _strip_restart(self, reason):
        """Window size or chart layout changed while playing: rebuild the strip for the new geometry and keep playing
        (instead of dropping to the slow normal path). Gives up after 3 restarts within 5 s."""
        now = time.perf_counter()
        recent = [t for t in self.__dict__.get("_strip_restarts", []) if now - t < 5.0]
        if len(recent) >= 3:
            self._strip_fallback(f"{reason} (kept changing)")
            return False
        recent.append(now)
        self._strip_restarts = recent
        strip = self.__dict__.get("_strip")
        pos = float(self.current_time_offset)
        if strip is not None and abs(pos - self._strip_last_pos) <= 1e-6:
            try:
                pos = float(strip.position())                  # layout-only change: continue where the strip was
            except Exception:
                pass
        # (after a window change set_time_window already moved current_time_offset: continue from there)
        pass
        self._strip_release()
        try:
            self.current_time_offset = pos
            self._reset_playback_transforms()
            self.refresh_charts()                              # live charts show exactly `pos` in the new layout
            self._strip_begin()
        except Exception as error:
            self._strip_fallback(error)
            return False
        if self.__dict__.get("_strip") is None:
            self._strip_fallback(f"{reason} (strip could not restart)")
            return False
        return True

    def _strip_tick(self, max_offset):
        """One playback frame in strip mode. Returns False if the strip was dropped (caller continues normally)."""
        strip = self._strip
        try:
            if abs(float(self.current_time_offset) - self._strip_last_pos) > 1e-6:
                strip.seek(float(self.current_time_offset))      # event click / arrows redrew the live charts elsewhere
            if abs(strip.clock.speed - float(self.playback_speed)) > 1e-9:
                strip.clock.set_speed(float(self.playback_speed))
            if abs(float(self.get_effective_time_window_seconds()) - strip.window_s) > 1e-6:
                raise RuntimeError("time window changed")
            if strip.geometry_changed():
                raise RuntimeError("chart layout changed")
            pos = strip.tick()
        except Exception as error:
            if str(error) in ("time window changed", "chart layout changed") and self._strip_restart(error):
                return True
            self._strip_fallback(error)
            return False
        self.current_time_offset = pos
        self._strip_last_pos = pos
        if pos >= max_offset - 1e-6:
            self.pause_playback()
            return True
        self.update_time_position_label(throttle=True)
        return True

    def _start_qtimer_pacer(self, reason=None):
        self.playback_timer.start(int(PLAYBACK_FRAME_INTERVAL_MS))
        if PERF_SUMMARY:
            suffix = f" (DWM fallback: {reason})" if reason else ""
            pass

    def _on_dwm_frame(self):
        worker = self.__dict__.get("_dwm_worker")
        if worker is None:
            return
        try:
            if self.is_playing:
                self.update_playback()
        finally:
            try:
                worker.acknowledge_tick()
            except RuntimeError:
                pass

    def _on_dwm_failed(self, worker, message):
        if worker is not self.__dict__.get("_dwm_worker"):
            return
        self._dwm_worker = None
        worker.requestInterruption()
        if self.is_playing:
            self._start_qtimer_pacer(reason=message)

    def _stop_playback_pacer(self):
        self.playback_timer.stop()
        worker = self.__dict__.get("_dwm_worker")
        self._dwm_worker = None
        if worker is not None:
            try:
                worker.requestInterruption()
                # DwmFlush normally returns at the next refresh boundary.
                # Do not leave a live QThread parented to a closing widget.
                worker.wait(250)
            except RuntimeError:
                pass
        vp = self.__dict__.get("_playback_vsync_widget")
        if vp is not None:
            try:
                vp.frameSwapped.disconnect(self._on_frame_swapped)
            except Exception:
                pass
        self._playback_vsync_widget = None
        self._playback_tick_pending = False

    def _on_frame_swapped(self):
        if not self.is_playing or self.__dict__.get("_playback_tick_pending"):
            return
        self._playback_tick_pending = True
        QTimer.singleShot(0, self._vsync_tick)

    def _vsync_tick(self):
        self._playback_tick_pending = False
        if not self.is_playing:
            return
        self.update_playback()
        vp = self.__dict__.get("_playback_vsync_widget")
        if vp is not None:
            vp.update()

    def _reset_playback_pacing(self):
        self._pace_dt = None
        self._pace_target = None
        self._pace_shown = None

    def _reset_playback_transforms(self):
        """Remove the cheap between-refresh translation from plotted curves."""
        for curve in self._iter_chart_curves():
            try:
                curve.setPos(0.0, 0.0)
            except Exception:
                pass

    def _get_adaptive_refresh_interval(self):
        """How often to fully rebuild the charts from source during playback.

        Normally PLAYBACK_DATA_REFRESH_SEC. If a rebuild is measured (see
        _record_refresh_cost) to cost more than PLAYBACK_REFRESH_COST_BUDGET of
        that interval - the translate-fallback path on an old machine, since a
        capable machine stays on the smooth strip and rarely reaches this code
        at all - the interval is stretched (up to PLAYBACK_REFRESH_MAX_SEC) so
        the expensive rebuild happens less often. refresh_charts() sizes its
        off-screen tail from this same value, so the cheap translated frames
        always have enough pre-rendered data to scroll into view and the right
        edge never goes blank while it waits for the next rebuild.
        """
        base = float(PLAYBACK_DATA_REFRESH_SEC)
        if not PLAYBACK_REFRESH_ADAPTIVE:
            return base
        cost = self.__dict__.get("_refresh_cost_ema_sec")
        if cost is None:
            return base
        budget = base * float(PLAYBACK_REFRESH_COST_BUDGET)
        if cost <= budget:
            return base
        stretched = cost / float(PLAYBACK_REFRESH_COST_BUDGET)
        return max(float(PLAYBACK_REFRESH_MIN_SEC), min(float(PLAYBACK_REFRESH_MAX_SEC), stretched))

    def _record_refresh_cost(self, cost_sec):
        """Smoothed (EMA) cost of a full chart rebuild, used by
        _get_adaptive_refresh_interval(). A couple of slow rebuilds move the
        average; one slow outlier (a GC pause, a background task) does not."""
        if not PLAYBACK_REFRESH_ADAPTIVE:
            return
        prev = self.__dict__.get("_refresh_cost_ema_sec")
        self._refresh_cost_ema_sec = (
            float(cost_sec) if prev is None
            else prev + (float(cost_sec) - prev) * float(PLAYBACK_REFRESH_COST_SMOOTHING)
        )

    def _capture_playback_anchor(self):
        """Remember item positions produced by the latest full data refresh."""
        self._playback_data_anchor_offset = float(self.current_time_offset)
        self._last_playback_data_refresh = time.perf_counter()
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            plot_widget = getattr(container, "plot_widget", None)
            if plot_widget is None:
                continue
            for attr in ("value_labels", "pulse_value_labels"):
                for label in getattr(plot_widget, attr, ()) or ():
                    try:
                        label._playback_anchor_pos = QPointF(label.pos())
                    except Exception:
                        pass

    def _translate_playback_items(self):
        """Move existing paths/labels for a smooth frame without rebuilding."""
        anchor = self.__dict__.get("_playback_data_anchor_offset")
        if anchor is None:
            self._capture_playback_anchor()
            return
        delta = max(0.0, float(self.current_time_offset) - float(anchor))
        for curve in self._iter_chart_curves():
            try:
                curve.setPos(-delta, 0.0)
            except Exception:
                pass
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            plot_widget = getattr(container, "plot_widget", None)
            if plot_widget is None:
                continue
            for attr in ("value_labels", "pulse_value_labels"):
                for label in getattr(plot_widget, attr, ()) or ():
                    try:
                        base = getattr(label, "_playback_anchor_pos", None)
                        if base is not None:
                            label.setPos(base.x() - delta, base.y())
                    except Exception:
                        pass

            # These background regions are independent GraphicsItems. Moving
            # only plot_curve made them freeze for a second and then snap on
            # the next full refresh. Keep every timed region on the same clock.
            for attr in ("exclusion_items", "sensor_off_items"):
                for item in getattr(plot_widget, attr, ()) or ():
                    try:
                        span = getattr(item, "_playback_span", None)
                        if span is not None and hasattr(item, "setRegion"):
                            item.setRegion(
                                [
                                    float(span[0]) - self.current_time_offset,
                                    float(span[1]) - self.current_time_offset,
                                ]
                            )
                        abs_x = getattr(item, "_playback_abs_x", None)
                        if abs_x is not None and hasattr(item, "pos"):
                            pos = item.pos()
                            item.setPos(float(abs_x) - self.current_time_offset, pos.y())
                    except Exception:
                        pass

        for item, _plot_widget in getattr(self, "airflow_event_items", ()) or ():
            try:
                span = getattr(item, "_playback_span", None)
                if span is not None and hasattr(item, "setRegion"):
                    item.setRegion(
                        [
                            float(span[0]) - self.current_time_offset,
                            float(span[1]) - self.current_time_offset,
                        ]
                    )
            except Exception:
                pass

        # Event / DE-SATURATION boxes: re-place every frame so they glide with the curve
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            plot_widget = getattr(container, "plot_widget", None)
            if plot_widget is None:
                continue
            vb = plot_widget.getViewBox()
            for overlay in getattr(plot_widget, "selection_overlays", ()) or ():
                try:
                    span = getattr(overlay, "_playback_span", None)
                    if span is None or sip.isdeleted(overlay) or not overlay.isVisible():
                        continue
                    x0 = plot_widget.mapFromScene(
                        vb.mapViewToScene(QPointF(span[0] - self.current_time_offset, 0))
                    ).x()
                    x1 = plot_widget.mapFromScene(
                        vb.mapViewToScene(QPointF(span[1] - self.current_time_offset, 0))
                    ).x()
                    self._place_overlay_in_plot_area(plot_widget, overlay, x0, x1)
                except Exception:
                    pass

    def _next_playback_offset(self, elapsed_sec):
        rate = float(PLAYBACK_TIME_SCALE) * float(self.playback_speed)
        current = float(self.current_time_offset)
        shown = getattr(self, "_pace_shown", None)
        if shown is None or abs(current - shown) > 1e-6:
            self._pace_target = current
            self._pace_dt = None

        self._pace_target = float(self._pace_target) + elapsed_sec * rate

        alpha = float(PLAYBACK_DT_SMOOTHING)
        steady = (
            self._pace_dt is not None
            and elapsed_sec <= float(PLAYBACK_SMOOTHING_MAX_FRAME_SEC)
            and abs(elapsed_sec - self._pace_dt) <= 0.5 * self._pace_dt
        )
        if self._pace_dt is None or alpha <= 0.0 or not steady:
            self._pace_dt = elapsed_sec
        else:
            self._pace_dt += alpha * (elapsed_sec - self._pace_dt)

        new_offset = current + self._pace_dt * rate
        error = self._pace_target - new_offset
        if abs(error) > float(PLAYBACK_RESYNC_SEC) * max(rate, 1e-6):
            new_offset = self._pace_target
        else:
            new_offset += error * float(PLAYBACK_DRIFT_CORRECTION)
        new_offset = max(new_offset, current)
        self._pace_shown = new_offset
        return new_offset

    def _iter_chart_curves(self):
        for i in range(self.charts_layout.count()):
            container = self.charts_layout.itemAt(i).widget()
            plot_widget = getattr(container, "plot_widget", None)
            if plot_widget is None:
                continue
            curve = getattr(plot_widget, "plot_curve", None)
            if curve is not None:
                yield curve
            for extra in (getattr(plot_widget, "snore_phase_curves", None) or {}).values():
                yield extra

    def _set_playback_thin_lines(self, enabled):
        saved = self.__dict__.setdefault("_playback_saved_pens", {})
        if enabled:
            for curve in self._iter_chart_curves():
                try:
                    if id(curve) in saved:
                        continue
                    pen = curve.opts.get("pen")
                    if pen is None:
                        continue
                    original = QPen(pg.mkPen(pen))
                    if original.widthF() <= float(PLAYBACK_LINE_WIDTH):
                        continue
                    thin = QPen(original)
                    thin.setWidthF(float(PLAYBACK_LINE_WIDTH))
                    saved[id(curve)] = (curve, original)
                    curve.setPen(thin)
                except Exception:
                    pass
        else:
            for curve, original in list(saved.values()):
                try:
                    curve.setPen(original)
                except Exception:
                    pass
            saved.clear()

    def _set_playback_segmented_lines(self, enabled):
        saved = self.__dict__.setdefault("_playback_saved_line_modes", {})
        if enabled:
            for curve in self._iter_chart_curves():
                try:
                    inner = getattr(curve, "curve", None)
                    if inner is None or "segmentedLineMode" not in inner.opts:
                        continue
                    if curve.opts.get("stepMode") or id(inner) in saved:
                        continue
                    saved[id(inner)] = (inner, inner.opts["segmentedLineMode"])
                    inner.opts["segmentedLineMode"] = "on"
                except Exception:
                    pass
        else:
            for inner, previous in list(saved.values()):
                try:
                    inner.opts["segmentedLineMode"] = previous
                    inner.update()
                except Exception:
                    pass
            saved.clear()

    @staticmethod
    def _x_range_is_current(plot_widget, vb, window_seconds):
        try:
            tol = max(1e-6, float(window_seconds) * 1e-6)
            low, high = vb.viewRange()[0]
            axis_range = getattr(plot_widget.getAxis("bottom"), "range", None)
            return bool(
                abs(low) <= tol
                and abs(high - window_seconds) <= tol
                and axis_range is not None
                and abs(axis_range[0]) <= tol
                and abs(axis_range[1] - window_seconds) <= tol
            )
        except Exception:
            return False

    def start_playback(self):
        """Start movie-like playback of recorded data"""
        sample_count = self._get_playback_sample_count()

        if self.is_detection_running():
            QMessageBox.information(
                self,
                "Detection in progress",
                "Please wait for event detection to finish before starting playback.",
            )
            return
        pass
        
        if self.block_if_selection_active():
            pass
            return
        
        if sample_count == 0:
            pass
            return

        self.current_time_offset = min(self.current_time_offset, self._get_playback_max_offset())
        
        self.is_playing = True
        self._playback_busy = False
        # Show the new state at once.  Starting the strip below needs ~0.5 s (a full refresh plus
        # three pre-rendered pages); the button used to change only after all of that, so Play
        # looked ignored while Pause (which only stops a clock) reacted instantly.
        if self.play_pause_btn:
            self.play_pause_btn.setText("⏸ Pause")
            self.play_pause_btn.repaint()
        if PLAYBACK_DISABLE_ANTIALIAS:
            self._set_playback_antialias(False)
        if PLAYBACK_THIN_LINES:
            self._set_playback_thin_lines(True)
        elif PLAYBACK_SEGMENTED_LINES:
            self._set_playback_segmented_lines(True)
        self._reset_playback_pacing()
        self._last_playback_decoration_update = 0.0
        self._reset_playback_transforms()
        self._capture_playback_anchor()
        # The first timer tick primes the off-screen right-hand data tail.
        self._last_playback_data_refresh = 0.0
        self._playback_clock.start()
        self._pause_hold = None
        self._strip_begin()
        pass
        self._start_playback_pacer()
        pass
        pass
        
        # Update button if it exists
        if self.play_pause_btn:
            self.play_pause_btn.setText("⏸ Pause")
    
    def pause_playback(self):
        """Pause the playback"""
        was_playing = self.is_playing
        self.is_playing = False
        self._playback_busy = False
        self._playback_clock.invalidate()
        self._stop_playback_pacer()
        self._reset_playback_pacing()
        strip = self.__dict__.get("_strip")
        if strip is not None:
            try:
                self.current_time_offset = float(strip.stop())
            except Exception:
                pass
            try:
                self._remember_play_scale_for_pause()
            except Exception:
                pass
            if getattr(self, "_slider_scrubbing", False):
                try:
                    self.refresh_charts()                 # bring the live charts to the paused position, then uncover them
                except Exception:
                    pass
                self._strip_release()
            else:
                self._strip_pending_release = True        # released by _refresh_after_pause once the live charts are exact
        # Pause button while playing: do NOT drag the curves back to their one-second
        # anchor here. That painted a frame 6-30 px behind, and the refresh below then
        # jumped forward again (visible back-and-forth on every click). That refresh
        # resets the translation and redraws at the exact offset in one step.
        if not was_playing and not getattr(self, "_slider_scrubbing", False):
            self._reset_playback_transforms()
        if PLAYBACK_THIN_LINES:
            self._set_playback_thin_lines(False)
        if PLAYBACK_SEGMENTED_LINES:
            self._set_playback_segmented_lines(False)
        if PLAYBACK_DISABLE_ANTIALIAS and was_playing:
            self._set_playback_antialias(True)
        pass
        if was_playing:
            try:
                self.update_time_position_label()
            except Exception:
                pass
        
        # Update button if it exists
        if self.play_pause_btn:
            self.play_pause_btn.setText("▶ Play")

        # Paint the button state first, then do one complete refresh so
        # throttled labels and overlays settle at the exact paused position.
        if was_playing:
            QTimer.singleShot(0, self._refresh_after_pause)

    def _remember_play_scale_for_pause(self):
        """Pause must show what Play showed.

        While playing, Airflow / Thorax run on ONE fixed Y range (the range of the paused
        chart at Play start).  On Pause the charts used to be re-fitted from scratch to the
        visible window: a movement or a big recovery breath in that window then widened
        the axis and the breathing was drawn flat.  Real PSG keeps the gain fixed, so the
        Play range is remembered here and re-applied while paused (see
        _pause_hold_range).  "R" returns to it, seeking far away / another time window /
        another recording / Play again drop it.
        """
        held = self.__dict__.get("_strip_y_held") or {}
        ranges = {}
        for key, value in held.items():
            name = str(key).strip()
            if name in AXIS_SMOOTH_CHARTS and value is not None:
                low, high = float(value[0]), float(value[1])
                if high > low:
                    ranges[name] = (low, high)
        if not ranges:
            self._pause_hold = None
            return
        self._pause_hold = {
            "ranges": ranges,
            "offset": float(self.current_time_offset),
            "window": float(self.get_effective_time_window_seconds()),
            "data": id(self.psg_full_data),
        }

    def _pause_hold_range(self, chart_name):
        """The remembered Play range for this chart while it is still valid, else None."""
        hold = self.__dict__.get("_pause_hold")
        if not hold or self.is_playing:
            return None
        try:
            window = float(self.get_effective_time_window_seconds())
            offset = float(self.current_time_offset)
            if (
                hold["data"] != id(self.psg_full_data)
                or abs(window - hold["window"]) > 1e-6
                or abs(offset - hold["offset"]) > 3.0 * hold["window"]
            ):
                self._pause_hold = None
                return None
            return hold["ranges"].get(str(chart_name).strip())
        except Exception:
            self._pause_hold = None
            return None

    def _log_axis_widened(self, chart_name, typical, normal_span, recording_amplitude, movement_limit):
        """Diagnostics (throttled): the fitted axis is much wider than the breathing."""
        now = time.monotonic()
        if now - float(self.__dict__.get("_axis_widen_log_t", -1e9)) < 2.0:
            return
        self._axis_widen_log_t = now
        _psg_playback_log(
            "%s axis wider than the breathing: typical amplitude=%.4g, axis span=%.4g (x%.1f), "
            "recording amplitude=%s, movement limit=%s, offset=%.1fs"
            % (chart_name, typical, normal_span, normal_span / max(typical, 1e-9),
               recording_amplitude, movement_limit,
               float(getattr(self, "current_time_offset", 0.0) or 0.0))
        )

    def _refresh_after_pause(self):
        if self.is_playing or getattr(self, "_slider_scrubbing", False):
            return
        try:
            self.refresh_charts()
        except Exception:
            pass
        if self.__dict__.get("_strip_pending_release") and not self.is_playing:
            self._strip_release(keep_tiles=True)
    
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
            if PERF_SUMMARY:
                _PERF.add_drop()
            return

        _tick_t0 = time.perf_counter()
        _tick_gap = (_tick_t0 - self.__dict__.get("_last_tick_t", _tick_t0)) * 1000.0
        self._last_tick_t = _tick_t0
        _tick_parts = {}
        self._playback_busy = True
        try:
            max_time = self._get_playback_max_duration()
            if max_time <= 0:
                self.pause_playback()
                return

            max_offset = self._get_playback_max_offset()

            if self.__dict__.get("_strip") is not None:
                if self._strip_tick(max_offset):
                    return

            # Move forward by the real elapsed time, scaled to keep the old feel.
            if self._playback_clock.isValid():
                elapsed_sec = self._playback_clock.restart() / 1000.0
            else:
                self._playback_clock.start()
                elapsed_sec = float(PLAYBACK_FRAME_INTERVAL_MS) / 1000.0
            # Guard against a huge jump after the app was blocked/minimised.
            elapsed_sec = min(elapsed_sec, 0.5)
            self.current_time_offset = self._next_playback_offset(elapsed_sec)

            # Stop on the last full visible window instead of sliding past the final samples.
            if self.current_time_offset >= max_offset:
                self.current_time_offset = max_offset
                self._reset_playback_pacing()
                self.refresh_charts()
                self.update_time_position_label()
                self.pause_playback()
                pass
                return

            _t = time.perf_counter()
            last_refresh = self.__dict__.get("_last_playback_data_refresh", 0.0)
            refresh_interval = self._get_adaptive_refresh_interval()
            if _t - last_refresh >= refresh_interval:
                # setData() does not clear a GraphicsItem translation, so put
                # paths back at their origin before replacing their samples.
                self._reset_playback_transforms()
                self.refresh_charts()
                self._capture_playback_anchor()
                refresh_cost_sec = time.perf_counter() - _t
                _tick_parts["refresh"] = refresh_cost_sec * 1000.0
                self._record_refresh_cost(refresh_cost_sec)
            else:
                self._translate_playback_items()
                _tick_parts["translate"] = (time.perf_counter() - _t) * 1000.0
            _t = time.perf_counter()
            self.update_time_position_label(throttle=True)
            _tick_parts["label+slider"] = (time.perf_counter() - _t) * 1000.0
        finally:
            self._playback_busy = False
            if PERF_SUMMARY:
                _PERF.add_tick(
                    _tick_gap,
                    (time.perf_counter() - _tick_t0) * 1000.0,
                    _tick_parts,
                    owner=self,
                )
            if PERF_FRAME_PROFILE and _tick_parts:
                inside = (time.perf_counter() - _tick_t0) * 1000.0
                detail = " ".join(f"{key}={value:.0f}" for key, value in _tick_parts.items())
                pass
    
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
            # Slider position is the actual multiplier: 1 -> 1x, 2 -> 2x, 3 -> 3x, 4 -> 4x.
            self.playback_speed = min(4.0, max(1.0, float(speed_value)))
        else:
            self.playback_speed = speed_map.get(str(speed_value), 1.0)
            if hasattr(self, "slider_speed"):
                target_value = int(round(self.playback_speed))
                if self.slider_speed.value() != target_value:
                    self.slider_speed.blockSignals(True)
                    self.slider_speed.setValue(target_value)
                    self.slider_speed.blockSignals(False)

        if hasattr(self, "lbl_speed_val"):
            self.lbl_speed_val.setText(f"{self.playback_speed:.1f}x")

        pass
    
    def update_time_position_label(self, throttle=False):
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
        if throttle and PLAYBACK_SLIDER_UPDATE_HZ > 0:
            now = time.perf_counter()
            last = self.__dict__.get("_last_time_position_emit", 0.0)
            if now - last < 1.0 / float(PLAYBACK_SLIDER_UPDATE_HZ):
                return
            self._last_time_position_emit = now
        self.time_position_updated.emit()
    
    def refresh_charts_minimal(self):
        """Refresh charts during playback without overlay rendering to prevent crashes"""
        window_seconds = self.get_effective_time_window_seconds()
        pass
        
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
                    pass
                
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

    @staticmethod
    def _visible_part_of_playback_tail(x_data, y_data, window_seconds, data_window_seconds):
        """Return the samples that lie inside the visible window.

        refresh_charts() asks for window + tail seconds while playing so that the
        translated curve always has data to scroll into view.  The tail must be
        DRAWN but must not feed axis fitting / event marking / labels, which assume
        the arrays cover the visible window only.  When there is no tail (not
        playing, all-PSG mode) the arrays are returned untouched.
        """
        if float(data_window_seconds) <= float(window_seconds) + 1e-9:
            return x_data, y_data
        x = np.asarray(x_data, dtype=float).reshape(-1)
        y = np.asarray(y_data, dtype=float).reshape(-1)
        n = min(x.size, y.size)
        if n == 0:
            return x[:0], y[:0]
        inside = int(np.count_nonzero(x[:n] <= float(window_seconds)))
        keep = min(n, inside + 2)          # +2: same slight overshoot the old slice had
        return x[:keep], y[:keep]

    def refresh_charts(self):
        """Refresh all charts with current time window and offset."""
        # Event jumps, the slider arrows and navigation can move current_time_offset
        # while playback is running. The per-frame translation on the curves belongs
        # to the OLD offset; leaving it on a freshly drawn window pushes the curves
        # off screen until the next periodic refresh. Always draw from a clean origin.
        self._reset_playback_transforms()
        window_seconds = self.get_effective_time_window_seconds()
        # Keep a small off-screen tail ready at the right edge. During the
        # cheap translated frames this tail scrolls into view, preventing a
        # blank strip before the next source-data refresh.
        data_window_seconds = float(window_seconds)
        if self.is_playing and not self.is_all_psg_mode():
            _refresh_interval = self._get_adaptive_refresh_interval()
            # Between two rebuilds the curve is only translated, so the tail must cover
            # (interval + the rebuild's own cost + a short GUI stall) * speed seconds.
            # 1.5x was only just enough on a clean run; 2x + 0.5 s leaves real margin.
            data_window_seconds += max(
                0.5,
                _refresh_interval * float(self.playback_speed) * 2.0 + 0.5,
            )
        pass

        _frame_t0 = time.perf_counter()
        _chart_ms = {}
        _lean = bool(
            PLAYBACK_LEAN_REPAINT
            and (self.is_playing or getattr(self, "_slider_scrubbing", False))
        )
        # Changing a Y range while the trace is moving reads as a full-graph
        # flash. Keep the current scale locked throughout playback and refit
        # once after pause/seek.
        # Strip pages are rendered infrequently in the background. Fit them
        # through the same axis path as a paused refresh so weak Effort/Snoring
        # signals do not look compressed during Play and jump larger on Pause.
        _axis_updates_due = not _lean or bool(self.__dict__.get("_strip_force_axis_fit", False))
        _axis_page_turn = False
        if _lean and AXIS_REFIT_ON_JUMP:
            _fit_at = self.__dict__.get("_axis_fit_offset")
            _turn = max(
                self.AXIS_OFFSET_JUMP_MIN_SEC,
                min(float(window_seconds) * 0.5, self.AXIS_OFFSET_JUMP_MAX_SEC),
            )
            _axis_page_turn = (
                _fit_at is None
                or abs(float(self.current_time_offset) - float(_fit_at)) > _turn
            )
        if _axis_updates_due or _axis_page_turn:
            self._axis_fit_offset = float(self.current_time_offset)
        _decorations_due = True
        if _lean and PLAYBACK_DECORATION_UPDATE_HZ > 0:
            _now = time.perf_counter()
            _last = self.__dict__.get("_last_playback_decoration_update", 0.0)
            _decorations_due = (
                _now - _last >= 1.0 / float(PLAYBACK_DECORATION_UPDATE_HZ)
            )
            if _decorations_due:
                self._last_playback_decoration_update = _now
        if not _lean:
            self.setUpdatesEnabled(False)
        try:
            for i in range(self.charts_layout.count()):
                _chart_t0 = time.perf_counter()
                container = self.charts_layout.itemAt(i).widget()
                if not (container and hasattr(container, 'plot_widget')):
                    continue

                try:
                    plot_widget = container.plot_widget
                    chart_name = plot_widget.chart_name

                    vb = plot_widget.getViewBox()
                    if hasattr(vb, 'set_time_window_limits'):
                        vb.set_time_window_limits(0, window_seconds)
                        pass

                    # Store current Y-axis range to preserve zoom settings
                    if not hasattr(plot_widget, 'zoom_y_range'):
                        plot_widget.zoom_y_range = None

                    if _decorations_due:
                        self.remove_stale_plot_curves(plot_widget)

                    if not self.is_all_psg_mode():
                        if not self._x_range_is_current(plot_widget, vb, window_seconds):
                            plot_widget.setXRange(0, window_seconds, padding=0)
                            bottom_axis = plot_widget.getAxis('bottom')
                            bottom_axis.setRange(0, window_seconds)

                            if hasattr(vb, 'setRange'):
                                try:
                                    vb.setRange(x=[0, window_seconds], padding=0)
                                except Exception:
                                    plot_widget.setXRange(0, window_seconds, padding=0)

                        plot_widget.fixed_range = [0, window_seconds]

                    if chart_name.strip() == "SpO2":
                        x, y = self.get_spo2_data_for_window(data_window_seconds, self.current_time_offset)
                        if len(x) > 0 and len(y) > 0:
                            # Update normal line plot
                            plot_widget.plot_curve.setData(x, y, connect='finite')
                            plot_widget.plot_curve.opts['fill'] = None

                            if self.is_all_psg_mode():
                                self._apply_all_psg_mode_range_fixup(plot_widget, vb, x, window_seconds)

                            zero_axis_applied = self._apply_spo2_zero_axis_if_needed(
                                plot_widget, y
                            )
                            if zero_axis_applied:
                                pass
                            elif hasattr(plot_widget, 'axis_properties') and _axis_updates_due:
                                properties = plot_widget.axis_properties
                                low_value = properties.get('low_value', 35.0)
                                high_value = properties.get('high_value', 100.0)
                                try:
                                    plot_widget.setYRange(low_value, high_value, padding=0)
                                except TypeError:
                                    plot_widget.setRange(yRange=[low_value, high_value], padding=0)
                            else:
                                # Match Airflow/Thorax: fit the visible data window.
                                self._apply_windowed_auto_axis(plot_widget, "SpO2", y)

                            # Labels on every window - raw samples on short ones,
                            # bucket averages on long ones.
                            pass
                            self.create_spo2_markers_and_labels(plot_widget, x, y)
                            pass
                        else:
                            plot_widget.plot_curve.setData([], [])
                            # The curve is empty here, but SpO2 labels are
                            # separate TextItems. Clearing them here keeps the
                            # previous recording's numbers from staying painted
                            # over a file that has no SpO2 channel.
                            self.create_spo2_markers_and_labels(plot_widget, [], [])
                    else:
                        # PLAYBACK RIGHT-EDGE GAP FIX.
                        # During playback the curves are only TRANSLATED between full
                        # rebuilds (see update_playback).  The pre-loaded off-screen tail
                        # (data_window_seconds) used to be requested for SpO2 only, so
                        # Airflow / Effort / Snoring / Pulse / Body Position ran out of data
                        # ~interval*speed seconds before the next rebuild and a blank strip
                        # opened at the right edge, then snapped shut on every rebuild.
                        # Draw the curve from the tail-extended data, but hand the
                        # visible-window part (x, y) to everything else (axis fit, events,
                        # labels) so their behaviour is exactly what it was before.
                        x_draw, y_draw = self.get_signal_data_for_window(
                            chart_name, data_window_seconds, self.current_time_offset)
                        x, y = self._visible_part_of_playback_tail(
                            x_draw, y_draw, window_seconds, data_window_seconds)

                        if len(x) > 0 and len(y) > 0:
                            if self.is_all_psg_mode():
                                self._apply_all_psg_mode_range_fixup(plot_widget, vb, x, window_seconds)
                            # Use real data from the uploaded recording.
                            if chart_name.strip() == "Body Position":
                                self._configure_body_position_axis(plot_widget)
                                x_step, y_step = self._build_body_position_step_data(x_draw, y_draw)
                                plot_widget.plot_curve.setData(x_step, y_step, connect='finite', stepMode=True)
                            else:
                                plot_widget.plot_curve.setData(x_draw, y_draw, connect='finite')
                            pass
                        else:
                            plot_widget.plot_curve.setData([], [])
                            pass

                        if hasattr(plot_widget, 'axis_properties'):
                            properties = plot_widget.axis_properties
                            low_value = properties.get('low_value', 35.0)
                            high_value = properties.get('high_value', 100.0)
                            try:
                                plot_widget.setYRange(low_value, high_value, padding=0)
                            except TypeError:
                                plot_widget.setRange(yRange=[low_value, high_value], padding=0)
                        elif chart_name.strip() == "Pulse":
                            self._apply_windowed_auto_axis(plot_widget, "Pulse", y)
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
                        elif chart_name.strip() == "Snoring":
                            self._apply_windowed_auto_axis(plot_widget, "Snoring", y)
                        elif chart_name.strip() in AUTO_RANGE_SIGNAL_NAMES:
                            auto_y_min, auto_y_max = self.get_signal_auto_axis_range(
                                chart_name.strip()
                            )
                            hard_min, hard_max = self._finite_min_max(y)
                            self._lock_auto_axis(
                                plot_widget, auto_y_min, auto_y_max, hard_min, hard_max
                            )
                    if chart_name.strip() == "Pulse":
                        # After the axis has been applied, so "row" mode sees this frame's range.
                        if len(x) > 0 and len(y) > 0:
                            self.create_pulse_markers_and_labels(plot_widget, x, y)
                        else:
                            self.create_pulse_markers_and_labels(plot_widget, [], [])
                    if chart_name.strip() == "Snoring":
                        self._update_snoring_phase_overlays(plot_widget, data_window_seconds)
                    if chart_name.strip() == "Airflow":
                        self.mark_dashboard_fl(plot_widget, x, y)
                        self._render_sensor_off_segments(plot_widget)
                    self._render_recording_exclusions(plot_widget)
                    _chart_ms[chart_name.strip()] = (
                        time.perf_counter() - _chart_t0
                    ) * 1000.0
                except Exception as chart_error:
                    pass
                    continue

            _t = time.perf_counter()
            self.render_dynamic_selections()
            _chart_ms["selections"] = (time.perf_counter() - _t) * 1000.0
            _t = time.perf_counter()
            self.update_apnea_events_display()
            _chart_ms["events_label"] = (time.perf_counter() - _t) * 1000.0
        finally:
            if self.is_playing:
                # Re-anchor the translation baseline to this fresh draw (see the top
                # of this function) so the next playback frames continue from it.
                self._capture_playback_anchor()
            _t = time.perf_counter()
            if not _lean:
                self.setUpdatesEnabled(True)
                self.update()
            _chart_ms["repaint"] = (time.perf_counter() - _t) * 1000.0
            if self.__dict__.get("_log_first_draw"):
                self._log_first_draw = False
                _psg_playback_log(
                    "first draw after load: %.0f ms | %s"
                    % ((time.perf_counter() - _frame_t0) * 1000.0,
                       " ".join("%s=%.0f" % (key, value) for key, value in _chart_ms.items()))
                )
            if PERF_SUMMARY:
                _PERF.add_refresh((time.perf_counter() - _frame_t0) * 1000.0, _chart_ms)
            if PERF_FRAME_PROFILE:
                # Profiling only: paint right now so the real painting cost shows up
                # in the log (normally Qt paints after this function returns).
                _t = time.perf_counter()
                self.repaint()
                _chart_ms["PAINT"] = (time.perf_counter() - _t) * 1000.0
                total = (time.perf_counter() - _frame_t0) * 1000.0
                parts = " ".join(f"{key}={value:.0f}" for key, value in _chart_ms.items())
                pass

    def _snoring_phase_window(self, phase_code, time_window_seconds, time_offset=0):
        """Return snoring samples of one phase for the visible window."""
        empty = np.array([]), np.array([])
        signals = (self.psg_full_data or {}).get("signals", {})
        packets = signals.get("snoring_packets")
        full = signals.get("snoring")
        if packets is None or full is None or self.is_all_psg_mode():
            return empty
        packets = np.asarray(packets, dtype=float)
        if packets.ndim != 2 or packets.shape[0] == 0:
            return empty
        rate = self.channel_rate("snoring")
        window_time, window_signal = self._slice_signal_for_window(
            full, time_window_seconds, time_offset, sample_rate_hz=rate)
        if window_signal.size == 0:
            return empty
        first = max(0, int(np.floor(float(time_offset) * rate)))
        last = first + window_signal.size
        wanted = (packets[:, 2] == float(phase_code)) & (packets[:, 1] > first) & (packets[:, 0] < last)
        mask = np.zeros(window_signal.size, dtype=bool)
        for start_idx, end_idx in packets[wanted][:, :2]:
            i0 = max(0, int(start_idx) - first)
            i1 = min(window_signal.size, int(end_idx) - first)
            if i1 > i0:
                mask[i0:i1] = True
        if not mask.any():
            return empty
        return self._prepare_plot_data_for_window(
            window_time, np.where(mask, window_signal, np.nan), time_window_seconds)

    def _update_snoring_phase_overlays(self, plot_widget, window_seconds):
        """Redraw exhale snore packets over the red inhale trace."""
        curves = getattr(plot_widget, "snore_phase_curves", None)
        if not curves:
            return
        if not SNORE_PHASE_OVERLAYS_ENABLED:
            for curve in curves.values():
                try:
                    if len(curve.xData or ()) > 0:
                        curve.setData([], [])
                except Exception:
                    pass
            return
        for key, code in (("exhale", SNORE_PHASE_EXHALE_CODE), ("review", SNORE_PHASE_ISOLATED_CODE)):
            curve = curves.get(key)
            if curve is None:
                continue
            x, y = self._snoring_phase_window(code, window_seconds, self.current_time_offset)
            if len(x) and np.isfinite(y).any():
                curve.setData(x, y, connect="finite")
            else:
                curve.setData([], [])

    def remove_stale_plot_curves(self, plot_widget):
        """Keep primary and snoring phase curves during chart refreshes."""
        primary_curve = getattr(plot_widget, "plot_curve", None)
        keep_ids = {id(primary_curve)} | {
            id(curve) for curve in (getattr(plot_widget, "snore_phase_curves", None) or {}).values()
        }
        try:
            for data_item in list(plot_widget.listDataItems()):
                if id(data_item) in keep_ids:
                    continue
                plot_widget.removeItem(data_item)
        except Exception:
            pass
    
    def set_time_window(self, seconds):
        """Set the time window for the sleep monitoring chart (legacy method for compatibility)"""
        pass
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
        # window is stale. Only when the window ACTUALLY changed: this method
        # can be called with the same value on every dashboard sync, and that
        # must not throw the held playback axis away each time.
        window_changed = abs(float(self.get_effective_time_window_seconds()) - float(previous_window)) > 1e-6
        if window_changed:
            self._clear_axis_hold()
            for chart_index in range(self.charts_layout.count()):
                chart_container = self.charts_layout.itemAt(chart_index).widget()
                if chart_container is None or not hasattr(chart_container, "plot_widget"):
                    continue
                chart_container.plot_widget.zoom_y_range = None
                chart_container.plot_widget.stable_y_range = None
                chart_container.plot_widget.stable_y_range_offset = None

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
            pass
            
            # Update charts with new time window (refresh data only, don't recreate charts)
            if chart_count > 0:
                pass
                self.refresh_charts()
                self.restore_all_selections()
            else:
                pass
                self.update_charts_for_time_window(seconds)

            # Keep dashboard slider and time label in sync with the new window.
            self.update_time_position_label()
            self.time_window_mode_changed.emit(self.is_all_psg_mode())
            
            pass

    
    def update_charts_for_time_window(self, seconds):
        """Update chart data based on time window selection"""
        pass
        
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

        self.play_pause_btn = PlayPauseButton()
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
                padding: 2px 10px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 10px;
                font-weight: 600;
                min-width: 84px;
            }
            QPushButton#playbackPlayButton:hover { background-color: #1d4ed8; }
            QPushButton#playbackPlayButton:pressed { background-color: #1e40af; }
            QPushButton#playbackPlayButton:disabled { background-color: #cbd5e1; color: #64748b; }
        """)
        
        # Add all controls to container
        controls_layout.addWidget(self.play_pause_btn)
        
        controls_layout.addWidget(self._divider())

        self.lbl_speed_title = QLabel("SPEED")
        self.lbl_speed_title.setStyleSheet(section_title_style)
        controls_layout.addWidget(self.lbl_speed_title)
        controls_layout.addSpacing(10)

        # Click-to-select speed presets (1x / 2x / 3x / 4x).  A drag slider jumped to 4x on
        # any click (see SpeedSelector), and a preset row is the standard control for this.
        self.slider_speed = SpeedSelector((1, 2, 3, 4))
        self.slider_speed.valueChanged.connect(self.change_playback_speed)
        controls_layout.addWidget(self.slider_speed)

        # The selected button already shows the speed, so the old "1.0x" text is not shown.
        self.lbl_speed_val = QLabel("1.0x")
        self.lbl_speed_val.setVisible(False)

        controls_layout.addWidget(self._divider())

        # Temporarily hidden: EVENTS section in the playback controls.
        # self.lbl_events_title = QLabel("EVENTS")
        # self.lbl_events_title.setStyleSheet(section_title_style)
        # controls_layout.addWidget(self.lbl_events_title)
        # controls_layout.addSpacing(10)

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
        self.detection_status_spinner = LoadingSpinner(self, size=16, line_width=2)
        # Temporarily hide the event status badge and spinner with the EVENTS section.
        self.detection_summary_label.hide()
        self.detection_status_spinner.hide()
        # controls_layout.addSpacing(6)
        # controls_layout.addWidget(self.detection_status_spinner)
        # controls_layout.addSpacing(4)
        # controls_layout.addWidget(self.detection_summary_label)
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
            pass
            chart = self.create_signal_chart(name, color, freq, amp, offset, y_min, y_max)
            self.charts_layout.addWidget(chart, stretch=1)
            # Track the original order
            self.graph_order.append(name)
        
        pass
        # INITIAL VIEWBOX SYNC (Fix first-time rendering)
        QTimer.singleShot(150, self._initial_viewbox_sync)
    
    def _initial_viewbox_sync(self):
        """Initial ViewBox synchronization to fix first-time rendering issue"""
        pass
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
                pass

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
        return series.to_numpy(dtype=float, copy=True)

    def _load_uploaded_psg_signals(self, recording_path):
        """Load chart signals from an uploaded binary SD recording.

        Returns ``(time_data, signals, times, sample_rates, source_format)``.
        ``time_data`` is the master timeline (airflow for SD recordings);
        ``times[name]`` is each channel's own time axis at its native rate.
        """
        if load_sleep_recording is None:
            raise RuntimeError(
                "Recording loader import failed."
                + (f" {RECORDING_IMPORT_ERROR}" if RECORDING_IMPORT_ERROR else "")
            )

        _t_load = time.perf_counter()
        recording = load_sleep_recording(recording_path, preserve_recorded_airflow=True)
        _t_parsed = time.perf_counter()
        raw_time = np.asarray(recording.get("time", []), dtype=float)
        finite_raw_time = raw_time[np.isfinite(raw_time)]
        raw_duration_sec = (
            float(finite_raw_time[-1] - finite_raw_time[0])
            if finite_raw_time.size > 1
            else 0.0
        )
        # Product rule: recordings shorter than one hour are rejected, and the
        # first/last 5 minutes are always removed (never analysed untrimmed).
        require_minimum_recording(recording)
        edge_trim_seconds = RECORDING_EDGE_TRIM_SECONDS
        recording = trim_recording_edges(
            recording,
            start_seconds=edge_trim_seconds,
            end_seconds=edge_trim_seconds,
        )
        _t_trimmed = time.perf_counter()
        source_format = recording.get("source_format", "csv")
        raw_signals = recording.get("signals", {})
        times = {name: np.asarray(values, dtype=float) for name, values in recording.get("times", {}).items()}
        sample_rates = {name: float(rate) for name, rate in recording.get("sample_rates", {}).items()}
        time_data = np.asarray(recording.get("time", []), dtype=float)
        if time_data.size == 0 or not raw_signals:
            raise ValueError("Uploaded PSG file did not contain any usable rows.")

        signals = {}
        if "airflow_recorded" in raw_signals:
            signals["airflow_recorded"] = np.asarray(raw_signals["airflow_recorded"], dtype=float)
            if source_format == "smf":
                # SD recordings: the airflow time axis IS the recorded time.
                signals["airflow_recorded_time"] = times["airflow_recorded"].copy()
            else:
                signals["airflow_recorded_time"] = np.asarray(raw_signals["timestamp"], dtype=float) / 1000.0
            times["airflow_recorded_time"] = times.get("airflow_recorded", time_data).copy()
            sample_rates["airflow_recorded_time"] = sample_rates.get("airflow_recorded", sample_rates.get("airflow", EXTERNAL_ARRAY_SAMPLE_RATE_HZ))

        # Binary SD recordings expose channels at their native rates. Keep the
        # processing list explicit so derived/metadata aliases are not treated
        # as ordinary waveform channels.
        binary_signal_names = (
            "body_position", "pulse", "spo2", "body_movement",
            "airflow", "thorax", "snoring",
        )
        for signal_name in binary_signal_names:
            if signal_name not in raw_signals:
                continue
            raw_signal = np.asarray(raw_signals[signal_name], dtype=float)
            if signal_name == "spo2":
                # Keep the existing validity handling, but cap occasional
                # above-range readings at the physiological maximum.
                raw_signal = np.where(
                    np.isfinite(raw_signal) & (raw_signal > 100.0),
                    100.0,
                    raw_signal,
                )
            rate = sample_rates.get(signal_name, EXTERNAL_ARRAY_SAMPLE_RATE_HZ)
            prepared_signal = self._prepare_external_array_signal(
                raw_signal,
                sample_rate_hz=rate,
                valid_range=SIGNAL_VALID_RANGES.get(signal_name),
                fill_gaps=signal_name not in SIGNAL_NO_GAP_FILL,
            )
            if signal_name == "spo2":
                # A zero SpO2 value is a device no-signal sentinel, not a
                # physiological reading. Keep the cleaned series so the
                # display can hold the preceding valid value through it.
                signals["spo2_display"] = prepared_signal.copy()
                times["spo2_display"] = times.get("spo2", time_data)
                sample_rates["spo2_display"] = rate
            signals[signal_name] = prepared_signal

            if signal_name == "airflow":
                raw_airflow = np.asarray(prepared_signal, dtype=float)
                # Filter kernels are in SAMPLES; scale them with the channel
                # rate so a "~1 s" median stays ~1 s at 125 Hz as it was at 10 Hz.
                kernel_scale = max(1.0, rate / EXTERNAL_ARRAY_SAMPLE_RATE_HZ)
                kernel_size = int(round(11 * kernel_scale)) | 1
                savgol_window = int(round(11 * kernel_scale)) | 1
                enhanced_airflow = enhance_airflow_for_graph_and_detection(
                    raw_airflow,
                    amplitude=1.10,
                    max_limit=None,
                    spike_threshold=15.0,
                    kernel_size=kernel_size,
                    low_protect_margin=2.0,
                    keep_integer=False,
                    savgol_window=savgol_window,
                    savgol_order=3,
                )
                signals["airflow_raw"] = raw_airflow
                signals["airflow_enhanced"] = enhanced_airflow
                signals["airflow_display"] = self._airflow_display_series(
                    raw_airflow, enhanced_airflow, rate, source_format,
                )
                signals["airflow_detection"] = enhanced_airflow
                if self._signal_swing_below(enhanced_airflow, rate, AIRFLOW_MIN_VALID_SWING_COUNTS):
                    # No cannula connected: draw a flat line from the FIRST draw. Otherwise the chart
                    # auto-zooms ~2 counts of ADC noise into a fake breathing wave until detection
                    # finishes and the sensor-off masking flattens it.  (Display copy only.)
                    shown = np.asarray(signals["airflow_display"], dtype=float)
                    finite_shown = shown[np.isfinite(shown)]
                    level = float(np.median(finite_shown)) if finite_shown.size else 0.0
                    signals["airflow_display"] = np.where(np.isfinite(shown), level, np.nan)
                if AIRFLOW_DEBUG_FLAT_TOPS:
                    self._airflow_flat_top_report("raw sensor signal", raw_airflow, rate)
                    self._airflow_flat_top_report(
                        "enhanced copy (what was drawn before)", enhanced_airflow, rate,
                    )
                for alias in ("airflow_raw", "airflow_enhanced", "airflow_display", "airflow_detection"):
                    times[alias] = times.get("airflow", time_data)
                    sample_rates[alias] = rate
            elif signal_name == "thorax":
                raw_thorax = np.asarray(prepared_signal, dtype=float)
                kernel_scale = max(1.0, rate / EXTERNAL_ARRAY_SAMPLE_RATE_HZ)
                smoothed_thorax = self.smooth_data(
                    np.arange(len(raw_thorax), dtype=float),
                    raw_thorax,
                    window_size=int(round(11 * kernel_scale)) | 1,
                )
                display_thorax = self._smooth_thorax_for_display(raw_thorax, rate)
                display_series = (
                    display_thorax if display_thorax is not None else smoothed_thorax
                )
                # DISPLAY copy only: take out the slow belt-baseline drift so the fixed
                # Play-time Y range keeps framing the whole breath (raw / smoothed copies,
                # used for analysis, are not touched).
                if THORAX_BASELINE_REMOVE:
                    try:
                        flattened = remove_slow_baseline(display_series, rate)
                    except Exception:
                        flattened = None
                    if flattened is not None:
                        display_series = flattened
                if self._thorax_is_unplugged(raw_thorax, rate):
                    # No belt connected: draw a flat line at the recorded level. Without this the
                    # low-pass + auto-zoom blows ~1 count of ADC noise up into a fake breathing wave.
                    finite_thorax = raw_thorax[np.isfinite(raw_thorax)]
                    level = float(np.median(finite_thorax)) if finite_thorax.size else 0.0
                    display_series = np.where(np.isfinite(raw_thorax), level, np.nan)
                signals["thorax_raw"] = raw_thorax
                signals["thorax_smoothed"] = smoothed_thorax
                signals["thorax_display"] = display_series
                for alias in ("thorax_raw", "thorax_smoothed", "thorax_display"):
                    times[alias] = times.get("thorax", time_data)
                    sample_rates[alias] = rate

        # Show SD snore vibration on the airflow display copy only.
        if (
            source_format == "smf"
            and "airflow_display" in signals
            and "snoring" in raw_signals
            and len(raw_signals["snoring"]) == len(signals["airflow_display"])
        ):
            signals["airflow_display"] = add_snore_texture_to_airflow_display(
                signals["airflow_display"],
                np.asarray(raw_signals["snoring"], dtype=float),
            )
        if "airflow_display" in signals:
            signals["airflow_display_base"] = np.array(
                signals["airflow_display"], dtype=float, copy=True
            )

        # Keep the original accelerometer axes alongside the derived movement.
        for axis_name in ("body_movement_x", "body_movement_y", "body_movement_z",
                          "accel_x", "accel_y", "accel_z"):
            if axis_name in raw_signals:
                signals[axis_name] = np.asarray(raw_signals[axis_name], dtype=float)

        # ECG is parsed from SD recordings but intentionally NOT plotted yet.
        if "ecg" in raw_signals:
            signals["ecg"] = np.asarray(raw_signals["ecg"], dtype=float)

        # Snore packets with their breath phase (inhale / exhale), SD
        # recordings only. One row per packet; see sd_record_reader.PACKET_COLUMNS.
        if "snoring_packets" in raw_signals:
            signals["snoring_packets"] = np.asarray(raw_signals["snoring_packets"], dtype=float)

        _psg_playback_log(
            "upload worker: read+parse %.0f ms (a parse started by the detector is shared), trim %.0f ms, "
            "channel processing %.0f ms"
            % ((_t_parsed - _t_load) * 1000.0, (_t_trimmed - _t_parsed) * 1000.0,
               (time.perf_counter() - _t_trimmed) * 1000.0)
        )
        return time_data, signals, times, sample_rates, source_format

    def _airflow_for_fl_detection(self, raw):
        """Return recorded airflow with breathing IN as the upward peak."""
        from .fl_waveform_widget import FL_LEGACY_LOGIC
        values = np.asarray(raw, dtype=float)
        data = self.psg_full_data or {}
        if (
            not FL_LEGACY_LOGIC
            and FL_DETECT_ON_INHALE_SIDE
            and INSPIRATION_IS_LOW_AIRFLOW
            and str(data.get("source_format", "")) == "smf"
        ):
            return -values
        return values

    def _snoring_for_fl_detection(self, signals, raw):
        """Return SD snore packets as ATS inspiratory confirmation evidence."""
        from .fl_waveform_widget import FL_LEGACY_LOGIC
        data = self.psg_full_data or {}
        if FL_LEGACY_LOGIC or str(data.get("source_format", "")) != "smf":
            return None
        snoring = signals.get("snoring")
        if snoring is None or raw is None or len(snoring) != len(raw):
            return None
        return np.asarray(snoring, dtype=float)

    def _fl_start_background(self, raw, signals):
        """Run the whole-night flow-limitation analysis in a worker thread.

        It used to run inside the first draw of the Airflow chart (GUI thread) and made "Drawing graphs"
        1.5-3 s longer.  Now the graphs are drawn at once and _on_fl_ready adds the markers when the
        analysis is done; the numbers are exactly those the synchronous call produced.
        """
        job = self.__dict__.get("_fl_job")
        if job is not None and job.get("source") is raw:
            return
        import threading
        from .fl_waveform_widget import plateau_breaths
        try:
            airflow = self._airflow_for_fl_detection(raw)
            times = signals["airflow_recorded_time"]
            snoring = self._snoring_for_fl_detection(signals, raw)
        except Exception:
            self._fl_cached_source = raw
            self._fl_cached_breaths = []
            return
        if not self.__dict__.get("_fl_signal_connected"):
            self._fl_ready.connect(self._on_fl_ready)
            self._fl_signal_connected = True
        self._fl_job = {"source": raw}
        signal = self._fl_ready

        def work():
            started = time.perf_counter()
            try:
                breaths = [b for b in plateau_breaths(airflow, times, snoring=snoring) if b["kind"] == "fl"]
            except Exception:
                breaths = []
            _psg_playback_log(
                "FL analysis (background): %.0f ms, %d flow-limited breaths"
                % ((time.perf_counter() - started) * 1000.0, len(breaths))
            )
            signal.emit((raw, breaths))

        threading.Thread(target=work, name="fl-analysis", daemon=True).start()

    def _on_fl_ready(self, payload):
        """GUI thread: the background FL analysis finished -> keep the result and draw the markers."""
        raw, breaths = payload
        job = self.__dict__.get("_fl_job")
        if job is not None and job.get("source") is raw:
            self._fl_job = None
        data = self.psg_full_data
        current = (data.get("signals", {}) if data else {}).get("airflow_recorded")
        if current is not raw:
            return                                   # another recording was loaded meanwhile
        self._fl_cached_source = raw
        self._fl_cached_breaths = breaths
        if not self.is_playing:
            self.refresh_charts()

    def mark_dashboard_fl(self, plot_widget, x, y):
        """Mark raw-sample plateau candidates at their dashboard waveform positions."""
        from .fl_waveform_widget import plateau_breaths, draw_dashboard_fl_labels

        data = self.psg_full_data
        signals = data.get("signals", {}) if data else {}
        raw = signals.get("airflow_recorded")
        fl_exclusions = list(self.get_recording_exclusions()["excluded_segments"]) + list(
            getattr(self, "sensor_off_shade_segments", None) or []
        )
        if getattr(self, "_fl_cached_source", None) is not raw and raw is not None and FL_COMPUTE_IN_BACKGROUND:
            self._fl_start_background(raw, signals)
            if getattr(self, "_fl_cached_source", None) is not raw:
                # Not ready yet: draw the chart without FL markers; _on_fl_ready redraws when the result exists.
                draw_dashboard_fl_labels(
                    plot_widget, [],
                    data.get("time", []) if data else [], x, y,
                    offset=0.0 if self.is_all_psg_mode() else self.current_time_offset,
                    exclusions=fl_exclusions,
                )
                return
        if getattr(self, "_fl_cached_source", None) is not raw:
            self._fl_cached_source = raw
            self._fl_cached_breaths = []
            if raw is not None:
                try:
                    self._fl_cached_breaths = [
                        b for b in plateau_breaths(
                            self._airflow_for_fl_detection(raw),
                            signals["airflow_recorded_time"],
                            snoring=self._snoring_for_fl_detection(signals, raw),
                        )
                        if b["kind"] == "fl"
                    ]
                except ValueError as error:
                    pass
            full_time_arr = np.asarray(data.get("time", []) if data else [], dtype=float)
            total_detected = len(self._fl_cached_breaths)
            excluded_count = 0
            for breath in self._fl_cached_breaths:
                if breath["end"] >= len(full_time_arr):
                    continue
                segment = {
                    "start_sec": float(full_time_arr[breath["start"]]),
                    "end_sec": float(full_time_arr[breath["end"]]),
                }
                if overlaps_exclusion(segment, fl_exclusions):
                    excluded_count += 1
            pass
        draw_dashboard_fl_labels(
            plot_widget,
            getattr(self, "_fl_cached_breaths", []) if raw is not None else [],
            data.get("time", []) if data else [], x, y,
            offset=0.0 if self.is_all_psg_mode() else self.current_time_offset,
            exclusions=fl_exclusions,
        )

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

    def _airflow_display_series(self, raw_airflow, enhanced_airflow, rate, source_format):
        """The airflow series that is DRAWN (detection always uses the enhanced series)."""
        if CLASSIC_PLOT_LOGIC:
            if source_format == "smf":
                return orient_airflow_for_display(enhanced_airflow)
            return enhanced_airflow
        aasm_function = getattr(self, "_aasm_airflow_for_display", None)
        aasm_airflow = aasm_function(raw_airflow, rate) if aasm_function is not None else None
        return orient_airflow_for_display(
            aasm_airflow if aasm_airflow is not None else enhanced_airflow
        )

    def _aasm_airflow_for_display(self, values, rate):
        """Airflow for drawing: AASM band-pass, zero phase."""
        if not AIRFLOW_AASM_FILTER_ENABLED:
            return None
        try:
            rate = float(rate)
        except (TypeError, ValueError):
            return None
        y = np.asarray(values, dtype=float).reshape(-1)
        low_hz = float(AIRFLOW_AASM_LOW_HZ)
        high_hz = float(AIRFLOW_AASM_HIGH_HZ)
        if rate <= 0.0 or y.size < int(40.0 * rate):
            return None
        finite = np.flatnonzero(np.isfinite(y))
        if finite.size < int(40.0 * rate):
            return None
        try:
            from scipy.signal import butter, sosfiltfilt
        except Exception:
            return None
        sections = []
        if low_hz > 0.0:
            sections.append(
                butter(
                    2,
                    low_hz * 0.41421356 ** 0.25 / (rate / 2.0),
                    btype="high",
                    output="sos",
                )
            )
        if high_hz > 0.0 and rate > 2.2 * high_hz:
            cutoff = min(high_hz / (0.41421356 ** 0.125), 0.45 * rate)
            sections.append(butter(4, cutoff / (rate / 2.0), output="sos"))
        if not sections:
            return None
        baseline = float(np.median(y[finite]))
        out = np.full_like(y, np.nan)
        pad = int(30.0 * rate)
        for segment in np.split(finite, np.where(np.diff(finite) > 1)[0] + 1):
            if segment.size < int(30.0 * rate):
                out[segment] = y[segment]
                continue
            values_in = y[segment] - baseline
            for sos in sections:
                values_in = sosfiltfilt(
                    sos,
                    values_in,
                    padtype="odd",
                    padlen=min(segment.size - 1, pad),
                )
            out[segment] = values_in + baseline
        return out

    @staticmethod
    def _thorax_is_unplugged(values, rate):
        """True when the RAW thorax is only ADC noise (no belt connected).

        Per 5 s block (95th - 5th percentile), then the 90th percentile over the night; a single
        spike cannot fake a breath and a belt that works for part of the night is not flagged.
        """
        try:
            x = np.asarray(values, dtype=float).reshape(-1)
            n = max(1, int(round(float(rate) * 5.0)))
            k = x.size // n
            if k < 1:
                return False
            blocks = x[: k * n].reshape(k, n)
            blocks = blocks[np.isfinite(blocks).all(axis=1)]
            if blocks.shape[0] == 0:
                return False
            # 90th percentile over the night = the best-connected stretch (same rule as the detector)
            swing = float(np.percentile(np.percentile(blocks, 95, axis=1) - np.percentile(blocks, 5, axis=1), 90))
            return swing < float(THORAX_MIN_VALID_SWING_COUNTS)
        except Exception:
            return False

    @staticmethod
    def _signal_swing_below(values, rate, limit):
        """True when even the best-connected stretch of ``values`` swings less than ``limit`` counts.

        Per 5 s block (95th - 5th percentile), then the 90th percentile over the night.
        """
        try:
            x = np.asarray(values, dtype=float).reshape(-1)
            n = max(1, int(round(float(rate) * 5.0)))
            k = x.size // n
            if k < 1:
                return False
            blocks = x[: k * n].reshape(k, n)
            blocks = blocks[np.isfinite(blocks).all(axis=1)]
            if blocks.shape[0] == 0:
                return False
            swing = float(np.percentile(np.percentile(blocks, 95, axis=1) - np.percentile(blocks, 5, axis=1), 90))
            return swing < float(limit)
        except Exception:
            return False

    def _airflow_flat_top_report(self, label, values, rate):
        """Debug whether many breaths end at one clipped level."""
        try:
            from scipy.signal import find_peaks
            rate = float(rate)
            y = np.asarray(values, dtype=float).reshape(-1)
            ok = y[np.isfinite(y)]
            if ok.size < int(60 * rate):
                return
            filled = np.where(np.isfinite(y), y, np.nanmedian(ok))
            spread = float(np.percentile(ok, 95) - np.percentile(ok, 5))
            parts = []
            for name, series, sign in (("tops", filled, 1.0), ("bottoms", -filled, -1.0)):
                peaks, _ = find_peaks(
                    series,
                    distance=max(1, int(1.5 * rate)),
                    prominence=0.4 * spread,
                )
                if peaks.size < 5:
                    parts.append(f"{name}: too few breaths")
                    continue
                levels = series[peaks]
                at_one_level = int(np.sum(levels >= levels.max() - 0.01 * spread))
                parts.append(
                    f"{name}: {at_one_level} of {peaks.size} breaths end within 1% of the single "
                    f"{'highest' if sign > 0 else 'lowest'} level"
                )
            pass
        except Exception:
            pass

    def _smooth_thorax_for_display(self, values, rate):
        """Zero-phase low-pass of the Thorax trace, for the DISPLAY copy only."""
        cutoff = float(THORAX_DISPLAY_LOWPASS_HZ)
        try:
            rate = float(rate)
        except (TypeError, ValueError):
            return None
        y = np.asarray(values, dtype=float).reshape(-1)
        if cutoff <= 0.0 or rate <= 2.5 * cutoff or y.size < 40:
            return None
        try:
            from scipy.signal import butter, filtfilt
            b, a = butter(2, cutoff / (rate / 2.0))
        except Exception:
            return None
        out = y.copy()
        finite = np.flatnonzero(np.isfinite(y))
        if finite.size == 0:
            return None
        for segment in np.split(finite, np.where(np.diff(finite) > 1)[0] + 1):
            if segment.size >= 30:
                out[segment] = filtfilt(b, a, y[segment])
        return out

    def _get_thorax_signal_variant(self, variant="display"):
        """Return the preferred thorax series for raw or smoothed thorax use."""
        if self.psg_full_data is None or "signals" not in self.psg_full_data:
            return np.array([])

        signals = self.psg_full_data["signals"]
        variant_map = {
            "raw": signals.get("thorax_raw"),
            "smoothed": signals.get("thorax_smoothed"),
            "display": signals.get("thorax_display", signals.get("thorax_smoothed")),
        }
        selected = variant_map.get(variant)
        if selected is None:
            selected = signals.get("thorax", np.array([]))
        return np.asarray(selected, dtype=float)

    def save_airflow_smoothing_debug_report(self, recording_path, raw_airflow, enhanced_airflow):
        """Write a text report showing how the shared enhanced airflow differs from raw data."""
        try:
            report_dir = get_configured_path("debug_reports_dir")
            report_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            source_name = Path(recording_path).stem if recording_path else "airflow"
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
                f"Source recording: {recording_path}",
                f"Generated: {datetime.now().isoformat()}",
                f"Samples compared: {point_count}",
                f"Sample rate used for timestamps: {self.channel_rate('airflow')} Hz",
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
                    time_sec = index / float(self.channel_rate("airflow"))
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
                time_sec = index / float(self.channel_rate("airflow"))
                lines.append(
                    f"{index:05d} | {time_sec:8.2f} | "
                    f"{raw_airflow[index]:.6f} | "
                    f"{enhanced_airflow[index]:.6f} | "
                    f"{enhanced_diff[index]:.6f}"
                )

            report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            pass
        except Exception:
            pass

    def _slice_signal_for_window(self, signal_values, time_window_seconds, time_offset=0, sample_rate_hz=None):
        """Slice a full signal into a fixed-duration window at its own rate."""
        signal_values = np.asarray(signal_values, dtype=float)
        samples_per_second = float(sample_rate_hz) if sample_rate_hz else EXTERNAL_ARRAY_SAMPLE_RATE_HZ
        expected_samples = int(round(time_window_seconds * samples_per_second))

        if expected_samples == 0:
            return np.array([]), np.array([])

        if len(signal_values) == 0:
            return np.arange(expected_samples) / samples_per_second, np.full(expected_samples, np.nan)

        # Slow SD channels are sampled once per second.  Rounding the
        # playback offset to an integer sample makes the trace freeze for
        # almost one second and then jump.  Sample at the fractional position
        # instead so playback advances continuously.  Invalid samples are not
        # interpolated across.
        if samples_per_second < self.DISPLAY_HOLD_BELOW_HZ:
            positions = float(max(0.0, time_offset)) * samples_per_second + np.arange(expected_samples, dtype=float)
            left = np.floor(positions).astype(int)
            right = np.minimum(left + 1, len(signal_values) - 1)
            fraction = positions - left
            in_bounds = (left >= 0) & (left < len(signal_values))
            left = np.clip(left, 0, len(signal_values) - 1)
            left_values = signal_values[left]
            right_values = signal_values[right]
            finite_pair = np.isfinite(left_values) & np.isfinite(right_values)
            window_signal = np.full(expected_samples, np.nan, dtype=float)
            usable = in_bounds & finite_pair
            window_signal[usable] = (
                left_values[usable]
                + fraction[usable] * (right_values[usable] - left_values[usable])
            )
            window_time = np.arange(expected_samples, dtype=float) / samples_per_second
            return window_time, window_signal

        offset = float(time_offset)
        start_sample = max(0, int(np.floor(offset * samples_per_second)))
        want = expected_samples + 2
        end_sample = min(len(signal_values), start_sample + want)

        window_signal = signal_values[start_sample:end_sample]
        if len(window_signal) < want:
            pad = np.full(want - len(window_signal), np.nan)
            window_signal = np.concatenate([window_signal, pad])

        window_time = (start_sample + np.arange(want, dtype=float)) / samples_per_second - offset
        return window_time, window_signal

    def _smart_downsample(self, time_data, signal_data, max_points=2500):
        """Peak-preserving downsample for plotting (minimum and maximum per bin)."""
        time_data = np.asarray(time_data, dtype=float).reshape(-1)
        signal_data = np.asarray(signal_data, dtype=float).reshape(-1)

        sample_count = min(len(time_data), len(signal_data))
        if sample_count <= max_points:
            return time_data[:sample_count], signal_data[:sample_count]

        time_data = time_data[:sample_count]
        signal_data = signal_data[:sample_count]

        bins = max(1, int(max_points) // 2)
        bin_size = int(np.ceil(sample_count / float(bins)))
        if bin_size <= 1:
            return time_data, signal_data

        usable_count = (sample_count // bin_size) * bin_size
        if usable_count < bin_size:
            return time_data, signal_data

        t = time_data[:usable_count].reshape(-1, bin_size)
        v = signal_data[:usable_count].reshape(-1, bin_size)
        all_nan = ~np.isfinite(v).any(axis=1)
        v_safe = np.where(np.isfinite(v), v, np.nan)
        with np.errstate(invalid="ignore"):
            i_min = np.nanargmin(np.where(all_nan[:, None], 0.0, v_safe), axis=1)
            i_max = np.nanargmax(np.where(all_nan[:, None], 0.0, v_safe), axis=1)
        rows = np.arange(v.shape[0])
        first = np.minimum(i_min, i_max)
        second = np.maximum(i_min, i_max)
        binned_time = np.column_stack([t[rows, first], t[rows, second]]).ravel()
        binned_signal = np.column_stack([v[rows, first], v[rows, second]]).ravel()
        binned_signal[np.repeat(all_nan, 2)] = np.nan

        if usable_count < sample_count:
            remainder_time = time_data[usable_count:]
            remainder_signal = signal_data[usable_count:]
            binned_time = np.concatenate([binned_time, remainder_time])
            binned_signal = np.concatenate([binned_signal, remainder_signal])

        pass
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
        # to render smoothly even for multi-hour recordings.
        if self.is_all_psg_mode():
            return self._smart_downsample(time_data, signal_data, max_points=2500)

        # While the user is dragging the timeline, prioritize immediate visual
        # feedback. The release handler redraws the final window at full detail.
        if getattr(self, "_slider_scrubbing", False) and sample_count > 2500:
            return self._smart_downsample(time_data, signal_data, max_points=2500)

        # Keep normal high-rate windows at native samples to preserve snore
        # vibration; downsample only unusually large windows.
        if sample_count > 20000 or float(time_window_seconds) >= 300:
            return self._smart_downsample(time_data, signal_data, max_points=8000)

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

    def _fill_leading_slow_channel_start(self, signal_data):
        """Fill leading SD warm-up zeros for display only.

        SpO2/Pulse use zero as an invalid sentinel.  Those startup samples
        fall outside the physiological Y-axis and make the trace look as if
        it starts late. Interior sensor-off zeros remain untouched.
        """
        signal = np.asarray(signal_data, dtype=float).reshape(-1).copy()
        if signal.size == 0:
            return signal
        valid = np.isfinite(signal) & (signal > 0.0)
        first_valid = np.flatnonzero(valid)
        if first_valid.size:
            first = int(first_valid[0])
            if first > 0:
                signal[:first] = signal[first]
        return signal

    def _bridge_slow_channel_dropouts(self, values, sample_rate_hz, max_gap_seconds=None):
        """Hold the preceding valid slow-channel value through no-signal zeros.

        SpO2/Pulse zero is a device sentinel. Once a valid value is available,
        zero/NaN runs up to ``max_gap_seconds`` are drawn as that preceding
        valid value; longer runs remain missing for the caller to show as zero.
        """
        signal = np.asarray(values, dtype=float).reshape(-1).copy()
        missing = ~np.isfinite(signal) | (signal <= 0.0)
        if not missing.any() or missing.all():
            return np.where(missing, np.nan, signal)
        signal[missing] = np.nan
        max_gap = (
            None if max_gap_seconds is None
            else int(round(float(max_gap_seconds) * float(sample_rate_hz)))
        )
        edges = np.diff(np.r_[False, missing, False].astype(np.int8))
        for start, stop in zip(
            np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
        ):
            if start > 0 and (max_gap is None or stop - start <= max_gap):
                signal[start:stop] = signal[start - 1]
        return signal

    def _spo2_display_full(self):
        """Return the cached, display-only SpO2 series for the whole recording."""
        if self.spo2_full_data is None:
            return np.array([], dtype=float)
        full_time, full_spo2 = self.spo2_full_data
        full_time = np.asarray(full_time, dtype=float).reshape(-1)
        full_spo2 = np.asarray(full_spo2, dtype=float).reshape(-1)
        full_spo2 = np.where(
            np.isfinite(full_spo2) & (full_spo2 > 100.0), 100.0, full_spo2
        )
        sample_rate_hz = self.channel_rate("spo2")
        key = (
            id(self.spo2_full_data[0]), len(full_time),
            id(self.spo2_full_data[1]), len(full_spo2),
            float(sample_rate_hz),
        )
        cached = getattr(self, "_spo2_display_cache", None)
        if cached is not None and cached[0] == key:
            return cached[1]

        # Some uploads contain a recording timeline and a Pulse channel but no
        # SpO2 column at all. That is a no-signal state, not an empty chart.
        if full_spo2.size == 0:
            missing_channel = np.zeros(full_time.size, dtype=float)
            self._spo2_display_cache = (key, missing_channel)
            return missing_channel

        bridged = self._bridge_slow_channel_dropouts(
            full_spo2,
            sample_rate_hz,
            SPO2_DISPLAY_BRIDGE_MAX_SECONDS,
        )
        # Runs longer than the bridge threshold are genuine no-signal periods
        # for display purposes and must remain visible at zero.
        bridged = np.where(np.isfinite(bridged), bridged, 0.0)
        real = np.flatnonzero(
            np.isfinite(bridged) & (bridged >= SPO2_DISPLAY_WARMUP_MIN)
        )
        if real.size:
            first = int(real[0])
            if first > 0:
                bridged[:first] = bridged[first]

        if full_time.size > bridged.size:
            bridged = np.pad(
                bridged,
                (0, full_time.size - bridged.size),
                mode="constant",
                constant_values=np.nan,
            )
        self._spo2_display_cache = (key, bridged)
        return bridged

    @staticmethod
    def _zero_where_reference_has_no_signal(
        target_values, target_times, reference_values, reference_times, reference_rate_hz
    ):
        """Force target samples to zero wherever the held reference is missing/zero."""
        target = np.asarray(target_values, dtype=float).reshape(-1).copy()
        target_time = np.asarray(target_times, dtype=float).reshape(-1)
        reference = np.asarray(reference_values, dtype=float).reshape(-1)
        reference_time = np.asarray(reference_times, dtype=float).reshape(-1)
        target_count = min(target.size, target_time.size)
        reference_count = min(reference.size, reference_time.size)
        if target_count == 0 or reference_count == 0:
            return target

        reference = reference[:reference_count]
        reference_time = reference_time[:reference_count]
        finite_time = np.isfinite(reference_time)
        reference = reference[finite_time]
        reference_time = reference_time[finite_time]
        if reference_time.size == 0:
            return target

        order = np.argsort(reference_time, kind="stable")
        reference = reference[order]
        reference_time = reference_time[order]
        lookup_time = target_time[:target_count]
        reference_index = np.searchsorted(reference_time, lookup_time, side="right") - 1
        period = 1.0 / max(float(reference_rate_hz), 1e-9)
        covered = (
            np.isfinite(lookup_time)
            & (reference_index >= 0)
            & (lookup_time < reference_time[-1] + period)
        )
        safe_index = np.clip(reference_index, 0, reference.size - 1)
        no_signal = covered & (
            ~np.isfinite(reference[safe_index]) | (reference[safe_index] <= 0.0)
        )
        target[np.flatnonzero(no_signal)] = 0.0
        return target

    def _cached_slow_display(self, key, full_values, prepare):
        """Whole-recording display array of a slow channel, built once and cached."""
        full_values = np.asarray(full_values, dtype=float)
        cache = self.__dict__.setdefault("_slow_display_cache", {})
        hit = cache.get(key)
        if hit is not None and hit[0] is full_values and hit[1] == len(full_values):
            return hit[2]
        prepared = prepare(full_values)
        cache[key] = (full_values, len(full_values), prepared)
        return prepared

    @staticmethod
    def _copy_slow_channel_for_display(signal_data):
        """Preserve native slow-channel values without display smoothing."""
        return np.asarray(signal_data, dtype=float).reshape(-1).copy()

    def _step_display_window(self, full_values, sample_rate_hz, time_window_seconds, time_offset):
        """Slow channel as exact sample-and-hold steps on the display grid."""
        full = np.asarray(full_values, dtype=float).reshape(-1)
        grid_hz = float(EXTERNAL_ARRAY_SAMPLE_RATE_HZ)
        offset = max(0.0, float(time_offset))
        first_tick = int(np.floor(offset * grid_hz + 1e-9))
        count = int(round(float(time_window_seconds) * grid_hz)) + 2
        abs_time = (first_tick + np.arange(count, dtype=float)) / grid_hz
        display_time = abs_time - offset
        source_index = np.floor(abs_time * float(sample_rate_hz) + 1e-9).astype(int)
        inside = (source_index >= 0) & (source_index < len(full))
        display_values = np.full(count, np.nan, dtype=float)
        display_values[inside] = full[source_index[inside]]
        return display_time, display_values

    def _smooth_slow_channel_for_display(self, signal_data, window=3):
        """Remove isolated 1 Hz SpO2/Pulse spikes for display only."""
        signal = np.asarray(signal_data, dtype=float).reshape(-1).copy()
        if signal.size < 3:
            return signal

        finite_idx = np.flatnonzero(np.isfinite(signal))
        if finite_idx.size == 0:
            return signal
        splits = np.where(np.diff(finite_idx) > 1)[0] + 1
        for segment in np.split(finite_idx, splits):
            if segment.size >= 3:
                signal[segment] = (
                    pd.Series(signal[segment])
                    .rolling(window=int(window), center=True, min_periods=1)
                    .median()
                    .to_numpy(dtype=float)
                )
        return signal

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
            sample_rate_hz=self.channel_rate("airflow"),
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
        floor = -float("inf") if chart_name in BIPOLAR_SIGNAL_NAMES else 0.0
        limit_min = max(min(y_min, float(default_min)) - headroom, floor)
        limit_max = max(y_max, float(default_max)) + headroom
        hard = AXIS_HARD_LIMITS.get(chart_name)
        if hard is not None:
            limit_min = max(limit_min, float(hard[0]))
            limit_max = min(limit_max, float(hard[1]))

        # Open the limits first. If the previous frame was constrained to a
        # narrower medical range (for example SpO2 35..135), setting the new
        # 0-based range before widening the limits silently clamps it back to
        # the old floor. The later setLimits call does not reapply that range.
        try:
            plot_widget.setLimits(yMin=limit_min, yMax=limit_max)
        except TypeError:
            plot_widget.setLimits(yMin=limit_min, yMax=limit_max)

        try:
            plot_widget.setYRange(y_min, y_max, padding=0)
        except TypeError:
            plot_widget.setRange(yRange=[y_min, y_max], padding=0)

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
        plot_widget.zoom_y_max_span = min(limit_max - limit_min, span * self.AXIS_MAX_ZOOM_OUT)

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
    AXIS_MAX_ZOOM_OUT = 2.5
    AXIS_FIT_PAD = 0.08
    # ---- Playback axis hold (how PSG viewers behave) -----------------------
    # Commercial PSG software keeps a channel's gain FIXED while paging or
    # scrolling; auto-scale is something that happens once (on demand, on a
    # page turn, on a jump), never continuously frame by frame. Refitting on
    # every ~50ms playback tick makes the trace "breathe" up and down even
    # though the data has not changed.
    AXIS_OFFSET_JUMP_MIN_SEC = 4.5
    AXIS_OFFSET_JUMP_MAX_SEC = 30.0
    AXIS_SHRINK_HOLD_SEC = 8.0

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

    def _pin_spo2_ticks(self, plot_widget, y_min, y_max):
        """SpO2 ticks and numbers stop at 100 % even though the view goes a little higher."""
        try:
            axis = plot_widget.getAxis('left')
        except Exception:
            return
        step = float(self._nice_axis_step(float(y_max) - float(y_min)))
        if step <= 0:
            return
        first = np.ceil(float(y_min) / step) * step
        majors = [float(v) for v in np.arange(first, 100.0 + 1e-9, step)]
        minors = [float(v) for v in np.arange(first - step / 2.0, 100.0 + 1e-9, step / 2.0)
                  if float(y_min) <= v <= 100.0 and v not in majors]
        try:
            axis.setTicks([[(v, f"{v:g}") for v in majors], [(v, "") for v in minors]])
        except Exception:
            pass

    def _pulse_strip_axis_reference(self):
        """Whole-recording Pulse exactly as the chart draws it (bridged, warm-up
        filled, zero where SpO2 has no signal), cached once per loaded file."""
        signals = (self.psg_full_data or {}).get("signals", {})
        raw = signals.get("pulse")
        if raw is None:
            return np.array([], dtype=float)
        raw = np.asarray(raw, dtype=float)
        cache = self.__dict__.setdefault("_slow_display_cache", {})
        hit = cache.get("pulse_strip_axis_ref")
        if hit is not None and hit[0] is raw and hit[1] == len(raw):
            return hit[2]
        rate = self.channel_rate("pulse")
        full = self._bridge_slow_channel_dropouts(
            raw, rate, SPO2_DISPLAY_BRIDGE_MAX_SECONDS
        )
        full = self._fill_leading_slow_channel_start(full)
        full = self._smooth_slow_channel_for_display(full)
        try:
            if self.spo2_full_data is not None:
                spo2_time, raw_spo2 = self.spo2_full_data
                if np.asarray(raw_spo2).size == 0:
                    full = np.zeros_like(full, dtype=float)
                else:
                    full = self._zero_where_reference_has_no_signal(
                        full, np.asarray(self.channel_time("pulse"), dtype=float)[: full.size],
                        self._bridge_slow_channel_dropouts(
                            raw_spo2,
                            self.channel_rate("spo2"),
                            SPO2_DISPLAY_BRIDGE_MAX_SECONDS,
                        ),
                        spo2_time,
                        self.channel_rate("spo2"),
                    )
        except Exception:
            pass
        full = np.where(np.isfinite(full), full, 0.0)
        cache["pulse_strip_axis_ref"] = (raw, len(raw), full)
        return full

    def _strip_axis_reference_values(self, chart_name, y_values):
        """Y values the SpO2 / Pulse axis is fitted to: the WHOLE recording.

        SpO2 and Pulse use a fixed clinical range whose floor/ceiling step out only
        when the DRAWN data goes past it (a 54 % dip -> floor 50, a sensor-off 0 ->
        floor 0).  Strip playback captures the charts page by page, so a page that
        contains such a dip was drawn on a different Y scale than its neighbours
        and the trace showed a vertical cut at the tile join.  Fitting these two
        charts to the whole recording gives every page one identical scale.

        It has to be the same while paused: fitting only the visible window when
        paused and the whole recording while playing made the axis jump (Pulse
        40-140 <-> 50-200) on every Play and every Pause.  Like a real PSG, the
        SpO2 / Pulse scale is now one fixed scale per recording, in every state.
        """
        try:
            name = str(chart_name).strip()
            if name == "SpO2":
                display_spo2 = self._spo2_display_full()
                full = self._cached_slow_display(
                    "spo2", display_spo2, self._copy_slow_channel_for_display)
            elif name == "Pulse":
                full = self._pulse_strip_axis_reference()
            else:
                return y_values
            full = np.asarray(full, dtype=float).reshape(-1)
            return full if np.isfinite(full).any() else y_values
        except Exception:
            return y_values

    def _apply_spo2_zero_axis_if_needed(self, plot_widget, y_values):
        """Make a zero SpO2 trace visible instead of clipping it below the axis.

        SpO2 normally uses a clinical 60-100-ish scale. When the sensor has no
        value, however, both the curve and its labels sit at y=0. Every render
        path (initial chart creation, upload refresh, playback and reset) must
        widen the axis to zero or a valid zero series looks like a blank chart.
        """
        y_values = self._strip_axis_reference_values("SpO2", y_values)
        drawn = np.asarray(y_values, dtype=float).reshape(-1)
        drawn = drawn[np.isfinite(drawn)]
        if drawn.size == 0 or float(drawn.min()) > 0.0:
            return False

        fixed_low = 0.0
        fixed_high = float(SPO2_FIXED_AXIS[1]) if SPO2_FIXED_AXIS is not None else 100.0
        if hasattr(plot_widget, "axis_properties"):
            try:
                fixed_high = max(
                    fixed_high,
                    float(plot_widget.axis_properties.get("high_value", fixed_high)),
                )
            except (TypeError, ValueError):
                pass
        fixed_high = self._view_high_with_gap(plot_widget, fixed_low, fixed_high)

        plot_widget.stable_y_range = (fixed_low, fixed_high)
        plot_widget.stable_y_range_offset = float(
            getattr(self, "current_time_offset", 0.0) or 0.0
        )
        self._lock_auto_axis(plot_widget, fixed_low, fixed_high)
        # A zero/no-signal sample needs the chart's normal range on first draw,
        # but it must not erase a range the user has manually zoomed to. Pulse
        # keeps its manual range in _apply_windowed_auto_axis_core; SpO2 reaches
        # this special zero-marker path first, so restore the same saved view.
        # A manual zoom must not hide the zero (no-signal) line below the chart.
        self._keep_spo2_zoom_inside(plot_widget, y_values)
        zoom_range = getattr(plot_widget, "zoom_y_range", None)
        if zoom_range is not None:
            zoom_low, zoom_high = (float(value) for value in zoom_range)
            try:
                plot_widget.setYRange(zoom_low, zoom_high, padding=0)
            except TypeError:
                plot_widget.setRange(yRange=[zoom_low, zoom_high], padding=0)
            self._pin_spo2_ticks(plot_widget, zoom_low, zoom_high)
        else:
            self._pin_spo2_ticks(plot_widget, fixed_low, fixed_high)
        return True

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

    # ---- SpO2 / Pulse value axis: fixed top gap, floor-step zoom ----------
    def _top_gap_px(self):
        """Pixels kept free above SpO2's 100 / Pulse's top tick."""
        if TOP_GAP_PX:
            return float(TOP_GAP_PX)
        from PyQt5.QtGui import QFont, QFontMetrics
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        return float(QFontMetrics(font).height() + 2)

    def _view_high_with_gap(self, plot_widget, low, top):
        """Return a view top with a fixed pixel gap above the requested top tick."""
        low = float(low)
        top = float(top)
        try:
            height = float(plot_widget.getViewBox().sceneBoundingRect().height())
        except Exception:
            height = 0.0
        gap = self._top_gap_px()
        if top <= low:
            return top + 1.0
        if height <= gap * 1.5:
            return top + (top - low) * 0.15
        return top + (top - low) * gap / (height - gap)

    def _spo2_view_high(self, plot_widget, low):
        return self._view_high_with_gap(plot_widget, low, 100.0)

    def _visible_curve_values(self, plot_widget):
        """Y samples of the drawn curve inside the visible X window."""
        curve = getattr(plot_widget, "plot_curve", None)
        if curve is None:
            return np.array([], dtype=float)
        try:
            x_data, y_data = curve.getData()
        except Exception:
            return np.array([], dtype=float)
        if x_data is None or y_data is None:
            return np.array([], dtype=float)
        x_values = np.asarray(x_data, dtype=float).reshape(-1)
        y_values = np.asarray(y_data, dtype=float).reshape(-1)
        n = min(len(x_values), len(y_values))
        x_values = x_values[:n]
        y_values = y_values[:n]
        try:
            x_lo, x_hi = plot_widget.getViewBox().viewRange()[0]
        except Exception:
            return y_values[np.isfinite(y_values)]
        mask = np.isfinite(x_values) & np.isfinite(y_values) & (x_values >= x_lo) & (x_values <= x_hi)
        return y_values[mask]

    def _spo2_max_floor(self, y_values):
        """Highest floor that still keeps every visible SpO2 value inside the chart."""
        values = np.asarray(y_values, dtype=float).reshape(-1)
        values = values[np.isfinite(values)]
        if values.size == 0:
            return float(SPO2_ZOOM_FLOORS[0])
        lowest = float(values.min())
        allowed = [floor for floor in SPO2_ZOOM_FLOORS if floor <= lowest - SPO2_FLOOR_MARGIN]
        return float(max(allowed)) if allowed else 0.0

    def _apply_spo2_zoom_view(self, plot_widget, low):
        low = float(low)
        high = self._spo2_view_high(plot_widget, low)
        try:
            plot_widget.setLimits(yMin=0.0, yMax=self._spo2_view_high(plot_widget, 0.0))
        except TypeError:
            pass
        self._set_y_view(plot_widget, low, high)
        plot_widget.zoom_y_range = (low, high)
        self._pin_spo2_ticks(plot_widget, low, high)

    def _keep_spo2_zoom_inside(self, plot_widget, y_values):
        """Lower the manual SpO2 floor if a new low sample would leave the chart."""
        zoom = getattr(plot_widget, "zoom_y_range", None)
        if zoom is None:
            return
        cap = self._spo2_max_floor(y_values)
        if float(zoom[0]) <= cap:
            return
        self._apply_spo2_zoom_view(plot_widget, cap)

    def _zoom_spo2_step(self, plot_widget, zoom_in):
        """Keep 100% fixed at the top and move the SpO2 floor one step."""
        floors = SPO2_ZOOM_FLOORS
        try:
            view_low = float(plot_widget.getViewBox().viewRange()[1][0])
        except Exception:
            view_low = 50.0
        index = min(range(len(floors)), key=lambda j: abs(floors[j] - view_low))
        if zoom_in:
            index = max(0, index - 1)
            cap = self._spo2_max_floor(self._visible_curve_values(plot_widget))
            while floors[index] > cap and index < len(floors) - 1:
                index += 1
        else:
            index = min(len(floors) - 1, index + 1)
        self._apply_spo2_zoom_view(plot_widget, floors[index])

    def _apply_pulse_axis(self, plot_widget, y_values):
        """Lay out Pulse like SpO2, with a fixed pixel gap above the top tick."""
        step = 20.0
        drawn = np.asarray(y_values, dtype=float).reshape(-1)
        drawn = drawn[np.isfinite(drawn)]
        if PULSE_FIXED_AXIS is not None:
            low, top = float(PULSE_FIXED_AXIS[0]), float(PULSE_FIXED_AXIS[1])
            if drawn.size:
                lowest, highest = float(drawn.min()), float(drawn.max())
                if lowest <= 0.0:
                    low = 0.0
                elif lowest - PULSE_FLOOR_MARGIN < low:
                    low = math.floor((lowest - PULSE_FLOOR_MARGIN) / step) * step
                if highest > top:
                    top = math.ceil(highest / step) * step
        elif drawn.size:
            lowest, highest = float(drawn.min()), float(drawn.max())
            low = 0.0 if lowest <= 0.0 else math.floor((lowest - PULSE_FLOOR_MARGIN) / step) * step
            top = math.ceil(highest / step) * step
        else:
            low, top = (float(value) for value in SIGNAL_Y_RANGES.get("Pulse", (40.0, 140.0)))
        low = max(0.0, float(low))
        top = max(float(top), low + 2.0 * step)
        high = self._view_high_with_gap(plot_widget, low, top)
        plot_widget.stable_y_range = (low, high)
        plot_widget.stable_y_range_offset = float(getattr(self, "current_time_offset", 0.0) or 0.0)
        try:
            view_low, view_high = plot_widget.getViewBox().viewRange()[1]
            if abs(float(view_low) - low) < 1e-6 and abs(float(view_high) - high) < 1e-6:
                return
        except Exception:
            pass
        self._lock_auto_axis(plot_widget, low, high)
        # Keep the final top-gap pixels free of tick labels.
        self._pin_core_ticks(plot_widget, low, top, self._nice_axis_step(top - low))

    def _refit_value_axis_after_resize(self, plot_widget):
        """Re-fit SpO2 / Pulse value axes after their container is resized."""
        if plot_widget is None:
            return
        name = str(getattr(plot_widget, "chart_name", "")).strip()
        if name not in ("SpO2", "Pulse") or hasattr(plot_widget, "axis_properties"):
            return
        try:
            zoom = getattr(plot_widget, "zoom_y_range", None)
            if zoom is not None:
                if name == "SpO2":
                    self._apply_spo2_zoom_view(plot_widget, float(zoom[0]))
                return
            window = self.get_effective_time_window_seconds()
            if name == "SpO2":
                _x, values = self.get_spo2_data_for_window(window, self.current_time_offset)
                if not self._apply_spo2_zero_axis_if_needed(plot_widget, values):
                    self._apply_windowed_auto_axis(plot_widget, name, values)
            else:
                _x, values = self.get_signal_data_for_window(name, window, self.current_time_offset)
                self._apply_windowed_auto_axis(plot_widget, name, values)
        except Exception:
            pass

    def _apply_dropout_axis(self, plot_widget, chart_name, y_values):
        """Keep SpO2/Pulse on the Y range declared in ACTIVE_SIGNAL_CONFIGS."""
        limit_min, limit_max = SIGNAL_Y_RANGES.get(chart_name, (0.0, 100.0))
        limit_min, limit_max = float(limit_min), float(limit_max)
        finite_values = np.asarray(y_values, dtype=float).reshape(-1)
        finite_values = finite_values[np.isfinite(finite_values)]
        has_zero_dropout = bool(
            finite_values.size and float(finite_values.min()) <= 0.0
        )
        if has_zero_dropout:
            limit_min = 0.0
        try:
            plot_widget.setLimits(yMin=limit_min, yMax=limit_max)
        except TypeError:
            plot_widget.setLimits(yMin=limit_min, yMax=limit_max)

        zoom_range = getattr(plot_widget, "zoom_y_range", None)
        if zoom_range is not None:
            y_min, y_max = float(zoom_range[0]), float(zoom_range[1])
            pass
            if has_zero_dropout and y_min > 0.0:
                y_min = limit_min
        else:
            y_min, y_max = limit_min, limit_max

        try:
            plot_widget.setYRange(y_min, y_max, padding=0)
        except TypeError:
            plot_widget.setRange(yRange=[y_min, y_max], padding=0)

    def _axis_typical_levels(self, y_values, window_seconds, offset_seconds, reference=None, reach_factor=None, ahead=None, movement_limit=None):
        """(typical_low, typical_high, normal_low, normal_high) of the visible signal, or None."""
        y = np.asarray(y_values, dtype=float).reshape(-1)
        n = int(y.size)
        window_seconds = float(window_seconds)
        if n < 16 or window_seconds <= 0.0:
            return None
        finite = np.isfinite(y)
        if int(finite.sum()) < 12:
            return None
        chunk = float(min(max(window_seconds / 10.0, 4.0), 10.0))
        if window_seconds < 3.0 * chunk:
            return None  # too short to chunk; caller falls back
        offset_seconds = float(offset_seconds)
        t = offset_seconds + np.linspace(0.0, window_seconds, n)
        expected = chunk * (n - 1) / window_seconds
        y_for_max = np.where(finite, y, -np.inf)
        y_for_min = np.where(finite, y, np.inf)
        all_max = []
        all_min = []
        env_max = []
        env_min = []
        for shift in (0.0, 0.5 * chunk):
            ids = np.floor((t - shift) / chunk + 1e-9).astype(np.int64)
            first = int(np.ceil((offset_seconds - shift) / chunk - 1e-9))
            last = int(np.floor((offset_seconds + window_seconds - shift) / chunk + 1e-9)) - 1
            starts = np.concatenate(([0], np.flatnonzero(np.diff(ids)) + 1))
            chunk_ids = ids[starts]
            counts = np.add.reduceat(finite.astype(np.int64), starts)
            maxima = np.maximum.reduceat(y_for_max, starts)
            minima = np.minimum.reduceat(y_for_min, starts)
            ok = (
                (chunk_ids >= first) & (chunk_ids <= last)
                & (counts >= 0.6 * expected)
                & np.isfinite(maxima) & np.isfinite(minima)
            )
            all_max.append(maxima[ok])
            all_min.append(minima[ok])
            # Include partly visible edge chunks so incoming large breaths widen the axis early.
            ok_edge = (
                (counts >= max(3.0, 0.08 * expected))
                & np.isfinite(maxima) & np.isfinite(minima)
            )
            env_max.append(maxima[ok_edge])
            env_min.append(minima[ok_edge])
        maxima = np.concatenate(all_max)
        minima = np.concatenate(all_min)
        edge_maxima = np.concatenate(env_max)
        edge_minima = np.concatenate(env_min)
        if ahead is not None and np.size(ahead) > 0:
            edge_maxima = np.append(edge_maxima, float(np.max(ahead)))
            edge_minima = np.append(edge_minima, float(np.min(ahead)))
        if maxima.size < 6:
            return None
        if movement_limit is not None and float(movement_limit) > 0.0:
            # Measure "typical breathing" on the calm chunks only (see
            # AXIS_MOVEMENT_AMPLITUDE_FACTOR_BY_CHART).  Too few calm chunks (the
            # whole window really is that big) -> keep the old behaviour.
            calm = (maxima - minima) <= float(movement_limit)
            if int(np.count_nonzero(calm)) >= 6:
                maxima = maxima[calm]
                minima = minima[calm]
        pct = float(AXIS_SMOOTH_TYPICAL_PCT)
        high = float(np.percentile(maxima, pct))
        low = float(np.percentile(minima, 100.0 - pct))
        if not (high > low):
            return None
        factor = float(AXIS_SMOOTH_NORMAL_REACH if reach_factor is None else reach_factor)
        fence_amplitude = high - low
        if reference is not None and float(reference) > fence_amplitude:
            fence_amplitude = float(reference)
        reach = factor * fence_amplitude
        upper = edge_maxima[edge_maxima <= high + reach]
        lower = edge_minima[edge_minima >= low - reach]
        high_normal = float(max(high, upper.max())) if upper.size else high
        low_normal = float(min(low, lower.min())) if lower.size else low
        return low, high, low_normal, high_normal

    def _axis_lookahead_values(self, chart_name, window_seconds, offset_seconds):
        """The samples just beyond the right edge of the window, or None."""
        seconds = float(AXIS_SMOOTH_LOOKAHEAD_SEC)
        if seconds <= 0.0 or str(chart_name).strip() not in AXIS_SMOOTH_NORMAL_REACH_BY_CHART:
            return None
        try:
            if self.is_all_psg_mode():
                return None
            speed = float(getattr(self, "playback_speed", 1.0) or 1.0)
            seconds = min(seconds * max(1.0, speed), 30.0)
            full = np.asarray(self._get_full_signal_for_auto_range(chart_name), dtype=float).reshape(-1)
            rate = float(self.channel_rate(chart_name))
        except Exception:
            return None
        if full.size == 0 or not np.isfinite(rate) or rate <= 0.0:
            return None
        start = int((float(offset_seconds) + float(window_seconds)) * rate)
        end = min(int(full.size), start + int(seconds * rate) + 1)
        if start < 0 or end - start < 3:
            return None
        segment = full[start:end]
        segment = segment[np.isfinite(segment)]
        return segment if segment.size >= 3 else None

    def _axis_smooth_target(self, y_values, chart_name, window_seconds, offset_seconds, reference=None, ahead=None):
        """Return the ideal (centre, half_span, typical_amplitude), or None for a flat/empty window."""
        reach_factor = AXIS_SMOOTH_NORMAL_REACH_BY_CHART.get(
            str(chart_name).strip(), AXIS_SMOOTH_NORMAL_REACH,
        )
        if str(chart_name).strip() not in AXIS_SMOOTH_NORMAL_REACH_BY_CHART:
            reference = None
        movement_limit = None
        recording_amplitude = None
        movement_factor = AXIS_MOVEMENT_AMPLITUDE_FACTOR_BY_CHART.get(str(chart_name).strip())
        if movement_factor:
            recording_amplitude = self._axis_reference_amplitude(chart_name)
            if recording_amplitude:
                movement_limit = float(movement_factor) * float(recording_amplitude)
        levels = self._axis_typical_levels(
            y_values, window_seconds, offset_seconds, reference, reach_factor, ahead,
            movement_limit,
        )
        if levels is not None:
            low, high, low_normal, high_normal = levels
            if movement_factor and (high_normal - low_normal) > 4.0 * max(high - low, 1e-9):
                self._log_axis_widened(
                    chart_name, high - low, high_normal - low_normal,
                    recording_amplitude, movement_limit,
                )
            amplitude = high - low
            centre = (high_normal + low_normal) / 2.0
            core_half = 0.5 * (high_normal - low_normal) + float(AXIS_SMOOTH_MARGIN) * amplitude
            band = self._axis_band_fraction()
            half = core_half / (1.0 - 2.0 * band)
            typical_amplitude = float(amplitude)
        else:
            typical_amplitude = None
            # Short window or too few chunks: use the classic trimmed fit.
            series = np.asarray(y_values, dtype=float).reshape(-1)
            series = series[np.isfinite(series)]
            if series.size < 8 or float(series.max()) <= float(series.min()):
                return None
            fallback_min, fallback_max = SIGNAL_Y_RANGES.get(chart_name, (0.0, 100.0))
            raw_min, raw_max = self._windowed_axis_range_from_values(
                series, fallback_min, fallback_max,
            )
            centre = (float(raw_max) + float(raw_min)) / 2.0
            half = (float(raw_max) - float(raw_min)) / 2.0
            # the classic fit is padded by ~8% on each side
            typical_amplitude = 2.0 * half / 1.16
        half = max(float(half), float(AXIS_SMOOTH_MIN_HALF))
        return float(centre), half, typical_amplitude

    @staticmethod
    def _axis_band_fraction():
        """Height of one compress band (0 when the compress display is off)."""
        if str(AXIS_SMOOTH_OVERFLOW) == "compress":
            return min(max(float(AXIS_SMOOTH_BAND), 0.0), 0.4)
        return 0.0

    def _axis_half_for_amplitude(self, amplitude):
        """View half-span that suits normal breathing of the given typical amplitude."""
        band = self._axis_band_fraction()
        core_half = (0.65 + float(AXIS_SMOOTH_MARGIN)) * float(amplitude)
        return max(core_half / (1.0 - 2.0 * band), float(AXIS_SMOOTH_MIN_HALF))

    def _axis_reference_amplitude(self, chart_name):
        """Typical breathing amplitude of the whole recording (cached), or None."""
        try:
            full = np.asarray(self._get_full_signal_for_auto_range(chart_name), dtype=float).reshape(-1)
            rate = float(self.channel_rate(chart_name))
        except Exception:
            return None
        if full.size < 200 or not np.isfinite(rate) or rate <= 0.0:
            return None
        cache = self.__dict__.setdefault("_axis_reference_cache", {})
        fingerprint = (
            str(chart_name), int(full.size),
            float(np.nansum(full[:: max(1, full.size // 64)])),
        )
        if fingerprint in cache:
            return cache[fingerprint]
        levels = self._axis_typical_levels(full, full.size / rate, 0.0)
        value = float(levels[1] - levels[0]) if levels is not None else None
        if value is not None and not value > 0.0:
            value = None
        for stale in [key for key in cache if key[0] == fingerprint[0]]:
            del cache[stale]
        cache[fingerprint] = value
        return value

    @staticmethod
    def _axis_smooth_step(state, centre_target, half_target, now):
        """Ease the shown axis (state) toward the target."""
        dt = min(max(float(now) - float(state["t"]), 0.0), 30.0)
        centre = float(state["c"])
        half = float(state["h"])

        # Half-span: quick to zoom out, slow to zoom in, with a start/stop latch.
        ratio = half_target / half
        if state["h_moving"]:
            if 0.93 <= ratio <= 1.07:
                state["h_moving"] = False
        elif ratio > 1.20 or ratio < 0.80:
            state["h_moving"] = True
        if state["h_moving"]:
            tau = AXIS_SMOOTH_ZOOM_OUT_SEC if half_target > half else AXIS_SMOOTH_ZOOM_IN_SEC
            alpha = 1.0 - math.exp(-dt / max(float(tau), 1e-3))
            half = math.exp(math.log(half) + alpha * (math.log(half_target) - math.log(half)))

        # Centre (baseline drift).
        offset = (centre_target - centre) / half
        if state["c_moving"]:
            if abs(offset) < 0.06:
                state["c_moving"] = False
        elif abs(offset) > 0.22:
            state["c_moving"] = True
        if state["c_moving"]:
            alpha = 1.0 - math.exp(-dt / max(float(AXIS_SMOOTH_SHIFT_SEC), 1e-3))
            centre += alpha * (centre_target - centre)

        state["c"] = centre
        state["h"] = half
        state["t"] = float(now)

    @staticmethod
    def _compress_knee(reach):
        """Knee width W so that the log compression has slope 1 where it starts."""
        reach = max(float(reach), 2.0)
        low, high = 1e-6, reach
        for _ in range(60):
            mid = 0.5 * (low + high)
            if mid * math.log1p(reach / mid) < 1.0:
                low = mid
            else:
                high = mid
        return 0.5 * (low + high)

    def _pin_core_ticks(self, plot_widget, core_low, core_high, step):
        """Y ticks only inside the linear part (the compress bands have no labels)."""
        try:
            axis = plot_widget.getAxis('left')
        except Exception:
            return
        if str(getattr(plot_widget, "chart_name", "")).strip() in HIDDEN_Y_AXIS_VALUE_CHARTS:
            axis.setStyle(showValues=False, tickLength=0)
            axis.setTicks([[]])
            plot_widget._core_ticks_active = False
            return
        step = float(step)
        if step <= 0.0:
            return
        first = np.ceil(core_low / step - 1e-9) * step
        majors = [float(v) for v in np.arange(first, core_high + 1e-9, step)]
        half = step / 2.0
        first_minor = np.ceil(core_low / half - 1e-9) * half
        minors = [
            float(v) for v in np.arange(first_minor, core_high + 1e-9, half)
            if all(abs(v - m) > half * 0.25 for m in majors)
        ]
        if not majors:
            return
        try:
            axis.setTicks([[(v, f"{v:g}") for v in majors], [(v, "") for v in minors]])
            plot_widget._core_ticks_active = True
        except Exception:
            pass

    def _release_core_ticks(self, plot_widget):
        """Give the axis back its automatic ticks (used when the user zooms by hand)."""
        if getattr(plot_widget, "_core_ticks_active", False):
            try:
                axis = plot_widget.getAxis('left')
                if str(getattr(plot_widget, "chart_name", "")).strip() in HIDDEN_Y_AXIS_VALUE_CHARTS:
                    axis.setStyle(showValues=False, tickLength=0)
                    axis.setTicks([[]])
                else:
                    axis.setTicks(None)
            except Exception:
                pass
            plot_widget._core_ticks_active = False

    def _apply_axis_overflow(self, plot_widget, y_min, y_max, core_low, core_high, mode):
        """Redraw the trace so a big movement stays visible instead of running off the chart."""
        curve = getattr(plot_widget, "plot_curve", None)
        if curve is None:
            return
        x = getattr(curve, "xData", None)
        y = getattr(curve, "yData", None)
        if x is None or y is None:
            return
        y = np.asarray(y, dtype=float)
        if y.size == 0:
            return
        finite = np.isfinite(y)
        span = float(y_max) - float(y_min)
        if mode == "edge":
            inset = 0.012 * span
            over = finite & ((y > y_max - inset) | (y < y_min + inset))
            if not over.any():
                return
            drawn = np.clip(y, y_min + inset, y_max - inset)
        else:
            over_high = finite & (y > core_high)
            over_low = finite & (y < core_low)
            if not (over_high.any() or over_low.any()):
                return
            band = float(core_low) - float(y_min)
            if band <= 0.0:
                return
            reach = float(AXIS_SMOOTH_COMPRESS_RANGE)
            knee = self._compress_knee(reach)
            norm = math.log1p(reach / knee)
            drawn = y.copy()
            u = (y[over_high] - core_high) / band
            drawn[over_high] = core_high + band * 0.97 * np.minimum(np.log1p(u / knee) / norm, 1.0)
            u = (core_low - y[over_low]) / band
            drawn[over_low] = core_low - band * 0.97 * np.minimum(np.log1p(u / knee) / norm, 1.0)
        try:
            curve.setData(x, drawn, connect='finite')
        except Exception:
            pass

    def _apply_smooth_auto_axis(self, plot_widget, chart_name, y_values):
        """Smooth, artifact-proof auto-scale. Returns False if it could not run."""
        hold_map = self._axis_hold_map()
        state = hold_map.get(chart_name)
        now = time.monotonic()
        try:
            current_offset = float(getattr(self, "current_time_offset", 0.0) or 0.0)
        except (TypeError, ValueError):
            current_offset = 0.0
        try:
            window_seconds = float(self.get_effective_time_window_seconds())
        except Exception:
            window_seconds = float(getattr(self, "current_time_window", 60.0) or 60.0)

        jump_threshold = max(
            self.AXIS_OFFSET_JUMP_MIN_SEC,
            min(window_seconds * 0.5, self.AXIS_OFFSET_JUMP_MAX_SEC),
        )
        if state is not None and (
            state.get("kind") != "smooth"
            or abs(current_offset - float(state["offset"])) > jump_threshold
        ):
            state = None  # seek / new window: fit straight away, no easing

        # Typical breathing amplitude of this recording controls the Airflow fence and gain hold.
        reference = state.get("amp_ref") if state is not None else None
        if reference is None:
            reference = self._axis_reference_amplitude(chart_name)
        ahead = self._axis_lookahead_values(chart_name, window_seconds, current_offset)
        target = self._axis_smooth_target(
            y_values, chart_name, window_seconds, current_offset, reference, ahead,
        )

        # Gain hold: a flat / dead window must not make the axis zoom in on noise.
        amplitude = target[2] if target is not None else None
        # No target at all = the window is flat or empty: nothing to measure = dead.
        dead_window = target is None
        hold = False
        if amplitude is not None or dead_window:
            if reference is not None and reference > 0.0:
                share = 0.0 if dead_window else amplitude / reference
                if share < float(AXIS_SMOOTH_FLAT_FRACTION):
                    since = state.get("flat_since") if state is not None else None
                    if since is None:
                        since = current_offset
                    if state is not None:
                        state["flat_since"] = since
                    weak_but_alive = share >= float(AXIS_SMOOTH_DEAD_FRACTION)
                    long_enough = (current_offset - since) >= float(AXIS_SMOOTH_FLAT_HOLD_SEC)
                    hold = not (weak_but_alive and long_enough)
                elif state is not None:
                    state.pop("flat_since", None)

        if state is None:
            if hold:
                # No axis yet (first fit / seek into a flat stretch): use the typical
                # scale of the recording, centred on the level the signal sits at.
                series = np.asarray(y_values, dtype=float).reshape(-1)
                series = series[np.isfinite(series)]
                if series.size:
                    centre = float(np.median(series))
                    half = self._axis_half_for_amplitude(reference)
                    if target is not None and target[1] > half:
                        # Larger breaths in the window must remain visible.
                        centre, half = target[0], target[1]
                    target = (centre, half, None)
            if target is None:
                return False
            state = {
                "kind": "smooth", "c": target[0], "h": target[1], "t": now,
                "offset": current_offset, "h_moving": False, "c_moving": False,
                "step": None, "applied": None,
                "amp_ref": reference if hold else amplitude,
            }
            if hold:
                state["flat_since"] = current_offset
        else:
            if target is not None and hold and target[1] > float(state["h"]):
                pass        # larger breathing than the held scale: zoom out to it (never in)
            elif target is None or hold:
                target = (state["c"], state["h"])       # keep the scale exactly as it is
            elif amplitude is not None:
                # Follow real changes of the breathing amplitude, slowly.
                old_reference = float(state.get("amp_ref") or amplitude)
                elapsed = min(abs(current_offset - float(state["offset"])), 600.0)
                follow = 1.0 - math.exp(-elapsed / max(float(AXIS_SMOOTH_REFERENCE_SEC), 1e-3))
                state["amp_ref"] = old_reference + follow * (amplitude - old_reference)
            self._axis_smooth_step(state, target[0], target[1], now)
            state["offset"] = current_offset
        hold_map[chart_name] = state

        y_min = float(state["c"]) - float(state["h"])
        y_max = float(state["c"]) + float(state["h"])
        span = y_max - y_min
        applied = state.get("applied")
        needs_apply = applied is None
        if not needs_apply:
            tolerance = span * 0.002  # ~0.2% of the height is well under a pixel
            needs_apply = (
                abs(y_min - applied[0]) > tolerance or abs(y_max - applied[1]) > tolerance
            )
            if not needs_apply:
                try:
                    view_low, view_high = plot_widget.getViewBox().viewRange()[1]
                    needs_apply = (
                        abs(float(view_low) - applied[0]) > span * 0.01
                        or abs(float(view_high) - applied[1]) > span * 0.01
                    )
                except Exception:
                    pass
        overflow_mode = str(AXIS_SMOOTH_OVERFLOW)
        band_fraction = float(AXIS_SMOOTH_BAND) if overflow_mode == "compress" else 0.0
        core_low = y_min + band_fraction * span
        core_high = y_max - band_fraction * span
        if needs_apply:
            self._lock_auto_axis(plot_widget, y_min, y_max)
            # Gridline spacing only changes when the span moved well away from
            # what the current spacing suits (no flipping between refreshes).
            core_span = core_high - core_low
            step_now = self._nice_axis_step(core_span)
            previous = state.get("step")
            step_changed = previous is None or (
                step_now != previous and not (2.5 <= core_span / previous <= 9.0)
            )
            if step_changed:
                state["step"] = step_now
            if band_fraction > 0.0:
                self._pin_core_ticks(plot_widget, core_low, core_high, state["step"])
            elif step_changed:
                self._pin_axis_tick_spacing(plot_widget, y_min, y_max)
            state["applied"] = (y_min, y_max)
        plot_widget.stable_y_range = (y_min, y_max)
        plot_widget.stable_y_range_offset = current_offset
        if overflow_mode in ("compress", "edge"):
            self._apply_axis_overflow(
                plot_widget, y_min, y_max, core_low, core_high, overflow_mode,
            )
        return True

    def _apply_windowed_auto_axis(self, plot_widget, chart_name, y_values):
        """Autoscale Airflow/Thorax to the visible data and preserve manual zoom."""
        self._apply_windowed_auto_axis_core(plot_widget, chart_name, y_values)
        if chart_name in AXIS_SMOOTH_CHARTS:
            self._extend_zoom_out_to_window(plot_widget, y_values)

    def _extend_zoom_out_to_window(self, plot_widget, y_values):
        """Let the "-" button zoom out far enough to bring the WHOLE window into view.

        _lock_auto_axis() caps zoom-out at AXIS_MAX_ZOOM_OUT (2.5) x the auto-fit
        span so a chart cannot be blown up until it looks flat.  A body movement is
        ~10x the breathing, so with that cap "-" could never bring it into the frame:
        it stayed cut at the top however often "-" was pressed.  Fixed gain stays the
        default (breathing big, movement cut); only the zoom-out LIMIT is raised to the
        farthest sample of the visible window from the zoom centre (+15 % air).
        "-" then shrinks everything proportionally until the movement fits, and "R"
        returns to the fitted view.
        """
        try:
            low = getattr(plot_widget, "original_y_min", None)
            high = getattr(plot_widget, "original_y_max", None)
            limit_low = getattr(plot_widget, "zoom_y_min_limit", None)
            limit_high = getattr(plot_widget, "zoom_y_max_limit", None)
            if None in (low, high, limit_low, limit_high):
                return
            values = np.asarray(y_values, dtype=float).reshape(-1)
            values = values[np.isfinite(values)]
            if values.size == 0:
                return
            default_cap = (float(high) - float(low)) * float(self.AXIS_MAX_ZOOM_OUT)
            # zoom_vertical() zooms around the median of the drawn trace, so the view
            # must reach the sample FARTHEST from that median on either side.
            centre = float(np.median(values))
            reach = max(float(values.max()) - centre, centre - float(values.min()))
            needed = 2.0 * reach * 1.15
            plot_widget.zoom_y_max_span = float(
                min(max(default_cap, needed), float(limit_high) - float(limit_low))
            )
        except Exception:
            pass

    def _apply_windowed_auto_axis_core(self, plot_widget, chart_name, y_values):
        """Original body of _apply_windowed_auto_axis (see the wrapper above)."""
        if hasattr(plot_widget, "axis_properties"):
            return
        # Strip playback: one identical SpO2 / Pulse scale for every captured page.
        y_values = self._strip_axis_reference_values(chart_name, y_values)

        zoom_y_range = getattr(plot_widget, "zoom_y_range", None)
        if zoom_y_range is not None:
            if chart_name == "SpO2":
                self._keep_spo2_zoom_inside(plot_widget, y_values)
            self._release_core_ticks(plot_widget)
            return

        # Use the fixed top gap and bottom anchored labels for Pulse before the
        # generic auto-fit can center the signal with matching top and bottom room.
        if chart_name == "Pulse":
            self._apply_pulse_axis(plot_widget, y_values)
            return

        if chart_name == "Snoring" and SNORING_FIXED_AXIS_FROM_RECORDING:
            fixed = self._snoring_recording_axis()
            if fixed is not None:
                y_min, y_max = fixed
                plot_widget.stable_y_range = (y_min, y_max)
                plot_widget.stable_y_range_offset = float(
                    getattr(self, "current_time_offset", 0.0) or 0.0
                )
                try:
                    view_low, view_high = plot_widget.getViewBox().viewRange()[1]
                    tolerance = max(y_max - y_min, 1e-9) * 1e-3
                    if abs(float(view_low) - y_min) <= tolerance and abs(float(view_high) - y_max) <= tolerance:
                        return
                except Exception:
                    pass
                self._lock_auto_axis(plot_widget, y_min, y_max)
                self._pin_axis_tick_spacing(plot_widget, y_min, y_max)
                return

        # Paused after a Play: keep the gain of the Play (see _remember_play_scale_for_pause).
        if chart_name in AXIS_SMOOTH_CHARTS and not self.__dict__.get("_strip_force_axis_fit", False):
            held_range = self._pause_hold_range(chart_name)
            if held_range is not None:
                y_min, y_max = (float(value) for value in held_range)
                plot_widget.stable_y_range = (y_min, y_max)
                plot_widget.stable_y_range_offset = float(
                    getattr(self, "current_time_offset", 0.0) or 0.0
                )
                self._lock_auto_axis(plot_widget, y_min, y_max)
                self._pin_axis_tick_spacing(plot_widget, y_min, y_max)
                return

        # A strip page is captured immediately after refresh_charts().  Changing
        # the ViewBox to this page's auto-fit and restoring the shared range only
        # after the refresh is too late: Qt can grab the already-scheduled scene
        # transform, so adjacent tiles encode the same boundary sample several
        # pixels apart. Apply the Play-start waveform range here, before the curve
        # is rendered, so every captured page has one identical data-to-pixel map.
        if (
            chart_name in ("Airflow", "Thorax", "Snoring")
            and self.__dict__.get("_strip_force_axis_fit", False)
        ):
            strip_range = self.__dict__.get("_strip_y_held", {}).get(chart_name)
            if strip_range is not None:
                y_min, y_max = (float(value) for value in strip_range)
                if y_max > y_min:
                    plot_widget.stable_y_range = (y_min, y_max)
                    plot_widget.stable_y_range_offset = float(
                        getattr(self, "current_time_offset", 0.0) or 0.0
                    )
                    self._lock_auto_axis(plot_widget, y_min, y_max)
                    self._pin_axis_tick_spacing(plot_widget, y_min, y_max)
                    return

        if AXIS_SMOOTH_ENABLED and not CLASSIC_PLOT_LOGIC and chart_name in AXIS_SMOOTH_CHARTS:
            if self._apply_smooth_auto_axis(plot_widget, chart_name, y_values):
                return

        if chart_name == "SpO2" and SPO2_FIXED_AXIS is not None:
            fixed_low, fixed_high = float(SPO2_FIXED_AXIS[0]), float(SPO2_FIXED_AXIS[1])
            drawn = np.asarray(y_values, dtype=float).reshape(-1)
            drawn = drawn[np.isfinite(drawn)]
            if drawn.size and float(drawn.min()) < fixed_low:
                lowest = float(drawn.min())
                # Step the floor down in 10s (68 -> 60, 21 -> 20); a recorded 0 goes to 0.
                fixed_low = max(float(SPO2_ARTIFACT_FLOOR), np.floor(lowest / 10.0) * 10.0) if lowest > 0 else float(SPO2_ARTIFACT_FLOOR)
                fixed_low = min(fixed_low, float(SPO2_FIXED_AXIS[0]))
            # Fixed pixel gap above 100 (room for the value numbers).
            fixed_high = self._view_high_with_gap(plot_widget, fixed_low, fixed_high)
            plot_widget.stable_y_range = (fixed_low, fixed_high)
            plot_widget.stable_y_range_offset = float(getattr(self, "current_time_offset", 0.0) or 0.0)
            try:
                view_low, view_high = plot_widget.getViewBox().viewRange()[1]
                if abs(float(view_low) - fixed_low) < 1e-6 and abs(float(view_high) - fixed_high) < 1e-6:
                    return
            except Exception:
                pass
            self._lock_auto_axis(plot_widget, fixed_low, fixed_high)
            self._pin_spo2_ticks(plot_widget, fixed_low, fixed_high)
            return

        hold_map = self._axis_hold_map()
        hold = hold_map.get(chart_name)
        try:
            current_offset = float(getattr(self, "current_time_offset", 0.0) or 0.0)
        except (TypeError, ValueError):
            current_offset = 0.0
        try:
            window_seconds = float(self.get_effective_time_window_seconds())
        except Exception:
            window_seconds = float(getattr(self, "current_time_window", 60.0) or 60.0)
        jump_threshold = max(
            self.AXIS_OFFSET_JUMP_MIN_SEC,
            min(window_seconds * 0.5, self.AXIS_OFFSET_JUMP_MAX_SEC),
        )
        if hold is not None and abs(current_offset - float(hold["offset"])) > jump_threshold:
            hold = None
        if chart_name in AXIS_ALWAYS_REFIT:
            hold = None

        fallback_min, fallback_max = SIGNAL_Y_RANGES.get(chart_name, (0.0, 100.0))
        finite_values = np.asarray(y_values, dtype=float).reshape(-1)
        finite_values = finite_values[np.isfinite(finite_values)]
        min_span = AXIS_MIN_SPAN.get(chart_name)
        if min_span and finite_values.size and float(finite_values.min()) == float(finite_values.max()):
            raw_min = raw_max = float(finite_values[0])
        else:
            raw_min, raw_max = self._windowed_axis_range_from_values(
                y_values, fallback_min, fallback_max,
            )
        if min_span:
            span = float(raw_max) - float(raw_min)
            if span < float(min_span):
                centre = (float(raw_max) + float(raw_min)) / 2.0
                raw_min = centre - float(min_span) / 2.0
                raw_max = centre + float(min_span) / 2.0
        if chart_name in BIPOLAR_SIGNAL_NAMES:
            magnitude = max(abs(float(raw_min)), abs(float(raw_max)))
            raw_min, raw_max = -magnitude, magnitude
        top_headroom = AXIS_TOP_HEADROOM.get(chart_name)
        if top_headroom:
            raw_max = float(raw_max) + (float(raw_max) - float(raw_min)) * float(top_headroom)
        pad = max((float(raw_max) - float(raw_min)) * self.AXIS_BREATHING_PAD, 1e-9)
        target = self._quantize_axis_range(raw_min - pad, raw_max + pad)
        ceiling = AXIS_TOP_CEILING.get(chart_name)
        if ceiling is not None and target[1] > ceiling:
            target = (target[0], float(ceiling))
        hard = AXIS_HARD_LIMITS.get(chart_name)
        if hard is not None:
            low, high = float(target[0]), float(target[1])
            if high > hard[1]:
                low, high = low - (high - hard[1]), hard[1]
            if low < hard[0]:
                low, high = hard[0], min(hard[1], high + (hard[0] - low))
            target = (round(low, 6), round(high, 6))
        now = time.monotonic()
        if hold is None:
            new_range = target
            shrink_since = None
            decision = "fit"
        else:
            held = (float(hold["y_min"]), float(hold["y_max"]))
            held_span = held[1] - held[0]
            if target[0] < held[0] or target[1] > held[1]:
                grow_low = min(target[0], held[0])
                grow_high = max(target[1], held[1])
                grow_pad = (grow_high - grow_low) * self.AXIS_FIT_PAD
                if target[0] < held[0]:
                    grow_low -= grow_pad
                if target[1] > held[1]:
                    grow_high += grow_pad
                new_range = self._quantize_axis_range(grow_low, grow_high)
                shrink_since = None
                decision = "grow"
            elif (target[1] - target[0]) < held_span * self.AXIS_SHRINK_THRESHOLD:
                shrink_since = hold.get("shrink_since") or now
                if now - shrink_since >= self.AXIS_SHRINK_HOLD_SEC:
                    new_range = target
                    shrink_since = None
                    decision = "shrink"
                else:
                    new_range = held
                    decision = "hold"
            else:
                new_range = held
                shrink_since = None
                decision = "hold"

        hold_map[chart_name] = {
            "y_min": float(new_range[0]),
            "y_max": float(new_range[1]),
            "offset": current_offset,
            "shrink_since": shrink_since,
        }
        y_min, y_max = float(new_range[0]), float(new_range[1])
        plot_widget.stable_y_range = (y_min, y_max)
        plot_widget.stable_y_range_offset = current_offset
        try:
            view_low, view_high = plot_widget.getViewBox().viewRange()[1]
            tolerance = max(y_max - y_min, 1e-9) * 1e-3
            if abs(float(view_low) - y_min) <= tolerance and abs(float(view_high) - y_max) <= tolerance:
                return
        except Exception:
            pass
        if chart_name in ("Thorax", "Airflow"):
            pass
        self._lock_auto_axis(plot_widget, y_min, y_max)
        self._pin_axis_tick_spacing(plot_widget, y_min, y_max)

    def _snoring_recording_axis(self):
        """One Y range for the Snoring chart, from the WHOLE recording (cached).

        Centred on the silent baseline, half-height = a high percentile of the
        snore-packet amplitudes. Returns (y_min, y_max) or None.
        """
        full = self._get_full_signal_for_auto_range("Snoring")
        key = (str(getattr(self, "loaded_recording_path", "") or ""), int(len(full)),
               float(SNORING_AXIS_PERCENTILE), float(SNORING_AXIS_GAIN))
        cache = self.__dict__.get("_snoring_axis_cache")
        if cache is not None and cache[0] == key:
            return cache[1]

        result = None
        values = np.asarray(full, dtype=float).reshape(-1)
        values = values[np.isfinite(values)]
        if values.size:
            baseline = float(np.median(values))
            deviation = np.abs(values - baseline)
            peak = float(deviation.max())
            if peak > 0.0:
                # Only samples that belong to snore packets, not the silence.
                active = deviation[deviation > 0.05 * peak]
                if active.size >= 50:
                    amplitude = float(np.percentile(active, float(SNORING_AXIS_PERCENTILE)))
                else:
                    amplitude = peak
                gain = float(SNORING_AXIS_GAIN) if float(SNORING_AXIS_GAIN) > 0 else 1.0
                half = max(amplitude * 1.10 / gain, 1e-6)
                result = (baseline - half, baseline + half)
        self._snoring_axis_cache = (key, result)
        if result is not None:
            pass
        return result

    def _axis_hold_map(self):
        """Per-chart held auto-axis ranges (created lazily)."""
        hold_map = getattr(self, "_axis_hold", None)
        if hold_map is None:
            hold_map = {}
            self._axis_hold = hold_map
        return hold_map

    def _clear_axis_hold(self, chart_name=None):
        """Forget held auto-axis ranges so the next redraw re-fits from scratch."""
        hold_map = self._axis_hold_map()
        if chart_name is None:
            hold_map.clear()
        else:
            hold_map.pop(str(chart_name).strip(), None)

    def get_signal_auto_axis_range(self, chart_name):
        """Return the data-driven default Y-axis range for a chart."""
        name = str(chart_name).strip()

        # Before data loads, show the mapping-based range instead of hardcoded
        # 0-100. That keeps startup charts aligned with the configured scale.
        if self.psg_full_data is None or "signals" not in self.psg_full_data:
            return SIGNAL_Y_RANGES.get(name, (0.0, 100.0))

        if name in AUTO_RANGE_SIGNAL_NAMES:
            if self.psg_full_data is None or "signals" not in self.psg_full_data:
                return SIGNAL_Y_RANGES.get(name, (0.0, 100.0))

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
        pass

        
    def load_psg_data(self, recording_path, defer_extras=False):
        """Reload the chart from the provided binary PSG recording.

        defer_extras=True (used by load_psg_data_and_detect): sleep metrics are
        computed in a background thread and the provisional threshold events
        are skipped, because the detector result replaces them anyway.
        """
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
            previous_recording_path = getattr(self, "loaded_recording_path", None)
            is_different_file = (
                previous_recording_path is not None
                and str(recording_path) != str(previous_recording_path)
            )
            if is_different_file:
                self.dynamic_selections = {}
                self.selection_labels = {}

            self.current_time_offset = 0
            self.auto_focus_applied = False
            self._clear_auto_detected_selections()

            time_data, signals, channel_times, channel_rates, source_format = (
                self._load_uploaded_signals_with_spinner(recording_path)
            )
            if len(time_data) == 0 or not signals:
                raise ValueError("Uploaded PSG data could not be loaded.")

            self.psg_full_data = {
                "time": time_data, "signals": signals, "times": channel_times,
                "sample_rates": channel_rates,
                "master_channel": "airflow" if "airflow" in channel_times else "timestamp",
                "source_format": source_format,
            }
            self.current_psg_data = self.psg_full_data
            self.spo2_full_data = (
                np.asarray(channel_times.get("spo2", time_data), dtype=float),
                np.asarray(
                    signals.get("spo2_display", signals.get("spo2", [])),
                    dtype=float,
                ),
            )
            self.loaded_recording_path = str(recording_path)
            self.current_recording_path = str(recording_path)
            # A fresh load resets session tracking; if this recording came from a
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
            self.sensor_off_shade_segments = []
            self.last_detection_error = None
            self._invalidate_signal_caches()
            # Different recording, different amplitude - start the axis fresh.
            self._clear_axis_hold()
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
                plot_widget.stable_y_range_offset = None
            enhanced_airflow = signals.get("airflow_enhanced", signals.get("airflow", []))
            sleep_mask = None
            for mask_key in ("sleep_mask", "sleep_staging", "staging_mask", "staging", "sleep_stage_mask"):
                if mask_key in signals and signals[mask_key] is not None:
                    sleep_mask = signals[mask_key]
                    break
            if AIRFLOW_DEBUG_REPORT_ON_UPLOAD:
                self.save_airflow_smoothing_debug_report(
                    recording_path=recording_path,
                    raw_airflow=signals.get("airflow_raw", signals.get("airflow", [])),
                    enhanced_airflow=enhanced_airflow,
                )
            self.analysis_results = None
            self.analysis_json_path = None
            if defer_extras:
                self._start_metrics_worker(
                    recording_path, time_data, signals, sleep_mask, channel_rates, channel_times,
                )
            else:
                self._compute_metrics_now(
                    recording_path, time_data, signals, sleep_mask, channel_rates, channel_times,
                )

            if defer_extras and self._detection_running:
                # Detector (already running in background) supplies the real
                # events; these provisional lists were two full passes over
                # the airflow signal on the GUI thread.
                self.airflow_detected_events = []
            else:
                self.airflow_detected_events = self._compute_fallback_navigation_events()
            self.current_window_airflow_events = []
            self.emit_detected_events_panel()
            self.update_detection_summary_label()
            pass
            pass
            return time_data, signals
            
        except Exception as e:
            pass
            import traceback
            traceback.print_exc()
            # Return empty data if loading fails
            self._invalidate_signal_caches()
            self.psg_full_data = None
            self.current_psg_data = None
            self.spo2_full_data = (np.array([]), np.array([]))
            self.loaded_recording_path = None
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

    def _compute_metrics_now(self, recording_path, time_data, signals, sleep_mask,
                             channel_rates, channel_times):
        """Original synchronous metrics path (kept for callers of load_psg_data)."""
        try:
            try:
                self.analysis_results = calculate_sleep_metrics(
                    time_data, signals, sleep_mask=sleep_mask,
                    sample_rate_hz=self.master_rate(),
                    sample_rates=channel_rates, channel_times=channel_times,
                )
            except TypeError:
                self.analysis_results = calculate_sleep_metrics(
                    time_data, signals, sleep_mask=sleep_mask,
                    sample_rate_hz=self.master_rate(),
                )
            self.analysis_json_path = save_sleep_metrics_json(
                self.analysis_results,
                source_recording=recording_path,
            )
            pass
        except Exception as analysis_error:
            self.analysis_results = None
            self.analysis_json_path = None
            pass

    def _start_metrics_worker(self, recording_path, time_data, signals, sleep_mask,
                              channel_rates, channel_times):
        worker = self._MetricsWorker(
            recording_path, time_data, signals, sleep_mask, self.master_rate(),
            channel_rates, channel_times, parent=self,
        )
        worker.done.connect(self._on_metrics_done)
        worker.failed.connect(self._on_metrics_failed)
        self._metrics_worker = worker
        worker.start()

    def _on_metrics_done(self, results, json_path, recording_path):
        if self.sender() is not None and self.sender() is not self._metrics_worker:
            return  # result of an older upload
        self._metrics_worker = None
        if str(recording_path) != str(self.loaded_recording_path or ""):
            return
        self.analysis_results = results
        self.analysis_json_path = json_path
        pass

    def _on_metrics_failed(self, error_message, recording_path):
        if self.sender() is not None and self.sender() is not self._metrics_worker:
            return
        self._metrics_worker = None
        if str(recording_path) != str(self.loaded_recording_path or ""):
            return
        self.analysis_results = None
        self.analysis_json_path = None
        pass

    def _compute_fallback_navigation_events(self):
        """Provisional threshold events (used when the detector is unavailable)."""
        signals = (self.psg_full_data or {}).get("signals", {})
        enhanced_airflow = signals.get("airflow_enhanced", signals.get("airflow", []))
        airflow_fs = self.channel_rate("airflow")
        global_events = self._build_airflow_navigation_events(enhanced_airflow, fs=airflow_fs)
        windowed_events = self._build_windowed_airflow_navigation_events(
            enhanced_airflow,
            fs=airflow_fs,
            window_seconds=max(1.0, float(self.current_time_window)),
        )
        return windowed_events if len(windowed_events) >= len(global_events) else global_events

    def load_psg_data_and_detect(
        self,
        recording_path,
        padding_seconds: float = 30.0,
        focus_first_event: bool = False,
    ):
        """Load uploaded PSG data, run rule-based detection, and optionally jump to the first event.

        PERF: detector reads the file from disk by itself, so it is started
        FIRST and runs in parallel with the chart load (before: load time +
        detection time). Its result is queued and applied after the load
        returns, so loaded_recording_path is already set when it is checked.
        """
        self.last_load_rejected_for_short_duration = False

        # Reject short recordings before detection and chart processing start.
        # load_sleep_recording() is cached, so an accepted file is reused by
        # the normal loader below instead of being parsed from disk twice.
        raw_duration_sec = 0.0
        try:
            recording = load_sleep_recording(recording_path)
            master_channel = recording.get("master_channel", "airflow")
            time_values = np.asarray(recording.get("time", []), dtype=float)
            master_rate = float(
                (recording.get("sample_rates", {}) or {}).get(master_channel, 0.0)
                or 0.0
            )
            finite_time = time_values[np.isfinite(time_values)]
            if finite_time.size:
                raw_duration_sec = float(finite_time[-1] - finite_time[0])
                if master_rate > 0.0:
                    raw_duration_sec += 1.0 / master_rate
        except Exception:
            # Let the existing loader report malformed/unreadable files.
            raw_duration_sec = 0.0

        self.last_load_rejection_message = ""
        if raw_duration_sec > 0.0 and raw_duration_sec + 1e-6 < MIN_RECORDING_SECONDS:
            # Too short: nothing is loaded or detected; whatever was open stays open.
            self.last_load_rejected_for_short_duration = True
            self.last_load_rejection_message = (
                f"Recording is too short: {raw_duration_sec / 60.0:.1f} minutes. "
                f"At least {MIN_RECORDING_SECONDS / 60.0:g} minutes of recording are required."
            )
            return np.array([]), {}, True

        self._pending_focus_first_event = float(padding_seconds) if focus_first_event else None
        self._pending_detection_result = None
        self._upload_loading_path = str(recording_path)
        self._upload_t0 = time.perf_counter()
        self._show_upload_overlay("Loading data...")
        loaded_ok = False
        try:
            self.run_rule_ai_apnea_detection(recording_path=recording_path)

            time_data, signals = self.load_psg_data(recording_path, defer_extras=True)
            _t_loaded = time.perf_counter()
            loaded_ok = len(time_data) > 0 and bool(signals)
            if loaded_ok:
                self._set_upload_overlay_message("Drawing graphs...")
                QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
                self.current_time_offset = 0
                self._log_first_draw = True
                self.refresh_charts()
                self.time_position_updated.emit()
                _psg_playback_log(
                    "upload timeline: loading data %.0f ms, drawing graphs %.0f ms, graphs visible %.0f ms "
                    "after the upload started"
                    % ((_t_loaded - self._upload_t0) * 1000.0, (time.perf_counter() - _t_loaded) * 1000.0,
                       (time.perf_counter() - self._upload_t0) * 1000.0)
                )
                if self._detection_running:
                    # load_psg_data() reset the status text to "Events: --".
                    if hasattr(self, "detection_summary_label"):
                        self.detection_summary_label.setText("Detecting events in background...")
                    if self.play_pause_btn:
                        self.play_pause_btn.setEnabled(False)
                        self.play_pause_btn.setText("Detecting...")
        finally:
            self._upload_loading_path = None
            self._hide_upload_overlay()

        # Detection may have finished while the file was still loading.
        pending = self._pending_detection_result
        self._pending_detection_result = None
        if pending is not None:
            kind, payload, pending_path = pending
            if kind == "done":
                self._on_detection_done(payload, pending_path, _from_pending=True)
            else:
                self._on_detection_failed(payload, pending_path, _from_pending=True)
        return time_data, signals, False

    # --- Loading spinners ---------------------------------------------------
    def _load_uploaded_signals_with_spinner(self, recording_path):
        """Parse the file in a worker thread while a local event loop keeps the
        spinner turning. User input is excluded, so nothing can be clicked
        twice. Same return value / exceptions as _load_uploaded_psg_signals."""
        if self._upload_loading_path != str(recording_path):
            return self._load_uploaded_psg_signals(recording_path)
        worker = self._CallWorker(
            self._load_uploaded_psg_signals, (recording_path,), parent=self,
        )
        loop = QEventLoop()
        worker.finished.connect(loop.quit)  # queued -> no start/exec race
        worker.start()
        loop.exec_(QEventLoop.ExcludeUserInputEvents)
        worker.wait()
        if worker.error is not None:
            raise worker.error
        return worker.result

    def _show_upload_overlay(self, message):
        target = getattr(self, "scroll_area", None) or self
        if self._upload_overlay is None or sip.isdeleted(self._upload_overlay):
            self._upload_overlay = BusyOverlay(target, message)
        self._upload_overlay.start(message)
        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)

    def _set_upload_overlay_message(self, message):
        if self._upload_overlay is not None and not sip.isdeleted(self._upload_overlay):
            self._upload_overlay.set_message(message)

    def _hide_upload_overlay(self):
        if self._upload_overlay is not None and not sip.isdeleted(self._upload_overlay):
            self._upload_overlay.stop()

    def set_events_panel_widget(self, widget):
        """Optional: tell the chart which widget is the Detected Events panel
        so the spinner covers exactly that card."""
        self._events_panel_widget = widget
        if self._events_panel_overlay is not None and not sip.isdeleted(self._events_panel_overlay):
            self._events_panel_overlay.deleteLater()
        self._events_panel_overlay = None
        if self._detection_running:
            self._set_detection_busy(True)

    def _find_events_panel(self):
        widget = self._events_panel_widget
        if widget is not None and not sip.isdeleted(widget):
            return widget
        # Fallback: find the side card by its "Detected Events" title label.
        try:
            window = self.window()
            for label in window.findChildren(QLabel):
                if label.text().strip().lower() != "detected events":
                    continue
                panel = label.parentWidget()
                for _ in range(4):
                    if panel is None or panel is window or panel.height() >= 150:
                        break
                    panel = panel.parentWidget()
                if panel is not None and panel is not window:
                    self._events_panel_widget = panel
                    return panel
        except RuntimeError:
            pass
        return None

    def _set_detection_busy(self, busy):
        spinner = getattr(self, "detection_status_spinner", None)
        if spinner is not None:
            spinner.start() if busy else spinner.stop()
        panel = self._find_events_panel()
        if panel is not None:
            overlay = self._events_panel_overlay
            if overlay is None or sip.isdeleted(overlay):
                overlay = BusyOverlay(panel, "Detecting events...", spinner_size=34)
                self._events_panel_overlay = overlay
            overlay.start("Detecting events...") if busy else overlay.stop()
        self.detection_busy_changed.emit(bool(busy))

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
        if overlaps_exclusion(normalized, self.get_recording_exclusions()["excluded_segments"]):
            return None
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
        if not getattr(self, "loaded_recording_path", None):
            return None
        return _sidecar_path_for(self.loaded_recording_path)

    def _selection_time_key(self, start_sec: float, end_sec: float) -> str:
        start_sec, end_sec = self._ordered_span(start_sec, end_sec)
        return f"{start_sec:.2f}_{end_sec:.2f}"

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
        if overrides_path is None:
            return

        raw_data = _read_signed_json(overrides_path)

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
            payload = {
                "label_overrides": self.manual_label_overrides,
                "manual_selections": self._collect_manual_selections_for_save(),
                "deleted_auto_events": self._collect_deleted_auto_events_for_save(),
            }
            _write_signed_json(overrides_path, payload)
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

    def _postprocess_desaturations(self):
        """Merge detector splits and attach PSG-style desaturation quality flags."""
        if not DESAT_POSTPROCESS_ENABLED or not self.auto_rule_ai_result:
            return

        desaturations = self.auto_rule_ai_result.get("desaturations") or []
        if not desaturations:
            return

        times = None
        spo2_values = None
        psg_data = getattr(self, "psg_full_data", None) or {}
        signals = psg_data.get("signals") or {}
        channel_times = psg_data.get("times") or {}
        if "spo2" in signals:
            # Use raw SpO2, never the display-bridged copy.
            spo2_values = np.asarray(signals["spo2"], dtype=float)
            times = np.asarray(
                channel_times.get("spo2", psg_data.get("time", [])),
                dtype=float,
            )
        else:
            spo2_full_data = getattr(self, "spo2_full_data", None)
            if spo2_full_data is not None:
                times, spo2_values = spo2_full_data

        if times is None or spo2_values is None or len(times) == 0:
            return

        count = min(len(times), len(spo2_values))
        times = np.asarray(times, dtype=float)[:count]
        spo2_values = np.asarray(spo2_values, dtype=float)[:count]
        try:
            merged = merge_split_desaturations(
                desaturations,
                times,
                spo2_values,
            )
            merged = flag_desat_quality(merged, times, spo2_values)
        except Exception as error:
            pass
            return

        pass
        self.auto_rule_ai_result["desaturations"] = merged

    def _finish_detection_result(self):
        self._postprocess_desaturations()
        self._apply_deleted_auto_event_filters_to_auto_result()
        self._apply_manual_label_overrides_to_auto_result()
        self.auto_focus_applied = False
        self.last_detection_error = None
        self._apply_sensor_off_masking_after_detection()
        self.refresh_charts()
        self._sync_auto_detected_selections_into_overlays()
        self.render_dynamic_selections()
        self.emit_detected_events_panel()
        self.update_detection_summary_label()

    def _on_detection_done(self, result, recording_path, _from_pending=False):
        if (not _from_pending and self.sender() is not None
                and self.sender() is not self._detect_worker):
            return  # an older upload's worker finished late; ignore it
        if self._upload_loading_path == str(recording_path):
            # Finished before the chart load did; applied right after it.
            self._pending_detection_result = ("done", result, recording_path)
            return
        self._detection_running = False
        self._set_detection_busy(False)
        self._detect_worker = None
        if self.play_pause_btn:
            self.play_pause_btn.setEnabled(True)
            self.play_pause_btn.setText("▶ Play")
        if str(recording_path) != str(self.loaded_recording_path or ""):
            return
        self.auto_rule_ai_result = result
        _t_apply = time.perf_counter()
        self._finish_detection_result()
        _upload_t0 = self.__dict__.get("_upload_t0")
        if _upload_t0 is not None:
            _psg_playback_log(
                "events shown: %.0f ms after the upload started (showing them took %.0f ms)"
                % ((time.perf_counter() - _upload_t0) * 1000.0, (time.perf_counter() - _t_apply) * 1000.0)
            )
        padding = self._pending_focus_first_event
        self._pending_focus_first_event = None
        if padding is not None:
            self.focus_on_first_detected_event(padding_seconds=padding)
            self.time_position_updated.emit()

    def _on_detection_failed(self, error_message, recording_path, _from_pending=False):
        if (not _from_pending and self.sender() is not None
                and self.sender() is not self._detect_worker):
            return
        if self._upload_loading_path == str(recording_path):
            self._pending_detection_result = ("failed", error_message, recording_path)
            return
        self._detection_running = False
        self._set_detection_busy(False)
        self._detect_worker = None
        if self.play_pause_btn:
            self.play_pause_btn.setEnabled(True)
            self.play_pause_btn.setText("▶ Play")
        if str(recording_path) != str(self.loaded_recording_path or ""):
            return
        self.auto_rule_ai_result = None
        self.last_detection_error = f"Detection failed: {error_message}"
        if not getattr(self, "airflow_detected_events", None):
            # Upload path skipped these; build them now as the fallback list.
            try:
                self.airflow_detected_events = self._compute_fallback_navigation_events()
            except Exception as fallback_error:
                pass
        self.emit_detected_events_panel()
        self.update_detection_summary_label()

    def is_detection_running(self):
        return bool(self._detection_running)

    def run_rule_ai_apnea_detection(self, background=True, recording_path=None):
        """Run apnea detection in a worker by default.

        recording_path: detect on this file instead of loaded_recording_path (used to start
        detection before the chart load has finished).
        """
        target_recording_path = (
            str(recording_path) if recording_path else self.loaded_recording_path
        )
        if not target_recording_path:
            self.last_detection_error = "Recording path missing for detection."
            self.auto_rule_ai_result = None
            self.emit_detected_events_panel()
            self.update_detection_summary_label()
            return

        if detect_apnea_events_from_recording is None:
            self.last_detection_error = (
                "Detector import failed."
                + (f" {DETECTION_IMPORT_ERROR}" if DETECTION_IMPORT_ERROR else "")
            )
            self.auto_rule_ai_result = None
            self.emit_detected_events_panel()
            self.update_detection_summary_label()
            return

        # Generated detector artifacts must be written outside the PyInstaller
        # bundle.  _MEIPASS is temporary/read-only in installed builds.
        output_dir = get_configured_path("detector_output_dir") / "chart_auto_events"
        if background:
            self._detection_running = True
            self.last_detection_error = None
            if self.is_playing:
                self.pause_playback()
            if self.play_pause_btn:
                self.play_pause_btn.setEnabled(False)
                self.play_pause_btn.setText("Detecting...")
            if hasattr(self, "detection_summary_label"):
                self.detection_summary_label.setText("Detecting events in background...")
            worker = self._DetectWorker(
                target_recording_path,
                output_dir,
                trim_seconds=RECORDING_EDGE_TRIM_SECONDS,
                parent=self,
            )
            worker.done.connect(self._on_detection_done)
            worker.failed.connect(self._on_detection_failed)
            self._detect_worker = worker
            worker.start()
            self._set_detection_busy(True)
            return

        try:
            self.auto_rule_ai_result = detect_apnea_events_from_recording(
                recording_path=target_recording_path,
                output_dir=output_dir,
                enable_ai=False,
                trim_start_seconds=RECORDING_EDGE_TRIM_SECONDS,
                trim_end_seconds=RECORDING_EDGE_TRIM_SECONDS,
            )
            self._finish_detection_result()
        except Exception as error:
            import traceback
            traceback.print_exc()
            self.auto_rule_ai_result = None
            self.auto_focus_applied = False
            self.last_detection_error = f"Detection failed: {error}"

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
        sensor_off_segments = []
        if SENSOR_OFF_SEGMENTS_AS_EVENTS:
            for segment in self.auto_rule_ai_result.get("sensor_off_segments", []) or []:
                try:
                    seg_start = float(segment.get("start_sec"))
                    seg_end = float(segment.get("end_sec"))
                except (TypeError, ValueError):
                    continue
                if seg_end - seg_start >= float(SENSOR_OFF_EVENT_MIN_SEC):
                    sensor_off_segments.append((seg_start, seg_end, str(segment.get("reason", ""))))

        if not events and not desaturations and not sensor_off_segments:
            return

        def _inside_sensor_off(start_time, end_time):
            duration = max(end_time - start_time, 1e-9)
            for seg_start, seg_end, _reason in sensor_off_segments:
                overlap = min(end_time, seg_end) - max(start_time, seg_start)
                if overlap / duration >= 0.5:
                    return True
            return False

        target_charts = ["Airflow"] if (events or sensor_off_segments) else []

        for chart_name in target_charts:
            self.selection_labels.setdefault(chart_name, [])
            self.dynamic_selections.setdefault(chart_name, [])

            for event in events:
                final_label = canonical_event_label(event.get("final_label") or event.get("rule_label") or "REVIEW")
                if final_label == "REVIEW":
                    continue
                start_time = float(event["start_sec"])
                end_time = float(event["end_sec"])
                if final_label == "SENSOR_OFF" and _inside_sensor_off(start_time, end_time):
                    # Covered by the full-length sensor-off entry added below.
                    continue
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

            for seg_start, seg_end, reason in sensor_off_segments:
                entry = {
                    "label": "SENSOR_OFF",
                    "start": seg_start,
                    "end": seg_end,
                    "start_time": seg_start,
                    "end_time": seg_end,
                    "color": self.get_label_color("SENSOR_OFF"),
                    "source": "auto_rule_ai",
                    "is_manually_edited": False,
                    "original_label": None,
                    "evidence": [reason] if reason else [],
                }
                self.selection_labels[chart_name].append(dict(entry))
                self.dynamic_selections[chart_name].append({
                    k: v for k, v in entry.items() if k not in ("start", "end")
                })

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
                display_start_time = self._desaturation_display_start(
                    desat,
                    start_time,
                )
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
                    "display_start_time": display_start_time,
                    "end_time": end_time,
                    "color": desat_color,
                    "source": "auto_rule_ai",
                    "spo2_info": spo2_info,
                })

    def _desaturation_display_start(self, desaturation, detected_start):
        """Return the visible fall onset without changing the scored event.

        The detector starts an event when the full threshold is reached.  For
        drawing only, walk backwards over the same continuous below-baseline
        run so the box also contains the beginning of the visible SpO2 fall.
        If no preceding baseline sample is found, keep the detector start.
        """
        try:
            detected_start = float(detected_start)
            baseline = float(desaturation.get("baseline_spo2"))
        except (AttributeError, TypeError, ValueError):
            return detected_start
        if not np.isfinite(baseline):
            return detected_start

        full_data = getattr(self, "spo2_full_data", None)
        if full_data is None or len(full_data) < 2:
            return detected_start
        times = np.asarray(full_data[0], dtype=float).reshape(-1)
        values = np.asarray(full_data[1], dtype=float).reshape(-1)
        count = min(times.size, values.size)
        if count < 2:
            return detected_start
        times = times[:count]
        values = values[:count]

        event_index = int(np.searchsorted(times, detected_start, side="left"))
        if event_index >= count:
            event_index = count - 1
        threshold = baseline - float(DESAT_DISPLAY_BASELINE_TOLERANCE)
        event_value = values[event_index]
        if (
            not np.isfinite(event_value)
            or event_value < float(DESAT_SPO2_VALID_RANGE[0])
            or event_value > float(DESAT_SPO2_VALID_RANGE[1])
            or event_value >= threshold
        ):
            return detected_start

        earliest = int(np.searchsorted(
            times,
            detected_start - float(DESAT_DISPLAY_ONSET_LOOKBACK_SEC),
            side="left",
        ))
        onset = event_index
        while onset > earliest:
            previous = onset - 1
            previous_value = values[previous]
            if (
                not np.isfinite(previous_value)
                or previous_value < float(DESAT_SPO2_VALID_RANGE[0])
                or previous_value > float(DESAT_SPO2_VALID_RANGE[1])
            ):
                return detected_start
            if previous_value >= threshold:
                candidate = float(times[onset])
                return candidate if candidate < detected_start else detected_start
            onset = previous

        # Do not extend to an arbitrary lookback boundary when the actual
        # baseline-to-fall transition is not present in the available data.
        return detected_start

    def get_first_detected_event(self):
        """Return the earliest automatically detected event."""
        events = self.get_available_navigation_events()
        if not events and self.is_detection_running():
            self.detection_summary_label.setText("Detecting events in background...")
            return
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
            elif (self.auto_rule_ai_result or {}).get("airflow_not_connected"):
                self.detection_summary_label.setText(
                    "Airflow sensor not connected - airflow events not scored"
                )
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
        - raw_snoring: Single-point snoring intensity values from the recording
        - airflow: Airflow signal for synchronization
        
        Returns:
        - Realistic snoring waveform with vibration packets
        """
        sampling_rate = self.channel_rate("snoring")
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
            pass
            return np.array([]), np.array([])
        
        if signal_col == "airflow":
            full_signal = self._get_airflow_signal_variant("display")
        elif signal_col == "thorax":
            full_signal = self._get_thorax_signal_variant("display")
        elif signal_col == "body_position":
            full_signal = self._get_body_position_signal()
        elif signal_col == "pulse":
            full_signal = self._bridge_slow_channel_dropouts(
                signals[signal_col],
                self.channel_rate(signal_col),
                SPO2_DISPLAY_BRIDGE_MAX_SECONDS,
            )
        else:
            full_signal = signals[signal_col]

        channel_rate = self.channel_rate(signal_col)
        if self.is_all_psg_mode():
            full_time = self.channel_time(signal_col)
            sample_count = min(len(full_time), len(full_signal))
            if sample_count == 0:
                return np.array([]), np.array([])
            window_time, window_signal = self._smart_downsample(
                full_time[:sample_count],
                full_signal[:sample_count],
                max_points=2500,
            )
        else:
            if signal_col == "pulse" and channel_rate < self.DISPLAY_HOLD_BELOW_HZ:
                # 1 Hz SD pulse: exact flat steps. The start-of-recording warm-up
                # is filled once for the whole file, not per visible window.
                step_source = self._cached_slow_display(
                    "pulse",
                    full_signal,
                    lambda arr: self._smooth_slow_channel_for_display(
                        self._fill_leading_slow_channel_start(arr)),
                )
                window_time, window_signal = self._step_display_window(
                    step_source, channel_rate, time_window_seconds, time_offset)
                window_time, window_signal = self._prepare_plot_data_for_window(
                    window_time, window_signal, time_window_seconds)
            else:
                window_time, window_signal = self._slice_signal_for_window(
                    full_signal,
                    time_window_seconds,
                    time_offset,
                    sample_rate_hz=channel_rate,
                )

                if signal_col == "pulse":
                    window_signal = self._fill_leading_slow_channel_start(window_signal)
                    window_signal = self._smooth_slow_channel_for_display(window_signal)

                window_time, window_signal = self._prepare_plot_data_for_window(
                    window_time,
                    window_signal,
                    time_window_seconds,
                )

                # Other slow channels: interpolate on the display grid.
                window_time, window_signal = self._hold_for_display(
                    window_time, window_signal, channel_rate
                )

        if signal_col == "pulse":
            # SpO2 and BPM arrive as separate fields from the same oximeter.
            # Per the display rule, missing/zero SpO2 is authoritative: both
            # charts show zero even if BPM still contains a stale non-zero value.
            if self.spo2_full_data is not None:
                spo2_time, raw_spo2 = self.spo2_full_data
                if np.asarray(raw_spo2).size == 0:
                    window_signal = np.zeros_like(window_signal, dtype=float)
                else:
                    absolute_window_time = (
                        np.asarray(window_time, dtype=float)
                        if self.is_all_psg_mode()
                        else np.asarray(window_time, dtype=float) + float(time_offset)
                    )
                    window_signal = self._zero_where_reference_has_no_signal(
                        window_signal,
                        absolute_window_time,
                        self._bridge_slow_channel_dropouts(
                            raw_spo2,
                            self.channel_rate("spo2"),
                            SPO2_DISPLAY_BRIDGE_MAX_SECONDS,
                        ),
                        spo2_time,
                        self.channel_rate("spo2"),
                    )
            # Any remaining invalid Pulse sample is also displayed as zero.
            window_signal = np.where(np.isfinite(window_signal), window_signal, 0.0)

        if len(window_signal) == 0:
            return np.array([]), np.array([])

        num_samples = len(window_signal)
        expected_samples = int(round(time_window_seconds * channel_rate))

        if signal_col == "airflow":
            nan_count = int(np.count_nonzero(~np.isfinite(window_signal)))
            zero_count = int(np.count_nonzero(window_signal == 0.0))
            pass
        
        pass
        
        return window_time, window_signal
    
    def get_spo2_data_for_window(self, time_window_seconds, time_offset=0):
        """Get SpO2 data filtered for specific time window"""
        if "SpO2" not in PLOTTED_SIGNAL_NAMES:
            return np.array([]), np.array([])

        if self.spo2_full_data is None or len(self.spo2_full_data[0]) == 0:
            return np.array([]), np.array([])
        
        full_time, _full_spo2 = self.spo2_full_data
        display_spo2 = self._spo2_display_full()

        if self.is_all_psg_mode():
            sample_count = min(len(full_time), len(display_spo2))
            if sample_count == 0:
                return np.array([]), np.array([])
            expected_samples = sample_count
            window_time, window_spo2 = self._smart_downsample(
                np.asarray(full_time[:sample_count], dtype=float),
                np.asarray(display_spo2[:sample_count], dtype=float),
                max_points=2500,
            )
        else:
            # Keep every window endpoint-exclusive: 60s at 10Hz must be exactly 600 samples.
            samples_per_second = self.channel_rate("spo2")
            expected_samples = int(round(time_window_seconds * samples_per_second))
            if samples_per_second < self.DISPLAY_HOLD_BELOW_HZ:
                # 1 Hz SD readings: exact flat steps (see _step_display_window).
                step_source = self._cached_slow_display(
                    "spo2", display_spo2, self._copy_slow_channel_for_display)
                window_time, window_spo2 = self._step_display_window(
                    step_source, samples_per_second, time_window_seconds, time_offset)
                window_time, window_spo2 = self._prepare_plot_data_for_window(
                    window_time, window_spo2, time_window_seconds)
            else:
                start_sample = max(0, int(np.floor(float(time_offset) * samples_per_second)))
                end_sample = min(len(display_spo2), start_sample + expected_samples + 2)
                window_spo2 = display_spo2[start_sample:end_sample]
                num_samples = len(window_spo2)
                window_spo2 = np.asarray(window_spo2, dtype=float).copy()
                window_time = (
                    (start_sample + np.arange(num_samples, dtype=float)) / samples_per_second
                    - float(time_offset)
                )
                window_time, window_spo2 = self._prepare_plot_data_for_window(
                    window_time,
                    window_spo2,
                    time_window_seconds,
                )

            num_samples = len(window_spo2)
            if num_samples == 0:
                return np.array([]), np.array([])

            # The display-only no-signal mask is already applied by
            # _spo2_display_full; report calculations separately exclude it.

        num_samples = len(window_spo2)
        if num_samples == 0:
            return np.array([]), np.array([])

        # Keep the display's short-gap hold behavior. Report calculations use
        # the preserved analysis signal and exclude zero intervals separately.
        self.calculate_spo2_statistics(window_spo2)

        pass
        
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
            pass
            return "NO_EVENT"

    @staticmethod
    def _below_threshold_runs(values, threshold):
        """Return below-threshold runs while preserving recovery endpoints."""
        values = np.asarray(values, dtype=float).reshape(-1)
        if values.size == 0:
            return []
        finite_index = np.flatnonzero(np.isfinite(values))
        if finite_index.size == 0:
            return []
        below = values[finite_index] < float(threshold)
        edges = np.diff(np.r_[False, below, False].astype(np.int8))
        starts = np.flatnonzero(edges == 1)
        ends = np.flatnonzero(edges == -1)
        last = values.size - 1
        return [
            (int(finite_index[a]), int(finite_index[b]) if b < finite_index.size else last)
            for a, b in zip(starts, ends)
        ]

    def _build_airflow_navigation_events(self, airflow, fs=None):
        """Build a reusable event list from the full airflow signal for navigation."""
        fs = float(fs) if fs else self.channel_rate("airflow")
        airflow = np.asarray(airflow, dtype=float)
        if len(airflow) == 0:
            return []

        baseline_airflow, baseline_occurrence = self.get_airflow_event_baseline(airflow)
        threshold = baseline_airflow
        min_samples = max(1, int(round(AIRFLOW_DROP_MIN_DURATION_SEC * fs)))
        events = self._below_threshold_runs(airflow, threshold)

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
        fs=None,
        window_seconds=60.0,
    ):
        """Build full-data events using the same local-window baseline style as visible markers."""
        fs = float(fs) if fs else self.channel_rate("airflow")
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
            events = self._below_threshold_runs(window_signal, threshold)

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
        fs=None,
    ):
        """Mark Airflow events from below threshold until the next recovery threshold."""
        fs = float(fs) if fs else self.channel_rate("airflow")
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
                pen=pg.mkPen(None),
                hoverPen=pg.mkPen(None),
            )
            region.setZValue(-10)
            region._playback_span = (start_time_abs, end_time_abs)
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
            block._playback_span = (start_time_abs, end_time_abs)
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
        spo2_array = np.where(
            np.isfinite(spo2_array) & (spo2_array > 100.0), 100.0, spo2_array
        )
        spo2_array = np.where(spo2_array == 0.0, np.nan, spo2_array)
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
                /* Keep the outline neutral: child widgets cover most of this
                   border, otherwise only blue top/bottom caps remain visible. */
                border: 2px solid #cbd5e1;
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
        
        label = QLabel("Effort" if name == "Thorax" else name)
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

        def centered_zoom_icon(draw_plus):
            """Draw +/− geometrically so font baselines cannot shift them."""
            pixmap = QPixmap(12, 12)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing, True)
            pen = QPen(QColor("#475569"), 1.6)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(2.5, 6.0), QPointF(9.5, 6.0))
            if draw_plus:
                painter.drawLine(QPointF(6.0, 2.5), QPointF(6.0, 9.5))
            painter.end()
            return QIcon(pixmap)

        zoom_in_btn = QPushButton()
        zoom_in_btn.setIcon(centered_zoom_icon(True))
        zoom_in_btn.setIconSize(QSize(12, 12))
        zoom_in_btn.setAccessibleName("Zoom in")

        zoom_out_btn = QPushButton()
        zoom_out_btn.setIcon(centered_zoom_icon(False))
        zoom_out_btn.setIconSize(QSize(12, 12))
        zoom_out_btn.setAccessibleName("Zoom out")

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
                QTimer.singleShot(0, lambda: self._refit_value_axis_after_resize(
                    getattr(container, "plot_widget", None)))
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
            QTimer.singleShot(0, lambda: self._refit_value_axis_after_resize(
                getattr(container, "plot_widget", None)))
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
        # Axis helpers run before the curve is created, so expose the owner
        # channel immediately (it used to be assigned only at the end).
        plot_widget.chart_name = name
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
                border: none;
                border-radius: 0px;
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
            # Oximetry is measured in whole percentage points. A 50% minimum
            # span (the generic fixed-axis default) makes SpO2 zoom feel as if
            # it barely responds and can make nearby readings hard to inspect.
            # Let the user zoom into a 5-point band while keeping the normal
            # clinical bounds and the recorded samples unchanged.
            plot_widget.zoom_y_min_span = (
                min(base_y_span, 5.0)
                if signal_name.strip() == "SpO2"
                else max(base_y_span * 0.5, 1.0)
            )
            plot_widget.zoom_y_max_span = base_y_span
            
        # Set X-axis to show time values based on current time window
        bottom_axis = plot_widget.getAxis('bottom')
        bottom_axis.setStyle(showValues=True)  # Show time values
        bottom_axis.setHeight(20)  # Keep the axis compact so it hugs the bottom edge
        
        left_axis = plot_widget.getAxis('left')
        # left_axis.setStyle(showValues=True)   # Show Y-axis values
        if signal_name in HIDDEN_Y_AXIS_VALUE_CHARTS:
            left_axis.setStyle(showValues=False, tickLength=0)
            # An explicit empty tick list removes the tiny dot-like tick marks too.
            left_axis.setTicks([[]])
        else:
            left_axis.setStyle(showValues=True)
        
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
                plot_item.layout.setContentsMargins(0, PLOT_TOP_MARGIN_PX, 0, 0)
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
        plot_widget.wheelEvent = lambda event, pw=plot_widget: self.handle_container_wheel_zoom(event, pw)
        
        # Keep the plot anchored to the top so the signal begins immediately under the card
        plot_container_layout.setAlignment(plot_widget, Qt.AlignTop)
        
        # Generate signal data
        if name.strip() == "SpO2":
            # Get SpO2 data for current time window
            # Get filtered data for current time window
            x, y = self.get_spo2_data_for_window(visible_window, self.current_time_offset)

            if len(x) > 0 and len(y) > 0:
                # Use real SpO2 data as-is (no artificial baseline correction)
                pass
        else:
            x, y = self.get_signal_data_for_window(name, visible_window, self.current_time_offset)
            if len(x) > 0 and len(y) > 0:
                pass
        
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

        if name.strip() in HIGH_RATE_CHART_NAMES and HIGH_RATE_PEAK_DOWNSAMPLING:
            try:
                plot_widget.setDownsampling(mode="peak", auto=True)
                plot_widget.setClipToView(True)
            except Exception:
                pass

        if name.strip() == "Snoring":
            # Red (main trace) = inhale. Exhale packets are redrawn on top in
            # orange when continuous, grey when isolated (review).
            plot_widget.snore_phase_curves = {
                "exhale": plot_widget.plot(
                    [], [], pen=pg.mkPen(color=SNORE_EXHALE_COLOR, width=1.5), connect="finite"),
                "review": plot_widget.plot(
                    [], [], pen=pg.mkPen(color=SNORE_REVIEW_COLOR, width=1.5), connect="finite"),
            }
            label.setToolTip(
                "Snoring: red = inhale, orange = exhale (continuous), "
                "grey = exhale (isolated - review)"
            )

        if name.strip() in AUTO_RANGE_SIGNAL_NAMES:
            if name.strip() == "SpO2" and self._apply_spo2_zero_axis_if_needed(plot_widget, y):
                pass
            else:
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
                pass

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
                pass

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
        
        pass
    
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
        
        pass
    
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
                
                pass
            
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
            pass
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
            pass
    
    def zoom_vertical(self, plot_widget, zoom_factor):
        """Zoom in/out vertically on the plot"""
        chart_name = getattr(plot_widget, 'chart_name', '')
        if chart_name.strip() == "SpO2" and not hasattr(plot_widget, "axis_properties"):
            self._zoom_spo2_step(plot_widget, zoom_in=zoom_factor < 1.0)
            return

        # Get current Y range
        current_range = plot_widget.getViewBox().viewRange()
        y_min, y_max = current_range[1]
        
        # Anchor zoom around the visible waveform strip instead of empty space.
        center = (y_min + y_max) / 2
        visible_y = np.array([], dtype=float)
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
        # Zooming out must never push visible Pulse samples outside the plot.
        if chart_name.strip() == "Pulse" and visible_y.size:
            pad = 0.05 * (new_y_max - new_y_min)
            new_y_min = min(new_y_min, float(visible_y.min()) - pad)
            new_y_max = max(new_y_max, float(visible_y.max()) + pad)
            
        try:
            plot_widget.setYRange(new_y_min, new_y_max)
            # Store zoom range to persist during playback
            plot_widget.zoom_y_range = (new_y_min, new_y_max)
            pass
        except TypeError:
            # Try alternative method for older pyqtgraph versions
            plot_widget.setRange(yRange=[new_y_min, new_y_max])
            # Store zoom range to persist during playback
            plot_widget.zoom_y_range = (new_y_min, new_y_max)
            pass

        self._release_core_ticks(plot_widget)
        self._pin_axis_tick_spacing(plot_widget, new_y_min, new_y_max)

    def zoom_vertical_at_ratio(self, plot_widget, zoom_factor, anchor_ratio):
        """Zoom vertically while keeping the chosen relative Y position visually anchored."""
        if str(getattr(plot_widget, 'chart_name', '')).strip() == "SpO2" and not hasattr(plot_widget, "axis_properties"):
            self._zoom_spo2_step(plot_widget, zoom_in=zoom_factor < 1.0)
            return
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
        if chart_name.strip() == "Pulse":
            visible_y = self._visible_curve_values(plot_widget)
            if visible_y.size:
                pad = 0.05 * (new_y_max - new_y_min)
                new_y_min = min(new_y_min, float(visible_y.min()) - pad)
                new_y_max = max(new_y_max, float(visible_y.max()) + pad)

        try:
            plot_widget.setYRange(new_y_min, new_y_max)
        except TypeError:
            plot_widget.setRange(yRange=[new_y_min, new_y_max])

        plot_widget.zoom_y_range = (new_y_min, new_y_max)
        self._release_core_ticks(plot_widget)
        self._pin_axis_tick_spacing(plot_widget, new_y_min, new_y_max)
        pass

    def handle_container_wheel_zoom(self, event, plot_widget):
        """Route wheel zoom from anywhere on the chart into centered graph zoom."""
        modifiers = event.modifiers() if hasattr(event, "modifiers") else Qt.NoModifier
        if not (modifiers & (Qt.ControlModifier | Qt.MetaModifier)):
            event.ignore()
            return
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
        if clean_name == "SpO2":
            # SpO2 has its own loader/display path. Routing Reset through the
            # generic signal lookup returns an empty array when the source
            # channel is absent and restores the old 60-100 range, hiding zero.
            _reset_x, reset_y = self.get_spo2_data_for_window(
                self.get_effective_time_window_seconds(), self.current_time_offset
            )
            self._clear_axis_hold(clean_name)
            plot_widget.stable_y_range = None
            plot_widget.zoom_y_range = None
            if not self._apply_spo2_zero_axis_if_needed(plot_widget, reset_y):
                self._apply_windowed_auto_axis(plot_widget, clean_name, reset_y)
        elif clean_name in AUTO_RANGE_SIGNAL_NAMES:
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
            # Reset means "forget the held range and re-fit from scratch":
            # drop the hold for this chart, then run the same fit the redraw
            # loop uses so Reset always matches what a fresh window shows.
            self._clear_axis_hold(clean_name)
            plot_widget.stable_y_range = None
            plot_widget.zoom_y_range = None
            self._apply_windowed_auto_axis(plot_widget, clean_name, reset_y)
        else:
            plot_widget.zoom_y_range = None
            _reset_x, reset_y = self.get_signal_data_for_window(
                clean_name, self.get_effective_time_window_seconds(), self.current_time_offset
            )
            if clean_name == "Body Position":
                self._configure_body_position_axis(plot_widget)
            elif hasattr(plot_widget, "axis_properties"):
                properties = plot_widget.axis_properties
                default_min, default_max = SIGNAL_Y_RANGES.get(clean_name, (0, 100))
                self._set_y_view(
                    plot_widget,
                    properties.get("low_value", default_min),
                    properties.get("high_value", default_max),
                )
            elif clean_name == "Pulse":
                self._clear_axis_hold(clean_name)
                plot_widget.stable_y_range = None
                self._apply_windowed_auto_axis(plot_widget, clean_name, reset_y)
            else:
                y_min, y_max = SIGNAL_Y_RANGES.get(clean_name, (0, 100))
                self._set_y_view(plot_widget, y_min, y_max)

        # Auto-range and fixed-range branches above set the view through the
        # same helpers used by startup, scrolling, and playback.
        pass
    
    def forward_playback(self):
        """Fast forward playback"""
        pass
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
                    pass
            
            # DELAYED OVERLAY RENDER (IMPORTANT)
            QTimer.singleShot(0, self.render_dynamic_selections)
            
            self.update_time_display()
            pass
    
    def backward_playback(self):
        """Rewind playback"""
        pass
        if self.is_playing:
            # Jump backward by current time window
            self.current_time = self.current_time.addSecs(-self.current_time_window)
            self.update_time_display()
            pass
    
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
    
    def create_pulse_markers_and_labels(self, plot_widget, x_data, y_data):
        """Pulse value labels: same windows, buckets and placement as SpO2."""
        if not PULSE_LABELS_ENABLED:
            return
        self.add_spo2_value_labels(
            plot_widget, x_data, y_data, self.get_effective_time_window_seconds(),
            labels_attr="pulse_value_labels", color=PULSE_LABEL_COLOR, stat=PULSE_LABEL_STAT,
            step_tolerance=PULSE_LABEL_STEP_TOLERANCE, position=PULSE_LABEL_POSITION,
        )

    def create_spo2_markers_and_labels(self, plot_widget, x_data, y_data):
        """Create value labels for SpO2 when they don't exist (no scatter plot dots)"""
        pass
        
        # Add value labels on the graph (positioned exactly on data points)
        self.add_spo2_value_labels(
            plot_widget, x_data, y_data, self.get_effective_time_window_seconds(),
            position=SPO2_LABEL_POSITION,
        )
        
        pass
    
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

    @staticmethod
    def _bucket_label_value(values, stat, step_tolerance):
        """Number for one averaged label.

        Uniform bucket: the mean (or median). Bucket that straddles a step: a value
        that was really recorded, never the mix of the two levels.
        """
        values = np.asarray(values, dtype=float)
        if (
            LABEL_STEP_SHOWS_REAL_VALUE
            and step_tolerance
            and values.size > 1
            and float(np.ptp(values)) > float(step_tolerance)
        ):
            rounded = np.round(values, 1)
            levels, counts = np.unique(rounded, return_counts=True)
            tied = levels[counts == counts.max()]
            if tied.size == 1:
                return float(tied[0])
            return float(max(tied, key=lambda level: int(np.flatnonzero(rounded == level).max())))
        if str(stat or SPO2_LABEL_STAT).strip().lower() == "median":
            return float(np.median(values))
        return float(np.mean(values))

    def _drop_labels_near_steps(self, label_points, x_displayed, y_displayed, keep_nadir_in_boxes):
        """Remove numbers close to a level change, restoring a box nadir if needed."""
        x = np.asarray(x_displayed, dtype=float).reshape(-1)
        y = np.asarray(y_displayed, dtype=float).reshape(-1)
        m = min(x.size, y.size)
        x, y = x[:m], y[:m]
        ok = np.isfinite(y)
        if m < 2 or not ok.any():
            return label_points
        level = np.round(y)
        change_mask = (
            ok[1:]
            & ok[:-1]
            & (np.abs(level[1:] - level[:-1]) > LABEL_STEP_MIN_CHANGE)
        )
        change = np.flatnonzero(change_mask) + 1
        if change.size == 0:
            return label_points
        step_x = x[change]
        clearance = float(LABEL_STEP_CLEARANCE_SEC)
        kept = [pt for pt in label_points if np.min(np.abs(step_x - pt[0])) >= clearance]
        if not keep_nadir_in_boxes:
            return kept
        try:
            offset = 0.0 if self.is_all_psg_mode() else float(self.current_time_offset)
        except Exception:
            offset = 0.0
        for sel in (self.dynamic_selections or {}).get("SpO2", []):
            if "SATURATION" not in str(sel.get("label", "")).upper():
                continue
            try:
                a, b = self._ordered_span(sel["start_time"], sel["end_time"])
            except Exception:
                continue
            a, b = float(a) - offset, float(b) - offset
            if any(a <= pt[0] <= b for pt in kept):
                continue
            inside = np.flatnonzero((x >= a) & (x <= b) & ok)
            if inside.size == 0:
                continue
            lowest = float(np.min(y[inside]))
            centre = (max(a, float(x[0])) + min(b, float(x[-1]))) / 2.0
            kept.append((centre, lowest, f"{int(round(lowest))}"))
        kept.sort(key=lambda pt: pt[0])
        return kept

    def _desat_box_label_points(self, label_points, x_displayed, y_displayed):
        """Replace labels inside each visible DE-SATURATION box by start and nadir."""
        spans = []
        try:
            offset = 0.0 if self.is_all_psg_mode() else float(self.current_time_offset)
        except Exception:
            offset = 0.0
        for sel in (self.dynamic_selections or {}).get("SpO2", []):
            if "SATURATION" not in str(sel.get("label", "")).upper():
                continue
            try:
                a, b = self._ordered_span(sel["start_time"], sel["end_time"])
            except Exception:
                continue
            spans.append((float(a) - offset, float(b) - offset))
        if not spans:
            return label_points
        x = np.asarray(x_displayed, dtype=float).reshape(-1)
        y = np.asarray(y_displayed, dtype=float).reshape(-1)
        m = min(x.size, y.size)
        x, y = x[:m], y[:m]
        kept = [pt for pt in label_points if not any(a - 1.0 <= pt[0] <= b + 1.0 for a, b in spans)]
        for a, b in spans:
            inside = np.flatnonzero((x >= a) & (x <= b) & np.isfinite(y))
            if inside.size == 0:
                continue
            first = int(inside[0])
            lowest = int(inside[int(np.argmin(y[inside]))])
            kept.append((float(x[first]), float(y[first]), f"{int(round(float(y[first])))}"))
            if lowest != first:
                kept.append((float(x[lowest]), float(y[lowest]), f"{int(round(float(y[lowest])))}"))
        kept.sort(key=lambda pt: pt[0])
        return kept

    def _spo2_label_points(self, x_displayed, y_displayed, y_values, time_window, stat=None,
                           step_tolerance=None):
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
        # Only a recorded 0 is no signal; every other displayed reading gets a label.
        spo2_floor = 1.0

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

        # Playback preloads a short data tail beyond the right edge so the
        # scrolling curve never exposes a blank strip. That tail is not on
        # screen, and using absolute_times[-1] as the visible edge made its next
        # SpO2/Pulse label appear during Play and disappear again on Pause.
        # Clamp label eligibility to the real ViewBox window instead.
        visible_low = max(float(absolute_times[0]), float(offset))
        visible_high = min(
            float(absolute_times[-1]),
            float(offset) + max(0.0, float(time_window)),
        )
        if visible_high <= visible_low:
            return []

        first_bucket = int(np.floor(visible_low / bucket_seconds))
        last_bucket = int(np.floor((visible_high - 1e-9) / bucket_seconds))

        points = []
        for bucket in range(first_bucket, last_bucket + 1):
            low = bucket * bucket_seconds
            high = low + bucket_seconds

            # Only label buckets that are fully on screen. A half-visible bucket
            # would average a shrinking slice and its number would drift as it
            # scrolled in - the very flicker we are removing.
            if low < visible_low - 1e-9 or high > visible_high + 1e-9:
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

            # A bucket that contains a real level change (the edge of a dip or of
            # the recovery) is NOT labelled. Its number would flip between the
            # upper and lower level as the step scrolls through the bucket,
            # creating the visible up/down "blip". Only buckets that sit fully on
            # one flat level get a number.
            if values.size > 1 and float(np.ptp(values)) > float(LABEL_STEP_MIN_CHANGE):
                continue

            mean_value = self._bucket_label_value(
                values, stat,
                SPO2_LABEL_STEP_TOLERANCE if step_tolerance is None else step_tolerance,
            )

            points.append((
                float(np.mean(times)),
                float(np.mean(drawn)),
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

    def add_spo2_value_labels(self, plot_widget, x_data, y_data, time_window,
                              labels_attr="value_labels", color=(122, 29, 29), stat=None,
                              step_tolerance=None, position="trace"):
        """Draw the SpO2 value labels for the current window.

        Playback re-draws this ~20 times a second, so the TextItems are reused
        (moved and re-texted) instead of being destroyed and rebuilt every
        frame. That is what lets the numbers glide with the trace rather than
        blink in place.
        """
        if not hasattr(plot_widget, labels_attr):
            setattr(plot_widget, labels_attr, [])
        labels = getattr(plot_widget, labels_attr)
        label_map_attr = f"_{labels_attr}_by_time"
        label_map = getattr(plot_widget, label_map_attr, None)
        if not isinstance(label_map, dict):
            label_map = {}
            setattr(plot_widget, label_map_attr, label_map)

        # If this window has no usable SpO2 samples, clear any old labels and
        # stop. The previous recording's curve object can still exist briefly,
        # so we must decide from the fresh x/y data first instead of consulting
        # plot_curve here.
        x_displayed = np.asarray(x_data, dtype=float).reshape(-1)
        y_displayed = np.asarray(y_data, dtype=float).reshape(-1)
        if x_displayed.size == 0 or y_displayed.size == 0 or not np.isfinite(y_displayed).any():
            while labels:
                stale = labels.pop()
                try:
                    plot_widget.removeItem(stale)
                except Exception:
                    pass
            label_map.clear()
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
        label_points = self._spo2_label_points(
            x_displayed, y_displayed, y_data, time_window, stat=stat,
            step_tolerance=step_tolerance,
        )

        if not label_points:
            while labels:
                stale = labels.pop()
                try:
                    plot_widget.removeItem(stale)
                except Exception:
                    pass
            label_map.clear()
            return

        from PyQt5.QtGui import QFont
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)

        # Every number sits just above the trace and moves with it ("trace"), or all of
        # them share one constant-height row near the top of the plot ("row").
        # Scale the label gap with the visible range so zooming keeps it readable.
        try:
            _view_low, _view_high = plot_widget.getViewBox().viewRange()[1]
            offset_above = 0.02 * (float(_view_high) - float(_view_low))
        except Exception:
            offset_above = 0.35
        row_y = None
        if str(position).strip().lower() == "row":
            try:
                view_low, view_high = plot_widget.getViewBox().viewRange()[1]
                row_y = float(view_high) - float(SPO2_LABEL_ROOM_FRACTION) * (float(view_high) - float(view_low))
            except Exception:
                row_y = None

        if labels_attr == "value_labels" and DESAT_BOX_TWO_LABELS:
            label_points = self._desat_box_label_points(label_points, x_displayed, y_displayed)
        if LABEL_STEP_CLEARANCE_SEC > 0:
            label_points = self._drop_labels_near_steps(
                label_points, x_displayed, y_displayed,
                keep_nadir_in_boxes=(labels_attr == "value_labels"),
            )

        # Bind each TextItem to absolute recording time, not to its index in
        # the visible list. During playback the first bucket eventually leaves
        # the left edge. Index-based reuse then reassigned every existing item
        # to its neighbour, invalidating the entire text row in one paint and
        # producing the conspicuous digit flicker. With stable keys, overlapping
        # buckets keep the exact same item; only one item enters/leaves an edge.
        time_offset = self._spo2_label_time_offset()
        keyed_points = []
        duplicate_counts = {}
        for x_pos, y_pos, label_text in label_points:
            absolute_ms = int(round((float(x_pos) + time_offset) * 1000.0))
            occurrence = duplicate_counts.get(absolute_ms, 0)
            duplicate_counts[absolute_ms] = occurrence + 1
            keyed_points.append(((absolute_ms, occurrence), x_pos, y_pos, label_text))

        desired_keys = {point[0] for point in keyed_points}
        for key, stale in list(label_map.items()):
            if key in desired_keys:
                continue
            label_map.pop(key, None)
            try:
                labels.remove(stale)
            except ValueError:
                pass
            try:
                plot_widget.removeItem(stale)
            except Exception:
                pass

        # Labels created before time-keyed reuse was introduced have no entry
        # in label_map. Remove them once so they cannot remain as ghost digits.
        mapped_ids = {id(item) for item in label_map.values()}
        for stale in list(labels):
            if id(stale) in mapped_ids:
                continue
            labels.remove(stale)
            try:
                plot_widget.removeItem(stale)
            except Exception:
                pass

        for key, x_pos, y_pos, label_text in keyed_points:
            text_item = label_map.get(key)
            if text_item is None:
                text_item = pg.TextItem(
                    text=label_text,
                    color=color,
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
                labels.append(text_item)
                label_map[key] = text_item
                text_item._value_label_text = str(label_text)
            elif getattr(text_item, "_value_label_text", None) != str(label_text):
                # Avoid setText() for unchanged readings: it invalidates the
                # glyph layout and briefly clears/repaints the digit.
                text_item.setText(label_text)
                text_item._value_label_text = str(label_text)
            target_x = float(x_pos)
            target_y = float(row_y if row_y is not None else y_pos + offset_above)
            current_pos = text_item.pos()
            if (
                abs(float(current_pos.x()) - target_x) > 1e-6
                or abs(float(current_pos.y()) - target_y) > 1e-6
            ):
                text_item.setPos(target_x, target_y)
    
    
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
            pass
        elif event.button() == Qt.RightButton:
            # RIGHT CLICK logic
            if self.selection_start and self.selection_end:
                pass
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
        pass
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
            pass
    
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
    #
    #         # Update SpO2 value labels to match the new scaled data
    #         if plot_widget.chart_name.strip() == "SpO2" and hasattr(plot_widget, 'plot_curve'):
    #             current_data = plot_widget.plot_curve.getData()
    #             if current_data[0] is not None and len(current_data[0]) > 0:
    #                 x_data, y_data = current_data
    #                 # Recreate value labels with the scaled data positions
    #                 self.create_spo2_markers_and_labels(plot_widget, x_data, y_data)
    #
    #         from PyQt5.QtCore import QTimer
    #         QTimer.singleShot(100, lambda: self.force_range_update(plot_widget, low_value, high_value))
    #
    #     except Exception as e:
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
    #
    #     except Exception as e:
    
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
                pass

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
                    pass
                    self.show_selection_menu()
                else:
                
                    pass
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
        
        pass
        pass
        pass
        pass

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
        return chart_name in {"Airflow", "SpO2"} and bool(
            getattr(self, "loaded_recording_path", None)
        )

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
        pass
        if not self.current_selection_chart:
            pass
            return
        chart_name = self.current_selection_chart.chart_name.strip()
        if not self._selection_allowed_for_chart(chart_name):
            pass
            self.clear_selection()
            return
        pass
            
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
        pass
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
        pass
        from PyQt5.QtGui import QCursor
        global_cursor_pos = QCursor.pos()
        pass
        pass
        
      
        menu.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint | Qt.WindowStaysOnTopHint)
        menu.setFixedSize(menu.sizeHint())  
        menu.setWindowModality(Qt.ApplicationModal)
        
        # Store menu reference to prevent garbage collection
        self.active_context_menu = menu
        
        menu.exec_(global_cursor_pos)
        pass
        
        # Clear menu reference after it's closed
        self.active_context_menu = None
        
        # Menu closed without choosing a label (X / Esc / outside click) ->
        # clear the dragged area instead of preserving a stale preview overlay.
        if self.selection_active:
            pass
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
        # A user may drag in either direction. Store every selection in
        # chronological order so its duration, saved data and hit-testing are
        # never negative for a right-to-left drag.
        start_time_abs, end_time_abs = self._ordered_span(
            self.selection_start.x() + self.current_time_offset,
            self.selection_end.x() + self.current_time_offset,
        )

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
            pass
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
                sampling_rate = self.channel_rate("spo2")
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

        pass

        # clear temp selection
        self.selection_start = None
        self.selection_end = None
        self.selection_start_scene = None
        self.selection_end_scene = None
        self.current_selection_chart = None
    
    def handle_overlay_click(self, event, overlay, chart_name):
        """Handle right click on overlay"""
        pass
        if event.button() == Qt.RightButton:
            pass
            self.show_overlay_menu(event.globalPos(), overlay, chart_name)
        else:
            pass
    
    def handle_overlay_double_click(self, event, overlay, chart_name):
        """Double click = quick remove option"""
        self.show_overlay_menu(event.globalPos(), overlay, chart_name)
    
    def show_overlay_menu(self, global_pos, overlay, chart_name):
        """Show remove menu for overlay"""
        pass
        menu = QMenu(self)

        remove_action = QAction("Remove Selection", self)
        remove_action.triggered.connect(lambda: self.delete_overlay(overlay, chart_name))
        menu.addAction(remove_action)
        
        # Find the label index for this overlay
        label_index = self._find_label_index_for_overlay(overlay, chart_name)
        pass
        if label_index is not None:
            selection_data = self.selection_labels[chart_name][label_index]
            if selection_data.get("is_manually_edited"):
                menu.addSeparator()
                reset_action = QAction("Reset to auto label", self)
                reset_action.triggered.connect(lambda: self.reset_overlay_label_to_auto(chart_name, label_index))
                menu.addAction(reset_action)

            # Add Change Label option
            pass
            menu.addSeparator()
            change_action = QAction("Change Label...", self)
            change_action.triggered.connect(lambda: self.change_label(chart_name, label_index))
            menu.addAction(change_action)
        else:
            pass

        pass
        menu.exec_(global_pos)

    def reset_overlay_label_to_auto(self, chart_name, label_index):
        """Remove a manual override and restore the detector label."""
        if chart_name not in self.selection_labels or not (0 <= label_index < len(self.selection_labels[chart_name])):
            return

        selection = self.selection_labels[chart_name][label_index]
        if not self.reset_manual_label_for_event(selection):
            return

        self._refresh_auto_rule_ai_views()
        pass
    
    def _find_label_index_for_overlay(self, overlay, chart_name):
        """Find the label index for a given overlay"""
        overlay_id = getattr(overlay, 'selection_id', None)
        pass
        if overlay_id is None:
            pass
            return None
            
        if chart_name not in self.selection_labels:
            pass
            return None
            
        pass
        for i, selection_data in enumerate(self.selection_labels[chart_name]):
            selection_id = self._get_selection_id(selection_data)
            pass
            if selection_id == overlay_id:
                pass
                return i
        pass
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
        pass
    
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
        if self.is_playing or getattr(self, "_slider_scrubbing", False):
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
                            pass
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
            'APNEA': (176, 60, 90),
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
                pass
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
        pass
    

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
            pass
        return 0.0, 0.0, float(plot_widget.width()), float(plot_widget.height())

    def _overlay_left_limit(self, plot_widget, plot_left):
        try:
            axis = plot_widget.getAxis('left')
            if axis is None or not axis.isVisible():
                return plot_left
            line_local = axis.mapRectFromParent(axis.geometry()).topRight()
            line_scene = axis.mapToScene(line_local)
            axis_x = float(plot_widget.mapFromScene(line_scene).x())
            axis_x += float(plot_widget.viewport().x())
            try:
                half_pen = max(1.0, float(axis.pen().widthF())) / 2.0
            except Exception:
                half_pen = 0.5
            limit = axis_x + half_pen + float(OVERLAY_AXIS_INSET_PX)
            return max(float(plot_left), float(np.ceil(limit - 1e-6)))
        except Exception:
            return plot_left

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
        left = self._overlay_left_limit(plot_widget, left)

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
            # Compute pass-wide values once; every chart shares this window.
            _visible_window = self.get_effective_time_window_seconds()
            _all_psg = self.is_all_psg_mode()
            _max_duration = self._get_playback_max_duration() if _all_psg else 0.0
            _charts_to_repaint = []
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
                                if overlay.isVisible() and plot_widget not in _charts_to_repaint:
                                    _charts_to_repaint.append(plot_widget)   # a box was here: repaint its area
                                overlay.hide()
                                overlay.setGeometry(-1000, -1000, 1, 1)
                        except Exception as e:
                            pass
                            continue

                if chart_name not in self.dynamic_selections:
                    continue

                for selection_data in self.dynamic_selections[chart_name]:
                    try:
                        start_time_abs, end_time_abs = self._ordered_span(
                            selection_data['start_time'],
                            selection_data['end_time'],
                        )
                        # Geometry may begin at the visible SpO2 fall onset,
                        # while start_time_abs remains the scored detector time
                        # used by duration, navigation, deletion and reports.
                        box_start_time_abs = start_time_abs
                        try:
                            display_start = float(selection_data.get(
                                "display_start_time",
                                start_time_abs,
                            ))
                            if np.isfinite(display_start):
                                box_start_time_abs = min(start_time_abs, display_start)
                        except (TypeError, ValueError):
                            pass
                        if _all_psg:
                            start_time_rel = box_start_time_abs
                            end_time_rel = end_time_abs
                            visible_start = 0.0
                            visible_end = _max_duration
                        else:
                            start_time_rel = box_start_time_abs - self.current_time_offset
                            end_time_rel = end_time_abs - self.current_time_offset
                            visible_start = 0.0
                            visible_end = _visible_window

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
                            overlay.setAlignment(Qt.AlignHCenter | Qt.AlignBottom)
                            overlay.setWordWrap(False)
                            if not hasattr(plot_widget, 'selection_overlays'):
                                plot_widget.selection_overlays = []
                            plot_widget.selection_overlays.append(overlay)
                        else:
                            overlay.setAlignment(Qt.AlignHCenter | Qt.AlignBottom)
                            overlay.setWordWrap(False)

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
                            full_text = (
                                f"{display_label}  |  {start_str}  |  {duration_str}  |  "
                                f"{selection_data['spo2_info']}"
                            )
                            spo2_change_html = html_escape(str(selection_data['spo2_info']))
                            # The thin down-arrow disappeared visually inside the
                            # small event caption.  A filled, high-contrast marker
                            # makes the direction of the SpO2 drop unambiguous.
                            spo2_change_html = spo2_change_html.replace(
                                "↓",
                                '<span style="color: #991b1b; font-size: 12px; '
                                'font-weight: 900;">▼</span>',
                            )
                            rich_text = (
                                '<span style="white-space: nowrap; font-weight: 600;">'
                                f'{html_escape(display_label)}&nbsp;&nbsp;|&nbsp;&nbsp;'
                                f'<span style="font-weight: 900;">{html_escape(start_str)}</span>'
                                '&nbsp;&nbsp;|&nbsp;&nbsp;'
                                f'<span style="font-weight: 900;">{html_escape(duration_str)}</span>'
                                '&nbsp;&nbsp;|&nbsp;&nbsp;'
                                f'<span style="font-weight: 900;">{spo2_change_html}</span>'
                                '</span>'
                            )
                        else:
                            full_text = f"{display_label}  |  {start_str}  |  {duration_str}"
                            rich_text = (
                                '<span style="white-space: nowrap; font-weight: 600;">'
                                f'{html_escape(display_label)}&nbsp;&nbsp;|&nbsp;&nbsp;'
                                f'<span style="font-weight: 900;">{html_escape(start_str)}</span>'
                                '&nbsp;&nbsp;|&nbsp;&nbsp;'
                                f'<span style="font-weight: 900;">{html_escape(duration_str)}</span>'
                                '</span>'
                            )
                        overlay.setTextFormat(Qt.RichText)
                        overlay.setText(rich_text)
                        overlay.setToolTip(full_text)
                        overlay_style = f"""
                            background-color: {selection_data['color']};
                            border: none;
                            border-radius: 0px;
                            color: #1a1a1a;
                            font-size: 9px;
                            font-weight: 600;
                            padding: 1px 3px;
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
                            overlay._playback_span = (float(box_start_time_abs), float(end_time_abs))
                            # Keep the original full-height event box.  Only the
                            # text layout changes: one row at the bottom leaves
                            # the SpO2 readings at the top unobstructed.
                            placed = self._place_overlay_in_plot_area(
                                plot_widget,
                                overlay,
                                start_widget.x(),
                                end_widget.x(),
                            )
                            if not placed:
                                continue
                            overlay.show()
                            if plot_widget not in _charts_to_repaint:
                                _charts_to_repaint.append(plot_widget)   # a box is here now

                            pass
                    except Exception as e:
                        pass
                        continue
            if OVERLAY_FORCE_REPAINT:
                for _chart in _charts_to_repaint:
                    try:
                        _chart.update()
                    except Exception:
                        pass
        except Exception as e:
            pass
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
            recording_path = getattr(self, "current_recording_path", None) or getattr(
                self, "loaded_recording_path", None
            )
            if not recording_path:
                return None

            recording_filename = os.path.basename(recording_path)
            recording_base = os.path.splitext(recording_filename)[0]
            import glob
            analysis_dirs = [
                Path(recording_path).parent.parent / "analysis_json",
                get_configured_path("analysis_json_dir"),
            ]
            files = []
            for analysis_dir in analysis_dirs:
                if analysis_dir.exists():
                    files.extend(glob.glob(str(analysis_dir / f"{recording_base}_analysis_*.json")))
            if files:
                return max(set(files), key=os.path.getctime)
            return None
        except Exception as error:
            pass
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
            pass
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
            pass
            pass

        for segment in sensor_off_segments:
            start_sec = float(segment.get("start_sec", 0.0))
            end_sec = float(segment.get("end_sec", 0.0))
            if not time_values.size:
                continue

            direct_mask = (time_values >= start_sec) & (time_values <= end_sec)
            if np.any(direct_mask):
                masked_airflow[direct_mask] = baseline
                pass
                continue

            # If the supplied time array is offset from the segment clock,
            # fall back to a zero-based view for debugging and masking.
            shifted_time_values = time_values - float(time_values[0])
            shifted_mask = (shifted_time_values >= start_sec) & (shifted_time_values <= end_sec)
            if np.any(shifted_mask):
                masked_airflow[shifted_mask] = baseline
                pass
            else:
                pass
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
                pass
            pass
        except Exception as error:
            pass
        return segments

    # Airflow "dead sensor" flatness test (display units, after enhancement).
    FLAT_AIRFLOW_P2P_MAX = 7.0
    FLAT_AIRFLOW_WINDOW_SEC = 10.0
    FLAT_AIRFLOW_MIN_SEC = 90.0

    def _detect_flat_airflow_segments(self, display_airflow, time_data):
        """Return stretches where airflow is nothing but sensor noise."""
        values = np.asarray(display_airflow, dtype=float).reshape(-1)
        times = np.asarray(time_data, dtype=float).reshape(-1)
        count = min(values.size, times.size)
        if count < 2:
            return []
        values = values[:count]
        times = times[:count]
        window = max(3, int(round(self.FLAT_AIRFLOW_WINDOW_SEC * self.channel_rate("airflow"))))
        series = pd.Series(values)
        rolling_max = series.rolling(window, center=True, min_periods=window // 2).max()
        rolling_min = series.rolling(window, center=True, min_periods=window // 2).min()
        p2p = (rolling_max - rolling_min).to_numpy(dtype=float)
        flat = np.isfinite(p2p) & (p2p < self.FLAT_AIRFLOW_P2P_MAX)
        edges = np.diff(np.r_[0, flat.astype(np.int8), 0])
        starts = np.flatnonzero(edges == 1)
        ends = np.flatnonzero(edges == -1)
        segments = []
        for start, end in zip(starts, ends):
            last = min(end, count - 1)
            duration = float(times[last] - times[start])
            if duration < self.FLAT_AIRFLOW_MIN_SEC:
                continue
            segments.append({
                "start_sec": float(times[start]),
                "end_sec": float(times[last]),
                "duration_sec": duration,
                "reason": "airflow_flat_sensor_noise_only",
            })
        return segments

    def _apply_sensor_off_masking_after_detection(self):
        """Flatten the airflow DISPLAY trace where the sensor delivered no signal."""
        try:
            result = getattr(self, "auto_rule_ai_result", None)
            sensor_off_segments = list(result.get("sensor_off_segments", []) if result else [])

            current_psg_data = getattr(self, "current_psg_data", None) or getattr(self, "psg_full_data", None)
            if not isinstance(current_psg_data, dict):
                self.sensor_off_shade_segments = sensor_off_segments
                return
            time_data = np.asarray(current_psg_data.get("time", []), dtype=float)
            signals = current_psg_data.get("signals", {})
            if "airflow_display" not in signals or len(signals["airflow_display"]) == 0:
                self.sensor_off_shade_segments = sensor_off_segments
                return

            display_source = signals.get(
                "airflow_display_base",
                signals.get("airflow_enhanced", signals["airflow_display"]),
            )
            display = np.array(display_source, dtype=float, copy=True)
            count = min(len(display), len(time_data))
            display = display[:count]
            time_data = time_data[:count]

            flat_segments = self._detect_flat_airflow_segments(display, time_data)
            all_segments = sorted(
                sensor_off_segments + flat_segments,
                key=lambda item: float(item.get("start_sec", 0.0)),
            )

            merged = []
            for segment in all_segments:
                try:
                    start_sec = float(segment.get("start_sec", 0.0))
                    end_sec = float(segment.get("end_sec", start_sec))
                except (TypeError, ValueError):
                    continue
                if end_sec <= start_sec:
                    continue
                reason = str(segment.get("reason", ""))
                if merged and start_sec <= merged[-1]["end_sec"] + 1.0:
                    merged[-1]["end_sec"] = max(merged[-1]["end_sec"], end_sec)
                    merged[-1]["duration_sec"] = merged[-1]["end_sec"] - merged[-1]["start_sec"]
                    reasons = set(merged[-1]["reason"].split("+")) | {reason}
                    merged[-1]["reason"] = "+".join(sorted(r for r in reasons if r))
                else:
                    merged.append({
                        "start_sec": start_sec,
                        "end_sec": end_sec,
                        "duration_sec": end_sec - start_sec,
                        "reason": reason,
                    })
            self.sensor_off_shade_segments = merged

            pass
            pass
            for segment in merged[:10]:
                pass
            pass

            flattened = 0
            for segment in merged:
                start_idx = int(np.searchsorted(time_data, segment["start_sec"], side="left"))
                end_idx = int(np.searchsorted(time_data, segment["end_sec"], side="right"))
                if end_idx - start_idx < 2:
                    continue
                chunk = display[start_idx:end_idx]
                finite = chunk[np.isfinite(chunk)]
                if finite.size == 0:
                    continue
                display[start_idx:end_idx] = float(np.median(finite))
                flattened += end_idx - start_idx
            signals["airflow_display"] = display
            pass
        except Exception as error:
            pass


