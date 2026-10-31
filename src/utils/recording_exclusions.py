"""Shared handling for SpO2 sensor dropouts.

An SpO2 value of zero is a sensor-off/artifact sample. The sample remains in
the raw signal so it can be plotted, while its interval can be excluded from
analysis and marked on charts.
"""

from __future__ import annotations

from typing import Any, Iterable

import numpy as np

from .sample_rate import DEFAULT_SAMPLE_RATE_HZ


def exclusion_summary(
    time: Any,
    spo2: Any,
    sample_rate_hz: float = DEFAULT_SAMPLE_RATE_HZ,
) -> dict[str, Any]:
    """Return contiguous zero-SpO2 intervals and their durations."""
    timestamps = np.asarray(time if time is not None else [], dtype=float).reshape(-1)
    values = np.asarray(spo2 if spo2 is not None else [], dtype=float).reshape(-1)
    try:
        rate = float(sample_rate_hz)
    except (TypeError, ValueError) as exc:
        raise ValueError("sample_rate_hz must be positive and finite") from exc
    if not np.isfinite(rate) or rate <= 0:
        raise ValueError("sample_rate_hz must be positive and finite")

    count = min(timestamps.size, values.size)
    if count == 0:
        return {
            "excluded_segments": [],
            "recording_duration_sec": 0.0,
            "excluded_duration_sec": 0.0,
            "analyzed_duration_sec": 0.0,
        }

    timestamps = timestamps[:count]
    values = values[:count]
    if not np.all(np.isfinite(timestamps)) or np.any(np.diff(timestamps) <= 0):
        raise ValueError("time must contain finite, strictly increasing timestamps")

    deltas = np.diff(timestamps)
    period = float(np.median(deltas)) if deltas.size else 1.0 / rate
    edges = np.concatenate((timestamps, [timestamps[-1] + period]))
    zero = values == 0
    transitions = np.diff(np.r_[False, zero, False].astype(np.int8))

    segments = []
    starts = np.flatnonzero(transitions == 1)
    ends = np.flatnonzero(transitions == -1)
    for start, end in zip(starts, ends):
        start_sec = float(edges[start])
        end_sec = float(edges[end])
        segments.append({
            "start_sec": start_sec,
            "end_sec": end_sec,
            "duration_sec": end_sec - start_sec,
        })

    recording_duration = float(edges[-1] - edges[0])
    excluded_duration = float(sum(item["duration_sec"] for item in segments))
    return {
        "excluded_segments": segments,
        "recording_duration_sec": recording_duration,
        "excluded_duration_sec": excluded_duration,
        "analyzed_duration_sec": max(0.0, recording_duration - excluded_duration),
    }


def overlaps_exclusion(
    event: dict[str, Any],
    excluded_segments: Iterable[dict[str, Any]],
) -> bool:
    """Return whether an event has positive-duration overlap with an interval."""
    try:
        start = float(event.get("start_sec", event.get("start", 0.0)))
        end = float(event.get("end_sec", event.get("end", start)))
    except (TypeError, ValueError):
        return False
    if not np.isfinite(start) or not np.isfinite(end) or end <= start:
        return False
    return any(
        start < float(segment["end_sec"])
        and end > float(segment["start_sec"])
        for segment in excluded_segments
    )
