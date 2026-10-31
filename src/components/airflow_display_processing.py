import numpy as np
import pandas as pd
from scipy.signal import medfilt, savgol_filter

# Raw hardware airflow goes DOWN during inspiration. Flip the display around
# its baseline so inspiration is drawn upward, matching usual PSG polarity.
AIRFLOW_DISPLAY_INHALE_UP = True


def orient_airflow_for_display(signal):
    """Orient airflow for display without changing the analysis signal."""
    values = np.asarray(signal, dtype=float).reshape(-1)
    finite = np.isfinite(values)
    if not AIRFLOW_DISPLAY_INHALE_UP or values.size == 0 or not finite.any():
        return values.copy()
    baseline = float(np.nanmedian(values[finite]))
    oriented = values.copy()
    oriented[finite] = 2.0 * baseline - values[finite]
    return oriented


def enhance_airflow_for_graph_and_detection(
    signal,
    amplitude=1.10,
    max_limit=None,
    spike_threshold=15.0,
    kernel_size=11,
    low_protect_margin=2.0,
    keep_integer=False,
    savgol_window=11,
    savgol_order=3,
):
    """Smooth, enhance, and share one airflow series for graphing and detection."""
    signal = np.asarray(signal, dtype=float).reshape(-1)

    if len(signal) == 0:
        return signal

    valid_mask = np.isfinite(signal)
    if not np.any(valid_mask):
        return signal

    # Fill temporarily only for filtering, then restore original NaN gaps.
    working = pd.Series(signal).interpolate(limit_direction="both").to_numpy(dtype=float)
    cleaned = working.copy()

    if len(cleaned) >= kernel_size:
        median_signal = medfilt(cleaned, kernel_size=kernel_size)
        diff = np.abs(cleaned - median_signal)
        spike_mask = diff >= spike_threshold
        cleaned[spike_mask] = median_signal[spike_mask]

    if len(cleaned) >= savgol_window:
        cleaned = savgol_filter(cleaned, savgol_window, savgol_order)

    lowest_value = float(np.nanmin(cleaned[valid_mask]))
    low_protect_limit = lowest_value + low_protect_margin
    low_protect_mask = cleaned <= low_protect_limit

    enhanced = cleaned.copy()
    enhance_mask = valid_mask & (~low_protect_mask)
    enhanced[enhance_mask] = lowest_value + (
        cleaned[enhance_mask] - lowest_value
    ) * amplitude
    enhanced[low_protect_mask] = cleaned[low_protect_mask]

    if max_limit is not None:
        enhanced = np.clip(enhanced, lowest_value, max_limit)

    if keep_integer:
        enhanced = np.rint(enhanced)

    enhanced[~valid_mask] = np.nan
    return enhanced.astype(float)


# 1.0 restores the vibration at its recorded amplitude.
AIRFLOW_SNORE_TEXTURE_GAIN = 0.3


def add_snore_texture_to_airflow_display(
    airflow_display,
    snoring,
    gain=AIRFLOW_SNORE_TEXTURE_GAIN,
):
    """Mix a subtle, sample-aligned snore vibration into display airflow only."""
    display = np.asarray(airflow_display, dtype=float).reshape(-1)
    snore = np.asarray(snoring, dtype=float).reshape(-1)
    if display.size == 0 or snore.size != display.size:
        return display.copy()

    textured = display.copy()
    valid = np.isfinite(display) & np.isfinite(snore) & (snore != 0.0)
    textured[valid] += float(gain) * snore[valid]
    return textured
