"""
Custom ViewBox with mouse release signal for drag selection
"""

import pyqtgraph as pg
from PyQt5.QtCore import pyqtSignal


class CustomViewBox(pg.ViewBox):
    """ViewBox with sigMouseReleased signal"""
    sigMouseReleased = pyqtSignal(object)
    sigViewChanged = pyqtSignal()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.time_window_min = 0
        self.time_window_max = 60  # Default to 60 seconds
    
    def set_time_window_limits(self, min_val, max_val):
        """Set the time window limits for X-axis"""
        self.time_window_min = min_val
        self.time_window_max = max_val
    
    def viewRange(self):
        """Override to enforce time window limits"""
        range_val = super().viewRange()
        x_range, y_range = range_val
        
        # Enforce X-axis limits
        if x_range[0] < self.time_window_min:
            x_range[0] = self.time_window_min
        if x_range[1] > self.time_window_max:
            x_range[1] = self.time_window_max
        
        return [x_range, y_range]
    
    def setRange(self, rect=None, padding=0.02, update=True, disableAutoRange=True, **kwargs):
        """Override setRange to enforce time window limits"""
        if rect is None:
            rect = self.viewRect()
        
        # Enforce X-axis limits
        if rect.left() < self.time_window_min:
            rect.setLeft(self.time_window_min)
        if rect.right() > self.time_window_max:
            rect.setRight(self.time_window_max)
        
        try:
            super().setRange(rect, padding=padding, update=update, disableAutoRange=disableAutoRange, **kwargs)
        except TypeError:
            # Handle older pyqtgraph versions
            super().setRange(rect, padding=padding, update=update, **kwargs)
        
        # Emit view changed signal for real-time selection updates
        self.sigViewChanged.emit()
    
    def mouseReleaseEvent(self, event):
        """Emit signal on mouse release"""
        self.sigMouseReleased.emit(event)
        super().mouseReleaseEvent(event)
