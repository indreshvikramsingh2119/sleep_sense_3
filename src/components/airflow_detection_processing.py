import numpy as np
from scipy.signal import medfilt


def light_median_for_detection(signal):
    """Apply very light denoising while preserving airflow event drops."""
    signal = np.asarray(signal, dtype=float).reshape(-1)

    if len(signal) < 3:
        return signal

    return np.asarray(medfilt(signal, kernel_size=3), dtype=float)
