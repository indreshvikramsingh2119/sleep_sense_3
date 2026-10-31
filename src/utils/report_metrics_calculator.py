"""
Sleep study metrics calculator.

This module centralizes the formulas used for oximetry, heart rate,
and snoring summaries so uploaded PSG data can be converted into a
single JSON payload immediately after load.

Formula notes:
- Mean SpO2 = sum(SpO2 readings) / count(SpO2 readings)
- Min/Max SpO2 = min/max of SpO2 readings
- Hypoxic burden = sum((95 - SpO2) * delta_t_minutes) for SpO2 < 95
- Total desats/events = count of contiguous SpO2 segments below 92%
- Desaturation index = total desats / sleep hours
- Desat max (%) = baseline SpO2 - minimum SpO2
- Duration below threshold = total time spent below that threshold
- Mean HR = sum(HR readings) / count(HR readings)
- Total snoring episodes = count of contiguous snoring segments above threshold
- Mean snoring duration = total snoring duration / episode count
- Snoring percentage = total snoring duration / total sleep duration
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import numpy as np

# The detector owns the single desaturation rule. Import it instead of scoring
# desaturations a second time here so the dashboard and the report stay aligned.
_APP_ROOT = Path(__file__).resolve().parents[2]
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

DESAT_SCORER_IMPORT_ERROR = None
try:
    from ai_models.sleep_apnea.detect_apnea_from_airflow import detect_desaturations
except Exception as import_error:  # pragma: no cover - defensive fallback
    detect_desaturations = None
    DESAT_SCORER_IMPORT_ERROR = str(import_error)

from .sample_rate import DEFAULT_SAMPLE_RATE_HZ
from .runtime_config import get_configured_path

DEFAULT_SNORING_THRESHOLD = 5.0
DEFAULT_MIN_SNORING_DURATION_SEC = 1.0
FIXED_SNORING_THRESHOLD = 6.0
FIXED_MIN_SNORING_DURATION_SEC = 1.0
FIXED_MAX_SNORING_DURATION_SEC = None  # long continuous snoring is kept, never discarded
# SD-card recordings: the reader already emits snore packets (adaptive noise floor,
# min 0.3 s, merge gap 0.2 s). Each packet = one snore event (~one breath).
# Literature-style episode = run of >= 3 consecutive snore events.
SNORE_EPISODE_MAX_GAP_SEC = 6.0      # max silence between events of one episode (app-defined)
SNORE_EPISODE_MIN_EVENTS = 3
DEFAULT_ANALYSIS_JSON_DIR = get_configured_path("analysis_json_dir")
INDEX_ON_VALID_TIME = True
HYPOXIC_BURDEN_BASELINE_SPO2 = 95.0
HYPOXIC_BURDEN_MIN_DROP_PCT = 3.0
HYPOXIC_BURDEN_RECOVERY_THRESHOLD = HYPOXIC_BURDEN_BASELINE_SPO2 - HYPOXIC_BURDEN_MIN_DROP_PCT
PUBLISHED_HB_EVENT_TYPES = {"OSA", "CSA", "MSA", "HSA", "HYPOPNEA"}
HB_WINDOW_MIN_LEN_SEC = 20
HB_WINDOW_MAX_LEN_SEC = 120
HB_WINDOW_MIN_START_SEC = -30
HB_FALLBACK_WINDOW_SEC = (-15, 45)
DESATURATION_EVENT_DROP_PCT = HYPOXIC_BURDEN_MIN_DROP_PCT
DESATURATION_EVENT_THRESHOLD_SPO2 = HYPOXIC_BURDEN_RECOVERY_THRESHOLD
MIN_VALID_SPO2_PCT = 70.0
MAX_VALID_SPO2_PCT = 100.0
MIN_VALID_SPO2_DURATION_SEC = 10.0
MIN_VALID_SPO2_RATIO = 0.5
ODI_BASELINE_WINDOW_SEC = 120.0
ODI_DEFAULT_THRESHOLD_PCT = 3.0
ODI_MIN_EVENT_DURATION_SEC = 10.0


def _as_float_array(values: Any) -> np.ndarray:
    array = np.asarray(values if values is not None else [], dtype=float).reshape(-1)
    if array.size == 0:
        return np.array([], dtype=float)
    return array[np.isfinite(array)]


def _first_signal(signals: Dict[str, Any], names: Iterable[str]) -> np.ndarray:
    for name in names:
        if name in signals and signals[name] is not None:
            return _as_float_array(signals[name])
    return np.array([], dtype=float)


def _aligned_sleep_mask(mask_values: Any, target_length: int) -> np.ndarray:
    mask_array = np.asarray(mask_values if mask_values is not None else [], dtype=float).reshape(-1)
    if target_length <= 0 or mask_array.size == 0:
        return np.zeros(max(target_length, 0), dtype=bool)
    if mask_array.size != target_length:
        limit = min(mask_array.size, target_length)
        aligned = np.zeros(target_length, dtype=float)
        aligned[:limit] = mask_array[:limit]
        mask_array = aligned
    finite_mask = np.isfinite(mask_array)
    sleep_mask = np.zeros(target_length, dtype=bool)
    sleep_mask[finite_mask] = mask_array[finite_mask] > 0
    return sleep_mask


def _time_step_seconds(time_data: Any, fallback_sample_rate_hz: float) -> float:
    time_array = _as_float_array(time_data)
    if time_array.size >= 2:
        diffs = np.diff(time_array)
        finite_diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
        if finite_diffs.size:
            raw_step = float(np.median(finite_diffs))
            # Tera exports often store timestamps in milliseconds.
            if raw_step > 10.0:
                return raw_step / 1000.0
            return raw_step
    if fallback_sample_rate_hz > 0:
        return 1.0 / float(fallback_sample_rate_hz)
    return 1.0


def _sample_rate_hz(time_data: Any, fallback_sample_rate_hz: float) -> float:
    step_seconds = _time_step_seconds(time_data, fallback_sample_rate_hz)
    if step_seconds > 0:
        return 1.0 / step_seconds
    return float(fallback_sample_rate_hz)


def _contiguous_segments(mask: np.ndarray) -> list[tuple[int, int]]:
    mask = np.asarray(mask, dtype=bool).reshape(-1)
    if mask.size == 0:
        return []

    segments = []
    start_index = None
    for index, value in enumerate(mask):
        if value and start_index is None:
            start_index = index
        elif not value and start_index is not None:
            segments.append((start_index, index))
            start_index = None
    if start_index is not None:
        segments.append((start_index, len(mask)))
    return segments


def _duration_text(seconds: float) -> str:
    seconds = float(max(0.0, seconds))
    if seconds < 60.0:
        return f"{seconds:.1f} sec"
    return f"{seconds / 60.0:.1f} min"


def _number_text(value: Optional[float]) -> str:
    if value is None or not np.isfinite(value):
        return "-"
    if abs(value - round(value)) < 1e-6:
        return str(int(round(value)))
    return f"{float(value):.1f}"


def _clock_time_text(timestamp_value: Any) -> str:
    try:
        numeric_value = float(timestamp_value)
    except (TypeError, ValueError):
        return "-"
    if not np.isfinite(numeric_value) or numeric_value <= 0:
        return "-"

    try:
        if numeric_value > 1e12:
            dt = datetime.fromtimestamp(numeric_value / 1000.0)
        elif numeric_value > 1e9:
            dt = datetime.fromtimestamp(numeric_value)
        else:
            return "-"
        return dt.strftime("%I:%M:%S %p")
    except Exception:
        return "-"


def _label_index_per_hour(count: int, hours: float) -> float:
    return float(count / hours) if hours > 0 else 0.0


def _severity_from_ahi(ahi_value: float) -> str:
    if ahi_value < 5:
        return "Normal"
    if ahi_value < 15:
        return "Mild"
    if ahi_value < 30:
        return "Moderate"
    return "Severe"


def _severity_from_hb_index(hb_index_value: float) -> str:
    if hb_index_value < 5.0:
        return "Normal"
    if hb_index_value < 30.0:
        return "Mild"
    if hb_index_value < 70.0:
        return "Moderate"
    return "Severe"


def _severity_from_odi(odi_value: float) -> str:
    if odi_value < 5.0:
        return "Normal"
    if odi_value < 15.0:
        return "Mild"
    if odi_value < 30.0:
        return "Moderate"
    return "Severe"


def _heart_rate_rhythm_label(highest_hr: Optional[float], lowest_hr: Optional[float]) -> str:
    highest = float(highest_hr) if highest_hr is not None and np.isfinite(highest_hr) else None
    lowest = float(lowest_hr) if lowest_hr is not None and np.isfinite(lowest_hr) else None
    labels: list[str] = []
    if highest is not None and highest > 100.0:
        labels.append("Sinus Tachycardia")
    if lowest is not None and lowest < 50.0:
        labels.append("Sinus Bradycardia")
    if labels:
        return " / ".join(labels)
    return "Normal Sinus Rhythm"


def _body_position_name(value: Any) -> str | None:
    try:
        numeric_value = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    mapping = {
        0: "Supine",
        1: "Left",
        2: "Right",
        3: "Prone",
        4: "Up",
    }
    return mapping.get(numeric_value)


def _baseline_spo2(spo2: np.ndarray) -> float:
    if spo2.size == 0:
        return 0.0
    upper_cutoff = np.percentile(spo2, 90)
    upper_values = spo2[spo2 >= upper_cutoff]
    if upper_values.size == 0:
        return float(np.percentile(spo2, 95))
    return float(np.mean(upper_values))


def _empty_hypoxic_metrics(status: str = "invalid", reason: str = "No valid SpO2 samples available.") -> Dict[str, Any]:
    return {
        "hypoxic_burden": 0.0,
        "hypoxic_burden_display": "0.00 %-min",
        "longest_duration_sec": 0.0,
        "longest_duration_display": "0.0 sec",
        "total_count_event": 0,
        "total_count_event_display": "0",
        "desaturation_index": 0.0,
        "desaturation_index_display": "0.0",
        "hb_index": 0.0,
        "hb_index_display": "0.0 %min/h",
        "hb_severity": "Normal",
        "total_desats": 0,
        "total_desats_display": "0",
        "quality_status": status,
        "quality_reason": reason,
        "raw_sample_count": 0,
        "valid_sample_count": 0,
        "valid_duration_sec": 0.0,
        "valid_ratio": 0.0,
    }


def _filter_valid_spo2_samples(spo2_values: Any, step_seconds: float) -> tuple[np.ndarray, Dict[str, Any]]:
    # Preserve the original sample count, including NaN sensor-off samples,
    # so valid SpO2 coverage is not falsely reported as 100%.
    raw_spo2 = np.asarray(spo2_values if spo2_values is not None else [], dtype=float).reshape(-1)
    if raw_spo2.size == 0:
        return np.array([], dtype=float), _empty_hypoxic_metrics()

    artifact_mask = np.isfinite(raw_spo2) & (raw_spo2 >= MIN_VALID_SPO2_PCT) & (raw_spo2 <= MAX_VALID_SPO2_PCT)
    valid_spo2 = raw_spo2[artifact_mask]
    raw_sample_count = int(raw_spo2.size)
    valid_sample_count = int(valid_spo2.size)
    valid_ratio = float(valid_sample_count / raw_sample_count) if raw_sample_count > 0 else 0.0
    valid_duration_sec = float(valid_sample_count * max(float(step_seconds), 0.0))

    quality = _empty_hypoxic_metrics()
    quality.update({
        "quality_status": "valid",
        "quality_reason": "",
        "raw_sample_count": raw_sample_count,
        "valid_sample_count": valid_sample_count,
        "valid_duration_sec": valid_duration_sec,
        "valid_ratio": valid_ratio,
    })

    if valid_sample_count == 0:
        quality["quality_status"] = "invalid"
        quality["quality_reason"] = "Invalid recording - no SpO2 samples remained after artifact rejection."
        return valid_spo2, quality
    if valid_duration_sec < MIN_VALID_SPO2_DURATION_SEC:
        quality["quality_status"] = "invalid"
        quality["quality_reason"] = (
            f"Invalid recording - only {valid_duration_sec:.1f} sec of valid SpO2 data; "
            f"at least {MIN_VALID_SPO2_DURATION_SEC:.0f} sec is required."
        )
        return valid_spo2, quality
    if valid_ratio < MIN_VALID_SPO2_RATIO:
        quality["quality_status"] = "invalid"
        quality["quality_reason"] = (
            f"Invalid recording - only {valid_ratio * 100.0:.0f}% of SpO2 samples are valid; "
            f"at least {MIN_VALID_SPO2_RATIO * 100.0:.0f}% is required."
        )
        return valid_spo2, quality
    return valid_spo2, quality


def _bridge_zero_gaps(
    values: Any,
    step_seconds: float,
    max_gap_seconds: float | None = None,
) -> np.ndarray:
    """Replace missing/zero readings with the preceding valid reading.

    For SpO2, zero is an invalid device sentinel, never a physiological
    saturation.  The default therefore holds the preceding valid value for
    every subsequent zero run, keeping the displayed and reported series in
    sync.  A finite limit remains available for channels that need it.
    """
    signal = np.asarray(values, dtype=float).reshape(-1).copy()
    missing = ~np.isfinite(signal) | (signal <= 0.0)
    if not missing.any() or missing.all():
        return np.where(missing, np.nan, signal)
    signal[missing] = np.nan
    max_samples = (
        None if max_gap_seconds is None
        else max(1, int(np.floor(float(max_gap_seconds) / max(float(step_seconds), 1e-9))))
    )
    edges = np.diff(np.r_[False, missing, False].astype(np.int8))
    for start, stop in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        if (
            start > 0
            and (max_samples is None or stop - start <= max_samples)
            and np.isfinite(signal[start - 1])
        ):
            signal[start:stop] = signal[start - 1]
    return signal


def calculate_hypoxic_burden_metrics(
    spo2_values: Any,
    step_seconds: float,
    baseline_spo2: float = HYPOXIC_BURDEN_BASELINE_SPO2,
    event_threshold_spo2: float = DESATURATION_EVENT_THRESHOLD_SPO2,
    recovery_threshold_spo2: float = HYPOXIC_BURDEN_RECOVERY_THRESHOLD,
) -> Dict[str, float]:
    """Calculate event-based hypoxic burden metrics from SpO2 samples."""
    valid_spo2, quality = _filter_valid_spo2_samples(spo2_values, step_seconds)
    if quality["quality_status"] != "valid":
        return quality

    sample_interval_min = max(float(step_seconds), 0.0) / 60.0
    baseline_spo2 = float(baseline_spo2)
    event_threshold_spo2 = float(event_threshold_spo2)
    recovery_threshold_spo2 = float(recovery_threshold_spo2)

    # Hypoxic burden keeps its own published definition: area under the 95%
    # baseline. It is not the desaturation count, so it stays independent.
    hypoxic_burden = 0.0
    total_count_event = 0
    longest_duration_sec = 0.0
    in_event = False
    event_burden = 0.0
    event_sample_count = 0

    # Walk the original time-aligned series so a long sensor-off gap ends an
    # event instead of concatenating samples from before and after the gap.
    event_series = np.asarray(spo2_values if spo2_values is not None else [], dtype=float).reshape(-1)
    for raw_value in event_series:
        if not np.isfinite(raw_value) or raw_value < MIN_VALID_SPO2_PCT or raw_value > MAX_VALID_SPO2_PCT:
            if in_event and event_burden > 0.0:
                hypoxic_burden += event_burden
                total_count_event += 1
                longest_duration_sec = max(longest_duration_sec, float(event_sample_count) * float(step_seconds))
            in_event = False
            event_burden = 0.0
            event_sample_count = 0
            continue
        spo2 = raw_value
        spo2_value = float(spo2)
        deficit = max(baseline_spo2 - spo2_value, 0.0) * sample_interval_min

        if not in_event:
            if spo2_value < event_threshold_spo2:
                in_event = True
                event_burden = deficit
                event_sample_count = 1
            continue

        if spo2_value < recovery_threshold_spo2:
            event_burden += deficit
            event_sample_count += 1
            continue

        hypoxic_burden += event_burden
        total_count_event += 1
        longest_duration_sec = max(longest_duration_sec, float(event_sample_count) * float(step_seconds))
        event_burden = 0.0
        event_sample_count = 0
        in_event = False

    if in_event and event_burden > 0.0:
        hypoxic_burden += event_burden
        total_count_event += 1
        longest_duration_sec = max(longest_duration_sec, float(event_sample_count) * float(step_seconds))

    # Desaturation count / index / longest come from the detector's single
    # AASM rule (>=3% below the pre-event baseline). The old sweep counted
    # "SpO2 below 92%" instead, which can miss real desaturations.
    aligned = np.asarray(spo2_values if spo2_values is not None else [], dtype=float).reshape(-1)
    aligned = aligned.astype(float)
    aligned[
        ~np.isfinite(aligned)
        | (aligned < MIN_VALID_SPO2_PCT)
        | (aligned > MAX_VALID_SPO2_PCT)
    ] = np.nan
    time_axis = np.arange(aligned.size, dtype=float) * float(step_seconds)

    if detect_desaturations is not None:
        desat_events = detect_desaturations(time_axis, aligned)
    else:  # Detector unavailable - keep the old absolute-threshold fallback.
        desat_events = [
            {"duration_sec": float((end_index - start_index) * float(step_seconds))}
            for start_index, end_index in _contiguous_segments(
                np.nan_to_num(aligned, nan=100.0) < float(event_threshold_spo2)
            )
        ]

    total_count_event = int(len(desat_events))
    longest_duration_sec = float(
        max((float(event.get("duration_sec", 0.0)) for event in desat_events), default=0.0)
    )

    # aligned.size, not valid_spo2.size: valid_spo2 has artifact samples removed,
    # and shrinking the denominator would inflate every per-hour index.
    sleep_duration_hours = float((aligned.size * float(step_seconds)) / 3600.0) if step_seconds > 0 else 0.0
    desaturation_index = float(total_count_event / sleep_duration_hours) if sleep_duration_hours > 0 else 0.0
    hb_index = float(hypoxic_burden / sleep_duration_hours) if sleep_duration_hours > 0 else 0.0

    quality.update({
        "hypoxic_burden": hypoxic_burden,
        "hypoxic_burden_display": f"{hypoxic_burden:.2f} %-min",
        "longest_duration_sec": longest_duration_sec,
        "longest_duration_display": _duration_text(longest_duration_sec),
        "total_count_event": total_count_event,
        "total_count_event_display": str(total_count_event),
        "desaturation_index": desaturation_index,
        "desaturation_index_display": f"{desaturation_index:.1f}",
        "hb_index": hb_index,
        "hb_index_display": f"{hb_index:.1f} %min/h",
        "hb_severity": _severity_from_hb_index(hb_index),
        "total_desats": total_count_event,
        "total_desats_display": str(total_count_event),
    })
    return quality


def _published_hypoxic_burden(spo2: Any, detected_events: Any, hours: float, valid_mask: Any = None) -> Dict[str, Any]:
    """Azarbarzin-style event-linked HB with guarded window and union overlap."""
    x = np.asarray(spo2 if spo2 is not None else [], dtype=float).reshape(-1)
    mask = None if valid_mask is None else np.asarray(valid_mask, dtype=bool).reshape(-1)
    events = []
    for event in detected_events or []:
        label = str(event.get("final_label") or event.get("rule_label") or "").upper().replace(" ", "_")
        if label in PUBLISHED_HB_EVENT_TYPES:
            try:
                end = int(round(float(event.get("end_sec"))))
            except (TypeError, ValueError):
                continue
            if 100 <= end < x.size and (mask is None or end >= mask.size or mask[end]):
                events.append(end)
    events = sorted(set(events))
    if not events:
        # Must carry the SAME keys as the normal return: calculate_report_context reads window_status and
        # hb_total_sum_mode, and a KeyError here made the Report button silently do nothing.
        return {
            "hypoxic_burden": 0.0,
            "hb_index": 0.0,
            "window": None,
            "window_status": "no usable events",
            "hb_total_sum_mode": 0.0,
            "event_count": 0,
        }

    # Event-end aligned ensemble average. The nadir is constrained to the
    # expected oximeter lag (0..40 s); the surrounding maxima define the window.
    pre, post = 100, 100
    usable = [x[e - pre:e + post + 1] for e in events
              if np.isfinite(x[e - pre:e + post + 1]).mean() >= 0.7]
    window = HB_FALLBACK_WINDOW_SEC
    window_status = "fallback (fewer than 5 usable events)"
    if len(usable) >= 5:
        avg = np.nanmean(np.vstack(usable), axis=0)
        avg = np.convolve(np.nan_to_num(avg, nan=np.nanmean(avg)), np.ones(3) / 3, mode="same")
        lo, hi = pre, pre + 40
        nadir = lo + int(np.nanargmin(avg[lo:hi + 1]))
        left = int(np.nanargmax(avg[:nadir + 1]))
        right = nadir + int(np.nanargmax(avg[nadir:]))
        candidate = (left - pre, right - pre)
        length = candidate[1] - candidate[0]
        if HB_WINDOW_MIN_LEN_SEC <= length <= HB_WINDOW_MAX_LEN_SEC and candidate[0] >= HB_WINDOW_MIN_START_SEC:
            window, window_status = candidate, "ensemble"
        else:
            window_status = f"fallback (ensemble window {candidate[0]}..{candidate[1]} s rejected)"

    union = np.zeros(x.size, dtype=float)
    total_sum = 0.0
    used = 0
    for end in events:
        baseline_values = x[end - 100:end + 1]
        if np.isfinite(baseline_values).sum() < 50:
            continue
        baseline = float(np.nanmax(baseline_values))
        start = max(0, end + window[0])
        stop = min(x.size, end + window[1] + 1)
        segment = x[start:stop]
        deficit = np.nan_to_num(np.maximum(baseline - segment, 0.0))
        total_sum += float(deficit.sum()) / 60.0
        union[start:stop] = np.maximum(union[start:stop], deficit)
        used += 1
    total = float(union.sum()) / 60.0
    return {
        "hypoxic_burden": total,
        "hb_index": total / hours if hours > 0 else 0.0,
        "window": window,
        "window_status": window_status,
        "hb_total_sum_mode": total_sum,
        "event_count": used,
    }


def _count_odi_events(series: np.ndarray, window_samples: int, min_event_samples: int,
                      threshold_pct: float) -> int:
    """Count ODI events; same result as the original per-sample scan, in one pass.

    The scan compared every valid sample with the median of the (up to ``window_samples``) valid samples
    just before it, walking backwards in Python for every sample (O(samples x window)).  That baseline only
    depends on the data, so it is computed once for all samples with a trailing rolling median that restarts
    after every invalid sample; only the (few) events are then walked one by one, exactly as before.
    """
    import pandas as pd

    n = int(series.size)
    if n == 0:
        return 0
    with np.errstate(invalid="ignore"):
        valid = np.isfinite(series) & (series >= MIN_VALID_SPO2_PCT) & (series <= MAX_VALID_SPO2_PCT)
    if not valid.any():
        return 0
    baseline = series.copy()                       # first sample of a valid run has no history: itself
    edges = np.diff(np.r_[False, valid, False].astype(np.int8))
    for run_start, run_stop in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        if run_stop - run_start > 1:
            run = pd.Series(series[run_start:run_stop])
            previous = run.rolling(window_samples, min_periods=1).median().shift(1).to_numpy(dtype=float)
            baseline[run_start + 1:run_stop] = previous[1:]
    with np.errstate(invalid="ignore"):
        candidate = valid & ((baseline - series) >= threshold_pct)

    event_count = 0
    index = 0
    candidates = np.flatnonzero(candidate)
    position = 0
    while position < candidates.size:
        onset = int(candidates[position])
        if onset < index:
            position += 1
            continue
        fixed = float(baseline[onset])
        end = onset
        while end < n and valid[end] and fixed - float(series[end]) >= threshold_pct:
            end += 1
        if (end - onset) >= min_event_samples:
            event_count += 1
        index = end
        position += 1
    return int(event_count)


def calculate_odi_metrics(
    spo2_values: Any,
    step_seconds: float,
    threshold_pct: float = ODI_DEFAULT_THRESHOLD_PCT,
    min_duration_sec: float = ODI_MIN_EVENT_DURATION_SEC,
    baseline_window_sec: float = ODI_BASELINE_WINDOW_SEC,
) -> Dict[str, Any]:
    """Calculate ODI from valid SpO2 samples using a trailing rolling baseline."""
    valid_spo2, quality = _filter_valid_spo2_samples(spo2_values, step_seconds)
    result = {
        "odi": 0.0,
        "odi_display": "0.0 /h",
        "odi_event_count": 0,
        "odi_event_count_display": "0",
        "odi_severity": "Normal",
    }
    if quality["quality_status"] != "valid":
        return result

    if step_seconds <= 0 or valid_spo2.size == 0:
        return result

    window_samples = max(1, int(round(float(baseline_window_sec) / float(step_seconds))))
    min_event_samples = max(1, int(np.ceil(float(min_duration_sec) / float(step_seconds))))
    threshold_pct = float(threshold_pct)

    event_count = 0
    series = np.asarray(spo2_values if spo2_values is not None else [], dtype=float).reshape(-1)
    event_count = _count_odi_events(series, window_samples, min_event_samples, threshold_pct)

    valid_hours = float(valid_spo2.size * float(step_seconds)) / 3600.0
    odi_value = float(event_count / valid_hours) if valid_hours > 0 else 0.0
    result.update({
        "odi": odi_value,
        "odi_display": f"{odi_value:.1f} /h",
        "odi_event_count": int(event_count),
        "odi_event_count_display": str(int(event_count)),
        "odi_severity": _severity_from_odi(odi_value),
    })
    return result


def _variability_label(std_dev: float) -> str:
    if std_dev < 1.5:
        return "Low"
    if std_dev < 3.0:
        return "Moderate"
    return "High"


def _trend_label(time_seconds: np.ndarray, values: np.ndarray) -> str:
    if values.size < 2:
        return "Stable"
    if time_seconds.size != values.size:
        time_seconds = np.arange(values.size, dtype=float)   
    slope = float(np.polyfit(time_seconds, values, 1)[0])
    if abs(slope) < 0.001:
        return "Stable"
    return "Rising" if slope > 0 else "Falling"


def _snoring_phase_counts(signals) -> Dict[str, Any]:
    """Return inhale/exhale counts from the SD snore packet table."""
    table = signals.get("snoring_packets") if isinstance(signals, dict) else None
    if table is None:
        return {}
    table = np.asarray(table, dtype=float)
    if table.ndim != 2 or table.shape[1] < 3:
        return {}
    phase = table[:, 2] if table.shape[0] else np.zeros(0)
    inhale = int(np.sum(phase == 1))
    exhale = int(np.sum(phase == 2))
    isolated = int(np.sum(phase == 3))
    unknown = int(np.sum(phase == 4))
    total = inhale + exhale + isolated + unknown
    return {
        "snoring_packets_total": total,
        "snoring_inhale_episodes": inhale,
        "snoring_exhale_episodes": exhale,
        "snoring_exhale_isolated_episodes": isolated,
        "snoring_phase_unknown_episodes": unknown,
        "snoring_inhale_share_percent": (inhale / total * 100.0) if total else 0.0,
    }


def _snoring_segments(
    snoring: np.ndarray,
    threshold: float = DEFAULT_SNORING_THRESHOLD,
    step_seconds: float | None = None,
    min_duration_sec: float = DEFAULT_MIN_SNORING_DURATION_SEC,
    max_duration_sec: float | None = None,
) -> list[tuple[int, int]]:
    """Contiguous snoring episodes above ``threshold`` (legacy / CSV path).

    A short rolling maximum of |snoring| (~0.25 s) bridges the zero crossings of a
    bipolar vibration so one snore is one segment. That padding is ONLY used to
    decide which samples belong together: the min/max duration checks and the
    returned (start, end) use the real, un-padded extent of the snore, so the
    padding can no longer lengthen a snore or let a too-short one through.
    """
    magnitude = np.abs(np.asarray(snoring, dtype=float))
    raw_active = magnitude > threshold
    dilated = magnitude
    if step_seconds and step_seconds > 0:
        window = int(round(0.25 / float(step_seconds)))
        if window >= 3 and magnitude.size >= window:
            import pandas as pd
            dilated = (
                pd.Series(magnitude)
                .rolling(window, center=True, min_periods=1)
                .max()
                .to_numpy(dtype=float)
            )
    step = float(step_seconds or 1.0)
    minimum_samples = max(1, int(np.ceil(float(min_duration_sec) / step)))
    maximum_samples = None
    if max_duration_sec is not None and max_duration_sec > 0 and step > 0:
        maximum_samples = int(np.floor(float(max_duration_sec) / step))

    accepted: list[tuple[int, int]] = []
    for start, end in _contiguous_segments(dilated > threshold):
        hits = np.flatnonzero(raw_active[start:end])
        if hits.size == 0:
            continue
        true_start = start + int(hits[0])
        true_end = start + int(hits[-1]) + 1
        length = true_end - true_start
        if length < minimum_samples:
            continue
        if maximum_samples is not None and length > maximum_samples:
            continue
        accepted.append((true_start, true_end))
    return accepted


def _snore_events_from_packets(packets: Any, step_seconds: float) -> np.ndarray:
    """(n, 2) array of [start_sec, end_sec] from the reader's ``snoring_packets`` table.

    Column 0/1 are start/end sample indices at the snoring sample rate. The reader has
    already applied the minimum duration, so no extra duration filter is applied here.
    """
    table = np.asarray(packets, dtype=float)
    if table.ndim != 2 or table.shape[0] == 0 or table.shape[1] < 2:
        return np.zeros((0, 2), dtype=float)
    events = np.column_stack([table[:, 0] * step_seconds, table[:, 1] * step_seconds])
    return events[np.argsort(events[:, 0], kind="stable")]


def _group_snore_episodes(
    events: np.ndarray,
    max_gap_sec: float = SNORE_EPISODE_MAX_GAP_SEC,
    min_events: int = SNORE_EPISODE_MIN_EVENTS,
) -> np.ndarray:
    """Group snore events into episodes: >= ``min_events`` events, each gap <= ``max_gap_sec``.

    Returns an (n, 3) array of [start_sec, end_sec, event_count].
    """
    events = np.asarray(events, dtype=float).reshape(-1, 2)
    if events.shape[0] == 0:
        return np.zeros((0, 3), dtype=float)
    groups: list[list[int]] = []
    current = [0]
    for i in range(1, events.shape[0]):
        if events[i, 0] - events[i - 1, 1] <= max_gap_sec:
            current.append(i)
        else:
            groups.append(current)
            current = [i]
    groups.append(current)
    rows = [
        [events[g[0], 0], events[g[-1], 1], float(len(g))]
        for g in groups if len(g) >= int(min_events)
    ]
    return np.asarray(rows, dtype=float).reshape(-1, 3)


def _build_snoring_summary(
    snoring: np.ndarray,
    signals: Dict[str, Any],
    step_seconds: float,
    threshold: float,
    min_duration_sec: float,
    max_duration_sec: float | None,
    recording_sec: float,
    sleep_flags: np.ndarray | None = None,
    flag_step_seconds: float = 1.0,
) -> Dict[str, Any]:
    """Snore events, snore index, snoring %, and >=3-event episodes."""
    finite = snoring[np.isfinite(snoring)] if snoring.size else snoring
    packets = signals.get("snoring_packets") if isinstance(signals, dict) else None
    packets_arr = np.asarray(packets, dtype=float) if packets is not None else None
    if packets_arr is not None and packets_arr.ndim == 2 and packets_arr.shape[1] >= 2 and (
        packets_arr.shape[0] > 0 or not finite.size or not np.any(finite != 0)
    ):
        events = _snore_events_from_packets(packets_arr, step_seconds)
        method = "device_packets"
    else:
        segments = _snoring_segments(
            finite, threshold=threshold, step_seconds=step_seconds,
            min_duration_sec=min_duration_sec, max_duration_sec=max_duration_sec,
        )
        events = (np.asarray(segments, dtype=float).reshape(-1, 2) * step_seconds
                  if segments else np.zeros((0, 2), dtype=float))
        method = "threshold_segments"

    basis, denominator = "recording", float(recording_sec)
    if denominator > 0 and events.size:
        events = events[events[:, 0] < denominator]      # keep numerator inside the analysed window
    if sleep_flags is not None and sleep_flags.size and bool(np.any(sleep_flags)):
        if events.size:
            mid = (events[:, 0] + events[:, 1]) / 2.0
            idx = np.minimum((mid / float(flag_step_seconds)).astype(int), sleep_flags.size - 1)
            events = events[sleep_flags[idx]]
        denominator = float(np.sum(sleep_flags)) * float(flag_step_seconds)
        basis = "sleep"

    durations = events[:, 1] - events[:, 0] if events.size else np.zeros(0)
    event_count = int(durations.size)
    total_sec = float(np.sum(durations))
    mean_event_sec = total_sec / event_count if event_count else 0.0
    hours = denominator / 3600.0 if denominator > 0 else 0.0
    percentage = (total_sec / denominator * 100.0) if denominator > 0 else 0.0
    index_per_hour = event_count / hours if hours > 0 else 0.0

    episodes = _group_snore_episodes(events)
    episode_count = int(episodes.shape[0])
    episode_durations = episodes[:, 1] - episodes[:, 0] if episode_count else np.zeros(0)
    mean_episode_sec = float(np.mean(episode_durations)) if episode_count else 0.0
    longest_episode_sec = float(np.max(episode_durations)) if episode_count else 0.0
    episode_index = episode_count / hours if hours > 0 else 0.0

    return {
        "snoring_method": method,
        "snoring_basis": basis,
        "snoring_denominator_sec": denominator,
        "snoring_threshold": threshold,
        "snoring_min_duration_sec": float(min_duration_sec),
        "snoring_episode_definition": (
            f">= {SNORE_EPISODE_MIN_EVENTS} snore events, gap <= {SNORE_EPISODE_MAX_GAP_SEC:g} s"
        ),
        "total_snoring_events": event_count,
        "total_snoring_events_display": str(event_count),
        "snore_index_per_hour": index_per_hour,
        "snore_index_display": f"{index_per_hour:.0f} /h",
        "total_snoring_episodes": episode_count,
        "total_snoring_episodes_display": str(episode_count),
        "snore_episode_index_per_hour": episode_index,
        "snore_episode_index_display": f"{episode_index:.1f} /h",
        "mean_snoring_episode_duration_sec": mean_episode_sec,
        "mean_snoring_episode_duration_display": _duration_text(mean_episode_sec),
        "longest_snoring_episode_duration_sec": longest_episode_sec,
        "longest_snoring_episode_duration_display": _duration_text(longest_episode_sec),
        "total_snoring_duration_sec": total_sec,
        "total_snoring_duration_display": _duration_text(total_sec),
        "mean_snoring_duration_sec": mean_event_sec,
        "mean_snoring_duration_display": _duration_text(mean_event_sec),
        "snoring_percentage": percentage,
        "snoring_percentage_display": f"{percentage:.1f} %",
        "snoring_signal_min": float(np.min(finite)) if finite.size else None,
        "snoring_signal_max": float(np.max(finite)) if finite.size else None,
        "snoring_signal_mean": float(np.mean(finite)) if finite.size else None,
    }


def calculate_sleep_metrics(
    time_data: Any,
    signals: Dict[str, Any],
    sleep_mask: Any = None,
    sample_rate_hz: float = DEFAULT_SAMPLE_RATE_HZ,
    snoring_threshold: float = DEFAULT_SNORING_THRESHOLD,
    snoring_min_duration_sec: float = DEFAULT_MIN_SNORING_DURATION_SEC,
    snoring_max_duration_sec: float | None = 5.0,
    sample_rates: Dict[str, float] | None = None,
    channel_times: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Calculate summary metrics from loaded PSG signals."""
    # Keep the clinical snoring definition fixed across reports.
    snoring_threshold = FIXED_SNORING_THRESHOLD
    snoring_min_duration_sec = FIXED_MIN_SNORING_DURATION_SEC
    snoring_max_duration_sec = FIXED_MAX_SNORING_DURATION_SEC
    time_array = _as_float_array(time_data)
    actual_sample_rate_hz = _sample_rate_hz(time_array, sample_rate_hz)
    step_seconds = 1.0 / actual_sample_rate_hz if actual_sample_rate_hz > 0 else _time_step_seconds(time_array, sample_rate_hz)

    spo2 = _first_signal(signals, ("spo2", "SpO2"))
    pulse = _first_signal(signals, ("pulse", "Pulse", "hr", "heart_rate"))
    snoring = _first_signal(signals, ("snoring", "Snoring"))

    def _channel_step(name: str) -> float:
        if sample_rates and name in sample_rates:
            try:
                rate = float(sample_rates[name])
                if rate > 0:
                    return 1.0 / rate
            except (TypeError, ValueError):
                pass
        if channel_times and name in channel_times:
            step = _time_step_seconds(channel_times[name], 0.0)
            if step > 0:
                return step
        return step_seconds

    spo2_step_seconds = _channel_step("spo2")
    snoring_step_seconds = _channel_step("snoring")
    # Zero is an invalid SpO2 sentinel. Hold the preceding valid saturation
    # through every subsequent zero run, exactly as the dashboard does.
    spo2 = _bridge_zero_gaps(spo2, spo2_step_seconds)
    pulse = _bridge_zero_gaps(pulse, _channel_step("pulse"), max_gap_seconds=60.0)

    sleep_duration_sec = float(len(time_array) * step_seconds) if time_array.size else float(max(len(spo2), len(pulse), len(snoring)) * step_seconds)
    sleep_hours = sleep_duration_sec / 3600.0 if sleep_duration_sec > 0 else 0.0

    oximetry: Dict[str, Any] = {}
    hypoxic_metrics = _empty_hypoxic_metrics(reason="No SpO2 signal available.")
    odi_metrics = {
        "odi": 0.0,
        "odi_display": "0.0 /h",
        "odi_event_count": 0,
        "odi_event_count_display": "0",
        "odi_severity": "Normal",
    }
    valid_spo2 = np.array([], dtype=float)
    if spo2.size:
        hypoxic_metrics = calculate_hypoxic_burden_metrics(spo2, spo2_step_seconds)
        odi_metrics = calculate_odi_metrics(spo2, spo2_step_seconds, threshold_pct=ODI_DEFAULT_THRESHOLD_PCT)
        valid_spo2, _quality = _filter_valid_spo2_samples(spo2, spo2_step_seconds)
        if hypoxic_metrics["quality_status"] != "valid":
            valid_spo2 = np.array([], dtype=float)

    if spo2.size and valid_spo2.size:
        baseline = _baseline_spo2(valid_spo2)
        # Keep the original timeline here; compacting valid samples would
        # incorrectly join desaturation periods across sensor-off gaps.
        aligned_spo2 = np.asarray(spo2, dtype=float).reshape(-1)
        below_90 = np.isfinite(aligned_spo2) & (aligned_spo2 >= MIN_VALID_SPO2_PCT) & (aligned_spo2 < 90.0)
        below_85 = np.isfinite(aligned_spo2) & (aligned_spo2 >= MIN_VALID_SPO2_PCT) & (aligned_spo2 < 85.0)
        below_80 = np.isfinite(aligned_spo2) & (aligned_spo2 >= MIN_VALID_SPO2_PCT) & (aligned_spo2 < 80.0)
        segments_below_90 = _contiguous_segments(below_90)
        desat_durations = [(end - start) * spo2_step_seconds for start, end in segments_below_90]

        minimum_value = float(np.nanmin(aligned_spo2))
        maximum_value = float(np.nanmax(aligned_spo2))
        min_duration = float(np.sum(np.isclose(aligned_spo2, minimum_value))) * spo2_step_seconds
        max_duration = float(np.sum(np.isclose(aligned_spo2, maximum_value))) * spo2_step_seconds
        desat_max_sec = float(max(desat_durations)) if desat_durations else 0.0
        duration_below_90_sec = float(np.sum(below_90)) * spo2_step_seconds
        duration_below_85_sec = float(np.sum(below_85)) * spo2_step_seconds
        duration_below_80_sec = float(np.sum(below_80)) * spo2_step_seconds
        valid_spo2_ratio_pct = float(hypoxic_metrics["valid_ratio"] * 100.0)
        duration_below_90_pct = (duration_below_90_sec / sleep_duration_sec) * 100.0 if sleep_duration_sec > 0 else 0.0
        duration_below_85_pct = (duration_below_85_sec / sleep_duration_sec) * 100.0 if sleep_duration_sec > 0 else 0.0
        duration_below_80_pct = (duration_below_80_sec / sleep_duration_sec) * 100.0 if sleep_duration_sec > 0 else 0.0

        oximetry = {
            "mean_spo2": float(np.mean(valid_spo2)),
            "mean_spo2_display": _number_text(float(np.mean(valid_spo2))),
            "min_spo2": minimum_value,
            "min_spo2_display": _number_text(minimum_value),
            "max_spo2": maximum_value,
            "max_spo2_display": _number_text(maximum_value),
            "total_desats": hypoxic_metrics["total_desats"],
            "total_desats_display": hypoxic_metrics["total_desats_display"],
            "desaturation_index": hypoxic_metrics["desaturation_index"],
            "desaturation_index_display": hypoxic_metrics["desaturation_index_display"],
            "odi3": odi_metrics["odi"],
            "odi3_display": odi_metrics["odi_display"],
            "odi3_event_count": odi_metrics["odi_event_count"],
            "odi3_event_count_display": odi_metrics["odi_event_count_display"],
            "odi3_severity": odi_metrics["odi_severity"],
            "desat_max_pct": max(0.0, baseline - minimum_value),
            "desat_max_pct_display": f"{max(0.0, baseline - minimum_value):.1f}",
            "hypoxic_burden": hypoxic_metrics["hypoxic_burden"],
            "hypoxic_burden_display": hypoxic_metrics["hypoxic_burden_display"],
            "hb_index": hypoxic_metrics["hb_index"],
            "hb_index_display": hypoxic_metrics["hb_index_display"],
            "hb_severity": hypoxic_metrics["hb_severity"],
            "oximetry_quality_status": hypoxic_metrics["quality_status"],
            "oximetry_quality_reason": hypoxic_metrics["quality_reason"],
            "valid_spo2_ratio": hypoxic_metrics["valid_ratio"],
            "valid_spo2_ratio_pct": valid_spo2_ratio_pct,
            "valid_spo2_ratio_display": f"{valid_spo2_ratio_pct:.0f}%",
            "valid_spo2_duration_sec": hypoxic_metrics["valid_duration_sec"],
            "valid_spo2_duration_display": _duration_text(hypoxic_metrics["valid_duration_sec"]),
            "desat_max_sec": desat_max_sec,
            "desat_max_sec_display": _duration_text(desat_max_sec),
            "longest_duration_sec": hypoxic_metrics["longest_duration_sec"],
            "longest_duration_display": hypoxic_metrics["longest_duration_display"],
            "lowest_spo2": minimum_value,
            "lowest_spo2_display": _number_text(minimum_value),
            "duration_of_min_spo2_sec": min_duration,
            "duration_of_min_spo2_display": _duration_text(min_duration),
            "highest_spo2": maximum_value,
            "highest_spo2_display": _number_text(maximum_value),
            "duration_of_max_spo2_sec": max_duration,
            "duration_of_max_spo2_display": _duration_text(max_duration),
            "total_count_event": hypoxic_metrics["total_count_event"],
            "total_count_event_display": hypoxic_metrics["total_count_event_display"],
            "duration_below_90_sec": duration_below_90_sec,
            "duration_below_90_display": _duration_text(duration_below_90_sec),
            "duration_below_90_pct": duration_below_90_pct,
            "duration_below_90_pct_display": f"{duration_below_90_pct:.1f}%",
            "duration_below_85_sec": duration_below_85_sec,
            "duration_below_85_display": _duration_text(duration_below_85_sec),
            "duration_below_85_pct": duration_below_85_pct,
            "duration_below_85_pct_display": f"{duration_below_85_pct:.1f}%",
            "duration_below_80_sec": duration_below_80_sec,
            "duration_below_80_display": _duration_text(duration_below_80_sec),
            "duration_below_80_pct": duration_below_80_pct,
            "duration_below_80_pct_display": f"{duration_below_80_pct:.1f}%",
            "baseline_spo2": baseline,
            "baseline_spo2_display": f"{baseline:.1f}",
            "spo2_variability": _variability_label(float(np.std(valid_spo2))),
            "oxygen_saturation_trend": _trend_label(
                time_array[: aligned_spo2.size][np.isfinite(aligned_spo2)],
                aligned_spo2[np.isfinite(aligned_spo2)],
            ),
        }
    else:
        oximetry = {
            "mean_spo2": None,
            "mean_spo2_display": "-",
            "min_spo2": None,
            "min_spo2_display": "-",
            "max_spo2": None,
            "max_spo2_display": "-",
            "total_desats": 0,
            "total_desats_display": "0",
            "desaturation_index": 0.0,
            "desaturation_index_display": "0.0",
            "odi3": odi_metrics["odi"],
            "odi3_display": odi_metrics["odi_display"],
            "odi3_event_count": odi_metrics["odi_event_count"],
            "odi3_event_count_display": odi_metrics["odi_event_count_display"],
            "odi3_severity": odi_metrics["odi_severity"],
            "desat_max_pct": 0.0,
            "desat_max_pct_display": "0.0",
            "hypoxic_burden": 0.0,
            "hypoxic_burden_display": "0.00 %-min",
            "hb_index": 0.0,
            "hb_index_display": "0.0 %min/h",
            "hb_severity": "Normal",
            "oximetry_quality_status": hypoxic_metrics["quality_status"],
            "oximetry_quality_reason": hypoxic_metrics["quality_reason"],
            "valid_spo2_ratio": hypoxic_metrics["valid_ratio"],
            "valid_spo2_ratio_pct": float(hypoxic_metrics["valid_ratio"] * 100.0),
            "valid_spo2_ratio_display": f"{hypoxic_metrics['valid_ratio'] * 100.0:.0f}%",
            "valid_spo2_duration_sec": hypoxic_metrics["valid_duration_sec"],
            "valid_spo2_duration_display": _duration_text(hypoxic_metrics["valid_duration_sec"]),
            "desat_max_sec": 0.0,
            "desat_max_sec_display": "0.0 sec",
            "longest_duration_sec": 0.0,
            "longest_duration_display": "0.0 sec",
            "lowest_spo2": None,
            "lowest_spo2_display": "-",
            "duration_of_min_spo2_sec": 0.0,
            "duration_of_min_spo2_display": "0.0 sec",
            "highest_spo2": None,
            "highest_spo2_display": "-",
            "duration_of_max_spo2_sec": 0.0,
            "duration_of_max_spo2_display": "0.0 sec",
            "total_count_event": 0,
            "total_count_event_display": "0",
            "duration_below_90_sec": 0.0,
            "duration_below_90_display": "0.0 sec",
            "duration_below_90_pct": 0.0,
            "duration_below_90_pct_display": "0.0%",
            "duration_below_85_sec": 0.0,
            "duration_below_85_display": "0.0 sec",
            "duration_below_85_pct": 0.0,
            "duration_below_85_pct_display": "0.0%",
            "duration_below_80_sec": 0.0,
            "duration_below_80_display": "0.0 sec",
            "duration_below_80_pct": 0.0,
            "duration_below_80_pct_display": "0.0%",
            "baseline_spo2": None,
            "baseline_spo2_display": "-",
            "spo2_variability": "-",
            "oxygen_saturation_trend": "-",
        }

    heart_rate: Dict[str, Any] = {}
    if pulse.size:
        tib_valid_mask = np.isfinite(pulse) & (pulse > 0)
        tib_hr = pulse[tib_valid_mask]
        sleep_hr = np.array([], dtype=float)
        if tib_hr.size:
            sleep_mask_array = _aligned_sleep_mask(sleep_mask, pulse.size)
            sleep_valid_mask = tib_valid_mask & sleep_mask_array
            sleep_hr = pulse[sleep_valid_mask]
            if sleep_hr.size == 0:
                sleep_hr = tib_hr

        if tib_hr.size:
            highest_hr_tib = float(np.max(tib_hr))
            lowest_hr_tib = float(np.min(tib_hr))
            highest_hr_sleep = float(np.max(sleep_hr)) if sleep_hr.size else None
            lowest_hr_sleep = float(np.min(sleep_hr)) if sleep_hr.size else None
            rhythm_label = _heart_rate_rhythm_label(highest_hr_tib, lowest_hr_tib)
            heart_rate = {
                "mean_hr_during_sleep": float(np.mean(sleep_hr)) if sleep_hr.size else None,
                "mean_hr_during_sleep_display": f"{float(np.mean(sleep_hr)):.1f} BPM" if sleep_hr.size else "-",
                "highest_hr_during_sleep": float(np.max(sleep_hr)) if sleep_hr.size else None,
                "highest_hr_during_sleep_display": f"{_number_text(float(np.max(sleep_hr)))} BPM" if sleep_hr.size else "-",
                "highest_hr_during_tib": float(np.max(tib_hr)),
                "highest_hr_during_tib_display": f"{_number_text(float(np.max(tib_hr)))} BPM",
                "lowest_hr_during_sleep": float(np.min(sleep_hr)) if sleep_hr.size else None,
                "lowest_hr_during_sleep_display": f"{_number_text(float(np.min(sleep_hr)))} BPM" if sleep_hr.size else "-",
                "lowest_hr_during_tib": float(np.min(tib_hr)),
                "lowest_hr_during_tib_display": f"{_number_text(float(np.min(tib_hr)))} BPM",
                "mean_hr": float(np.mean(sleep_hr)) if sleep_hr.size else float(np.mean(tib_hr)),
                "mean_hr_display": f"{float(np.mean(sleep_hr)):.1f} BPM" if sleep_hr.size else f"{float(np.mean(tib_hr)):.1f} BPM",
                "highest_hr": float(np.max(tib_hr)),
                "highest_hr_display": f"{_number_text(float(np.max(tib_hr)))} BPM",
                "lowest_hr": float(np.min(tib_hr)),
                "lowest_hr_display": f"{_number_text(float(np.min(tib_hr)))} BPM",
            }
        else:
            heart_rate = {
                "mean_hr_during_sleep": None,
                "mean_hr_during_sleep_display": "-",
                "highest_hr_during_sleep": None,
                "highest_hr_during_sleep_display": "-",
                "highest_hr_during_tib": None,
                "highest_hr_during_tib_display": "-",
                "lowest_hr_during_sleep": None,
                "lowest_hr_during_sleep_display": "-",
                "lowest_hr_during_tib": None,
                "lowest_hr_during_tib_display": "-",
                "mean_hr": None,
                "mean_hr_display": "-",
                "highest_hr": None,
                "highest_hr_display": "-",
                "lowest_hr": None,
                "lowest_hr_display": "-",
            }
    else:
        heart_rate = {
            "mean_hr_during_sleep": None,
            "mean_hr_during_sleep_display": "-",
            "highest_hr_during_sleep": None,
            "highest_hr_during_sleep_display": "-",
            "highest_hr_during_tib": None,
            "highest_hr_during_tib_display": "-",
            "lowest_hr_during_sleep": None,
            "lowest_hr_during_sleep_display": "-",
            "lowest_hr_during_tib": None,
            "lowest_hr_during_tib_display": "-",
            "mean_hr": None,
            "mean_hr_display": "-",
            "highest_hr": None,
            "highest_hr_display": "-",
            "lowest_hr": None,
            "lowest_hr_display": "-",
        }

    sleep_flags = None
    if sleep_mask is not None and pulse.size:
        flags = _aligned_sleep_mask(sleep_mask, pulse.size)
        if bool(np.any(flags)):
            sleep_flags = flags
    snoring_summary: Dict[str, Any] = _build_snoring_summary(
        snoring,
        signals,
        step_seconds=snoring_step_seconds,
        threshold=snoring_threshold,
        min_duration_sec=snoring_min_duration_sec,
        max_duration_sec=snoring_max_duration_sec,
        recording_sec=sleep_duration_sec,
        sleep_flags=sleep_flags,
        flag_step_seconds=_channel_step("pulse"),
    )
    if snoring.size:
        snoring_summary.update(_snoring_phase_counts(signals))

    return {
        "metadata": {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "sample_rate_hz": float(actual_sample_rate_hz),
            "sleep_duration_sec": sleep_duration_sec,
            "sleep_duration_display": _duration_text(sleep_duration_sec),
            "sample_count": int(max(len(time_array), len(spo2), len(pulse), len(snoring))),
            "time_step_sec": step_seconds,
        },
        "oximetry": oximetry,
        "heart_rate": heart_rate,
        "snoring": snoring_summary,
    }


def calculate_report_context(
    analysis_results: Optional[Dict[str, Any]],
    psg_data: Optional[Dict[str, Any]] = None,
    detected_events: Optional[list[Dict[str, Any]]] = None,
    sensor_off_segments: Optional[list[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build dynamic report sections from loaded PSG signals and detector output."""
    analysis_results = analysis_results or {}
    metadata = analysis_results.get("metadata", {}) or {}
    psg_data = psg_data or {}
    detected_events = detected_events or []

    if isinstance(psg_data.get("signals"), dict):
        signals = psg_data.get("signals", {}) or {}
        time_axis = _as_float_array(psg_data.get("time"))
    else:
        signals = psg_data
        time_axis = _as_float_array(psg_data.get("time")) if isinstance(psg_data, dict) else np.array([], dtype=float)

    sleep_duration_sec = float(metadata.get("sleep_duration_sec") or 0.0)
    sleep_hours = sleep_duration_sec / 3600.0 if sleep_duration_sec > 0 else 0.0
    sample_rate_hz = float(metadata.get("sample_rate_hz") or DEFAULT_SAMPLE_RATE_HZ)
    sample_count = int(metadata.get("sample_count") or 0)
    if sample_count <= 0 and signals:
        sample_count = max((len(np.asarray(values).reshape(-1)) for values in signals.values() if values is not None), default=0)
    if sleep_duration_sec <= 0 and sample_count > 0 and sample_rate_hz > 0:
        sleep_duration_sec = float(sample_count / sample_rate_hz)
        sleep_hours = sleep_duration_sec / 3600.0 if sleep_duration_sec > 0 else 0.0

    timestamp_raw = np.asarray(signals.get("timestamp_raw", []), dtype=float).reshape(-1)
    lights_off = _clock_time_text(timestamp_raw[0]) if timestamp_raw.size else "-"
    lights_on = _clock_time_text(timestamp_raw[-1]) if timestamp_raw.size else "-"
    duration_display = _duration_text(sleep_duration_sec)

    body_position = np.asarray(signals.get("body_position", []), dtype=float).reshape(-1)
    position_names = ("Supine", "Prone", "Left", "Right", "Up")
    position_counts = {name: 0 for name in position_names}
    position_durations_sec = {name: 0.0 for name in position_names}

    body_position_rate_hz = (
        float(body_position.size) / sleep_duration_sec
        if body_position.size and sleep_duration_sec > 0 else sample_rate_hz
    )
    if body_position.size and body_position_rate_hz > 0:
        sample_sec = 1.0 / body_position_rate_hz
        for position_name in position_names:
            if position_name == "Supine":
                mask = np.isclose(body_position, 0)
            elif position_name == "Right":
                mask = np.isclose(body_position, 2)
            elif position_name == "Left":
                mask = np.isclose(body_position, 1)
            elif position_name == "Prone":
                mask = np.isclose(body_position, 3)
            else:
                mask = np.isclose(body_position, 4)
            position_durations_sec[position_name] = float(np.sum(mask)) * sample_sec

    total_position_time_sec = float(sum(position_durations_sec.values()))

    grouped_events = {
        "Central Apneas": [],
        "Obstructive Apneas": [],
        "Mixed Apneas": [],
        "Hypopneas": [],
    }
    event_label_map = {
        "CSA": "Central Apneas",
        "OSA": "Obstructive Apneas",
        "HSA": "Hypopneas",
        "HYPOPNEA": "Hypopneas",
        "MSA": "Mixed Apneas",
        "APNEA": "Obstructive Apneas",
    }
    # Union (not sum) of explicit SENSOR_OFF events and detector segments.
    off_intervals: list[tuple[float, float]] = []
    for event in detected_events:
        raw_label = str(event.get("final_label") or event.get("rule_label") or "").upper().replace(" ", "_")
        if raw_label == "SENSOR_OFF":
            off_intervals.append((float(event.get("start_sec", 0.0)), float(event.get("end_sec", 0.0))))
    for segment in (sensor_off_segments or []):
        try:
            off_intervals.append((float(segment["start_sec"]), float(segment["end_sec"])))
        except (KeyError, TypeError, ValueError):
            continue
    sensor_off_sec = 0.0
    last_end = None
    for seg_start, seg_end in sorted(i for i in off_intervals if i[1] > i[0]):
        seg_start = max(seg_start, last_end) if last_end is not None else seg_start
        if seg_end > seg_start:
            sensor_off_sec += seg_end - seg_start
            last_end = seg_end
    valid_analysis_sec = max(0.0, float(sleep_duration_sec) - sensor_off_sec)
    index_hours = (valid_analysis_sec / 3600.0) if (INDEX_ON_VALID_TIME and valid_analysis_sec > 0) else sleep_hours
    position_valid_durations_sec = dict(position_durations_sec)
    if body_position.size and body_position_rate_hz > 0 and off_intervals:
        _codes = {"Supine": 0, "Left": 1, "Right": 2, "Prone": 3, "Up": 4}
        _off = np.zeros(body_position.size, dtype=bool)
        for _a, _b in off_intervals:
            _off[max(0, int(_a * body_position_rate_hz)):min(body_position.size, int(_b * body_position_rate_hz) + 1)] = True
        for _name, _code in _codes.items():
            position_valid_durations_sec[_name] = float(np.sum(np.isclose(body_position, _code) & ~_off)) / body_position_rate_hz
    valid_pct = (valid_analysis_sec / float(sleep_duration_sec) * 100.0) if sleep_duration_sec > 0 else 0.0

    for event in detected_events:
        label = str(event.get("final_label") or event.get("rule_label") or "").upper()
        target_group = event_label_map.get(label)
        if not target_group:
            continue
        grouped_events[target_group].append(event)
        if body_position.size and body_position_rate_hz > 0:
            midpoint_sec = (float(event.get("start_sec", 0.0)) + float(event.get("end_sec", 0.0))) / 2.0
            midpoint_index = int(np.clip(round(midpoint_sec * body_position_rate_hz), 0, len(body_position) - 1))
            position_name = _body_position_name(body_position[midpoint_index])
            if position_name:
                position_counts[position_name] += 1

    respiratory_rows = []
    total_events = 0
    total_duration = 0.0
    total_max_duration = 0.0

    for row_name in ("Central Apneas", "Obstructive Apneas", "Mixed Apneas", "Hypopneas"):
        events = grouped_events[row_name]
        event_count = len(events)
        durations = [float(event.get("duration_sec", 0.0) or 0.0) for event in events]
        mean_duration = float(np.mean(durations)) if durations else 0.0
        max_duration = float(np.max(durations)) if durations else 0.0
        index_per_hour = _label_index_per_hour(event_count, index_hours)

        row_position_counts = {name: 0 for name in position_names}
        if events and body_position.size and body_position_rate_hz > 0:
            for event in events:
                midpoint_sec = (float(event.get("start_sec", 0.0)) + float(event.get("end_sec", 0.0))) / 2.0
                midpoint_index = int(np.clip(round(midpoint_sec * body_position_rate_hz), 0, len(body_position) - 1))
                position_name = _body_position_name(body_position[midpoint_index])
                if position_name:
                    row_position_counts[position_name] += 1

        respiratory_rows.append({
            "name": row_name,
            "index_display": f"{index_per_hour:.1f}",
            "count_display": str(event_count),
            "mean_duration_display": f"{mean_duration:.2f}",
            "max_duration_display": f"{max_duration:.2f}",
            "positions": row_position_counts,
        })
        total_events += event_count
        total_duration += float(sum(durations))
        total_max_duration = max(total_max_duration, max_duration)

    # Derived indices shown in the respiratory-events table. HI is the
    # hypopnea-only index; AI is the combined apnea-only index (OA + CA + MA).
    row_by_name = {row["name"]: row for row in respiratory_rows}
    hypopnea_row = row_by_name["Hypopneas"]
    hypopnea_index = _label_index_per_hour(len(grouped_events["Hypopneas"]), index_hours)
    displayed_hypopnea_index = float(f"{hypopnea_index:.1f}")
    respiratory_rows.append({
        "name": "Hypopnea Index (HI)",
        "index_display": f"{displayed_hypopnea_index:.1f}",
        "count_display": hypopnea_row["count_display"],
        "mean_duration_display": hypopnea_row["mean_duration_display"],
        "max_duration_display": hypopnea_row["max_duration_display"],
        "positions": dict(hypopnea_row["positions"]),
    })

    apnea_rows = [row_by_name[name] for name in ("Obstructive Apneas", "Central Apneas", "Mixed Apneas")]
    apnea_count = sum(int(row["count_display"]) for row in apnea_rows)
    apnea_index = _label_index_per_hour(apnea_count, index_hours)
    displayed_apnea_index = float(f"{apnea_index:.1f}")
    displayed_ahi_index = displayed_apnea_index + displayed_hypopnea_index
    apnea_durations = []
    for name in ("Obstructive Apneas", "Central Apneas", "Mixed Apneas"):
        apnea_durations.extend(
            float(event.get("duration_sec", 0.0) or 0.0)
            for event in grouped_events[name]
        )
    apnea_positions = {
        position: sum(int(row["positions"].get(position, 0)) for row in apnea_rows)
        for position in position_names
    }
    respiratory_rows.append({
        "name": "Apnea Index (AI)",
        "index_display": f"{displayed_apnea_index:.1f}",
        "count_display": str(apnea_count),
        "mean_duration_display": f"{(float(np.mean(apnea_durations)) if apnea_durations else 0.0):.2f}",
        "max_duration_display": f"{(float(np.max(apnea_durations)) if apnea_durations else 0.0):.2f}",
        "positions": apnea_positions,
    })

    total_index = _label_index_per_hour(total_events, index_hours)
    # Match the mobile report: AHI mean duration is the average of the
    # non-empty event-type means (OSA/CSA/MSA/HYP), not event-count-weighted.
    category_means = [
        float(row["mean_duration_display"])
        for row in respiratory_rows[:4]
        if int(row["count_display"]) > 0
    ]
    total_mean_duration = float(np.mean(category_means)) if category_means else 0.0
    rei_in_position = {
        name: f"{_label_index_per_hour(position_counts[name], position_valid_durations_sec[name] / 3600.0):.1f}"
        if position_valid_durations_sec[name] > 0 else "0.0"
        for name in position_names
    }
    time_in_position = {
        name: {
            "duration_sec": float(position_durations_sec[name]),
            "duration_display": _duration_text(position_durations_sec[name]),
            "minutes_display": f"{position_durations_sec[name] / 60.0:.1f}",
            "percentage": ((position_durations_sec[name] / total_position_time_sec) * 100.0) if total_position_time_sec > 0 else 0.0,
            "percentage_display": (
                f"{((position_durations_sec[name] / total_position_time_sec) * 100.0):.1f}%"
                if total_position_time_sec > 0 else "0.0%"
            ),
            "rei_display": rei_in_position[name],
            "event_count": int(position_counts[name]),
        }
        for name in position_names
    }

    group_counts = {
        row["name"]: int(row.get("count_display", 0) or 0)
        for row in respiratory_rows
    }
    dominant_group = max(group_counts, key=group_counts.get) if group_counts else "Obstructive Apneas"
    if total_index < 5.0:
        diagnosis = "No significant sleep-disordered breathing detected in the loaded recording."
    elif group_counts.get("Obstructive Apneas", 0) >= max(
        group_counts.get("Central Apneas", 0),
        group_counts.get("Mixed Apneas", 0),
        group_counts.get("Hypopneas", 0),
    ):
        diagnosis = f"{_severity_from_ahi(total_index)} obstructive sleep apnea pattern detected."
    elif group_counts.get("Central Apneas", 0) >= max(
        group_counts.get("Mixed Apneas", 0),
        group_counts.get("Hypopneas", 0),
    ):
        diagnosis = f"{_severity_from_ahi(total_index)} central sleep apnea pattern detected."
    elif group_counts.get("Mixed Apneas", 0) >= group_counts.get("Hypopneas", 0):
        diagnosis = f"{_severity_from_ahi(total_index)} mixed sleep apnea pattern detected."
    else:
        diagnosis = f"{_severity_from_ahi(total_index)} hypopnea-dominant sleep-disordered breathing detected."

    oximetry = dict(analysis_results.get("oximetry", {}) or {})
    # Reports use the event-linked published HB definition. Keep the other
    # oximetry metrics unchanged; only HB total/index are replaced here.
    # Preserve timeline/NaN positions here: event end_sec is an absolute
    # sample position, so compacting invalid samples would misalign HB.
    report_spo2 = np.asarray(
        signals.get("spo2", signals.get("SpO2", [])) if isinstance(signals, dict) else [],
        dtype=float,
    ).reshape(-1)
    if report_spo2.size and detected_events and sleep_hours > 0:
        report_spo2 = _bridge_zero_gaps(report_spo2, 1.0)
        hb_valid = np.ones(report_spo2.size, dtype=bool)
        for off_start, off_end in off_intervals:
            hb_valid[max(0, int(off_start)):max(0, int(off_end))] = False
        published_hb = _published_hypoxic_burden(
            report_spo2, detected_events, index_hours, valid_mask=hb_valid)
        oximetry["hypoxic_burden"] = published_hb["hypoxic_burden"]
        oximetry["hypoxic_burden_display"] = f"{published_hb['hypoxic_burden']:.2f} %-min"
        oximetry["hb_index"] = published_hb["hb_index"]
        oximetry["hb_index_display"] = f"{published_hb['hb_index']:.1f} %min/h"
        oximetry["hb_severity"] = _severity_from_hb_index(published_hb["hb_index"])
        oximetry["hb_method"] = "Azarbarzin-style event-linked HB (overlap-corrected)"
        oximetry["hb_search_window_sec"] = published_hb.get("window")
        oximetry["hb_window_status"] = published_hb.get("window_status", "no usable events")
        oximetry["hb_event_count"] = published_hb.get("event_count", 0)
        oximetry["hb_total_sum_mode"] = published_hb.get("hb_total_sum_mode", 0.0)
    snoring = analysis_results.get("snoring", {}) or {}
    findings: list[str] = [
        f"Respiratory event index is {total_index:.1f} events/hour ({_severity_from_ahi(total_index)} severity)."
    ]
    if total_events > 0:
        findings.append(
            f"{total_events} respiratory events were detected; dominant class: {dominant_group}."
        )
    if oximetry.get("lowest_spo2") is not None:
        findings.append(
            f"Lowest SpO2 was {oximetry.get('lowest_spo2_display', '-') }% with hypoxic burden {oximetry.get('hypoxic_burden_display', '0.00 %-min')}."
        )
    if float(oximetry.get("odi3") or 0.0) > 0.0:
        findings.append(
            f"ODI3 was {oximetry.get('odi3_display', '0.0 /h')} ({oximetry.get('odi3_severity', 'Normal')})."
        )
    if oximetry.get("duration_below_90_sec", 0.0) > 0:
        findings.append(
            f"Time below 90% SpO2: {oximetry.get('duration_below_90_display', '0.0 sec')} ({oximetry.get('duration_below_90_pct_display', '0.0%')})."
        )
    if snoring.get("total_snoring_events", snoring.get("total_snoring_episodes", 0)) > 0:
        _basis = "sleep time" if snoring.get("snoring_basis") == "sleep" else "recording"
        findings.append(
            f"Snoring (airflow-derived) occupied {snoring.get('snoring_percentage_display', '0.0 %')} of the {_basis} "
            f"across {snoring.get('total_snoring_episodes_display', '0')} episodes."
        )

    dominant_position = max(time_in_position, key=lambda name: time_in_position[name]["duration_sec"]) if time_in_position else None
    recommendations: list[str] = []
    if total_index >= 30.0:
        recommendations.append("Prompt specialist review is recommended because the event burden is in the severe range.")
    elif total_index >= 15.0:
        recommendations.append("Sleep specialist follow-up is recommended because the event burden is in the moderate range.")
    elif total_index >= 5.0:
        recommendations.append("Clinical correlation and follow-up are recommended because a mild event burden is present.")
    else:
        recommendations.append("No high event burden is visible in the loaded recording; correlate with symptoms before deciding next steps.")
    if oximetry.get("lowest_spo2") is not None and float(oximetry.get("lowest_spo2") or 0.0) < 88.0:
        recommendations.append("Oxygen desaturation is significant; review this recording alongside clinical oxygenation history.")
    if dominant_position and time_in_position[dominant_position]["event_count"] > 0:
        recommendations.append(
            f"Most events occurred while the patient was {dominant_position.lower()}; positional review may be useful."
        )
    if snoring.get("snoring_percentage", 0.0) >= 20.0:
        recommendations.append("Snoring burden is elevated in this recording and should be reviewed with airway symptoms.")

    urgency = "High" if total_index >= 30.0 or float(oximetry.get("lowest_spo2") or 100.0) < 80.0 else (
        "Moderate" if total_index >= 15.0 or float(oximetry.get("lowest_spo2") or 100.0) < 88.0 else "Routine"
    )

    summary = {
        "ahi_rei_display": f"{displayed_ahi_index:.1f}",
        "ahi_valid_time_display": f"{displayed_ahi_index:.1f}",
        "oai_display": next((row["index_display"] for row in respiratory_rows if row["name"] == "Obstructive Apneas"), "0.0"),
        "cai_display": next((row["index_display"] for row in respiratory_rows if row["name"] == "Central Apneas"), "0.0"),
        "hypopnea_display": next((row["index_display"] for row in respiratory_rows if row["name"] == "Hypopneas"), "0.0"),
        # Keep the severity scale/KPI aligned with the respiratory table AHI:
        # table AHI is the sum of the displayed AI and HI values.
        "severity_label": _severity_from_ahi(displayed_ahi_index),
        "severity_value": displayed_ahi_index,
        "rows": respiratory_rows,
        "total_row": {
            "index_display": f"{displayed_ahi_index:.1f}",
            "count_display": str(total_events),
            "mean_duration_display": f"{total_mean_duration:.1f}",
            "max_duration_display": f"{total_max_duration:.2f}",
            "positions": dict(position_counts),
        },
        "rei_in_position": rei_in_position,
        "time_in_position": time_in_position,
    }

    return {
        "oximetry": oximetry,
        "time_information": {
            "lights_off": lights_off,
            "lights_on": lights_on,
            "trt_display": duration_display,
            "sensor_off_display": _duration_text(sensor_off_sec) if sensor_off_sec > 0 else "0 min",
            "valid_time_display": f"{_duration_text(valid_analysis_sec)} ({valid_pct:.0f}%)",
            "tib_display": duration_display,
            "sample_rate_display": f"{sample_rate_hz:.1f} Hz",
            "sample_count_display": str(sample_count),
            "recording_start_sec": float(time_axis[0]) if time_axis.size else 0.0,
            "recording_end_sec": float(time_axis[-1]) if time_axis.size else sleep_duration_sec,
        },
        "respiratory_summary": summary,
        "report_interpretation": {
            "diagnosis": diagnosis,
            "severity": _severity_from_ahi(displayed_ahi_index),
            "urgency": urgency,
            "findings": findings,
            "recommendations": recommendations,
        },
    }


def save_sleep_metrics_json(
    metrics: Dict[str, Any],
    source_recording: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> str:
    """Save the calculated metrics into a timestamped JSON file."""
    base_dir = Path(output_dir) if output_dir else DEFAULT_ANALYSIS_JSON_DIR
    base_dir.mkdir(parents=True, exist_ok=True)

    source_stem = Path(source_recording).stem if source_recording else "sleep_metrics"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = base_dir / f"{source_stem}_analysis_{timestamp}.json"

    payload = dict(metrics)
    payload["source_recording"] = source_recording
    payload["json_path"] = str(output_path)

    with open(output_path, "w", encoding="utf-8") as file_handle:
        json.dump(payload, file_handle, indent=2, ensure_ascii=False)

    return str(output_path)
