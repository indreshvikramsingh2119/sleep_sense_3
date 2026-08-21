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

try:
    from src.components.airflow_display_processing import enhance_airflow_for_graph_and_detection
except ImportError:
    enhance_airflow_for_graph_and_detection = None


SKIP_MINUTES = 20.0
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

# ---------------------------------------------------------------------------
# AASM scoring rules
# ---------------------------------------------------------------------------
# Hypopnea: airflow reduced >=30%, AND SpO2 desaturation >=3% (AASM
# "recommended" rule). The alternative AASM rule allows arousal instead of
# desaturation, but this device has no EEG/arousal signal, so only the
# desaturation path is usable here.
AASM_HYPOPNEA_DROP_PERCENT = 30.0
AASM_HYPOPNEA_SPO2_DESAT_MIN = 3.0
# Apnea (Obstructive/Central/Mixed): airflow reduced >=90%.
AASM_APNEA_DROP_PERCENT = 90.0
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
    ai_label: str | None = None
    ai_confidence: float | None = None
    final_label: str | None = None
    image_path: str | None = None

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


def _effort_amplitude(values: np.ndarray) -> float:
    """Measure breathing-effort amplitude (peak-to-trough spread) for a Thorax/Abdomen segment."""
    return _robust_signal_amplitude(values)


def _compute_effort_baseline(
    thorax: np.ndarray | None,
    abdomen: np.ndarray | None,
    baseline_mask: np.ndarray,
) -> tuple[float, float] | None:
    """Return (thorax_baseline_amplitude, abdomen_baseline_amplitude), or None
    if Thorax/Abdomen signals are missing or unusable for this recording."""
    if thorax is None or abdomen is None:
        return None
    thorax_baseline_window = thorax[baseline_mask]
    abdomen_baseline_window = abdomen[baseline_mask]
    if len(thorax_baseline_window) == 0 or len(abdomen_baseline_window) == 0:
        return None
    thorax_baseline_amp = _effort_amplitude(thorax_baseline_window)
    abdomen_baseline_amp = _effort_amplitude(abdomen_baseline_window)
    if thorax_baseline_amp <= 0 or abdomen_baseline_amp <= 0:
        return None
    return thorax_baseline_amp, abdomen_baseline_amp


def _effort_state(
    thorax_segment: np.ndarray,
    abdomen_segment: np.ndarray,
    thorax_baseline_amp: float,
    abdomen_baseline_amp: float,
    absent_below: float = OBSTRUCTIVE_APNEA_EFFORT_THRESHOLD,
    present_at_or_above: float = CENTRAL_APNEA_EFFORT_THRESHOLD,
) -> str:
    """Classify one half-event's breathing effort relative to baseline as
    'absent', 'borderline', or 'present'."""
    thorax_ratio = _effort_amplitude(thorax_segment) / thorax_baseline_amp if thorax_baseline_amp else 0.0
    abdomen_ratio = _effort_amplitude(abdomen_segment) / abdomen_baseline_amp if abdomen_baseline_amp else 0.0
    best_ratio = max(thorax_ratio, abdomen_ratio)
    if best_ratio < absent_below:
        return "absent"
    if best_ratio >= present_at_or_above:
        return "present"
    return "borderline"


def classify_apnea_effort_type(
    thorax_event: np.ndarray,
    abdomen_event: np.ndarray,
    thorax_baseline_amp: float,
    abdomen_baseline_amp: float,
) -> str:
    """Classify an apnea-tier event (>=90% airflow drop) as Obstructive (OSA),
    Central (CSA), or Mixed (MSA) based on whether breathing effort
    (Thorax/Abdomen movement) continues during the event - the real AASM
    signal for this distinction (not how deep the airflow drop is).
    """
    sample_count = len(thorax_event)
    if sample_count < 2:
        return "OSA"
    midpoint = sample_count // 2
    first_half_state = _effort_state(
        thorax_event[:midpoint], abdomen_event[:midpoint], thorax_baseline_amp, abdomen_baseline_amp
    )
    second_half_state = _effort_state(
        thorax_event[midpoint:], abdomen_event[midpoint:], thorax_baseline_amp, abdomen_baseline_amp
    )
    if first_half_state == "present" and second_half_state == "present":
        return "OSA"
    if first_half_state == "absent" and second_half_state == "absent":
        thorax_ratio = _effort_amplitude(thorax_event) / thorax_baseline_amp if thorax_baseline_amp else 0.0
        abdomen_ratio = _effort_amplitude(abdomen_event) / abdomen_baseline_amp if abdomen_baseline_amp else 0.0
        whole_event_ratio = max(thorax_ratio, abdomen_ratio)
        if whole_event_ratio < CENTRAL_APNEA_AMPLITUDE_CONFIRM_RATIO:
            return "CSA"
        return "MSA"
    return "MSA"


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
) -> str:
    if duration_sec is not None and duration_sec > MAX_EVENT_SEC:
        return "NO_EVENT"

    if duration_sec is None or duration_sec < MIN_EVENT_SEC:
        return "NO_EVENT"

    drop_percent = drop_ratio * 100.0

    if drop_percent >= AASM_APNEA_DROP_PERCENT:
        return "APNEA_CANDIDATE"

    if drop_percent >= AASM_HYPOPNEA_DROP_PERCENT:
        if spo2_drop >= AASM_HYPOPNEA_SPO2_DESAT_MIN:
            return "HYPOPNEA"
        return "NO_EVENT"

    return "NO_EVENT"


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
    effort_baseline = _compute_effort_baseline(thorax, abdomen, baseline_mask)

    apnea_threshold = baseline_airflow_reference * (1.0 - AASM_APNEA_DROP_PERCENT / 100.0)
    hypopnea_threshold = baseline_airflow_reference * (1.0 - AASM_HYPOPNEA_DROP_PERCENT / 100.0)

    analysis_mask = time_sec >= skip_sec
    analysis_time = time_sec[analysis_mask]
    analysis_airflow = airflow[analysis_mask]
    global_indices = np.where(analysis_mask)[0]

    analysis_peak_envelope = (
        pd.Series(analysis_airflow)
        .rolling(window=peak_window_points, center=True, min_periods=1)
        .max()
        .to_numpy()
    )
    analysis_window_baseline = _build_hourly_baseline_array(analysis_time, hourly_peak_baselines)
    if len(analysis_window_baseline) != len(analysis_time) or np.any(analysis_window_baseline <= 0):
        raise ValueError("Hourly baseline mapping failed for analysis window.")

    analysis_drop_percent = (
        ((analysis_window_baseline - analysis_peak_envelope) / analysis_window_baseline) * 100.0
    )
    analysis_drop_percent = np.clip(analysis_drop_percent, 0.0, 100.0)

    label_specs = [
        (
            "APNEA_CANDIDATE",
            lambda x: x >= AASM_APNEA_DROP_PERCENT,
            MIN_EVENT_SEC,
        ),
        (
            "HYPOPNEA",
            lambda x: (x >= AASM_HYPOPNEA_DROP_PERCENT) & (x < AASM_APNEA_DROP_PERCENT),
            MIN_EVENT_SEC,
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

    for expected_label, label_mask_fn, _label_min_sec in label_specs:
        label_mask = label_mask_fn(analysis_drop_percent)
        # The band mask only captures the core. The 10 second rule is applied
        # after expanding the core to the full drop extent.
        label_segments = _segment_mask(label_mask, analysis_time, CORE_MIN_SEC)
        raw_segment_count += len(label_segments)

        for core_start, core_end, _core_duration_sec in label_segments:
            # Expand boundaries to the full drop extent before measuring duration.
            local_start, local_end = _expand_segment_to_drop_extent(
                core_start,
                core_end,
                analysis_drop_percent,
                analysis_time,
            )

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

            # AASM-style: use the real pre-event 2-minute local baseline.
            # Fall back to the hourly baseline only when the pre-event window
            # is too short or too sparse.
            event_baseline_airflow, _event_baseline_mode = compute_pre_event_baseline(
                time_sec=time_sec,
                airflow=airflow,
                event_start_sec=float(time_sec[start_index]),
                pre_event_window_sec=120.0,
                stability_cv_threshold=0.25,
                fallback_baseline=hourly_fallback_baseline,
            )

            event_min_airflow = float(np.nanmin(core_airflow))
            event_mean_airflow = float(np.nanmean(core_airflow))
            event_peak_airflow = float(np.nanmax(core_airflow))
            event_airflow_amplitude = _robust_signal_amplitude(core_airflow)
            airflow_amplitude_ratio = (
                event_airflow_amplitude / baseline_airflow_amplitude
                if baseline_airflow_amplitude
                else 0.0
            )

            drop_ratio = (
                (event_baseline_airflow - event_peak_airflow) / event_baseline_airflow
                if event_baseline_airflow
                else 0.0
            )
            drop_ratio = float(np.clip(drop_ratio, 0.0, 1.0))
            drop_percent = drop_ratio * 100.0

            pre_mask = (time_sec >= max(0.0, time_sec[start_index] - 30.0)) & (time_sec < time_sec[start_index])
            pre_spo2 = spo2[pre_mask]
            pre_spo2_ref = float(np.nanmax(pre_spo2)) if len(pre_spo2) > 0 else float(np.nanmax(spo2))

            post_mask = (time_sec > time_sec[end_index]) & (time_sec <= (time_sec[end_index] + 30.0))
            post_spo2 = spo2[post_mask]
            post_spo2_min = float(np.nanmin(post_spo2)) if len(post_spo2) > 0 else float(np.nanmin(event_spo2))
            spo2_drop = float(pre_spo2_ref - post_spo2_min)

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
            )
            if detected_rule_label == "NO_EVENT":
                continue

            if detected_rule_label != expected_label:
                continue

            rule_label = detected_rule_label

            if rule_label == "APNEA_CANDIDATE":
                if thorax is not None and abdomen is not None and effort_baseline is not None:
                    thorax_baseline_amp, abdomen_baseline_amp = effort_baseline
                    rule_label = classify_apnea_effort_type(
                        thorax_event=thorax[start_index:end_index + 1],
                        abdomen_event=abdomen[start_index:end_index + 1],
                        thorax_baseline_amp=thorax_baseline_amp,
                        abdomen_baseline_amp=abdomen_baseline_amp,
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

        # For overlapping events with different labels, keep the one with the
        # deeper airflow drop.
        if event["start_sec"] < previous["end_sec"]:
            if float(event["airflow_drop_percent"]) > float(previous["airflow_drop_percent"]):
                merged_events[-1] = dict(event)
            continue

        merged_events.append(dict(event))

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
                ai_label=ai_label,
                ai_confidence=ai_confidence,
                final_label=final_label,
                image_path=image_path,
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
        baseline_source="hourly_window_most_frequent_peak_values",
    )
    debug_events = [_build_event_debug_line(event.to_dict(), event.event_id) for event in events]

    return {
        "baseline_source": "hourly_window_most_frequent_peak_values",
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
    print(f"OSA threshold 70% drop      : airflow <= {result['apnea_threshold']:.2f}")
    print(f"HSA threshold 30% drop      : airflow <= {result['hypopnea_threshold']:.2f}")
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
