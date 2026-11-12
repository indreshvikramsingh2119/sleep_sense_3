from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Iterable

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["pdf.fonttype"] = 42
matplotlib.rcParams["ps.fonttype"] = 42

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import ticker
from matplotlib.patches import Rectangle

from src.utils.event_labels import canonical_event_label
from src.utils.sample_rate import DEFAULT_SAMPLE_RATE_HZ, channel_sample_rate


PAGE_BG = "#ffffff"
INK = "#1c2431"
MUTE = "#5b6573"
GRID = "#d7dde6"
PANEL_BG = "#fbfcfd"
NAVY = "#1d3a6b"
TEAL = "#0f7c8a"
CORAL = "#c2410c"
AMBER = "#b45309"
GREEN = "#3f7d20"
PURPLE = "#6d28d9"
GRAY = "#8b95a5"

# ---- Framed report panels (same look as before: frame + header band) ----
FRAME_EDGE = "#4b5563"
HEADER_BAND_FILL = "#e6ebf1"
FRAME_PAD_BOTTOM = 0.008
FRAME_HEADER_H = 0.015
FRAME_GAP_ABOVE = 0.005
FRAME_X0 = 0.015
FRAME_W = 0.975

EVENT_BAR_MAX_SEC = 30.0        # y-scale of every event strip
EVENT_BAR_MIN_WIDTH_H = 0.004   # ~15 s: thinner bars vanish when printed

CHANNEL_CONFIG = (
    {"key": "body_position", "label": "Body position", "kind": "signal",
     "signal_keys": ("body_position", "position"), "height": 1.0},
    {"key": "obstructive_track", "label": "Obstructive apnea + Mixed", "kind": "event",
     "event_labels": {"OSA", "MSA"}, "height": 0.75},
    {"key": "central_track", "label": "Central apnea", "kind": "event",
     "event_labels": {"CSA"}, "height": 0.75},
    {"key": "hypopnea_track", "label": "Hypopnea", "kind": "event",
     "event_labels": {"HSA", "HYPOPNEA"}, "height": 0.75},
    {"key": "spo2", "label": "SpO2", "kind": "signal",
     "signal_keys": ("spo2_report_display", "spo2"), "height": 1.15},
    {"key": "airflow", "label": "Airflow", "kind": "signal",
     "signal_keys": ("airflow", "flow"), "height": 0.9},
)

CHANNEL_UNITS = {
    "body_position": "",
    "spo2": "%",
    "pulse": "bpm",
    "snoring": "",
    "movement": "",
    "airflow": "",
}

SIGNAL_LINE_COLORS = {
    "body_position": NAVY,
    "spo2": TEAL,
    "pulse": PURPLE,
    "snoring": "#f59e0b",
    "movement": GRAY,
    "airflow": "#115e59",
}

EVENT_STYLES = {
    "OSA": {"color": CORAL, "label": "Obstructive"},
    "MSA": {"color": "#7c2d12", "label": "Mixed"},
    "CSA": {"color": AMBER, "label": "Central"},
    "HSA": {"color": GREEN, "label": "Hypopnea"},
    "HYPOPNEA": {"color": GREEN, "label": "Hypopnea"},
}
EXCLUDED_EVENT_LABELS = {"REVIEW", "APNEA_REVIEW", "NO_EVENT", "SENSOR_OFF", "SENSOR OFF", "ARTIFACT", "DESATURATION", "DESAT", "ODI"}
SENSOR_OFF_LABELS = {"SENSOR_OFF", "SENSOR OFF"}


def _as_1d_float_array(signal: Iterable[float] | None) -> np.ndarray:
    if signal is None:
        return np.array([], dtype=float)
    array = np.asarray(list(signal) if not isinstance(signal, np.ndarray) else signal, dtype=float).ravel()
    if array.size == 0:
        return array
    return np.nan_to_num(array, nan=0.0, posinf=0.0, neginf=0.0)


def _downsample_pair(x_values: np.ndarray, y_values: np.ndarray, max_points: int) -> tuple[np.ndarray, np.ndarray]:
    n = min(x_values.size, y_values.size)
    if n == 0:
        return np.array([], dtype=float), np.array([], dtype=float)
    x_values, y_values = x_values[:n], y_values[:n]
    if n <= max_points:
        return x_values, y_values
    bins = max_points // 2
    edges = np.linspace(0, n, bins + 1).astype(int)
    xs, ys = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        if b <= a:
            continue
        seg = y_values[a:b]
        lo, hi = int(np.argmin(seg)), int(np.argmax(seg))
        first, second = sorted((lo, hi))
        xs.extend((x_values[a + first], x_values[a + second]))
        ys.extend((seg[first], seg[second]))
    return np.asarray(xs), np.asarray(ys)


def _event_elapsed_time_text(seconds: float) -> str:
    total_seconds = max(0, int(round(float(seconds))))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _normalize_detected_events(
    detected_events: Iterable[dict[str, Any]] | None,
    recording_hours: float,
) -> tuple[list[dict[str, Any]], list[tuple[float, float]]]:
    """Return (respiratory/desat events, sensor-off spans in hours)."""
    normalized_events: list[dict[str, Any]] = []
    sensor_off_spans: list[tuple[float, float]] = []
    max_end_hours = max(0.0, float(recording_hours))

    for event in list(detected_events or []):
        try:
            raw_label = canonical_event_label(event.get("final_label") or event.get("rule_label") or "")
            start_sec = max(0.0, float(event.get("start_sec", 0.0)))
            end_sec = max(start_sec, float(event.get("end_sec", 0.0)))
            start_hours = start_sec / 3600.0
            end_hours = end_sec / 3600.0
            if max_end_hours > 0:
                start_hours = min(start_hours, max_end_hours)
                end_hours = min(end_hours, max_end_hours)
            if end_hours <= start_hours:
                continue

            if raw_label in SENSOR_OFF_LABELS:
                sensor_off_spans.append((start_hours, end_hours))
                continue
            if not raw_label or raw_label in EXCLUDED_EVENT_LABELS:
                continue

            style = EVENT_STYLES.get(raw_label, {"color": "#6b7280", "label": raw_label})
            normalized_events.append({
                "label_key": raw_label,
                "legend_label": style["label"],
                "color": style["color"],
                "is_manual": (
                    str(event.get("source") or "").strip().lower() == "manual"
                    or bool(event.get("is_manually_edited"))
                    or bool(event.get("manual_label_override"))
                ),
                "start_sec": start_sec,
                "end_sec": end_sec,
                "duration_sec": end_sec - start_sec,
                "start_hours": start_hours,
                "end_hours": end_hours,
                "time_text": f"{_event_elapsed_time_text(start_sec)} ({max(1, int(round(end_sec - start_sec)))}s)",
            })
        except (TypeError, ValueError):
            continue

    return normalized_events, sensor_off_spans


def _style_axis(ax, line_color: str) -> None:
    ax.set_facecolor(PANEL_BG)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.spines["bottom"].set_visible(True)
    ax.spines["bottom"].set_color(GRAY)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.grid(True, axis="x", color=GRID, linewidth=0.7)
    ax.grid(False, axis="y")
    ax.tick_params(axis="both", labelsize=7, colors=MUTE, length=0)
    ax.tick_params(axis="x", labelbottom=False)


def _panel_title(ax, title: str, right_text: str = "") -> None:
    ax._panel_label = title
    ax._panel_right = right_text


def _add_framed_panels(fig, axes, channels: list[dict[str, Any]]) -> None:
    """Frame + header band around every panel (kept from the previous design)."""
    for ax, channel in zip(axes, channels):
        key = channel["key"]
        line_color = SIGNAL_LINE_COLORS.get(key, {
            "obstructive_track": CORAL, "central_track": AMBER,
            "hypopnea_track": GREEN, "desat_track": TEAL,
        }.get(key, "#0f5d73"))
        pos = ax.get_position()
        label = getattr(ax, "_panel_label", channel["label"])
        right_text = getattr(ax, "_panel_right", "")

        fig.add_artist(Rectangle(
            (FRAME_X0, pos.y0 - FRAME_PAD_BOTTOM), FRAME_W,
            pos.height + FRAME_PAD_BOTTOM + FRAME_GAP_ABOVE + FRAME_HEADER_H,
            transform=fig.transFigure, facecolor=PAGE_BG, edgecolor=FRAME_EDGE,
            linewidth=1.0, zorder=-5,
        ))
        band_y = pos.y0 + pos.height + FRAME_GAP_ABOVE
        fig.add_artist(Rectangle(
            (FRAME_X0, band_y), FRAME_W, FRAME_HEADER_H,
            transform=fig.transFigure, facecolor=HEADER_BAND_FILL, edgecolor=FRAME_EDGE,
            linewidth=1.0, zorder=-4,
        ))
        fig.add_artist(Rectangle(
            (FRAME_X0 + 0.007, band_y + FRAME_HEADER_H * 0.25), 0.005, FRAME_HEADER_H * 0.5,
            transform=fig.transFigure, facecolor=line_color, edgecolor="none", zorder=-3,
        ))
        fig.text(FRAME_X0 + 0.016, band_y + FRAME_HEADER_H / 2, label.upper(),
                 ha="left", va="center", fontsize=8.0, fontweight="bold", color="#111827")
        if right_text:
            fig.text(FRAME_X0 + FRAME_W - 0.006, band_y + FRAME_HEADER_H / 2, right_text,
                     ha="right", va="center", fontsize=7.2, color="#374151")


def _shade_sensor_off(ax, spans: list[tuple[float, float]]) -> None:
    for a, b in spans:
        ax.axvspan(a, b, facecolor="#e5e7eb", edgecolor="none", alpha=0.9, zorder=0.5)


def _plot_event_track(ax, events: list[dict[str, Any]]) -> None:
    """Bars whose HEIGHT is the event duration (0-30 s)."""
    ax.set_ylim(-5.0, EVENT_BAR_MAX_SEC)
    ax.set_yticks([0, EVENT_BAR_MAX_SEC])
    ax.set_yticklabels(["0s", "30s"], fontsize=6.5)
    if not events:
        ax.text(0.5, 0.5, "No events", transform=ax.transAxes, ha="center", va="center",
                fontsize=7.5, color=GRAY, style="italic", zorder=3)
        return
    for event in events:
        width = max(event["end_hours"] - event["start_hours"], EVENT_BAR_MIN_WIDTH_H)
        height = min(float(event["duration_sec"]), EVENT_BAR_MAX_SEC)
        ax.bar(event["start_hours"], height, width=width, align="edge",
               color=event["color"], edgecolor=event["color"], linewidth=0.3, zorder=2)
        if event.get("is_manual"):
            event_center = (event["start_hours"] + event["end_hours"]) / 2.0
            ax.scatter(
                [event_center], [-2.8], marker="o", s=14,
                color="#e11d48", edgecolors="#b91c1c", linewidths=0.35,
                zorder=5, clip_on=False,
            )


def _annotate_box(ax, x_hours: float, y: float, text: str, color: str, *, above: bool = True) -> None:
    ax.annotate(
        text, xy=(x_hours, y), xytext=(4, 10 if above else -12), textcoords="offset points",
        fontsize=6.6, fontweight="bold", color="#ffffff", ha="left", va="bottom" if above else "top",
        bbox={"boxstyle": "round,pad=0.25", "facecolor": color, "edgecolor": "none"}, zorder=6,
        annotation_clip=False,
    )


def _summary_pill(ax, text: str, color: str, bg: str) -> None:
    ax.text(0.006, 0.08, text, transform=ax.transAxes, ha="left", va="bottom", fontsize=6.6,
            fontweight="bold", color=color,
            bbox={"boxstyle": "round,pad=0.25", "facecolor": bg, "edgecolor": "none"}, zorder=6)


def generate_full_psg_hypnogram(
    psg_data: dict,
    output_folder: str,
    sampling_rate: float = DEFAULT_SAMPLE_RATE_HZ,
    patient_id: str | None = None,
    study_id: str | None = None,
    title: str = "Full-night trends",
    max_plot_points: int = 6000,
    detected_events: Iterable[dict[str, Any]] | None = None,
    recording_start: datetime | None = None,
) -> str:
    """Create one stacked, shared-axis report image.

    A PNG is intentionally used instead of a separately overlaid PDF page:
    ReportLab can attach the image directly, which keeps the hypnogram visible
    in both the development app and the frozen Windows executable.
    """
    if not psg_data:
        raise ValueError("PSG data is not available for report generation.")
    if sampling_rate <= 0:
        raise ValueError("Sampling rate must be greater than zero.")

    signal_map = psg_data.get("signals") if isinstance(psg_data, dict) else None
    if not isinstance(signal_map, dict):
        signal_map = psg_data
    rate_map = psg_data.get("sample_rates") if isinstance(psg_data, dict) else None
    time_map = psg_data.get("times") if isinstance(psg_data, dict) else None
    rate_map = rate_map if isinstance(rate_map, dict) else {}
    time_map = time_map if isinstance(time_map, dict) else {}

    available_channels: list[dict[str, Any]] = []
    for channel in CHANNEL_CONFIG:
        if channel["kind"] == "event":
            available_channels.append(dict(channel))
            continue
        signal = np.array([], dtype=float)
        matched_key = None
        for candidate in channel["signal_keys"]:
            signal = _as_1d_float_array(signal_map.get(candidate))
            if signal.size:
                matched_key = candidate
                break
        if signal.size == 0:
            continue
        rate = channel_sample_rate(matched_key, rate_map, default=float(sampling_rate))
        time_sec = _as_1d_float_array(time_map.get(matched_key)) if matched_key in time_map else np.array([])
        if time_sec.size != signal.size:
            time_sec = np.arange(signal.size, dtype=float) / float(rate)
        available_channels.append({**channel, "signal": signal, "rate": float(rate), "time_sec": time_sec})

    signal_channels = [c for c in available_channels if c["kind"] == "signal"]
    if not signal_channels:
        raise ValueError("No PSG signal channels are available for the full overview report.")

    if any(c["signal"].size == 0 for c in signal_channels):
        raise ValueError("Loaded PSG channels do not contain any samples.")

    recording_hours = max((float(c["time_sec"][-1]) + 1.0 / c["rate"]) / 3600.0 for c in signal_channels)
    normalized_events, sensor_off_spans = _normalize_detected_events(detected_events, recording_hours)

    for channel in available_channels:
        if channel["kind"] == "event":
            wanted = set(channel.get("event_labels", set()))
            channel["track_events"] = [e for e in normalized_events if e["label_key"] in wanted]

    height_ratios = [float(c.get("height", 1.0)) for c in available_channels]
    # Figure proportions match an A4 report page (content area ~ 1.30 : 1),
    # so the PNG fills the page instead of leaving blank space underneath.
    fig_width = 11.0
    fig_height = fig_width * 1.30
    fig, axes = plt.subplots(
        len(available_channels), 1,
        figsize=(fig_width, fig_height), sharex=True,
        gridspec_kw={"height_ratios": height_ratios, "hspace": 0.45},
    )
    if len(available_channels) == 1:
        axes = [axes]

    x_max = recording_hours if recording_hours > 0 else 1 / 3600.0

    for ax, channel in zip(axes, available_channels):
        key, label = channel["key"], channel["label"]
        line_color = SIGNAL_LINE_COLORS.get(key, "#0f5d73")
        _style_axis(ax, line_color)
        _shade_sensor_off(ax, sensor_off_spans)
        right_text = ""

        if channel["kind"] == "event":
            events = channel.get("track_events", [])
            _plot_event_track(ax, events)
            if events:
                mean_dur = float(np.mean([e["duration_sec"] for e in events]))
                right_text = f"{len(events)} event{'s' if len(events) != 1 else ''} | mean {mean_dur:.1f} s"
            _panel_title(ax, label, right_text)
            continue

        clipped = channel["signal"]
        channel_rate = float(channel["rate"])
        time_hours = channel["time_sec"] / 3600.0
        x_plot, y_plot = _downsample_pair(time_hours, clipped, max_plot_points)

        if key == "body_position":
            ax.step(x_plot, y_plot, where="post", linewidth=1.6, color=line_color, zorder=2)
            ax.set_yticks([0, 1, 2, 3, 4])
            ax.set_yticklabels(["Supine", "Left", "Right", "Prone", "Up"], fontsize=6.5)
            ax.set_ylim(-0.4, 4.4)
            for yv in (0, 1, 2, 3, 4):
                ax.axhline(yv, color=GRID, linewidth=0.6, linestyle=(0, (2, 3)), zorder=1)
            names = ["Supine", "Left", "Right", "Prone", "Up"]
            y_plot = np.where(y_plot >= 5, np.nan, y_plot)
            mins = [float(np.sum(np.rint(clipped) == i)) / channel_rate / 60.0 for i in range(5)]
            right_text = " | ".join(f"{n} {m:.0f} min" for n, m in zip(names, mins) if m >= 0.5)

        elif key == "spo2":
            ax.plot(x_plot, y_plot, linewidth=0.9, color=line_color, zorder=2)
            ax.set_ylim(68, 101)
            ax.set_yticks([70, 80, 90, 100])
            for yv in (70, 80, 90, 100):
                ax.axhline(yv, color=GRID, linewidth=0.6, zorder=1)
            ax.axhline(90, color=CORAL, linewidth=0.9, linestyle=(0, (4, 3)), zorder=1.5)
            valid = clipped[(clipped > 0) & (clipped <= 100)]
            if valid.size:
                mean_v, min_v = float(np.mean(valid)), float(np.min(valid))
                min_idx = int(np.argmin(np.where((clipped > 0) & (clipped <= 100), clipped, 999)))
                min_x = float(time_hours[min_idx])
                ax.axvline(min_x, color=INK, linewidth=0.7, linestyle=(0, (2, 2)), zorder=3)
                _annotate_box(ax, min_x, 100, f"Min {min_v:.0f}", INK, above=False)
                _summary_pill(ax, f"Mean {mean_v:.1f}", INK, "#e8eef6")
                below90_min = float(np.sum(valid < 90)) / channel_rate / 60.0
                right_text = f"Mean {mean_v:.1f} | Min {min_v:.0f} | T<90% {below90_min:.1f} min"

        elif key == "pulse":
            ax.plot(x_plot, y_plot, linewidth=0.8, color=line_color, zorder=2)
            valid = clipped[(clipped >= 30) & (clipped <= 220)]
            lo = 40 if not valid.size else max(30, int(np.min(valid) // 10 * 10) - 10)
            hi = 200 if not valid.size else min(220, int(np.max(valid) // 10 * 10) + 20)
            ax.set_ylim(lo, hi)
            ax.yaxis.set_major_locator(ticker.MaxNLocator(4, integer=True))
            for yv in ax.get_yticks():
                ax.axhline(yv, color=GRID, linewidth=0.6, zorder=1)
            if valid.size:
                mean_v, min_v, max_v = float(np.mean(valid)), float(np.min(valid)), float(np.max(valid))
                _summary_pill(ax, f"Mean {mean_v:.0f}", PURPLE, "#efe9fb")
                right_text = f"Mean {mean_v:.0f} | Min {min_v:.0f} | Max {max_v:.0f}"
                if max_v >= 160:
                    max_idx = int(np.argmax(np.where((clipped >= 30) & (clipped <= 220), clipped, -1)))
                    _annotate_box(ax, float(time_hours[max_idx]), max_v, f"{max_v:.0f} \u2691 artifact?", CORAL, above=False)

        elif key in ("snoring", "movement"):
            bin_sec = 120.0
            n_bins = int(np.ceil(clipped.size / (channel_rate * bin_sec)))
            edges = (np.arange(n_bins + 1) * bin_sec * channel_rate).astype(int)
            vals = np.array([np.max(np.abs(clipped[a:b])) if b > a else 0.0 for a, b in zip(edges[:-1], edges[1:])])
            top = float(np.percentile(vals, 99)) if vals.size else 1.0
            vals = np.clip(vals / max(top, 1e-9), 0, 1)
            ax.bar(edges[:-1] / channel_rate / 3600.0, vals, width=bin_sec / 3600.0 * 0.9,
                   align="edge", color=line_color, linewidth=0, zorder=2)
            ax.set_ylim(0, 1.05)
            ax.set_yticks([0])
            ax.set_yticklabels(["0"], fontsize=6.5)
            if key == "snoring":
                active_pct = 100.0 * float(np.mean(vals > 0.25)) if vals.size else 0.0
                right_text = f"active {active_pct:.0f}% of TRT (2-min bins)"

        else:
            ax.plot(x_plot, y_plot, linewidth=0.6, color=line_color, zorder=2)
            lo, hi = float(np.nanmin(y_plot)), float(np.nanmax(y_plot))
            pad = max((hi - lo) * 0.12, 1.0)
            ax.set_ylim(lo - pad, hi + pad)
            ax.yaxis.set_major_locator(ticker.MaxNLocator(3))
            if key == "airflow":
                for event in normalized_events:
                    if event["label_key"] in ("DESATURATION", "DESAT", "ODI"):
                        continue
                    ax.axvspan(event["start_hours"], event["end_hours"], facecolor=event["color"],
                               edgecolor="none", alpha=0.35, zorder=1)

        unit = CHANNEL_UNITS.get(key, "")
        _panel_title(ax, f"{label}" + (f"  ({unit})" if unit else ""), right_text)

    last_ax = axes[-1]
    last_ax.set_xlim(0, x_max)
    last_ax.tick_params(axis="x", labelbottom=True, labelsize=7.5, colors=INK)
    if recording_start is not None:
        def _fmt(h, _pos):
            return (recording_start + timedelta(hours=float(h))).strftime("%H:%M")
        last_ax.xaxis.set_major_formatter(ticker.FuncFormatter(_fmt))
        last_ax.set_xlabel("Clock time", fontsize=7.5, color=MUTE, labelpad=3)
    else:
        last_ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda h, _p: f"{h:.0f}h" if float(h).is_integer() else f"{h:.1f}h"))
        last_ax.set_xlabel("Elapsed recording time", fontsize=7.5, color=MUTE, labelpad=3)
    last_ax.xaxis.set_major_locator(ticker.MaxNLocator(10))

    fig.patch.set_facecolor(PAGE_BG)
    fig.text(0.02, 0.985, title, fontsize=13, fontweight="bold", color=NAVY, ha="left", va="top")
    fig.text(0.02, 0.968, "All channels on one shared time axis | bar height = event duration (0\u201330 s) | grey = sensor off",
             fontsize=7.5, color=MUTE, ha="left", va="top")
    seen: dict[str, str] = {}
    for e in normalized_events:
        seen.setdefault(str(e["legend_label"]), str(e["color"]))
    if seen:
        handles = [Rectangle((0, 0), 1, 1, facecolor=c, edgecolor=c, label=l) for l, c in seen.items()]
        fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.985, 0.995), ncol=len(handles),
                   frameon=False, fontsize=7.5, handlelength=1.0, handleheight=0.9, columnspacing=1.2)

    fig.subplots_adjust(left=0.085, right=0.975, top=0.93, bottom=0.04)
    _add_framed_panels(fig, axes, available_channels)

    os.makedirs(output_folder, exist_ok=True)
    uid = uuid.uuid4().hex[:8]
    file_name = f"{patient_id or 'patient'}_{study_id or 'study'}_psg_hypnogram_{uid}.png"
    output_path = os.path.join(output_folder, file_name)
    fig.savefig(output_path, format="png", dpi=220, facecolor=PAGE_BG)
    plt.close(fig)
    return output_path
