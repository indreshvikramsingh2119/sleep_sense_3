import numpy as np
from scipy.signal import medfilt, savgol_filter


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

    cleaned = signal.copy()

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

    return enhanced.astype(float)
