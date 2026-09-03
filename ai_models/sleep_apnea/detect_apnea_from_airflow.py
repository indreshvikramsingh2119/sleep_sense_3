#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.signal import find_peaks

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))
PROJECT_ROOT = CURRENT_DIR.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from .hybrid_pipeline_common import (
        DEFAULT_OUTPUT_DIR,
        create_event_window_image,
        estimate_sample_rate_hz,
        load_cnn_model_bundle,
        load_sleep_csv,
        predict_event_image,
        preprocess_signals,
    )
except ImportError:
    from hybrid_pipeline_common import (
        DEFAULT_OUTPUT_DIR,
        create_event_window_image,
        estimate_sample_rate_hz,
        load_cnn_model_bundle,
        load_sleep_csv,
        predict_event_image,
        preprocess_signals,
    )

from src.utils.sample_rate import DEFAULT_SAMPLE_RATE_HZ

try:
    from src.components.airflow_display_processing import enhance_airflow_for_graph_and_detection
except ImportError:
    enhance_airflow_for_graph_and_detection = None


SKIP_MINUTES = 2.0
BASELINE_HOURLY_WINDOW_SEC = 3600.0
MIN_EVENT_SEC = 10.0
MAX_EVENT_SEC = 120.0
MIN_STABLE_OCCURRENCE = 30
MIN_STABLE_OCCURRENCE_PERCENT = 5.0
MIN_STABLE_OCCURRENCE_FLOOR = 10
BASELINE_TARGET_OCCURRENCE = 500
BASELINE_OCCURRENCE_TOLERANCE = 50
CANDIDATE_WINDOW_SEC = 1.0
CORE_MIN_SEC = 3.0
# AASM: event continues as long as airflow stays below the hypopnea floor (30%).
EVENT_BOUNDARY_DROP_PERCENT = 30.0
MERGE_GAP_SEC = 0.0
PULSE_FLATLINE_STD_BPM = 1.5
PULSE_FLATLINE_MIN_UNIQUE_RATIO = 0.05


def _pulse_looks_artifactual(pulse_segment: np.ndarray) -> bool:
    """Return True when pulse data looks flat or unnaturally stepped."""
    values = np.asarray(pulse_segment, dtype=float).reshape(-1)
    values = values[np.isfinite(values) & (values > 0)]
    if values.size < 10:
        return False
    standard_deviation = float(np.std(values))
    unique_ratio = float(np.unique(values).size / values.size)
    return (
        standard_deviation < PULSE_FLATLINE_STD_BPM
        or unique_ratio <= PULSE_FLATLINE_MIN_UNIQUE_RATIO
    )

# ---------------------------------------------------------------------------
# AASM scoring rules
# ---------------------------------------------------------------------------
# Hypopnea: airflow reduced >=30%, AND SpO2 desaturation >=3% (AASM
# "recommended" rule). The alternative AASM rule allows arousal instead of
# desaturation, but this device has no EEG/arousal signal, so only the
# desaturation path is usable here.
AASM_HYPOPNEA_DROP_PERCENT = 30.0
AASM_HYPOPNEA_SPO2_DESAT_MIN = 3.0
# Apnea (Obstructive/Central/Mixed): airflow reduced >=75%.
AASM_APNEA_DROP_PERCENT = 75.0
# Obstructive vs Central is decided by breathing effort (Thorax/Abdomen), not
# by how deep the airflow drop is. ResMed-style two-threshold band: below
# OBSTRUCTIVE_APNEA_EFFORT_THRESHOLD, effort is "absent"; at/above
# CENTRAL_APNEA_EFFORT_THRESHOLD, effort is clearly "present"; the band
# between the two is "borderline". A CSA verdict is only finalized if the
# whole event's effort amplitude also clears the stricter
# CENTRAL_APNEA_AMPLITUDE_CONFIRM_RATIO floor (ResMed's "Amplitude threshold
# for central apnea") -- otherwise it is downgraded to MSA.
OBSTRUCTIVE_APNEA_EFFORT_THRESHOLD = 0.20
CENTRAL_APNEA_EFFORT_THRESHOLD = 0.60
CENTRAL_APNEA_AMPLITUDE_CONFIRM_RATIO = 0.08
DESAT_DROP_PERCENT = 3.0
DESAT_LINK_WINDOW_SEC = 30.0
DESAT_BASELINE_LOOKBACK_SEC = 60.0   # how far back the pre-desat baseline is taken
# The fall must also be a fall against the RECENT level, not just against the
# best value in the last minute. On a slow drift (99 -> 98 -> 97 -> 96 over a
# minute) the 60 s p90 keeps quoting a value half a minute old and manufactures
# a 3% "desaturation" where nothing ever fell. This is checked only at ONSET;
# once a desaturation has started it runs on the normal baseline, so a long
# event is not truncated when SpO2 sits at its new low level.
DESAT_RECENT_BASELINE_SEC = 20.0

# ---------------------------------------------------------------------------
# Adjustable analysis parameters (Settings -> Analysis parameters bridge)
# ---------------------------------------------------------------------------
_ADJUSTABLE_DEFAULTS = {
    "AASM_HYPOPNEA_DROP_PERCENT": AASM_HYPOPNEA_DROP_PERCENT,
    "AASM_APNEA_DROP_PERCENT": AASM_APNEA_DROP_PERCENT,
    "AASM_HYPOPNEA_SPO2_DESAT_MIN": AASM_HYPOPNEA_SPO2_DESAT_MIN,
    "OBSTRUCTIVE_APNEA_EFFORT_THRESHOLD": OBSTRUCTIVE_APNEA_EFFORT_THRESHOLD,
    "CENTRAL_APNEA_EFFORT_THRESHOLD": CENTRAL_APNEA_EFFORT_THRESHOLD,
    "CENTRAL_APNEA_AMPLITUDE_CONFIRM_RATIO": CENTRAL_APNEA_AMPLITUDE_CONFIRM_RATIO,
    "MIN_EVENT_SEC": MIN_EVENT_SEC,
    "MAX_EVENT_SEC": MAX_EVENT_SEC,
}


# Registered here, not in the _ADJUSTABLE_DEFAULTS literal above: that dict is
# built long before this constant exists, so naming it there would be a
# NameError at import.
_ADJUSTABLE_DEFAULTS["DESAT_DROP_PERCENT"] = DESAT_DROP_PERCENT


def get_analysis_parameters() -> dict[str, Any]:
    """Return the currently active adjustable detection parameters."""
    return {key: globals()[key] for key in _ADJUSTABLE_DEFAULTS}


def get_default_analysis_parameters() -> dict[str, Any]:
    """Return the built-in default parameters without changing live settings."""
    return dict(_ADJUSTABLE_DEFAULTS)


def apply_analysis_parameters(values: dict[str, Any]) -> None:
    """Override adjustable detection parameters at runtime."""
    for key, value in values.items():
        if key in _ADJUSTABLE_DEFAULTS:
            globals()[key] = value


def reset_analysis_parameters() -> None:
    """Restore all adjustable detection parameters to their built-in defaults."""
    apply_analysis_parameters(_ADJUSTABLE_DEFAULTS)


@dataclass
class DetectedApneaEvent:
    event_id: int
    start_sec: float
    end_sec: float
    duration_sec: float
    baseline_airflow: float
    event_min_airflow: float
    event_mean_airflow: float
    event_peak_airflow: float
    event_airflow_amplitude: float
    airflow_amplitude_ratio: float
    airflow_drop_percent: float
    spo2_drop: float
    snoring_mean: float
    movement_mean: float
    variability_score: float
    rule_label: str
    spo2_confirmed: bool = True
    desat_nadir_sec: float | None = None
    desat_nadir_spo2: float | None = None
    desat_baseline_spo2: float | None = None
    ai_label: str | None = None
    ai_confidence: float | None = None
    final_label: str | None = None
    image_path: str | None = None
    evidence: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def stable_max(values: pd.Series | np.ndarray, min_occurrence: int = MIN_STABLE_OCCURRENCE) -> tuple[float, int]:
    series = pd.Series(values).dropna()
    series = pd.to_numeric(series, errors="coerce").dropna()
    rounded = series.round(2)
    counts = rounded.value_counts()
    candidates = [
        (float(value), int(count))
        for value, count in counts.items()
        if int(count) >= int(min_occurrence)
    ]
    if candidates:
        candidates.sort(key=lambda item: (item[1], item[0]), reverse=True)
        return candidates[0]
    fallback_value = float(counts.idxmax())
    fallback_count = int(counts.max())
    return fallback_value, fallback_count


def stable_peak_max(
    values: pd.Series | np.ndarray,
    min_occurrence: int = MIN_STABLE_OCCURRENCE,
) -> tuple[float, int, np.ndarray]:
    series = pd.Series(values).dropna()
    series = pd.to_numeric(series, errors="coerce").dropna()
    if series.empty:
        return 0.0, 0, np.array([], dtype=int)

    signal = series.to_numpy(dtype=float)
    peak_indices, _ = find_peaks(signal)
    if len(peak_indices) == 0:
        value, count = stable_max(signal, min_occurrence=min_occurrence)
        fallback_indices = np.where(np.round(signal, 2) == round(value, 2))[0]
        return value, count, fallback_indices

    peak_values = pd.Series(signal[peak_indices]).round(2)
    counts = peak_values.value_counts()
    candidates = [
        (float(value), int(count))
        for value, count in counts.items()
        if int(count) >= int(min_occurrence)
    ]
    if candidates:
        candidates.sort(key=lambda item: (item[1], item[0]), reverse=True)
        selected_value, selected_count = candidates[0]
    else:
        selected_value = float(counts.idxmax())
        selected_count = int(counts.max())

    selected_indices = peak_indices[np.round(signal[peak_indices], 2) == round(selected_value, 2)]
    return selected_value, selected_count, selected_indices


def _percent_based_min_occurrence(
    window_signal: np.ndarray,
    percent: float = MIN_STABLE_OCCURRENCE_PERCENT,
    floor: int = MIN_STABLE_OCCURRENCE_FLOOR,
) -> int:
    """Scale the minimum-occurrence requirement to the local window."""
    series = pd.Series(window_signal).dropna()
    series = pd.to_numeric(series, errors="coerce").dropna()
    if series.empty:
        return int(floor)

    peak_indices, _ = find_peaks(series.to_numpy(dtype=float))
    total_peaks = len(peak_indices)
    if total_peaks <= 0:
        return int(floor)
    return max(int(floor), int(total_peaks * percent / 100.0))


def compute_hourly_peak_baselines(
    time_sec: np.ndarray,
    airflow: np.ndarray,
    skip_sec: float,
) -> list[dict[str, float | int | None]]:
    hourly_results: list[dict[str, float | int | None]] = []
    analysis_end_sec = float(time_sec[-1]) if len(time_sec) else skip_sec
    window_start = float(skip_sec)
    window_index = 1
    full_window_end_limit = analysis_end_sec - BASELINE_HOURLY_WINDOW_SEC

    while window_start <= full_window_end_limit + 1e-9:
        window_end = window_start + BASELINE_HOURLY_WINDOW_SEC
        window_mask = (time_sec >= window_start) & (time_sec < window_end)
        window_airflow = airflow[window_mask]
        window_time = time_sec[window_mask]
        if len(window_airflow) == 0:
            window_start += BASELINE_HOURLY_WINDOW_SEC
            window_index += 1
            continue

        window_min_occurrence = _percent_based_min_occurrence(window_airflow)
        peak_value, peak_occurrence, peak_indices = stable_peak_max(
            window_airflow,
            min_occurrence=window_min_occurrence,
        )
        peak_times = window_time[peak_indices] if len(peak_indices) > 0 else np.array([], dtype=float)
        hourly_results.append(
            {
                "window_index": int(window_index),
                "window_label": f"Hour {window_index}",
                "window_type": "hour",
                "start_sec": float(window_start),
                "end_sec": float(window_end),
                "duration_sec": float(window_end - window_start),
                "peak_value": float(peak_value),
                "peak_occurrence": int(peak_occurrence),
                "peak_first_time_sec": float(peak_times[0]) if len(peak_times) > 0 else None,
                "peak_last_time_sec": float(peak_times[-1]) if len(peak_times) > 0 else None,
            }
        )

        window_index += 1
        window_start += BASELINE_HOURLY_WINDOW_SEC

    remainder_start = float(skip_sec) + (window_index - 1) * BASELINE_HOURLY_WINDOW_SEC
    remainder_duration_sec = float(analysis_end_sec - remainder_start)
    if remainder_duration_sec > 0:
        remainder_end = analysis_end_sec + 1e-9
        remainder_mask = (time_sec >= remainder_start) & (time_sec <= analysis_end_sec)
        remainder_airflow = airflow[remainder_mask]
        remainder_time = time_sec[remainder_mask]
        if len(remainder_airflow) > 0:
            remainder_min_occurrence = _percent_based_min_occurrence(remainder_airflow)
            peak_value, peak_occurrence, peak_indices = stable_peak_max(
                remainder_airflow,
                min_occurrence=remainder_min_occurrence,
            )
            peak_times = remainder_time[peak_indices] if len(peak_indices) > 0 else np.array([], dtype=float)
            hourly_results.append(
                {
                    "window_index": int(window_index),
                    "window_label": "Remainder Window",
                    "window_type": "remainder",
                    "start_sec": float(remainder_start),
                    "end_sec": float(remainder_end),
                    "duration_sec": float(remainder_duration_sec),
                    "peak_value": float(peak_value),
                    "peak_occurrence": int(peak_occurrence),
                    "peak_first_time_sec": float(peak_times[0]) if len(peak_times) > 0 else None,
                    "peak_last_time_sec": float(peak_times[-1]) if len(peak_times) > 0 else None,
                }
            )

    return hourly_results


def stable_min_from_occurrence_band(
    values: pd.Series | np.ndarray,
    target_occurrence: int = BASELINE_TARGET_OCCURRENCE,
    tolerance: int = BASELINE_OCCURRENCE_TOLERANCE,
) -> tuple[float, int]:
    series = pd.Series(values).dropna()
    series = pd.to_numeric(series, errors="coerce").dropna()

    rounded = series.round(2)
    counts = rounded.value_counts().sort_index(ascending=True)

    lower = target_occurrence - tolerance
    upper = target_occurrence + tolerance

    candidates: list[tuple[float, int]] = []
    for value, count in counts.items():
        if lower <= int(count) <= upper:
            candidates.append((float(value), int(count)))

    if candidates:
        candidates.sort(key=lambda item: item[0])
        return candidates[0]

    closest: list[tuple[float, int]] = []
    min_diff: int | None = None
    for value, count in counts.items():
        diff = abs(int(count) - target_occurrence)
        if min_diff is None or diff < min_diff:
            min_diff = diff
            closest = [(float(value), int(count))]
        elif diff == min_diff:
            closest.append((float(value), int(count)))

    closest.sort(key=lambda item: item[0])
    return closest[0]


def compute_pre_event_baseline(
    time_sec: np.ndarray,
    airflow: np.ndarray,
    event_start_sec: float,
    pre_event_window_sec: float = 120.0,
    stability_cv_threshold: float = 0.25,
    fallback_baseline: float | None = None,
) -> tuple[float, str]:
    """AASM-style baseline from the 2 minutes before event onset."""
    window_mask = (time_sec >= event_start_sec - pre_event_window_sec) & (time_sec < event_start_sec)
    window_airflow = airflow[window_mask]
    if len(window_airflow) < 3:
        return (float(fallback_baseline) if fallback_baseline else 0.0), "insufficient_data"

    breath_indices, _ = find_peaks(window_airflow)
    if len(breath_indices) == 0:
        return float(np.nanmax(window_airflow)), "no_breaths_found"

    breath_amplitudes = window_airflow[breath_indices]
    mean_amp = float(np.mean(breath_amplitudes))
    std_amp = float(np.std(breath_amplitudes))
    cv = std_amp / mean_amp if mean_amp else 0.0

    if cv <= stability_cv_threshold:
        return mean_amp, "stable"

    largest_three = np.sort(breath_amplitudes)[-3:] if len(breath_amplitudes) >= 3 else breath_amplitudes
    return float(np.mean(largest_three)), "unstable"


# ---------------------------------------------------------------------------
# AASM amplitude engine (peak-to-trough, drift/DC-offset immune)
# ---------------------------------------------------------------------------
BREATH_WINDOW_SEC = 5.0            # one breath cycle fits in this window
ROLLING_BASELINE_WINDOW_SEC = 120.0  # AASM pre-event baseline window
ROLLING_BASELINE_STEP_SEC = 1.0    # baseline recomputed on a 1 s grid
BASELINE_CV_THRESHOLD = 0.25       # stable vs unstable window
BASELINE_EXCLUDE_FIRST_SEC = 45.0
# The 5 s breath window is right for measuring breathing amplitude, but it
# SMEARS the edges of a flat stretch (~2.5 s lost per side), so a genuine 11 s
# apnea measures as 7 s and fails the 10 s rule. Apnea-core DURATION is
# therefore re-measured with a short window.
APNEA_CORE_WINDOW_SEC = 1.0
# Effort belts: a real breath is a peak with prominence >= this fraction of the
# baseline breath amplitude. Quantisation noise never clears it, so counting
# breaths tells "effort absent" apart from "small but present effort".
EFFORT_BREATH_PROMINENCE_RATIO = 0.35
EFFORT_MIN_BREATH_RATE_PER_MIN = 6.0
# Breathing is RHYTHMIC. One lone blip is not a breath -- on a low-resolution
# belt a single quantisation step can clear the prominence test and, divided by
# a short half-event, fake a "10 breaths/min" rate. Require at least two peaks
# so there is at least one real breath-to-breath interval.
EFFORT_MIN_BREATH_PEAKS = 2
# Effort amplitude is measured inside one breath-length window so that slow
# belt drift does not masquerade as breathing.
EFFORT_BREATH_WINDOW_SEC = 3.0

# ---------------------------------------------------------------------------
# Sensor-off / dislodged-cannula detection
# ---------------------------------------------------------------------------
# A dislodged/blocked nasal cannula kills airflow while the chest belt keeps
# moving. A real central apnea silences both, so effort distinguishes them.
SENSOR_OFF_MIN_SEC = 60.0
SENSOR_OFF_AIRFLOW_RATIO = 0.12
SENSOR_OFF_ERRATIC_RATIO = 1.75
SENSOR_OFF_THORAX_MIN_RATIO = 0.20
SENSOR_OFF_MIN_DEAD_CORE_SEC = 30.0
SENSOR_OFF_RECOVERY_STABLE_SEC = 5.0
SENSOR_OFF_NORMAL_RATIO_BAND = (0.5, 1.4)
SENSOR_OFF_REFERENCE_PERCENTILE = 90.0
SENSOR_OFF_EVENT_OVERLAP_RATIO = 0.5
LONG_EVENT_SENSOR_SUSPECT_SEC = 90.0


def _continuous_breath_amplitude(
    airflow: np.ndarray,
    fs: float,
    breath_window_sec: float = BREATH_WINDOW_SEC,
) -> np.ndarray:
    """Per-sample breathing amplitude = (rolling max - rolling min) within one
    breath-sized window. Because it is a difference, any DC offset or slow
    sensor drift cancels out -- this is what makes drop%% valid on
    uncalibrated hardware where 'zero flow' is not stored as 0."""
    window_points = max(3, int(round(fs * breath_window_sec)))
    series = pd.Series(np.asarray(airflow, dtype=float))
    upper = series.rolling(window=window_points, center=True, min_periods=1).max()
    lower = series.rolling(window=window_points, center=True, min_periods=1).min()
    return (upper - lower).to_numpy(dtype=float)


def _rolling_aasm_baseline(
    amplitude: np.ndarray,
    fs: float,
    window_sec: float = ROLLING_BASELINE_WINDOW_SEC,
    cv_threshold: float = BASELINE_CV_THRESHOLD,
    step_sec: float = ROLLING_BASELINE_STEP_SEC,
) -> np.ndarray:
    """AASM-style baseline for every sample: the mean breathing amplitude of
    the PRECEDING 2 minutes; if that window is unstable (CV > 0.25), the 90th
    percentile of it (~= the largest breaths, AASM's 'largest 3' rule).
    Computed on a 1 s grid and interpolated back for speed."""
    amp = np.asarray(amplitude, dtype=float)
    n = len(amp)
    if n == 0:
        return amp
    step = max(1, int(round(fs * step_sec)))
    win = max(step, int(round(fs * window_sec)))

    # Settling breaths at the start of the recording are excluded as baseline
    # SOURCES (they can still be scored themselves once real history exists).
    amp_source = amp.copy()
    exclude_points = min(n, int(round(fs * BASELINE_EXCLUDE_FIRST_SEC)))
    amp_source[:exclude_points] = np.nan
    global_fallback = float(np.nanmedian(amp_source)) if np.any(np.isfinite(amp_source)) else float(np.nanmedian(amp))

    grid = np.arange(0, n, step)
    baseline_grid = np.empty(len(grid), dtype=float)
    for gi, i in enumerate(grid):
        lo = max(0, i - win)
        window = amp_source[lo:i] if i > lo else amp_source[: max(1, step)]
        valid = int(np.sum(np.isfinite(window)))
        if valid == 0:
            baseline_grid[gi] = global_fallback
            continue
        mean_val = float(np.nanmean(window))
        std_val = float(np.nanstd(window))
        cv = std_val / (mean_val + 1e-9)
        if cv <= cv_threshold or valid < int(fs * 30):
            baseline_grid[gi] = mean_val
        else:
            baseline_grid[gi] = float(np.nanpercentile(window, 90))
    return np.interp(np.arange(n, dtype=float), grid.astype(float), baseline_grid)


def _refine_apnea_core(
    core_start: int,
    core_end: int,
    drop_short: np.ndarray,
    drop_threshold: float = AASM_APNEA_DROP_PERCENT,
) -> tuple[int, int]:
    """Re-measure a >=75% core using the SHORT-window drop array.

    The core was found on the 5 s smoothed drop array, which loses ~2.5 s at
    each edge of a flat stretch. Expanding outward on the 1 s array recovers
    the true length so the AASM 10 s rule is applied to the real duration.
    """
    n = len(drop_short)
    start = int(core_start)
    end = int(core_end)
    while start - 1 >= 0 and drop_short[start - 1] >= drop_threshold:
        start -= 1
    while end + 1 < n and drop_short[end + 1] >= drop_threshold:
        end += 1
    return start, end


def _effort_breath_rate(segment: np.ndarray | None, baseline_amp: float, fs: float) -> float:
    """Breaths per minute visible on an effort belt segment."""
    if segment is None or baseline_amp <= 0:
        return 0.0
    values = np.asarray(segment, dtype=float)
    duration_min = len(values) / fs / 60.0
    if duration_min <= 0 or len(values) < int(fs * 2):
        return 0.0
    peaks, _ = find_peaks(
        values,
        distance=max(2, int(fs * 1.2)),
        prominence=EFFORT_BREATH_PROMINENCE_RATIO * baseline_amp,
    )
    if len(peaks) < EFFORT_MIN_BREATH_PEAKS:
        return 0.0
    return float(len(peaks)) / duration_min


def _global_amplitude_reference(
    amplitude: np.ndarray,
    fs: float,
    exclude_first_sec: float = BASELINE_EXCLUDE_FIRST_SEC,
    percentile: float = SENSOR_OFF_REFERENCE_PERCENTILE,
) -> float:
    """Return a fixed whole-recording amplitude reference."""
    amp = np.asarray(amplitude, dtype=float)
    n = len(amp)
    if n == 0:
        return 0.0
    exclude_points = min(n, int(round(fs * exclude_first_sec)))
    source = amp[exclude_points:]
    source = source[np.isfinite(source)]
    if source.size == 0:
        source = amp[np.isfinite(amp)]
    if source.size == 0:
        return 0.0
    return float(np.nanpercentile(source, percentile))


def detect_sensor_off_segments(
    airflow: np.ndarray,
    thorax: np.ndarray | None,
    fs: float,
    time_sec: np.ndarray,
    min_duration_sec: float = SENSOR_OFF_MIN_SEC,
    airflow_dead_ratio: float = SENSOR_OFF_AIRFLOW_RATIO,
    erratic_ratio: float = SENSOR_OFF_ERRATIC_RATIO,
    thorax_min_ratio: float = SENSOR_OFF_THORAX_MIN_RATIO,
    min_dead_core_sec: float = SENSOR_OFF_MIN_DEAD_CORE_SEC,
) -> list[dict[str, Any]]:
    """Find prolonged airflow dropouts while thorax effort continues."""
    airflow = np.asarray(airflow, dtype=float)
    n = len(airflow)
    if n == 0 or thorax is None or len(thorax) != n:
        return []

    airflow_amp = _continuous_breath_amplitude(airflow, fs)
    thorax_amp = _continuous_breath_amplitude(np.asarray(thorax, dtype=float), fs)
    airflow_ref = _global_amplitude_reference(airflow_amp, fs)
    thorax_ref = _global_amplitude_reference(thorax_amp, fs)
    if airflow_ref <= 0:
        return []

    airflow_ratio = airflow_amp / max(airflow_ref, 1e-9)
    thorax_ratio = (
        thorax_amp / max(thorax_ref, 1e-9)
        if thorax_ref > 0
        else np.full(n, np.nan)
    )
    dead_mask = (airflow_ratio <= airflow_dead_ratio) & (thorax_ratio >= thorax_min_ratio)
    unreliable_mask = (
        (airflow_ratio <= airflow_dead_ratio) | (airflow_ratio >= erratic_ratio)
    ) & (thorax_ratio >= thorax_min_ratio)
    raw_segments = _segment_mask(unreliable_mask, time_sec, min_duration_sec)

    results: list[dict[str, Any]] = []
    for start_idx, end_idx, _duration_sec in raw_segments:
        dead_sec = int(np.count_nonzero(dead_mask[start_idx:end_idx + 1])) / fs
        if dead_sec < min_dead_core_sec:
            continue
        # Keep the segment limited to the genuinely dead/erratic range.
        # Extending backward can swallow weak but real breathing into the
        # sensor-off marker.
        idx = start_idx
        results.append({
            "start_sec": float(time_sec[idx]),
            "end_sec": float(time_sec[end_idx]),
            "duration_sec": float(time_sec[end_idx] - time_sec[idx]),
            "dead_core_sec": float(dead_sec),
            "reason": "airflow_unreliable_effort_present",
        })

    results.sort(key=lambda item: item["start_sec"])
    merged: list[dict[str, Any]] = []
    for segment in results:
        if merged and segment["start_sec"] <= merged[-1]["end_sec"] + 1.0:
            merged[-1]["end_sec"] = max(merged[-1]["end_sec"], segment["end_sec"])
            merged[-1]["duration_sec"] = merged[-1]["end_sec"] - merged[-1]["start_sec"]
            merged[-1]["dead_core_sec"] += segment["dead_core_sec"]
        else:
            merged.append(segment)
    return merged


def _extend_boundary_through_flat(
    local_start: int,
    local_end: int,
    airflow_arr: np.ndarray,
    baseline_amp: float,
    fs: float,
    time_arr: np.ndarray,
    max_event_sec: float = MAX_EVENT_SEC,
    short_window_sec: float = 1.0,
    breath_present_ratio: float = 0.30,
) -> tuple[int, int]:
    """Fix the centered-window smear at event edges.

    The 5 s centered amplitude window 'sees' the recovery breath ~2.5 s
    before it visually starts, so the event end lands a couple of seconds
    early and leaves a flat sliver outside the box (same on the start side).
    Extend each boundary through truly-flat samples using a SHORT 1 s
    window: keep extending while no breath >= 30% of baseline is present.
    """
    n = len(airflow_arr)
    w = max(2, int(round(fs * short_window_sec)))
    threshold = breath_present_ratio * max(float(baseline_amp), 1e-9)
    start = int(local_start)
    end = int(local_end)

    while end + 1 < n:
        if float(time_arr[end + 1] - time_arr[start]) > max_event_sec:
            break
        segment = airflow_arr[end + 1: min(n, end + 1 + w)]
        if len(segment) == 0 or float(np.nanmax(segment) - np.nanmin(segment)) >= threshold:
            break
        end += 1

    while start - 1 >= 0:
        if float(time_arr[end] - time_arr[start - 1]) > max_event_sec:
            break
        segment = airflow_arr[max(0, start - w): start]
        if len(segment) == 0 or float(np.nanmax(segment) - np.nanmin(segment)) >= threshold:
            break
        start -= 1

    return start, end


def _thoracoabdominal_paradox(
    thorax_event: np.ndarray,
    abdomen_event: np.ndarray,
    fs: float = DEFAULT_SAMPLE_RATE_HZ,
) -> bool:
    """True when thorax and abdomen move OUT of phase during the event
    (paradoxical breathing) -- the classic obstructive signature."""
    if len(thorax_event) < 10 or len(abdomen_event) < 10:
        return False
    t = np.asarray(thorax_event, dtype=float)
    a = np.asarray(abdomen_event, dtype=float)
    # Remove slow belt drift so movement during the event, not belt sliding,
    # determines the thorax/abdomen phase relationship.
    window = max(3, int(round(fs * EFFORT_BREATH_WINDOW_SEC)))
    t = t - pd.Series(t).rolling(window, center=True, min_periods=1).mean().to_numpy()
    a = a - pd.Series(a).rolling(window, center=True, min_periods=1).mean().to_numpy()
    denom = float(np.sqrt(np.nansum(t * t) * np.nansum(a * a)))
    if denom <= 0:
        return False
    correlation = float(np.nansum(t * a) / denom)
    return correlation <= -0.3


def _segment_mask(mask: np.ndarray, time_sec: np.ndarray, min_event_sec: float) -> list[tuple[int, int, float]]:
    segments: list[tuple[int, int, float]] = []
    start_index: int | None = None
    sample_dt = float(np.nanmedian(np.diff(time_sec))) if len(time_sec) > 1 else 0.0

    for index, is_active in enumerate(mask):
        if is_active and start_index is None:
            start_index = index
            continue

        if not is_active and start_index is not None:
            end_index = index - 1
            duration_sec = float(time_sec[end_index] - time_sec[start_index] + sample_dt)
            if duration_sec >= min_event_sec:
                segments.append((start_index, end_index, duration_sec))
            start_index = None

    if start_index is not None:
        end_index = len(mask) - 1
        duration_sec = float(time_sec[end_index] - time_sec[start_index] + sample_dt)
        if duration_sec >= min_event_sec:
            segments.append((start_index, end_index, duration_sec))

    return segments


def _expand_segment_to_drop_extent(
    start_index: int,
    end_index: int,
    drop_percent: np.ndarray,
    time_sec: np.ndarray,
    boundary_drop_percent: float = EVENT_BOUNDARY_DROP_PERCENT,
    max_event_sec: float = MAX_EVENT_SEC,
) -> tuple[int, int]:
    """Expand a core segment outward until the airflow drop no longer holds.

    The band mask captures only the core of the event. The ramp down and ramp
    up belong to the event too, so we expand the boundaries while the drop
    remains above the boundary threshold.
    """
    total = len(drop_percent)
    new_start = int(start_index)
    new_end = int(end_index)

    while new_start - 1 >= 0 and drop_percent[new_start - 1] >= boundary_drop_percent:
        if float(time_sec[new_end] - time_sec[new_start - 1]) > max_event_sec:
            break
        new_start -= 1

    while new_end + 1 < total and drop_percent[new_end + 1] >= boundary_drop_percent:
        if float(time_sec[new_end + 1] - time_sec[new_start]) > max_event_sec:
            break
        new_end += 1

    return new_start, new_end


def _robust_signal_amplitude(values: pd.Series | np.ndarray) -> float:
    series = pd.Series(values)
    series = pd.to_numeric(series, errors="coerce").dropna()
    if len(series) == 0:
        return 0.0
    return float(np.nanpercentile(series, 95) - np.nanpercentile(series, 5))


def _effort_amplitude(values: np.ndarray | None, fs: float = DEFAULT_SAMPLE_RATE_HZ) -> float:
    """Breathing amplitude on an effort belt, immune to slow belt drift.

    p95-p5 of the raw segment measures DRIFT as well as breathing: a belt that
    slides monotonically by 20 counts while the patient does not breathe at all
    scores the same as real breathing of that size, which turns a central apnea
    into an obstructive one. Measuring peak-to-trough INSIDE one breath-length
    window removes the drift, exactly as the airflow engine does.
    """
    if values is None:
        return 0.0
    series = pd.to_numeric(pd.Series(np.asarray(values, dtype=float)), errors="coerce").dropna()
    if len(series) == 0:
        return 0.0
    window_points = max(3, int(round(fs * EFFORT_BREATH_WINDOW_SEC)))
    if len(series) < window_points:
        return _robust_signal_amplitude(series)
    spread = (
        series.rolling(window_points, center=True, min_periods=2).max()
        - series.rolling(window_points, center=True, min_periods=2).min()
    )
    return float(np.nanmedian(spread.to_numpy()))


def _effort_ratios(
    thorax_segment: np.ndarray | None,
    abdomen_segment: np.ndarray | None,
    thorax_baseline_amp: float,
    abdomen_baseline_amp: float,
    fs: float = DEFAULT_SAMPLE_RATE_HZ,
) -> float:
    thorax_ratio = (
        _effort_amplitude(thorax_segment, fs) / thorax_baseline_amp
        if (thorax_segment is not None and thorax_baseline_amp > 0)
        else 0.0
    )
    abdomen_ratio = (
        _effort_amplitude(abdomen_segment, fs) / abdomen_baseline_amp
        if (abdomen_segment is not None and abdomen_baseline_amp > 0)
        else 0.0
    )
    return max(thorax_ratio, abdomen_ratio)


def _effort_baseline_amplitude(values: np.ndarray, fs: float) -> float:
    """Baseline breathing amplitude for an effort belt.

    Uses a HIGH percentile of the per-breath spread, not the median: a study
    full of events spends much of its time in reduced breathing, so a median
    baseline is dragged down by the very events being measured. The 90th
    percentile represents the patient's normal breathing.
    """
    series = pd.to_numeric(pd.Series(np.asarray(values, dtype=float)), errors="coerce").dropna()
    if len(series) == 0:
        return 0.0
    window_points = max(3, int(round(fs * EFFORT_BREATH_WINDOW_SEC)))
    if len(series) < window_points:
        return _robust_signal_amplitude(series)
    spread = (
        series.rolling(window_points, center=True, min_periods=2).max()
        - series.rolling(window_points, center=True, min_periods=2).min()
    )
    return float(np.nanpercentile(spread.to_numpy(), 90))


def _compute_effort_baseline(
    thorax: np.ndarray | None,
    abdomen: np.ndarray | None,
    baseline_mask: np.ndarray,
    fs: float = DEFAULT_SAMPLE_RATE_HZ,
) -> tuple[float, float] | None:
    """Return (thorax_baseline_amplitude, abdomen_baseline_amplitude).

    Abdomen is optional: many recordings carry only a thorax belt. In that
    case the abdomen baseline is 0.0 and every downstream check falls back to
    thorax alone -- far better than the old blind "call it OSA" fallback.
    Returns None only when NO usable effort belt exists.
    """
    thorax_baseline_amp = 0.0
    abdomen_baseline_amp = 0.0
    if thorax is not None:
        thorax_baseline_window = thorax[baseline_mask]
        if len(thorax_baseline_window) > 0:
            thorax_baseline_amp = _effort_baseline_amplitude(thorax_baseline_window, fs)
    if abdomen is not None:
        abdomen_baseline_window = abdomen[baseline_mask]
        if len(abdomen_baseline_window) > 0:
            abdomen_baseline_amp = _effort_baseline_amplitude(abdomen_baseline_window, fs)
    if thorax_baseline_amp <= 0 and abdomen_baseline_amp <= 0:
        return None
    return thorax_baseline_amp, abdomen_baseline_amp


def _effort_state(
    thorax_segment: np.ndarray | None,
    abdomen_segment: np.ndarray | None,
    thorax_baseline_amp: float,
    abdomen_baseline_amp: float,
    fs: float,
    absent_below: float | None = None,
    present_at_or_above: float | None = None,
) -> str:
    """Classify one half-event's breathing effort as 'absent', 'borderline'
    or 'present'.

    Amplitude alone is not enough on a low-resolution belt: when the baseline
    breath is only a few counts tall, quantisation noise keeps the ratio near
    0.3 even on a dead-flat trace. So a segment with NO detectable breaths is
    called absent regardless of that ratio.
    """
    # Resolved at call time, not at def time. Python binds a default argument
    # once, when the function object is created, so these used to keep the
    # 0.20 / 0.60 they were born with -- the Settings dialog could rebind the
    # module globals all it liked and the classifier never noticed.
    if absent_below is None:
        absent_below = OBSTRUCTIVE_APNEA_EFFORT_THRESHOLD
    if present_at_or_above is None:
        present_at_or_above = CENTRAL_APNEA_EFFORT_THRESHOLD

    best_ratio = _effort_ratios(
        thorax_segment, abdomen_segment, thorax_baseline_amp, abdomen_baseline_amp, fs
    )
    breath_rate = max(
        _effort_breath_rate(thorax_segment, thorax_baseline_amp, fs),
        _effort_breath_rate(abdomen_segment, abdomen_baseline_amp, fs),
    )
    if breath_rate < EFFORT_MIN_BREATH_RATE_PER_MIN and best_ratio < present_at_or_above:
        return "absent"
    if best_ratio < absent_below:
        return "absent"
    # Countable breathing is the strongest evidence in EITHER direction. During
    # an obstructive apnea the chest keeps moving but often at only 0.3-0.5 of
    # baseline; judging that on amplitude alone wrongly calls it "borderline".
    if breath_rate >= EFFORT_MIN_BREATH_RATE_PER_MIN:
        return "present"
    if best_ratio < present_at_or_above:
        return "absent"
    return "borderline"


def classify_apnea_effort_type(
    thorax_event: np.ndarray | None,
    abdomen_event: np.ndarray | None,
    thorax_baseline_amp: float,
    abdomen_baseline_amp: float,
    fs: float = DEFAULT_SAMPLE_RATE_HZ,
) -> str:
    """Classify an apnea-tier event (>=75% airflow drop) as Obstructive (OSA),
    Central (CSA), or Mixed (MSA) based on whether breathing effort
    (Thorax/Abdomen movement) continues during the event - the real AASM
    signal for this distinction (not how deep the airflow drop is).
    """
    reference = thorax_event if thorax_event is not None else abdomen_event
    if reference is None or len(reference) < 2:
        return "OSA"
    # Paradoxical (out-of-phase) thoraco-abdominal movement is the strongest
    # obstructive signature -- only checkable when BOTH belts exist.
    if thorax_event is not None and abdomen_event is not None:
        if _thoracoabdominal_paradox(thorax_event, abdomen_event, fs):
            return "OSA"

    sample_count = len(reference)
    midpoint = sample_count // 2

    def half(segment, lo, hi):
        return None if segment is None else segment[lo:hi]

    first_half_state = _effort_state(
        half(thorax_event, 0, midpoint), half(abdomen_event, 0, midpoint),
        thorax_baseline_amp, abdomen_baseline_amp, fs,
    )
    second_half_state = _effort_state(
        half(thorax_event, midpoint, sample_count), half(abdomen_event, midpoint, sample_count),
        thorax_baseline_amp, abdomen_baseline_amp, fs,
    )
    if first_half_state == "absent" and second_half_state == "absent":
        whole_event_ratio = _effort_ratios(
            thorax_event, abdomen_event, thorax_baseline_amp, abdomen_baseline_amp, fs
        )
        whole_event_breaths = max(
            _effort_breath_rate(thorax_event, thorax_baseline_amp, fs),
            _effort_breath_rate(abdomen_event, abdomen_baseline_amp, fs),
        )
        # CSA needs effort truly gone across the WHOLE event: either the
        # amplitude floor, or no detectable breath on any belt.
        if (
            whole_event_ratio < CENTRAL_APNEA_AMPLITUDE_CONFIRM_RATIO
            or whole_event_breaths < EFFORT_MIN_BREATH_RATE_PER_MIN
        ):
            return "CSA"
        return "MSA"
    # AASM mixed apnea has a specific shape: NO effort at the start, effort
    # resuming later. Anything else with effort present is obstructive --
    # "MSA" must never be the dumping ground for uncertain cases.
    if first_half_state == "absent":
        return "MSA"
    return "OSA"


def _build_event_evidence(event: dict[str, Any]) -> list[str]:
    """Build the detector evidence lines shown when an event is hovered."""
    lines: list[str] = []

    baseline_amp = float(event.get("baseline_airflow", 0.0) or 0.0)
    event_amp = float(event.get("event_airflow_amplitude", 0.0) or 0.0)
    drop = float(event.get("airflow_drop_percent", 0.0) or 0.0)
    if drop >= AASM_APNEA_DROP_PERCENT:
        tier = "apnea tier (>=75%)"
    elif drop >= AASM_HYPOPNEA_DROP_PERCENT:
        tier = "hypopnea tier (30-75%)"
    else:
        tier = "below hypopnea tier"
    lines.append(
        f"Airflow   drop {drop:.0f}%   amplitude {baseline_amp:.1f} -> {event_amp:.1f}   {tier}"
    )

    nadir_sec = event.get("desat_nadir_sec")
    base_spo2 = event.get("desat_baseline_spo2")
    nadir_spo2 = event.get("desat_nadir_spo2")
    if nadir_sec is not None and base_spo2 is not None and nadir_spo2 is not None:
        base_spo2 = float(base_spo2)
        nadir_spo2 = float(nadir_spo2)
        delay = float(nadir_sec) - float(event.get("end_sec", 0.0))
        spo2_drop = float(event.get("spo2_drop", 0.0) or 0.0)
        mark = "OK" if spo2_drop >= AASM_HYPOPNEA_SPO2_DESAT_MIN else "below 3%"
        lines.append(
            f"SpO2      {base_spo2:.0f} -> {nadir_spo2:.0f}  (-{base_spo2 - nadir_spo2:.0f}%)   "
            f"nadir {delay:+.0f} s from event end   {mark}"
        )
    else:
        lines.append("SpO2      no desaturation linked   no")

    if event.get("pulse_artifact"):
        lines.append("Pulse     trace looked artifactual during event (probe disturbed)   no")

    reason = event.get("sensor_off_reason")
    if reason:
        lines.append(f"Sensor    reassigned to SENSOR_OFF: {reason}")

    return lines


def _build_debug_summary(
    baseline_airflow_reference: float,
    stable_min_airflow: float,
    airflow_reduction_range: float,
    apnea_threshold: float,
    hypopnea_threshold: float,
    raw_segments: int,
    filtered_segments: int,
    merged_segments: int,
    baseline_source: str,
) -> list[str]:
    return [
        f"baseline_source={baseline_source}",
        "baseline_mode=hourly_window_only",
        f"baseline_reference_first_window={baseline_airflow_reference:.2f}",
        f"stable_min_airflow={stable_min_airflow:.2f}",
        f"reduction_scale=percent_drop_from_baseline",
        f"airflow_reduction_range={airflow_reduction_range:.2f}",
        f"apnea_threshold={apnea_threshold:.2f}",
        f"hypopnea_threshold={hypopnea_threshold:.2f}",
        f"raw_candidate_segments={raw_segments}",
        f"after_filter_segments={filtered_segments}",
        f"after_merge_segments={merged_segments}",
    ]


def _build_event_debug_line(event: dict[str, Any], event_id: int) -> str:
    return (
        f"Event {event_id}: "
        f"{float(event['start_sec']):.1f}s - {float(event['end_sec']):.1f}s | "
        f"duration={float(event['duration_sec']):.1f}s | "
        f"baseline={float(event['baseline_airflow']):.2f} | "
        f"peak_airflow={float(event['event_peak_airflow']):.2f} | " 
        f"min_airflow={float(event['event_min_airflow']):.2f} | "
        f"amp_ratio={float(event.get('airflow_amplitude_ratio', 0.0)):.2f} | "
        f"drop={float(event['airflow_drop_percent']):.1f}% | "
        f"rule={str(event['rule_label'])}"
    )


def _format_window_duration(duration_sec: float) -> str:
    total_seconds = max(0.0, float(duration_sec))
    hours = int(total_seconds // 3600)
    remaining_after_hours = total_seconds - (hours * 3600)
    minutes = int(remaining_after_hours // 60)
    seconds = remaining_after_hours - (minutes * 60)

    if hours > 0:
        return f"{hours}h {minutes}m {seconds:.1f}s"
    if minutes > 0:
        return f"{minutes}m {seconds:.1f}s"
    return f"{seconds:.1f}s"


def _build_hourly_baseline_array(
    analysis_time: np.ndarray,
    hourly_peak_baselines: list[dict[str, float | int | None]],
) -> np.ndarray:
    baseline_array = np.zeros(len(analysis_time), dtype=float)

    for item in hourly_peak_baselines:
        start_sec = float(item["start_sec"])
        end_sec = float(item["end_sec"])
        peak_value = float(item["peak_value"])
        if str(item.get("window_type", "")) == "remainder":
            window_mask = (analysis_time >= start_sec) & (analysis_time <= end_sec)
        else:
            window_mask = (analysis_time >= start_sec) & (analysis_time < end_sec)
        baseline_array[window_mask] = peak_value

    if len(baseline_array) > 0:
        last_nonzero = next((value for value in baseline_array[::-1] if value > 0), 0.0)
        if last_nonzero > 0:
            baseline_array[baseline_array <= 0] = last_nonzero

    return baseline_array


def _write_text_report(result: dict[str, Any], csv_path: str | Path, output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"{Path(csv_path).stem}_rule_ai_events_{timestamp}.txt"
    generated_dt = datetime.now()

    lines: list[str] = [
        f"report_type=rule_based_apnea_detection | source_csv={csv_path} | generated_date={generated_dt.strftime('%Y-%m-%d')} | generated_time={generated_dt.strftime('%H:%M:%S')}",
        "formula=legacy_candidate_scan_drop_percent=((window_baseline-analysis_peak_envelope)/window_baseline)*100",
        f"label_rules=AASM | Hypopnea:>={AASM_HYPOPNEA_DROP_PERCENT:.0f}%+spo2_desat>={AASM_HYPOPNEA_SPO2_DESAT_MIN:.0f}% | Apnea:>={AASM_APNEA_DROP_PERCENT:.0f}%(OSA/CSA/MSA by effort) | min_event_sec={MIN_EVENT_SEC:.1f}",
        "baseline_note=detection_uses_hourly_or_remainder_window_peak_baselines_not_one_combined_average",
        f"baseline_source={result.get('baseline_source', '--')}",
        "hourly_peak_baselines:",
    ]

    hourly_peak_baselines = result.get("hourly_peak_baselines", [])
    if hourly_peak_baselines:
        for item in hourly_peak_baselines:
            display_item = dict(item)
            window_label = str(display_item.get("window_label", "Window"))
            if str(display_item.get("window_type", "")) == "remainder":
                window_label = f"{window_label} ({_format_window_duration(float(display_item.get('duration_sec', 0.0)))})"
            display_item["window_label"] = window_label
            lines.append(
                "window_label={window_label} | range={start_sec:.1f}s-{end_sec:.1f}s | duration={duration_sec:.1f}s | "
                "peak={peak_value:.2f} | occurrence={peak_occurrence} | first={peak_first_time_sec} | "
                "last={peak_last_time_sec}".format(
                    **display_item,
                )
            )
    else:
        lines.append("No hourly peak baselines found.")

    lines.append("summary:")

    for line in result.get("debug_summary", []):
        lines.append(str(line))

    lines.append(f"total_detected_events={len(result.get('events', []))}")
    lines.append("detected_events:")

    debug_events = result.get("debug_events", [])
    if debug_events:
        lines.extend(str(line) for line in debug_events)
    else:
        lines.append("none")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def classify_rule_event(
    drop_ratio: float,
    spo2_drop: float,
    snoring_mean: float,
    movement_mean: float,
    variability_score: float,
    duration_sec: float | None = None,
    airflow_amplitude: float | None = None,
    airflow_amplitude_ratio: float | None = None,
    spo2_usable: bool = True,
) -> str:
    if duration_sec is not None and duration_sec > MAX_EVENT_SEC:
        return "NO_EVENT"

    if duration_sec is None or duration_sec < MIN_EVENT_SEC:
        return "NO_EVENT"

    drop_percent = drop_ratio * 100.0

    if drop_percent >= AASM_APNEA_DROP_PERCENT:
        return "APNEA_CANDIDATE"

    if drop_percent >= AASM_HYPOPNEA_DROP_PERCENT:
        # AASM hypopnea requires both the airflow drop and a confirmed SpO2
        # desaturation; do not score an unconfirmed hypopnea.
        if spo2_usable and spo2_drop >= AASM_HYPOPNEA_SPO2_DESAT_MIN:
            return "HYPOPNEA"
        return "NO_EVENT"

    return "NO_EVENT"


def detect_desaturations(
    time_sec: np.ndarray,
    spo2: np.ndarray,
    lookback_sec: float | None = None,
    drop_percent: float | None = None,
    min_event_sec: float = 0.0,
) -> list[dict[str, Any]]:
    """Detect AASM-style desaturation events from SpO2.

    The rule is a fall of at least `drop_percent` from the recent pre-event
    baseline. This helper is intentionally small so the report can reuse the
    detector's logic instead of inventing a second counting formula.
    """
    # Same late-binding trap as _effort_state: resolve from the live globals so
    # the Desaturation tab's threshold actually reaches the scorer.
    if drop_percent is None:
        drop_percent = DESAT_DROP_PERCENT
    if lookback_sec is None:
        lookback_sec = DESAT_BASELINE_LOOKBACK_SEC

    time_arr = np.asarray(time_sec, dtype=float).reshape(-1)
    spo2_arr = np.asarray(spo2, dtype=float).reshape(-1)
    if time_arr.size == 0 or spo2_arr.size == 0:
        return []

    sample_count = min(time_arr.size, spo2_arr.size)
    time_arr = time_arr[:sample_count]
    spo2_arr = spo2_arr[:sample_count].copy()
    # 70, not 50: pulse oximeters are only validated down to about 70%, and
    # report_metrics_calculator already rejects below 70. Two different floors
    # meant the dashboard scored 16 desaturations where the report scored 14.
    spo2_arr[~np.isfinite(spo2_arr) | (spo2_arr < 70.0) | (spo2_arr > 100.0)] = np.nan

    finite_diffs = np.diff(time_arr)
    finite_diffs = finite_diffs[np.isfinite(finite_diffs) & (finite_diffs > 0)]
    sample_dt = float(np.median(finite_diffs)) if finite_diffs.size else 0.0
    if sample_dt <= 0.0:
        sample_dt = 1.0

    lookback_samples = max(1, int(round(float(lookback_sec) / sample_dt)))
    recent_samples = max(1, int(round(DESAT_RECENT_BASELINE_SEC / sample_dt)))

    # Both trailing baselines are computed once for the full recording with a
    # vectorized rolling quantile. The old per-sample np.nanpercentile() loop
    # dominated runtime on long studies. shift(1) keeps each baseline strictly
    # before the current sample, matching the original slice spo2_arr[start:index].
    spo2_series = pd.Series(spo2_arr)
    baseline_series = (
        spo2_series.rolling(window=lookback_samples, min_periods=1)
        .quantile(0.90)
        .shift(1)
        .to_numpy(dtype=float)
    )
    recent_series = (
        spo2_series.rolling(window=recent_samples, min_periods=1)
        .quantile(0.90)
        .shift(1)
        .to_numpy(dtype=float)
    )

    active = np.zeros(sample_count, dtype=bool)
    in_desaturation = False

    for index, value in enumerate(spo2_arr):
        if not np.isfinite(value):
            continue
        baseline_spo2 = baseline_series[index]
        if not np.isfinite(baseline_spo2) or baseline_spo2 <= 0.0:
            continue
        if baseline_spo2 - float(value) < float(drop_percent):
            in_desaturation = False
            continue

        if not in_desaturation:
            # ONSET only: a drift has already carried the recent level down, so
            # the fall does not show against the last few seconds. A real
            # desaturation still does -- SpO2 is high right up to the fall.
            recent_baseline = recent_series[index]
            if np.isfinite(recent_baseline) and recent_baseline - float(value) < float(drop_percent):
                continue
            in_desaturation = True

        active[index] = True

    events: list[dict[str, Any]] = []
    for start_index, end_index, duration_sec in _segment_mask(active, time_arr, min_event_sec):
        baseline_spo2 = float(baseline_series[start_index])
        segment = spo2_arr[start_index : end_index + 1]
        finite_segment = segment[np.isfinite(segment)]
        if finite_segment.size:
            nadir_local_index = int(np.nanargmin(finite_segment))
            nadir_spo2 = float(finite_segment[nadir_local_index])
            finite_positions = np.flatnonzero(np.isfinite(segment))
            nadir_abs_index = int(start_index + finite_positions[nadir_local_index])
            nadir_sec = float(time_arr[nadir_abs_index])
        else:
            nadir_spo2 = float("nan")
            nadir_sec = float(time_arr[start_index])
        measured_drop = (
            float(baseline_spo2 - nadir_spo2)
            if np.isfinite(baseline_spo2) and np.isfinite(nadir_spo2)
            else float(drop_percent)
        )
        events.append(
            {
                "start_index": int(start_index),
                "end_index": int(end_index),
                "start_sec": float(time_arr[start_index]),
                "end_sec": float(time_arr[end_index]),
                "duration_sec": float(duration_sec),
                "baseline_spo2": baseline_spo2,
                "nadir_sec": nadir_sec,
                "nadir_spo2": nadir_spo2,
                "drop_percent": measured_drop,
                "threshold_percent": float(drop_percent),
            }
        )

    return events


def _finalize_label(rule_label: str, ai_label: str | None, ai_confidence: float | None) -> str:
    if ai_label is None or ai_confidence is None:
        return rule_label
    if rule_label == "NO_EVENT":
        return rule_label
    if rule_label in {"OSA", "CSA", "MSA", "APNEA", "HYPOPNEA"}:
        return rule_label
    if ai_label == rule_label and ai_confidence >= 0.40:
        return ai_label
    if ai_confidence >= 0.75:
        return ai_label
    return rule_label


def detect_apnea_events_from_dataframe(
    signal_df: pd.DataFrame,
    output_dir: str | Path | None = None,
    enable_ai: bool = False,
) -> dict[str, Any]:
    signal_df = signal_df.copy()
    airflow_enhancement_applied = False
    if enhance_airflow_for_graph_and_detection is not None and "airflow" in signal_df.columns:
        enhanced_airflow = enhance_airflow_for_graph_and_detection(
            signal_df["airflow"].to_numpy(dtype=float),
            amplitude=1.15,
            max_limit=None,
            spike_threshold=20.0,
            kernel_size=5,
            low_protect_margin=2.0,
            keep_integer=True,
        )
        signal_df["airflow"] = enhanced_airflow
        airflow_enhancement_applied = True

    processed_df, preprocess_meta = preprocess_signals(signal_df)

    raw_time_sec = signal_df["time_sec"].to_numpy(dtype=float)
    raw_airflow = signal_df["airflow"].to_numpy(dtype=float)

    time_sec = signal_df["time_sec"].to_numpy(dtype=float)
    airflow = signal_df["airflow"].to_numpy(dtype=float)
    spo2 = signal_df["spo2"].to_numpy(dtype=float)
    pulse = signal_df["pulse"].to_numpy(dtype=float) if "pulse" in signal_df.columns else None
    # 70, not 50: pulse oximeters are only validated down to about 70%, and
    # report_metrics_calculator already rejects below 70. Two different floors
    # meant the dashboard scored 16 desaturations where the report scored 14.
    spo2 = np.where(~np.isfinite(spo2) | (spo2 < 70.0) | (spo2 > 100.0), np.nan, spo2)
    snoring = signal_df["snoring"].to_numpy(dtype=float)
    body_movement = signal_df["body_movement"].to_numpy(dtype=float)
    thorax = signal_df["thorax"].to_numpy(dtype=float) if "thorax" in signal_df.columns else None
    abdomen = signal_df["abdomen"].to_numpy(dtype=float) if "abdomen" in signal_df.columns else None

    estimated_fs = estimate_sample_rate_hz(signal_df)
    sample_dt = 1.0 / estimated_fs if estimated_fs else 0.1
    peak_window_points = max(1, int(round(estimated_fs * CANDIDATE_WINDOW_SEC)))

    skip_sec = SKIP_MINUTES * 60.0
    baseline_mask = raw_time_sec >= skip_sec
    baseline_airflow_window = raw_airflow[baseline_mask]
    if len(baseline_airflow_window) == 0:
        raise ValueError("Baseline airflow window is empty. Recording is too short.")

    hourly_peak_baselines = compute_hourly_peak_baselines(
        time_sec=raw_time_sec,
        airflow=raw_airflow,
        skip_sec=skip_sec,
    )
    if not hourly_peak_baselines:
        raise ValueError("Hourly baseline windows are empty. Recording is too short after skip period.")

    hourly_peak_values = [float(item["peak_value"]) for item in hourly_peak_baselines]
    baseline_airflow_reference = float(hourly_peak_values[0])
    baseline_occurrence = int(sum(int(item["peak_occurrence"]) for item in hourly_peak_baselines))
    baseline_occurrence_duration_sec = (
        float(baseline_occurrence / estimated_fs) if estimated_fs and baseline_occurrence > 0 else 0.0
    )
    baseline_peak_first_time = next(
        (item["peak_first_time_sec"] for item in hourly_peak_baselines if item["peak_first_time_sec"] is not None),
        None,
    )
    baseline_peak_last_time = next(
        (
            item["peak_last_time_sec"]
            for item in reversed(hourly_peak_baselines)
            if item["peak_last_time_sec"] is not None
        ),
        None,
    )
    stable_min_airflow, stable_min_occurrence = stable_min_from_occurrence_band(
        baseline_airflow_window,
        target_occurrence=BASELINE_TARGET_OCCURRENCE,
        tolerance=BASELINE_OCCURRENCE_TOLERANCE,
    )
    airflow_reduction_range = float(baseline_airflow_reference - stable_min_airflow)
    if airflow_reduction_range <= 0:
        airflow_reduction_range = float(baseline_airflow_reference) if baseline_airflow_reference else 1.0
    baseline_airflow_amplitude = _robust_signal_amplitude(baseline_airflow_window)
    if baseline_airflow_amplitude <= 0:
        baseline_airflow_amplitude = airflow_reduction_range
    effort_baseline = _compute_effort_baseline(thorax, abdomen, baseline_mask, estimated_fs)

    apnea_threshold = baseline_airflow_reference * (1.0 - AASM_APNEA_DROP_PERCENT / 100.0)
    hypopnea_threshold = baseline_airflow_reference * (1.0 - AASM_HYPOPNEA_DROP_PERCENT / 100.0)

    analysis_mask = time_sec >= skip_sec
    analysis_time = time_sec[analysis_mask]
    analysis_airflow = airflow[analysis_mask]
    global_indices = np.where(analysis_mask)[0]

    # ------------------------------------------------------------------
    # AASM amplitude engine: peak-to-trough amplitude per sample (immune to
    # DC offset / sensor drift) + rolling 120 s pre-window baseline.
    # The hourly baselines above are kept for reports only.
    # ------------------------------------------------------------------
    amplitude_all = _continuous_breath_amplitude(airflow, estimated_fs)
    rolling_baseline_all = _rolling_aasm_baseline(amplitude_all, estimated_fs)
    sensor_off_segments = detect_sensor_off_segments(
        airflow=airflow,
        thorax=thorax,
        fs=estimated_fs,
        time_sec=time_sec,
    )

    analysis_amplitude = amplitude_all[analysis_mask]
    analysis_window_baseline = rolling_baseline_all[analysis_mask]
    if len(analysis_window_baseline) != len(analysis_time) or not np.any(analysis_window_baseline > 0):
        raise ValueError("Rolling amplitude baseline failed for analysis window.")

    # Short-window twin of the same measurement, used ONLY to time how long a
    # flat stretch really lasts (the 5 s window shortens it by ~5 s).
    amplitude_short = _continuous_breath_amplitude(airflow, estimated_fs, APNEA_CORE_WINDOW_SEC)
    analysis_drop_short = (
        1.0 - (amplitude_short[analysis_mask] / np.maximum(analysis_window_baseline, 1e-9))
    ) * 100.0
    analysis_drop_short = np.clip(np.nan_to_num(analysis_drop_short, nan=0.0), 0.0, 100.0)

    analysis_drop_percent = (
        1.0 - (analysis_amplitude / np.maximum(analysis_window_baseline, 1e-9))
    ) * 100.0
    analysis_drop_percent = np.clip(np.nan_to_num(analysis_drop_percent, nan=0.0), 0.0, 100.0)

    spo2_usable = bool(np.any(np.isfinite(spo2)))
    # Score desaturations independently (AASM reports these as ODI) so they can
    # be drawn on the SpO2 channel and linked to the event they belong to.
    desaturations = detect_desaturations(time_sec, spo2) if spo2_usable else []

    label_specs = [
        (
            # AASM: apnea needs the >=75% drop itself to last >=10 s. The 10 s
            # test is applied AFTER _refine_apnea_core re-measures the core.
            "APNEA_CANDIDATE",
            lambda x: x >= AASM_APNEA_DROP_PERCENT,
            CORE_MIN_SEC,
        ),
        (
            "HYPOPNEA",
            lambda x: (x >= AASM_HYPOPNEA_DROP_PERCENT) & (x < AASM_APNEA_DROP_PERCENT),
            CORE_MIN_SEC,
        ),
    ]

    model = None
    class_names: list[str] = []
    model_meta: dict[str, Any] = {}
    if enable_ai:
        try:
            model, class_names, model_meta = load_cnn_model_bundle()
        except Exception:
            model = None
            class_names = []
            model_meta = {"ai_disabled_reason": "CNN bundle could not be loaded."}

    event_output_dir = Path(output_dir or DEFAULT_OUTPUT_DIR) / "rule_ai_event_images"
    event_output_dir.mkdir(parents=True, exist_ok=True)

    preliminary_events: list[dict[str, Any]] = []
    raw_segment_count = 0

    for expected_label, label_mask_fn, label_min_sec in label_specs:
        label_mask = label_mask_fn(analysis_drop_percent)
        # APNEA: the >=75% core itself must last >=10 s (AASM). HYPOPNEA: a
        # short core is allowed because the 30% boundary expansion below
        # defines the true event extent, then the 10 s rule is applied.
        label_segments = _segment_mask(label_mask, analysis_time, label_min_sec)
        raw_segment_count += len(label_segments)

        for core_start, core_end, _core_duration_sec in label_segments:
            if expected_label == "APNEA_CANDIDATE":
                # Re-measure the >=75% core on the short window, then apply the
                # AASM 10 s rule to the TRUE length.
                core_start, core_end = _refine_apnea_core(
                    core_start, core_end, analysis_drop_short, AASM_APNEA_DROP_PERCENT
                )
                core_duration_sec = float(
                    analysis_time[core_end] - analysis_time[core_start] + sample_dt
                )
                if core_duration_sec < MIN_EVENT_SEC:
                    continue
                # AASM: an apnea's duration IS the >=75% stretch. Do NOT widen
                # it out to the 30% hypopnea boundary, or the box swallows the
                # normal-looking ramp breaths on either side.
                local_start, local_end = core_start, core_end
            else:
                # Hypopnea: the event runs as long as the >=30% drop holds.
                local_start, local_end = _expand_segment_to_drop_extent(
                    core_start,
                    core_end,
                    analysis_drop_percent,
                    analysis_time,
                )
                # Tighten both edges: cover flat slivers the centered amplitude
                # window smeared out of the event (up to ~2.5 s per side).
                # local_start, local_end = _extend_boundary_through_flat(
                #     local_start,
                #     local_end,
                #     analysis_airflow,
                #     float(analysis_window_baseline[local_start]),
                #     estimated_fs,
                #     analysis_time,
                # )

            duration_sec = float(
                analysis_time[local_end] - analysis_time[local_start] + sample_dt
            )
            if duration_sec < MIN_EVENT_SEC:
                continue

            start_index = int(global_indices[local_start])
            end_index = int(global_indices[local_end])
            core_start_index = int(global_indices[core_start])
            core_end_index = int(global_indices[core_end])

            event_airflow = airflow[start_index:end_index + 1]
            event_spo2 = spo2[start_index:end_index + 1]
            event_snoring = snoring[start_index:end_index + 1]
            event_movement = body_movement[start_index:end_index + 1]

            # Severity is measured from the core, not the expanded window.
            # Expanded ramps can include higher values that reduce the drop
            # percentage and cause CSA to drift into HSA incorrectly.
            core_airflow = airflow[core_start_index:core_end_index + 1]
            event_window_baseline = analysis_window_baseline[core_start:core_end + 1]
            hourly_fallback_baseline = (
                float(np.nanmean(event_window_baseline))
                if len(event_window_baseline) > 0
                else float(baseline_airflow_reference)
            )

            # AASM baseline: breathing AMPLITUDE of the 2 minutes before event
            # onset (rolling_baseline_all already encodes mean-if-stable /
            # largest-breaths-if-unstable). Taken AT event start so the event
            # itself never contaminates its own baseline.
            event_baseline_airflow = float(rolling_baseline_all[start_index])
            if event_baseline_airflow <= 0:
                event_baseline_airflow = float(hourly_fallback_baseline)

            event_min_airflow = float(np.nanmin(core_airflow))
            event_mean_airflow = float(np.nanmean(core_airflow))
            event_peak_airflow = float(np.nanmax(core_airflow))
            core_amplitude = amplitude_all[core_start_index:core_end_index + 1]
            event_airflow_amplitude = (
                float(np.nanmedian(core_amplitude))
                if len(core_amplitude) > 0
                else _robust_signal_amplitude(core_airflow)
            )
            airflow_amplitude_ratio = (
                event_airflow_amplitude / event_baseline_airflow
                if event_baseline_airflow
                else 0.0
            )

            # AASM drop%%: how far the breathing amplitude fell vs baseline
            # amplitude (NOT raw peak values -- those break on offset sensors).
            drop_ratio = 1.0 - airflow_amplitude_ratio
            drop_ratio = float(np.clip(drop_ratio, 0.0, 1.0))
            drop_percent = drop_ratio * 100.0

            # Attach the scored desaturation whose NADIR sits closest after this
            # event. SpO2 falls with a circulation delay, so the nadir almost
            # always lands after the event is over. Nearest -- not deepest --
            # or one big dip gets claimed by every nearby event.
            linked_desat = None
            best_gap = None
            for candidate in desaturations:
                nadir_sec = float(candidate["nadir_sec"])
                if not (
                    time_sec[start_index]
                    <= nadir_sec
                    <= time_sec[end_index] + DESAT_LINK_WINDOW_SEC
                ):
                    continue
                gap = abs(nadir_sec - time_sec[end_index])
                if best_gap is None or gap < best_gap:
                    best_gap = gap
                    linked_desat = candidate

            # The SCORED desaturation is the single source of truth. The old
            # max-minus-min sweep over a 60 s window could span a slow drift or
            # two unrelated plateaus and report a "drop" where no desaturation
            # was ever scored -- confirming hypopneas that have no dip to point
            # at. When SpO2 is usable, no linked desaturation means 0%.
            if not spo2_usable:
                spo2_drop = 0.0
                spo2_measurable = False
            elif linked_desat is not None:
                spo2_drop = float(linked_desat["drop_percent"])
                spo2_measurable = True
            else:
                spo2_drop = 0.0
                spo2_measurable = True

            snoring_mean = float(np.nanmean(event_snoring))
            movement_mean = float(np.nanmean(event_movement))
            airflow_std = float(np.nanstd(core_airflow))
            variability_score = airflow_std / event_baseline_airflow if event_baseline_airflow else 0.0

            detected_rule_label = classify_rule_event(
                drop_ratio=drop_ratio,
                spo2_drop=spo2_drop,
                snoring_mean=snoring_mean,
                movement_mean=movement_mean,
                variability_score=variability_score,
                duration_sec=float(duration_sec),
                airflow_amplitude=float(event_airflow_amplitude),
                airflow_amplitude_ratio=float(airflow_amplitude_ratio),
                spo2_usable=spo2_usable and spo2_measurable,
            )
            if detected_rule_label == "NO_EVENT":
                continue

            if detected_rule_label != expected_label:
                continue

            rule_label = detected_rule_label

            if rule_label == "APNEA_CANDIDATE":
                if effort_baseline is not None:
                    thorax_baseline_amp, abdomen_baseline_amp = effort_baseline
                    rule_label = classify_apnea_effort_type(
                        thorax_event=(
                            thorax[start_index:end_index + 1] if thorax is not None else None
                        ),
                        abdomen_event=(
                            abdomen[start_index:end_index + 1] if abdomen is not None else None
                        ),
                        thorax_baseline_amp=thorax_baseline_amp,
                        abdomen_baseline_amp=abdomen_baseline_amp,
                        fs=estimated_fs,
                    )
                else:
                    rule_label = "OSA"

            preliminary_events.append(
                {
                    "start_index": start_index,
                    "end_index": end_index,
                    "start_sec": float(time_sec[start_index]),
                    "end_sec": float(time_sec[end_index]),
                    "duration_sec": float(duration_sec),
                    "baseline_airflow": float(event_baseline_airflow),
                    "event_min_airflow": event_min_airflow,
                    "event_mean_airflow": event_mean_airflow,
                    "event_peak_airflow": event_peak_airflow,
                    "event_airflow_amplitude": float(event_airflow_amplitude),
                    "airflow_amplitude_ratio": float(airflow_amplitude_ratio),
                    "airflow_drop_percent": float(drop_percent),
                    "spo2_drop": spo2_drop,
                    "snoring_mean": snoring_mean,
                    "movement_mean": movement_mean,
                    "variability_score": float(variability_score),
                    "rule_label": rule_label,
                    "spo2_confirmed": bool(
                        spo2_usable
                        and spo2_measurable
                        and spo2_drop >= AASM_HYPOPNEA_SPO2_DESAT_MIN
                    ),
                    "desat_nadir_sec": (
                        float(linked_desat["nadir_sec"]) if linked_desat else None
                    ),
                    "desat_nadir_spo2": (
                        float(linked_desat["nadir_spo2"]) if linked_desat else None
                    ),
                    "desat_baseline_spo2": (
                        float(linked_desat["baseline_spo2"]) if linked_desat else None
                    ),
                }
            )

    filtered_events = sorted(
        preliminary_events,
        key=lambda item: (item["start_sec"], item["end_sec"], item["rule_label"]),
    )

    merged_events: list[dict[str, Any]] = []
    for event in filtered_events:
        if not merged_events:
            merged_events.append(dict(event))
            continue

        previous = merged_events[-1]
        same_label = previous["rule_label"] == event["rule_label"]
        small_gap = (event["start_sec"] - previous["end_sec"]) <= MERGE_GAP_SEC
        merged_duration = float(event["end_sec"]) - float(previous["start_sec"])

        if same_label and small_gap and merged_duration <= MAX_EVENT_SEC:
            previous["end_sec"] = max(previous["end_sec"], event["end_sec"])
            previous["end_index"] = max(previous["end_index"], event["end_index"])
            previous["duration_sec"] = previous["end_sec"] - previous["start_sec"]
            previous["event_min_airflow"] = min(previous["event_min_airflow"], event["event_min_airflow"])
            previous["event_mean_airflow"] = min(previous["event_mean_airflow"], event["event_mean_airflow"])
            previous["event_peak_airflow"] = max(previous["event_peak_airflow"], event["event_peak_airflow"])
            previous["event_airflow_amplitude"] = max(
                previous["event_airflow_amplitude"],
                event["event_airflow_amplitude"],
            )
            previous["airflow_amplitude_ratio"] = max(
                previous["airflow_amplitude_ratio"],
                event["airflow_amplitude_ratio"],
            )
            previous["airflow_drop_percent"] = max(previous["airflow_drop_percent"], event["airflow_drop_percent"])
            previous["spo2_drop"] = max(previous["spo2_drop"], event["spo2_drop"])
            previous["snoring_mean"] = max(previous["snoring_mean"], event["snoring_mean"])
            previous["movement_mean"] = max(previous["movement_mean"], event["movement_mean"])
            previous["variability_score"] = max(previous["variability_score"], event["variability_score"])
            continue

        # Overlapping events with different labels: keep the DEEPER one whole
        # and TRIM the shallower one to its non-overlapping part instead of
        # deleting it. The reduced breathing that leads into an apnea is real
        # and must still be scored when it meets the 10 s rule on its own.
        if event["start_sec"] < previous["end_sec"]:
            new_is_deeper = float(event["airflow_drop_percent"]) > float(previous["airflow_drop_percent"])
            if new_is_deeper:
                kept_end = float(event["start_sec"])
                if kept_end - float(previous["start_sec"]) >= MIN_EVENT_SEC:
                    previous["end_sec"] = kept_end
                    previous["duration_sec"] = kept_end - float(previous["start_sec"])
                    merged_events.append(dict(event))
                else:
                    merged_events[-1] = dict(event)
            else:
                kept_start = float(previous["end_sec"])
                if float(event["end_sec"]) - kept_start >= MIN_EVENT_SEC:
                    trimmed = dict(event)
                    trimmed["start_sec"] = kept_start
                    trimmed["duration_sec"] = float(event["end_sec"]) - kept_start
                    merged_events.append(trimmed)
            continue

        merged_events.append(dict(event))

    for event in merged_events:
        event_start = float(event["start_sec"])
        event_end = float(event["end_sec"])
        event_duration = max(0.0, event_end - event_start)
        if event_duration <= 0:
            continue
        trust_spo2 = False
        if event.get("spo2_confirmed"):
            trust_spo2 = True
            if pulse is not None and len(pulse) == len(time_sec):
                event_mask = (time_sec >= event_start) & (time_sec <= event_end)
                event_pulse = pulse[event_mask]
                if _pulse_looks_artifactual(event_pulse):
                    trust_spo2 = False
                    event["pulse_artifact"] = True
                    print(
                        f"Pulse artifact during {event_start:.0f}s-{event_end:.0f}s; "
                        "SpO2 confirmation will not block SENSOR_OFF reassignment"
                    )
            if trust_spo2:
                continue

        reassign = False
        reason = ""
        for segment in sensor_off_segments:
            overlap = min(event_end, float(segment["end_sec"])) - max(
                event_start, float(segment["start_sec"])
            )
            if overlap / event_duration >= SENSOR_OFF_EVENT_OVERLAP_RATIO:
                reassign = True
                reason = "overlaps detected sensor-off segment"
                break

        # Long unconfirmed events near the scoring ceiling are more consistent
        # with a cannula dropout than a genuine sustained apnea.
        if (
            not reassign
            and event_duration >= LONG_EVENT_SENSOR_SUSPECT_SEC
            and not trust_spo2
        ):
            reassign = True
            reason = (
                f"duration {event_duration:.0f}s close to {MAX_EVENT_SEC:.0f}s cap, "
                "no confirmed desaturation"
            )

        if reassign and event["rule_label"] in {"OSA", "CSA", "MSA", "HYPOPNEA"}:
            event["rule_label"] = "SENSOR_OFF"
            event["sensor_off_reason"] = reason
            print(
                f"Reassigned {event_start:.0f}s-{event_end:.0f}s to SENSOR_OFF "
                f"({reason})"
            )

    events: list[DetectedApneaEvent] = []
    ai_candidates_processed = 0

    for event_id, event in enumerate(merged_events, start=1):
        if float(event["duration_sec"]) > MAX_EVENT_SEC:
            continue

        ai_label = None
        ai_confidence = None
        image_path = None

        if model is not None and str(event["rule_label"]) in {"OSA", "CSA", "MSA", "APNEA", "HYPOPNEA"}:
            try:
                ai_candidates_processed += 1
                image_file = event_output_dir / f"event_{event_id:03d}.png"
                candidate_stub = type(
                    "CandidateStub",
                    (),
                    {
                        "event_id": f"event_{event_id:03d}",
                        "start_sec": float(event["start_sec"]),
                        "end_sec": float(event["end_sec"]),
                        "duration_sec": float(event["duration_sec"]),
                    },
                )()
                create_event_window_image(
                    signal_df=processed_df,
                    candidate=candidate_stub,
                    output_path=image_file,
                    pre_event_seconds=30.0,
                    post_event_seconds=30.0,
                )
                prediction = predict_event_image(image_file, model, class_names)
                ai_label = str(prediction["predicted_label"])
                ai_confidence = float(prediction["confidence"])
                image_path = str(image_file)
            except Exception:
                ai_label = None
                ai_confidence = None
                image_path = None

        final_label = _finalize_label(str(event["rule_label"]), ai_label, ai_confidence)

        events.append(
            DetectedApneaEvent(
                event_id=event_id,
                start_sec=float(event["start_sec"]),
                end_sec=float(event["end_sec"]),
                duration_sec=float(event["duration_sec"]),
                baseline_airflow=float(event["baseline_airflow"]),
                event_min_airflow=float(event["event_min_airflow"]),
                event_mean_airflow=float(event["event_mean_airflow"]),
                event_peak_airflow=float(event["event_peak_airflow"]),
                event_airflow_amplitude=float(event["event_airflow_amplitude"]),
                airflow_amplitude_ratio=float(event["airflow_amplitude_ratio"]),
                airflow_drop_percent=float(event["airflow_drop_percent"]),
                spo2_drop=float(event["spo2_drop"]),
                snoring_mean=float(event["snoring_mean"]),
                movement_mean=float(event["movement_mean"]),
                variability_score=float(event["variability_score"]),
                rule_label=str(event["rule_label"]),
                spo2_confirmed=bool(event.get("spo2_confirmed", True)),
                desat_nadir_sec=event.get("desat_nadir_sec"),
                desat_nadir_spo2=event.get("desat_nadir_spo2"),
                desat_baseline_spo2=event.get("desat_baseline_spo2"),
                ai_label=ai_label,
                ai_confidence=ai_confidence,
                final_label=final_label,
                image_path=image_path,
                evidence=_build_event_evidence(event),
            )
        )

    debug_summary = _build_debug_summary(
        baseline_airflow_reference=float(baseline_airflow_reference),
        stable_min_airflow=float(stable_min_airflow),
        airflow_reduction_range=float(airflow_reduction_range),
        apnea_threshold=float(apnea_threshold),
        hypopnea_threshold=float(hypopnea_threshold),
        raw_segments=int(raw_segment_count),
        filtered_segments=int(len(preliminary_events)),
        merged_segments=int(len(merged_events)),
        baseline_source="rolling_120s_pre_event_amplitude",
    )
    debug_events = [_build_event_debug_line(event.to_dict(), event.event_id) for event in events]

    return {
        "baseline_source": "rolling_120s_pre_event_amplitude",
        "pipeline_mode": "rule_first_ai_second",
        "rule_scan_used": True,
        "ai_enabled_requested": bool(enable_ai),
        "ai_model_loaded": model is not None,
        "rule_candidate_segments_found": int(raw_segment_count),
        "rule_candidates_after_filter": int(len(preliminary_events)),
        "rule_candidates_after_merge": int(len(merged_events)),
        "ai_candidates_processed": int(ai_candidates_processed),
        "baseline_airflow": float(baseline_airflow_reference),
        "baseline_airflow_note": "Legacy scalar reference only; detection uses hourly_peak_baselines per window.",
        "baseline_occurrence": int(baseline_occurrence),
        "stable_peak_baseline": float(baseline_airflow_reference),
        "stable_peak_baseline_note": "Legacy scalar reference only; detection uses hourly_peak_baselines per window.",
        "stable_peak_occurrence": int(baseline_occurrence),
        "stable_peak_occurrence_duration_sec": float(baseline_occurrence_duration_sec),
        "stable_peak_first_time_sec": float(baseline_peak_first_time) if baseline_peak_first_time is not None else None,
        "stable_peak_last_time_sec": float(baseline_peak_last_time) if baseline_peak_last_time is not None else None,
        "hourly_peak_baselines": hourly_peak_baselines,
        "stable_min_baseline": float(stable_min_airflow),
        "stable_min_occurrence": int(stable_min_occurrence),
        "airflow_reduction_scale": "percent_drop_from_baseline",
        "airflow_reduction_range": float(airflow_reduction_range),
        "hourly_airflow_reduction_ranges": [
            {
                "window_index": int(item["window_index"]),
                "window_label": str(item["window_label"]),
                "airflow_reduction_range": float(float(item["peak_value"]) - stable_min_airflow),
            }
            for item in hourly_peak_baselines
        ],
        "apnea_threshold": float(apnea_threshold),
        "hypopnea_threshold": float(hypopnea_threshold),
        "hourly_apnea_thresholds": [
            {
                "window_index": int(item["window_index"]),
                "window_label": str(item["window_label"]),
                "apnea_threshold": float(float(item["peak_value"]) * (1.0 - AASM_APNEA_DROP_PERCENT / 100.0)),
            }
            for item in hourly_peak_baselines
        ],
        "hourly_hypopnea_thresholds": [
            {
                "window_index": int(item["window_index"]),
                "window_label": str(item["window_label"]),
                "hypopnea_threshold": float(float(item["peak_value"]) * (1.0 - AASM_HYPOPNEA_DROP_PERCENT / 100.0)),
            }
            for item in hourly_peak_baselines
        ],
        "estimated_sample_rate_hz": float(estimated_fs),
        "preprocess_meta": preprocess_meta,
        "airflow_enhancement_applied": bool(airflow_enhancement_applied),
        "model_meta": model_meta,
        "debug_summary": debug_summary,
        "debug_events": debug_events,
        "events": [event.to_dict() for event in events],
        "desaturations": desaturations,
        "sensor_off_segments": sensor_off_segments,
        "sensor_off_total_sec": float(sum(item["duration_sec"] for item in sensor_off_segments)),
        "desaturation_count": len(desaturations),
        "odi_per_hour": (
            float(len(desaturations) / (float(time_sec[-1]) / 3600.0))
            if (spo2_usable and len(time_sec) and time_sec[-1] > 0)
            else None
        ),
        "spo2_channel_usable": bool(spo2_usable),
        "desat_threshold_percent": float(DESAT_DROP_PERCENT),
    }


def detect_apnea_events_from_csv(
    csv_path: str | Path,
    output_dir: str | Path | None = None,
    enable_ai: bool = False,
) -> dict[str, Any]:
    signal_df = load_sleep_csv(csv_path)
    result = detect_apnea_events_from_dataframe(signal_df, output_dir=output_dir, enable_ai=enable_ai)
    result["source_csv"] = str(csv_path)
    if output_dir is not None:
        result["text_report_path"] = str(_write_text_report(result, csv_path=csv_path, output_dir=output_dir))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Rule-based apnea detection with AI-assisted event labeling.")
    parser.add_argument("--input", required=True, help="Input CSV path")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR / "rule_ai_detector"))
    parser.add_argument("--enable-ai", action="store_true")
    args = parser.parse_args()

    result = detect_apnea_events_from_csv(
        csv_path=args.input,
        output_dir=args.output_dir,
        enable_ai=args.enable_ai,
    )

    print("Rule-based airflow detection summary")
    for line in result.get("debug_summary", []):
        print(f"  {line}")
    if result.get("debug_events"):
        print("Detected events")
        for line in result["debug_events"]:
            print(f"  {line}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{Path(args.input).stem}_rule_ai_events.json"
    report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("=" * 80)
    print("AIRFLOW BASELINE")
    print("=" * 80)
    print("Detection uses hourly/remainder peak baselines listed in the report.")
    print(f"Apnea threshold {AASM_APNEA_DROP_PERCENT:.0f}% drop    : airflow <= {result['apnea_threshold']:.2f}")
    print(f"Hypopnea threshold {AASM_HYPOPNEA_DROP_PERCENT:.0f}% drop : airflow <= {result['hypopnea_threshold']:.2f}")
    print("=" * 80)
    print(f"Total candidate events found: {len(result['events'])}")
    print("=" * 80)
    for event in result["events"]:
        print(
            f"Event {event['event_id']}: {event['start_sec']:.1f}s - {event['end_sec']:.1f}s | "
            f"rule={event['rule_label']} | ai={event.get('ai_label')} | final={event.get('final_label')}"
        )
    print("=" * 80)
    print(f"Saved rule+AI event report: {report_path}")


if __name__ == "__main__":
    main()
