"""Shared sample-rate constants for PSG processing."""

from __future__ import annotations

# Rate of the old CSV/TXT exports (all channels).
LEGACY_CSV_SAMPLE_RATE_HZ = 10.2

# Native per-channel rates of the SD-card record format (Hz).
CHANNEL_SAMPLE_RATES: dict[str, float] = {
    "spo2": 1.0,
    "pulse": 1.0,
    "accel_x": 25.0,
    "accel_y": 25.0,
    "accel_z": 25.0,
    "body_movement": 25.0,
    "body_position": 25.0,
    "thorax": 25.0,
    "airflow": 125.0,
    "snoring": 125.0,
    "ecg": 125.0,
}

# Backwards-compatible single-rate constant (legacy CSV path).
DEFAULT_SAMPLE_RATE_HZ = LEGACY_CSV_SAMPLE_RATE_HZ
# Grid used by the apnea detector for SD recordings; display remains native-rate.
DETECTION_SAMPLE_RATE_HZ = 12.5


def channel_sample_rate(name: str, rates: dict[str, float] | None = None,
                        default: float = DEFAULT_SAMPLE_RATE_HZ) -> float:
    """Return the sample rate for ``name`` from ``rates`` (or the defaults)."""
    table = rates if rates is not None else CHANNEL_SAMPLE_RATES
    key = str(name).strip().lower().replace(" ", "_")
    try:
        return float(table.get(key, default))
    except (TypeError, ValueError):
        return float(default)
