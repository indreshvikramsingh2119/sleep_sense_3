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
    
    def wheelEvent(self, ev, axis=None):
        """Stable zoom behavior anchored to the visible waveform strip."""
        # Get current view range
        current_x_range, current_y_range = self.viewRange()
        x_min, x_max = current_x_range
        y_min, y_max = current_y_range
        
        # Zoom factor based on scroll direction
        zoom_factor = 0.9 if ev.delta() > 0 else 1.1  # 0.9 for zoom in, 1.1 for zoom out

        y_anchor = (y_min + y_max) / 2.0
        if self.owner_plot_widget is not None and hasattr(self.owner_plot_widget, "plot_curve"):
            x_data, y_data = self.owner_plot_widget.plot_curve.getData()
            if x_data is not None and y_data is not None:
                x_values = np.asarray(x_data, dtype=float)
                y_values = np.asarray(y_data, dtype=float)
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
        
        # KEEP X FIXED at time window limits
        self.setRange(
            xRange=[self.time_window_min, self.time_window_max],
            yRange=[new_y_min, new_y_max],
            padding=0
        )

        if self.owner_plot_widget is not None:
            self.owner_plot_widget.zoom_y_range = (new_y_min, new_y_max)
        
        ev.accept()
    
    def mouseReleaseEvent(self, event):
        """Emit signal on mouse release"""
        self.sigMouseReleased.emit(event)
        super().mouseReleaseEvent(event)
