"""Shared dialog helpers for consistent warning popups."""

from PyQt5.QtWidgets import QMessageBox


def show_styled_warning(parent, title, message, button_text="OK"):
    """Show a warning dialog with a more visible confirmation button."""
    dialog = QMessageBox(parent)
    dialog.setIcon(QMessageBox.Warning)
    dialog.setWindowTitle(title)
    dialog.setText(message)
    dialog.setStandardButtons(QMessageBox.Ok)
    dialog.setDefaultButton(QMessageBox.Ok)
    dialog.setMinimumWidth(440)
    dialog.setStyleSheet("""
        QMessageBox {
            background-color: #f8fafc;
        }
        QMessageBox QLabel {
            color: #0f172a;
            font-size: 12px;
        }
        QMessageBox QPushButton {
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 #3b82f6,
                stop: 0.5 #2563eb,
                stop: 1 #1d4ed8
            );
            color: white;
            border: 1px solid #1e40af;
            border-radius: 8px;
            padding: 7px 16px;
            min-width: 92px;
            font-size: 12px;
            font-weight: 700;
        }
        QMessageBox QPushButton:hover {
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 #60a5fa,
                stop: 0.5 #3b82f6,
                stop: 1 #2563eb
            );
        }
        QMessageBox QPushButton:pressed {
            background: qlineargradient(
                x1: 0, y1: 0, x2: 0, y2: 1,
                stop: 0 #1d4ed8,
                stop: 0.5 #1e40af,
                stop: 1 #1e3a8a
            );
        }
    """)

    button = dialog.button(QMessageBox.Ok)
    if button is not None:
        button.setText(button_text)
        # Apply the button style directly as well. Some parent-window themes
        # override descendant QMessageBox rules and otherwise leave only the
        # bare "OK" text visible.
        button.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: #ffffff;
                border: 1px solid #1e40af;
                border-radius: 5px;
                padding: 6px 16px;
                min-width: 72px;
                min-height: 20px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #3b82f6;
                border-color: #1d4ed8;
            }
            QPushButton:pressed {
                background-color: #1e40af;
            }
        """)
        button.setMinimumSize(88, 34)
        button.setFlat(False)

    return dialog.exec_()
