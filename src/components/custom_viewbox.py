"""
Custom ViewBox with mouse release signal for drag selection
"""

import pyqtgraph as pg
from PyQt5.QtCore import pyqtSignal, QRectF


class CustomViewBox(pg.ViewBox):
    """ViewBox with sigMouseReleased signal"""
    sigMouseReleased = pyqtSignal(object)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.time_window_min = 0
        self.time_window_max = 60  # Default to 60 seconds
    
    def set_time_window_limits(self, min_val, max_val):
        """Set the time window limits for X-axis"""
        self.time_window_min = min_val
        self.time_window_max = max_val
    
    def viewRange(self):
        """Override to enforce fixed time window limits"""
        range_val = super().viewRange()
        x_range, y_range = range_val
        
        # Force X-axis to be exactly the limits
        forced_x_range = [self.time_window_min, self.time_window_max]
        
        return [forced_x_range, y_range]
    
    def setRange(self, rect=None, padding=0.02, update=True, disableAutoRange=True, **kwargs):
        """Override setRange to enforce time window limits"""
        if rect is None:
            rect = self.viewRect()
        
        # Force X-axis to stay within limits
        current_width = rect.width()
        
        # Always force the range to be exactly the limits
        forced_rect = QRectF(self.time_window_min, rect.top(), 
                             self.time_window_max - self.time_window_min, rect.height())
        
        try:
            super().setRange(forced_rect, padding=0, update=update, disableAutoRange=disableAutoRange, **kwargs)
        except TypeError:
            # Handle older pyqtgraph versions
            super().setRange(forced_rect, padding=0, update=update, **kwargs)
    
    def mouseReleaseEvent(self, event):
        """Emit signal on mouse release"""
        self.sigMouseReleased.emit(event)
        super().mouseReleaseEvent(event)
