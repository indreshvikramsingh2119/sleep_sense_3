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
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import numpy as np
from .runtime_config import get_configured_path

DEFAULT_SAMPLE_RATE_HZ = 10.0
DEFAULT_SNORING_THRESHOLD = 5.0
DEFAULT_ANALYSIS_JSON_DIR = get_configured_path("analysis_json_dir")
HYPOXIC_BURDEN_BASELINE_SPO2 = 95.0
DESATURATION_EVENT_DROP_PCT = 3.0
DESATURATION_EVENT_THRESHOLD_SPO2 = HYPOXIC_BURDEN_BASELINE_SPO2 - DESATURATION_EVENT_DROP_PCT
MIN_VALID_SPO2_PCT = 70.0
MAX_VALID_SPO2_PCT = 100.0
MIN_VALID_SPO2_DURATION_SEC = 10.0
MIN_VALID_SPO2_RATIO = 0.5


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


def _body_position_name(value: Any) -> str | None:
    try:
        numeric_value = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    mapping = {
        0: "Supine",
        1: "Right",
        2: "Left",
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
    raw_spo2 = _as_float_array(spo2_values)
    if raw_spo2.size == 0:
        return np.array([], dtype=float), _empty_hypoxic_metrics()

    artifact_mask = (raw_spo2 >= MIN_VALID_SPO2_PCT) & (raw_spo2 <= MAX_VALID_SPO2_PCT)
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


def calculate_hypoxic_burden_metrics(
    spo2_values: Any,
    step_seconds: float,
    baseline_spo2: float = HYPOXIC_BURDEN_BASELINE_SPO2,
    event_threshold_spo2: float = DESATURATION_EVENT_THRESHOLD_SPO2,
) -> Dict[str, float]:
    """Calculate real-time compatible hypoxic burden metrics from SpO2 samples."""
    valid_spo2, quality = _filter_valid_spo2_samples(spo2_values, step_seconds)
    if quality["quality_status"] != "valid":
        return quality

    sample_interval_min = max(float(step_seconds), 0.0) / 60.0
    below_baseline = valid_spo2 < float(baseline_spo2)
    hypoxic_burden = float(
        np.sum(np.maximum(float(baseline_spo2) - valid_spo2, 0.0) * below_baseline) * sample_interval_min
    )

    contiguous_below_baseline = _contiguous_segments(below_baseline)
    longest_duration_sec = float(
        max(
            (((end - start) * float(step_seconds)) for start, end in contiguous_below_baseline),
            default=0.0,
        )
    )

    event_mask = valid_spo2 <= float(event_threshold_spo2)
    event_segments = _contiguous_segments(event_mask)
    total_count_event = int(len(event_segments))

    sleep_duration_hours = float((valid_spo2.size * float(step_seconds)) / 3600.0) if step_seconds > 0 else 0.0
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


def _snoring_segments(snoring: np.ndarray, threshold: float = DEFAULT_SNORING_THRESHOLD) -> list[tuple[int, int]]:
    return _contiguous_segments(snoring > threshold)


def calculate_sleep_metrics(
    time_data: Any,
    signals: Dict[str, Any],
    sleep_mask: Any = None,
    sample_rate_hz: float = DEFAULT_SAMPLE_RATE_HZ,
    snoring_threshold: float = DEFAULT_SNORING_THRESHOLD,
) -> Dict[str, Any]:
    """Calculate summary metrics from loaded PSG signals."""
    time_array = _as_float_array(time_data)
    actual_sample_rate_hz = _sample_rate_hz(time_array, sample_rate_hz)
    step_seconds = 1.0 / actual_sample_rate_hz if actual_sample_rate_hz > 0 else _time_step_seconds(time_array, sample_rate_hz)

    spo2 = _first_signal(signals, ("spo2", "SpO2"))
    pulse = _first_signal(signals, ("pulse", "Pulse", "hr", "heart_rate"))
    snoring = _first_signal(signals, ("snoring", "Snoring"))

    sleep_duration_sec = float(len(time_array) * step_seconds) if time_array.size else float(max(len(spo2), len(pulse), len(snoring)) * step_seconds)
    sleep_hours = sleep_duration_sec / 3600.0 if sleep_duration_sec > 0 else 0.0

    oximetry: Dict[str, Any] = {}
    hypoxic_metrics = _empty_hypoxic_metrics(reason="No SpO2 signal available.")
    valid_spo2 = np.array([], dtype=float)
    if spo2.size:
        hypoxic_metrics = calculate_hypoxic_burden_metrics(spo2, step_seconds)
        valid_spo2, _quality = _filter_valid_spo2_samples(spo2, step_seconds)
        if hypoxic_metrics["quality_status"] != "valid":
            valid_spo2 = np.array([], dtype=float)

    if spo2.size and valid_spo2.size:
        baseline = _baseline_spo2(valid_spo2)
        below_90 = valid_spo2 < 90.0
        below_85 = valid_spo2 < 85.0
        below_80 = valid_spo2 < 80.0
        segments_below_90 = _contiguous_segments(below_90)
        desat_durations = [(end - start) * step_seconds for start, end in segments_below_90]

        minimum_value = float(np.min(valid_spo2))
        maximum_value = float(np.max(valid_spo2))
        min_duration = float(np.sum(np.isclose(valid_spo2, minimum_value))) * step_seconds
        max_duration = float(np.sum(np.isclose(valid_spo2, maximum_value))) * step_seconds
        desat_max_sec = float(max(desat_durations)) if desat_durations else 0.0
        duration_below_90_sec = float(np.sum(below_90)) * step_seconds
        duration_below_85_sec = float(np.sum(below_85)) * step_seconds
        duration_below_80_sec = float(np.sum(below_80)) * step_seconds

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
            "valid_spo2_ratio_display": f"{hypoxic_metrics['valid_ratio'] * 100.0:.0f}%",
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
            "duration_below_85_sec": duration_below_85_sec,
            "duration_below_85_display": _duration_text(duration_below_85_sec),
            "duration_below_80_sec": duration_below_80_sec,
            "duration_below_80_display": _duration_text(duration_below_80_sec),
            "baseline_spo2": baseline,
            "baseline_spo2_display": f"{baseline:.1f}",
            "spo2_variability": _variability_label(float(np.std(valid_spo2))),
            "oxygen_saturation_trend": _trend_label(time_array[: valid_spo2.size], valid_spo2),
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
            "duration_below_85_sec": 0.0,
            "duration_below_85_display": "0.0 sec",
            "duration_below_80_sec": 0.0,
            "duration_below_80_display": "0.0 sec",
            "baseline_spo2": None,
            "baseline_spo2_display": "-",
            "spo2_variability": "-",
            "oxygen_saturation_trend": "-",
        }

    heart_rate: Dict[str, Any] = {}
    if pulse.size:
        valid_hr = pulse[(np.isfinite(pulse)) & (pulse > 0)]
        heart_rate = {
            "mean_hr": float(np.mean(valid_hr)),
            "mean_hr_display": f"{float(np.mean(valid_hr)):.1f} BPM",
            "highest_hr": float(np.max(valid_hr)),
            "highest_hr_display": f"{_number_text(float(np.max(valid_hr)))} BPM",
            "lowest_hr": float(np.min(valid_hr)),
            "lowest_hr_display": f"{_number_text(float(np.min(valid_hr)))} BPM",
        }
    else:
        heart_rate = {
            "mean_hr": None,
            "mean_hr_display": "-",
            "highest_hr": None,
            "highest_hr_display": "-",
            "lowest_hr": None,
            "lowest_hr_display": "-",
        }

    snoring_summary: Dict[str, Any] = {}
    if snoring.size:
        valid_snoring = snoring[np.isfinite(snoring)]
        segments = _snoring_segments(valid_snoring, threshold=snoring_threshold)
        total_snore_duration_sec = float(sum((end - start) for start, end in segments)) * step_seconds
        episode_count = int(len(segments))
        mean_snore_duration_sec = total_snore_duration_sec / episode_count if episode_count else 0.0
        snoring_percentage = (total_snore_duration_sec / sleep_duration_sec) * 100.0 if sleep_duration_sec > 0 else 0.0
        snoring_summary = {
            "snoring_threshold": snoring_threshold,
            "total_snoring_episodes": episode_count,
            "total_snoring_episodes_display": str(episode_count),
            "total_snoring_duration_sec": total_snore_duration_sec,
            "total_snoring_duration_display": _duration_text(total_snore_duration_sec),
            "mean_snoring_duration_sec": mean_snore_duration_sec,
            "mean_snoring_duration_display": _duration_text(mean_snore_duration_sec),
            "snoring_percentage": snoring_percentage,
            "snoring_percentage_display": f"{snoring_percentage:.1f} %",
            "snoring_signal_min": float(np.min(valid_snoring)),
            "snoring_signal_max": float(np.max(valid_snoring)),
            "snoring_signal_mean": float(np.mean(valid_snoring)),
        }
    else:
        snoring_summary = {
            "snoring_threshold": snoring_threshold,
            "total_snoring_episodes": 0,
            "total_snoring_episodes_display": "0",
            "total_snoring_duration_sec": 0.0,
            "total_snoring_duration_display": "0.0 sec",
            "mean_snoring_duration_sec": 0.0,
            "mean_snoring_duration_display": "0.0 sec",
            "snoring_percentage": 0.0,
            "snoring_percentage_display": "0.0 %",
            "snoring_signal_min": None,
            "snoring_signal_max": None,
            "snoring_signal_mean": None,
        }

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
) -> Dict[str, Any]:
    """Build dynamic report sections from loaded PSG signals and detector output."""
    analysis_results = analysis_results or {}
    metadata = analysis_results.get("metadata", {}) or {}
    psg_data = psg_data or {}
    detected_events = detected_events or []

    sleep_duration_sec = float(metadata.get("sleep_duration_sec") or 0.0)
    sleep_hours = sleep_duration_sec / 3600.0 if sleep_duration_sec > 0 else 0.0
    sample_rate_hz = float(metadata.get("sample_rate_hz") or DEFAULT_SAMPLE_RATE_HZ)
    sample_count = int(metadata.get("sample_count") or 0)
    if sample_count <= 0 and psg_data:
        sample_count = max(len(np.asarray(values).reshape(-1)) for values in psg_data.values() if values is not None)
    if sleep_duration_sec <= 0 and sample_count > 0 and sample_rate_hz > 0:
        sleep_duration_sec = float(sample_count / sample_rate_hz)
        sleep_hours = sleep_duration_sec / 3600.0 if sleep_duration_sec > 0 else 0.0

    timestamp_raw = np.asarray(psg_data.get("timestamp_raw", []), dtype=float).reshape(-1)
    lights_off = _clock_time_text(timestamp_raw[0]) if timestamp_raw.size else "-"
    lights_on = _clock_time_text(timestamp_raw[-1]) if timestamp_raw.size else "-"
    duration_display = _duration_text(sleep_duration_sec)

    body_position = np.asarray(psg_data.get("body_position", []), dtype=float).reshape(-1)
    position_names = ("Supine", "Prone", "Left", "Right", "Up")
    position_counts = {name: 0 for name in position_names}
    position_durations_sec = {name: 0.0 for name in position_names}

    if body_position.size and sample_rate_hz > 0:
        sample_sec = 1.0 / sample_rate_hz
        for position_name in position_names:
            if position_name == "Supine":
                mask = np.isclose(body_position, 0)
            elif position_name == "Right":
                mask = np.isclose(body_position, 1)
            elif position_name == "Left":
                mask = np.isclose(body_position, 2)
            elif position_name == "Prone":
                mask = np.isclose(body_position, 3)
            else:
                mask = np.isclose(body_position, 4)
            position_durations_sec[position_name] = float(np.sum(mask)) * sample_sec

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
    for event in detected_events:
        label = str(event.get("final_label") or event.get("rule_label") or "").upper()
        target_group = event_label_map.get(label)
        if not target_group:
            continue
        grouped_events[target_group].append(event)
        if body_position.size and sample_rate_hz > 0:
            midpoint_sec = (float(event.get("start_sec", 0.0)) + float(event.get("end_sec", 0.0))) / 2.0
            midpoint_index = int(np.clip(round(midpoint_sec * sample_rate_hz), 0, len(body_position) - 1))
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
        index_per_hour = _label_index_per_hour(event_count, sleep_hours)

        row_position_counts = {name: 0 for name in position_names}
        if events and body_position.size and sample_rate_hz > 0:
            for event in events:
                midpoint_sec = (float(event.get("start_sec", 0.0)) + float(event.get("end_sec", 0.0))) / 2.0
                midpoint_index = int(np.clip(round(midpoint_sec * sample_rate_hz), 0, len(body_position) - 1))
                position_name = _body_position_name(body_position[midpoint_index])
                if position_name:
                    row_position_counts[position_name] += 1

        respiratory_rows.append({
            "name": row_name,
            "index_display": f"{index_per_hour:.1f}",
            "count_display": str(event_count),
            "mean_duration_display": f"{mean_duration:.1f}",
            "max_duration_display": f"{max_duration:.1f}",
            "positions": row_position_counts,
        })
        total_events += event_count
        total_duration += float(sum(durations))
        total_max_duration = max(total_max_duration, max_duration)

    total_index = _label_index_per_hour(total_events, sleep_hours)
    total_mean_duration = (total_duration / total_events) if total_events else 0.0
    rei_in_position = {
        name: f"{_label_index_per_hour(position_counts[name], position_durations_sec[name] / 3600.0):.1f}"
        if position_durations_sec[name] > 0 else "0.0"
        for name in position_names
    }

    summary = {
        "ahi_rei_display": f"{total_index:.1f}",
        "oai_display": next((row["index_display"] for row in respiratory_rows if row["name"] == "Obstructive Apneas"), "0.0"),
        "cai_display": next((row["index_display"] for row in respiratory_rows if row["name"] == "Central Apneas"), "0.0"),
        "hypopnea_display": next((row["index_display"] for row in respiratory_rows if row["name"] == "Hypopneas"), "0.0"),
        "severity_label": _severity_from_ahi(total_index),
        "severity_value": total_index,
        "rows": respiratory_rows,
        "total_row": {
            "index_display": f"{total_index:.1f}",
            "count_display": str(total_events),
            "mean_duration_display": f"{total_mean_duration:.1f}",
            "max_duration_display": f"{total_max_duration:.1f}",
            "positions": dict(position_counts),
        },
        "rei_in_position": rei_in_position,
    }

    return {
        "time_information": {
            "lights_off": lights_off,
            "lights_on": lights_on,
            "trt_display": duration_display,
            "tib_display": duration_display,
        },
        "respiratory_summary": summary,
    }


def save_sleep_metrics_json(
    metrics: Dict[str, Any],
    source_csv: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> str:
    """Save the calculated metrics into a timestamped JSON file."""
    base_dir = Path(output_dir) if output_dir else DEFAULT_ANALYSIS_JSON_DIR
    base_dir.mkdir(parents=True, exist_ok=True)

    source_stem = Path(source_csv).stem if source_csv else "sleep_metrics"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = base_dir / f"{source_stem}_analysis_{timestamp}.json"

    payload = dict(metrics)
    payload["source_csv"] = source_csv
    payload["json_path"] = str(output_path)

    with open(output_path, "w", encoding="utf-8") as file_handle:
        json.dump(payload, file_handle, indent=2, ensure_ascii=False)

    return str(output_path)
