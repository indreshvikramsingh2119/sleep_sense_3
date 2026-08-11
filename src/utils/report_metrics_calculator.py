"""
Sleep study metrics calculator.

This module centralizes the formulas used for oximetry, heart rate,
and snoring summaries so uploaded PSG data can be converted into a
single JSON payload immediately after load.

Formula notes:
- Mean SpO2 = sum(SpO2 readings) / count(SpO2 readings)
- Min/Max SpO2 = min/max of SpO2 readings
- Total desats = count of contiguous SpO2 segments below 90%
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

DEFAULT_SAMPLE_RATE_HZ = 10.0
DEFAULT_SNORING_THRESHOLD = 5.0
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ANALYSIS_JSON_DIR = REPO_ROOT / "data" / "analysis_json"


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
            return float(np.median(finite_diffs))
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


def _baseline_spo2(spo2: np.ndarray) -> float:
    if spo2.size == 0:
        return 0.0
    upper_cutoff = np.percentile(spo2, 90)
    upper_values = spo2[spo2 >= upper_cutoff]
    if upper_values.size == 0:
        return float(np.percentile(spo2, 95))
    return float(np.mean(upper_values))


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
    if spo2.size:
        valid_spo2 = spo2[np.isfinite(spo2)]
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
        total_desats = int(len(segments_below_90))
        desat_index = float(total_desats / sleep_hours) if sleep_hours > 0 else 0.0
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
            "total_desats": total_desats,
            "total_desats_display": str(total_desats),
            "desaturation_index": desat_index,
            "desaturation_index_display": f"{desat_index:.1f}",
            "desat_max_pct": max(0.0, baseline - minimum_value),
            "desat_max_pct_display": f"{max(0.0, baseline - minimum_value):.1f}",
            "desat_max_sec": desat_max_sec,
            "desat_max_sec_display": _duration_text(desat_max_sec),
            "lowest_spo2": minimum_value,
            "lowest_spo2_display": _number_text(minimum_value),
            "duration_of_min_spo2_sec": min_duration,
            "duration_of_min_spo2_display": _duration_text(min_duration),
            "highest_spo2": maximum_value,
            "highest_spo2_display": _number_text(maximum_value),
            "duration_of_max_spo2_sec": max_duration,
            "duration_of_max_spo2_display": _duration_text(max_duration),
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
            "desat_max_sec": 0.0,
            "desat_max_sec_display": "0.0 sec",
            "lowest_spo2": None,
            "lowest_spo2_display": "-",
            "duration_of_min_spo2_sec": 0.0,
            "duration_of_min_spo2_display": "0.0 sec",
            "highest_spo2": None,
            "highest_spo2_display": "-",
            "duration_of_max_spo2_sec": 0.0,
            "duration_of_max_spo2_display": "0.0 sec",
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
