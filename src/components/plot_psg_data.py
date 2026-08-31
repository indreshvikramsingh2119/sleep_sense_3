"""Shared PSG signal mapping and a small inspection plot utility."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.utils.sample_rate import DEFAULT_SAMPLE_RATE_HZ as SAMPLE_RATE_HZ
TIMESTAMP_COLUMN = 0

# Canonical signal key -> raw CSV column index.
SIGNAL_COLUMNS = {
    "timestamp": 0,
    "body_position": 1,
    "pulse": 2,
    "spo2": 3,
    "body_movement": 4,
    "airflow": 5,
    "thorax": 6,
    "snoring": 7,
    "abdomen": 10,
}

CSV_SIGNAL_NAMES = tuple(name for name in SIGNAL_COLUMNS if name != "timestamp")
INTERPOLATED_SIGNAL_NAMES = CSV_SIGNAL_NAMES

# Dashboard chart label -> canonical signal key.
CHART_SIGNAL_MAPPING = {
    "Body Position": "body_position",
    "Airflow": "airflow",
    "Snoring": "snoring",
    "Thorax": "thorax",
    "Abdomen": "abdomen",
    "SpO2": "spo2",
    "Pulse": "pulse",
    "Body Movement": "body_movement",
}
CHART_ORDER = tuple(CHART_SIGNAL_MAPPING)

BODY_POSITION_TICKS = [
    (0, "S"),
    (1, "P"),
    (2, "L"),
    (3, "R"),
    (4, "U"),
]
BODY_POSITION_LABEL_TO_CODE = {
    "s": 0,
    "supine": 0,
    "p": 1,
    "prone": 1,
    "l": 2,
    "left": 2,
    "r": 3,
    "right": 3,
    "u": 4,
    "unknown": 4,
    "upright": 4,
}


def signal_key_for_chart(chart_name):
    """Return the canonical signal key for a chart label."""
    cleaned = str(chart_name).strip()
    if cleaned in CHART_SIGNAL_MAPPING:
        return CHART_SIGNAL_MAPPING[cleaned]
    return cleaned.lower().replace(" ", "_")


def csv_column_for(name):
    """Return the raw CSV column index for a signal key or chart label."""
    cleaned = str(name).strip()
    if cleaned in SIGNAL_COLUMNS:
        return SIGNAL_COLUMNS[cleaned]
    return SIGNAL_COLUMNS.get(signal_key_for_chart(cleaned))


def _auto_ylim(values, sample_rate_hz=SAMPLE_RATE_HZ):
    """Return a padded data-driven Y range or None for a constant signal."""
    series = np.asarray(values, dtype=float)
    settle = int(30.0 * sample_rate_hz)
    if len(series) > settle * 2:
        series = series[settle:]
    series = series[np.isfinite(series)]
    if len(series) == 0 or series.min() == series.max():
        return None
    low, high = np.percentile(series, [0.5, 99.5])
    if high <= low:
        low, high = float(series.min()), float(series.max())
    pad = max((high - low) * 0.15, 1.0)
    return low - pad, high + pad


def _load_csv(csv_path):
    """Load a PSG export and keep only numeric columns."""
    raw = pd.read_csv(csv_path, header=None)
    numeric = raw.apply(pd.to_numeric, errors="coerce")
    numeric = numeric.dropna(how="all").reset_index(drop=True)
    return numeric


def _plot_inspection_figure(df, out_path):
    time_seconds = np.arange(len(df), dtype=float) / SAMPLE_RATE_HZ
    chart_rows = [
        ("Body Position", "body_position", "blue"),
        ("Pulse", "pulse", "red"),
        ("SpO2", "spo2", "green"),
        ("Body Movement", "body_movement", "purple"),
        ("Airflow", "airflow", "orange"),
        ("Thorax", "thorax", "teal"),
        ("Snoring", "snoring", "brown"),
    ]

    plottable = []
    for chart_label, signal_key, color in chart_rows:
        column_index = csv_column_for(signal_key)
        if column_index is None or column_index >= df.shape[1]:
            continue
        plottable.append((chart_label, column_index, color))

    if not plottable:
        raise SystemExit("No mapped signal columns were found in this file.")

    fig, axes = plt.subplots(len(plottable), 1, figsize=(15, 2.0 * len(plottable)), sharex=True)
    axes = np.atleast_1d(axes)
    fig.suptitle("PSG Signal Data - Column Position Verification", fontsize=16)

    for axis, (chart_label, column_index, color) in zip(axes, plottable):
        values = df[column_index].to_numpy(dtype=float)
        axis.plot(time_seconds, values, color=color, linewidth=0.5)
        axis.set_ylabel(chart_label, fontsize=10)
        axis.grid(True, alpha=0.3)
        axis.set_title(f"{chart_label} (Column {column_index})", fontsize=9)

        limits = _auto_ylim(values)
        if limits is not None:
            axis.set_ylim(*limits)

    axes[-1].set_xlabel("Time (seconds)", fontsize=12)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150)


def main():
    parser = argparse.ArgumentParser(description="Plot PSG signals from an uploaded CSV/TXT file.")
    parser.add_argument("csv_path", help="Path to the PSG CSV/TXT file to inspect")
    parser.add_argument("--out", default="psg_signal_plot.png", help="Output PNG path")
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    df = _load_csv(csv_path)

    print(f"CSV shape: {df.shape}")
    print(f"First few rows:\n{df.head(10)}")
    print("\nColumn statistics:")
    for i in range(df.shape[1]):
        print(f"Column {i}: min={df[i].min()}, max={df[i].max()}, unique={df[i].nunique()}")

    _plot_inspection_figure(df, args.out)
    print(f"\nPlot saved to {args.out}")

    print("\n=== Signal Statistics ===")
    for chart_label, signal_key in CHART_SIGNAL_MAPPING.items():
        column_index = csv_column_for(signal_key)
        if column_index is None or column_index >= df.shape[1]:
            continue
        values = df[column_index].to_numpy(dtype=float)
        print(
            f"{chart_label}: min={values.min()}, max={values.max()}, unique={np.unique(values)}"
        )


if __name__ == "__main__":
    main()

