"""
Generate manual CSA, OSA, MSA, and HSA event images from real PSG data.

Images are saved directly into the AI dataset structure:
`ai_models/sleep_apnea/event_image_dataset/train|val/<CLASS>/`.
"""

from __future__ import annotations
import argparse
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt 
import numpy as np
import pandas as pd


FS = 10
PRE_SEC = 30
EVENT_SEC = 20
POST_SEC = 30
START_ROW = 1
SOURCE_CSV = Path("extracted_data/human.data.csv")    
DATASET_DIR = Path("ai_models/sleep_apnea/event_image_dataset")
DEFAULT_VAL_RATIO = 0.2
DEFAULT_SEED = 42

TOTAL_SEC = PRE_SEC + EVENT_SEC + POST_SEC
EVENT_START_SEC = PRE_SEC
EVENT_END_SEC = PRE_SEC + EVENT_SEC
SUPPORTED_EVENTS = ("CSA", "OSA", "MSA", "HSA")
SUPPORTED_PROFILES = ("realistic", "separable", "ultra_separable")
CLASS_STYLE_MAP = {
    "CSA": {"line": "#1d4ed8", "shade": "#bfdbfe", "accent": "#1e3a8a"},
    "HSA": {"line": "#059669", "shade": "#bbf7d0", "accent": "#065f46"},
    "OSA": {"line": "#dc2626", "shade": "#fecaca", "accent": "#7f1d1d"},
    "MSA": {"line": "#a16207", "shade": "#fde68a", "accent": "#78350f"},
}
DEFAULT_STYLE = {"line": "#0f172a", "shade": "#dbeafe", "accent": "#1f2937"}


def add_wave(signal: np.ndarray, amplitude: float, cycles: float, phase: float = 0.0) -> np.ndarray:
    """Add mild physiological-looking variation to avoid flat synthetic ramps."""
    x = np.linspace(0.0, 2.0 * np.pi * cycles, len(signal))
    return signal + amplitude * np.sin(x + phase)


def event_baseline(signal: np.ndarray, reference_len: int) -> float:
    return float(np.nanmedian(signal[:reference_len]))


def build_event_timing(sample_index: int, event_type: str, profile: str) -> tuple[int, int]:
    if profile == "ultra_separable":
        ultra_offsets = {"CSA": 0, "HSA": 4, "OSA": 8, "MSA": 12}
        ultra_durations = {"CSA": 20, "HSA": 20, "OSA": 20, "MSA": 20}
        return PRE_SEC + ultra_offsets[event_type], ultra_durations[event_type]

    if profile != "separable":
        return EVENT_START_SEC, EVENT_SEC

    start_offsets = {
        "CSA": [0, 1, 2, 0, 2, 1],
        "HSA": [5, 6, 5, 7, 6, 5],
        "OSA": [10, 11, 12, 10, 12, 11],
        "MSA": [15, 16, 15, 17, 16, 15],
    }
    durations = {
        "CSA": [18, 19, 20, 18, 20, 19],
        "HSA": [24, 25, 26, 24, 26, 25],
        "OSA": [30, 31, 32, 30, 32, 31],
        "MSA": [34, 33, 32, 34, 32, 33],
    }
    event_start_sec = PRE_SEC + start_offsets[event_type][sample_index % len(start_offsets[event_type])]
    event_duration_sec = durations[event_type][sample_index % len(durations[event_type])]
    return event_start_sec, event_duration_sec


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate manual apnea event images directly inside the AI dataset folders."
    )
    parser.add_argument(
        "--event-type",
        default="all",
        choices=["all", *SUPPORTED_EVENTS],
        help="Event type to generate. Default: all",
    )
    parser.add_argument(
        "--start-row",
        type=int,
        default=START_ROW,
        help="Row index in source CSV to use as the baseline segment.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="How many images to generate per event type. Default: 1",
    )
    parser.add_argument(
        "--row-step",
        type=int,
        default=TOTAL_SEC * FS,
        help="How many source rows to move forward for each generated sample.",
    )
    parser.add_argument(
        "--profile",
        default="separable",
        choices=SUPPORTED_PROFILES,
        help="Pattern profile. 'separable' gives cleaner class-separated training images.",
    )
    parser.add_argument(
        "--source-csv",
        type=Path,
        default=SOURCE_CSV,
        help="Source CSV to use as PSG baseline. Default: extracted_data/human.data.csv",
    )
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=DATASET_DIR,
        help="Dataset root where train/ and val/ folders will be written.",
    )
    parser.add_argument(
        "--split",
        default="auto",
        choices=("auto", "train", "val", "direct"),
        help="Write to train/, val/, or directly into class folders. Default: auto",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=DEFAULT_VAL_RATIO,
        help="Fraction of generated samples per class to place in val. Default: 0.2",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help="Random seed used to choose which generated samples go into val.",
    )
    parser.add_argument(
        "--class-signatures",
        action="store_true",
        help="Embed class-specific visual signatures in generated plots.",
    )
    return parser.parse_args()


def load_base_segment(start_row: int, source_csv: Path) -> tuple[np.ndarray, ...]:
    time_sec = np.arange(0, TOTAL_SEC, 1 / FS)
    timestamp_ms = (time_sec * 1000).astype(int)
    total_samples = len(time_sec)
    end_row = start_row + total_samples

    source_df = pd.read_csv(source_csv, header=None)
    segment = source_df.iloc[start_row:end_row].copy()

    if len(segment) < total_samples:
        raise ValueError(f"CSV me enough data nahi hai. Kam se kam {total_samples} usable rows chahiye.")

    body_position = segment[2].to_numpy(copy=True)
    pulse = pd.Series(segment[3].astype(float)).interpolate(limit_direction="both").to_numpy(copy=True)
    spo2 = pd.Series(segment[4].astype(float)).interpolate(limit_direction="both").to_numpy(copy=True)
    body_movement = pd.Series(segment[5].astype(float)).interpolate(limit_direction="both").to_numpy(copy=True)
    airflow = pd.Series(segment[6].astype(float)).interpolate(limit_direction="both").to_numpy(copy=True)
    snoring = pd.Series(segment[8].astype(float)).interpolate(limit_direction="both").to_numpy(copy=True)

    return time_sec, timestamp_ms, body_position, pulse, spo2, body_movement, airflow, snoring


def apply_csa_pattern(
    pulse: np.ndarray,
    spo2: np.ndarray,
    body_movement: np.ndarray,
    airflow: np.ndarray,
    snoring: np.ndarray,
    idx: np.ndarray,
    post_idx: np.ndarray,
    normal_pulse: float,
    normal_spo2: float,
    profile: str,
) -> None:
    k = np.linspace(0.0, 1.0, len(idx))
    r = np.linspace(0.0, 1.0, len(post_idx))
    airflow_base = event_baseline(airflow, PRE_SEC * FS)
    if profile == "ultra_separable":
        airflow[idx] = add_wave(np.full(len(idx), airflow_base * 0.015), 0.004 * airflow_base, 0.6)
        snoring[idx] = np.full(len(idx), 0.2)
        body_movement[idx] = np.full(len(idx), 0.2)
        spo2[idx] = add_wave(normal_spo2 - 7.5 * k, 0.04, 0.5)
        pulse[idx] = add_wave(normal_pulse + 3.5 * k, 0.05, 0.5)
    elif profile == "separable":
        airflow[idx] = add_wave(np.full(len(idx), airflow_base * 0.02), 0.005 * airflow_base, 0.7)
        snoring[idx] = np.full(len(idx), 0.2)
        body_movement[idx] = np.full(len(idx), 0.3)
        spo2[idx] = add_wave(normal_spo2 - 6.0 * k, 0.06, 0.8)
        pulse[idx] = add_wave(normal_pulse + 7.5 * k, 0.10, 0.9)
    else:
        airflow[idx] = airflow[idx] * 0.03
        snoring[idx] = np.minimum(snoring[idx], 2)
        body_movement[idx] = np.minimum(body_movement[idx], 1)
        spo2[idx] = add_wave(normal_spo2 - 5.5 * k, 0.20, 1.4)
        pulse[idx] = add_wave(normal_pulse + 10 * k, 0.35, 1.8)

    spo2_recovery = spo2[idx[-1]] + (normal_spo2 - spo2[idx[-1]]) * r
    pulse_recovery = pulse[idx[-1]] + (normal_pulse - pulse[idx[-1]]) * r
    spo2[post_idx] = add_wave(spo2_recovery, 0.12, 1.0, phase=np.pi / 8)
    pulse[post_idx] = add_wave(pulse_recovery, 0.25, 1.4, phase=np.pi / 6)


def apply_osa_pattern(
    pulse: np.ndarray,
    spo2: np.ndarray,
    body_movement: np.ndarray,
    airflow: np.ndarray,
    snoring: np.ndarray,
    idx: np.ndarray,
    post_idx: np.ndarray,
    normal_pulse: float,
    normal_spo2: float,
    profile: str,
) -> None:
    k = np.linspace(0.0, 1.0, len(idx))
    r = np.linspace(0.0, 1.0, len(post_idx))
    event_cycles = np.linspace(0.0, 5.0 * np.pi, len(idx))

    if profile == "ultra_separable":
        airflow_base = max(1.0, np.nanstd(airflow[: PRE_SEC * FS]))
        event_cycles = np.linspace(0.0, 8.0 * np.pi, len(idx))
        airflow[idx] = add_wave(
            np.full(len(idx), airflow_base) * (0.020 + 0.030 * (np.sin(event_cycles) ** 2)),
            0.012 * airflow_base,
            8.0,
        )
        snoring[idx] = 96 + 20 * np.abs(np.sin(event_cycles))
        body_movement[idx] = 72 + 18 * (np.sin(event_cycles * 0.8) ** 2)
        spo2[idx] = add_wave(normal_spo2 - 13.0 * k, 0.05, 0.8)
        pulse[idx] = add_wave(normal_pulse + 24.0 * k, 0.08, 0.8)
    elif profile == "separable":
        airflow_base = max(1.0, np.nanstd(airflow[: PRE_SEC * FS]))
        rebound_wave = np.clip(np.sin(event_cycles * 1.8), 0.0, None)
        terminal_arousal = (k > 0.65).astype(float)
        obstruction_envelope = 0.004 + 0.030 * (rebound_wave**2) + 0.020 * terminal_arousal
        airflow[idx] = add_wave(
            np.full(len(idx), airflow_base) * obstruction_envelope,
            0.010 * airflow_base,
            8.0,
        )
        snoring[idx] = (
            90
            + 22 * np.abs(np.sin(event_cycles))
            + 26 * (rebound_wave > 0.45)
            + 22 * terminal_arousal
        )
        body_movement[idx] = (
            38
            + 28 * (np.sin(event_cycles * 1.6) ** 4)
            + 38 * terminal_arousal
        )
        spo2[idx] = add_wave(normal_spo2 - 11.5 * k, 0.08, 1.0)
        pulse[idx] = add_wave(normal_pulse + 20.0 * k, 0.14, 1.2)
    else:
        collapse_envelope = 0.015 + 0.045 * (np.sin(event_cycles * 1.2) ** 2)
        airflow[idx] = np.abs(airflow[idx]) * collapse_envelope
        airflow[idx] = add_wave(airflow[idx], 0.015 * np.nanstd(airflow[: PRE_SEC * FS]), 5.5)
        snoring[idx] = np.clip(snoring[idx] + 78 + 22 * np.abs(np.sin(event_cycles)), 0, None)
        body_movement[idx] = np.clip(
            body_movement[idx] + 30 + 22 * (np.sin(event_cycles * 1.6) ** 4) + 18 * (k > 0.72),
            0,
            None,
        )
        spo2[idx] = add_wave(normal_spo2 - 10.5 * k, 0.28, 2.1)
        pulse[idx] = add_wave(normal_pulse + 22 * k, 0.48, 2.3)

    spo2_recovery = spo2[idx[-1]] + (normal_spo2 - spo2[idx[-1]]) * r
    pulse_recovery = pulse[idx[-1]] + (normal_pulse - pulse[idx[-1]]) * r
    spo2[post_idx] = add_wave(spo2_recovery, 0.20, 1.4, phase=np.pi / 7)
    pulse[post_idx] = add_wave(pulse_recovery, 0.45, 2.0, phase=np.pi / 5)


def apply_msa_pattern(
    pulse: np.ndarray,
    spo2: np.ndarray,
    body_movement: np.ndarray,
    airflow: np.ndarray,
    snoring: np.ndarray,
    idx: np.ndarray,
    post_idx: np.ndarray,
    normal_pulse: float,
    normal_spo2: float,
    profile: str,
) -> None:
    k = np.linspace(0.0, 1.0, len(idx))
    r = np.linspace(0.0, 1.0, len(post_idx))
    third = len(idx) // 3
    csa_idx = idx[:third]
    transition_idx = idx[third : 2 * third]
    osa_idx = idx[2 * third :]
    transition_k = np.linspace(0.0, 1.0, len(transition_idx))
    osa_cycles = np.linspace(0.0, 4.0 * np.pi, len(osa_idx))

    if profile == "ultra_separable":
        airflow_base = max(1.0, np.nanstd(airflow[: PRE_SEC * FS]))
        half = len(idx) // 2
        csa_idx = idx[:half]
        osa_idx = idx[half:]
        osa_cycles = np.linspace(0.0, 6.0 * np.pi, len(osa_idx))

        airflow[csa_idx] = add_wave(np.full(len(csa_idx), airflow_base * 0.012), 0.003 * airflow_base, 0.5)
        snoring[csa_idx] = np.full(len(csa_idx), 0.3)
        body_movement[csa_idx] = np.full(len(csa_idx), 0.3)

        airflow[osa_idx] = add_wave(
            np.full(len(osa_idx), airflow_base) * (0.080 + 0.050 * (np.sin(osa_cycles) ** 2)),
            0.018 * airflow_base,
            5.0,
        )
        snoring[osa_idx] = 62 + 14 * np.abs(np.sin(osa_cycles))
        body_movement[osa_idx] = 18 + 6 * (np.sin(osa_cycles / 2.0) ** 2)
        spo2[idx] = add_wave(normal_spo2 - 9.5 * k, 0.05, 0.8)
        pulse[idx] = add_wave(normal_pulse + 13.0 * k, 0.08, 0.8)
    elif profile == "separable":
        airflow_base = max(1.0, np.nanstd(airflow[: PRE_SEC * FS]))
        airflow[csa_idx] = add_wave(np.full(len(csa_idx), airflow_base * 0.02), 0.004 * airflow_base, 0.7)
        snoring[csa_idx] = np.full(len(csa_idx), 0.3)
        body_movement[csa_idx] = np.full(len(csa_idx), 0.3)

        airflow[transition_idx] = add_wave(
            np.full(len(transition_idx), airflow_base) * (0.08 + 0.10 * transition_k),
            0.05 * airflow_base,
            1.5,
            phase=np.pi / 4,
        )
        snoring[transition_idx] = 6 + 10 * transition_k
        body_movement[transition_idx] = 1 + 4 * transition_k

        airflow[osa_idx] = add_wave(
            np.full(len(osa_idx), airflow_base) * (0.10 + 0.18 * (np.sin(osa_cycles) ** 2)),
            0.08 * airflow_base,
            5.0,
        )
        snoring[osa_idx] = 28 + 18 * np.abs(np.sin(osa_cycles))
        body_movement[osa_idx] = 8 + 8 * (np.sin(osa_cycles / 2.0) ** 2)
        spo2[idx] = add_wave(normal_spo2 - 8.8 * k, 0.10, 1.2)
        pulse[idx] = add_wave(normal_pulse + 15.5 * k, 0.16, 1.3)
    else:
        airflow_base = max(1.0, np.nanstd(airflow[: PRE_SEC * FS]))
        central_cycles = np.linspace(0.0, 1.4 * np.pi, len(csa_idx))
        transition_cycles = np.linspace(0.0, 2.4 * np.pi, len(transition_idx))
        airflow[csa_idx] = add_wave(
            np.full(len(csa_idx), airflow_base * 0.010),
            0.002 * airflow_base,
            0.4,
        )
        airflow[csa_idx] += 0.004 * airflow_base * np.sin(central_cycles) ** 2
        snoring[csa_idx] = np.minimum(snoring[csa_idx], 1.5)
        body_movement[csa_idx] = np.minimum(body_movement[csa_idx], 0.8)

        airflow[transition_idx] = add_wave(
            np.full(len(transition_idx), airflow_base) * (0.05 + 0.28 * transition_k),
            0.04 * airflow_base,
            2.0,
            phase=np.pi / 5,
        )
        airflow[transition_idx] += 0.05 * airflow_base * np.abs(np.sin(transition_cycles))
        snoring[transition_idx] = np.clip(snoring[transition_idx] + 3 + 15 * transition_k, 0, None)
        body_movement[transition_idx] = np.clip(body_movement[transition_idx] + 1 + 7 * transition_k, 0, None)

        airflow[osa_idx] = add_wave(
            np.full(len(osa_idx), airflow_base) * (0.14 + 0.18 * (np.sin(osa_cycles) ** 2)),
            0.07 * airflow_base,
            4.4,
        )
        snoring[osa_idx] = np.clip(
            snoring[osa_idx] + 54 + 24 * np.abs(np.sin(osa_cycles)) + 8 * (k[2 * third :] > 0.85),
            0,
            None,
        )
        body_movement[osa_idx] = np.clip(
            body_movement[osa_idx] + 16 + 10 * np.sin(osa_cycles / 2.0) ** 2,
            0,
            None,
        )

        spo2[idx] = add_wave(normal_spo2 - 9.0 * k - 1.8 * (k > 0.55), 0.24, 1.5)
        pulse[idx] = add_wave(normal_pulse + 15.5 * k + 4.0 * (k > 0.6), 0.38, 1.8)

    spo2_recovery = spo2[idx[-1]] + (normal_spo2 - spo2[idx[-1]]) * r
    pulse_recovery = pulse[idx[-1]] + (normal_pulse - pulse[idx[-1]]) * r
    spo2[post_idx] = add_wave(spo2_recovery, 0.18, 1.3, phase=np.pi / 7)
    pulse[post_idx] = add_wave(pulse_recovery, 0.42, 1.8, phase=np.pi / 5)


def apply_hsa_pattern(
    pulse: np.ndarray,
    spo2: np.ndarray,
    body_movement: np.ndarray,
    airflow: np.ndarray,
    snoring: np.ndarray,
    idx: np.ndarray,
    post_idx: np.ndarray,
    normal_pulse: float,
    normal_spo2: float,
    profile: str,
) -> None:
    k = np.linspace(0.0, 1.0, len(idx))
    r = np.linspace(0.0, 1.0, len(post_idx))
    airflow_base = event_baseline(airflow, PRE_SEC * FS)

    if profile == "ultra_separable":
        airflow[idx] = add_wave(np.full(len(idx), airflow_base * 0.62), 0.025 * airflow_base, 1.0)
        snoring[idx] = 4 + 1.5 * np.sin(np.linspace(0.0, 2.0 * np.pi, len(idx)))
        body_movement[idx] = 1.0 + 0.4 * np.sin(np.linspace(0.0, 1.5 * np.pi, len(idx)))
        spo2[idx] = add_wave(normal_spo2 - 1.4 * k, 0.03, 0.5)
        pulse[idx] = add_wave(normal_pulse + 2.5 * k, 0.04, 0.5)
    elif profile == "separable":
        airflow[idx] = add_wave(np.full(len(idx), airflow_base * 0.68), 0.025 * airflow_base, 1.3)
        snoring[idx] = 4 + 2.0 * np.sin(np.linspace(0.0, 2.0 * np.pi, len(idx)))
        body_movement[idx] = 1.2 + 0.5 * np.sin(np.linspace(0.0, 1.5 * np.pi, len(idx)))
        spo2[idx] = add_wave(normal_spo2 - 1.6 * k, 0.05, 0.8)
        pulse[idx] = add_wave(normal_pulse + 3.0 * k, 0.08, 0.9)
    else:
        hypopnea_cycles = np.linspace(0.0, 4.2 * np.pi, len(idx))
        partial_obstruction = 0.48 + 0.11 * (np.sin(hypopnea_cycles) ** 2)
        airflow[idx] = add_wave(
            np.full(len(idx), airflow_base) * partial_obstruction,
            0.035 * max(1.0, airflow_base),
            1.7,
        )
        airflow[idx] += 0.02 * airflow_base * np.sin(hypopnea_cycles / 2.0)
        snoring[idx] = np.clip(
            snoring[idx] + 24 + 12 * np.abs(np.sin(hypopnea_cycles)) + 8 * (k > 0.55),
            0,
            None,
        )
        body_movement[idx] = np.clip(
            body_movement[idx] + 8 + 5 * (k > 0.68) + 2 * np.sin(hypopnea_cycles / 2.0) ** 2,
            0,
            None,
        )
        spo2[idx] = add_wave(normal_spo2 - 4.2 * k - 0.9 * (k > 0.72), 0.12, 0.9)
        pulse[idx] = add_wave(normal_pulse + 8.5 * k + 2.0 * (k > 0.7), 0.18, 1.0)

    spo2_recovery = spo2[idx[-1]] + (normal_spo2 - spo2[idx[-1]]) * r
    pulse_recovery = pulse[idx[-1]] + (normal_pulse - pulse[idx[-1]]) * r
    spo2[post_idx] = add_wave(spo2_recovery, 0.10, 1.0, phase=np.pi / 8)
    pulse[post_idx] = add_wave(pulse_recovery, 0.22, 1.3, phase=np.pi / 6)


EVENT_APPLIERS = {
    "CSA": apply_csa_pattern,
    "OSA": apply_osa_pattern,
    "MSA": apply_msa_pattern,
    "HSA": apply_hsa_pattern,
}


def build_manual_event(
    event_type: str,
    start_row: int,
    profile: str,
    event_start_sec: int,
    event_duration_sec: int,
    source_csv: Path,
) -> pd.DataFrame:
    time_sec, timestamp_ms, body_position, pulse, spo2, body_movement, airflow, snoring = load_base_segment(
        start_row,
        source_csv,
    )

    event_end_sec = event_start_sec + event_duration_sec
    event_mask = (time_sec >= event_start_sec) & (time_sec < event_end_sec)
    idx = np.where(event_mask)[0]
    post_idx = np.where(time_sec >= event_end_sec)[0]

    normal_spo2 = float(np.nanmean(spo2[: PRE_SEC * FS]))
    normal_pulse = float(np.nanmean(pulse[: PRE_SEC * FS]))

    EVENT_APPLIERS[event_type](
        pulse,
        spo2,
        body_movement,
        airflow,
        snoring,
        idx,
        post_idx,
        normal_pulse,
        normal_spo2,
        profile,
    )

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
    df.loc[event_mask, 10] = event_type
    return df


def plot_manual_event_for_dataset(
    df: pd.DataFrame,
    plot_path: Path,
    event_start_sec: int,
    event_duration_sec: int,
    use_class_signature: bool = True,
) -> None:
    labels = [str(value) for value in df[10].unique().tolist() if str(value) not in {"0", "0.0"}]
    event_type = labels[0] if labels else "CSA"
    style = CLASS_STYLE_MAP.get(event_type, CLASS_STYLE_MAP["CSA"]) if use_class_signature else DEFAULT_STYLE
    time_sec = df[1].to_numpy() / 1000.0
    relative_time = time_sec - time_sec[0]
    airflow = df[6].to_numpy()
    spo2 = df[4].to_numpy()
    pulse = df[3].to_numpy()
    body_movement = df[5].to_numpy()
    snoring = df[8].to_numpy()

    event_end_sec = event_start_sec + event_duration_sec
    fig, axes = plt.subplots(5, 1, figsize=(12, 8), sharex=True)
    fig.patch.set_facecolor(style["shade"])
    if use_class_signature:
        fig.add_artist(
            plt.Rectangle(
                (0.0, 0.955),
                1.0,
                0.045,
                transform=fig.transFigure,
                color=style["accent"],
                alpha=1.0,
                zorder=10,
            )
        )
        fig.text(
            0.5,
            0.977,
            f"{event_type} CLASS",
            ha="center",
            va="center",
            fontsize=22,
            fontweight="bold",
            color="white",
            zorder=11,
        )
        fig.text(
            0.985,
            0.08,
            event_type,
            ha="right",
            va="bottom",
            fontsize=34,
            fontweight="bold",
            color=style["accent"],
            alpha=0.28,
            zorder=1,
        )
    plots = [
        (airflow, "Airflow"),
        (spo2, "SpO2"),
        (pulse, "Pulse"),
        (body_movement, "Movement"),
        (snoring, "Snoring"),
    ]
    ylim_map = {
        "Airflow": (-5, 105),
        "SpO2": (70, 100),
        "Pulse": (40, 140),
        "Movement": (0, 100),
        "Snoring": (0, 100),
    }

    for axis, (signal, label) in zip(axes, plots):
        axis.set_facecolor("white")
        axis.plot(relative_time, signal, linewidth=2.0, color=style["line"])
        axis.set_ylabel(label, color=style["accent"], fontweight="bold")
        axis.set_ylim(*ylim_map[label])
        axis.axvspan(event_start_sec, event_end_sec, color=style["shade"], alpha=0.95)
        axis.axvline(event_start_sec, color=style["accent"], linewidth=2.2)
        axis.axvline(event_end_sec, color=style["accent"], linewidth=2.2)
        axis.grid(False)
        for spine in axis.spines.values():
            spine.set_linewidth(2.0)
            spine.set_color(style["accent"])

    axes[1].axhline(90, linestyle="--", color="gray", linewidth=1)
    axes[-1].set_xlabel("Time (seconds)", color=style["accent"], fontweight="bold")
    title = f"{event_type} event window" if use_class_signature else "Event window"
    fig.suptitle(title, fontsize=20, fontweight="bold", color=style["accent"])
    fig.tight_layout()
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(plot_path, dpi=220, facecolor="white")
    plt.close(fig)


def build_split_map(sample_count: int, val_ratio: float, seed: int) -> list[str]:
    if not 0.0 <= val_ratio < 1.0:
        raise ValueError("--val-ratio must be between 0.0 and 1.0.")

    split_map = ["train"] * sample_count
    if sample_count <= 1 or val_ratio == 0.0:
        return split_map

    val_count = int(round(sample_count * val_ratio))
    val_count = min(sample_count - 1, max(1, val_count))

    rng = np.random.default_rng(seed)
    val_indices = set(rng.choice(sample_count, size=val_count, replace=False).tolist())
    for index in val_indices:
        split_map[index] = "val"
    return split_map


def generate_event_outputs(
    event_type: str,
    start_row: int,
    timestamp: str,
    split: str,
    profile: str,
    dataset_dir: Path,
    sample_index: int,
    source_csv: Path,
    use_class_signature: bool = True,
) -> None:
    output_prefix = event_type.lower()       
    row_tag = f"row{start_row}"
    event_start_sec, event_duration_sec = build_event_timing(sample_index, event_type, profile)
    timing_tag = f"s{event_start_sec}_d{event_duration_sec}"

    df = build_manual_event(event_type, start_row, profile, event_start_sec, event_duration_sec, source_csv)
    if split == "direct":
        dataset_class_dir = dataset_dir / event_type
    else:
        dataset_class_dir = dataset_dir / split / event_type
    dataset_class_dir.mkdir(parents=True, exist_ok=True)
    dataset_plot_path = dataset_class_dir / f"manual_{output_prefix}_{row_tag}_{timing_tag}_{timestamp}.png"
    plot_manual_event_for_dataset(
        df,
        dataset_plot_path,
        event_start_sec,
        event_duration_sec,
        use_class_signature=use_class_signature,
    )
    print(f"[{event_type}] Saved dataset plot: {dataset_plot_path}")
    print(
        f"[{event_type}] Split={split} | Total samples: {len(df)} | "
        f"event_start={event_start_sec}s | event_duration={event_duration_sec}s"
    )



def main() -> None:
    args = parse_args()
    args.dataset_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.event_type == "all":
        event_types = SUPPORTED_EVENTS
    else:
        event_types = (args.event_type,)

    split_map = build_split_map(args.count, args.val_ratio, args.seed)
    for sample_index in range(args.count):
        sample_start_row = args.start_row + (sample_index * args.row_step)
        sample_timestamp = f"{timestamp}_{sample_index + 1:03d}"
        split = split_map[sample_index] if args.split == "auto" else args.split
        for event_type in event_types:
            generate_event_outputs(
                event_type,
                sample_start_row,
                sample_timestamp,
                split,
                args.profile,
                args.dataset_dir,
                sample_index,
                args.source_csv,
                use_class_signature=args.class_signatures,
            )

    print(f"Base event window: {EVENT_START_SEC}s to {EVENT_END_SEC}s ({EVENT_SEC} sec)")
    print(f"Source CSV: {args.source_csv}")
    print(f"Dataset directory: {args.dataset_dir}")
    print(f"Split assignment: {split_map}")
    print(
        f"Source segment rows: {args.start_row} to "
        f"{args.start_row + ((args.count - 1) * args.row_step) + int(TOTAL_SEC * FS) - 1}"
    )


if __name__ == "__main__":
    main()
 
