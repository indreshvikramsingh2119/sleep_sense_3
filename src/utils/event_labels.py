"""Shared label normalization for sleep event detection and display."""

from __future__ import annotations


_EVENT_LABEL_ALIASES = {
    "OSA": "OSA",
    "OBSTRUCTIVE APNEA": "OSA",
    "OBSTRUCTIVE": "OSA",
    "CSA": "CSA",
    "CENTRAL APNEA": "CSA",
    "CENTRAL": "CSA",
    "MSA": "MSA",
    "MIXED APNEA": "MSA",
    "MIXED": "MSA",
    "HSA": "HSA",
    "HYPOPNEA": "HSA",
    "HYPOPNOEA": "HSA",
}


def canonical_event_label(raw_label: str) -> str:
    """Return the canonical UI/storage label for an event."""
    label = str(raw_label or "").strip().upper().replace("-", " ").replace("_", " ")
    return _EVENT_LABEL_ALIASES.get(label, label.replace(" ", "_"))
