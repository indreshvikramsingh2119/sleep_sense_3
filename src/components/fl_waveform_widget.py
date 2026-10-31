"""Evaluate every raw nasal-cannula breath peak for flow limitation."""

from collections import deque
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from scipy.signal import butter, find_peaks, sosfiltfilt
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget


# MASTER SWITCH.
# True keeps the original raw-trace FL logic; False enables ATS-2017 logic.
FL_LEGACY_LOGIC = False
ATS_MIN_FLAT_SPAN_RATIO_LEGACY = 0.70

FL_MAX_PMR = 1.10
FL_MIN_TOP_WIDTH_RATIO = 0.25
FL_MAX_TOP_SPREAD_RATIO = 0.07
FL_MIN_AMPLITUDE_RATIO = 0.30
FL_MIN_ABSOLUTE_NOISE_MULTIPLE = 8.0
FL_MIN_TOP_WIDTH_SECONDS = 0.30
FL_BOX_INSET_FRACTION = 0.12
INSPIRATION_END_FRACTION = 0.93
PRE_EVENT_BASELINE_SECONDS = 120.0

# plateau_breaths() treats the UPWARD part of the array as inspiration. The
# current SD export already has inhale upward; the widget still supports
# mirroring when a future hardware export reports inhale as LOW.
FL_DETECT_ON_INHALE_SIDE = True

# --- ApneaLink-style 7-class inspiratory shape classifier -------------------
PEAK_PROMINENCE_RATIO = 0.35
PEAK_MIN_SEPARATION_SECONDS = 0.25
PEAK_NOISE_FLOOR_MULTIPLE = 3.0

CLASS7_MIN_SPAN_RATIO = 0.70
SHELF_MIN_LEVEL_RATIO = 0.35
SHELF_MAX_LEVEL_RATIO = 0.88
SHELF_BAND_RATIO = 0.15
SHELF_MIN_SECONDS = 0.25

CLASS_LABELS = {
    1: "Class 1: sinusoidal (no flattening)",
    2: "Class 2: two inspiratory peaks",
    3: "Class 3: three+ small peaks (scalloped top)",
    45: "Class 4/5: peak with plateau",
    6: "Class 6: peak late, preceded by an earlier shelf",
    7: "Class 7: plateau through inspiration",
}
CLASS_ALWAYS_FL = {6, 7}
CLASS_GATED = {2, 3, 45}

# --- ATS 2017 Workshop Report (Pamidi/Redline/Rapoport et al., Ann Am
# Thorac Soc 2017;14(7):1076-1085) inspiratory flow limitation (IFL)
# algorithm -- replaces the old PMR/width/spread "pattern_1" gate as the
# actual FL/normal decision. The 7-class shape classifier stays (feeds Step 1).
ATS_FLAT_LEVEL_FRACTION = 0.75
# The SHAPE of each breath is judged on airflow with snore vibration filtered
# out. Snoring vibration rides on the inspiratory peak and can fake scalloping.
FL_SHAPE_LOWPASS_HZ = 5.0

# A flow-limited breath must be a real inspiration above the resting level.
# A flat trace at rest is a pause/apnea, not flow limitation.
FL_MIN_PLATEAU_LIFT_RATIO = 0.10
FL_MAX_TI_RATIO = 2.0
FL_RESTING_LEVEL_WINDOW_SECONDS = 60.0

# ATS 2017 workshop report (Pamidi et al., Ann Am Thorac Soc 14:1076):
# flattening and/or scooping must cover 75% or more of inspiratory time.
ATS_MIN_FLAT_SPAN_RATIO = 0.75
ATS_TI_PROLONGATION_RATIO = 0.10
ATS_CONFIRM_MIN_SIGNS = 1
ATS_TI_REFERENCE_MIN_SECONDS = 0.5


def _fast_median(values):
    """``np.median`` for the small per-breath arrays, with the same result and much less call overhead.

    np.median costs ~40 us per call; plateau_breaths asks for a median several times per breath (tens of
    thousands of calls per recording).  The median is the middle value (odd count) or the mean of the two
    middle values (even count) -- exactly what is computed here.  Anything unusual (empty, NaN/inf) goes
    to np.median itself so special cases behave as before.
    """
    a = np.asarray(values, dtype=float)
    n = a.size
    if n == 0 or a.ndim != 1 or not np.isfinite(a).all():
        return np.median(a)
    half = n // 2
    if n % 2:
        return np.partition(a, half)[half]
    part = np.partition(a, [half - 1, half])
    return (part[half - 1] + part[half]) / 2.0


def _min_flat_span():
    """Return the flat-span threshold for the selected detector mode."""
    return ATS_MIN_FLAT_SPAN_RATIO_LEGACY if FL_LEGACY_LOGIC else ATS_MIN_FLAT_SPAN_RATIO


def _lowpass_for_shape(values, times, cutoff_hz):
    """Zero-phase low-pass each finite run; NaN positions stay NaN."""
    values = np.asarray(values, dtype=float)
    if not cutoff_hz or cutoff_hz <= 0:
        return values
    steps = np.diff(np.asarray(times, dtype=float))
    steps = steps[np.isfinite(steps) & (steps > 0)]
    if not steps.size:
        return values
    fs = 1.0 / float(np.median(steps))
    if cutoff_hz >= 0.4 * fs:
        return values
    sos = butter(4, cutoff_hz, btype="low", fs=fs, output="sos")
    out = values.copy()
    finite = np.isfinite(values)
    edges = np.diff(np.r_[False, finite, False].astype(np.int8))
    for start, stop in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        if stop - start > 40:
            out[start:stop] = sosfiltfilt(sos, values[start:stop])
    return out


def _resting_level(values, times, window_seconds):
    """Return rolling-median resting level and source-to-grid step."""
    import pandas as pd
    values = np.asarray(values, dtype=float)
    steps = np.diff(np.asarray(times, dtype=float))
    steps = steps[np.isfinite(steps) & (steps > 0)]
    if not steps.size or not np.isfinite(values).any():
        return None, 1
    dt = float(np.median(steps))
    step = max(1, int(round(0.1 / dt)))
    grid = pd.Series(values[::step]).interpolate(limit_direction="both")
    window = max(3, int(round(window_seconds / (dt * step))))
    return grid.rolling(window, center=True, min_periods=1).median().to_numpy(), step


def ats_ifl_status(shape_class, flat_span_ratio, amplitude_ok,
                   adjacent, ti_prolonged, snoring, plausible_breath=True):
    """Return the ATS IFL status for one breath."""
    if shape_class == 1 or not amplitude_ok or not plausible_breath:
        return "no_ifl"
    confirmations = int(bool(adjacent)) + int(bool(ti_prolonged)) + int(bool(snoring))
    if flat_span_ratio >= _min_flat_span():
        return "confirmed_ifl" if confirmations >= ATS_CONFIRM_MIN_SIGNS else "potential_ifl"
    return "potential_ifl" if confirmations >= 2 else "no_ifl"


def _top_bounds(wave, times, baseline, height, peak, top_fraction=0.88):
    """Return the connected upper-peak band, allowing one noisy sample."""
    high = wave >= baseline + top_fraction * height
    high_indices = np.flatnonzero(high)
    if not len(high_indices):
        return peak, peak

    dt = float(_fast_median(np.diff(times)))
    # Permit a one-sample notch in the high band because cannula data is noisy.
    splits = np.flatnonzero(np.diff(times[high_indices]) > 2.1 * dt) + 1
    groups = np.split(high_indices, splits)
    group = next(
        (candidate for candidate in groups if candidate[0] <= peak <= candidate[-1]),
        None,
    )
    if group is None:
        group = min(groups, key=lambda candidate: min(abs(candidate - peak)))

    lo, hi = int(group[0]), int(group[-1])
    return lo, hi


def _inspiration_end(wave, times, baseline, height, peak):
    """Find where the inspiratory (rising + capped) phase actually ends.

    A single noisy sample is a poor way to split inspiration from
    expiration: on real cannula data the very highest sample of a breath is
    frequently just a noise tick sitting in the middle of a broader plateau
    -- the plain argmax can land a few samples before the plateau's real
    end. Instead, take the same tolerant connected high-value band used for
    the flat-top check itself, just at a tighter fraction of the breath's
    own height -- inspiration lasts as long as the signal keeps riding that
    band; only once it leaves the band for good has expiration begun. That
    end index is returned; the caller treats wave[:end + 1] as the full
    inspiratory phase (rise + plateau) and wave[end:] as expiration, which
    is never inspected for flatness.

    The band uses a tight INSPIRATION_END_FRACTION (93%) threshold rather
    than the looser 88% used for the flat-top check itself. A smooth,
    rounded (non-FL) breath is curved enough that even a fairly tight
    near-max band still sits symmetrically around its single true peak,
    spanning some width on both sides -- the looser 88% band was wide
    enough on real breath shapes to swallow a chunk of the following
    expiratory decline too, which inflated the measured plateau width on
    curved breaths that must NOT be marked FL. 93% keeps the band tight
    enough to still capture a real plateau's own noise (a genuine flat cap
    stays close to its own peak for many consecutive samples) without also
    catching a rounded breath's symmetric shoulders.
    """
    _, hi = _top_bounds(
        wave, times, baseline, height, peak, top_fraction=INSPIRATION_END_FRACTION
    )
    return max(hi, peak)


def _flat_top_features(insp_wave, insp_times, baseline, height):
    """Measure Pattern 1 flat-top features within the inspiratory phase only.

    Textbook flow limitation is a phenomenon of inspiration alone: the flow
    curve rises (rounded), then gets capped by a flat ceiling for the rest of
    inspiration, while expiration afterwards follows its own separate,
    normal rounded shape and is never examined here. ``insp_wave`` /
    ``insp_times`` cover only the rise-and-plateau samples up to where
    inspiration ends (see ``_inspiration_end``) -- nothing from the falling
    expiratory phase is ever passed in, so a flat or high-valued expiratory
    stretch right after the peak can no longer be absorbed into what looks
    like "the top" the way it could when this scanned the whole
    trough-to-trough cycle.
    """
    peak = int(np.argmax(insp_wave))
    if len(insp_wave) < 3:
        return float("inf"), peak, peak, 0.0, float("inf"), 0.0

    sample_count = len(insp_wave)
    middle_start = sample_count // 4
    middle_end = sample_count - middle_start
    if middle_end <= middle_start:
        middle_start, middle_end = 0, sample_count
    middle = insp_wave[middle_start:middle_end] - baseline
    middle = middle[middle > 0]
    middle_mean = float(np.mean(middle)) if len(middle) else 0.0
    pmr = height / middle_mean if middle_mean > 0 else float("inf")

    lo, hi = _top_bounds(insp_wave, insp_times, baseline, height, peak)
    core_lo, core_hi = _top_bounds(insp_wave, insp_times, baseline, height, peak, 0.95)
    insp_duration = max(float(insp_times[-1] - insp_times[0]), 1e-9)
    top_width_seconds = float(insp_times[core_hi] - insp_times[core_lo])
    top_width_ratio = top_width_seconds / insp_duration
    top_values = insp_wave[core_lo:core_hi + 1]
    top_spread_ratio = (
        float(np.max(top_values) - np.min(top_values)) / height
        if len(top_values) and height > 0 else float("inf")
    )
    # Round every ratio that gets compared against a fixed threshold below
    # (FL_MAX_PMR / FL_MIN_TOP_WIDTH_RATIO / FL_MAX_TOP_SPREAD_RATIO /
    # FL_MIN_TOP_WIDTH_SECONDS) to 9 decimal places. A breath whose real
    # value sits essentially exactly on a threshold (e.g. a top band that
    # spans precisely 1/4 of the inspiration) can come out as
    # 0.25000000000003625 or 0.24999999999996 purely from floating-point
    # summation order. Rounding to 1e-9 makes the comparisons stable without
    # affecting genuine near-threshold decisions.
    return (
        round(pmr, 9),
        lo,
        hi,
        round(top_width_ratio, 9),
        round(top_spread_ratio, 9),
        round(top_width_seconds, 9),
    )


def _ats_flat_span_ratio(insp_wave, insp_times, baseline, height):
    """Measure the ATS 2017 Step 2 flattened/scooped span across Ti."""
    ti = float(insp_times[-1] - insp_times[0])
    if height <= 0 or len(insp_wave) < 2 or ti <= 0:
        return 0.0, max(ti, 0.0)
    near_max = insp_wave >= baseline + ATS_FLAT_LEVEL_FRACTION * height
    reached = np.flatnonzero(near_max)
    if not len(reached):
        return 0.0, ti
    first_idx = int(reached[0])
    flat_span_seconds = float(insp_times[-1] - insp_times[first_idx])
    return round(flat_span_seconds / ti, 9), ti


def _count_extra_peaks(insp_wave, insp_times, height):
    if len(insp_wave) < 5 or height <= 0:
        return 0
    dt = float(_fast_median(np.diff(insp_times))) or 1.0
    distance = max(1, int(round(PEAK_MIN_SEPARATION_SECONDS / dt)))
    noise_floor = float(_fast_median(np.abs(np.diff(insp_wave))))
    prominence = max(
        PEAK_PROMINENCE_RATIO * height,
        PEAK_NOISE_FLOOR_MULTIPLE * noise_floor,
        1e-9,
    )
    valleys, _ = find_peaks(-insp_wave, prominence=prominence, distance=distance)
    return len(valleys)


def _has_earlier_shelf(insp_wave, insp_times, baseline, height, lo):
    if lo < 4 or height <= 0:
        return False
    region = insp_wave[:lo]
    region_times = insp_times[:lo]
    level = (region - baseline) / height
    in_band = (level >= SHELF_MIN_LEVEL_RATIO) & (level <= SHELF_MAX_LEVEL_RATIO)

    n = len(region)
    i = 0
    while i < n:
        if not in_band[i]:
            i += 1
            continue
        j = i
        while (
            j < n - 1
            and in_band[j + 1]
            and abs(level[j + 1] - level[i]) <= SHELF_BAND_RATIO
        ):
            j += 1
        if region_times[j] - region_times[i] >= SHELF_MIN_SECONDS:
            return True
        i = j + 1
    return False


def _classify_shape(insp_wave, insp_times, baseline, height):
    extra_peaks = _count_extra_peaks(insp_wave, insp_times, height)
    if extra_peaks >= 2:
        return 3, CLASS_LABELS[3]
    if extra_peaks == 1:
        return 2, CLASS_LABELS[2]

    pmr, lo, hi, top_width_ratio, top_spread_ratio, top_width_seconds = (
        _flat_top_features(insp_wave, insp_times, baseline, height)
    )
    has_plateau = top_width_seconds >= FL_MIN_TOP_WIDTH_SECONDS and (
        pmr < FL_MAX_PMR
        or (
            top_width_ratio >= FL_MIN_TOP_WIDTH_RATIO
            and top_spread_ratio <= FL_MAX_TOP_SPREAD_RATIO
        )
    )
    if not has_plateau:
        return 1, CLASS_LABELS[1]

    if top_width_ratio >= CLASS7_MIN_SPAN_RATIO:
        return 7, CLASS_LABELS[7]

    if _has_earlier_shelf(insp_wave, insp_times, baseline, height, lo):
        return 6, CLASS_LABELS[6]

    return 45, CLASS_LABELS[45]


def _breath_boundaries(values, times, scale, dt):
    """Find trough-to-trough breaths without splitting at an upper-half notch."""
    troughs, properties = find_peaks(
        -values,
        distance=max(1, int(0.6 / dt)),
        prominence=0.15 * scale,
    )
    low_level = float(np.percentile(values, 40))
    deep_troughs = [
        int(trough) for trough, prominence in zip(troughs, properties["prominences"])
        if values[trough] <= low_level or prominence >= 0.30 * scale
    ]
    boundaries = deep_troughs if len(deep_troughs) >= 2 else list(troughs)
    index = 1
    while index < len(boundaries) - 1:
        left, middle, right = boundaries[index - 1:index + 2]
        baseline = max(float(values[left]), float(values[right]))
        height = float(np.max(values[left:right + 1]) - baseline)
        if (
            height > 0
            and 1 <= times[right] - times[left] <= 10
            and values[middle] >= baseline + 0.50 * height
        ):
            boundaries.pop(index)
        else:
            index += 1
    return boundaries


def plateau_breaths(airflow, time_seconds, snoring=None,
                    shape_lowpass_hz=FL_SHAPE_LOWPASS_HZ):
    """Check every complete breath's own inspiratory phase for IFL, per the
    ATS 2017 Workshop Report algorithm (Pamidi/Redline/Rapoport et al.).

    Step 1: shape_class == 1 (sinusoidal) -> No IFL.
    Step 2: flattening/scooping (_ats_flat_span_ratio) must cover >=75% of
            inspiratory time (Ti). If not -> No IFL.
    Step 3: for breaths passing Step 2, look for confirmation -- (a) an
            adjacent breath also clears Step 2, (b) Ti is >=10% longer than
            this patient's own recent-baseline Ti, (c) snoring/vibration during
            inspiration, from ``snoring``. Any one sign confirms IFL; breaths
            flat for less than 75% of Ti need two signs for potential IFL.
    A breath under FL_MIN_AMPLITUDE_RATIO (30%) of its local reference
    amplitude is forced to "no_ifl" regardless of the above.

    A duplicate or out-of-order timestamp (which does occur in raw device
    logs) ends the current run the same way a signal gap already does, so
    only that stretch is skipped -- one bad sample no longer aborts FL
    marking for the rest of the recording. Timestamps with no usable
    increasing step anywhere still raise, since no sample rate can be
    established at all in that case.
    """
    legacy = bool(FL_LEGACY_LOGIC)
    if legacy:
        snoring = None
        shape_lowpass_hz = None
    y = np.asarray(airflow, dtype=float)
    t = np.asarray(time_seconds, dtype=float)      
    if y.ndim != 1 or t.ndim != 1 or len(y) != len(t):
        raise ValueError("Airflow and timestamps must be equal-length 1D arrays.")
    if len(t) < 3:
        return []

    snore_active = None
    if snoring is not None:
        snore_active = np.asarray(snoring, dtype=float).reshape(-1)
        if len(snore_active) != len(y):
            raise ValueError("Snoring and airflow must be equal-length 1D arrays.")
        snore_active = np.nan_to_num(snore_active, nan=0.0) != 0.0

    diffs = np.diff(t)
    positive_diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
    if not len(positive_diffs):
        raise ValueError(
            "Timestamps must be finite and contain at least one increasing step."
        )
    dt = float(np.median(positive_diffs))

    # Noise floor comes from the trace as recorded; breath shape is judged on
    # the low-passed copy so vibration is removed.
    finite_y = y[np.isfinite(y)]
    global_noise_floor = (
        float(np.median(np.abs(np.diff(finite_y)))) if len(finite_y) > 1 else 0.0
    )
    y = _lowpass_for_shape(y, t, shape_lowpass_hz)
    valid = np.isfinite(y) & np.isfinite(t)
    bad_step = ~(np.isfinite(diffs) & (diffs > 0))
    large_gap = np.isfinite(diffs) & (diffs > 3 * dt)
    breaks = np.flatnonzero(
        (~valid[:-1]) | (~valid[1:]) | bad_step | large_gap
    ) + 1
    results = []
    breath_number = 0

    for indices in np.split(np.arange(len(y)), breaks):
        if len(indices) < 5 or not valid[indices].all():
            continue
        values = y[indices]
        scale = float(np.percentile(values, 95) - np.percentile(values, 5))
        if scale <= 0:
            continue
        troughs = _breath_boundaries(values, t[indices], scale, dt)
        for left, right in zip(troughs[:-1], troughs[1:]):
            start, end = int(indices[left]), int(indices[right])
            duration = float(t[end] - t[start])
            if not 1 <= duration <= 10:
                continue
            wave = y[start:end + 1]
            times = t[start:end + 1]
            baseline = float(max(wave[0], wave[-1]))
            height = float(wave.max() - baseline)
            if height <= 0.15 * scale:
                continue

            breath_number += 1
            peak = int(np.argmax(wave))
            insp_end = _inspiration_end(wave, times, baseline, height, peak)
            insp_wave = wave[: insp_end + 1]
            insp_times = times[: insp_end + 1]
            pmr, lo, hi, top_width_ratio, top_spread_ratio, top_width_seconds = (
                _flat_top_features(insp_wave, insp_times, baseline, height)
            )
            shape_class, shape_label = _classify_shape(
                insp_wave, insp_times, baseline, height
            )
            flat_span_ratio, ti_seconds = _ats_flat_span_ratio(
                insp_wave, insp_times, baseline, height
            )
            ats_flatness_ok = (
                shape_class != 1 and flat_span_ratio >= _min_flat_span()
            )

            results.append(
                dict(
                    number=breath_number,
                    start=start,
                    end=end,
                    peak_index=start + peak,
                    peak_value=float(wave[peak]),
                    baseline=baseline,
                    kind="normal",
                    amplitude=height,
                    top_start=start + lo,
                    top_end=start + hi,
                    ceiling=float(_fast_median(wave[lo:hi + 1])),
                    pmr=pmr,
                    top_width_ratio=top_width_ratio,
                    top_spread_ratio=top_spread_ratio,
                    top_width_seconds=top_width_seconds,
                    shape_class=shape_class,
                    shape_label=shape_label,
                    ti_seconds=ti_seconds,
                    flat_span_ratio=flat_span_ratio,
                    ats_flatness_ok=ats_flatness_ok,
                    snore_in_insp=bool(
                        snore_active is not None
                        and snore_active[start:start + insp_end + 1].any()
                    ),
                )
            )
    if not results:
        return results

    initial_end = float(t[0]) + PRE_EVENT_BASELINE_SECONDS
    initial_amplitudes = [
        row["amplitude"] for row in results
        if float(t[row["start"]]) <= initial_end
    ]
    initial_reference = float(np.mean(sorted(initial_amplitudes)[-3:]))

    initial_ti_values = [
        row["ti_seconds"] for row in results
        if float(t[row["start"]]) <= initial_end
        and row["ti_seconds"] >= ATS_TI_REFERENCE_MIN_SECONDS
    ]
    initial_ti_reference = float(np.median(initial_ti_values)) if initial_ti_values else 0.0

    # Reject flat pauses at the resting level and inspirations implausibly long
    # relative to the patient's usual inspiratory time.
    rest, rest_step = (
        (None, 1) if legacy
        else _resting_level(y, t, FL_RESTING_LEVEL_WINDOW_SECONDS)
    )
    typical_amplitude = float(np.percentile([r["amplitude"] for r in results], 75))
    all_ti = [r["ti_seconds"] for r in results if r["ti_seconds"] >= ATS_TI_REFERENCE_MIN_SECONDS]
    usual_ti = float(np.median(all_ti)) if all_ti else 0.0
    for row in results:
        lift = 0.0
        if rest is not None and typical_amplitude > 0:
            level = float(rest[min(row["peak_index"] // rest_step, len(rest) - 1)])
            lift = (row["ceiling"] - level) / typical_amplitude
        row["plateau_lift_ratio"] = lift
        ti_ok = usual_ti <= 0 or row["ti_seconds"] <= FL_MAX_TI_RATIO * usual_ti
        row["plausible_breath"] = True if legacy else bool(
            (rest is None or lift >= FL_MIN_PLATEAU_LIFT_RATIO) and ti_ok
        )

    for i, row in enumerate(results):
        prev_ok = (
            i > 0
            and results[i - 1]["ats_flatness_ok"]
            and results[i - 1]["plausible_breath"]
        )
        next_ok = (
            i < len(results) - 1
            and results[i + 1]["ats_flatness_ok"]
            and results[i + 1]["plausible_breath"]
        )
        row["ats_sign_adjacent"] = bool(prev_ok or next_ok)

    window = deque()  # (end_time, amplitude, ti_seconds) of processed breaths
    for row in results:
        start_time = float(t[row["start"]])
        cutoff = start_time - PRE_EVENT_BASELINE_SECONDS
        while window and window[0][0] < cutoff:
            window.popleft()

        candidates = [amp for end_time, amp, _ in window if end_time <= start_time]
        reference = (
            float(np.mean(sorted(candidates)[-3:])) if candidates else initial_reference
        )
        ti_candidates = [
            ti for end_time, _, ti in window
            if end_time <= start_time and ti >= ATS_TI_REFERENCE_MIN_SECONDS
        ]
        ti_reference = (
            float(np.median(ti_candidates)) if ti_candidates else initial_ti_reference
        )

        amplitude_drop = max(0.0, 100.0 * (reference - row["amplitude"]) / reference)
        amplitude_ratio = row["amplitude"] / reference
        amplitude_above_noise_floor = (
            global_noise_floor <= 0
            or row["amplitude"] >= FL_MIN_ABSOLUTE_NOISE_MULTIPLE * global_noise_floor
        )
        amplitude_ok = (
            amplitude_ratio >= FL_MIN_AMPLITUDE_RATIO and amplitude_above_noise_floor
        )

        sign_ti_prolonged = (
            ti_reference > 0
            and row["ti_seconds"] >= (1.0 + ATS_TI_PROLONGATION_RATIO) * ti_reference
        )
        sign_snoring = bool(row.get("snore_in_insp", False))
        signs_count = (
            int(row["ats_sign_adjacent"])
            + int(sign_ti_prolonged)
            + int(sign_snoring)
        )

        if legacy:
            if not row["ats_flatness_ok"] or not amplitude_ok:
                ifl_status = "no_ifl"
            elif row["ats_sign_adjacent"] and signs_count >= ATS_CONFIRM_MIN_SIGNS:
                ifl_status = "confirmed_ifl"
            elif signs_count >= 1:
                ifl_status = "potential_ifl"
            else:
                ifl_status = "no_ifl"
        else:
            ifl_status = ats_ifl_status(
                row["shape_class"], row["flat_span_ratio"], amplitude_ok,
                row["ats_sign_adjacent"], sign_ti_prolonged, sign_snoring,
                row["plausible_breath"],
            )

        row["reference_amplitude"] = reference
        row["amplitude_above_noise_floor"] = amplitude_above_noise_floor
        row["global_noise_floor"] = global_noise_floor
        row["amplitude_drop_percent"] = amplitude_drop
        row["amplitude_ratio"] = amplitude_ratio
        row["ti_reference"] = ti_reference
        row["ats_sign_ti_prolonged"] = sign_ti_prolonged
        row["ats_sign_snoring"] = sign_snoring
        row["ats_signs_count"] = signs_count
        row["ifl_status"] = ifl_status
        row["kind"] = "fl" if ifl_status == "confirmed_ifl" else "normal"

        window.append((float(t[row["end"]]), row["amplitude"], row["ti_seconds"]))
    return results


def draw_dashboard_fl_labels(plot, breaths, full_time, x, y, *, offset=0.0, exclusions=()):
    """Draw a shaded box spanning each FL breath, plus an FL label above its peak."""
    from src.utils.recording_exclusions import overlaps_exclusion

    for item in getattr(plot, "fl_labels", []):
        plot.removeItem(item)
    plot.fl_labels = []
    for item in getattr(plot, "fl_boxes", []):
        plot.removeItem(item)
    plot.fl_boxes = []
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    full_time = np.asarray(full_time, dtype=float)
    if not len(x) or len(x) != len(y) or not len(full_time):
        return

    for breath in breaths:
        if breath["end"] >= len(full_time):
            continue
        start = float(full_time[breath["start"]])
        end = float(full_time[breath["end"]])
        if overlaps_exclusion({"start_sec": start, "end_sec": end}, exclusions):
            continue
        center = float(full_time[breath["peak_index"]]) - float(offset)
        if center < x[0] or center > x[-1]:
            continue
        index = min(int(np.searchsorted(x, center)), len(x) - 1)
        if index and abs(x[index - 1] - center) < abs(x[index] - center):
            index -= 1
        if not np.isfinite(y[index]):
            continue

        tooltip = (
            f"Breath {breath['number']}: FL candidate\n"
            f"Amplitude: {breath['amplitude_ratio']:.0%} of baseline\n"
            f"{_fl_reason_text(breath)}"
        )

        inset = FL_BOX_INSET_FRACTION * (end - start)
        box_start = max(float(x[0]), start - float(offset) + inset)
        box_end = min(float(x[-1]), end - float(offset) - inset)
        if box_end > box_start:
            box = pg.LinearRegionItem(
                (box_start, box_end),
                movable=False,
                brush=pg.mkBrush(249, 115, 22, 45),
                pen=pg.mkPen(249, 115, 22, 160, width=1),
            )
            box.setZValue(-1)
            box.setAcceptedMouseButtons(Qt.NoButton)
            box.setToolTip(tooltip)
            plot.addItem(box, ignoreBounds=True)
            plot.fl_boxes.append(box)

        label = pg.TextItem("FL", color="#f97316", anchor=(0.5, 1.15))
        label_font = QFont()
        label_font.setPointSize(31)
        label_font.setBold(True)
        label.setFont(label_font)
        label.setPos(float(x[index]), float(y[index]))
        label.setZValue(100)
        label.setToolTip(tooltip)
        plot.addItem(label, ignoreBounds=True)
        plot.fl_labels.append(label)


def _fl_reason_text(breath):
    """Describe why the ATS 2017 algorithm confirmed this breath as IFL."""
    shape_label = breath.get("shape_label", "")
    prefix = f"{shape_label}\n" if shape_label else ""

    signs = []
    if breath.get("ats_sign_adjacent"):
        signs.append("adjacent breath also >=75% Ti")
    if breath.get("ats_sign_ti_prolonged"):
        signs.append(
            f"Ti {breath.get('ti_seconds', 0):.2f}s >= "
            f"{1 + ATS_TI_PROLONGATION_RATIO:.0%} of baseline "
            f"({breath.get('ti_reference', 0):.2f}s)"
        )
    if breath.get("ats_sign_snoring"):
        signs.append("snoring/vibration on signal")
    signs_text = "; ".join(signs) if signs else "no supporting signs"

    return (
        f"{prefix}ATS: flat/scooped {breath.get('flat_span_ratio', 0):.0%} of Ti "
        f"(>= {_min_flat_span():.0%}) -- confirmed via "
        f"{breath.get('ats_signs_count', 0)} sign(s): {signs_text}\n"
        f"(PMR {breath['pmr']:.3f} | top width {breath['top_width_ratio']:.0%} -- "
        f"reference only, not used for this call)"
    )


class FlWaveformWidget(QWidget):
    """Standalone review widget retained for reuse outside the dashboard."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.breaths = []
        self.t = np.array([])
        self.y = np.array([])
        self.overlays = []
        self.starts = np.array([])
        self.ends = np.array([])

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Recorded airflow - FL = clear Pattern 1 flat top - wheel: zoom, drag: scroll"
        ))
        self.source_label = QLabel("No recording loaded")
        self.source_label.setWordWrap(True)
        layout.addWidget(self.source_label)
        self.plot = pg.PlotWidget(background="#101827")
        self.plot.setLabel("bottom", "Recording time", units="s")
        self.plot.setLabel("left", "Airflow", units="recorded units")
        self.plot.setMouseEnabled(x=True, y=False)
        self.plot.showGrid(x=True, y=True, alpha=0.15)
        self.curve = self.plot.plot(
            pen=pg.mkPen("#22c55e", width=1.5), connect="finite"
        )
        self.curve.setDownsampling(ds=1, auto=False)
        self.curve.setClipToView(True)
        layout.addWidget(self.plot)
        self.plot.sigXRangeChanged.connect(self._draw_overlays)
        self.hover = pg.SignalProxy(
            self.plot.scene().sigMouseMoved, rateLimit=30, slot=self._hover
        )

    def set_data(self, airflow_array, timestamps_ms, *, inhale_is_low=False, snoring=None):
        """Show airflow and mark FL breaths with a consistent orientation."""
        y = np.asarray(airflow_array, dtype=float)
        self.inhale_is_low = bool(
            inhale_is_low and FL_DETECT_ON_INHALE_SIDE and not FL_LEGACY_LOGIC
        )
        if self.inhale_is_low and np.isfinite(y).any():
            y = 2.0 * float(np.nanmedian(y)) - y
        t = np.asarray(timestamps_ms, dtype=float) / 1000.0
        breaths = plateau_breaths(y, t, snoring=snoring)
        self.y, self.t, self.breaths = y.copy(), t.copy(), breaths
        self.starts = np.array([t[b["start"]] for b in breaths])
        self.ends = np.array([t[b["end"]] for b in breaths])

        connections = np.zeros(len(t), dtype=bool)
        if len(t) > 1:
            connections[:-1] = (
                np.isfinite(y[:-1])
                & np.isfinite(y[1:])
                & (np.diff(t) <= 3 * np.median(np.diff(t)))
            )
        self.curve.setData(self.t, self.y, connect=connections)
        self.plot.setToolTip("")
        self.source_label.setText(
            ("Inhale drawn UP (mirrored around the median) | " if self.inhale_is_low else "")
            + f"Samples: {len(y):,} | Missing: {np.count_nonzero(~np.isfinite(y)):,} | "
            f"FL candidates: {sum(b['kind'] == 'fl' for b in breaths)} | "
            f"Potential IFL: {sum(b.get('ifl_status') == 'potential_ifl' for b in breaths)} | "
            "Rule: ATS 2017 Workshop IFL algorithm (flat/scooped >= 75% of Ti "
            "+ >= 2 supporting signs), amplitude >= 30% of baseline | "
            "No smoothing or gap filling"
        )
        if len(t) > 1:
            self.plot.setLimits(xMin=float(t[0]), xMax=float(t[-1]))
            self.plot.setXRange(t[0], min(t[-1], t[0] + 30), padding=0)
            self.plot.enableAutoRange(axis="y")
        self._draw_overlays()

    def load_from_file(self, path, *, timestamp_unit="ms"):
        from ai_models.sleep_apnea.hybrid_pipeline_common import (
            load_sleep_recording,
            recording_to_dataframe,
        )

        if timestamp_unit not in ("ms", "s"):
            raise ValueError("timestamp_unit must be 'ms' or 's'.")
        recording = load_sleep_recording(path, preserve_recorded_airflow=True)
        frame = recording_to_dataframe(recording)
        if frame.empty or "airflow" not in frame:
            raise ValueError("Recording has no airflow samples.")
        timestamps = frame["timestamp"].to_numpy(dtype=float)
        timestamps = (timestamps - timestamps[0]) * (
            1000 if timestamp_unit == "s" else 1
        )
        inhale_is_low = False
        if str(recording.get("source_format", "")) == "smf":
            from src.utils.sd_record_reader import INSPIRATION_IS_LOW_AIRFLOW
            inhale_is_low = bool(INSPIRATION_IS_LOW_AIRFLOW)
        # SD snore packets are zero outside packets; legacy CSV snoring is a
        # continuous intensity column and must not be used as ATS evidence.
        snoring = None
        if inhale_is_low and "snoring" in frame:
            snoring = frame["snoring"].to_numpy()
        self.set_data(
            frame["airflow"].to_numpy(), timestamps,
            inhale_is_low=inhale_is_low, snoring=snoring,
        )
        self.source_label.setText(
            f"File: {Path(path).name} | Recorded timestamps: {timestamp_unit} | "
            + self.source_label.text()
        )

    def _draw_overlays(self, *_args):
        for item in self.overlays:
            self.plot.removeItem(item)
        self.overlays.clear()
        if not self.breaths:
            return
        left, right = self.plot.viewRange()[0]
        first = int(np.searchsorted(self.ends, left))
        last = int(np.searchsorted(self.starts, right, side="right"))
        for breath in self.breaths[first:last]:
            if breath["kind"] != "fl" or last - first > 200:
                continue
            start, end = breath["start"], breath["end"]
            region = pg.LinearRegionItem(
                (self.t[start], self.t[end]),
                movable=False,
                brush=pg.mkBrush(249, 115, 22, 45),
                pen=pg.mkPen(None),
            )
            region.setZValue(-1)
            line = pg.PlotDataItem(
                self.t[start:end + 1], self.y[start:end + 1],
                pen=pg.mkPen("#f97316", width=2),
            )
            ceiling = pg.PlotDataItem(
                [self.t[breath["top_start"]], self.t[breath["top_end"]]],
                [breath["ceiling"]] * 2,
                pen=pg.mkPen("#ef4444", style=Qt.DashLine),
            )
            label = pg.TextItem("FL", color="#fb923c", anchor=(0.5, 1))
            label_font = QFont()
            label_font.setPointSize(11)
            label_font.setBold(True)
            label.setFont(label_font)
            label.setPos(
                self.t[breath["peak_index"]], self.y[breath["peak_index"]]
            )
            for item in (region, line, ceiling, label):
                self.plot.addItem(item, ignoreBounds=True)
                self.overlays.append(item)

    def _hover(self, event):
        point = event[0]
        if not self.plot.sceneBoundingRect().contains(point) or not self.breaths:
            self.plot.setToolTip("")
            return
        x_value = self.plot.getViewBox().mapSceneToView(point).x()
        index = int(np.searchsorted(self.starts, x_value, side="right")) - 1
        if index < 0 or x_value > self.ends[index]:
            self.plot.setToolTip("")
            return
        breath = self.breaths[index]
        status = breath.get("ifl_status", "no_ifl")
        kind = {
            "confirmed_ifl": "FL: ATS confirmed IFL",
            "potential_ifl": "Potential IFL (1 supporting sign only)",
            "no_ifl": "No IFL",
        }.get(status, "No IFL")
        detail = (
            _fl_reason_text(breath) if breath["kind"] == "fl"
            else (
                f"{breath.get('shape_label', '')}\n"
                f"Flat/scooped span: {breath.get('flat_span_ratio', 0):.0%} of Ti "
                f"(need >= {_min_flat_span():.0%}) | "
                f"PMR: {breath['pmr']:.3f} | Top width: {breath['top_width_ratio']:.0%}"
            )
        )
        self.plot.setToolTip(
            f"Breath {breath['number']} - {kind}\n"
            f"Amplitude: {breath['amplitude_ratio']:.0%} of baseline | "
            f"{detail}"
        )
