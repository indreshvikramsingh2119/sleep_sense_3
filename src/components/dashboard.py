"""
Sleep Sense Dashboard - Main Dashboard Component
"""

import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QSplitter, QSizePolicy, QScrollArea,
    QSlider, QPushButton, QMenuBar, QMenu, QAction, QComboBox, QToolBar, QFileDialog, QMessageBox, QCheckBox, QStyle
)
from PyQt5.QtCore import Qt, QSize, QPoint, QRect, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QPainter, QColor, QPen

from .patient_info_widget import PatientInfoWidget
from .sleep_monitor_chart import SleepMonitorChart
from .database_window import DatabaseWindow
from .archive_window import ArchiveWindow
from .event_window import EventWindow
from ..utils.toolbar_utils import create_toolbar_button, get_icon_definitions, get_toolbar_qss_styles
from src.utils.button_functions import ButtonFunctions


class ScreenshotSelectionLabel(QLabel):
    """Pixmap label that lets the user drag a crop rectangle."""

    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setPixmap(pixmap)
        self.setMouseTracking(True)
        self.dragging = False
        self.selection_start = QPoint()
        self.selection_end = QPoint()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.selection_start = event.pos()
            self.selection_end = event.pos()
            self.update()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.selection_end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.dragging:
            self.selection_end = event.pos()
            self.dragging = False
            self.update()

    def selection_rect(self):
        if self.pixmap() is None:
            return QRect()
        rect = QRect(self.selection_start, self.selection_end).normalized()
        return rect.intersected(self.pixmap().rect())

    def has_selection(self):
        return self.selection_rect().width() > 5 and self.selection_rect().height() > 5

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.selection_rect().isNull():
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.selection_rect()
        painter.fillRect(rect, QColor(59, 130, 246, 60))
        pen = QPen(QColor(59, 130, 246))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(rect)


class ScreenshotOverlayWidget(QWidget):
    """Inline overlay that lets the user drag-select a crop area on the dashboard."""

    selection_confirmed = pyqtSignal(QRect)
    cancelled = pyqtSignal()

    def __init__(self, source_pixmap, parent=None):
        super().__init__(parent)
        self.source_pixmap = source_pixmap
        self.selection_start = QPoint()
        self.selection_end = QPoint()
        self.dragging = False
        self._cached_scaled_background = QPixmap()
        self._cached_background_size = QSize()

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.SubWindow)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.setFocusPolicy(Qt.StrongFocus)

        self.overlay_ratio_x = 1.0
        self.overlay_ratio_y = 1.0

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus()
        self._update_background_cache()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_background_cache()

    def _update_background_cache(self):
        if self.size().isEmpty() or self.source_pixmap.isNull():
            self._cached_scaled_background = QPixmap()
            self._cached_background_size = QSize()
            return
        if self._cached_background_size == self.size() and not self._cached_scaled_background.isNull():
            return
        self._cached_scaled_background = self.source_pixmap.scaled(
            self.size(),
            Qt.IgnoreAspectRatio,
            Qt.FastTransformation,
        )
        self._cached_background_size = QSize(self.size())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.selection_start = event.pos()
            self.selection_end = event.pos()
            self.update()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.selection_end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.dragging:
            self.selection_end = event.pos()
            self.dragging = False
            self.update()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Escape, Qt.Key_Backspace):
            self.cancelled.emit()
            return
        super().keyPressEvent(event)

    def selection_rect(self):
        rect = QRect(self.selection_start, self.selection_end).normalized()
        return rect

    def source_selection_rect(self):
        rect = self.selection_rect().intersected(self.rect())
        if rect.isNull():
            return QRect()
        return QRect(
            int(rect.x() * self.overlay_ratio_x),
            int(rect.y() * self.overlay_ratio_y),
            int(rect.width() * self.overlay_ratio_x),
            int(rect.height() * self.overlay_ratio_y),
        ).intersected(self.source_pixmap.rect())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self._cached_scaled_background.isNull() or self._cached_background_size != self.size():
            self._update_background_cache()
        if not self._cached_scaled_background.isNull():
            painter.drawPixmap(0, 0, self._cached_scaled_background)

        painter.fillRect(self.rect(), QColor(15, 23, 42, 70))

        header = QRect(16, 16, max(300, self.width() - 32), 56)
        painter.setPen(Qt.NoPen)
        painter.fillRect(header, QColor(255, 255, 255, 235))
        painter.setPen(QColor("#111827"))
        painter.drawText(header.adjusted(16, 8, -16, -8), Qt.AlignLeft | Qt.AlignVCenter,
                         "Drag to select the screenshot area")
        painter.setPen(QColor("#4b5563"))
        painter.drawText(header.adjusted(16, 26, -16, -8), Qt.AlignLeft | Qt.AlignVCenter,
                         "Press Esc to cancel. Release mouse, then click Capture Selected Area.")

        rect = self.selection_rect()
        if not rect.isNull():
            painter.fillRect(rect, QColor(59, 130, 246, 70))
            pen = QPen(QColor(59, 130, 246))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(rect)

        footer_height = 60
        footer = QRect(0, self.height() - footer_height, self.width(), footer_height)
        painter.setPen(Qt.NoPen)
        painter.fillRect(footer, QColor(255, 255, 255, 240))

        capture_rect = QRect(self.width() - 180, self.height() - 46, 160, 32)
        cancel_rect = QRect(self.width() - 350, self.height() - 46, 150, 32)
        painter.setBrush(QColor("#16a34a"))
        painter.setPen(QColor("#15803d"))
        painter.drawRoundedRect(capture_rect, 6, 6)
        painter.setPen(QColor("white"))
        painter.drawText(capture_rect, Qt.AlignCenter, "Capture Selected Area")

        painter.setBrush(QColor("#f3f4f6"))
        painter.setPen(QColor("#d1d5db"))
        painter.drawRoundedRect(cancel_rect, 6, 6)
        painter.setPen(QColor("#374151"))
        painter.drawText(cancel_rect, Qt.AlignCenter, "Cancel")

    def mousePressInFooter(self, pos):
        capture_rect = QRect(self.width() - 180, self.height() - 46, 160, 32)
        cancel_rect = QRect(self.width() - 350, self.height() - 46, 150, 32)
        if capture_rect.contains(pos):
            return "capture"
        if cancel_rect.contains(pos):
            return "cancel"
        return None

    def mousePressEvent(self, event):
        action = self.mousePressInFooter(event.pos())
        if action == "capture":
            rect = self.source_selection_rect()
            if rect.isNull() or rect.width() <= 5 or rect.height() <= 5:
                QMessageBox.information(self, "Select Area", "Please drag to select a screenshot area first.")
                return
            self.selection_confirmed.emit(rect)
            return
        if action == "cancel":
            self.cancelled.emit()
            return

        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.selection_start = event.pos()
            self.selection_end = event.pos()
            self.update()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.selection_end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.dragging:
            self.selection_end = event.pos()
            self.dragging = False
            self.update()


class ScreenshotSelectorDialog(QDialog):
    """Dialog for selecting a crop area from a dashboard screenshot."""

    def __init__(self, source_pixmap, parent=None):
        super().__init__(parent)
        self.source_pixmap = source_pixmap
        self.selected_rect = QRect()
        self.display_scale = 1.0

        self.setWindowTitle("Select Screenshot Area")
        self.setModal(True)
        self.setMinimumSize(900, 600)

        self._build_ui()

    def _build_ui(self):
        from PyQt5.QtWidgets import QApplication

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        title = QLabel("Drag to select the area you want to capture")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #111827;")

        hint = QLabel("Release the mouse, then click 'Capture Selected Area'.")
        hint.setStyleSheet("font-size: 11px; color: #4b5563;")

        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        max_width = (available.width() - 80) if available else self.source_pixmap.width()
        max_height = (available.height() - 180) if available else self.source_pixmap.height()
        max_width = max(400, max_width)
        max_height = max(300, max_height)

        scaled_pixmap = self.source_pixmap
        if self.source_pixmap.width() > max_width or self.source_pixmap.height() > max_height:
            scaled_pixmap = self.source_pixmap.scaled(
                max_width,
                max_height,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        self.display_scale = (
            scaled_pixmap.width() / self.source_pixmap.width()
            if self.source_pixmap.width()
            else 1.0
        )

        self.selection_label = ScreenshotSelectionLabel(scaled_pixmap)
        self.selection_label.setStyleSheet("background-color: #f8fafc; border: 1px solid #d1d5db;")
        self.selection_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        button_row = QHBoxLayout()
        button_row.addStretch()

        capture_button = QPushButton("Capture Selected Area")
        capture_button.setFixedSize(170, 32)
        capture_button.clicked.connect(self.accept_selection)

        cancel_button = QPushButton("Cancel")
        cancel_button.setFixedSize(100, 32)
        cancel_button.clicked.connect(self.reject)

        button_row.addWidget(capture_button)
        button_row.addWidget(cancel_button)

        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(self.selection_label, stretch=1)
        layout.addLayout(button_row)

    def accept_selection(self):
        rect = self.selection_label.selection_rect()
        if rect.isNull() or rect.width() <= 5 or rect.height() <= 5:
            QMessageBox.information(self, "Select Area", "Please drag to select a screenshot area first.")
            return

        self.selected_rect = QRect(
            int(rect.x() / self.display_scale),
            int(rect.y() / self.display_scale),
            int(rect.width() / self.display_scale),
            int(rect.height() / self.display_scale),
        ).intersected(self.source_pixmap.rect())
        self.accept()

class SleepSenseDashboard(QMainWindow):
    
    """Main Sleep Sense Dashboard Window"""
    
    def __init__(self):
        super().__init__()
        self.logo_frame = None
        self.logo_label = None
        self.dashboard_screenshot_paths = []
        self.current_patient_data = None
        self.screenshot_overlay = None
        self._screenshot_source_pixmap = None
        
        # Global event navigation system
        self.current_event_index = -1  # Global pointer for event navigation
        self.all_events = []  # Master event array sorted chronologically
        
        self.button_functions = ButtonFunctions(self)
        self.init_ui()
        self.load_stylesheet()
        
    def init_ui(self):
        self.setWindowTitle("")
        
        # Central Widget
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Menu Bar Container - Custom menu bar positioned below system menu bar
        menu_container = QFrame()
        menu_container.setObjectName("menuContainer")
        menu_container.setMinimumHeight(50)
        menu_container.setMaximumHeight(55)
        menu_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        menu_layout = QHBoxLayout(menu_container)
        menu_layout.setContentsMargins(8, 8, 8, 8)
        menu_layout.setSpacing(4)
        
        # Create custom menu buttons
        self.button_functions.create_custom_menu_buttons(menu_layout)
        
        main_layout.addWidget(menu_container)
        
        # Create a horizontal layout for toolbar and controls
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(0)
        
        # Professional Icon Toolbar
        self.toolbar = self.create_professional_toolbar()
        top_layout.addWidget(self.toolbar)
        
        # Add spacer to push controls to the right
        top_layout.addStretch()
        
        # Controls Container (Time Window, Hidden Graphs) - Right Side
        controls_container = self.create_controls_container()
        top_layout.addWidget(controls_container)
        
        # Add the top layout to main layout
        main_layout.addLayout(top_layout)
        
        # Main Content Area with Scroll
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        content_widget = QWidget()
        content_widget.setMinimumWidth(0)
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(16)
        
        # Splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        
        # Left Panel - Patient Info
        patient_panel = QFrame()
        patient_panel.setObjectName("patientPanel")
        patient_panel.setMinimumWidth(380)  
        patient_panel.setMaximumWidth(450) 
        patient_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        patient_layout = QVBoxLayout(patient_panel)
        patient_layout.setContentsMargins(2, 2, 2, 2)  # Reduced margins for more left shift
        
        self.patient_info = PatientInfoWidget()
        patient_layout.addWidget(self.patient_info)
        
        splitter.addWidget(patient_panel)
        
        # Right Panel - Monitor Chart with Time Navigation
        chart_panel = QFrame()
        chart_panel.setObjectName("chartPanel")
        chart_layout = QVBoxLayout(chart_panel)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        
        self.monitor_chart = SleepMonitorChart()
        self.monitor_chart.set_patient_id("--------")
        self.monitor_chart.raw_data_saved.connect(self.patient_info.add_saved_raw_file)
        self.monitor_chart.apnea_events_updated.connect(self.patient_info.update_detected_events_list)

        # Connect monitor chart reference to patient info for upload/save/event jump functionality
        self.patient_info.monitor_chart = self.monitor_chart

        # Connect dashboard slider to chart navigation updates
        self.monitor_chart.time_position_updated.connect(self.update_slider_position)
        self.monitor_chart.time_window_mode_changed.connect(self.update_time_navigation_controls)
        self.monitor_chart.set_dashboard_controls(self.time_window_dropdown, None)

        # Keep the time-window control aligned with any one-hour external array data.
        for index in range(self.time_window_dropdown.count()):
            if self.time_window_dropdown.itemData(index) == self.monitor_chart.current_time_window:
                self.time_window_dropdown.setCurrentIndex(index)
                break

        # If detection already exists later, mirror it in the side event list immediately
        if self.monitor_chart.auto_rule_ai_result:
            self.patient_info.update_detected_events_list(
                self.monitor_chart.auto_rule_ai_result.get("events", [])
            )

        # Update button text to show initial count
        self.graph_dropdown_button.setText("Graphs (8/8) ▼")
        
        # Use the user-activation signal so programmatic syncs do not retrigger refresh loops.
        self.time_window_dropdown.activated[int].connect(self.monitor_chart.on_time_window_changed)

        # Keep the slider controls in sync with the current mode on startup.
        self.update_time_navigation_controls(self.monitor_chart.is_all_psg_mode())
                
        chart_layout.addWidget(self.monitor_chart)
        
        # Add Time Navigation in chart panel (same size as graph containers)
        time_slider_bar = self.create_time_slider_bar()
        chart_layout.addWidget(time_slider_bar)
        
        splitter.addWidget(chart_panel)
        splitter.setSizes([300, 1000])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1) 
        
        content_layout.addWidget(splitter)
        
        # Set content widget to scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        main_layout.setContentsMargins(0, 0, 0, 0)
        
    def _create_event_nav_button(self, text, tooltip, callback, icon):
        button = QPushButton(text)
        button.setObjectName("eventNavButton")
        button.setFixedHeight(22)
        button.setFixedWidth(28)
        button.setIcon(icon)
        button.setIconSize(QSize(14, 14))
        button.setToolTip(tooltip)
        button.clicked.connect(callback)
        button.setStyleSheet("""
            QPushButton#eventNavButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #f0f9ff,
                    stop: 1 #e0f2fe
                );
                border: 1px solid #3b82f6;
                border-radius: 4px;
                color: #1e40af;
            }
            QPushButton#eventNavButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #dbeafe,
                    stop: 0.5 #bfdbfe,
                    stop: 1 #93c5fd
                );
                border: 1px solid #2563eb;
                color: #1e3a8a;
            }
            QPushButton#eventNavButton:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #93c5fd,
                    stop: 0.5 #60a5fa,
                    stop: 1 #3b82f6
                );
                border: 1px solid #1d4ed8;
                color: #ffffff;
            }
            QPushButton#eventNavButton:disabled {
                background: #f3f4f6;
                border: 1px solid #d1d5db;
                color: #9ca3af;
            }
        """)
        return button

    def create_controls_container(self):
        """Create controls container with Time Window and Hidden Graphs"""
        controls_container = QFrame()
        controls_container.setObjectName("controlsContainer")
        controls_container.setStyleSheet("""
            QFrame#controlsContainer {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 4px;
                margin: 4px 8px;
            }
        """)
        controls_layout = QHBoxLayout(controls_container)
        controls_layout.setContentsMargins(8, 4, 8, 4)
        controls_layout.setSpacing(8)
        
        # Time Window Dropdown
        time_window_label = QLabel("TIME WINDOW")
        time_window_label.setStyleSheet("font-size: 10px; color: #374151; font-weight: 800; letter-spacing: 1px;")
        controls_layout.addWidget(time_window_label)
        
        self.time_window_dropdown = QComboBox()
        self.time_window_dropdown.setObjectName("timeWindowDropdown")
        self.time_window_dropdown.setFixedHeight(22)
        self.time_window_dropdown.setMinimumWidth(60)
        
        # Add time window options (in seconds)
        time_windows = [
            ("10s", 10),
            ("30s", 30), 
            ("1m", 60),
            ("2m", 120),
            ("5m", 300),
            ("10m", 600),
            ("1h", 3600),
            ("All PSG", -1),
        ]
        for label, value in time_windows:
            self.time_window_dropdown.addItem(label, value)
        
        self.time_window_dropdown.setCurrentIndex(2)
        
        controls_layout.addWidget(self.time_window_dropdown)
        
        # Add vertical divider line
        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setFrameShadow(QFrame.Sunken)
        divider.setStyleSheet("""
            QFrame {
                background-color: #d1d5db;
                color: #d1d5db;
                border: none;
                margin: 0 4px;
            }
        """)
        divider.setFixedWidth(1)
        controls_layout.addWidget(divider)
        
        # Graph Selection Dropdown
        graphs_label = QLabel("GRAPHS")
        graphs_label.setStyleSheet("font-size: 10px; color: #374151; font-weight: 800; letter-spacing: 1px;")
        controls_layout.addWidget(graphs_label)
        
        # Create dropdown button for graph selection
        self.graph_dropdown_button = QPushButton("Select Graphs v")
        self.graph_dropdown_button.setObjectName("graphDropdownButton")
        self.graph_dropdown_button.setFixedHeight(22)
        self.graph_dropdown_button.setMinimumWidth(100)
        self.graph_dropdown_button.setStyleSheet("""
            QPushButton#graphDropdownButton {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: 600;
                color: #374151;
                text-align: left;
            }
            QPushButton#graphDropdownButton:hover {
                background-color: #f8fafc;
                border-color: #9ca3af;
            }
            QPushButton#graphDropdownButton:pressed {
                background-color: #e2e8f0;
            }
        """)
        self.graph_dropdown_button.clicked.connect(self.show_graph_selection_menu)
        
        # Store graph visibility state
        self.graph_visibility = {
            "Body Position": True ,
            "Airflow": True, 
            "Snoring": True,
            "Thorax": True,
            "Abdomen": True,
            "SpO2": True,
            "Pulse": True,
            "Body Movement": True
        }
        
        controls_layout.addWidget(self.graph_dropdown_button)
        
        # Add vertical divider line
        divider2 = QFrame()
        divider2.setFrameShape(QFrame.VLine)
        divider2.setFrameShadow(QFrame.Sunken)
        divider2.setStyleSheet("""
            QFrame {
                background-color: #d1d5db;
                color: #d1d5db;
                border: none;
                margin: 0 4px;
            }
        """)
        divider2.setFixedWidth(1)
        controls_layout.addWidget(divider2)
        
        # Screenshot Button
        self.btn_screenshot = QPushButton("📷")
        self.btn_screenshot.setObjectName("screenshotButton")
        self.btn_screenshot.setFixedSize(30, 22)
        self.btn_screenshot.setToolTip("Take Screenshot")
        self.btn_screenshot.setStatusTip("Capture entire application window")
        self.btn_screenshot.clicked.connect(self.take_screenshot)
        self.btn_screenshot.setStyleSheet("""
            QPushButton#screenshotButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #f8fafc,
                    stop: 1 #f1f5f9
                );
                border: 1px solid #d1d5db;
                border-radius: 4px;
                color: #374151;
                font-size: 14px;
                font-weight: bold;
                text-align: center;
            }
            QPushButton#screenshotButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                      stop: 0 #ffffff,
                    stop: 0.5 #dbeafe,
                    stop: 1 #bfdbfe
                );
                border: 1px solid #3b82f6;
                color: #1e40af;
            }
            QPushButton#screenshotButton:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f8fafc,
                    stop: 0.5 #e2e8f0,
                    stop: 1 #cbd5e1
                );
                border: 1px solid #94a3b8;
                color: #1e293b;
            }
        """)
        # Add vertical divider line
        divider4 = QFrame()
        divider4.setFrameShape(QFrame.VLine)
        divider4.setFrameShadow(QFrame.Sunken)
        divider4.setStyleSheet("""
            QFrame {
                background-color: #d1d5db;
                color: #d1d5db;
                border: none;
                margin: 0 4px;
            }
        """)
        divider4.setFixedWidth(1)
        controls_layout.addWidget(divider4)

        # Event Navigation Buttons
        event_label = QLabel("EVENT NAV")
        event_label.setStyleSheet("font-size: 10px; color: #374151; font-weight: 800; letter-spacing: 1px;")
        controls_layout.addWidget(event_label)

        self.btn_first_event = self._create_event_nav_button(
            text="",
            tooltip="Go to First Event",
            callback=self.navigate_to_first_event,
            icon=self.style().standardIcon(QStyle.SP_MediaSkipBackward),
        )
        controls_layout.addWidget(self.btn_first_event)

        self.btn_prev_event = self._create_event_nav_button(
            text="",
            tooltip="Go to Previous Event",
            callback=self.navigate_to_previous_event,
            icon=self.style().standardIcon(QStyle.SP_MediaSeekBackward),
        )
        controls_layout.addWidget(self.btn_prev_event)

        self.btn_next_event = self._create_event_nav_button(
            text="",
            tooltip="Go to Next Event",
            callback=self.navigate_to_next_event,
            icon=self.style().standardIcon(QStyle.SP_MediaSeekForward),
        )
        controls_layout.addWidget(self.btn_next_event)

        self.btn_last_event = self._create_event_nav_button(
            text="",
            tooltip="Go to Last Event",
            callback=self.navigate_to_last_event,
            icon=self.style().standardIcon(QStyle.SP_MediaSkipForward),
        )
        controls_layout.addWidget(self.btn_last_event)

        # Screenshot Button
        self.btn_screenshot = QPushButton("📷")
        self.btn_screenshot.setObjectName("screenshotButton")
        self.btn_screenshot.setFixedSize(35, 22)
        self.btn_screenshot.setToolTip("Take Screenshot")
        self.btn_screenshot.setStatusTip("Capture entire application window")
        self.btn_screenshot.clicked.connect(self.take_screenshot)
        self.btn_screenshot.setStyleSheet("""
            QPushButton#screenshotButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #f8fafc,
                    stop: 1 #f1f5f9
                );
                border: 1px solid #d1d5db;
                border-radius: 4px;
                color: #374151;
                font-size: 14px;
                font-weight: bold;
                text-align: center;
            }
            QPushButton#screenshotButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #dbeafe,
                    stop: 1 #bfdbfe
                );
                border: 1px solid #3b82f6;
                color: #1e40af;
            }
            QPushButton#screenshotButton:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f8fafc,
                    stop: 0.5 #e2e8f0,
                    stop: 1 #cbd5e1
                );
                border: 1px solid #94a3b8;
                color: #1e293b;
            }
        """)
        controls_layout.addWidget(self.btn_screenshot)
        
        controls_layout.addStretch()
        
        return controls_container

    def _get_effective_window_seconds(self):
        """Return the currently active visible window in seconds."""
        if hasattr(self, "monitor_chart") and self.monitor_chart:
            if hasattr(self.monitor_chart, "get_effective_time_window_seconds"):
                return self.monitor_chart.get_effective_time_window_seconds()
            value = getattr(self.monitor_chart, "current_time_window", 60)
            try:
                return max(1.0, float(value))
            except Exception:
                return 60.0
        return 60.0

    def update_time_navigation_controls(self, all_psg_mode):
        """Enable or disable time navigation controls based on PSG mode."""
        controls_enabled = not bool(all_psg_mode)

        for widget_name in ("time_slider", "slider_left_btn", "slider_right_btn"):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.setEnabled(controls_enabled)
        if controls_enabled and hasattr(self, "time_slider"):
            self.update_slider_position()
    
        
    def on_time_window_changed(self, index):
        """Handle time window dropdown change"""
        if hasattr(self, 'monitor_chart') and self.monitor_chart:
            # Get the value from dropdown item data
            seconds = self.time_window_dropdown.itemData(index)
            print(f"Debug: Dashboard on_time_window_changed called with index {index}, seconds {seconds}")
            
            # Update the chart's time window
            self.monitor_chart.set_time_window(seconds)
            print(f"Debug: Dashboard called set_time_window({seconds})")
    
        
    def show_graph_selection_menu(self):
        """Show dropdown menu with checkboxes for graph selection"""
        from PyQt5.QtWidgets import QMenu, QWidgetAction, QVBoxLayout
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 4px;
                font-size: 11px;
                color: #374151;
                min-width: 150px;
            }
            QMenu::item {
                padding: 4px 8px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #f3f4f6;
            }
        """)
        
        # Create a widget to hold checkboxes
        checkbox_widget = QWidget()
        checkbox_layout = QVBoxLayout(checkbox_widget)
        checkbox_layout.setContentsMargins(4, 4, 4, 4)
        checkbox_layout.setSpacing(2)
        
        # Add checkboxes for each graph
        for graph_name in self.graph_visibility.keys():
            # Use display name without trailing spaces for checkbox text
            display_name = graph_name.rstrip()
            checkbox = QCheckBox(display_name)
            checkbox.setChecked(self.graph_visibility[graph_name])
            checkbox.toggled.connect(lambda checked, name=graph_name: self.toggle_graph_visibility(name, checked))
            checkbox.setStyleSheet("""
                QCheckBox {
                    font-size: 10px;
                    color: #374151;
                    spacing: 8px;
                    padding: 3px;
                    font-weight: 500;
                }
                QCheckBox::indicator {
                    width: 17px;
                    height: 16px;
                    border: 2px solid #d1d5db;
                    border-radius: 3px;
                    background-color: #ffffff;
                }
                QCheckBox::indicator:hover {
                    border-color: #9ca3af;
                    background-color: #f8fafc;
                }
                QCheckBox::indicator:checked {
                    background-color: #2563eb;
                    border-color: #2563eb;
                    image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTIuNSA2TDQuNSA5TDkuNSAzIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjMiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIgZmlsbC1ydWxlPSJldmVub2RkIi8+Cjwvc3ZnPg==);
                }
                QCheckBox::indicator:checked:hover {
                    background-color: #1d4ed8;
                    border-color: #1d4ed8;
                }
            """)
            checkbox_layout.addWidget(checkbox)
        
        # Add the checkbox widget to the menu
        action = QWidgetAction(self)
        action.setDefaultWidget(checkbox_widget)
        menu.addAction(action)
        
        # Show the menu below the button
        button_rect = self.graph_dropdown_button.rect()
        global_pos = self.graph_dropdown_button.mapToGlobal(button_rect.bottomLeft())
        menu.exec_(global_pos)
    
    def toggle_graph_visibility(self, graph_name, checked):
        """Toggle graph visibility based on checkbox state"""
        self.graph_visibility[graph_name] = checked
        
        # Directly find and hide/show the chart container
        if hasattr(self, 'monitor_chart') and self.monitor_chart:
            # Find the container for this graph
            container = None
            for i in range(self.monitor_chart.charts_layout.count()):
                widget = self.monitor_chart.charts_layout.itemAt(i).widget()
                if widget and hasattr(widget, 'plot_widget'):
                    plot_widget = widget.plot_widget
                    if hasattr(plot_widget, 'chart_name'):
                        chart_name_actual = plot_widget.chart_name
                        # Try exact match first, then try without trailing spaces
                        if chart_name_actual == graph_name or chart_name_actual.strip() == graph_name.strip():
                            container = widget
                            break
            
            if container:
                if checked:
                    container.show()
                    print(f"Graph '{graph_name}' shown")
                else:
                    container.hide()
                    print(f"Graph '{graph_name}' hidden")
            else:
                print(f"Graph '{graph_name}' not found")
        
        # Update button text to show selected count
        selected_count = sum(1 for visible in self.graph_visibility.values() if visible)
        self.graph_dropdown_button.setText(f"Graphs ({selected_count}/8) ▼")
    
        
    def create_time_slider_bar(self):
        """Create time slider navigation bar with professional styling - same size as graph containers"""
        # Main container with same styling as graph containers
        main_container = QWidget()
        main_container.setObjectName("signalChartContainer")
        main_container.setMinimumHeight(35) 
        main_container.setMaximumHeight(35)
        main_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # Apply professional double-shaded medical styling to container
        main_container.setStyleSheet("""
            QWidget#signalChartContainer {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.45 #f8fafc,
                    stop: 0.55 #f1f5f9,
                    stop: 1 #e2e8f0
                );
                border: 2px solid #cbd5e1;
                border-radius: 8px;
                margin: 2px;
            }
            QWidget#signalChartContainer:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.45 #f0f9ff,
                    stop: 0.55 #e0f2fe,
                    stop: 1 #bae6fd
                );
                border: 2px solid #3b82f6;
                box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
            }
        """)
        
        # Inner layout for the container
        container_layout = QHBoxLayout(main_container)
        container_layout.setContentsMargins(4, 3, 4, 3) 
        container_layout.setSpacing(6) 
        
        # Time Position Label - smaller font
        time_label = QLabel("Time Nav:")
        time_label.setStyleSheet("font-size: 10px; font-weight: 700; color: #1e293b;")
        container_layout.addWidget(time_label)
        
        # Left navigation button - with clear arrow
        self.slider_left_btn = QPushButton("◀")
        self.slider_left_btn.setObjectName("sliderNavButton")
        self.slider_left_btn.setFixedHeight(20)  
        self.slider_left_btn.setFixedWidth(28)   
        # Apply clear arrow styling
        self.slider_left_btn.setStyleSheet("""
            QPushButton#sliderNavButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #dbeafe,
                    stop: 1 #bfdbfe
                );
                border: 2px solid #3b82f6;
                border-radius: 4px;
                color: #1e40af;
                font-size: 14px;
                font-weight: bold;
                text-align: center;
            }
            QPushButton#sliderNavButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #bfdbfe,
                    stop: 1 #93c5fd
                );
                border: 2px solid #2563eb;
                color: #1e3a8a;
            }
            QPushButton#sliderNavButton:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #dbeafe,
                    stop: 0.5 #93c5fd,
                    stop: 1 #60a5fa
                );
                border: 2px solid #1d4ed8;
                color: #1e3a8a;
            }
        """)
        self.slider_left_btn.clicked.connect(self.slider_navigate_backward)
        container_layout.addWidget(self.slider_left_btn)
        
        # Time slider - make it expand to fill available space
        self.time_slider = QSlider(Qt.Horizontal)
        self.time_slider.setObjectName("timeSlider")
        self.time_slider.setMinimum(0)
        self.time_slider.setMaximum(100)
        self.time_slider.setValue(0)
        self.time_slider.setFixedHeight(20)  
        self.time_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.time_slider.setTracking(True)
        self.slider_is_being_dragged = False
        
        # Apply custom styling to slider
        self.time_slider.setStyleSheet("""
            QSlider#timeSlider::groove:horizontal {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #f1f5f9,
                    stop: 0.5 #e2e8f0,
                    stop: 1 #cbd5e1
                );
                border: 1px solid #94a3b8;
                border-radius: 4px;
                height: 8px;
                margin: 2px 0;
            }
            QSlider#timeSlider::handle:horizontal {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #3b82f6,
                    stop: 1 #1d4ed8
                );
                border: 1px solid #1e40af;
                border-radius: 6px;
                width: 16px;
                margin: -4px 0;
            }
            QSlider#timeSlider::handle:horizontal:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #dbeafe,
                    stop: 0.5 #60a5fa,
                    stop: 1 #2563eb
                );
                border: 1px solid #1e40af;
            }
            QSlider#timeSlider::handle:horizontal:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #93c5fd,
                    stop: 0.5 #3b82f6,
                    stop: 1 #1d4ed8
                );
                border: 1px solid #1e3a8a;
            }
        """)
        
        self.time_slider.valueChanged.connect(self.on_slider_changed)
        self.time_slider.sliderPressed.connect(self.on_slider_pressed)
        self.time_slider.sliderReleased.connect(self.on_slider_released)
        container_layout.addWidget(self.time_slider, stretch=1)  # Add stretch factor
        
        # Right navigation button - with clear arrow
        self.slider_right_btn = QPushButton("▶")
        self.slider_right_btn.setObjectName("sliderNavButton")
        self.slider_right_btn.setFixedHeight(20)  
        self.slider_right_btn.setFixedWidth(28)   
        # Apply clear arrow styling
        self.slider_right_btn.setStyleSheet("""
            QPushButton#sliderNavButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #dbeafe,
                    stop: 1 #bfdbfe
                );
                border: 2px solid #3b82f6;
                border-radius: 4px;
                color: #1e40af;
                font-size: 14px;
                font-weight: bold;
                text-align: center;
            }
            QPushButton#sliderNavButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #ffffff,
                    stop: 0.5 #bfdbfe,
                    stop: 1 #93c5fd
                );
                border: 2px solid #2563eb;
                color: #1e3a8a;
            }
            QPushButton#sliderNavButton:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #dbeafe,
                    stop: 0.5 #93c5fd,
                    stop: 1 #60a5fa
                );
                border: 2px solid #1d4ed8;
                color: #1e3a8a;
            }
        """)
        self.slider_right_btn.clicked.connect(self.slider_navigate_forward)
        container_layout.addWidget(self.slider_right_btn)
        
        # Current time display - smaller
        self.slider_time_label = QLabel("0:00")
        self.slider_time_label.setObjectName("sliderTimeLabel")
        self.slider_time_label.setFixedWidth(84)
        self.slider_time_label.setStyleSheet("""
            QLabel#sliderTimeLabel {
                background-color: #eff6ff;
                color: #1e40af;
                border: 1px solid #3b82f6;
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 10px;
                min-width: 60px;
            }
        """)
        self.slider_time_label.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(self.slider_time_label)
        
        # Add stretch to push everything to the left
        container_layout.addStretch()
        
        return main_container
    
        
    def slider_navigate_backward(self):
        """Navigate backward using slider buttons"""
        
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return

        if self.monitor_chart.is_all_psg_mode():
            self.update_slider_position()
            return
        
        max_duration = self.monitor_chart._get_playback_max_duration() if hasattr(self.monitor_chart, '_get_playback_max_duration') else 0.0
        if max_duration > 0:
            # Step size equals the current time window size
            step_size = self._get_effective_window_seconds()
            
            # Move backward by step size
            self.monitor_chart.current_time_offset = max(0, self.monitor_chart.current_time_offset - step_size)
            self.monitor_chart.refresh_charts()
            self.update_slider_position()
            
            print(f"Dashboard slider backward to: {self.monitor_chart.current_time_offset:.1f}s (step: {step_size:.1f}s)")
    
    def slider_navigate_forward(self):
        """Navigate forward using slider buttons"""
        # Check if monitor chart has selection active and block if needed
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return

        if self.monitor_chart.is_all_psg_mode():
            self.update_slider_position()
            return
        
        max_duration = self.monitor_chart._get_playback_max_duration() if hasattr(self.monitor_chart, '_get_playback_max_duration') else 0.0
        if max_duration > 0:
            # Step size equals the current time window size
            step_size = self._get_effective_window_seconds()
            max_offset = self.monitor_chart._get_playback_max_offset() if hasattr(self.monitor_chart, '_get_playback_max_offset') else max(0.0, max_duration - self._get_effective_window_seconds())
            
            # Move forward by step size
            self.monitor_chart.current_time_offset = min(max_offset, self.monitor_chart.current_time_offset + step_size)
            
            #  FORCE VIEWBOX UPDATE AND PLOT REDRAW
            for i in range(self.monitor_chart.charts_layout.count()):
                container = self.monitor_chart.charts_layout.itemAt(i).widget()
                if hasattr(container, 'plot_widget'):
                    pw = container.plot_widget
                    
                    # Force X-axis range update
                    start = 0
                    end = self._get_effective_window_seconds()
                    pw.setXRange(start, end, padding=0)
                    print(f"Updated ViewBox range to {start} → {end} for {pw.chart_name}")
            
            #  DELAYED OVERLAY RENDER (IMPORTANT)
            if not self.monitor_chart.is_all_psg_mode():
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(0, self.monitor_chart.render_dynamic_selections)
            
            self.monitor_chart.refresh_charts()
            self.update_slider_position()
            
            print(f"Dashboard slider forward to: {self.monitor_chart.current_time_offset:.1f}s (step: {step_size:.1f}s)")
    
    def on_slider_changed(self, value):
        """Handle slider value change"""
        print(f"DEBUG: on_slider_changed called with value={value}, current_event_index={self.current_event_index}")
        
        max_duration = self.monitor_chart._get_playback_max_duration() if hasattr(self.monitor_chart, '_get_playback_max_duration') else 0.0
        if max_duration > 0:
            if self.monitor_chart.is_all_psg_mode():
                self.update_slider_position()
                if not self.all_events:
                    self.all_events = self.get_all_events_sorted()
                self.update_event_navigation_buttons()
                return

            slider_progress = value / 100.0
            # Normal case: there is room to slide full windows across the recording
            window_seconds = self._get_effective_window_seconds()
            if max_duration > window_seconds:
                max_offset = max_duration - window_seconds
                self.monitor_chart.current_time_offset = slider_progress * max_offset
            else:
                # Edge case: recording shorter than (or equal to) visible window.
                # Instead of forcing offset to 0, center the visible window around
                # the selected relative position so the user sees the area they chose.
                center_time = slider_progress * max_duration
                half_window = float(window_seconds) / 2.0
                desired_offset = max(0.0, center_time - half_window)
                # Ensure offset does not exceed the logical maximum (may be 0)
                self.monitor_chart.current_time_offset = min(max(0.0, desired_offset), max(0.0, max_duration - 0.0001))

            # Remember whether playback was active before the manual release
            was_playing = getattr(self.monitor_chart, 'is_playing', False)

            # Refresh and update UI (apply the requested offset)
            self.monitor_chart.refresh_charts()
            self.update_slider_position()

            # If playback was running, keep it running from the new offset
            if was_playing:
                if hasattr(self.monitor_chart, 'start_playback'):
                    try:
                        if not getattr(self.monitor_chart, 'is_playing', False):
                            self.monitor_chart.start_playback()
                    except Exception:
                        try:
                            self.monitor_chart.is_playing = True
                            self.monitor_chart.playback_timer.start(50)
                        except Exception:
                            pass
            self.all_events = self.get_all_events_sorted()
            self.update_event_navigation_buttons()
            print(f"Dashboard slider released at: {value}% (time: {self.monitor_chart.current_time_offset:.1f}s)")

    def on_slider_pressed(self):
        """Handle slider press event."""
        self.slider_is_being_dragged = True
        print("DEBUG: on_slider_pressed called")

    def on_slider_released(self):
        """Handle slider release event."""
        self.slider_is_being_dragged = False
        print("DEBUG: on_slider_released called")
        self.update_slider_position()

    def update_slider_position(self):
        """Update slider position based on current time offset"""
        if getattr(self, 'slider_is_being_dragged', False):
            return
        max_duration = self.monitor_chart._get_playback_max_duration() if hasattr(self.monitor_chart, '_get_playback_max_duration') else 0.0
        if self.time_slider and max_duration > 0:
            
            # Calculate slider value (0-100) based on current position
            window_seconds = self._get_effective_window_seconds()
            if max_duration > window_seconds:
                max_offset = max_duration - window_seconds
                slider_progress = self.monitor_chart.current_time_offset / max_offset
                slider_value = int(slider_progress * 100)
                slider_value = max(0, min(100, slider_value))  
                print(f"Debug: time_offset={self.monitor_chart.current_time_offset:.1f}s, max_duration={max_duration:.1f}s, max_offset={max_offset:.1f}s, progress={slider_progress:.3f}, slider_value={slider_value}")
                
                # Block signals to prevent recursive calls
                self.time_slider.blockSignals(True)
                self.time_slider.setValue(slider_value)
                self.time_slider.blockSignals(False)
                
                print(f"Slider position updated: {slider_value}% (time: {self.monitor_chart.current_time_offset:.1f}s)")
            
            def format_time(value):
                hours = int(value // 3600)
                minutes = int((value % 3600) // 60)
                seconds = int(value % 60)
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            visible_end = min(
                self.monitor_chart.current_time_offset
                + self._get_effective_window_seconds(),
                max_duration,
            )
            displayed_time = (
                max_duration
                if visible_end >= max_duration
                else self.monitor_chart.current_time_offset
            )
            self.slider_time_label.setText(format_time(displayed_time))
            
    def load_stylesheet(self):
        """Load QSS stylesheet"""
        
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        qss_file = os.path.join(script_dir, "sleep_sense_medical_white.qss")
        
        # Start with toolbar styles
        stylesheet = get_toolbar_qss_styles()
        
        
        if os.path.exists(qss_file):
            with open(qss_file, 'r') as f:
                stylesheet += f.read()
        else:
            print(f"Warning: Stylesheet file '{qss_file}' not found!")
        
        self.setStyleSheet(stylesheet)
    
    def create_professional_toolbar(self):
        """Create professional icon toolbar with grouped buttons"""
        toolbar = QToolBar("MainToolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(32, 32))
        toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        toolbar.setMinimumHeight(50)
        
        # Get icon definitions
        icons = get_icon_definitions()
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Navigation Group: Previous / Next
        self.btn_previous = create_toolbar_button(
            os.path.join(script_dir, icons[0]["icon"]),
            icons[0]["tooltip"],
            icons[0]["status_tip"],
            self.go_to_previous
        )
        toolbar.addWidget(self.btn_previous)
        
        self.btn_next = create_toolbar_button(
            os.path.join(script_dir, icons[1]["icon"]),
            icons[1]["tooltip"],
            icons[1]["status_tip"],
            self.go_to_next
        )
        toolbar.addWidget(self.btn_next)
        
        toolbar.addSeparator()
        
        # Device Group: Prepare / Download
        self.btn_prepare_device = create_toolbar_button(
            os.path.join(script_dir, icons[2]["icon"]),
            icons[2]["tooltip"],
            icons[2]["status_tip"],
            self.prepare_device
        )
        toolbar.addWidget(self.btn_prepare_device)
        
        self.btn_download_data = create_toolbar_button(
            os.path.join(script_dir, icons[3]["icon"]),
            icons[3]["tooltip"],
            icons[3]["status_tip"],
            self.download_data
        )
        self.btn_download_data.setEnabled(False)  
        toolbar.addWidget(self.btn_download_data)
        
        
        # Data Group: Database / Archive
        self.btn_database = create_toolbar_button(
            os.path.join(script_dir, icons[4]["icon"]),
            icons[4]["tooltip"],
            icons[4]["status_tip"],
            self.open_database
        )
        toolbar.addWidget(self.btn_database)
        
        self.btn_archive = create_toolbar_button(
            os.path.join(script_dir, icons[8]["icon"]),
            icons[8]["tooltip"],
            icons[8]["status_tip"],
            self.open_archive
        )
        toolbar.addWidget(self.btn_archive)
        
        toolbar.addSeparator()
        
        # Extended Database Options (initially hidden - using QAction)
        from PyQt5.QtGui import QIcon
        
        self.action_patient_record = QAction(QIcon(os.path.join(script_dir, "icons/patient_report_card.svg")), "Patient Record Card", self)
        self.action_patient_record.setToolTip("Patient Record Card")
        self.action_patient_record.setStatusTip("Open Patient Record Card Form")
        self.action_patient_record.triggered.connect(self.open_patient_report_card)
        self.action_patient_record.setVisible(False)
        self.action_patient_record.setEnabled(True)
        toolbar.addAction(self.action_patient_record)
                
        self.action_medical_report = QAction(QIcon(os.path.join(script_dir, "icons/medical_report.svg")), "Medical Report", self)
        self.action_medical_report.setToolTip("Medical Report")
        self.action_medical_report.setStatusTip("Open Medical Report Form")
        self.action_medical_report.triggered.connect(self.open_medical_report)
        self.action_medical_report.setVisible(False)
        self.action_medical_report.setEnabled(True)
        toolbar.addAction(self.action_medical_report)
        
        self.action_event_list = QAction(QIcon(os.path.join(script_dir, icons[7]["icon"])), "Event List", self)
        self.action_event_list.setToolTip("Event List")
        self.action_event_list.setStatusTip("View detected events")
        self.action_event_list.triggered.connect(self.open_event_list)
        self.action_event_list.setVisible(False)
        self.action_event_list.setEnabled(True)
        toolbar.addAction(self.action_event_list)
        
        return toolbar
    
    # Toolbar Button Callback Methods
    def go_to_previous(self):
        """Go to previous time window"""
        print("Previous button clicked")
        self.hide_extended_buttons()
        if self.monitor_chart.is_all_psg_mode():
            self.update_slider_position()
            return
        if hasattr(self.monitor_chart, '_get_playback_max_duration') and self.monitor_chart._get_playback_max_duration() > 0:
            step_size = self._get_effective_window_seconds()
            self.monitor_chart.current_time_offset = max(0, self.monitor_chart.current_time_offset - step_size)
            self.monitor_chart.refresh_charts()
            self.update_slider_position()
            print(f"Toolbar previous: offset={self.monitor_chart.current_time_offset:.1f}s")
    
    def go_to_next(self):
        """Go to next time window"""
        print("Next button clicked")
        self.hide_extended_buttons()
        if self.monitor_chart.is_all_psg_mode():
            self.update_slider_position()
            return
        max_duration = self.monitor_chart._get_playback_max_duration() if hasattr(self.monitor_chart, '_get_playback_max_duration') else 0.0
        if max_duration > 0:
            step_size = self._get_effective_window_seconds()
            max_offset = self.monitor_chart._get_playback_max_offset() if hasattr(self.monitor_chart, '_get_playback_max_offset') else max(0.0, max_duration - self._get_effective_window_seconds())
            self.monitor_chart.current_time_offset = min(max_offset, self.monitor_chart.current_time_offset + step_size)
            self.monitor_chart.refresh_charts()
            self.update_slider_position()
            print(f"Toolbar next: offset={self.monitor_chart.current_time_offset:.1f}s") 
    
    def prepare_device(self):
        """Initialize and connect device"""
        print("Prepare Device button clicked")
        self.hide_extended_buttons()
        # TODO: Implement device preparation logic
   
        self.btn_download_data.setEnabled(True)
    
    def download_data(self):
        """Download data from device"""
        # Check if monitor chart has selection active and block if needed
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return
        
        print("Download Data button clicked")
        # TODO: Implement data download logic
    
    def open_database(self):
        """Open patient database as modeless window and show extended buttons"""
        # Check if monitor chart has selection active and block if needed
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return
        
        print("Database button clicked")
        # Show extended buttons immediately
        self.action_patient_record.setVisible(True)
        self.action_medical_report.setVisible(True)
        self.action_event_list.setVisible(True)
        # Open database window as modeless (non-blocking)
        self.database_window = DatabaseWindow(self)
        self.database_window.show()
    
    def hide_extended_buttons(self):
        """Hide extended database buttons"""
        self.action_patient_record.setVisible(False)
        self.action_medical_report.setVisible(False)
        self.action_event_list.setVisible(False)  
    
    def open_archive(self):
        """Access archived records as modal dialog"""
        # Check if monitor chart has selection active and block if needed
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return
        
        print("Archive button clicked")
        self.hide_extended_buttons()
        self.archive_window = ArchiveWindow(self)
        self.archive_window.exec_()  # Modal dialog
    
    def open_patient_report_card(self):
        """Open Patient Report Card Form as modal dialog"""
        # Check if monitor chart has selection active and block if needed
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return
        
        print("Patient Report Card button clicked")
        # Import the patient record form
        from .patient_record_form import PatientRecordForm
        
        # Create and show the patient record form as modal dialog
        self.patient_record_form = PatientRecordForm(self)
        self.patient_record_form.exec_()  # Modal dialog
    
    def open_medical_report(self):
        """Generate Medical Report and show in internal viewer"""
        # Check if monitor chart has selection active and block if needed
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return
        
        print("Medical Report button clicked")
        # Import the medical report generation function and PDF viewer
        from .medical_report_form import generate_sleep_report, PDFViewerWidget
        
        # Generate the report and show in internal viewer
        try:
            screenshot_paths = list(getattr(self, 'dashboard_screenshot_paths', []))
            pdf_path = generate_sleep_report(
                dashboard_screenshot_path=screenshot_paths if screenshot_paths else None
            )
            print("✅ Medical report generated successfully!")
            
            # Show PDF in internal viewer
            self.pdf_viewer = PDFViewerWidget(pdf_path, self)
            self.pdf_viewer.exec_()
            
        except Exception as e:
            print(f"❌ Error generating medical report: {str(e)}")
    
    def load_patient_data(self, patient_data):
        """Load patient data from database and display in dashboard"""
        print(f"Loading patient data: {patient_data['last_name']} {patient_data['first_name']}")
        self.current_patient_data = dict(patient_data)
        
        # Create patient ID string for display
        patient_id_str = patient_data.get('patient_id', str(patient_data.get('id', '--------')))
        
        # Set patient ID in monitor chart
        if hasattr(self, 'monitor_chart'):
            self.monitor_chart.set_patient_id(patient_id_str)
        
        # Update patient info widget
        if hasattr(self, 'patient_info'):
            self.patient_info.set_patient_data({
                'last_name': patient_data.get('last_name', ''),
                'first_name': patient_data.get('first_name', ''),
                'dob': patient_data.get('dob', ''),
                'patient_id': patient_id_str
            })
        
        print(f"Patient data loaded successfully in dashboard")
    
    def open_signal_view(self):
        """View live physiological signals"""
        # Check if monitor chart has selection active and block if needed
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return
        
        print("Signal View button clicked")
        # TODO: Implement signal view logic
    
    def open_event_list(self):
        """View detected events"""
        # Check if monitor chart has selection active and block if needed
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return
        
        print("Event List button clicked")
        self.event_window = EventWindow(self)
        self.event_window.exec_()  # Modal dialog
    
    def take_screenshot(self):
        """Take a screenshot of the entire application"""
        try:
            # Get the main window
            from PyQt5.QtWidgets import QApplication
            from PyQt5.QtGui import QPixmap, QScreen
            from datetime import datetime
            import tempfile
            
            source_pixmap = self.grab()
            if source_pixmap.isNull():
                QMessageBox.warning(self, "Screenshot Error", "Dashboard screenshot capture failed.")
                return

            if hasattr(self, 'screenshot_overlay') and self.screenshot_overlay:
                try:
                    self.screenshot_overlay.close()
                except Exception:
                    pass

            self._screenshot_source_pixmap = source_pixmap
            overlay = ScreenshotOverlayWidget(source_pixmap, self)
            overlay.setGeometry(self.rect())
            overlay.overlay_ratio_x = source_pixmap.width() / max(1, overlay.width())
            overlay.overlay_ratio_y = source_pixmap.height() / max(1, overlay.height())

            def finish_capture(selected_rect):
                cropped_pixmap = source_pixmap.copy(selected_rect)
                if cropped_pixmap.isNull():
                    QMessageBox.warning(self, "Screenshot Error", "No valid area was selected.")
                    overlay.close()
                    return

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_path = os.path.join(
                    tempfile.gettempdir(),
                    f"sleep_sense_dashboard_screenshot_{timestamp}.png"
                )

                if not cropped_pixmap.save(file_path, "PNG"):
                    QMessageBox.warning(self, "Screenshot Error", "Selected area screenshot could not be saved.")
                    overlay.close()
                    return

                self.dashboard_screenshot_paths.append(file_path)
                overlay.close()
                self.show_screenshot_actions(file_path)

            def cancel_capture():
                overlay.close()

            overlay.selection_confirmed.connect(finish_capture)
            overlay.cancelled.connect(cancel_capture)
            overlay.destroyed.connect(lambda: setattr(self, 'screenshot_overlay', None))

            self.screenshot_overlay = overlay
            overlay.show()
            overlay.raise_()
            overlay.activateWindow()
            overlay.setFocus()
        except Exception as e:
            QMessageBox.critical(self, "Screenshot Error", 
                               f"Failed to take screenshot:\n{str(e)}")

    def show_screenshot_actions(self, file_path):
        """Show the screenshot preview with report/delete actions only."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Dashboard Screenshot")
        dialog.setModal(True)
        dialog.resize(900, 600)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        preview_label = QLabel()
        preview_label.setAlignment(Qt.AlignCenter)
        preview_label.setStyleSheet("background-color: #f8fafc; border: 1px solid #d1d5db;")

        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            preview_label.setPixmap(
                pixmap.scaled(860, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            preview_label.setText("Screenshot preview is not available.")

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        send_button = QPushButton("Send to Report")
        send_button.setFixedSize(130, 32)
        send_button.clicked.connect(dialog.accept)

        delete_button = QPushButton("Delete Screenshot")
        delete_button.setFixedSize(140, 32)
        delete_button.clicked.connect(lambda: self.delete_screenshot_and_close(file_path, dialog))

        button_layout.addWidget(send_button)
        button_layout.addWidget(delete_button)

        layout.addWidget(preview_label)
        layout.addLayout(button_layout)
        dialog.exec_()

    def delete_screenshot_and_close(self, file_path, dialog):
        """Delete the previewed screenshot and close the preview dialog."""
        self.remove_dashboard_screenshot(file_path, show_message=False)
        dialog.reject()

    def remove_dashboard_screenshot(self, file_path=None, show_message=True):
        """Remove one or all pending dashboard screenshots from the report flow."""
        paths_to_remove = [file_path] if file_path else list(self.dashboard_screenshot_paths)
        for path in paths_to_remove:
            if path in self.dashboard_screenshot_paths:
                self.dashboard_screenshot_paths.remove(path)
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError as error:
                    print(f"⚠️ Could not remove dashboard screenshot: {error}")

        if not file_path:
            self.dashboard_screenshot_paths = []

        if show_message:
            QMessageBox.information(
                self,
                "Screenshot Removed",
                f"Screenshot removed. Pending screenshots: {len(self.dashboard_screenshot_paths)}"
            )

    def clear_dashboard_screenshots(self):
        """Remove all pending dashboard screenshots."""
        for screenshot_path in list(self.dashboard_screenshot_paths):
            try:
                if os.path.exists(screenshot_path):
                    os.remove(screenshot_path)
            except OSError as error:
                print(f"⚠️ Could not remove dashboard screenshot: {error}")
        self.dashboard_screenshot_paths = []
        QMessageBox.information(self, "Screenshots Removed", "All dashboard screenshots were removed from the report queue.")
    
    def create_menubar(self):
        """Create menubar with File and View menus"""
        menubar = self.menuBar()
        menubar.setObjectName("mainMenuBar")
        
        # File menu
        file_menu = menubar.addMenu('File')
        
        # View menu and wire to handlers in button_functions
        view_menu = menubar.addMenu('View')

        fullscreen_action = QAction('Fullscreen', self)
        fullscreen_action.setCheckable(True)
        fullscreen_action.setStatusTip('Toggle fullscreen')
        fullscreen_action.triggered.connect(self.button_functions.view_fullscreen)
        view_menu.addAction(fullscreen_action)

        view_menu.addSeparator()

        zoom_in_action = QAction('Zoom In', self)
        zoom_in_action.setShortcut('Ctrl++')
        zoom_in_action.triggered.connect(self.button_functions.view_zoom_in)
        view_menu.addAction(zoom_in_action)

        zoom_out_action = QAction('Zoom Out', self)
        zoom_out_action.setShortcut('Ctrl+-')
        zoom_out_action.triggered.connect(self.button_functions.view_zoom_out)
        view_menu.addAction(zoom_out_action)

        reset_zoom_action = QAction('Reset Zoom', self)
        reset_zoom_action.setShortcut('Ctrl+0')
        reset_zoom_action.triggered.connect(self.button_functions.view_reset_zoom)
        view_menu.addAction(reset_zoom_action)

        view_menu.addSeparator()

        report_view_action = QAction('Report view', self)
        report_view_action.triggered.connect(self.button_functions.view_report_view)
        view_menu.addAction(report_view_action)

        signal_view_action = QAction('Signal view', self)
        signal_view_action.triggered.connect(self.button_functions.view_signal_view)
        view_menu.addAction(signal_view_action)

        event_list_action = QAction('Event list', self)
        event_list_action.triggered.connect(self.button_functions.view_event_list)
        view_menu.addAction(event_list_action)
    
    def start_auto_playback(self):
        """Playback is intentionally manual only."""
        if hasattr(self, "monitor_chart"):
            self.monitor_chart.skip_next_auto_playback = False
        print("Auto-playback disabled. Use Play/Pause manually.")

    def get_all_events_sorted(self):
        """Gather all events from dynamic_selections and sort chronologically"""
        all_events = []

        if hasattr(self.monitor_chart, "get_available_navigation_events"):
            for selection in self.monitor_chart.get_available_navigation_events():
                all_events.append({
                    "chart_name": "Airflow",
                    "label": selection.get("final_label") or selection.get("rule_label") or selection.get("label", "Unknown"),
                    "start_time": selection.get("start_sec", selection.get("start_time", 0)),
                    "end_time": selection.get("end_sec", selection.get("end_time", 0)),
                    "color": selection.get("color", "#ff0000"),
                })
            if all_events:
                all_events.sort(key=lambda x: x["start_time"])
                return all_events
        
        if hasattr(self.monitor_chart, 'dynamic_selections'):
            # Iterate through all charts and their dynamic selections
            for chart_name, selections in self.monitor_chart.dynamic_selections.items():
                for selection in selections:
                    # Create event object with essential information
                    event = {
                        'chart_name': chart_name,
                        'label': selection.get('label', 'Unknown'),
                        'start_time': selection.get('start_time', 0),
                        'end_time': selection.get('end_time', 0),
                        'color': selection.get('color', '#ff0000')
                    }
                    all_events.append(event)
        
        # Sort events by start_time (chronological order)
        all_events.sort(key=lambda x: x['start_time'])
        
        return all_events

    def navigate_to_next_event(self):
        """Navigate to the next event that is NOT currently visible on screen"""
        # Check if monitor chart has selection active and block if needed
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return

        if self.monitor_chart.is_all_psg_mode():
            if not self.all_events:
                self.all_events = self.get_all_events_sorted()
            self.update_event_navigation_buttons()
            return
        
        # Refresh the event list to get current events
        self.all_events = self.get_all_events_sorted()
        
        if not self.all_events:
            print("No events found for navigation")
            return
        
        # Get current viewport range
        viewport_start = self.monitor_chart.current_time_offset
        viewport_end = viewport_start + self._get_effective_window_seconds()
        
        # Find the first event that is OUTSIDE the current viewport (after viewport_end)
        next_event_index = -1
        for i, event in enumerate(self.all_events):
            if event['start_time'] > viewport_end:
                next_event_index = i
                break
        
        if next_event_index != -1:
            # Found an event outside viewport, navigate to it
            self.current_event_index = next_event_index
            self.go_to_event(self.current_event_index)
            print(f"Navigated to next visible event (index {self.current_event_index}) at {self.all_events[next_event_index]['start_time']:.1f}s")
        else:
            print("No more events ahead - all remaining events are visible")

    def navigate_to_first_event(self):
        """Navigate to the first event in the data"""
        # Check if monitor chart has selection active and block if needed
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return

        if self.monitor_chart.is_all_psg_mode():
            if not self.all_events:
                self.all_events = self.get_all_events_sorted()
            self.current_event_index = 0
            self.update_event_navigation_buttons()
            return
        
        # Refresh the event list to get current events
        self.all_events = self.get_all_events_sorted()
        
        if not self.all_events:
            print("No events found for navigation")
            return
        
        # Navigate to first event (index 0)
        self.current_event_index = 0
        self.go_to_event(self.current_event_index)
        print(f"Navigated to first event (index {self.current_event_index}) at {self.all_events[0]['start_time']:.1f}s")

    def navigate_to_previous_event(self):
        """Navigate to the previous event that is NOT currently visible on screen"""
        # Check if monitor chart has selection active and block if needed
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return

        if self.monitor_chart.is_all_psg_mode():
            if not self.all_events:
                self.all_events = self.get_all_events_sorted()
            self.update_event_navigation_buttons()
            return
        
        # Refresh the event list to get current events
        self.all_events = self.get_all_events_sorted()
        
        if not self.all_events:
            print("No events found for navigation")
            return
        
        # Get current viewport range
        viewport_start = self.monitor_chart.current_time_offset
        viewport_end = viewport_start + self._get_effective_window_seconds()
        
        # Find the first event that is OUTSIDE the current viewport (before viewport_start)
        # Search in reverse order
        prev_event_index = -1
        for i in range(len(self.all_events) - 1, -1, -1):
            event = self.all_events[i]
            if event['end_time'] < viewport_start:
                prev_event_index = i
                break
        
        if prev_event_index != -1:
            # Found an event outside viewport, navigate to it
            self.current_event_index = prev_event_index
            self.go_to_event(self.current_event_index)
            print(f"Navigated to previous visible event (index {self.current_event_index}) at {self.all_events[prev_event_index]['start_time']:.1f}s")
        else:
            print("No more events behind - all previous events are visible")

    def navigate_to_last_event(self):
        """Navigate to the last event in the data"""
        # Check if monitor chart has selection active and block if needed
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return

        if self.monitor_chart.is_all_psg_mode():
            if not self.all_events:
                self.all_events = self.get_all_events_sorted()
            self.current_event_index = max(0, len(self.all_events) - 1)
            self.update_event_navigation_buttons()
            return

        self.all_events = self.get_all_events_sorted()
        if not self.all_events:
            print("No events found for navigation")
            return

        # Navigate to last event (index len-1)
        self.current_event_index = len(self.all_events) - 1
        self.go_to_event(self.current_event_index)
        print(f"Navigated to last event (index {self.current_event_index}) at {self.all_events[-1]['start_time']:.1f}s")

    def go_to_event(self, event_index):
        """Navigate to a specific event by index - syncs all charts and time slider"""
        if event_index < 0 or event_index >= len(self.all_events):
            print(f"Invalid event index: {event_index}")
            return
        
        event = self.all_events[event_index]
        event_time = event['start_time']
        
        # Calculate viewport window size (center the event)
        window_size = self._get_effective_window_seconds()
        # Position event at center of viewport (offset = event_time - window_size/2)
        requested_offset = max(0, event_time - window_size / 2)
        max_offset = self.monitor_chart._get_playback_max_offset() if hasattr(self.monitor_chart, '_get_playback_max_offset') else requested_offset
        new_offset = min(max_offset, requested_offset)
        
        # Update monitor chart time offset
        self.monitor_chart.current_time_offset = new_offset
        # Full PSG already shows the whole recording, so avoid expensive redraws.
        if not self.monitor_chart.is_all_psg_mode():
            self.monitor_chart.refresh_charts()
        
        # Sync time navigation slider
        self.update_slider_position()
        
        # Update button states (enable/disable based on position)
        self.update_event_navigation_buttons()
        
        print(f"Jumped to event '{event['label']}' at {event_time:.1f}s (offset: {new_offset:.1f}s)")

    def update_event_navigation_buttons(self):
        """Update event navigation button states based on current position"""
        print(f"DEBUG update_event_navigation_buttons: all_events count={len(self.all_events)}, current_event_index={self.current_event_index}")
        
        # Always enable buttons regardless of events
        # User wants buttons permanently enabled
        self.btn_first_event.setEnabled(True)
        self.btn_prev_event.setEnabled(True)
        self.btn_next_event.setEnabled(True)
        self.btn_last_event.setEnabled(True)
        print(f"DEBUG: All navigation buttons enabled (permanently)")

    def auto_load_psg_data(self):
        """Keep startup neutral; graphs should come from the user-selected upload."""
        print("ℹ️ Auto-load disabled. Upload/select a PSG CSV file to plot its data.")
    
    def load_psg_data_from_file(self):
        """Open file dialog to select and load PSG data file"""
        from PyQt5.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select PSG Data File",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            print(f"🎬 Loading PSG data from: {file_path}")
            self.monitor_chart.skip_next_auto_playback = True
            self.monitor_chart.load_psg_data_and_detect(file_path)
            print("✅ PSG data loaded successfully - Playback ready!")
