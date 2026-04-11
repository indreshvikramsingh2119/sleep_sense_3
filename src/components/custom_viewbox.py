"""
Custom ViewBox with mouse release signal for drag selection
"""

import pyqtgraph as pg
from PyQt5.QtCore import pyqtSignal


class CustomViewBox(pg.ViewBox):
    """ViewBox with sigMouseReleased signal"""
    sigMouseReleased = pyqtSignal(object)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def mouseReleaseEvent(self, event):
        """Emit signal on mouse release"""
        self.sigMouseReleased.emit(event)
        super().mouseReleaseEvent(event)
