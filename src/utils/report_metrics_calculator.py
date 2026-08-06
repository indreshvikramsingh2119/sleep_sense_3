import json
from datetime import datetime
from pathlib import Path

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_JSON_DIR = REPO_ROOT / "data" / "analysis_json"


def _as_float_array(values):
    if values is None:
        return np.asarray([], dtype=float)
    array = np.asarray(values, dtype=float)
    if array.ndim == 0:
        array = array.reshape(1)
    return array[np.isfinite(array)]


def _format_number(value, digits=1):
    return f"{float(value):.{digits}f}"


def _format_seconds(value):
    return f"{int(round(max(float(value), 0.0)))} sec"


def _safe_duration_seconds(time_data):
    time_array = _as_float_array(time_data)
    if time_array.size >= 2:
        duration = float(time_array[-1] - time_array[0])
        if duration > 0:
            return duration
    return 0.0


def _sample_period_seconds(time_data, sample_rate_hz):
    time_array = _as_float_array(time_data)
    if time_array.size >= 2:
        diffs = np.diff(time_array)
        diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
        if diffs.size:
            return float(np.median(diffs))
    if sample_rate_hz and sample_rate_hz > 0:
        return 1.0 / float(sample_rate_hz)
    return 1.0


def _threshold_duration(signal, threshold, direction, sample_period_seconds):
    if signal.size == 0:
        return 0.0
    if direction == "below":
        mask = signal < threshold
    else:
        mask = signal > threshold
    return float(np.count_nonzero(mask) * sample_period_seconds)


def _longest_run_seconds(mask, sample_period_seconds):
    if mask.size == 0:
        return 0.0
    max_run = 0
    current_run = 0
    for active in mask:
        if active:
            current_run += 1
            if current_run > max_run:
                max_run = current_run
        else:
            current_run = 0
    return float(max_run * sample_period_seconds)


def _estimate_desaturations(spo2, sample_rate_hz):
    if spo2.size < 2:
        return 0, 0.0
    drop_mask = np.diff(spo2) <= -3.0
    total_desats = int(np.count_nonzero(drop_mask))
    if sample_rate_hz and sample_rate_hz > 0:
        desat_max_sec = float(1.0 / sample_rate_hz)
    else:
        desat_max_sec = 1.0
    return total_desats, desat_max_sec


def _build_oximetry_section(spo2, duration_seconds, sample_period_seconds, sample_rate_hz):
    if spo2.size == 0:
        return {
            "mean_spo2_display": "0",
            "min_spo2_display": "0",
            "max_spo2_display": "0",
            "total_desats_display": "0",
            "desaturation_index_display": "0.0",
            "desat_max_pct_display": "0",
            "desat_max_sec_display": "0 sec",
            "lowest_spo2_display": "0",
            "duration_of_min_spo2_display": "0 sec",
            "highest_spo2_display": "0",
            "duration_of_max_spo2_display": "0 sec",
            "duration_below_90_display": "0 sec",
            "duration_below_85_display": "0 sec",
            "duration_below_80_display": "0 sec",
            "baseline_spo2_display": "0",
            "spo2_variability": "0.0",
            "oxygen_saturation_trend": "0.0",
        }

    mean_spo2 = float(np.mean(spo2))
    min_spo2 = float(np.min(spo2))
    max_spo2 = float(np.max(spo2))
    total_desats, desat_max_sec = _estimate_desaturations(spo2, sample_rate_hz)
    hours = duration_seconds / 3600.0 if duration_seconds > 0 else 0.0
    desat_index = total_desats / hours if hours > 0 else 0.0

    min_mask = np.isclose(spo2, min_spo2)
    max_mask = np.isclose(spo2, max_spo2)

    trend = 0.0
    if spo2.size >= 2:
        trend = float(np.polyfit(np.arange(spo2.size, dtype=float), spo2, 1)[0])

    return {
        "mean_spo2_display": _format_number(mean_spo2, 1),
        "min_spo2_display": _format_number(min_spo2, 1),
        "max_spo2_display": _format_number(max_spo2, 1),
        "total_desats_display": str(total_desats),
        "desaturation_index_display": _format_number(desat_index, 1),
        "desat_max_pct_display": _format_number(max(mean_spo2 - min_spo2, 0.0), 1),
        "desat_max_sec_display": _format_seconds(desat_max_sec),
        "lowest_spo2_display": _format_number(min_spo2, 1),
        "duration_of_min_spo2_display": _format_seconds(_longest_run_seconds(min_mask, sample_period_seconds)),
        "highest_spo2_display": _format_number(max_spo2, 1),
        "duration_of_max_spo2_display": _format_seconds(_longest_run_seconds(max_mask, sample_period_seconds)),
        "duration_below_90_display": _format_seconds(_threshold_duration(spo2, 90.0, "below", sample_period_seconds)),
        "duration_below_85_display": _format_seconds(_threshold_duration(spo2, 85.0, "below", sample_period_seconds)),
        "duration_below_80_display": _format_seconds(_threshold_duration(spo2, 80.0, "below", sample_period_seconds)),
        "baseline_spo2_display": _format_number(float(np.median(spo2)), 1),
        "spo2_variability": _format_number(float(np.std(spo2)), 2),
        "oxygen_saturation_trend": _format_number(trend, 4),
    }


def _build_heart_rate_section(pulse):
    if pulse.size == 0:
        return {
            "mean_hr_display": "0 BPM",
            "highest_hr_display": "0 BPM",
            "lowest_hr_display": "0 BPM",
        }

    return {
        "mean_hr_display": f"{_format_number(np.mean(pulse), 1)} BPM",
        "highest_hr_display": f"{_format_number(np.max(pulse), 1)} BPM",
        "lowest_hr_display": f"{_format_number(np.min(pulse), 1)} BPM",
    }


def _build_snoring_section(snoring, duration_seconds, sample_period_seconds):
    if snoring.size == 0:
        return {
            "total_snoring_episodes_display": "0",
            "total_snoring_duration_display": "0 sec",
            "mean_snoring_duration_display": "0 sec",
            "snoring_percentage_display": "0.0 %",
        }

    threshold = float(np.mean(snoring) + np.std(snoring))
    active = snoring > threshold
    episode_lengths = []
    run_length = 0
    for is_active in active:
        if is_active:
            run_length += 1
        elif run_length:
            episode_lengths.append(run_length)
            run_length = 0
    if run_length:
        episode_lengths.append(run_length)

    total_duration = float(np.count_nonzero(active) * sample_period_seconds)
    mean_duration = (
        float(np.mean(episode_lengths) * sample_period_seconds)
        if episode_lengths
        else 0.0
    )
    percentage = (total_duration / duration_seconds * 100.0) if duration_seconds > 0 else 0.0

    return {
        "total_snoring_episodes_display": str(len(episode_lengths)),
        "total_snoring_duration_display": _format_seconds(total_duration),
        "mean_snoring_duration_display": _format_seconds(mean_duration),
        "snoring_percentage_display": f"{_format_number(percentage, 1)} %",
    }


def calculate_sleep_metrics(time_data, signals, sample_rate_hz=1.0):
    duration_seconds = _safe_duration_seconds(time_data)
    sample_period_seconds = _sample_period_seconds(time_data, sample_rate_hz)
    spo2 = _as_float_array(signals.get("spo2"))
    pulse = _as_float_array(signals.get("pulse"))
    snoring = _as_float_array(signals.get("snoring"))

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "duration_seconds": round(duration_seconds, 2),
        "sample_rate_hz": float(sample_rate_hz) if sample_rate_hz else 0.0,
        "oximetry": _build_oximetry_section(
            spo2,
            duration_seconds=duration_seconds,
            sample_period_seconds=sample_period_seconds,
            sample_rate_hz=sample_rate_hz,
        ),
        "heart_rate": _build_heart_rate_section(pulse),
        "snoring": _build_snoring_section(
            snoring,
            duration_seconds=duration_seconds,
            sample_period_seconds=sample_period_seconds,
        ),
    }


def save_sleep_metrics_json(analysis_results, source_csv=None):
    ANALYSIS_JSON_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(source_csv).stem if source_csv else "sleep_metrics"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = ANALYSIS_JSON_DIR / f"{stem}_analysis_{timestamp}.json"

    payload = dict(analysis_results or {})
    if source_csv:
        payload["source_csv"] = str(source_csv)

    with output_path.open("w", encoding="utf-8") as file_handle:
        json.dump(payload, file_handle, indent=2)

    return str(output_path)
