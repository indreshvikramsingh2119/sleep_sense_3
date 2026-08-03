#!/usr/bin/env python3

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image

LEGACY_PIPELINE_NOTE = (
    "Legacy candidate-generation helpers retained for offline scripts. "
    "The dashboard uses detect_apnea_from_airflow.py as the active detector."
)

CURRENT_DIR = Path(__file__).resolve().parent
MODELS_DIR = CURRENT_DIR / "models"
DEFAULT_MODEL_PATH = MODELS_DIR / "event_image_cnn_custom.keras"
DEFAULT_META_PATH = MODELS_DIR / "event_image_cnn_meta.json"
DEFAULT_CLASS_NAMES_PATH = MODELS_DIR / "event_image_cnn_class_names.json"
DEFAULT_OUTPUT_DIR = CURRENT_DIR / "hybrid_pipeline_output"

SIGNAL_COLUMNS = {
    "timestamp": 0,
    "body_position": 1,
    "pulse": 2,
    "spo2": 3,
    "body_movement": 4,
    "airflow": 5,
    "snoring": 7,
    "abdomen": 10,
}
CSV_SIGNAL_NAMES = tuple(
    signal_name
    for signal_name in SIGNAL_COLUMNS
    if signal_name != "timestamp"
)
INTERPOLATED_SIGNAL_NAMES = tuple(
    signal_name
    for signal_name in CSV_SIGNAL_NAMES
    if signal_name != "timestamp"
)
EVENT_IMAGE_CHANNEL_ORDER = ["airflow", "spo2", "pulse", "body_movement", "snoring"]
EVENT_IMAGE_Y_LIMITS = {
    "airflow": (-10, 110),
    "spo2": (50, 105),
    "pulse": (30, 180),
    "body_movement": (-10, 110),
    "snoring": (-10, 110),
}
DEFAULT_SAMPLE_RATE_HZ = 10.0
DEFAULT_IMAGE_SIZE = (64, 64)


@dataclass
class CandidateEvent:
    event_id: str
    start_sec: float
    end_sec: float
    duration_sec: float
    start_index: int
    end_index: int
    airflow_baseline: float
    airflow_min: float
    airflow_drop_percent: float
    spo2_baseline: float
    spo2_min: float
    spo2_drop: float
    movement_mean: float
    snoring_mean: float
    rule_hint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _resolve_existing_path(path_str: str | None, fallback: Path) -> Path:
    if path_str:
        candidate = Path(path_str)
        if candidate.exists():
            return candidate
    return fallback


def _normalize_leading_empty_columns(numeric: pd.DataFrame) -> pd.DataFrame:
    """Drop fully empty leading columns so signal mapping always starts from column 0."""
    normalized = numeric.copy()
    while normalized.shape[1] > 0:
        first_col = pd.to_numeric(normalized.iloc[:, 0], errors="coerce")
        if first_col.notna().sum() > 0:
            break
        normalized = normalized.iloc[:, 1:].reset_index(drop=True)
    return normalized


def load_sleep_csv(csv_path: str | Path) -> pd.DataFrame:
    csv_path = Path(csv_path)
    raw = pd.read_csv(csv_path, header=None)
    numeric = raw.apply(pd.to_numeric, errors="coerce")
    numeric = numeric.dropna(how="all").reset_index(drop=True)
    numeric = _normalize_leading_empty_columns(numeric)

    if numeric.shape[1] == 0:
        raise ValueError(
            f"CSV {csv_path} has no usable numeric columns."
        )

    timestamp_index = SIGNAL_COLUMNS["timestamp"]
    if numeric.shape[1] <= timestamp_index:
        raise ValueError(f"CSV {csv_path} is missing the timestamp column at index {timestamp_index}.")

    available_signal_columns = {
        name: index
        for name, index in SIGNAL_COLUMNS.items()
        if index < numeric.shape[1]
    }

    signal_df = pd.DataFrame(
        {
            name: numeric.iloc[:, index]
            for name, index in available_signal_columns.items()
        }
    )
    signal_df = signal_df.dropna(subset=["timestamp"]).reset_index(drop=True)
    signal_df["timestamp"] = signal_df["timestamp"].astype(float)

    # Project timing is fixed at 10 Hz, so derive time from sample index
    signal_df["time_sec"] = np.arange(len(signal_df), dtype=float) / DEFAULT_SAMPLE_RATE_HZ

    for channel in INTERPOLATED_SIGNAL_NAMES:
        if channel not in signal_df.columns:
            continue
        signal_df[channel] = pd.to_numeric(signal_df[channel], errors="coerce")
        signal_df[channel] = signal_df[channel].interpolate(limit_direction="both")
        signal_df[channel] = signal_df[channel].ffill().bfill()

    return signal_df


def estimate_sample_rate_hz(signal_df: pd.DataFrame) -> float:
    return DEFAULT_SAMPLE_RATE_HZ


def preprocess_signals(
    signal_df: pd.DataFrame,
    smoothing_seconds: float = 1.5,
    target_sample_rate_hz: float = DEFAULT_SAMPLE_RATE_HZ,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    processed = signal_df.copy()
    estimated_rate_hz = estimate_sample_rate_hz(signal_df)
    smoothing_points = max(3, int(round(estimated_rate_hz * smoothing_seconds)))
    if smoothing_points % 2 == 0:
        smoothing_points += 1

    for channel in EVENT_IMAGE_CHANNEL_ORDER:
        processed[channel] = (
            processed[channel]
            .rolling(window=smoothing_points, center=True, min_periods=1)
            .median()
        )

    metadata = {
        "source_rows": int(len(signal_df)),
        "processed_rows": int(len(processed)),
        "estimated_sample_rate_hz": estimated_rate_hz,
        "target_sample_rate_hz": float(target_sample_rate_hz),
        "smoothing_seconds": float(smoothing_seconds),
        "channels": EVENT_IMAGE_CHANNEL_ORDER,
    }
    return processed, metadata


def _classify_rule_hint(airflow_drop: float, spo2_drop: float, movement_mean: float, snoring_mean: float) -> str:
    # Legacy candidate-generation flow intentionally avoids subtype thresholds.
    # The active detector in detect_apnea_from_airflow.py owns HSA/OSA/CSA labeling.
    if airflow_drop >= 70.0 and movement_mean >= 25:
        return "MSA"

    return "REVIEW"


def detect_rule_candidates(
    signal_df: pd.DataFrame,
    min_event_seconds: float = 10.0,
    airflow_drop_threshold_percent: float = 10.0,
    spo2_drop_threshold: float = 2.0,
) -> list[CandidateEvent]:
    """Legacy rule-candidate extractor used by offline helper scripts."""
    time_values = signal_df["time_sec"].to_numpy(dtype=float)
    if len(time_values) == 0:
        return []

    global_airflow_drop = max(float(airflow_drop_threshold_percent), 10.0)
    window_seconds = max(60.0, min_event_seconds * 4.0)
    step_seconds = max(10.0, min_event_seconds)
    movement_threshold = float(signal_df["body_movement"].quantile(0.90))
    snoring_threshold = float(signal_df["snoring"].quantile(0.90))

    provisional: list[dict[str, Any]] = []
    window_start = float(time_values[0])
    window_end_limit = float(time_values[-1])

    while window_start + window_seconds <= window_end_limit:
        window_end = window_start + window_seconds
        window_df = signal_df[
            (signal_df["time_sec"] >= window_start)
            & (signal_df["time_sec"] < window_end)
        ]
        if len(window_df) < 10:
            window_start += step_seconds
            continue

        airflow = window_df["airflow"].to_numpy(dtype=float)
        spo2 = window_df["spo2"].to_numpy(dtype=float)
        movement = window_df["body_movement"].to_numpy(dtype=float)
        snoring = window_df["snoring"].to_numpy(dtype=float)

        airflow_median = float(np.median(airflow))
        airflow_min = float(np.min(airflow))
        airflow_drop_percent = max(0.0, (airflow_median - airflow_min) / max(airflow_median, 1.0) * 100.0)
        low_airflow_threshold = max(airflow_median * 0.45, airflow_min + 2.0)
        low_airflow_fraction = float(np.mean(airflow <= low_airflow_threshold))
        spo2_baseline = float(np.median(spo2))
        spo2_min = float(np.min(spo2))
        spo2_drop = max(0.0, spo2_baseline - spo2_min)
        movement_mean = float(np.mean(movement))
        snoring_mean = float(np.mean(snoring))
        movement_high_fraction = float(np.mean(movement >= movement_threshold))
        snoring_high_fraction = float(np.mean(snoring >= snoring_threshold))

        qualifies = (
            airflow_min <= 12.0
            and airflow_drop_percent >= global_airflow_drop
            and low_airflow_fraction >= 0.04
            and spo2_drop >= spo2_drop_threshold
        )
        if qualifies:
            provisional.append(
                {
                    "start_sec": window_start,
                    "end_sec": window_end,
                    "airflow_baseline": airflow_median,
                    "airflow_min": airflow_min,
                    "airflow_drop_percent": airflow_drop_percent,
                    "spo2_baseline": spo2_baseline,
                    "spo2_min": spo2_min,
                    "spo2_drop": spo2_drop,
                    "movement_mean": movement_mean,
                    "snoring_mean": snoring_mean,
                    "movement_high_fraction": movement_high_fraction,
                    "snoring_high_fraction": snoring_high_fraction,
                }
            )

        window_start += step_seconds

    merged: list[dict[str, Any]] = []
    overlap_margin = max(15.0, min_event_seconds)
    for row in provisional:
        if not merged or row["start_sec"] > (merged[-1]["end_sec"] - overlap_margin):
            merged.append(dict(row))
            continue

        active = merged[-1]
        active["end_sec"] = max(active["end_sec"], row["end_sec"])
        active["airflow_baseline"] = min(active["airflow_baseline"], row["airflow_baseline"])
        active["airflow_min"] = min(active["airflow_min"], row["airflow_min"])
        active["airflow_drop_percent"] = max(active["airflow_drop_percent"], row["airflow_drop_percent"])
        active["spo2_baseline"] = max(active["spo2_baseline"], row["spo2_baseline"])
        active["spo2_min"] = min(active["spo2_min"], row["spo2_min"])
        active["spo2_drop"] = max(active["spo2_drop"], row["spo2_drop"])
        active["movement_mean"] = max(active["movement_mean"], row["movement_mean"])
        active["snoring_mean"] = max(active["snoring_mean"], row["snoring_mean"])
        active["movement_high_fraction"] = max(active["movement_high_fraction"], row["movement_high_fraction"])
        active["snoring_high_fraction"] = max(active["snoring_high_fraction"], row["snoring_high_fraction"])

    candidates: list[CandidateEvent] = []
    sample_rate_hz = estimate_sample_rate_hz(signal_df)
    baseline_points = max(10, int(round(sample_rate_hz * 30)))

    for event_counter, row in enumerate(merged, start=1):
        start_indices = signal_df.index[signal_df["time_sec"] >= row["start_sec"]].tolist()
        end_indices = signal_df.index[signal_df["time_sec"] >= row["end_sec"]].tolist()
        if not start_indices:
            continue

        start_index = int(start_indices[0])
        end_index = int(end_indices[0]) if end_indices else int(signal_df.index[-1])
        end_index = max(start_index, min(end_index, len(signal_df) - 1))
        candidate = _build_candidate(
            signal_df=signal_df,
            start_index=start_index,
            end_index=end_index,
            event_counter=event_counter,
            baseline_points=baseline_points,
        )
        candidates.append(candidate)

    return candidates


def _build_candidate(
    signal_df: pd.DataFrame,
    start_index: int,
    end_index: int,
    event_counter: int,
    baseline_points: int,
) -> CandidateEvent:
    airflow = signal_df["airflow"].to_numpy(dtype=float)
    spo2 = signal_df["spo2"].to_numpy(dtype=float)
    movement = signal_df["body_movement"].to_numpy(dtype=float)
    snoring = signal_df["snoring"].to_numpy(dtype=float)
    time_sec = signal_df["time_sec"].to_numpy(dtype=float)

    baseline_start = max(0, start_index - baseline_points)
    airflow_baseline = float(np.median(airflow[baseline_start:start_index + 1]))
    spo2_baseline = float(np.median(spo2[baseline_start:start_index + 1]))

    airflow_min = float(np.min(airflow[start_index:end_index + 1]))
    spo2_min = float(np.min(spo2[start_index:end_index + 1]))
    movement_mean = float(np.mean(movement[start_index:end_index + 1]))
    snoring_mean = float(np.mean(snoring[start_index:end_index + 1]))

    airflow_drop_percent = max(0.0, (airflow_baseline - airflow_min) / max(airflow_baseline, 1.0) * 100.0)
    spo2_drop = max(0.0, spo2_baseline - spo2_min)

    start_sec = float(time_sec[start_index])
    end_sec = float(time_sec[end_index])
    duration_sec = max(0.0, end_sec - start_sec)
    rule_hint = _classify_rule_hint(airflow_drop_percent, spo2_drop, movement_mean, snoring_mean)

    return CandidateEvent(
        event_id=f"event_{event_counter:03d}",
        start_sec=start_sec,
        end_sec=end_sec,
        duration_sec=duration_sec,
        start_index=start_index,
        end_index=end_index,
        airflow_baseline=airflow_baseline,
        airflow_min=airflow_min,
        airflow_drop_percent=airflow_drop_percent,
        spo2_baseline=spo2_baseline,
        spo2_min=spo2_min,
        spo2_drop=spo2_drop,
        movement_mean=movement_mean,
        snoring_mean=snoring_mean,
        rule_hint=rule_hint,
    )


def create_event_window_image(
    signal_df: pd.DataFrame,
    candidate: CandidateEvent,
    output_path: str | Path,
    pre_event_seconds: float = 30.0,
    post_event_seconds: float = 30.0,
) -> Path:
    output_path = Path(output_path)
    start_sec = max(float(signal_df["time_sec"].min()), candidate.start_sec - pre_event_seconds)
    end_sec = min(float(signal_df["time_sec"].max()), candidate.end_sec + post_event_seconds)
    window_df = signal_df[(signal_df["time_sec"] >= start_sec) & (signal_df["time_sec"] <= end_sec)].copy()
    if window_df.empty:
        raise ValueError(f"No samples found for {candidate.event_id} image window.")

    relative_time = window_df["time_sec"].to_numpy(dtype=float) - candidate.start_sec
    fig, axes = plt.subplots(len(EVENT_IMAGE_CHANNEL_ORDER), 1, figsize=(6, 6), dpi=140, sharex=True)
    fig.patch.set_facecolor("white")

    for axis, channel in zip(axes, EVENT_IMAGE_CHANNEL_ORDER):
        y = window_df[channel].to_numpy(dtype=float)
        axis.plot(relative_time, y, color="#111111", linewidth=1.2)
        axis.axvspan(0.0, max(candidate.duration_sec, 0.1), color="#e5e7eb", alpha=0.9)
        axis.set_ylabel(channel, fontsize=8)
        axis.set_ylim(*EVENT_IMAGE_Y_LIMITS[channel])
        axis.grid(False)
        axis.tick_params(axis="both", labelsize=8)

    axes[-1].set_xlabel("seconds relative to event start", fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 1))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=140, facecolor="white")
    plt.close(fig)
    return output_path


def load_cnn_model_bundle(
    model_path: str | Path = DEFAULT_MODEL_PATH,
    meta_path: str | Path = DEFAULT_META_PATH,
    class_names_path: str | Path = DEFAULT_CLASS_NAMES_PATH,
) -> tuple[Any, list[str], dict[str, Any]]:
    try:
        import tensorflow as tf
    except ImportError as error:
        raise ImportError("TensorFlow is required only for AI event classification.") from error

    meta: dict[str, Any] = {}
    meta_candidate = Path(meta_path)
    if meta_candidate.exists():
        meta = json.loads(meta_candidate.read_text(encoding="utf-8"))

    resolved_model_path = _resolve_existing_path(meta.get("model_path"), Path(model_path))
    resolved_class_names_path = _resolve_existing_path(meta.get("class_names_path"), Path(class_names_path))

    if not resolved_model_path.exists():
        raise FileNotFoundError(f"CNN model not found: {resolved_model_path}")
    if not resolved_class_names_path.exists():
        raise FileNotFoundError(f"Class names not found: {resolved_class_names_path}")

    model = tf.keras.models.load_model(resolved_model_path)
    class_names = json.loads(resolved_class_names_path.read_text(encoding="utf-8"))
    meta["resolved_model_path"] = str(resolved_model_path)
    meta["resolved_class_names_path"] = str(resolved_class_names_path)
    return model, class_names, meta


def predict_event_image(
    image_path: str | Path,
    model: Any,
    class_names: list[str],
) -> dict[str, Any]:
    image_path = Path(image_path)
    _, height, width, channels = model.input_shape

    image = Image.open(image_path).convert("L" if channels == 1 else "RGB")
    image = image.resize((width, height))
    image_array = np.asarray(image, dtype=np.float32)
    if channels == 1:
        image_array = image_array[..., None]

    probs = model.predict(np.expand_dims(image_array, axis=0), verbose=0)[0]
    pred_index = int(np.argmax(probs))
    top_pairs = sorted(
        ((class_names[index], float(prob)) for index, prob in enumerate(probs)),
        key=lambda item: item[1],
        reverse=True,
    )

    return {
        "predicted_label": class_names[pred_index],
        "confidence": float(probs[pred_index]),
        "top_probabilities": [
            {"label": label, "confidence": confidence}
            for label, confidence in top_pairs
        ],
    }


def validate_event_with_rules(
    candidate: CandidateEvent,
    cnn_prediction: dict[str, Any],
    confidence_threshold: float = 0.70,
) -> dict[str, Any]:
    predicted_label = str(cnn_prediction["predicted_label"])
    confidence = float(cnn_prediction["confidence"])

    if confidence < confidence_threshold:
        final_label = candidate.rule_hint if candidate.rule_hint != "REVIEW" else predicted_label
        status = "low_confidence_rule_override"
        reason = f"CNN confidence {confidence:.3f} below threshold {confidence_threshold:.2f}"
    elif candidate.rule_hint == "REVIEW":
        final_label = predicted_label
        status = "accepted_with_review_flag"
        reason = "Rules found an event but could not map it confidently to one subtype."
    elif candidate.rule_hint == predicted_label:
        final_label = predicted_label
        status = "accepted"
        reason = "CNN and rule hint agree."
    else:
        final_label = candidate.rule_hint
        status = "rule_override"
        reason = f"CNN predicted {predicted_label} but rule hint favored {candidate.rule_hint}."

    return {
        "candidate_label": candidate.rule_hint,
        "cnn_label": predicted_label,
        "cnn_confidence": confidence,
        "final_label": final_label,
        "validation_status": status,
        "validation_reason": reason,
    }


def generate_sleep_report(
    rows: list[dict[str, Any]],
    output_dir: str | Path,
    stem: str,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    report_df = pd.DataFrame(rows)
    csv_path = output_dir / f"{stem}_event_report.csv"
    json_path = output_dir / f"{stem}_event_report.json"
    report_df.to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return {"csv": csv_path, "json": json_path}


def run_hybrid_pipeline(
    csv_path: str | Path,
    output_dir: str | Path | None = DEFAULT_OUTPUT_DIR,
    pre_event_seconds: float = 30.0,
    post_event_seconds: float = 30.0,
    confidence_threshold: float = 0.70,
) -> dict[str, Any]:
    csv_path = Path(csv_path)
    output_dir = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR
    image_dir = output_dir / "event_images"
    image_dir.mkdir(parents=True, exist_ok=True)

    raw_df = load_sleep_csv(csv_path)
    processed_df, preprocessing_meta = preprocess_signals(raw_df)
    candidates = detect_rule_candidates(processed_df)
    model, class_names, model_meta = load_cnn_model_bundle()

    report_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        image_path = image_dir / f"{candidate.event_id}.png"
        create_event_window_image(
            signal_df=processed_df,
            candidate=candidate,
            output_path=image_path,
            pre_event_seconds=pre_event_seconds,
            post_event_seconds=post_event_seconds,
        )
        cnn_prediction = predict_event_image(image_path=image_path, model=model, class_names=class_names)
        validation = validate_event_with_rules(
            candidate=candidate,
            cnn_prediction=cnn_prediction,
            confidence_threshold=confidence_threshold,
        )

        row = candidate.to_dict()
        row["image_path"] = str(image_path)
        row.update(validation)
        row["top_probabilities"] = cnn_prediction["top_probabilities"]
        report_rows.append(row)

    report_paths = generate_sleep_report(report_rows, output_dir=output_dir, stem=csv_path.stem.replace(" ", "_"))
    summary = {
        "source_csv": str(csv_path),
        "output_dir": str(output_dir),
        "candidate_count": len(candidates),
        "report_csv": str(report_paths["csv"]),
        "report_json": str(report_paths["json"]),
        "preprocessing": preprocessing_meta,
        "model_meta": model_meta,
    }
    (output_dir / f"{csv_path.stem.replace(' ', '_')}_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    return summary
