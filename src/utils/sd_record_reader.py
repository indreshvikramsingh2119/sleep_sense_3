"""Reader for the Sleep Monitor SD-card binary recording format (.smf).

* One fixed-size 712-byte record per second, written back-to-back.
* Record = 4-byte sync marker ``AA 55 3C 91`` + 706-byte payload + CRC16.
* CRC16-CCITT (poly 0x1021, init 0xFFFF) over the 706-byte payload only.
* All multi-byte fields little-endian.

Payload layout (offsets relative to payload start)::

    timestamp  uint32   1   0-3     ms since device boot
    spo2       uint8    1   4
    bpm        uint8    1   5
    accel_x    int16   25   6-55
    accel_y    int16   25   56-105
    accel_z    int16   25   106-155
    thorax     uint16  25   156-205  12-bit ADC
    airflow    uint16 125   206-455  12-bit ADC
    ecg        uint16 125   456-705  12-bit ADC (parsed, not used yet)

Every channel is kept at its native rate.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Record framing
# ---------------------------------------------------------------------------
SYNC_MARKER = b"\xAA\x55\x3C\x91"
SYNC_SIZE = 4
PAYLOAD_SIZE = 706
CRC_SIZE = 2
RECORD_SIZE = SYNC_SIZE + PAYLOAD_SIZE + CRC_SIZE  # 712
RECORD_SECONDS = 1.0

CRC16_POLY = 0x1021
CRC16_INIT = 0xFFFF

# Payload field layout: name -> (numpy dtype (little-endian), count, offset)
PAYLOAD_FIELDS: dict[str, tuple[str, int, int]] = {
    "timestamp": ("<u4", 1, 0),
    "spo2": ("u1", 1, 4),
    "bpm": ("u1", 1, 5),
    "accel_x": ("<i2", 25, 6),
    "accel_y": ("<i2", 25, 56),
    "accel_z": ("<i2", 25, 106),
    "thorax": ("<u2", 25, 156),
    "airflow": ("<u2", 125, 206),
    "ecg": ("<u2", 125, 456),
}

# Native per-channel sample rates (samples per one-second record).
SD_CHANNEL_RATES: dict[str, float] = {
    name: float(count) for name, (_dtype, count, _offset) in PAYLOAD_FIELDS.items()
    if name != "timestamp"
}

ADC_MAX = 4095  # 12-bit ADC stored in uint16

# ---------------------------------------------------------------------------
# Derived-channel constants
# ---------------------------------------------------------------------------
# Accelerometer scale (MPU-6050 default +/-2 g range): 16384 counts = 1 g.
ACCEL_COUNTS_PER_G = 16384.0
# Firmware axis-dominance threshold. CHANGE THIS ONE LINE to match
# ``#define TILT_THRESHOLD`` in the device firmware. Default = 0.5 g.
TILT_THRESHOLD = 8192

# Body-position codes (must match the firmware and plot_psg_data.py).
POS_SUPINE, POS_LEFT, POS_RIGHT, POS_PRONE, POS_UPRIGHT, POS_UNKNOWN = 0, 1, 2, 3, 4, 5

# Movement intensity: percent of 1 g change between adjacent accel vectors.
MOVEMENT_NOISE_FLOOR_PERCENT_G = 1.0

# Thorax (Effort) DISPLAY copy: the belt baseline drifts a few ADC counts over minutes
# (e.g. 2010 -> 1995) while the breathing swing is only ~10-40 counts.  While Play runs the
# chart keeps ONE fixed Y range, so that drift slides the trace under the bottom edge and only
# the tops of the breaths remain ("humps sitting on the axis").  The display copy therefore
# has its slow baseline removed (robust rolling median) and is re-centred on a constant level.
THORAX_BASELINE_REMOVE = True
THORAX_BASELINE_WINDOW_SEC = 30.0   # must be several breaths long; apnea flat spots stay visible

# Snoring is derived from the 125 Hz airflow waveform as bipolar vibration.
SNORE_BANDPASS_HZ = (15.0, 55.0)
SNORE_ENVELOPE_LOWPASS_HZ = 10.0
SNORE_NOISE_FLOOR_WINDOW_SEC = 300.0
SNORE_NOISE_FLOOR_K = 4.0
SNORE_MIN_EVENT_SEC = 0.3
SNORE_MERGE_GAP_SEC = 0.2
SNORE_EDGE_FADE_SEC = 0.05

# 255 = firmware "no reading". Recorded zero values are kept so the display
# layer can bridge short artifacts and show longer artifacts as a visible dip.
SPO2_INVALID_VALUES = (255,)
BPM_INVALID_VALUES = (0, 255)

# File extensions treated as SD-card binary recordings. Any other file whose
# first bytes contain the sync marker is also accepted (see is_sd_recording).
SD_RECORDING_EXTENSIONS = (".smf", ".bin", ".dat", ".sd", ".raw", ".psg")


# ---------------------------------------------------------------------------
# CRC16-CCITT
# ---------------------------------------------------------------------------
def _build_crc16_table(poly: int = CRC16_POLY) -> np.ndarray:
    table = np.zeros(256, dtype=np.uint16)
    for byte in range(256):
        crc = byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ poly) if (crc & 0x8000) else (crc << 1)
            crc &= 0xFFFF
        table[byte] = crc
    return table


_CRC16_TABLE = _build_crc16_table()


def crc16_ccitt(data: bytes | bytearray | memoryview | np.ndarray, init: int = CRC16_INIT) -> int:
    """CRC16-CCITT (poly 0x1021, init 0xFFFF, no reflection, no final xor)."""
    crc = init & 0xFFFF
    table = _CRC16_TABLE
    for byte in bytes(data):
        crc = ((crc << 8) & 0xFFFF) ^ int(table[((crc >> 8) ^ byte) & 0xFF])
    return crc


def _crc16_bulk(payloads: np.ndarray) -> np.ndarray:
    """Vectorised CRC16-CCITT over a (n_records, PAYLOAD_SIZE) uint8 array."""
    n = payloads.shape[0]
    crc = np.full(n, CRC16_INIT, dtype=np.uint16)
    table = _CRC16_TABLE
    for column in range(payloads.shape[1]):
        index = ((crc >> 8) ^ payloads[:, column]).astype(np.uint16) & 0xFF
        crc = ((crc << 8) & 0xFFFF) ^ table[index]
    return crc.astype(np.uint16)


# ---------------------------------------------------------------------------
# Record parsing
# ---------------------------------------------------------------------------
@dataclass
class SDRecording:
    """Parsed SD-card recording with every channel at its native rate."""

    signals: dict[str, np.ndarray] = field(default_factory=dict)
    times: dict[str, np.ndarray] = field(default_factory=dict)
    sample_rates: dict[str, float] = field(default_factory=dict)
    record_timestamps_ms: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int64))
    record_time_sec: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_sec(self) -> float:
        if self.record_time_sec.size == 0:
            return 0.0
        return float(self.record_time_sec[-1] + RECORD_SECONDS)


def is_sd_recording(path: str | Path, *, probe_bytes: int = RECORD_SIZE * 4) -> bool:
    """True when ``path`` looks like an SD-card binary recording."""
    path = Path(path)
    if not path.is_file():
        return False
    if path.suffix.lower() in (".csv", ".txt", ".tsv"):
        return False
    if path.suffix.lower() in SD_RECORDING_EXTENSIONS:
        return True
    try:
        with open(path, "rb") as handle:
            head = handle.read(probe_bytes)
    except OSError:
        return False
    return SYNC_MARKER in head


def _find_sync(buffer: np.ndarray, start: int) -> int | None:
    """Byte-by-byte search for the sync marker starting at ``start``."""
    if start >= buffer.size:
        return None
    view = buffer[start:].tobytes()
    index = view.find(SYNC_MARKER)
    return None if index < 0 else start + index


def _find_valid_records(buffer: np.ndarray, *, verify_crc: bool = True) -> tuple[np.ndarray, dict[str, int]]:
    """Return start offsets of every valid record in ``buffer`` (uint8 array).

    Normal operation reads records at fixed 712-byte offsets. When a record
    fails the sync or CRC check, it is discarded and the reader scans forward
    byte-by-byte for the next sync marker whose record also passes the CRC.

    The sync/CRC check of all records on the current 712-byte grid is done once
    and reused after every corrupt record that leaves the grid unchanged (the
    usual case), so a card with many bad records no longer re-checks the rest
    of the file once per bad record.
    """
    total = int(buffer.size)
    stats = {"records_valid": 0, "records_corrupt": 0, "bytes_skipped": 0, "resyncs": 0}
    offsets: list[np.ndarray] = []

    sync = np.frombuffer(SYNC_MARKER, dtype=np.uint8)
    raw_bytes = buffer.tobytes()

    def find_sync(start: int) -> int | None:
        if start >= total:
            return None
        index = raw_bytes.find(SYNC_MARKER, start)
        return None if index < 0 else index

    def record_ok(offset: int) -> bool:
        if offset + RECORD_SIZE > total:
            return False
        if not np.array_equal(buffer[offset:offset + SYNC_SIZE], sync):
            return False
        if not verify_crc:
            return True
        payload = buffer[offset + SYNC_SIZE:offset + SYNC_SIZE + PAYLOAD_SIZE]
        stored = int(buffer[offset + SYNC_SIZE + PAYLOAD_SIZE]) | (int(buffer[offset + SYNC_SIZE + PAYLOAD_SIZE + 1]) << 8)
        return crc16_ccitt(payload) == stored

    # Locate the first sync marker (tolerates an unexpected header / junk).
    first = find_sync(0)
    if first is None:
        return np.array([], dtype=np.int64), stats
    stats["bytes_skipped"] += first
    position = first

    while position + RECORD_SIZE <= total:
        # Check every record on the 712-byte grid that starts at ``position``.
        grid_start = position
        n_grid = (total - grid_start) // RECORD_SIZE
        block = buffer[grid_start:grid_start + n_grid * RECORD_SIZE].reshape(n_grid, RECORD_SIZE)
        ok = np.all(block[:, :SYNC_SIZE] == sync, axis=1)
        if verify_crc:
            stored = block[:, SYNC_SIZE + PAYLOAD_SIZE].astype(np.uint16) | (
                block[:, SYNC_SIZE + PAYLOAD_SIZE + 1].astype(np.uint16) << 8
            )
            ok &= _crc16_bulk(block[:, SYNC_SIZE:SYNC_SIZE + PAYLOAD_SIZE]) == stored
        bad = np.flatnonzero(~ok)

        index = 0
        regrid = False
        while not regrid:
            next_bad = int(np.searchsorted(bad, index))
            stop = int(bad[next_bad]) if next_bad < bad.size else n_grid
            if stop > index:
                offsets.append(grid_start + np.arange(index, stop, dtype=np.int64) * RECORD_SIZE)
                stats["records_valid"] += stop - index
            position = grid_start + stop * RECORD_SIZE
            if stop >= n_grid:
                break

            # Corrupt record: discard it and scan forward for the next sync+CRC.
            stats["records_corrupt"] += 1
            stats["resyncs"] += 1
            scan_from = position + 1
            found = None
            while True:
                candidate = find_sync(scan_from)
                if candidate is None:
                    break
                if record_ok(candidate):
                    found = candidate
                    break
                scan_from = candidate + 1
            if found is None:
                stats["bytes_skipped"] += total - position
                position = total
                break
            stats["bytes_skipped"] += found - position
            position = found
            if (found - grid_start) % RECORD_SIZE == 0:
                index = (found - grid_start) // RECORD_SIZE      # same grid: reuse the checks
            else:
                regrid = True                                    # shifted data: check the new grid

    if not offsets:
        return np.array([], dtype=np.int64), stats
    return np.concatenate(offsets).astype(np.int64), stats


def parse_records(buffer: bytes | np.ndarray, *, verify_crc: bool = True) -> tuple[dict[str, np.ndarray], dict[str, int]]:
    """Parse every valid record in ``buffer`` into per-field arrays.

    Returns ``(fields, stats)`` where ``fields[name]`` has shape
    ``(n_records,)`` for scalar fields and ``(n_records, count)`` for arrays.
    """
    data = np.frombuffer(bytes(buffer) if not isinstance(buffer, np.ndarray) else buffer.tobytes(), dtype=np.uint8)
    offsets, stats = _find_valid_records(data, verify_crc=verify_crc)
    n = int(offsets.size)
    fields: dict[str, np.ndarray] = {}
    if n == 0:
        for name, (dtype, count, _offset) in PAYLOAD_FIELDS.items():
            fields[name] = np.zeros((0,) if count == 1 else (0, count), dtype=np.dtype(dtype))
        return fields, stats

    payload_starts = offsets + SYNC_SIZE
    payloads = data[(payload_starts[:, None] + np.arange(PAYLOAD_SIZE)[None, :])]
    for name, (dtype, count, offset) in PAYLOAD_FIELDS.items():
        width = np.dtype(dtype).itemsize * count
        raw = np.ascontiguousarray(payloads[:, offset:offset + width])
        values = raw.view(np.dtype(dtype)).reshape(n, count)
        fields[name] = values[:, 0].copy() if count == 1 else values.copy()
    return fields, stats


# ---------------------------------------------------------------------------
# Derived channels
# ---------------------------------------------------------------------------
def remove_slow_baseline(values, rate, window_sec: float = THORAX_BASELINE_WINDOW_SEC):
    """Remove slow baseline drift from a waveform (display use) and keep its overall level.

    1 s block medians -> rolling median over ``window_sec`` -> light smoothing -> interpolated
    back to every sample.  ``out = y - baseline + median(baseline)``, so the absolute level
    (e.g. ~2000 ADC counts) is unchanged, only the slow wander is gone.  Breathing (~0.2-0.5 Hz)
    and apnea flat segments are preserved.  NaN samples stay NaN.  Returns ``None`` when the
    input is too short, so the caller can keep the original signal.
    """
    from scipy.ndimage import median_filter, uniform_filter1d

    y = np.asarray(values, dtype=float).reshape(-1)
    rate = float(rate)
    block = max(1, int(round(rate)))              # samples per 1 s block
    n_blocks = y.size // block
    if rate <= 0 or n_blocks < 8:
        return None
    finite = np.isfinite(y)
    if not finite.any():
        return None

    blocks = np.where(finite, y, np.nan)[: n_blocks * block].reshape(n_blocks, block)
    with np.errstate(all="ignore"):
        med = np.nanmedian(blocks, axis=1)
    ok = np.isfinite(med)
    if ok.sum() < 8:
        return None
    centres = (np.arange(n_blocks) + 0.5) * block
    med = np.interp(np.arange(n_blocks), np.flatnonzero(ok), med[ok])   # fill all-NaN seconds

    win = max(3, int(round(window_sec)) | 1)                            # odd, in blocks (1 s each)
    base = median_filter(med, size=win, mode="nearest")
    base = uniform_filter1d(base, size=max(3, win // 2) | 1, mode="nearest")
    baseline = np.interp(np.arange(y.size) + 0.5, centres, base)        # flat-extrapolates edges

    out = y - baseline + float(np.median(base))
    out[~finite] = np.nan
    return out


def derive_body_position(ax: np.ndarray, ay: np.ndarray, az: np.ndarray,
                         tilt_threshold: int | float = TILT_THRESHOLD) -> np.ndarray:
    """Vectorised port of the firmware axis-dominance body-position logic.

    Firmware::

        if (abs_z >= abs_x && abs_z >= abs_y && abs_z > TILT) return az > 0 ? PRONE : SUPINE;
        if (abs_x >= abs_y && abs_x > TILT)                    return UPRIGHT;
        if (abs_y > TILT)                                      return ay > 0 ? RIGHT : LEFT;
        return UNKNOWN;
    """
    ax = np.asarray(ax, dtype=float).ravel()
    ay = np.asarray(ay, dtype=float).ravel()
    az = np.asarray(az, dtype=float).ravel()
    abs_x, abs_y, abs_z = np.abs(ax), np.abs(ay), np.abs(az)
    thr = float(tilt_threshold)

    position = np.full(ax.shape, POS_UNKNOWN, dtype=float)
    z_dom = (abs_z >= abs_x) & (abs_z >= abs_y) & (abs_z > thr)
    x_dom = ~z_dom & (abs_x >= abs_y) & (abs_x > thr)
    y_dom = ~z_dom & ~x_dom & (abs_y > thr)

    position[z_dom] = np.where(az[z_dom] > 0, POS_PRONE, POS_SUPINE)
    position[x_dom] = POS_UPRIGHT
    position[y_dom] = np.where(ay[y_dom] > 0, POS_RIGHT, POS_LEFT)
    position[~(np.isfinite(ax) & np.isfinite(ay) & np.isfinite(az))] = np.nan
    return position


def derive_body_movement(ax: np.ndarray, ay: np.ndarray, az: np.ndarray) -> np.ndarray:
    """Movement intensity (percent of 1 g) from adjacent accel-vector changes.

    Same maths as the legacy CSV ``X|Y|Z`` parser so the dashboard scale
    (0-100) does not change between data sources.
    """
    xyz = np.column_stack([
        np.asarray(ax, dtype=float).ravel(),
        np.asarray(ay, dtype=float).ravel(),
        np.asarray(az, dtype=float).ravel(),
    ])
    n = xyz.shape[0]
    movement = np.full(n, np.nan, dtype=float)
    if n == 0:
        return movement
    valid = np.isfinite(xyz).all(axis=1)
    zero_vector = valid & np.all(xyz == 0.0, axis=1)
    movement[valid] = 0.0
    if n > 1:
        adjacent_valid = valid[1:] & valid[:-1] & ~zero_vector[1:] & ~zero_vector[:-1]
        changes = np.linalg.norm(xyz[1:] - xyz[:-1], axis=1)
        intensity = changes / ACCEL_COUNTS_PER_G * 100.0
        intensity[intensity < MOVEMENT_NOISE_FLOOR_PERCENT_G] = 0.0
        indices = np.flatnonzero(adjacent_valid) + 1
        movement[indices] = np.clip(intensity[adjacent_valid], 0.0, 100.0)
    return movement


def _snore_packet_ranges(active: np.ndarray, fs: float) -> list[tuple[int, int]]:
    """Merge nearby threshold crossings and drop bursts shorter than 0.3 s."""
    active = np.asarray(active, dtype=bool)
    if active.size == 0:
        return []
    edges = np.diff(np.r_[False, active, False].astype(np.int8))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1)
    merge_gap = max(1, int(round(SNORE_MERGE_GAP_SEC * fs)))
    minimum = max(1, int(round(SNORE_MIN_EVENT_SEC * fs)))
    merged: list[list[int]] = []
    for start, end in zip(starts, ends):
        if merged and int(start) - merged[-1][1] <= merge_gap:
            merged[-1][1] = int(end)
        else:
            merged.append([int(start), int(end)])
    return [(a, b) for a, b in merged if b - a >= minimum]


def _trailing_median(values, window) -> np.ndarray:
    """Same numbers as ``pd.Series(values).rolling(window, min_periods=1).median()`` for NaN-free input.

    pandas keeps a skip list per window; scipy's 1-D rank filter does the same job about 3-4x faster.
    The first ``window - 1`` samples (growing window) are done with a sorted list so the result is
    identical, not just close.  Input with NaN goes through pandas as before.
    """
    import bisect
    import pandas as pd
    from scipy.ndimage import rank_filter

    x = np.asarray(values, dtype=float).reshape(-1)
    n = x.size
    w = int(window)
    if n == 0 or w <= 1 or not np.isfinite(x).all():
        return pd.Series(x).rolling(max(1, w), min_periods=1).median().to_numpy(dtype=float)
    out = np.empty(n, dtype=float)
    head = min(w - 1, n)
    ordered: list[float] = []
    for i in range(head):                       # growing window x[:i+1]
        bisect.insort(ordered, float(x[i]))
        m = len(ordered)
        out[i] = ordered[m // 2] if m % 2 else 0.5 * (ordered[m // 2 - 1] + ordered[m // 2])
    if n >= w:                                  # full windows x[i-w+1:i+1]
        origin = (w - 1) // 2                   # positive origin shifts the window left, ending at i
        lower = rank_filter(x, (w - 1) // 2, size=w, origin=origin, mode="nearest")
        upper = lower if w % 2 else rank_filter(x, w // 2, size=w, origin=origin, mode="nearest")
        out[w - 1:] = (0.5 * (lower + upper))[w - 1:]
    return out


def derive_snoring_from_airflow(airflow, fs) -> np.ndarray:
    """Snoring as bipolar vibration packets (around 0) at the airflow's rate.

    A smoothed absolute envelope of the 15-55 Hz band decides WHERE a snore
    packet exists (adaptive noise floor). Inside each accepted packet the
    real band-passed airflow disturbance is returned; elsewhere exactly 0.
    Requires fs >= ~110 Hz to resolve the band (the 125 Hz SD airflow is fine).
    """
    from scipy.signal import butter, sosfiltfilt

    raw = np.asarray(airflow, dtype=float).reshape(-1)
    fs = float(fs)
    if raw.size < 10 or fs <= 0:
        return np.zeros_like(raw)

    finite = np.isfinite(raw)
    if not finite.any():
        return np.zeros_like(raw)
    indices = np.arange(raw.size)
    continuous = np.interp(indices, indices[finite], raw[finite]) if not finite.all() else raw

    nyquist = fs / 2.0
    high = min(SNORE_BANDPASS_HZ[1], nyquist * 0.9)
    low = min(SNORE_BANDPASS_HZ[0], high * 0.5)
    if high <= low:
        return np.zeros_like(raw)

    bandpass_sos = butter(4, [low, high], btype="bandpass", fs=fs, output="sos")
    envelope_sos = butter(4, min(SNORE_ENVELOPE_LOWPASS_HZ, nyquist * 0.9),
                          btype="lowpass", fs=fs, output="sos")
    try:
        vibration = sosfiltfilt(bandpass_sos, continuous - float(np.mean(continuous)))
        envelope = np.maximum(sosfiltfilt(envelope_sos, np.abs(vibration)), 0.0)
    except ValueError:
        return np.zeros_like(raw)

    # Adaptive threshold, vectorised over the 10 Hz history grid.
    hist_step = max(1, int(round(fs / 10.0)))
    n_hist = int(np.ceil(envelope.size / hist_step))
    padded = np.pad(envelope, (0, n_hist * hist_step - envelope.size), constant_values=np.nan)
    hist_values = np.nanmean(padded.reshape(n_hist, hist_step), axis=1)
    hist_window = max(1, int(round(SNORE_NOISE_FLOOR_WINDOW_SEC * 10.0)))
    median = _trailing_median(hist_values, hist_window)
    mad = _trailing_median(np.abs(hist_values - median), hist_window) + 1e-9
    threshold_hist = ((median + 1.4826 * mad) * SNORE_NOISE_FLOOR_K).astype(float)
    chunk = max(1, int(round(fs)))
    n_chunks = int(np.ceil(envelope.size / chunk))
    chunk_end_hist = np.minimum(
        np.ceil((np.arange(n_chunks) + 1) * chunk / hist_step).astype(int), n_hist
    ) - 1
    threshold_per_chunk = threshold_hist[np.maximum(chunk_end_hist, 0)]
    threshold = np.repeat(threshold_per_chunk, chunk)[:envelope.size]
    active = envelope > threshold

    output = np.zeros_like(continuous)
    fade_len = max(1, int(round(SNORE_EDGE_FADE_SEC * fs)))
    for start, end in _snore_packet_ranges(active, fs):
        packet = vibration[start:end].copy()
        fade = min(fade_len, len(packet) // 2)
        if fade:
            ramp = np.linspace(0.0, 1.0, fade, endpoint=False)
            packet[:fade] *= ramp
            packet[-fade:] *= ramp[::-1]
        output[start:end] = packet
    output[~finite] = 0.0
    return output


# Backwards-compatible name.
derive_snoring = derive_snoring_from_airflow

# ---------------------------------------------------------------------------
# Breath phase of every snore packet (INHALE / EXHALE)
# ---------------------------------------------------------------------------
# Most snoring happens while breathing IN, so a packet is treated as an INHALE
# snore by default. A packet that falls in the EXHALE half of the breath is
# only shown as an EXHALE snore when it keeps happening (several exhale
# packets in a row, and they are the majority nearby); a lone exhale packet is
# kept but flagged "isolated" for review, because a single vibration on the way
# out is more often the cannula moving or mouth-breathing than real snoring.
# This hardware/export presents inspiration as the upward airflow excursion.
# Keep False so phase classification and FL detection use the recorded polarity.
INSPIRATION_IS_LOW_AIRFLOW = True
PHASE_LOWPASS_HZ = 1.0
PHASE_BASELINE_WINDOW_SEC = 30.0
PHASE_AMPLITUDE_WINDOW_SEC = 10.0
PHASE_MIN_AMPLITUDE = 20.0
EXHALE_CONTINUOUS_WINDOW_SEC = 60.0
EXHALE_CONTINUOUS_MIN_PACKETS = 3
EXHALE_CONTINUOUS_MIN_SHARE = 0.5

PHASE_INHALE = 1
PHASE_EXHALE = 2
PHASE_EXHALE_ISOLATED = 3
PHASE_UNKNOWN = 4
PHASE_NAMES = {
    PHASE_INHALE: "INHALE",
    PHASE_EXHALE: "EXHALE",
    PHASE_EXHALE_ISOLATED: "EXHALE (isolated)",
    PHASE_UNKNOWN: "UNKNOWN",
}
PACKET_COLUMNS = ("start_idx", "end_idx", "phase", "inspiration_fraction",
                  "peak", "start_sec", "end_sec")


def snore_packets_from_signal(snoring, fs) -> list[tuple[int, int]]:
    """Return ``(start, end-exclusive)`` ranges for derived snore packets."""
    active = np.asarray(snoring, dtype=float).reshape(-1) != 0.0
    if not active.any():
        return []
    gap = max(1, int(round(0.05 * float(fs))))
    edges = np.diff(np.r_[False, active, False].astype(np.int8))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1)
    merged: list[list[int]] = []
    for start, end in zip(starts, ends):
        if merged and int(start) - merged[-1][1] <= gap:
            merged[-1][1] = int(end)
        else:
            merged.append([int(start), int(end)])
    return [(a, b) for a, b in merged]


def breath_inspiration_mask(airflow, fs):
    """Return inspiration flag, validity mask, and the reduced sample rate."""
    import pandas as pd
    from scipy.signal import butter, decimate, sosfiltfilt

    x = np.asarray(airflow, dtype=float).reshape(-1)
    fs = float(fs)
    finite = np.isfinite(x)
    if x.size < 64 or not finite.any():
        return np.zeros(0, dtype=bool), np.zeros(0, dtype=bool), fs
    if not finite.all():
        x = np.interp(np.arange(x.size), np.flatnonzero(finite), x[finite])
    q = max(1, int(round(fs / 10.0)))
    x10 = decimate(x, q, ftype="fir", zero_phase=True) if q > 1 else x.copy()
    fs10 = fs / q
    sos = butter(4, min(PHASE_LOWPASS_HZ, fs10 * 0.4), btype="low", fs=fs10, output="sos")
    slow = pd.Series(sosfiltfilt(sos, x10))
    baseline = slow.rolling(
        max(3, int(round(PHASE_BASELINE_WINDOW_SEC * fs10))),
        center=True,
        min_periods=1,
    ).median().to_numpy()
    amp_window = max(3, int(round(PHASE_AMPLITUDE_WINDOW_SEC * fs10)))
    amplitude = (slow.rolling(amp_window, center=True, min_periods=1).max()
                 - slow.rolling(amp_window, center=True, min_periods=1).min()).to_numpy()
    slow = slow.to_numpy()
    inspiration = (slow < baseline) if INSPIRATION_IS_LOW_AIRFLOW else (slow > baseline)
    return inspiration, amplitude >= PHASE_MIN_AMPLITUDE, fs10


def snore_packet_table(airflow, snoring, time_sec, fs) -> np.ndarray:
    """Return one row per snore packet with breath phase and timing metadata."""
    packets = snore_packets_from_signal(snoring, fs)
    if not packets:
        return np.zeros((0, len(PACKET_COLUMNS)), dtype=float)
    inspiration, valid, fs10 = breath_inspiration_mask(airflow, fs)
    step = float(fs) / fs10 if fs10 > 0 else 1.0
    snoring = np.asarray(snoring, dtype=float).reshape(-1)
    time_sec = np.asarray(time_sec, dtype=float).reshape(-1)

    rows = []
    for a, b in packets:
        phase, fraction = PHASE_UNKNOWN, np.nan
        if inspiration.size:
            i0 = min(int(a / step), inspiration.size - 1)
            i1 = min(max(i0 + 1, int(np.ceil(b / step))), inspiration.size)
            ok = valid[i0:i1]
            if ok.any():
                fraction = float(np.mean(inspiration[i0:i1][ok]))
                phase = PHASE_INHALE if fraction >= 0.5 else PHASE_EXHALE
        peak = float(np.max(np.abs(snoring[a:b]))) if b > a else 0.0
        start_sec = float(time_sec[min(a, time_sec.size - 1)]) if time_sec.size else a / float(fs)
        end_sec = float(time_sec[min(b - 1, time_sec.size - 1)]) if time_sec.size else b / float(fs)
        rows.append([a, b, phase, fraction, peak, start_sec, end_sec])
    table = np.asarray(rows, dtype=float)

    centers = (table[:, 5] + table[:, 6]) / 2.0
    order = np.argsort(centers, kind="stable")
    c_sorted = centers[order]
    p_sorted = table[order, 2]
    is_exhale = np.r_[0, np.cumsum(p_sorted == PHASE_EXHALE)]
    is_known = np.r_[0, np.cumsum((p_sorted == PHASE_EXHALE) | (p_sorted == PHASE_INHALE))]
    lo = np.searchsorted(c_sorted, c_sorted - EXHALE_CONTINUOUS_WINDOW_SEC, side="left")
    hi = np.searchsorted(c_sorted, c_sorted + EXHALE_CONTINUOUS_WINDOW_SEC, side="right")
    n_exhale = is_exhale[hi] - is_exhale[lo]
    n_known = np.maximum(is_known[hi] - is_known[lo], 1)
    isolated_sorted = (p_sorted == PHASE_EXHALE) & (
        (n_exhale < EXHALE_CONTINUOUS_MIN_PACKETS)
        | ((n_exhale / n_known) < EXHALE_CONTINUOUS_MIN_SHARE)
    )
    isolated = np.zeros(table.shape[0], dtype=bool)
    isolated[order] = isolated_sorted
    table[isolated, 2] = PHASE_EXHALE_ISOLATED
    return table


def snore_phase_counts(table) -> dict:
    """Packet counts grouped by breath phase."""
    table = np.asarray(table, dtype=float)
    counts = {name: 0 for name in PHASE_NAMES.values()}
    if table.ndim == 2 and table.shape[0]:
        for code, name in PHASE_NAMES.items():
            counts[name] = int(np.sum(table[:, 2] == code))
    return counts


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------
def _expand_scalar(values: np.ndarray, invalid: tuple[int, ...]) -> np.ndarray:
    out = np.asarray(values, dtype=float)
    for sentinel in invalid:
        out = np.where(out == sentinel, np.nan, out)
    return out


def read_sd_recording(path: str | Path, *, verify_crc: bool = True,
                      tilt_threshold: int | float = TILT_THRESHOLD,
                      derive: bool = True) -> SDRecording:
    """Read an SD-card recording and return every channel at its native rate.

    ``times[channel]`` is elapsed seconds from the first valid record, built
    from the per-record device timestamps, so a discarded (corrupt) or missing
    second shows up as a real gap in time rather than shifting later data.
    """
    path = Path(path)
    with open(path, "rb") as handle:
        buffer = np.frombuffer(handle.read(), dtype=np.uint8)

    fields, stats = parse_records(buffer, verify_crc=verify_crc)
    n = int(fields["timestamp"].size)
    recording = SDRecording()
    recording.meta = {
        "source_path": str(path),
        "file_bytes": int(buffer.size),
        "record_size": RECORD_SIZE,
        "records_expected": int(buffer.size // RECORD_SIZE),
        "tilt_threshold": float(tilt_threshold),
        **stats,
    }
    if n == 0:
        return recording

    # ---- per-record time base (from device timestamps) --------------------
    timestamps_ms = fields["timestamp"].astype(np.int64)
    # Handle uint32 wrap-around (~49.7 days) and any backwards jumps (device
    # reboot): fall back to record counting from that point.
    rel_ms = timestamps_ms - timestamps_ms[0]
    deltas = np.diff(rel_ms)
    bad = (deltas <= 0) | (deltas > 60_000)
    if bad.any():
        deltas = deltas.astype(float)
        deltas[bad] = 1000.0
        rel_ms = np.concatenate([[0.0], np.cumsum(deltas)])
    record_time_sec = rel_ms.astype(float) / 1000.0
    recording.record_timestamps_ms = timestamps_ms
    recording.record_time_sec = record_time_sec

    # ---- channels at native rate -----------------------------------------
    def block_time(count: int) -> np.ndarray:
        # Sample k of a record sits at record_start + k / count seconds.
        return (record_time_sec[:, None] + (np.arange(count) / float(count))[None, :]).ravel()

    signals: dict[str, np.ndarray] = {}
    times: dict[str, np.ndarray] = {}
    rates: dict[str, float] = {}

    signals["spo2"] = _expand_scalar(fields["spo2"], SPO2_INVALID_VALUES)
    signals["pulse"] = _expand_scalar(fields["bpm"], BPM_INVALID_VALUES)
    for name in ("spo2", "pulse"):
        times[name] = record_time_sec.copy()
        rates[name] = 1.0

    for name in ("accel_x", "accel_y", "accel_z", "thorax", "airflow", "ecg"):
        _dtype, count, _offset = PAYLOAD_FIELDS[name]
        signals[name] = fields[name].astype(float).ravel()
        times[name] = block_time(count)
        rates[name] = float(count)

    if derive:
        signals["body_position"] = derive_body_position(
            signals["accel_x"], signals["accel_y"], signals["accel_z"], tilt_threshold)
        times["body_position"] = times["accel_x"].copy()
        rates["body_position"] = rates["accel_x"]

        signals["body_movement"] = derive_body_movement(
            signals["accel_x"], signals["accel_y"], signals["accel_z"])
        times["body_movement"] = times["accel_x"].copy()
        rates["body_movement"] = rates["accel_x"]

        signals["snoring"] = derive_snoring_from_airflow(signals["airflow"], rates["airflow"])
        times["snoring"] = times["airflow"].copy()
        rates["snoring"] = rates["airflow"]

        # Breath phase (inhale / exhale) of every snore packet. Never allowed
        # to stop a recording from loading.
        try:
            table = snore_packet_table(
                signals["airflow"], signals["snoring"], times["airflow"], rates["airflow"])
            signals["snoring_packets"] = table
            recording.meta["snore_phase_counts"] = snore_phase_counts(table)
        except Exception as error:  # noqa: BLE001
            recording.meta["snore_phase_error"] = str(error)

    recording.signals = signals
    recording.times = times
    recording.sample_rates = rates
    recording.meta["duration_sec"] = recording.duration_sec
    return recording


# ---------------------------------------------------------------------------
# Encoder (used for tests / synthetic data; mirrors the device format)
# ---------------------------------------------------------------------------
def encode_record(timestamp_ms: int, spo2: int, bpm: int,
                  accel_x, accel_y, accel_z, thorax, airflow, ecg) -> bytes:
    """Build one 712-byte record exactly as the device writes it."""
    payload = bytearray(PAYLOAD_SIZE)
    values = {
        "timestamp": [int(timestamp_ms)], "spo2": [int(spo2)], "bpm": [int(bpm)],
        "accel_x": accel_x, "accel_y": accel_y, "accel_z": accel_z,
        "thorax": thorax, "airflow": airflow, "ecg": ecg,
    }
    for name, (dtype, count, offset) in PAYLOAD_FIELDS.items():
        arr = np.asarray(values[name], dtype=np.dtype(dtype)).ravel()
        if arr.size != count:
            raise ValueError(f"{name}: expected {count} samples, got {arr.size}")
        raw = arr.tobytes()
        payload[offset:offset + len(raw)] = raw
    crc = crc16_ccitt(payload)
    return SYNC_MARKER + bytes(payload) + crc.to_bytes(2, "little")


def write_sd_recording(path: str | Path, records: list[bytes]) -> Path:
    path = Path(path)
    os.makedirs(path.parent, exist_ok=True)
    with open(path, "wb") as handle:
        for record in records:
            handle.write(record)
    return path
