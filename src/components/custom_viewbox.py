"""
Custom ViewBox with stable Y-axis zoom and fixed X-axis for PSG monitoring
"""

import pyqtgraph as pg
from PyQt5.QtCore import pyqtSignal


class CustomViewBox(pg.ViewBox):
    """ViewBox with sigMouseReleased signal and stable zoom behavior"""
    sigMouseReleased = pyqtSignal(object)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.time_window_min = 0
        self.time_window_max = 60  # Default to 60 seconds
        # IMPORTANT: Set mouse mode to RectMode for natural behavior
        self.setMouseMode(self.RectMode)
    
    def set_time_window_limits(self, min_val, max_val):
        """Set the time window limits for X-axis"""
        self.time_window_min = min_val
        self.time_window_max = max_val
        # FIXED X RANGE - keep it fixed when limits change
        self.setXRange(min_val, max_val, padding=0)
    
    def wheelEvent(self, ev, axis=None):
        """Stable zoom behavior - only Y-axis zoom centered on waveform position"""
        # Get current view range
        current_x_range, current_y_range = self.viewRange()
        x_min, x_max = current_x_range
        y_min, y_max = current_y_range
        
        # Zoom factor based on scroll direction
        zoom_factor = 0.9 if ev.delta() > 0 else 1.1  # 0.9 for zoom in, 1.1 for zoom out
        
        # -----------------------------------------
        # ONLY Y ZOOM - centered on visible data range (NOT mouse position)
        # This keeps the strip plot anchored to its position
        # -----------------------------------------
        y_center = (y_min + y_max) / 2  # Center of visible Y-range where data is
        new_y_min = y_center - (y_center - y_min) * zoom_factor
        new_y_max = y_center + (y_max - y_center) * zoom_factor
        
        # KEEP X FIXED at time window limits
        self.setRange(
            xRange=[self.time_window_min, self.time_window_max],
            yRange=[new_y_min, new_y_max],
            padding=0
        )
        
        ev.accept()
    
    def mouseReleaseEvent(self, event):
        """Emit signal on mouse release"""
        self.sigMouseReleased.emit(event)
        super().mouseReleaseEvent(event)
