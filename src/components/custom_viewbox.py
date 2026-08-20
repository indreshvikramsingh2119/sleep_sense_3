"""
Custom ViewBox with stable Y-axis zoom and fixed X-axis for PSG monitoring
"""

import pyqtgraph as pg
from PyQt5.QtCore import pyqtSignal
import numpy as np


class CustomViewBox(pg.ViewBox):
    """ViewBox with sigMouseReleased signal and stable zoom behavior"""
    sigMouseReleased = pyqtSignal(object)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.time_window_min = 0
        self.time_window_max = 60  # Default to 60 seconds
        self.owner_plot_widget = None
        # IMPORTANT: Set mouse mode to RectMode for natural behavior
        self.setMouseMode(self.RectMode)
    
    def set_time_window_limits(self, min_val, max_val):
        """Set the time window limits for X-axis"""
        self.time_window_min = min_val
        self.time_window_max = max_val
        # FIXED X RANGE - keep it fixed when limits change
        self.setXRange(min_val, max_val, padding=0)

    def clear_rubber_band_state(self):
        """Hide any stuck rubber-band zoom box and reset drag bookkeeping."""
        box = getattr(self, "_rbScaleBox", None)
        if box is None:
            box = getattr(self, "rbScaleBox", None)

        if box is not None:
            try:
                box.hide()
            except Exception:
                pass

        if hasattr(self, "clickEvents") and isinstance(self.clickEvents, list):
            self.clickEvents.clear()

        for attr_name, value in (
            ("dragButtons", []),
            ("dragItem", None),
            ("lastDrag", None),
        ):
            if hasattr(self, attr_name):
                try:
                    setattr(self, attr_name, value)
                except Exception:
                    pass
    
    def wheelEvent(self, ev, axis=None):
        """Stable zoom behavior anchored to the visible waveform strip."""
        # Get current view range
        current_x_range, current_y_range = self.viewRange()
        x_min, x_max = current_x_range
        y_min, y_max = current_y_range
        
        # Zoom factor based on scroll direction
        zoom_factor = 0.96 if ev.delta() > 0 else 1.04  # softer zoom for stable row sizing

        y_anchor = (y_min + y_max) / 2.0
        if self.owner_plot_widget is not None and hasattr(self.owner_plot_widget, "plot_curve"):
            x_data, y_data = self.owner_plot_widget.plot_curve.getData()
            if x_data is not None and y_data is not None:
                x_values = np.asarray(x_data, dtype=float)
                y_values = np.asarray(y_data, dtype=float)
                min_len = min(len(x_values), len(y_values))
                x_values = x_values[:min_len]
                y_values = y_values[:min_len]
                visible_mask = (
                    np.isfinite(x_values)
                    & np.isfinite(y_values)
                    & (x_values >= x_min)
                    & (x_values <= x_max)
                )
                visible_y = y_values[visible_mask]
                if visible_y.size > 0:
                    y_anchor = float(np.median(visible_y))

        new_y_min = y_anchor - (y_anchor - y_min) * zoom_factor
        new_y_max = y_anchor + (y_max - y_anchor) * zoom_factor

        new_y_min, new_y_max = self._clamp_y_range(new_y_min, new_y_max)
        
        # KEEP X FIXED at time window limits
        self.setRange(
            xRange=[self.time_window_min, self.time_window_max],
            yRange=[new_y_min, new_y_max],
            padding=0
        )

        if self.owner_plot_widget is not None:
            self.owner_plot_widget.zoom_y_range = (new_y_min, new_y_max)
        
        ev.accept()

    def _clamp_y_range(self, new_y_min, new_y_max):
        """Clamp Y zoom so it stays inside the chart's original display bounds."""
        if self.owner_plot_widget is None:
            return new_y_min, new_y_max

        y_min_limit = getattr(self.owner_plot_widget, "zoom_y_min_limit", getattr(self.owner_plot_widget, "original_y_min", new_y_min))
        y_max_limit = getattr(self.owner_plot_widget, "zoom_y_max_limit", getattr(self.owner_plot_widget, "original_y_max", new_y_max))
        if y_max_limit <= y_min_limit:
            return new_y_min, new_y_max

        base_span = max(float(y_max_limit) - float(y_min_limit), 1e-6)
        min_span = float(getattr(self.owner_plot_widget, "zoom_y_min_span", base_span * 0.5))
        max_span = float(getattr(self.owner_plot_widget, "zoom_y_max_span", base_span))
        min_span = max(1e-6, min(min_span, base_span))
        max_span = max(min_span, min(max_span, base_span))

        current_span = max(float(new_y_max) - float(new_y_min), 1e-6)
        target_span = min(max(current_span, min_span), max_span)
        center = (float(new_y_min) + float(new_y_max)) / 2.0
        new_y_min = center - target_span / 2.0
        new_y_max = center + target_span / 2.0

        if new_y_min < y_min_limit:
            shift = y_min_limit - new_y_min
            new_y_min += shift
            new_y_max += shift
        if new_y_max > y_max_limit:
            shift = new_y_max - y_max_limit
            new_y_min -= shift
            new_y_max -= shift

        if new_y_min < y_min_limit:
            new_y_min = y_min_limit
        if new_y_max > y_max_limit:
            new_y_max = y_max_limit

        if new_y_max - new_y_min < min_span:
            new_y_max = min(y_max_limit, new_y_min + min_span)
            new_y_min = max(y_min_limit, new_y_max - min_span)

        return new_y_min, new_y_max
    
    def mouseReleaseEvent(self, event):
        """Emit signal on mouse release"""
        self.sigMouseReleased.emit(event)
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Suppress double-click rubber-band state and keep zoom box from sticking."""
        self.clear_rubber_band_state()
        event.accept()
