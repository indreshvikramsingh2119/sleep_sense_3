"""
Generate a manual MSA event sample from real PSG data and plot the signals.

Output CSV layout is kept compatible with the existing project mapping:
df[1] -> timestamp
df[2] -> body_position
df[3] -> pulse
df[4] -> spo2
df[5] -> body_movement
df[6] -> airflow
df[8] -> snoring
"""

from pathlib import Path
from datetime import datetime 

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


FS = 10
PRE_SEC = 10
EVENT_SEC = 25
POST_SEC = 5
START_ROW = 3
SOURCE_CSV = Path("extracted_data/human.data.csv")


TOTAL_SEC = PRE_SEC + EVENT_SEC + POST_SEC
EVENT_START_SEC = PRE_SEC
EVENT_END_SEC = PRE_SEC + EVENT_SEC

OUTPUT_DIR = Path("extracted_data")
CSV_BASENAME = "manual_msa_10hz"
PLOT_BASENAME = "msa_event_image"


def add_wave(signal: np.ndarray, amplitude: float, cycles: float, phase: float = 0.0) -> np.ndarray:
    """Add slight physiological-looking variation to avoid flat synthetic ramps."""
    x = np.linspace(0.0, 2.0 * np.pi * cycles, len(signal))
    return signal + amplitude * np.sin(x + phase)


def build_manual_hsa_event() -> pd.DataFrame:
    """Create a real-data-backed MSA example using PSG baseline signals."""
    time_sec = np.arange(0, TOTAL_SEC, 1 / FS)
    timestamp_ms = (time_sec * 1000).astype(int)
    total_samples = len(time_sec)
    start_row = START_ROW
    end_row = start_row + total_samples

    source_df = pd.read_csv(SOURCE_CSV, header=None)
    segment = source_df.iloc[start_row:end_row].copy()

    if len(segment) < total_samples:
        raise ValueError("CSV me enough data nahi hai. Kam se kam 460 usable rows chahiye.")

    body_position = segment[2].to_numpy(copy=True)
    pulse = pd.Series(segment[3].astype(float)).interpolate(limit_direction="both").to_numpy()
    spo2 = pd.Series(segment[4].astype(float)).interpolate(limit_direction="both").to_numpy()
    body_movement = pd.Series(segment[5].astype(float)).interpolate(limit_direction="both").to_numpy()
    airflow = pd.Series(segment[6].astype(float)).interpolate(limit_direction="both").to_numpy()
    snoring = pd.Series(segment[8].astype(float)).interpolate(limit_direction="both").to_numpy()

    event_mask = (time_sec >= EVENT_START_SEC) & (time_sec < EVENT_END_SEC)
    idx = np.where(event_mask)[0]
    post_idx = np.where(time_sec >= EVENT_END_SEC)[0]
    k = np.linspace(0.0, 1.0, len(idx))
    r = np.linspace(0.0, 1.0, len(post_idx))

    normal_spo2 = float(np.nanmean(spo2[: PRE_SEC * FS]))
    normal_pulse = float(np.nanmean(pulse[: PRE_SEC * FS]))

    # MSA event: first half central apnea-like, second half obstructive apnea-like.
    half = len(idx) // 2
    csa_idx = idx[:half]
    osa_idx = idx[half:]

    airflow[csa_idx] = airflow[csa_idx] * 0.05
    snoring[csa_idx] = np.minimum(snoring[csa_idx], 2)
    body_movement[csa_idx] = np.minimum(body_movement[csa_idx], 1)

    airflow[osa_idx] = airflow[osa_idx] * 0.05
    snoring[osa_idx] = np.clip(snoring[osa_idx] + 25, 0, None)
    body_movement[osa_idx] = np.clip(body_movement[osa_idx] + 8, 0, None)

    spo2[idx] = add_wave(normal_spo2 - 7 * k, 0.25, 1.5)
    pulse[idx] = add_wave(normal_pulse + 15 * k, 0.50, 2.0)

    spo2_recovery = spo2[idx[-1]] + (normal_spo2 - spo2[idx[-1]]) * r
    pulse_recovery = pulse[idx[-1]] + (normal_pulse - pulse[idx[-1]]) * r
    spo2[post_idx] = add_wave(spo2_recovery, 0.15, 1.2, phase=np.pi / 7)
    pulse[post_idx] = add_wave(pulse_recovery, 0.35, 1.6, phase=np.pi / 5)

    # Keep the same 11-column shape as the extracted PSG CSV files.
    df = pd.DataFrame(
        {
            0: np.nan,
            1: timestamp_ms,
            2: body_position,
            3: pulse,
            4: spo2,
            5: body_movement,
            6: airflow,
            7: 1,
            8: snoring,
            9: 1,
            10: "0",
        }
    )
    df.loc[event_mask, 10] = "MSA"
    return df


def plot_manual_hsa_event(df: pd.DataFrame, plot_path: Path) -> None:
    """Plot generated signals and highlight the event duration."""
    time_sec = df[1].to_numpy() / 1000.0
    airflow = df[6].to_numpy()
    spo2 = df[4].to_numpy()
    pulse = df[3].to_numpy()
    body_movement = df[5].to_numpy()
    snoring = df[8].to_numpy()

    fig, axes = plt.subplots(5, 1, figsize=(18, 10), sharex=True)

    plots = [
        (airflow, "Airflow"),
        (spo2, "SpO2"),
        (pulse, "Pulse"),
        (body_movement, "Movement"),
        (snoring, "Snoring"),
    ]

    for axis, (signal, label) in zip(axes, plots):
        axis.plot(time_sec, signal, linewidth=0.8, color="black")
        axis.set_ylabel(label)
        axis.axvspan(EVENT_START_SEC, EVENT_END_SEC, color="red", alpha=0.15)
        axis.grid(True, alpha=0.25)

    axes[1].axhline(90, linestyle="--", color="gray", linewidth=1)
    axes[0].text(
        EVENT_START_SEC + 1,
        np.nanmax(airflow),
        "MSA",
        color="red",
        fontsize=12,
        fontweight="bold",
        va="top",
    )
    axes[-1].set_xlabel("Time (seconds)")

    fig.suptitle(f"MSA Event | {PRE_SEC} sec Normal + {EVENT_SEC} sec Event + {POST_SEC} sec Normal")
    fig.tight_layout()
    fig.savefig(plot_path, dpi=300)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = OUTPUT_DIR / f"{CSV_BASENAME}_{timestamp}.csv"
    plot_path = OUTPUT_DIR / f"{PLOT_BASENAME}_{timestamp}.png"
    latest_csv_path = OUTPUT_DIR / f"{CSV_BASENAME}.csv"
    latest_plot_path = OUTPUT_DIR / f"{PLOT_BASENAME}.png"

    df = build_manual_hsa_event()
    df.to_csv(csv_path, index=False, header=False)
    df.to_csv(latest_csv_path, index=False, header=False)
    plot_manual_hsa_event(df, plot_path)
    plot_manual_hsa_event(df, latest_plot_path)

    print(f"Saved CSV: {csv_path}")
    print(f"Saved plot: {plot_path}")
    print(f"Updated latest CSV: {latest_csv_path}")
    print(f"Updated latest plot: {latest_plot_path}")
    print(f"Total samples: {len(df)}")
    print(f"Event window: {EVENT_START_SEC}s to {EVENT_END_SEC}s ({EVENT_SEC} sec)")
    print(f"Source segment: {SOURCE_CSV} rows {START_ROW} to {START_ROW + len(df) - 1}")


if __name__ == "__main__":
    main()
