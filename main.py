"""
Main Entry Point - Sleep Sense Dashboard Application
Medical Grade PyQt5 Sleep Monitoring System
"""
import sys
import os
import threading
from PyQt5.QtWidgets import QApplication, QSplashScreen, QMessageBox
from PyQt5.QtGui import QFont, QPixmap, QColor, QPainter, QPen, QIcon, QLinearGradient
from PyQt5.QtCore import Qt, QTimer, QRectF
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from src.utils.db_utils import init_db


def get_asset_path(relative_path):
    """Returns correct path for assets whether running as exe or in dev mode."""
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)


class AnimatedSplash(QSplashScreen):
    """
    Animated splash screen with spinning ring animation.
    Shows on exe double-click while app initializes.
    """
    def __init__(self):
        super().__init__(QPixmap(), Qt.WindowStaysOnTopHint)
        self._angle = 0
        self._msg = ""
        self.setFixedSize(600, 380)

        # Timer drives the spinning animation (refreshes every 20ms)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)
        self._timer.start(20)

    def _rotate(self):
        self._angle = (self._angle + 6) % 360
        self.update()  # update() is safer than repaint() for animations

    def showMessage(self, msg, *args):
        self._msg = msg
        self.update()

    def drawContents(self, painter):
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # --- Background gradient (dark teal - medical sleep monitoring) ---
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, QColor("#0d2b2b"))
        grad.setColorAt(1, QColor("#1a4f4f"))
        painter.fillRect(0, 0, w, h, grad)

        # --- Top & bottom decorative lines ---
        painter.setPen(QPen(QColor("#2dd4bf"), 2))
        painter.drawLine(40, 8, w - 40, 8)
        painter.drawLine(40, h - 8, w - 40, h - 8)

        # --- Spinner position ---
        cx, cy = w // 2, h // 2 - 35
        r = 52

        # Outer ring (static background ring)
        painter.setPen(QPen(QColor("#134040"), 6))
        painter.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # Outer spinning arc (rotates clockwise)
        pen = QPen(QColor("#2dd4bf"), 6)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawArc(QRectF(cx - r, cy - r, r * 2, r * 2),
                        -self._angle * 16, 100 * 16)

        # Inner spinning arc (rotates counter-clockwise)
        inner_r = 37
        pen2 = QPen(QColor("#99f6e4"), 3)
        pen2.setCapStyle(Qt.RoundCap)
        painter.setPen(pen2)
        painter.drawArc(QRectF(cx - inner_r, cy - inner_r, inner_r * 2, inner_r * 2),
                        self._angle * 16, 60 * 16)

        # "SS" label in center of spinner
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Segoe UI", 18, QFont.Bold))
        painter.drawText(QRectF(cx - r, cy - r, r * 2, r * 2),
                         Qt.AlignCenter, "SS")

        # --- App title ---
        painter.setFont(QFont("Segoe UI", 26, QFont.Bold))
        painter.setPen(QColor("white"))
        painter.drawText(QRectF(0, cy + r + 12, w, 40),
                         Qt.AlignCenter, "Sleep Sense")

        # --- Subtitle ---
        painter.setFont(QFont("Segoe UI", 10))
        painter.setPen(QColor("#99f6e4"))
        painter.drawText(QRectF(0, cy + r + 54, w, 24),
                         Qt.AlignCenter,
                         "Medical Grade Polysomnography Monitoring System")

        # --- Made by (subtitle ke neeche) ---
        painter.setFont(QFont("Segoe UI", 10, QFont.Medium))
        painter.setPen(QColor("#2dd4bf"))
        painter.drawText(QRectF(0, cy + r + 78, w, 22),
                         Qt.AlignCenter,
                         "Developed by Deckmont Medical Technologies")

        # --- Loading message ---
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor("#2dd4bf"))
        painter.drawText(QRectF(0, h - 36, w, 20),
                         Qt.AlignCenter, self._msg)


def is_already_running():
    """Returns True if another instance of the app is already open."""
    socket = QLocalSocket()
    socket.connectToServer("SleepSenseApp")
    if socket.waitForConnected(500):
        socket.disconnectFromServer()
        return True
    return False


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
    app = QApplication(sys.argv)
    app.setApplicationName("Sleep Sense")

    # --- Single instance check ---
    if is_already_running():
        QMessageBox.information(
            None,
            "Already Running",
            "Sleep Sense is already open.\nCheck the taskbar."
        )
        sys.exit(0)

    # Register this instance
    server = QLocalServer()
    QLocalServer.removeServer("SleepSenseApp")
    server.listen("SleepSenseApp")

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
    run_in_background(app, splash, "Initializing database...", init_db)

    # --- Step 2: Import dashboard module in background ---
    dashboard_holder = [None]

    def import_dashboard():
        from src.components.dashboard import SleepSenseDashboard
        dashboard_holder[0] = SleepSenseDashboard


    
    run_in_background(app, splash, "Loading dashboard...", import_dashboard)

    # --- Step 3: Create window in main thread (Qt requires this) ---
    splash.showMessage("Ready!")
    app.processEvents()

    SleepSenseDashboard = dashboard_holder[0]
    window = SleepSenseDashboard()

    if os.path.exists(app_icon_path):
        window.setWindowIcon(QIcon(app_icon_path))

    window.showMaximized()
    splash.finish(window)

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
