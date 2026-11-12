"""
Main Entry Point - Sleep Sense Dashboard Application
Medical Grade PyQt5 Sleep Monitoring System
"""
import sys
import os
import threading
import math
import time


def configure_utf8_console():
    """Keep Unicode log messages safe in Windows terminals and Code Runner."""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"): 
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, OSError, ValueError):
                # Frozen/windowed builds can expose streams that cannot be
                # reconfigured. Logging must never stop the application.
                pass


configure_utf8_console()


def set_windows_app_id():
    """Give Sleep Sense its own taskbar identity.   so Windows shows our icon,
    not the python.exe icon, and groups windows correctly."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "Deckmount.SleepSense.3"
            )
        except Exception:
            pass


set_windows_app_id()

from PyQt5.QtWidgets import QApplication, QSplashScreen, QMessageBox, QPushButton, QProxyStyle, QStyle
from PyQt5.QtGui import QFont, QPixmap, QColor, QPainter, QPen, QIcon, QLinearGradient, QPainterPath, QFontMetrics
from PyQt5.QtCore import Qt, QTimer, QRectF
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from src.utils.app_paths import get_resource_path
from src.utils.app_version import APP_VERSION as APP_VERSION_STRING
from src.utils.db_utils import init_db


SINGLE_INSTANCE_SERVER = "SleepSenseApp"
SINGLE_INSTANCE_MUTEX = r"Local\SleepSenseApp.SingleInstance.v3"


class _ButtonFocusStyle(QProxyStyle):
    """Keep Qt's dotted focus frame off buttons while preserving other focus cues."""

    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PE_FrameFocusRect and isinstance(widget, QPushButton):
            return
        super().drawPrimitive(element, option, painter, widget)


def get_asset_path(relative_path):
    """Returns correct path for assets whether running as exe or in dev mode."""
    return get_resource_path(*relative_path.replace("\\", "/").split("/"))

class AnimatedSplash(QSplashScreen):
    """  
    Two-tone splash: navy brand block with a breathing wave on top,
    3-step checklist + progress bar on the white bottom half.
    Steps: 1 = Initializing database, 2 = Loading dashboard, 3 = Ready
    """
    APP_VERSION = APP_VERSION_STRING
    STEPS = ("Initializing database", "Loading dashboard", "Ready")

    NAVY = QColor("#1d3a6b")
    NAVY_DARK = QColor("#16305a")
    WAVE = QColor("#7fb3ff")
    INK = QColor("#1c2431")
    MUTE = QColor("#8b95a5")
    LINE = QColor("#e5e7eb")
    FONT = "Segoe UI" if sys.platform.startswith("win") else "Helvetica Neue"
    WIDTH, HEIGHT = 760, 460
    TOP_H = 250 

    def __init__(self):
        super().__init__(QPixmap(), Qt.WindowStaysOnTopHint)
        self._logo = None
        logo_path = get_asset_path("assets/images/DECKMOUNT_Logo.png")
        if os.path.exists(logo_path):
            pm = QPixmap(logo_path)
            if not pm.isNull():
                self._logo = pm.scaledToHeight(34, Qt.SmoothTransformation)
        self._phase = 0.0
        self._step = 0            # 0 = nothing done yet, 1..3 = current step in progress
        self._progress = 0.0      # 0..1, eased toward the target
        self._target = 0.0
        self.setFixedSize(self.WIDTH, self.HEIGHT)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(20)

    # ---- public API used by main() ----
    def set_step(self, step_index):
        """Mark step 1..3 as in progress (previous steps become done)."""
        self._step = max(0, min(step_index, len(self.STEPS)))           
        self._target = (self._step - 1) / len(self.STEPS) + 0.15
        self.update()

    def set_done(self):
        self._step = len(self.STEPS) + 1
        self._target = 1.0
        self.update()

    def showMessage(self, msg, *args):
        # Kept for compatibility; step text is drawn from STEPS instead.
        self.update()

    # ---- animation ----
    def _tick(self):
        self._phase = (self._phase + 0.06) % (2 * math.pi)
        self._progress += (self._target - self._progress) * 0.08
        self.update()

    def _draw_wave(self, painter, y0, amp, color, width, phase, periods=3.2):
        w = self.width()
        path = QPainterPath()
        path.moveTo(-10, y0)
        n = 220
        for i in range(1, n + 1):
            t = i / n
            x = -10 + (w + 20) * t
            envelope = math.sin(math.pi * t)
            y = y0 - amp * envelope * math.sin(2 * math.pi * periods * t + phase)
            path.lineTo(x, y)
        pen = QPen(color, width)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)

    def drawContents(self, painter):
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        top_h = self.TOP_H

        # ---- top navy block ----
        grad = QLinearGradient(0, 0, w, top_h)
        grad.setColorAt(0, self.NAVY_DARK)
        grad.setColorAt(1, self.NAVY)
        painter.fillRect(0, 0, w, top_h, grad)
        painter.fillRect(0, top_h, w, h - top_h, QColor("#ffffff"))

        self._draw_wave(painter, top_h - 44, 20, QColor(255, 255, 255, 50), 2.4, self._phase)
        self._draw_wave(painter, top_h - 44, 20, self.WAVE, 1.8, self._phase + 0.8)

        # brand: real logo on a white chip if available, else text
        if self._logo is not None:
            chip_w, chip_h = self._logo.width() + 24, self._logo.height() + 14
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("white"))
            painter.drawRoundedRect(QRectF(36, 26, chip_w, chip_h), 6, 6)
            painter.drawPixmap(48, 33, self._logo)
        else:
            brand_font = QFont(self.FONT, 15, QFont.Bold)
            painter.setFont(brand_font)
            painter.setPen(QColor("white"))
            painter.drawText(QRectF(36, 30, 400, 26), Qt.AlignLeft | Qt.AlignVCenter, "DECK MOUNT")
            brand_w = QFontMetrics(brand_font).horizontalAdvance("DECK MOUNT")
            painter.setFont(QFont(self.FONT, 8))
            painter.setPen(QColor("#b8c4d6"))
            painter.drawText(QRectF(36 + brand_w + 10, 33, 200, 22), Qt.AlignLeft | Qt.AlignVCenter, "ELECTRONICS")

        # title + subtitle
        painter.setFont(QFont(self.FONT, 34, QFont.Bold))
        painter.setPen(QColor("white"))
        painter.drawText(QRectF(0, 92, w, 52), Qt.AlignCenter, "Sleep Sense")
        painter.setFont(QFont(self.FONT, 12))
        painter.setPen(QColor("#b8c4d6"))
        painter.drawText(QRectF(0, 146, w, 24), Qt.AlignCenter, "Home Sleep Apnea Test  |  Level 3 Diagnostics")

        # ---- bottom: step checklist ----
        painter.setFont(QFont(self.FONT, 11))
        y = top_h + 34
        for index, label in enumerate(self.STEPS, start=1):
            if index < self._step:            # done
                text, color = f"{label}  \u2713", self.INK
            elif index == self._step:         # in progress
                dots = "." * (1 + int(self._phase / (2 * math.pi) * 3) % 3)
                text, color = f"{label} {dots}", self.NAVY
            else:                             # pending
                text, color = label, self.MUTE
            painter.setPen(color)
            painter.drawText(QRectF(0, y, w, 22), Qt.AlignCenter, text)
            y += 26

        # ---- progress bar ----
        bar_w, bar_h = 360, 7
        bar_x, bar_y = (w - bar_w) / 2, top_h + 126
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.LINE)
        painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 3, 3)
        painter.setBrush(self.NAVY)
        painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w * max(0.0, min(1.0, self._progress)), bar_h), 3, 3)

        # ---- footer ----
        painter.setFont(QFont(self.FONT, 9))
        painter.setPen(self.MUTE)
        painter.drawText(QRectF(0, h - 34, w, 20), Qt.AlignCenter,
                         f"\u00a9 2026 Deckmount Electronics Pvt. Ltd.  \u00b7  Version {self.APP_VERSION}")

        # thin border
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(self.LINE, 1))
        painter.drawRect(0, 0, w - 1, h - 1)

def acquire_single_instance_lock(name=SINGLE_INSTANCE_MUTEX):
    """Acquire an OS-level process lock; return None in secondary instances."""
    if sys.platform.startswith("win"):
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_bool

        handle = kernel32.CreateMutexW(None, False, str(name))
        if not handle:
            raise OSError(ctypes.get_last_error(), "Could not create the Sleep Sense instance mutex")
        if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
            kernel32.CloseHandle(handle)
            return None
        return (kernel32, handle)

    # Non-Windows development fallback. The packaged application uses the
    # named Windows mutex above.
    from PyQt5.QtCore import QLockFile
    import tempfile

    lock_name = str(name).replace("\\", "_").replace("/", "_")
    lock = QLockFile(os.path.join(tempfile.gettempdir(), f"{lock_name}.lock"))
    lock.setStaleLockTime(5000)
    return lock if lock.tryLock(0) else None


def release_single_instance_lock(instance_lock):
    """Release the platform-specific single-instance lock."""
    if instance_lock is None:
        return
    if isinstance(instance_lock, tuple):
        kernel32, handle = instance_lock
        kernel32.CloseHandle(handle)
    else:
        instance_lock.unlock()


def notify_existing_instance(timeout_ms=4000):
    """Ask the running instance to activate its window."""
    deadline = time.monotonic() + max(0.1, float(timeout_ms) / 1000.0)
    while time.monotonic() < deadline:
        socket = QLocalSocket()
        socket.connectToServer(SINGLE_INSTANCE_SERVER)
        if socket.waitForConnected(250):
            socket.write(b"activate")
            socket.flush()
            socket.waitForBytesWritten(500)
            socket.disconnectFromServer()
            return True
        time.sleep(0.05)
    return False


def acquire_single_instance_server():
    """Atomically become the primary instance, or notify the current one."""
    server = QLocalServer()
    if server.listen(SINGLE_INSTANCE_SERVER):
        return server

    # A live server owns the name. Notify it and let this process exit without
    # creating a splash, window, taskbar icon, or its own message box.
    if notify_existing_instance():
        return None

    # On platforms that use a filesystem socket, a crashed process can leave a
    # stale endpoint behind. Remove it only after a connection attempt failed.
    QLocalServer.removeServer(SINGLE_INSTANCE_SERVER)
    if server.listen(SINGLE_INSTANCE_SERVER):
        return server

    # Another process may have won the stale-endpoint recovery race.
    notify_existing_instance()
    return None


def run_in_background(app, splash, message, fn):
    """
    Run fn() in a background thread while keeping the splash animation alive.
    Main thread stays free → QTimer fires → animation keeps spinning.
    """
    splash.showMessage(message)

    done = threading.Event()
    error_holder = [None]

    def worker ():
        try:
            fn()
        except Exception as e:
            error_holder[0] = e
        finally:
            done.set()

    threading.Thread(target=worker, daemon=True).start()

    # Keep event loop running so timer + paint events fire → animation spins
    while not done.is_set():
        app.processEvents()

    if error_holder[0]:
        raise error_holder[0]


def main():
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)

    # Claim the process slot before importing the large chart stack or showing
    # any Qt window. Rapid double-clicks therefore cannot start two primaries.
    instance_lock = acquire_single_instance_lock()
    if instance_lock is None:
        secondary_app = QApplication(sys.argv)
        secondary_app.setApplicationName("Sleep Sense")
        notify_existing_instance()
        return 0

    from src.components.sleep_monitor_chart import configure_opengl_for_playback
    configure_opengl_for_playback()
    app = QApplication(sys.argv)
    app.setApplicationName("Sleep Sense")
    app.setStyle(_ButtonFocusStyle(app.style()))

    # --- Atomic single-instance ownership ---
    server = acquire_single_instance_server()
    if server is None:
        release_single_instance_lock(instance_lock)
        return 0

    window_holder = [None]
    activation_pending = [False]
    already_open_box = [None]

    def show_existing_instance_notice():
        """Raise the primary window and keep at most one notice visible."""
        window = window_holder[0]
        if window is None:
            activation_pending[0] = True
            return

        activation_pending[0] = False
        state = window.windowState()
        if state & Qt.WindowMinimized:
            window.setWindowState((state & ~Qt.WindowMinimized) | Qt.WindowActive)
        window.show()
        window.raise_()
        window.activateWindow()

        current_box = already_open_box[0]
        if current_box is not None and current_box.isVisible():
            current_box.raise_()
            current_box.activateWindow()
            return

        box = QMessageBox(window)
        box.setAttribute(Qt.WA_DeleteOnClose, True)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle("Sleep Sense Already Open")
        box.setText(
            "Sleep Sense is already running.\n"
            "The existing window has been brought to the front."
        )
        box.setStandardButtons(QMessageBox.Ok)
        box.setDefaultButton(QMessageBox.Ok)

        ok_button = box.button(QMessageBox.Ok)
        if ok_button is not None:
            ok_button.setMinimumSize(82, 32)
            ok_button.setStyleSheet("""
                QPushButton {
                    background-color: #2563eb;
                    color: #ffffff;
                    border: 1px solid #1d4ed8;
                    border-radius: 5px;
                    padding: 5px 16px;
                    font-size: 12px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #1d4ed8;
                    border-color: #1e40af;
                }
                QPushButton:pressed {
                    background-color: #1e3a8a;
                    border-color: #172554;
                }
            """)

        already_open_box[0] = box

        def clear_notice(_result=None, closing_box=box):
            if already_open_box[0] is closing_box:
                already_open_box[0] = None

        box.finished.connect(clear_notice)
        box.open()

    def handle_instance_connections():
        """Collapse any burst of launches into one activation request."""
        received_activation = False
        while server.hasPendingConnections():
            connection = server.nextPendingConnection()
            if connection is None:
                continue
            received_activation = True
            connection.disconnectFromServer()
            connection.deleteLater()
        if received_activation:
            show_existing_instance_notice()

    server.newConnection.connect(handle_instance_connections)
    app.aboutToQuit.connect(server.close)

    # --- App icon ---
    app_icon_path = get_asset_path("assets/icon.ico")
    if os.path.exists(app_icon_path):
        app.setWindowIcon(QIcon(app_icon_path))
      
    app.setFont(QFont("Segoe UI", 10))

    # --- Show animated splash ---
    splash = AnimatedSplash()
    splash.setWindowFlag(Qt.FramelessWindowHint)

    # Position the splash screen at the center of the screen
    screen = QApplication.primaryScreen().geometry()
    splash.move(
        (screen.width()  - splash.width())  // 2,
        (screen.height() - splash.height()) // 2



         
    )
 
    splash.show()
    app.processEvents()

    # --- Step 1: Init DB in background (animation keeps spinning) ---
    splash.set_step(1)
    run_in_background(app, splash, "Initializing database...", init_db)

    # --- Step 2: Import dashboard module in background ---
    dashboard_holder = [None]

    def import_dashboard():
        from src.components.dashboard import SleepSenseDashboard
        dashboard_holder[0] = SleepSenseDashboard


    
    splash.set_step(2)
    run_in_background(app, splash, "Loading dashboard...", import_dashboard)

    # --- Step 3: Create window in main thread (Qt requires this) ---
    splash.set_step(3)
    app.processEvents()

    SleepSenseDashboard = dashboard_holder[0]
    window = SleepSenseDashboard()
    window_holder[0] = window
  
    if os.path.exists(app_icon_path):
        window.setWindowIcon(QIcon(app_icon_path))

    window.showMaximized()
    splash.set_done()
    app.processEvents()
    splash.finish(window)
    if activation_pending[0]:
        QTimer.singleShot(0, show_existing_instance_notice)

    exit_code = app.exec_()
    release_single_instance_lock(instance_lock)
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
 
              
