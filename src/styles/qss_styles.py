"""
QSS Styles Module - Python equivalent of QSS files
For PyQt5 application styling - converted from QSS to Python classes
"""

class QSSStyles:
    """Python equivalent of QSS stylesheets for PyQt5 application"""
    
    @staticmethod
    def get_default_style():
        """Default Sleep Sense Dashboard Style"""
        return """
        /* Main Window and Background */
        QMainWindow {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                        stop:0 #f8fafc, stop:1 #dbeafe);
        }

        /* Header Section */
        QWidget#headerWidget {
            background-color: #ffffff;
            border-bottom: 1px solid #e5e7eb;
        }

        QLabel#headerTitle {
            font-size: 18px;
            font-weight: bold;
            color: #1f2937;
        }

        QLabel#headerSubtitle {
            font-size: 12px;
            color: #6b7280;
        }

        /* Logo Container */
        QWidget#logoContainer {
            background-color: #8b5cf6;
            border-radius: 8px;
            min-width: 36px;
            max-width: 36px;
            min-height: 36px;
            max-height: 36px;
        }

        /* Card/Panel Styling */
        QFrame#patientCard, QFrame#chartCard {
            background-color: #ffffff;
            border-radius: 12px;
            border: 1px solid #e5e7eb;
            padding: 16px;
        }

        /* Patient Info Section */
        QLabel#patientName {
            font-size: 18px;
            font-weight: 600;
            color: #1f2937;
        }

        QLabel#patientId {
            font-size: 11px;
            color: #6b7280;
        }

        QLabel#infoLabel {
            font-size: 11px;
            color: #6b7280;
        }

        QLabel#infoValue {
            font-size: 13px;
            font-weight: 500;
            color: #1f2937;
        }

        /* Stats Cards */
        QFrame#statCard {
            background-color: rgba(241, 245, 249, 0.5);
            border-radius: 8px;
            padding: 8px;
        }

        QLabel#statLabel {
            font-size: 11px;
            color: #6b7280;
        }

        QLabel#statValue {
            font-size: 15px;
            font-weight: 600;
            color: #1f2937;
        }

        /* Tab Widget */
        QTabWidget::pane {
            border: none;
            background-color: transparent;
        }

        QTabBar::tab {
            background-color: transparent;
            color: #6b7280;
            padding: 8px 16px;
            border: none;
            border-bottom: 2px solid transparent;
            font-size: 13px;
            font-weight: 500;
        }

        QTabBar::tab:selected {
            color: #8b5cf6;
            border-bottom: 2px solid #8b5cf6;
        }

        QTabBar::tab:hover {
            color: #1f2937;
            background-color: rgba(0, 0, 0, 0.02);
        }

        /* Buttons */
        QPushButton {
            background-color: #8b5cf6;
            color: #ffffff;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 500;
        }

        QPushButton:hover {
            background-color: #7c3aed;
        }

        QPushButton:pressed {
            background-color: #6d28d9;
        }

        QPushButton:disabled {
            background-color: #e5e7eb;
            color: #9ca3af;
        }

        /* Outline Buttons */
        QPushButton#outlineButton {
            background-color: transparent;
            color: #1f2937;
            border: 1px solid #d1d5db;
        }

        QPushButton#outlineButton:hover {
            background-color: #f9fafb;
            border-color: #9ca3af;
        }

        /* Icon Buttons */
        QPushButton#iconButton {
            background-color: transparent;
            color: #6b7280;
            border: none;
            padding: 4px;
            max-width: 32px;
            max-height: 32px;
        }

        QPushButton#iconButton:hover {
            background-color: #f3f4f6;
            border-radius: 4px;
        }

        /* Zoom Buttons */
        QPushButton#zoomButton {
            background-color: #3b82f6;
            color: white;
            border: 1px solid #2563eb;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 700;
            padding: 2px 4px;
            min-width: 28px;
            min-height: 20px;
        }
        QPushButton#zoomButton:hover {
            background-color: #2563eb;
            border-color: #1d4ed8;
        }
        QPushButton#zoomButton:pressed {
            background-color: #1d4ed8;
            border-color: #1e3a8a;
        }

        /* Upload Area */
        QFrame#uploadArea {
            border: 2px dashed #d1d5db;
            border-radius: 8px;
            background-color: transparent;
            padding: 16px;
        }

        QFrame#uploadArea:hover {
            border-color: #8b5cf6;
            background-color: rgba(139, 92, 246, 0.02);
        }

        /* File List Item */
        QFrame#fileItem {
            background-color: #f9fafb;
            border-radius: 8px;
            padding: 8px;
        }

        QFrame#fileItem:hover {
            background-color: #f3f4f6;
        }

        /* Chart Control Bar */
        QFrame#chartControlBar {
            background-color: #f9fafb;
            border-bottom: 1px solid #e5e7eb;
            padding: 8px;
        }

        /* ComboBox / Dropdown */
        QComboBox {
            background-color: #ffffff;
            border: 1px solid #d1d5db;
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 13px;
            color: #1f2937;
            min-height: 28px;
        }

        QComboBox:hover {
            border-color: #8b5cf6;
        }

        QComboBox::drop-down {
            border: none;
            width: 20px;
        }

        QComboBox::down-arrow {
            image: url(down-arrow.png);
            width: 12px;
            height: 12px;
        }

        QComboBox QAbstractItemView {
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
            selection-background-color: #f3f4f6;
            selection-color: #1f2937;
        }

        /* ScrollBar */
        QScrollBar:vertical {
            background-color: #f9fafb;
            width: 8px;
            border-radius: 4px;
        }

        QScrollBar::handle:vertical {
            background-color: #d1d5db;
            border-radius: 4px;
            min-height: 20px;
        }

        QScrollBar::handle:vertical:hover {
            background-color: #9ca3af;
        }

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }

        QScrollBar:horizontal {
            background-color: #f9fafb;
            height: 8px;
            border-radius: 4px;
        }

        QScrollBar::handle:horizontal {
            background-color: #d1d5db;
            border-radius: 4px;
            min-width: 20px;
        }

        QScrollBar::handle:horizontal:hover {
            background-color: #9ca3af;
        }

        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0px;
        }

        /* Input Fields */
        QLineEdit {
            background-color: #ffffff;
            border: 1px solid #d1d5db;
            border-radius: 6px;
            padding: 8px 12px;
            font-size: 13px;
            color: #1f2937;
        }

        QLineEdit:focus {
            border-color: #8b5cf6;
            outline: none;
        }

        QLineEdit:disabled {
            background-color: #f9fafb;
            color: #9ca3af;
        }

        /* Icon Circle Backgrounds */
        QFrame#iconCirclePrimary {
            background-color: rgba(139, 92, 246, 0.1);
            border-radius: 16px;
            min-width: 32px;
            max-width: 32px;
            min-height: 32px;
            max-height: 32px;
        }

        QFrame#iconCircleBlue {
            background-color: rgba(59, 130, 246, 0.1);
            border-radius: 16px;
            min-width: 32px;
            max-width: 32px;
            min-height: 32px;
            max-height: 32px;
        }

        QFrame#iconCirclePurple {
            background-color: rgba(139, 92, 246, 0.1);
            border-radius: 16px;
            min-width: 32px;
            max-width: 32px;
            min-height: 32px;
            max-height: 32px;
        }

        QFrame#iconCircleGreen {
            background-color: rgba(16, 185, 129, 0.1);
            border-radius: 16px;
            min-width: 32px;
            max-width: 32px;
            min-height: 32px;
            max-height: 32px;
        }

        /* Separator/Divider */
        QFrame[frameShape="4"] {
            color: #e5e7eb;
            background-color: #e5e7eb;
            max-height: 1px;
        }

        QFrame[frameShape="5"] {
            color: #e5e7eb;
            background-color: #e5e7eb;
            max-width: 1px;
        }

        /* Tooltip */
        QToolTip {
            background-color: #1f2937;
            color: #ffffff;
            border: none;
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 12px;
        }

        /* Chart Background */
        QFrame#chartBackground {
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
        }

        /* Signal Chart Containers */
        QWidget#signalChartContainer {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            margin: 1px;
        }

        QWidget#signalChartContainer:hover {
            border-color: #cbd5e1;
            background-color: #fafbfc;
        }

        /* Plot Container */
        QWidget#plotContainer {
            background-color: #ffffff;
            border: none;
            border-radius: 6px;
            margin: 1px;
        }

        /* Zoom Controls Frame */
        QFrame#zoomControlsFrame {
            background-color: #f1f5f9;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
            padding: 1px;
        }

        /* Buttons Container */
        QFrame#buttonsContainer {
            background-color: transparent;
            border: none;
            padding: 0px;
        }

        /* Time Labels */
        QLabel#timeLabel {
            font-family: 'Courier New', monospace;
            font-size: 12px;
            color: #6b7280;
        }

        /* Signal Labels */
        QLabel#signalLabel {
            font-size: 11px;
            font-weight: 500;
            color: #4b5563;
            background-color: rgba(255, 255, 255, 0.8);
            padding: 4px 8px;
            border-radius: 4px;
        }

        /* Status Bar */
        QStatusBar {
            background-color: #f9fafb;
            border-top: 1px solid #e5e7eb;
            color: #6b7280;
            font-size: 11px;
        }

        /* Menu Bar */
        QMenuBar {
            background-color: #ffffff;
            border-bottom: 1px solid #e5e7eb;
            padding: 4px;
        }

        QMenuBar::item {
            background-color: transparent;
            color: #1f2937;
            padding: 6px 12px;
            font-size: 13px;
        }

        QMenuBar::item:selected {
            background-color: #f3f4f6;
            border-radius: 4px;
        }

        QMenu {
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            padding: 4px;
        }

        QMenu::item {
            background-color: transparent;
            color: #1f2937;
            padding: 8px 16px;
            font-size: 13px;
        }

        QMenu::item:selected {
            background-color: #f3f4f6;
            border-radius: 4px;
        }

        /* Group Box */
        QGroupBox {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 12px;
            font-weight: 500;
            color: #1f2937;
        }

        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 8px;
            background-color: #ffffff;
            color: #1f2937;
        }

        /* Progress Bar */
        QProgressBar {
            border: 1px solid #e5e7eb;
            border-radius: 4px;
            background-color: #f3f4f6;
            text-align: center;
            color: #1f2937;
            font-size: 11px;
        }

        QProgressBar::chunk {
            background-color: #8b5cf6;
            border-radius: 3px;
        }

        /* Slider */
        QSlider::groove:horizontal {
            border: none;
            height: 4px;
            background-color: #e5e7eb;
            border-radius: 2px;
        }

        QSlider::handle:horizontal {
            background-color: #8b5cf6;
            width: 16px;
            height: 16px;
            margin: -6px 0;
            border-radius: 8px;
        }

        QSlider::handle:horizontal:hover {
            background-color: #7c3aed;
        }

        /* CheckBox */
        QCheckBox {
            color: #1f2937;
            font-size: 13px;
            spacing: 8px;
        }

        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border: 2px solid #d1d5db;
            border-radius: 4px;
            background-color: #ffffff;
        }

        QCheckBox::indicator:checked {
            background-color: #8b5cf6;
            border-color: #8b5cf6;
            image: url(checkmark.png);
        }

        QCheckBox::indicator:hover {
            border-color: #8b5cf6;
        }

        /* Radio Button */
        QRadioButton {
            color: #1f2937;
            font-size: 13px;
            spacing: 8px;
        }

        QRadioButton::indicator {
            width: 18px;
            height: 18px;
            border: 2px solid #d1d5db;
            border-radius: 9px;
            background-color: #ffffff;
        }

        QRadioButton::indicator:checked {
            background-color: #8b5cf6;
            border-color: #8b5cf6;
        }

        QRadioButton::indicator:hover {
            border-color: #8b5cf6;
        }

        /* Table Widget */
        QTableWidget {
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            gridline-color: #e5e7eb;
            font-size: 13px;
        }

        QTableWidget::item {
            padding: 8px;
            color: #1f2937;
        }

        QTableWidget::item:selected {
            background-color: #f3f4f6;
            color: #1f2937;
        }

        QHeaderView::section {
            background-color: #f9fafb;
            color: #6b7280;
            padding: 8px;
            border: none;
            border-bottom: 1px solid #e5e7eb;
            font-weight: 500;
            font-size: 12px;
        }

        /* Spin Box */
        QSpinBox, QDoubleSpinBox {
            background-color: #ffffff;
            border: 1px solid #d1d5db;
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 13px;
            color: #1f2937;
        }

        QSpinBox:focus, QDoubleSpinBox:focus {
            border-color: #8b5cf6;
        }

        QSpinBox::up-button, QDoubleSpinBox::up-button {
            border-left: 1px solid #d1d5db;
            border-bottom: 1px solid #d1d5db;
            border-top-right-radius: 4px;
        }

        QSpinBox::down-button, QDoubleSpinBox::down-button {
            border-left: 1px solid #d1d5db;
            border-bottom-right-radius: 4px;
        }
        """

    @staticmethod
    def get_medical_white_style():
        """Medical White Theme Style"""
        return """
        /* MAIN WINDOW */
        QMainWindow {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                        stop:0 #f9fafb, stop:0.5 #eff6ff, stop:1 #f3f4f6);
        }

        QWidget#centralWidget {
            background: transparent;
        }

        /* HEADER */
        QWidget#headerWidget {
            background-color: #ffffff;
            border-bottom: 2px solid #dbeafe;
        }

        QLabel#headerTitle {
            font-size: 24px;
            font-weight: bold;
            color: #111827;
            letter-spacing: -0.5px;
        }

        QLabel#headerSubtitle {
            font-size: 14px;
            color: #4b5563;
        }

        /* Logo Container */
        QFrame#logoContainer {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                        stop:0 #34d399, stop:1 #10b981);
            border-radius: 12px;
            min-width: 120px;
            max-width: 120px;
            min-height: 44px;
            max-height: 44px;
        }

        /* Status Badges */
        QFrame#liveSessionBadge {
            background-color: #eff6ff;
            border: 1px solid #bfdbfe;
            border-radius: 16px;
            padding: 4px 12px;
        }

        QLabel#liveSessionText {
            color: #1e40af;
            font-size: 12px;
            font-weight: 600;
        }

        /* Medical Grade Cards */
        QFrame#medicalCard {
            background-color: #ffffff;
            border: 2px solid #e5e7eb;
            border-radius: 16px;
            padding: 20px;
        }

        QFrame#medicalCard:hover {
            border-color: #3b82f6;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
        }

        /* Patient Info Panel */
        QLabel#patientName {
            font-size: 20px;
            font-weight: 700;
            color: #111827;
        }

        QLabel#patientId {
            font-size: 14px;
            color: #6b7280;
            font-family: 'Courier New', monospace;
        }

        /* Vital Signs */
        QFrame#vitalSignFrame {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 12px;
        }

        QLabel#vitalSignLabel {
            font-size: 12px;
            color: #64748b;
            font-weight: 500;
        }

        QLabel#vitalSignValue {
            font-size: 18px;
            font-weight: 700;
            color: #0f172a;
        }

        QLabel#vitalSignUnit {
            font-size: 11px;
            color: #64748b;
        }

        /* Medical Buttons */
        QPushButton {
            background-color: #3b82f6;
            color: #ffffff;
            border: none;
            border-radius: 8px;
            padding: 10px 20px;
            font-size: 14px;
            font-weight: 600;
        }

        QPushButton:hover {
            background-color: #2563eb;
        }

        QPushButton:pressed {
            background-color: #1d4ed8;
        }

        QPushButton#emergencyButton {
            background-color: #ef4444;
        }

        QPushButton#emergencyButton:hover {
            background-color: #dc2626;
        }

        /* Zoom Buttons - Medical Theme */
        QPushButton#zoomButton {
            background-color: #10b981;
            color: white;
            border: 1px solid #059669;
            border-radius: 6px;
            font-size: 12px;
            font-weight: bold;
            padding: 2px;
        }
        QPushButton#zoomButton:hover {
            background-color: #059669;
            border-color: #047857;
        }
        QPushButton#zoomButton:pressed {
            background-color: #047857;
            border-color: #065f46;
        }

        /* Medical Charts */
        QFrame#chartFrame {
            background-color: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 16px;
        }

        QLabel#chartTitle {
            font-size: 16px;
            font-weight: 600;
            color: #1f2937;
        }

        QLabel#chartSubtitle {
            font-size: 12px;
            color: #6b7280;
        }

        /* Alert Status */
        QFrame#alertFrame {
            background-color: #fef2f2;
            border: 1px solid #fecaca;
            border-radius: 8px;
            padding: 12px;
        }

        QLabel#alertText {
            color: #991b1b;
            font-size: 13px;
            font-weight: 500;
        }

        QFrame#warningFrame {
            background-color: #fffbeb;
            border: 1px solid #fed7aa;
            border-radius: 8px;
            padding: 12px;
        }

        QLabel#warningText {
            color: #92400e;
            font-size: 13px;
            font-weight: 500;
        }

        QFrame#normalFrame {
            background-color: #f0fdf4;
            border: 1px solid #bbf7d0;
            border-radius: 8px;
            padding: 12px;
        }

        QLabel#normalText {
            color: #166534;
            font-size: 13px;
            font-weight: 500;
        }
        """

    @staticmethod
    def get_modern_style():
        """Modern Dark Glassmorphism Theme Style"""
        return """
        /* Main Window - Dark Gradient Background */
        QMainWindow {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                        stop:0 #1e1b4b, stop:0.5 #581c87, stop:1 #0f172a);
        }

        /* Central Widget */
        QWidget#centralWidget {
            background: transparent;
        }

        /* GLASSMORPHISM CARDS */
        QFrame#glassCard {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 24px;
            padding: 24px;
        }

        QFrame#patientPanel {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 24px;
            padding: 24px;
        }

        QFrame#chartPanel {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 24px;
        }

        /* HEADER */
        QWidget#headerWidget {
            background: rgba(255, 255, 255, 0.1);
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
        }

        QLabel#headerTitle {
            font-size: 24px;
            font-weight: bold;
            color: #ffffff;
        }

        QLabel#headerSubtitle {
            font-size: 14px;
            color: rgba(255, 255, 255, 0.7);
        }

        /* Logo Container */
        QFrame#logoContainer {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                                        stop:0 #8b5cf6, stop:1 #3b82f6);
            border-radius: 16px;
            min-width: 48px;
            max-width: 48px;
            min-height: 48px;
            max-height: 48px;
        }

        /* Modern Buttons */
        QPushButton {
            background: rgba(139, 92, 246, 0.8);
            color: #ffffff;
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            padding: 12px 24px;
            font-size: 14px;
            font-weight: 600;
        }

        QPushButton:hover {
            background: rgba(139, 92, 246, 1);
            border-color: rgba(255, 255, 255, 0.3);
        }

        QPushButton:pressed {
            background: rgba(107, 70, 193, 1);
        }

        /* Zoom Buttons - Modern Theme */
        QPushButton#zoomButton {
            background: rgba(139, 92, 246, 0.8);
            color: #ffffff;
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 6px;
            font-size: 12px;
            font-weight: bold;
            padding: 2px;
        }
        QPushButton#zoomButton:hover {
            background: rgba(139, 92, 246, 1);
            border-color: rgba(255, 255, 255, 0.5);
        }
        QPushButton#zoomButton:pressed {
            background: rgba(107, 70, 193, 1);
            border-color: rgba(255, 255, 255, 0.7);
        }

        /* Glass Input Fields */
        QLineEdit {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            padding: 12px 16px;
            font-size: 14px;
            color: #ffffff;
        }

        QLineEdit:focus {
            background: rgba(255, 255, 255, 0.15);
            border-color: rgba(139, 92, 246, 0.5);
        }

        /* Modern Labels */
        QLabel {
            color: #ffffff;
        }

        QLabel#patientName {
            font-size: 20px;
            font-weight: 700;
            color: #ffffff;
        }

        QLabel#patientId {
            font-size: 12px;
            color: rgba(255, 255, 255, 0.6);
        }

        QLabel#infoLabel {
            font-size: 12px;
            color: rgba(255, 255, 255, 0.6);
        }

        QLabel#infoValue {
            font-size: 14px;
            font-weight: 600;
            color: #ffffff;
        }

        /* Modern Tabs */
        QTabWidget::pane {
            border: none;
            background-color: transparent;
        }

        QTabBar::tab {
            background-color: rgba(255, 255, 255, 0.05);
            color: rgba(255, 255, 255, 0.7);
            padding: 12px 20px;
            border: none;
            border-bottom: 2px solid transparent;
            font-size: 14px;
            font-weight: 500;
            border-radius: 8px 8px 0 0;
        }

        QTabBar::tab:selected {
            background-color: rgba(139, 92, 246, 0.2);
            color: #ffffff;
            border-bottom: 2px solid #8b5cf6;
        }

        QTabBar::tab:hover {
            background-color: rgba(255, 255, 255, 0.1);
            color: #ffffff;
        }

        /* Modern ComboBox */
        QComboBox {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 14px;
            color: #ffffff;
            min-height: 32px;
        }

        QComboBox:hover {
            background: rgba(255, 255, 255, 0.15);
            border-color: rgba(139, 92, 246, 0.5);
        }

        QComboBox QAbstractItemView {
            background: rgba(30, 27, 75, 0.95);
            border: 1px solid rgba(139, 92, 246, 0.3);
            selection-background-color: rgba(139, 92, 246, 0.3);
            selection-color: #ffffff;
            color: #ffffff;
        }

        /* Modern ScrollBar */
        QScrollBar:vertical {
            background: rgba(255, 255, 255, 0.05);
            width: 12px;
            border-radius: 6px;
        }

        QScrollBar::handle:vertical {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 6px;
            min-height: 20px;
        }

        QScrollBar::handle:vertical:hover {
            background: rgba(255, 255, 255, 0.3);
        }

        /* Modern Charts */
        QFrame#chartBackground {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
        }

        QLabel#chartTitle {
            font-size: 16px;
            font-weight: 600;
            color: #ffffff;
        }

        QLabel#signalLabel {
            font-size: 12px;
            font-weight: 500;
            color: rgba(255, 255, 255, 0.8);
            background-color: rgba(0, 0, 0, 0.3);
            padding: 6px 12px;
            border-radius: 8px;
        }

        /* Modern Status */
        QStatusBar {
            background: rgba(255, 255, 255, 0.05);
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            color: rgba(255, 255, 255, 0.7);
            font-size: 12px;
        }

        /* Modern Tooltip */
        QToolTip {
            background-color: rgba(30, 27, 75, 0.95);
            color: #ffffff;
            border: 1px solid rgba(139, 92, 246, 0.3);
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 12px;
        }
        """

class StyleManager:
    """Style management for PyQt5 application"""
    
    def __init__(self):
        self.current_style = "default"
        self.qss_styles = QSSStyles()
    
    def apply_style(self, app, style_name="default"):
        """Apply specified style to application"""
        if style_name == "default":
            stylesheet = self.qss_styles.get_default_style()
        elif style_name == "medical_white":
            stylesheet = self.qss_styles.get_medical_white_style()
        elif style_name == "modern":
            stylesheet = self.qss_styles.get_modern_style()
        else:
            stylesheet = self.qss_styles.get_default_style()
        
        app.setStyleSheet(stylesheet)
        self.current_style = style_name
    
    def get_available_styles(self):
        """Get list of available styles"""
        return ["default", "medical_white", "modern"]
    
    def get_current_style(self):
        """Get current style name"""
        return self.current_style

# Global style manager instance
style_manager = StyleManager()

def get_style_manager():
    """Get global style manager instance"""
    return style_manager

def apply_style(app, style_name="default"):
    """Apply style to application"""
    style_manager.apply_style(app, style_name)
