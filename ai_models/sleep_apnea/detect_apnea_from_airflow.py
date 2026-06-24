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

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

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


SKIP_MINUTES = 20.0
BASELINE_MINUTES = 45.0
MIN_CANDIDATE_SEC = 4.0
HSA_MIN_SEC = 4.0
OSA_MIN_SEC = 4.0
CSA_MIN_SEC = 10.0
MAX_EVENT_SEC = 120.0
MIN_STABLE_OCCURRENCE = 30
BASELINE_TARGET_OCCURRENCE = 500
BASELINE_OCCURRENCE_TOLERANCE = 50
CANDIDATE_WINDOW_SEC = 1.0
CANDIDATE_MIN_FRACTION = 0.60
BAND_MAX_GAP_SAMPLES = 3

APNEA_DROP = 0.80
HYPOPNEA_DROP = 0.30
MSA_DROP = 0.70
MERGE_GAP_SEC = 0.0

SPO2_APNEA_DROP = 3.0
SPO2_HYPOPNEA_DROP = 4.0

SNORING_HIGH = 10.0
MOVEMENT_HIGH = 2.5
SNORING_LOW = 10.0
MOVEMENT_LOW = 2.5


@dataclass
class DetectedApneaEvent:
    event_id: int
    start_sec: float
    end_sec: float
    duration_sec: float
    baseline_airflow: float
    event_min_airflow: float
    event_mean_airflow: float
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
    counts = rounded.value_counts().sort_index(ascending=False)
    for value, count in counts.items():
        if int(count) >= int(min_occurrence):
            return float(value), int(count)
    max_value = float(rounded.max())
    return max_value, int((rounded == max_value).sum())


def baseline_from_occurrence_band(
    values: pd.Series | np.ndarray,
    target_occurrence: int = BASELINE_TARGET_OCCURRENCE,
    tolerance: int = BASELINE_OCCURRENCE_TOLERANCE,
) -> tuple[float, int]:
    series = pd.Series(values).dropna()
    series = pd.to_numeric(series, errors="coerce").dropna()

    rounded = series.round(2)
    counts = rounded.value_counts().sort_index(ascending=False)

    lower = target_occurrence - tolerance
    upper = target_occurrence + tolerance

    candidates: list[tuple[float, int]] = []
    for value, count in counts.items():
        if lower <= int(count) <= upper:
            candidates.append((float(value), int(count)))

    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
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

    closest.sort(key=lambda item: item[0], reverse=True)
    return closest[0]


def _segment_mask(mask: np.ndarray, time_sec: np.ndarray, min_event_sec: float) -> list[tuple[int, int, float]]:
    segments: list[tuple[int, int, float]] = []
    start_index: int | None = None

    for index, is_active in enumerate(mask):
        if is_active and start_index is None:
            start_index = index
            continue

        if not is_active and start_index is not None:
            end_index = index - 1
            duration_sec = float(time_sec[end_index] - time_sec[start_index])
            if duration_sec >= min_event_sec:
                segments.append((start_index, end_index, duration_sec))
            start_index = None

    if start_index is not None:
        end_index = len(mask) - 1
        duration_sec = float(time_sec[end_index] - time_sec[start_index])
        if duration_sec >= min_event_sec:
            segments.append((start_index, end_index, duration_sec))

    return segments


def _rolling_fraction_mask(mask: np.ndarray, window_size: int, min_fraction: float) -> np.ndarray:
    if window_size <= 1:
        return mask.astype(bool)
    kernel = np.ones(int(window_size), dtype=float)
    fraction = np.convolve(mask.astype(float), kernel, mode="same") / float(window_size)
    return fraction >= float(min_fraction)


def _longest_true_run(mask: np.ndarray) -> tuple[int, int] | None:
    best_start: int | None = None
    best_end: int | None = None
    run_start: int | None = None

    for index, is_true in enumerate(mask):
        if is_true and run_start is None:
            run_start = index
            continue

        if not is_true and run_start is not None:
            run_end = index - 1
            if best_start is None or (run_end - run_start) > (best_end - best_start):
                best_start = run_start
                best_end = run_end
            run_start = None

    if run_start is not None:
        run_end = len(mask) - 1
        if best_start is None or (run_end - run_start) > (best_end - best_start):
            best_start = run_start
            best_end = run_end

    if best_start is None or best_end is None:
        return None

    return best_start, best_end


def _fill_short_false_gaps(mask: np.ndarray, max_gap: int) -> np.ndarray:
    filled = mask.astype(bool).copy()
    gap_start: int | None = None

    for index, is_true in enumerate(filled):
        if not is_true and gap_start is None:
            gap_start = index
            continue

        if is_true and gap_start is not None:
            gap_len = index - gap_start
            if gap_len <= max_gap:
                filled[gap_start:index] = True
            gap_start = None

    return filled


def _band_limits_for_label(baseline_airflow: float, label: str) -> tuple[float, float] | None:
    if label == "HSA":
        return 0.0, baseline_airflow * 0.30

    if label == "OSA":
        return baseline_airflow * 0.50, baseline_airflow * 0.70

    if label == "CSA":
        return baseline_airflow * 0.80, baseline_airflow * 0.90

    return None


def _label_min_duration_sec(label: str) -> float:
    if label == "HSA":
        return HSA_MIN_SEC
    if label == "OSA":
        return OSA_MIN_SEC
    if label == "CSA":
        return CSA_MIN_SEC
    return MIN_CANDIDATE_SEC


def _build_debug_summary(
    baseline_airflow: float,
    apnea_threshold: float,
    hypopnea_threshold: float,
    raw_segments: int,
    filtered_segments: int,
    merged_segments: int,
    baseline_source: str,
) -> list[str]:
    return [
        f"baseline_source={baseline_source}",
        f"baseline_airflow={baseline_airflow:.2f}",
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
        f"min_airflow={float(event['event_min_airflow']):.2f} | "
        f"drop={float(event['airflow_drop_percent']):.1f}% | "
        f"rule={str(event['rule_label'])}"
    )


def classify_rule_event(
    drop_ratio: float,
    spo2_drop: float,
    snoring_mean: float,
    movement_mean: float,
    variability_score: float,
    duration_sec: float | None = None,
) -> str:
    # AIRFLOW-ONLY MODE
    # HSA
    # airflow_drop 70% to 100%
    # >>>>>>>>>>>>>>>>>>>>>
    #
    # OSA
    # airflow_drop 40% to <70%
    # >>>>>>>>>>>>>>>>>>>>>
    #
    # CSA
    # airflow_drop 10% to <40%
    # >>>>>>>>>>>>>>>>>>>>>
    #
    # NO_EVENT
    # duration < candidate sec
    # >>>>>>>>>>>>>>>>>>>>>
    if duration_sec is not None and duration_sec > MAX_EVENT_SEC:
        return "NO_EVENT"

    if duration_sec is None or duration_sec < MIN_CANDIDATE_SEC:
        return "NO_EVENT"

    drop_percent = drop_ratio * 100.0

    if 70.0 <= drop_percent <= 100.0:
        return "HSA"

    if 30.0 <= drop_percent < 50.0:
        return "OSA"

    if 10.0 <= drop_percent < 20.0:
        return "CSA"

    return "NO_EVENT"


def _finalize_label(rule_label: str, ai_label: str | None, ai_confidence: float | None) -> str:
    if ai_label is None or ai_confidence is None:
        return rule_label
    if rule_label == "NO_EVENT":
        return rule_label
    if rule_label in {"HSA", "OSA", "CSA"}:
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
    processed_df, preprocess_meta = preprocess_signals(signal_df)
    raw_time_sec = signal_df["time_sec"].to_numpy(dtype=float)
    raw_airflow = signal_df["airflow"].to_numpy(dtype=float)
    time_sec = signal_df["time_sec"].to_numpy(dtype=float)
    airflow = signal_df["airflow"].to_numpy(dtype=float)
    spo2 = signal_df["spo2"].to_numpy(dtype=float)
    snoring = signal_df["snoring"].to_numpy(dtype=float)
    body_movement = signal_df["body_movement"].to_numpy(dtype=float)

    estimated_fs = estimate_sample_rate_hz(signal_df)
    sample_dt = 1.0 / estimated_fs if estimated_fs else 0.1
    skip_sec = SKIP_MINUTES * 60.0
    baseline_end_sec = skip_sec + (BASELINE_MINUTES * 60.0)

    baseline_mask = (raw_time_sec >= skip_sec) & (raw_time_sec < baseline_end_sec)
    baseline_airflow_window = raw_airflow[baseline_mask]
    if len(baseline_airflow_window) == 0:
        raise ValueError("Baseline airflow window is empty. Recording is too short.")

    airflow_baseline, baseline_occurrence = baseline_from_occurrence_band(
        baseline_airflow_window,
        target_occurrence=BASELINE_TARGET_OCCURRENCE,
        tolerance=BASELINE_OCCURRENCE_TOLERANCE,
    )
    apnea_threshold = airflow_baseline * (1.0 - APNEA_DROP)
    hypopnea_threshold = airflow_baseline * (1.0 - HYPOPNEA_DROP)
    analysis_mask = time_sec >= skip_sec
    analysis_time = time_sec[analysis_mask]
    analysis_airflow = airflow[analysis_mask]
    raw_candidate_mask = analysis_airflow <= hypopnea_threshold
    candidate_window_points = max(1, int(round(estimated_fs * CANDIDATE_WINDOW_SEC)))
    candidate_mask = _rolling_fraction_mask(
        raw_candidate_mask,
        window_size=candidate_window_points,
        min_fraction=CANDIDATE_MIN_FRACTION,
    )
    segments = _segment_mask(candidate_mask, analysis_time, MIN_CANDIDATE_SEC)
    global_indices = np.where(analysis_mask)[0]

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
    for local_start, local_end, duration_sec in segments:
        start_index = int(global_indices[local_start])
        end_index = int(global_indices[local_end])

        event_airflow = airflow[start_index:end_index + 1]
        event_spo2 = spo2[start_index:end_index + 1]
        event_snoring = snoring[start_index:end_index + 1]
        event_movement = body_movement[start_index:end_index + 1]

        event_min_airflow = float(np.nanmin(event_airflow))
        event_mean_airflow = float(np.nanmean(event_airflow))
        drop_ratio = 1.0 - (event_min_airflow / airflow_baseline) if airflow_baseline else 0.0
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
        airflow_std = float(np.nanstd(event_airflow))
        variability_score = airflow_std / airflow_baseline if airflow_baseline else 0.0

        valid_band_candidates: list[tuple[float, str, int, int]] = []
        for candidate_label in ("HSA", "OSA", "CSA"):
            band_limits = _band_limits_for_label(airflow_baseline, candidate_label)
            if band_limits is None:
                continue

            band_low, band_high = band_limits
            band_mask = (event_airflow >= band_low) & (event_airflow <= band_high)

            if candidate_label in {"HSA", "OSA"}:
                band_mask = _fill_short_false_gaps(band_mask, max_gap=BAND_MAX_GAP_SAMPLES)

            band_run = _longest_true_run(band_mask)
            if band_run is None:
                continue

            local_band_start, local_band_end = band_run
            band_duration_sec = (local_band_end - local_band_start + 1) * sample_dt
            if band_duration_sec < _label_min_duration_sec(candidate_label):
                continue

            valid_band_candidates.append(
                (band_duration_sec, candidate_label, local_band_start, local_band_end)
            )

        if not valid_band_candidates:
            continue

        valid_band_candidates.sort(key=lambda item: item[0], reverse=True)
        band_duration_sec, rule_label, local_band_start, local_band_end = valid_band_candidates[0]

        trimmed_start_index = start_index + local_band_start
        trimmed_end_index = start_index + local_band_end

        start_index = trimmed_start_index
        end_index = trimmed_end_index
        duration_sec = band_duration_sec

        event_airflow = airflow[start_index:end_index + 1]
        event_spo2 = spo2[start_index:end_index + 1]
        event_snoring = snoring[start_index:end_index + 1]
        event_movement = body_movement[start_index:end_index + 1]

        event_min_airflow = float(np.nanmin(event_airflow))
        event_mean_airflow = float(np.nanmean(event_airflow))
        drop_ratio = 1.0 - (event_min_airflow / airflow_baseline) if airflow_baseline else 0.0
        drop_percent = drop_ratio * 100.0

        snoring_mean = float(np.nanmean(event_snoring))
        movement_mean = float(np.nanmean(event_movement))
        airflow_std = float(np.nanstd(event_airflow))
        variability_score = airflow_std / airflow_baseline if airflow_baseline else 0.0

        preliminary_events.append(
            {
                "start_index": start_index,
                "end_index": end_index,
                "start_sec": float(time_sec[start_index]),
                "end_sec": float(time_sec[end_index]),
                "duration_sec": float(duration_sec),
                "baseline_airflow": float(airflow_baseline),
                "event_min_airflow": event_min_airflow,
                "event_mean_airflow": event_mean_airflow,
                "airflow_drop_percent": float(drop_percent),
                "spo2_drop": spo2_drop,
                "snoring_mean": snoring_mean,
                "movement_mean": movement_mean,
                "variability_score": float(variability_score),
                "rule_label": rule_label,
            }
        )

    filtered_events = sorted(preliminary_events, key=lambda item: (item["start_sec"], item["end_sec"], item["rule_label"]))
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
            previous["airflow_drop_percent"] = max(previous["airflow_drop_percent"], event["airflow_drop_percent"])
            previous["spo2_drop"] = max(previous["spo2_drop"], event["spo2_drop"])
            previous["snoring_mean"] = max(previous["snoring_mean"], event["snoring_mean"])
            previous["movement_mean"] = max(previous["movement_mean"], event["movement_mean"])
            previous["variability_score"] = max(previous["variability_score"], event["variability_score"])
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
        if model is not None and str(event["rule_label"]) in {"OSA", "CSA", "HSA"}:
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
        baseline_airflow=float(airflow_baseline),
        apnea_threshold=float(apnea_threshold),
        hypopnea_threshold=float(hypopnea_threshold),
        raw_segments=int(len(segments)),
        filtered_segments=int(len(preliminary_events)),
        merged_segments=int(len(merged_events)),
        baseline_source="raw_airflow_occurrence_band_500pm50",
    )
    debug_events = [_build_event_debug_line(event.to_dict(), event.event_id) for event in events]

    return {
        "baseline_source": "raw_airflow_occurrence_band_500pm50",
        "pipeline_mode": "rule_first_ai_second",
        "rule_scan_used": True,
        "ai_enabled_requested": bool(enable_ai),
        "ai_model_loaded": model is not None,
        "rule_candidate_segments_found": int(len(segments)),
        "rule_candidates_after_filter": int(len(preliminary_events)),
        "rule_candidates_after_merge": int(len(merged_events)),
        "ai_candidates_processed": int(ai_candidates_processed),
        "baseline_airflow": float(airflow_baseline),
        "baseline_occurrence": int(baseline_occurrence),
        "stable_peak_baseline": float(airflow_baseline),
        "stable_peak_occurrence": int(baseline_occurrence),
        "apnea_threshold": float(apnea_threshold),
        "hypopnea_threshold": float(hypopnea_threshold),
        "estimated_sample_rate_hz": float(estimated_fs),
        "preprocess_meta": preprocess_meta,
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
    print(f"Stable airflow baseline     : {result['baseline_airflow']:.2f}")
    print(f"Baseline occurrence         : {result['baseline_occurrence']}")
    print(f"Apnea threshold 90% drop    : airflow <= {result['apnea_threshold']:.2f}")
    print(f"Hypopnea threshold 30% drop : airflow <= {result['hypopnea_threshold']:.2f}")
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
