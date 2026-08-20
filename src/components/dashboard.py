"""
Sleep Sense Dashboard - Main Dashboard Component
"""

import os
import tempfile
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QSplitter, QSizePolicy, QScrollArea,
    QSplitterHandle, QSlider, QPushButton, QMenuBar, QMenu, QAction, QComboBox, QToolBar, QFileDialog, QMessageBox, QCheckBox, QStyle, QGraphicsOpacityEffect
)
from PyQt5.QtCore import Qt, QSize, QPoint, QRect, pyqtSignal, QUrl, QEvent
from PyQt5.QtGui import QFont, QPixmap, QPainter, QColor, QPen, QDesktopServices

from .patient_info_widget import PatientInfoWidget
from .sleep_monitor_chart import SleepMonitorChart
from .database_window import DatabaseWindow
# from .archive_window import ArchiveWindow
# from .event_window import EventWindow
from ..utils.toolbar_utils import create_toolbar_button, get_icon_definitions, get_toolbar_qss_styles
from ..utils.dialog_helpers import show_styled_warning
from ..utils.database_manager import DatabaseManager
from src.utils.button_functions import ButtonFunctions
from ..utils.app_paths import get_resource_path as get_asset_path
from ..utils.report_metrics_calculator import calculate_report_context


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


# Patient panel width settings
PATIENT_PANEL_RAIL_WIDTH = 40
PATIENT_PANEL_OPEN_WIDTH = 380
PATIENT_PANEL_SNAP_WIDTH = 240

# Database icons stay invisible until Database is active.
DATABASE_ICON_INACTIVE_OPACITY = 0.0


class CollapsedPanelRail(QFrame):
    """Rail shown when the patient panel is collapsed."""

    def __init__(self, title="PATIENT PANEL", parent=None):
        super().__init__(parent)
        self.setObjectName("patientRail")
        self.rail_title = title
        self.hover_active = False
        self.on_expand = None
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Click to reopen the patient panel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("""
            QFrame#patientRail {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ffffff, stop:1 #e8eef6);
                border: 1px solid #cbd5e1;
                border-left: 3px solid #2563eb;
                border-radius: 6px;
            }
        """)

    def enterEvent(self, event):
        self.hover_active = True
        self.update()

    def leaveEvent(self, event):
        self.hover_active = False
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and callable(self.on_expand):
            self.on_expand()
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        rail_w = self.width()
        rail_h = self.height()
        accent_color = QColor(29, 78, 216) if self.hover_active else QColor(37, 99, 235)

        chip_rect = QRect(int((rail_w - 24) / 2), 10, 24, 24)
        painter.setPen(Qt.NoPen)
        painter.setBrush(accent_color)
        painter.drawRoundedRect(chip_rect, 5, 5)

        arrow_font = QFont()
        arrow_font.setPointSize(9)
        arrow_font.setBold(True)
        painter.setFont(arrow_font)
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.drawText(chip_rect, Qt.AlignCenter, "▶")

        painter.save()
        painter.translate(rail_w / 2.0, rail_h / 2.0 + 18)
        painter.rotate(-90)
        title_font = QFont()
        title_font.setPointSize(8)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QPen(QColor(51, 65, 85) if self.hover_active else QColor(100, 116, 139)))
        text_width = max(0, rail_h - 100)
        painter.drawText(
            QRect(int(-text_width / 2), -10, text_width, 20),
            Qt.AlignCenter,
            self.rail_title,
        )
        painter.restore()

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(148, 163, 184, 160))
        for offset_y in (-6, 0, 6):
            painter.drawEllipse(int(rail_w / 2 - 1.5), int(rail_h - 28 + offset_y), 3, 3)

        painter.end()


class PanelSplitterHandle(QSplitterHandle):
    """Visible grip handle that makes panel dragging obvious."""

    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setCursor(Qt.SplitHCursor)
        self.hover_active = False
        self.setToolTip("Drag to change panel width • Double-click to hide/show")

    def enterEvent(self, event):
        self.hover_active = True
        self.update()

    def leaveEvent(self, event):
        self.hover_active = False
        self.update()

    def mouseDoubleClickEvent(self, event):
        toggle_callback = getattr(self.splitter(), "on_handle_double_clicked", None)
        if callable(toggle_callback):
            toggle_callback()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        handle_w = self.width()
        handle_h = self.height()
        center_x = handle_w / 2.0
        center_y = handle_h / 2.0

        track_color = QColor(59, 130, 246, 60) if self.hover_active else QColor(148, 163, 184, 70)
        painter.setPen(Qt.NoPen)
        painter.setBrush(track_color)
        painter.drawRoundedRect(int(center_x - 1.5), 6, 3, max(0, handle_h - 12), 2, 2)

        capsule_w = 8
        capsule_h = 54
        capsule_color = QColor(37, 99, 235) if self.hover_active else QColor(203, 213, 225)
        painter.setBrush(capsule_color)
        painter.drawRoundedRect(
            int(center_x - capsule_w / 2),
            int(center_y - capsule_h / 2),
            capsule_w,
            capsule_h,
            4,
            4,
        )

        dot_color = QColor(255, 255, 255) if self.hover_active else QColor(100, 116, 139)
        painter.setBrush(dot_color)
        for offset_y in (-8, 0, 8):
            painter.drawEllipse(int(center_x - 1.5), int(center_y + offset_y - 1.5), 3, 3)

        painter.end()


class PanelSplitter(QSplitter):
    """QSplitter with a custom visible handle."""

    def createHandle(self):
        return PanelSplitterHandle(self.orientation(), self)


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

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.SubWindow)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(False)
        self.setMouseTracking(True)
        self.setCursor(Qt.CrossCursor)
        self.setFocusPolicy(Qt.StrongFocus)

        self.overlay_ratio_x = 1.0
        self.overlay_ratio_y = 1.0
        self._drag_start_in_footer = False

    def showEvent(self, event):
        super().showEvent(event)
        self.setFocus()
        self.overlay_ratio_x = (
            self.source_pixmap.width() / self.width()
            if self.width() > 0
            else 1.0
        )
        self.overlay_ratio_y = (
            self.source_pixmap.height() / self.height()
            if self.height() > 0
            else 1.0
        )

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

    def _clamp_pos(self, pos):
        bounds = self.rect()
        if bounds.isNull():
            return pos
        return QPoint(
            max(bounds.left(), min(pos.x(), bounds.right())),
            max(bounds.top(), min(pos.y(), bounds.bottom())),
        )

    def _header_rect(self):
        width = min(560, max(320, self.width() - 48))
        return QRect((self.width() - width) // 2, 16, width, 64)

    def _footer_rect(self):
        width = min(390, max(340, self.width() - 48))
        return QRect(self.width() - width - 18, self.height() - 100, width, 72)

    def _capture_button_rect(self):
        footer = self._footer_rect()
        return QRect(footer.right() - 178, footer.y() + 28, 160, 34)

    def _cancel_button_rect(self):
        footer = self._footer_rect()
        return QRect(footer.right() - 350, footer.y() + 28, 152, 34)

    def _drag_drop_icon_pixmap(self):
        """Create a small blue drag/drop-style icon for warning dialogs."""
        pixmap = QPixmap(48, 48)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#3b82f6"))
        painter.drawEllipse(4, 4, 40, 40)

        pen = QPen(QColor("white"))
        pen.setWidth(3)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)

        painter.drawLine(24, 12, 24, 36)
        painter.drawLine(24, 12, 18, 18)
        painter.drawLine(24, 12, 30, 18)
        painter.drawLine(24, 36, 18, 30)
        painter.drawLine(24, 36, 30, 30)
        painter.drawLine(12, 24, 36, 24)
        painter.drawLine(12, 24, 18, 18)
        painter.drawLine(12, 24, 18, 30)
        painter.drawLine(36, 24, 30, 18)
        painter.drawLine(36, 24, 30, 30)
        painter.end()
        return pixmap

    def _is_control_zone(self, pos):
        return self._header_rect().contains(pos) or self._footer_rect().contains(pos)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        header = self._header_rect()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#d3e2ff"))
        painter.drawRoundedRect(header, 12, 12)

        painter.setPen(QColor("#96b4ea"))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(header, 12, 12)

        title_font = painter.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 1)

        hint_font = painter.font()
        hint_font.setBold(True)

        painter.setFont(title_font)
        painter.setPen(QColor("#0f172a"))
        painter.drawText(header.adjusted(18, 8, -18, -34), Qt.AlignCenter,
                         "Select screenshot area")
        painter.setFont(hint_font)
        painter.setPen(QColor("#475569"))
        painter.drawText(header.adjusted(18, 32, -18, -10), Qt.AlignCenter,
                         "Drag to select. Release mouse, then click Capture Selected Area.")

        rect = self.selection_rect()
        if not rect.isNull():
            painter.fillRect(rect, QColor(59, 130, 246, 60))
            pen = QPen(QColor(59, 130, 246))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(rect)

        footer = self._footer_rect()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#d3e2ff"))
        painter.drawRoundedRect(footer, 12, 12)

        painter.setPen(QColor("#96b4ea"))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(footer, 12, 12)

        hint_rect = QRect(footer.left() + 12, footer.top() + 8, footer.width() - 24, 16)
        painter.setFont(hint_font)
        painter.setPen(QColor("#334155"))
        painter.drawText(hint_rect, Qt.AlignCenter | Qt.AlignVCenter,
                         "Use the buttons below to confirm or cancel.")

        capture_rect = self._capture_button_rect()
        cancel_rect = self._cancel_button_rect()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#2563eb"))
        painter.drawRoundedRect(capture_rect, 8, 8)
        painter.setPen(QColor("white"))
        painter.drawText(capture_rect, Qt.AlignCenter, "Capture Selected Area")

        painter.setBrush(QColor("#eef2f7"))
        painter.drawRoundedRect(cancel_rect, 8, 8)
        painter.setPen(QColor("#334155"))
        painter.drawText(cancel_rect, Qt.AlignCenter, "Cancel")

    def mousePressInFooter(self, pos):
        capture_rect = self._capture_button_rect()
        cancel_rect = self._cancel_button_rect()
        if capture_rect.contains(pos):
            return "capture"
        if cancel_rect.contains(pos):
            return "cancel"
        return None

    def _update_cursor_for_pos(self, pos):
        action = self.mousePressInFooter(pos)
        if action in ("capture", "cancel"):
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.CrossCursor)

    def mousePressEvent(self, event):
        action = self.mousePressInFooter(event.pos())
        if action == "capture":
            rect = self.source_selection_rect()
            if rect.isNull() or rect.width() <= 5 or rect.height() <= 5:
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Select Area")
                msg_box.setText("Please drag to select a screenshot area first.")
                msg_box.setIconPixmap(self._drag_drop_icon_pixmap())
                msg_box.setStyleSheet("""
                    QMessageBox {
                        background-color: #f8fbff;
                    }
                    QMessageBox QLabel {
                        color: #111827;
                        font-size: 13px;
                        font-weight: 500;
                    }
                    QMessageBox QPushButton {
                        min-width: 54px;
                        min-height: 22px;
                        padding: 4px 12px;
                        border-radius: 6px;
                        border: 1px solid #1d4ed8;
                        background-color: #2563eb;
                        color: white;
                        font-size: 11px;
                        font-weight: 700;
                    }
                    QMessageBox QPushButton:hover {
                        background-color: #3b82f6;
                        border: 1px solid #1e40af;
                    }
                    QMessageBox QPushButton:pressed {
                        background-color: #1e40af;
                        border: 1px solid #1e3a8a;
                    }
                """)
                ok_button = msg_box.button(QMessageBox.Ok)
                if ok_button is not None:
                    ok_button.setAutoDefault(False)
                    ok_button.setDefault(True)
                    ok_button.setStyleSheet("""
                        QPushButton {
                            min-width: 54px;
                            min-height: 22px;
                            padding: 4px 12px;
                            border-radius: 6px;
                            border: 1px solid #1d4ed8;
                            background-color: #2563eb;
                            color: white;
                            font-size: 11px;
                            font-weight: 700;
                        }
                        QPushButton:hover {
                            background-color: #3b82f6;
                            border: 1px solid #1e40af;
                        }
                        QPushButton:pressed {
                            background-color: #1e40af;
                            border: 1px solid #1e3a8a;
                        }
                    """)
                msg_box.exec_()
                return
            self.selection_confirmed.emit(rect)
            return
        if action == "cancel":
            self.cancelled.emit()
            return

        if self._is_control_zone(event.pos()):
            return

        if event.button() == Qt.LeftButton:
            self.dragging = True
            pos = self._clamp_pos(event.pos())
            self.selection_start = pos
            self.selection_end = pos
            self.update()

    def mouseMoveEvent(self, event):
        if self.dragging:
            self.selection_end = self._clamp_pos(event.pos())
            self.update()
        else:
            if self._is_control_zone(event.pos()):
                self.setCursor(Qt.PointingHandCursor)
            else:
                self.setCursor(Qt.CrossCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.dragging:
            self.selection_end = self._clamp_pos(event.pos())
            self.dragging = False
            self.update()
        if self._is_control_zone(event.pos()):
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.CrossCursor)

    def leaveEvent(self, event):
        self.setCursor(Qt.CrossCursor)
        super().leaveEvent(event)


class ScreenshotCropResultDialog(QDialog):
    """Small confirmation dialog shown after the crop is captured."""

    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.setWindowTitle("Screenshot Captured")
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setMinimumHeight(180)
        self.setStyleSheet("""
            QDialog {
                background: #f8fafc;
            }
            QLabel#screenshotConfirmTitle {
                color: #0f172a;
                font-size: 16px;
                font-weight: 800;
            }
            QLabel#screenshotConfirmBody {
                color: #475569;
                font-size: 12px;
                line-height: 1.4;
            }
            QPushButton#confirmYesButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #3b82f6,
                    stop: 0.5 #2563eb,
                    stop: 1 #1d4ed8
                );
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 12px;
                font-weight: 700;
                min-width: 88px;
            }
            QPushButton#confirmYesButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #60a5fa,
                    stop: 0.5 #3b82f6,
                    stop: 1 #2563eb
                );
            }
            QPushButton#confirmYesButton:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #1d4ed8,
                    stop: 0.5 #1e40af,
                    stop: 1 #1e3a8a
                );
            }
            QPushButton#confirmNoButton {
                background: #eef2f7;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 12px;
                font-weight: 700;
                min-width: 88px;
            }
            QPushButton#confirmNoButton:hover {
                background: #e2e8f0;
                border-color: #94a3b8;
            }
            QPushButton#confirmNoButton:pressed {
                background: #cbd5e1;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        message = QLabel("Screenshot captured successfully.")
        message.setObjectName("screenshotConfirmTitle")
        message.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(message)

        subtext = QLabel("Do you want to add this screenshot to the medical patient report?")
        subtext.setObjectName("screenshotConfirmBody")
        subtext.setWordWrap(True)
        layout.addWidget(subtext)

        spacer = QFrame()
        spacer.setFixedHeight(1)
        spacer.setStyleSheet("background: #e2e8f0; border: none;")
        layout.addWidget(spacer)

        button_row = QHBoxLayout()
        button_row.addStretch()

        add_button = QPushButton("Yes")
        add_button.setObjectName("confirmYesButton")
        add_button.setFixedHeight(36)
        add_button.setAutoDefault(False)
        add_button.setDefault(False)
        add_button.setStyleSheet("""
            QPushButton#confirmYesButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #3b82f6,
                    stop: 0.5 #2563eb,
                    stop: 1 #1d4ed8
                );
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 12px;
                font-weight: 700;
                min-width: 88px;
            }
            QPushButton#confirmYesButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #60a5fa,
                    stop: 0.5 #3b82f6,
                    stop: 1 #2563eb
                );
            }
            QPushButton#confirmYesButton:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #1d4ed8,
                    stop: 0.5 #1e40af,
                    stop: 1 #1e3a8a
                );
            }
        """)
        add_button.clicked.connect(self.accept)

        discard_button = QPushButton("No")
        discard_button.setObjectName("confirmNoButton")
        discard_button.setFixedHeight(36)
        discard_button.setAutoDefault(False)
        discard_button.setDefault(False)
        discard_button.clicked.connect(self.reject)

        button_row.addWidget(add_button)
        button_row.addWidget(discard_button)
        layout.addLayout(button_row)

        self.setLayout(layout)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)


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
        capture_button.setCursor(Qt.PointingHandCursor)
        capture_button.setAutoDefault(False)
        capture_button.setDefault(False)
        capture_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #3b82f6,
                    stop: 0.5 #2563eb,
                    stop: 1 #1d4ed8
                );
                color: white;
                border: none;
                border-radius: 8px;
                padding: 7px 14px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #60a5fa,
                    stop: 0.5 #3b82f6,
                    stop: 1 #2563eb
                );
            }
            QPushButton:pressed {
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 0, y2: 1,
                    stop: 0 #1d4ed8,
                    stop: 0.5 #1e40af,
                    stop: 1 #1e3a8a
                );
            }
        """)
        capture_button.clicked.connect(self.accept_selection)

        cancel_button = QPushButton("Cancel")
        cancel_button.setFixedSize(100, 32)
        cancel_button.setCursor(Qt.PointingHandCursor)
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


class ReportRequirementsDialog(QDialog):
    """Styled warning dialog for report prerequisites."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Report Requirements")
        self.setMinimumWidth(520)
        self.setStyleSheet("""
            QDialog {
                background: #f8fafc;
            }
            QLabel#reportRequirementsTitle {
                color: #0f172a;
                font-size: 16px;
                font-weight: 800;
            }
            QLabel#reportRequirementsBody {
                color: #475569;
                font-size: 12px;
                line-height: 1.45;
            }
            QPushButton#reportConfirmButton {
                background: #2563eb;
                color: white;
                border: none;
                border-radius: 9px;
                padding: 7px 12px;
                font-size: 12px;
                font-weight: 700;
                min-width: 88px;
            }
            QPushButton#reportConfirmButton:hover {
                background: #1d4ed8;
            }
            QPushButton#reportConfirmButton:pressed {
                background: #1e40af;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        top_row = QHBoxLayout()

        icon = QLabel("!")
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(60, 60)
        icon.setStyleSheet("""
            QLabel {
                background: #fde68a;
                color: #a16207;
                border: 1px solid #f59e0b;
                border-radius: 30px;
                font-size: 28px;
                font-weight: 900;
            }
        """)
        top_row.addWidget(icon)

        text_column = QVBoxLayout()
        title = QLabel("Report is not ready yet")
        title.setObjectName("reportRequirementsTitle")
        text_column.addWidget(title)

        body = QLabel(
            "Please select a patient ID and upload the data first before opening the medical report."
        )
        body.setObjectName("reportRequirementsBody")
        body.setWordWrap(True)
        text_column.addWidget(body)
        text_column.addStretch()

        top_row.addLayout(text_column)
        layout.addLayout(top_row)

        spacer = QFrame()
        spacer.setFixedHeight(1)
        spacer.setStyleSheet("background: #e2e8f0; border: none;")
        layout.addWidget(spacer)

        button_row = QHBoxLayout()
        button_row.addStretch()

        confirm_button = QPushButton("Yes, got it")
        confirm_button.setObjectName("reportConfirmButton")
        confirm_button.setFixedHeight(34)
        confirm_button.setCursor(Qt.PointingHandCursor)
        confirm_button.clicked.connect(self.accept)
        button_row.addWidget(confirm_button)
        layout.addLayout(button_row)

class SleepSenseDashboard(QMainWindow):
    
    """Main Sleep Sense Dashboard Window"""
    
    def __init__(self):
        super().__init__()
        self.logo_frame = None
        self.logo_label = None
        self.dashboard_screenshot_paths = []
        self.screenshot_overlay = None
        self.current_patient_db_id = None
        
        # Global event navigation system
        self.current_event_index = -1  # Global pointer for event navigation
        self.all_events = []  # Master event array sorted chronologically
        self.graph_visibility = self._default_graph_visibility()
        self.graph_toggle_buttons = {}
        
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
        self._set_database_icons_active(False)
        top_layout.addWidget(self.toolbar)

        # Quick graph toggle chips (center-top)
        self.graph_toggle_bar = self.create_graph_toggle_bar()
        top_layout.addWidget(self.graph_toggle_bar)
        
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
        splitter = PanelSplitter(Qt.Horizontal)
        splitter.setHandleWidth(12)
        splitter.setChildrenCollapsible(False)
        splitter.on_handle_double_clicked = self.toggle_patient_panel
        splitter.splitterMoved.connect(self.on_patient_splitter_moved)
        self.main_splitter = splitter

        # Left Panel - Patient Info
        patient_panel = QFrame()
        patient_panel.setObjectName("patientPanel")
        patient_panel.setMinimumWidth(PATIENT_PANEL_RAIL_WIDTH)
        patient_panel.setMaximumWidth(450) 
        patient_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        patient_layout = QVBoxLayout(patient_panel)
        patient_layout.setContentsMargins(2, 2, 2, 2)
        self.patient_panel = patient_panel

        self.patient_info = PatientInfoWidget()
        self.patient_info.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        patient_layout.addWidget(self.patient_info)

        # Collapsed rail - shown when the panel is hidden
        self.patient_rail = CollapsedPanelRail("PATIENT PANEL")
        self.patient_rail.on_expand = self.expand_patient_panel
        self.patient_rail.hide()
        self._patient_panel_collapsed = False
        patient_layout.addWidget(self.patient_rail)
        
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

        # Sync graph chip states with the current defaults and hide Abdomen by default.
        self._update_graph_controls_state()
        self.toggle_graph_visibility("Abdomen", self.graph_visibility["Abdomen"])
        
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
        self._set_patient_panel_collapsed(False)
        
        content_layout.addWidget(splitter)
        
        # Set content widget to scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        main_layout.setContentsMargins(0, 0, 0, 0)

    def on_patient_splitter_moved(self, pos, index):
        """Collapse the patient panel when it is dragged below the snap width."""
        if index != 1:
            return
        if self.patient_panel.width() < PATIENT_PANEL_SNAP_WIDTH:
            self.collapse_patient_panel()
        else:
            self._set_patient_panel_collapsed(False)

    def _set_patient_panel_collapsed(self, collapsed):
        """Show the rail when collapsed and the full panel when expanded."""
        if getattr(self, "_patient_panel_collapsed", None) == collapsed:
            return
        self._patient_panel_collapsed = collapsed
        self.patient_info.setVisible(not collapsed)
        self.patient_rail.setVisible(collapsed)

    def collapse_patient_panel(self):
        """Collapse the patient panel into a narrow rail instead of hiding it."""
        if not hasattr(self, "main_splitter"):
            return
        self._set_patient_panel_collapsed(True)
        total_width = max(1, self.main_splitter.width() - self.main_splitter.handleWidth())
        self.main_splitter.setSizes([
            PATIENT_PANEL_RAIL_WIDTH,
            max(1, total_width - PATIENT_PANEL_RAIL_WIDTH),
        ])

    def expand_patient_panel(self):
        """Expand the patient panel back to its normal width."""
        if not hasattr(self, "main_splitter"):
            return
        self._set_patient_panel_collapsed(False)
        total_width = max(1, self.main_splitter.width() - self.main_splitter.handleWidth())
        self.main_splitter.setSizes([
            PATIENT_PANEL_OPEN_WIDTH,
            max(1, total_width - PATIENT_PANEL_OPEN_WIDTH),
        ])

    def toggle_patient_panel(self):
        """Toggle between the collapsed rail and the expanded patient panel."""
        if getattr(self, "_patient_panel_collapsed", False):
            self.expand_patient_panel()
        else:
            self.collapse_patient_panel()
        
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

    def _default_graph_visibility(self):
        return {
            "Body Position": True,
            "Airflow": True,
            "Snoring": True,
            "Thorax": True,
            "Abdomen": False,
            "SpO2": True,
            "Pulse": True,
            "Body Movement": True,
        }

    def create_graph_toggle_bar(self):
        """Create the center-top quick graph toggle buttons."""
        container = QFrame()
        container.setObjectName("graphToggleBar")
        container.setStyleSheet("""         
            QFrame#graphToggleBar {
                background: transparent;
                border: none;
                margin: 0 10px;
            }
        """)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        for graph_name in self.graph_visibility.keys():
            button = QPushButton()
            button.setObjectName("graphToggleChip")
            button.setCheckable(True)
            button.setMinimumHeight(28)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(
                lambda checked, name=graph_name: self.toggle_graph_visibility(name, checked)
            )
            button.setStyleSheet("""
                QPushButton#graphToggleChip {
                    background-color: #ffffff;
                    border: 1px solid #d1d5db;
                    border-radius: 14px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: 700;
                    color: #475569;
                }
                QPushButton#graphToggleChip:hover {
                    background-color: #f8fafc;
                    border-color: #94a3b8;
                }
                QPushButton#graphToggleChip:checked {
                    background: qlineargradient(
                        x1: 0, y1: 0, x2: 0, y2: 1,
                        stop: 0 #eff6ff,
                        stop: 0.5 #dbeafe,
                        stop: 1 #bfdbfe
                    );
                    border: 1px solid #3b82f6;
                    color: #1e3a8a;
                }
                QPushButton#graphToggleChip:pressed {
                    background-color: #dbeafe;
                }
            """)
            self.graph_toggle_buttons[graph_name] = button
            layout.addWidget(button)

        return container

    def _refresh_graph_toggle_buttons(self):
        """Sync center graph toggle buttons with current visibility state."""
        for graph_name, button in self.graph_toggle_buttons.items():
            is_visible = bool(self.graph_visibility.get(graph_name, False))
            button.blockSignals(True)
            button.setChecked(is_visible)
            prefix = "✓ " if is_visible else ""
            button.setText(f"{prefix}{graph_name.strip()}")
            button.blockSignals(False)

    def _update_graph_controls_state(self):
        """Refresh all graph-selection UI with the latest visibility state."""
        self._refresh_graph_toggle_buttons()

    def create_controls_container(self):
        """Create controls container with Time Window and Hidden Graphs"""
        controls_container = QFrame()
        controls_container.setObjectName("controlsContainer")
        controls_container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
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
    
    def toggle_graph_visibility(self, graph_name, checked):
        """Toggle graph visibility based on checkbox state"""
        self.graph_visibility[graph_name] = checked
        
        if hasattr(self, 'monitor_chart') and self.monitor_chart:
            # Directly find and hide/show the chart container
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
        self._update_graph_controls_state()
    
        
    def create_time_slider_bar(self):
        """Create time slider navigation bar with professional styling - same size as graph containers"""
        # Main container with same styling as graph containers
        main_container = QWidget()
        main_container.setObjectName("signalChartContainer")
        main_container.setMinimumHeight(40) 
        main_container.setMaximumHeight(40)
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
            }
        """)
        
        # Inner layout for the container
        container_layout = QHBoxLayout(main_container)
        container_layout.setContentsMargins(8, 6, 8, 6) 
        container_layout.setSpacing(8) 
        
        # Time Position Label - smaller font
        time_label = QLabel("TIME NAV")
        time_label.setStyleSheet("font-size: 10px; color: #374151; font-weight: 700; letter-spacing: 1px; padding-right: 2px;")
        container_layout.addWidget(time_label)
        
        # Left navigation button - with clear arrow
        self.slider_left_btn = QPushButton("◀")
        self.slider_left_btn.setObjectName("sliderNavButton")
        self.slider_left_btn.setFixedHeight(22)  
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
        self.time_slider.setFixedHeight(22)  
        self.time_slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
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
                height: 9px;
                margin: 3px 0;
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
        self.slider_right_btn.setFixedHeight(22)  
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
        self.slider_time_label.setStyleSheet("""
            QLabel#sliderTimeLabel {
                background-color: #eff6ff;
                color: #1e40af;
                border: 1px solid #3b82f6;
                border-radius: 3px;
                padding: 2px 6px;
                font-size: 10px;
                min-width: 40px;
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
            
    def resizeEvent(self, event):
        """Keep the active screenshot overlay aligned with window resizes."""
        super().resizeEvent(event)

        overlay = getattr(self, "screenshot_overlay", None)
        if overlay is None:
            return

        capture_widget = self.centralWidget() or self
        overlay.setGeometry(capture_widget.geometry())
        overlay.update()

    def changeEvent(self, event):
        """Keep the active screenshot overlay synced with minimize/restore."""
        super().changeEvent(event)
        if event.type() != QEvent.WindowStateChange:
            return

        overlay = getattr(self, "screenshot_overlay", None)
        if overlay is None:
            return

        if self.isMinimized():
            overlay.hide()
        else:
            capture_widget = self.centralWidget() or self
            overlay.setGeometry(capture_widget.geometry())
            overlay.show()
            overlay.raise_()

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
            "Hide database icons",
            "Hide the database extra icons",
            self.hide_database_menu_icons
        )
        toolbar.addWidget(self.btn_previous)
        
        self.btn_next = create_toolbar_button(
            os.path.join(script_dir, icons[1]["icon"]),
            "Show database icons",
            "Show the database extra icons",
            self.show_database_menu_icons
        )
        toolbar.addWidget(self.btn_next)

        self.set_toolbar_navigation_enabled(False)
        
        toolbar.addSeparator()
        
        # Device Group: Prepare / Download
        self.btn_prepare_device = create_toolbar_button(
            os.path.join(script_dir, icons[2]["icon"]),
            icons[2]["tooltip"],
            icons[2]["status_tip"],
            self.prepare_device
        )
        toolbar.addWidget(self.btn_prepare_device)
        
        # Download Data button temporarily disabled.
        # self.btn_download_data = create_toolbar_button(
        #     os.path.join(script_dir, icons[3]["icon"]),
        #     icons[3]["tooltip"],
        #     icons[3]["status_tip"], 
        #     self.download_data
        # )  
        # self.btn_download_data.setEnabled(False)  
        # toolbar.addWidget(self.btn_download_data)
        
        
        # Data Group: Database / Archive
        self.btn_database = create_toolbar_button(
            os.path.join(script_dir, icons[4]["icon"]),
            icons[4]["tooltip"],
            icons[4]["status_tip"],
            self.open_database
        )
        toolbar.addWidget(self.btn_database)
        
        # Archive button disabled by request.
        # self.btn_archive = create_toolbar_button(
        #     os.path.join(script_dir, icons[8]["icon"]),
        #     icons[8]["tooltip"],
        #     icons[8]["status_tip"],
        #     self.open_archive
        # )
        # toolbar.addWidget(self.btn_archive)
        
        toolbar.addSeparator()
        
        # Extended Database Options (initially hidden - using QAction)
        from PyQt5.QtGui import QIcon
        
        self.action_patient_record = QAction(QIcon(os.path.join(script_dir, "icons/patient_report_card.svg")), "Patient Record Card", self)
        self.action_patient_record.setToolTip("Patient Record Card")
        self.action_patient_record.setStatusTip("Open Patient Record Card Form")
        self.action_patient_record.triggered.connect(self.open_patient_report_card)
        self.action_patient_record.setVisible(True)
        self.action_patient_record.setEnabled(False)
        toolbar.addAction(self.action_patient_record)
                
        self.action_medical_report = QAction(QIcon(os.path.join(script_dir, "icons/medical_report.svg")), "Medical Report", self)
        self.action_medical_report.setToolTip("Medical Report")
        self.action_medical_report.setStatusTip("Open Medical Report Form")
        self.action_medical_report.triggered.connect(self.open_medical_report)
        self.action_medical_report.setVisible(True)
        self.action_medical_report.setEnabled(False)
        toolbar.addAction(self.action_medical_report)
        
        # self.action_event_list = QAction(QIcon(os.path.join(script_dir, icons[7]["icon"])), "Event List", self)
        # self.action_event_list.setToolTip("Event List")
        # self.action_event_list.setStatusTip("View detected events")
        # self.action_event_list.triggered.connect(self.open_event_list)
        # self.action_event_list.setVisible(False)
        # self.action_event_list.setEnabled(True)
        # toolbar.addAction(self.action_event_list)
        
        return toolbar
    
    # Toolbar Button Callback Methods
    def set_toolbar_navigation_enabled(self, enabled):
        """Enable or disable the database icon toggle buttons."""
        labels = ("Hide database icons", "Show database icons")
        buttons = (getattr(self, "btn_previous", None), getattr(self, "btn_next", None))

        for button, label in zip(buttons, labels):
            if button is None:
                continue
            button.setEnabled(bool(enabled))
            button.setToolTip(label if enabled else "Pehle Database button dabaayein")
    
    def prepare_device(self):
        """Initialize and connect device"""
        print("Prepare Device button clicked")
        self.hide_extended_buttons()
        # TODO: Implement device preparation logic
   
        # self.btn_download_data.setEnabled(True)
    
    # def download_data(self):
    #     """Download data from device"""
    #     # Check if monitor chart has selection active and block if needed
    #     if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
    #         return
    #
    #     print("Download Data button clicked")
    #     # TODO: Implement data download logic
    
    def open_database(self):
        """Open patient database as modeless window and toggle extended buttons"""
        # Check if monitor chart has selection active and block if needed
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return
        
        print("Database button clicked")

        existing_window = getattr(self, "database_window", None)
        if existing_window is not None:
            try:
                if existing_window.isVisible():
                    self.show_database_menu_icons()
                    self.set_toolbar_navigation_enabled(True)
                    existing_window.raise_()
                    existing_window.activateWindow()
                    existing_window.show()
                    return
            except Exception:
                pass

        # Show extended buttons immediately
        self.show_database_menu_icons()
        self.set_toolbar_navigation_enabled(True)
        # Open database window as modeless (non-blocking)
        self.database_window = DatabaseWindow(self)
        self.database_window.show()
    
    def _set_database_icons_active(self, active):
        """Keep database actions in the layout, but hide them until active."""
        toolbar = getattr(self, "toolbar", None)
        if toolbar is None:
            return

        for action in (
            getattr(self, "action_patient_record", None),
            getattr(self, "action_medical_report", None),
        ):
            if action is None:
                continue

            action.setVisible(True)
            action.setEnabled(bool(active))

            tool_button = toolbar.widgetForAction(action)
            if tool_button is None:
                continue

            fade_effect = tool_button.graphicsEffect()
            if not isinstance(fade_effect, QGraphicsOpacityEffect):
                fade_effect = QGraphicsOpacityEffect(tool_button)
                tool_button.setGraphicsEffect(fade_effect)
            fade_effect.setOpacity(1.0 if active else DATABASE_ICON_INACTIVE_OPACITY)
            tool_button.setCursor(Qt.PointingHandCursor if active else Qt.ArrowCursor)

    def show_database_menu_icons(self):
        """Enable the database extra icons and show them at full strength."""
        self._set_database_icons_active(True)
        print("Database menu icons active")

    def hide_database_menu_icons(self):
        """Fade and disable the database extra icons while keeping their space."""
        self._set_database_icons_active(False)
        print("Database menu icons faded")

    def hide_extended_buttons(self):
        """Hide database mode extras and disable the database toggle buttons."""
        self.hide_database_menu_icons()
        self.set_toolbar_navigation_enabled(False)
    
    # def open_archive(self):
    #     """Access archived records as modal dialog"""
    #     # Check if monitor chart has selection active and block if needed
    #     if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
    #         return
    #
    #     print("Archive button clicked")
    #     self.hide_extended_buttons()
    #     self.archive_window = ArchiveWindow(self)
    #     self.archive_window.exec_()  # Modal dialog
    
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

        if not getattr(self.monitor_chart, "loaded_csv_path", None) or not getattr(self, "current_patient_db_id", None):
            dialog = ReportRequirementsDialog(self)
            dialog.exec_()
            return
        
        print("Medical Report button clicked")
        # Import the medical report generation function and PDF viewer
        from .medical_report_form import generate_sleep_report, PDFViewerWidget
        from .full_psg_hypnogram import generate_full_psg_hypnogram

        # Generate the report and show in internal viewer
        try:
            patient_data = None
            patient_db_id = getattr(self, "current_patient_db_id", None)
            if patient_db_id:
                try:
                    db_manager = DatabaseManager()
                    patient_data = db_manager.get_patient_by_id(patient_db_id)
                except Exception as db_error:
                    print(f"⚠️ Could not fetch patient from DB for report: {db_error}")
            else:
                print("⚠️ No current patient DB id available for report generation")

            screenshot_paths = list(getattr(self, 'dashboard_screenshot_paths', []))
            report_context = calculate_report_context(
                getattr(self.monitor_chart, "analysis_results", None),
                getattr(self.monitor_chart, "psg_full_data", {}).get("signals", {}) if getattr(self.monitor_chart, "psg_full_data", None) else {},
                getattr(getattr(self.monitor_chart, "auto_rule_ai_result", None), "get", lambda *_: [])("events", []),
            )

            hypnogram_path = None
            try:
                psg_payload = getattr(self.monitor_chart, "psg_full_data", None) or {}
                signals = psg_payload.get("signals", {})
                if signals:
                    output_folder = Path.home() / "SleepSenseReports" / "generated_assets"
                    hypnogram_path = generate_full_psg_hypnogram(
                        psg_data=signals,
                        output_folder=str(output_folder),
                        sampling_rate=10.0,
                        patient_id=str(patient_data.get("patient_id") or patient_db_id or "patient") if patient_data else str(patient_db_id or "patient"),
                        study_id=Path(getattr(self.monitor_chart, "loaded_csv_path", "study")).stem if getattr(self.monitor_chart, "loaded_csv_path", None) else "study",
                        detected_events=(getattr(self.monitor_chart, "auto_rule_ai_result", {}) or {}).get("events", []),
                    )
                    print(f"✅ Full PSG hypnogram generated: {hypnogram_path}")
            except Exception as hypnogram_error:
                print(f"⚠️ Could not generate full PSG hypnogram: {hypnogram_error}")

            if hypnogram_path:
                screenshot_paths.insert(0, hypnogram_path)

            pdf_path = generate_sleep_report(
                patient_data=patient_data,
                dashboard_screenshot_path=screenshot_paths if screenshot_paths else None,
                report_context=report_context,
            )
            print("✅ Medical report generated successfully!")

            # Also save the report to the DB, otherwise nothing ever appears in
            # the Database window's "3. Reports" section.
            self.save_generated_report_to_db(patient_data, patient_db_id, pdf_path)
            
            # Show PDF in internal viewer
            self.pdf_viewer = PDFViewerWidget(pdf_path, self)
            self.pdf_viewer.exec_()
            
        except Exception as e:
            print(f"❌ Error generating medical report: {str(e)}")

    def save_generated_report_to_db(self, patient_data, patient_db_id, pdf_path):
        """Insert the generated report into the reports table with its PDF path."""
        if not patient_db_id or not pdf_path:
            print("⚠️ Report was not saved to the DB - patient id or pdf path missing")
            return None

        from datetime import datetime

        patient_data = patient_data or {}
        full_name = " ".join(
            part for part in [
                str(patient_data.get('last_name') or '').strip(),
                str(patient_data.get('first_name') or '').strip(),
            ] if part
        ) or "Unknown"

        report_row = {
            'patient_id': patient_db_id,
            'patient_name': full_name,
            # Store both date and time so multiple reports on the same day remain distinct
            'report_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'findings': '',
            'diagnosis': '',
            'recommendations': '',
            'doctor_name': str(patient_data.get('physician') or '').strip(),
            'specialization': str(patient_data.get('department') or '').strip(),
            'pdf_path': str(pdf_path),
        }

        try:
            report_id = DatabaseManager().save_report(report_row)
            if report_id:
                print(f"🗂️ Report saved to DB (id={report_id})")
            return report_id
        except Exception as error:
            print(f"⚠️ Report could not be saved to DB: {error}")
            return None
    
    def load_patient_data(self, patient_data):
        """Load patient data from database and display in dashboard"""
        print(f"Loading patient data: {patient_data['last_name']} {patient_data['first_name']}")

        # Keep the database primary key so report generation can fetch a fresh row later.
        self.current_patient_db_id = patient_data.get('id')
        
        # Create patient ID string for display
        patient_id_str = patient_data.get('patient_id') or str(patient_data.get('id', '--------'))
        
        # Set patient ID in monitor chart
        if hasattr(self, 'monitor_chart'):
            self.monitor_chart.set_patient_id(patient_id_str)
            self.monitor_chart.patient_db_id = patient_data.get('id')
        
        # Update patient info widget
        if hasattr(self, 'patient_info'):
            self.patient_info.set_patient_data({
                'last_name': patient_data.get('last_name', ''),
                'first_name': patient_data.get('first_name', ''),
                'dob': patient_data.get('dob', ''),
                'patient_id': patient_id_str,
                'gender': patient_data.get('gender', ''),
                'age': patient_data.get('age', ''),
            })
        
        print(f"Patient data loaded successfully in dashboard")

    def load_psg_data_from_path(self, file_path):
        """Load a previously saved PSG file directly from disk."""
        if not file_path:
            return False

        from pathlib import Path

        if not Path(file_path).exists():
            QMessageBox.warning(
                self,
                "File Missing",
                f"Saved PSG file not found:\n{file_path}",
            )
            return False

        print(f"🎬 Loading PSG data from saved session: {file_path}")
        self.monitor_chart.skip_next_auto_playback = True
        self.monitor_chart.load_psg_data(file_path)
        return True
    
    def open_signal_view(self):
        """View live physiological signals"""
        # Check if monitor chart has selection active and block if needed
        if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
            return
        
        print("Signal View button clicked")
        # TODO: Implement signal view logic
    
    # def open_event_list(self):
    #     """View detected events"""
    #     # Check if monitor chart has selection active and block if needed
    #     if hasattr(self.monitor_chart, 'block_if_selection_active') and self.monitor_chart.block_if_selection_active():
    #         return
    #
    #     print("Event List button clicked")
    #     self.event_window = EventWindow(self)
    #     self.event_window.exec_()  # Modal dialog
    
    def take_screenshot(self):
        """Take a drag-selected screenshot on top of the current dashboard."""
        try:
            if not getattr(self.monitor_chart, "loaded_csv_path", None):
                show_styled_warning(
                    self,
                    "No Data Uploaded",
                    "Please upload the data first before taking a screenshot.",
                )
                return

            self.repaint()
            if getattr(self, "monitor_chart", None) is not None:
                self.monitor_chart.repaint()
                self.monitor_chart.update()
                scroll_area = getattr(self.monitor_chart, "scroll_area", None)
                if scroll_area is not None and hasattr(scroll_area, "viewport"):
                    scroll_area.viewport().repaint()
                charts_widget = getattr(self.monitor_chart, "charts_widget", None)
                if charts_widget is not None:
                    charts_widget.repaint()
                try:
                    import pyqtgraph as pg

                    for plot_widget in self.monitor_chart.findChildren(pg.PlotWidget):
                        try:
                            plot_widget.getViewBox().update()
                        except Exception:
                            pass
                        plot_widget.repaint()
                except Exception:
                    pass
            QApplication.processEvents()
            QApplication.sendPostedEvents(None, 0)
            QApplication.processEvents()

            capture_widget = self.centralWidget() or self
            capture_widget.repaint()
            QApplication.processEvents()
            source_pixmap = capture_widget.grab()
            if source_pixmap.isNull():
                raise RuntimeError("Could not capture the dashboard area.")

            if self.screenshot_overlay is not None:
                try:
                    self.screenshot_overlay.cancelled.disconnect()
                except Exception:
                    pass
                try:
                    self.screenshot_overlay.selection_confirmed.disconnect()
                except Exception:
                    pass
                self.screenshot_overlay.deleteLater()
                self.screenshot_overlay = None

            overlay = ScreenshotOverlayWidget(source_pixmap, self)
            overlay.setGeometry(capture_widget.geometry())
            overlay.selection_confirmed.connect(
                lambda rect, pixmap=source_pixmap, widget=overlay: self._finalize_dashboard_screenshot(pixmap, rect, widget)
            )
            overlay.cancelled.connect(lambda widget=overlay: self._cancel_dashboard_screenshot(widget))
            self.screenshot_overlay = overlay
            overlay.show()
            overlay.raise_()
            overlay.activateWindow()
        except Exception as e:
            QMessageBox.critical(self, "Screenshot Error", 
                               f"Failed to take screenshot:\n{str(e)}")

    def _cancel_dashboard_screenshot(self, overlay=None):
        """Close the inline screenshot overlay without saving anything."""
        if overlay is None:
            overlay = self.screenshot_overlay
        if overlay is not None:
            overlay.hide()
            overlay.deleteLater()
        if self.screenshot_overlay is overlay:
            self.screenshot_overlay = None

    def _finalize_dashboard_screenshot(self, source_pixmap, selected_rect, overlay=None):
        """Crop the selected area, ask to attach it to the report, and then clean up."""
        from datetime import datetime

        if overlay is None:
            overlay = self.screenshot_overlay

        if selected_rect.isNull() or selected_rect.width() <= 5 or selected_rect.height() <= 5:
            QMessageBox.information(self, "Select Area", "Please drag to select a screenshot area first.")
            return

        cropped_pixmap = source_pixmap.copy(selected_rect)
        if cropped_pixmap.isNull():
            raise RuntimeError("Selected screenshot area could not be captured.")

        temp_dir = tempfile.gettempdir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_path = os.path.join(temp_dir, f"sleep_sense_dashboard_{timestamp}.png")

        if not cropped_pixmap.save(temp_path, "PNG"):
            raise RuntimeError("Failed to prepare screenshot image.")

        if overlay is not None:
            overlay.hide()
            overlay.deleteLater()
        if self.screenshot_overlay is overlay:
            self.screenshot_overlay = None

        choice = ScreenshotCropResultDialog(temp_path, self).exec_()

        if choice == QDialog.Accepted:
            screenshot_paths = list(getattr(self, "dashboard_screenshot_paths", []))
            if temp_path not in screenshot_paths:
                screenshot_paths.append(temp_path)
            self.dashboard_screenshot_paths = screenshot_paths
            self.open_medical_report()
        else:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass
    
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

        # event_list_action = QAction('Event list', self)
        # event_list_action.triggered.connect(self.button_functions.view_event_list)
        # view_menu.addAction(event_list_action)
    
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
        if not getattr(self, "current_patient_db_id", None):
            QMessageBox.warning(
                self,
                "No Patient Selected",
                "Please select a patient from the database before uploading data.",
            )
            return

        from PyQt5.QtWidgets import QFileDialog
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select PSG Data File",
            "",
            "Signal Files (*.csv *.txt);;CSV Files (*.csv);;Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            print(f"🎬 Loading PSG data from: {file_path}")
            self.monitor_chart.skip_next_auto_playback = True
            self.monitor_chart.load_psg_data(file_path)
            print("✅ PSG data loaded successfully - Playback ready!")
