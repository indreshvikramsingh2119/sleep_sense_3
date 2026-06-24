#!/usr/bin/env python3

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from hybrid_pipeline_common import DEFAULT_SAMPLE_RATE_HZ, load_sleep_csv


SIGNAL_DISPLAY_ORDER = [
    ("body_position", "Body Position"),
    ("airflow", "Airflow"),
    ("snoring", "Snoring"),
    ("spo2", "SpO2"),
    ("pulse", "Pulse"),
    ("body_movement", "Body Movement"),
]

BASELINE_TARGET_OCCURRENCE = 500
BASELINE_OCCURRENCE_TOLERANCE = 50


def build_time_seconds(df: pd.DataFrame, sample_rate_hz: float) -> np.ndarray:
    return np.arange(len(df), dtype=float) / float(sample_rate_hz)


def baseline_from_occurrence_band(
    values: pd.Series | np.ndarray,
    target_occurrence: int = BASELINE_TARGET_OCCURRENCE,
    tolerance: int = BASELINE_OCCURRENCE_TOLERANCE,
) -> tuple[float | None, int]:
    numeric_values = pd.to_numeric(values, errors="coerce").dropna()
    if numeric_values.empty:
        return None, 0

    rounded = numeric_values.round(2)
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


def analyze_signal(signal_label: str, values: pd.Series, threshold: float) -> dict[str, float | int | str] | None:
    numeric_values = pd.to_numeric(values, errors="coerce").dropna()
    if numeric_values.empty:
        return None

    min_value = float(numeric_values.min())
    max_value = float(numeric_values.max())
    mean_value = float(numeric_values.mean())

    rounded_values = numeric_values.round(2)
    rounded_max = round(max_value, 2)
    max_occurrence = int((rounded_values == rounded_max).sum())
    threshold_occurrence = int((numeric_values >= threshold).sum())
    value_counts = rounded_values.value_counts().sort_index()

    occurrence_band_value, occurrence_band_count = baseline_from_occurrence_band(numeric_values)

    return {
        "signal": signal_label,
        "min": min_value,
        "max": max_value,
        "mean": mean_value,
        "max_occurrence": max_occurrence,
        "threshold_occurrence": threshold_occurrence,
        "occurrence_band_value": occurrence_band_value,
        "occurrence_band_count": occurrence_band_count,
        "total_samples": int(len(numeric_values)),
    }


def print_summary(
    csv_path: Path,
    total_rows: int,
    window_rows: int,
    sample_rate_hz: float,
    skip_minutes: float,
    analyze_minutes: float,
    threshold: float,
    results: list[dict[str, float | int | str]],
    generated_at: str,
) -> None:
    print("=" * 80)
    print("SLEEP SENSE PEAK RULE CHECK")
    print("=" * 80)
    print(f"Input CSV          : {csv_path}")
    print(f"Total rows         : {total_rows}")
    print(f"Sample rate        : {sample_rate_hz:.3f} Hz")
    print(f"Skipped data       : first {skip_minutes} minutes")
    print(f"Analyzed window    : next {analyze_minutes} minutes")
    print(f"Rows in window     : {window_rows}")
    print(f"Occurrence rule    : value >= {threshold}")
    print(f"Generated at       : {generated_at}")
    print("=" * 80)
    print()

    if not results:
        print("No valid signal values found in the selected window.")
        return

    for result in results:
        print(f"{result['signal']}")
        print(f"  Min value                : {result['min']:.2f}")
        print(f"  Max value                : {result['max']:.2f}")
        print(f"  Mean value               : {result['mean']:.2f}")
        print(f"  Max value occurrence     : {result['max_occurrence']}")
        print(f"  {threshold}+ occurrence        : {result['threshold_occurrence']}")
        if result["occurrence_band_value"] is not None:
            print(f"  Baseline (500 +/- 50)    : {result['occurrence_band_value']:.2f}")
            print(f"  Baseline occurrence      : {result['occurrence_band_count']}")
        else:
            print("  Baseline (500 +/- 50)    : not found")
            print("  Baseline occurrence      : 0")
        print(f"  Total valid samples      : {result['total_samples']}")
        print()


def build_summary_text(
    csv_path: Path,
    total_rows: int,
    window_rows: int,
    sample_rate_hz: float,
    skip_minutes: float,
    analyze_minutes: float,
    threshold: float,
    results: list[dict[str, float | int | str]],
    generated_at: str,
) -> str:
    lines = []
    lines.append("=" * 80)
    lines.append("SLEEP SENSE PEAK RULE CHECK")
    lines.append("=" * 80)
    lines.append(f"Input CSV          : {csv_path}")
    lines.append(f"Total rows         : {total_rows}")
    lines.append(f"Sample rate        : {sample_rate_hz:.3f} Hz")
    lines.append(f"Skipped data       : first {skip_minutes} minutes")
    lines.append(f"Analyzed window    : next {analyze_minutes} minutes")
    lines.append(f"Rows in window     : {window_rows}")
    lines.append(f"Occurrence rule    : value >= {threshold}")
    lines.append(f"Generated at       : {generated_at}")
    lines.append("=" * 80)
    lines.append("")

    if not results:
        lines.append("No valid signal values found in the selected window.")
        return "\n".join(lines)

    for result in results:
        lines.append(f"{result['signal']}")
        lines.append(f"  Min value                : {result['min']:.2f}")
        lines.append(f"  Max value                : {result['max']:.2f}")
        lines.append(f"  Mean value               : {result['mean']:.2f}")
        lines.append(f"  Max value occurrence     : {result['max_occurrence']}")
        lines.append(f"  {threshold}+ occurrence        : {result['threshold_occurrence']}")
        if result["occurrence_band_value"] is not None:
            lines.append(f"  Baseline (500 +/- 50)    : {result['occurrence_band_value']:.2f}")
            lines.append(f"  Baseline occurrence      : {result['occurrence_band_count']}")
        else:
            lines.append("  Baseline (500 +/- 50)    : not found")
            lines.append("  Baseline occurrence      : 0")
        lines.append(f"  Total valid samples      : {result['total_samples']}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Skip first 20 minutes, analyze next 45 minutes, and print peak rule stats."
    )
    parser.add_argument("--input", required=True, help="Input SleepSense CSV path")
    parser.add_argument(
        "--sample-rate",
        type=float,
        default=DEFAULT_SAMPLE_RATE_HZ,
        help="Fallback sample rate used only if timestamp/time_sec is unavailable.",
    )
    parser.add_argument(
        "--skip-minutes",
        type=float,
        default=20.0,
        help="Starting minutes to ignore before analysis.",
    )
    parser.add_argument(
        "--analyze-minutes",
        type=float,
        default=45.0,
        help="Minutes to analyze after the skip window.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=40.0,
        help="Count occurrences where value >= threshold.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional TXT output path. If omitted, a .txt file is created next to the input CSV.",
    )
    args = parser.parse_args()

    csv_path = Path(args.input)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    signal_df = load_sleep_csv(csv_path)
    generated_at = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    time_sec = build_time_seconds(signal_df, args.sample_rate)

    skip_sec = float(args.skip_minutes) * 60.0
    end_sec = skip_sec + float(args.analyze_minutes) * 60.0
    window_mask = (time_sec >= skip_sec) & (time_sec < end_sec)
    window_df = signal_df.loc[window_mask].copy()

    if window_df.empty:
        empty_text = "\n".join(
            [
                "=" * 80,
                "SLEEP SENSE PEAK RULE CHECK",
                "=" * 80,
                "Selected analysis window is empty.",
                f"Input CSV      : {csv_path}",
                f"Skip minutes   : {args.skip_minutes}",
                f"Analyze minutes: {args.analyze_minutes}",
                "Check whether the recording is long enough.",
            ]
        )
        print(empty_text)
        return

    results: list[dict[str, float | int | str]] = []
    for signal_key, signal_label in SIGNAL_DISPLAY_ORDER:
        if signal_key not in window_df.columns:
            continue
        result = analyze_signal(signal_label, window_df[signal_key], args.threshold)
        if result is not None:
            results.append(result)

    summary_text = build_summary_text(
        csv_path=csv_path,
        total_rows=len(signal_df),
        window_rows=len(window_df),
        sample_rate_hz=float(args.sample_rate),
        skip_minutes=float(args.skip_minutes),
        analyze_minutes=float(args.analyze_minutes),
        threshold=float(args.threshold),
        results=results,
        generated_at=generated_at,
    )
    print(summary_text)

    if args.output:
        output_path = Path(args.output)
    else:
        timestamp_suffix = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        output_name = f"{csv_path.stem}_peak_rule_report_{timestamp_suffix}.txt"
        output_path = csv_path.parent / output_name

    output_path.write_text(summary_text + "\n", encoding="utf-8")
    print(f"Saved TXT report   : {output_path}")


if __name__ == "__main__":
    main()
