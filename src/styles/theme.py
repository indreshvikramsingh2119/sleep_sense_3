"""
Theme System - Python equivalent of theme.css
For PyQt5 application styling and theming
"""

from PyQt5.QtCore import QObject
from PyQt5.QtGui import QColor

class ThemeColors:
    """Theme color definitions for PyQt5 application"""
    
    # Light theme colors
    LIGHT = {
        'font_size': 16,
        'background': '#ffffff',
        'foreground': '#212529',  # oklch(0.145 0 0) approx
        'card': '#ffffff',
        'card_foreground': '#212529',
        'popover': '#ffffff',
        'popover_foreground': '#212529',
        'primary': '#030213',
        'primary_foreground': '#ffffff',
        'secondary': '#f8f9fa',  # oklch(0.95 0.0058 264.53) approx
        'secondary_foreground': '#030213',
        'muted': '#ececf0',
        'muted_foreground': '#717182',
        'accent': '#e9ebef',
        'accent_foreground': '#030213',
        'destructive': '#d4183d',
        'destructive_foreground': '#ffffff',
        'border': 'rgba(0, 0, 0, 0.1)',
        'input': 'transparent',
        'input_background': '#f3f3f5',
        'switch_background': '#cbced4',
        'font_weight_medium': 500,
        'font_weight_normal': 400,
        'ring': '#adb5bd',  # oklch(0.708 0 0) approx
        'chart_1': '#ff6b6b',  # oklch(0.646 0.222 41.116) approx
        'chart_2': '#4ecdc4',  # oklch(0.6 0.118 184.704) approx
        'chart_3': '#45b7d1',  # oklch(0.398 0.07 227.392) approx
        'chart_4': '#96ceb4',  # oklch(0.828 0.189 84.429) approx
        'chart_5': '#ffeaa7',  # oklch(0.769 0.188 70.08) approx
        'radius': '10px',  # 0.625rem approx
        'sidebar': '#fafafa',  # oklch(0.985 0 0) approx
        'sidebar_foreground': '#212529',
        'sidebar_primary': '#030213',
        'sidebar_primary_foreground': '#fafafa',
        'sidebar_accent': '#f8f9fa',  # oklch(0.97 0 0) approx
        'sidebar_accent_foreground': '#343a40',  # oklch(0.205 0 0) approx
        'sidebar_border': '#e9ecef',  # oklch(0.922 0 0) approx
        'sidebar_ring': '#adb5bd',  # oklch(0.708 0 0) approx
    }
    
    # Dark theme colors
    DARK = {
        'background': '#212529',  # oklch(0.145 0 0) approx
        'foreground': '#f8f9fa',  # oklch(0.985 0 0) approx
        'card': '#212529',
        'card_foreground': '#f8f9fa',
        'popover': '#212529',
        'popover_foreground': '#f8f9fa',
        'primary': '#f8f9fa',  # oklch(0.985 0 0) approx
        'primary_foreground': '#343a40',  # oklch(0.205 0 0) approx
        'secondary': '#495057',  # oklch(0.269 0 0) approx
        'secondary_foreground': '#f8f9fa',
        'muted': '#495057',
        'muted_foreground': '#adb5bd',  # oklch(0.708 0 0) approx
        'accent': '#495057',
        'accent_foreground': '#f8f9fa',
        'destructive': '#dc3545',  # oklch(0.396 0.141 25.723) approx
        'destructive_foreground': '#f8f9fa',
        'border': '#495057',
        'input': '#495057',
        'ring': '#6c757d',  # oklch(0.439 0 0) approx
        'font_weight_medium': 500,
        'font_weight_normal': 400,
        'chart_1': '#6f42c1',  # oklch(0.488 0.243 264.376) approx
        'chart_2': '#20c997',  # oklch(0.696 0.17 162.48) approx
        'chart_3': '#ffeaa7',  # oklch(0.769 0.188 70.08) approx
        'chart_4': '#fd79a8',  # oklch(0.627 0.265 303.9) approx
        'chart_5': '#a29bfe',  # oklch(0.645 0.246 16.439) approx
        'sidebar': '#343a40',  # oklch(0.205 0 0) approx
        'sidebar_foreground': '#f8f9fa',
        'sidebar_primary': '#6f42c1',  # oklch(0.488 0.243 264.376) approx
        'sidebar_primary_foreground': '#f8f9fa',
        'sidebar_accent': '#495057',
        'sidebar_accent_foreground': '#f8f9fa',
        'sidebar_border': '#495057',
        'sidebar_ring': '#6c757d',  # oklch(0.439 0 0) approx
    }

class ThemeManager(QObject):
    """Theme management for PyQt5 application"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_dark = False
        self._current_theme = ThemeColors.LIGHT
    
    def set_theme(self, is_dark=False):
        """Set current theme"""
        self._is_dark = is_dark
        self._current_theme = ThemeColors.DARK if is_dark else ThemeColors.LIGHT
    
    def get_color(self, color_name):
        """Get color from current theme"""
        return self._current_theme.get(color_name, '#000000')
    
    def get_stylesheet(self, widget_type='QWidget'):
        """Generate stylesheet for widget type"""
        colors = self._current_theme
        
        base_styles = {
            'QWidget': f"""
                QWidget {{
                    background-color: {colors['background']};
                    color: {colors['foreground']};
                    border: 1px solid {colors['border']};
                    font-size: {colors['font_size']}px;
                }}
            """,
            'QPushButton': f"""
                QPushButton {{
                    background-color: {colors['primary']};
                    color: {colors['primary_foreground']};
                    border: 1px solid {colors['border']};
                    padding: 8px 16px;
                    font-weight: {colors['font_weight_medium']};
                    border-radius: {colors['radius']};
                }}
                QPushButton:hover {{
                    background-color: {colors['accent']};
                }}
                QPushButton:pressed {{
                    background-color: {colors['secondary']};
                }}
            """,
            'QLabel': f"""
                QLabel {{
                    background-color: transparent;
                    color: {colors['foreground']};
                    font-weight: {colors['font_weight_medium']};
                }}
            """,
            'QFrame': f"""
                QFrame {{
                    background-color: {colors['card']};
                    border: 1px solid {colors['border']};
                    border-radius: {colors['radius']};
                }}
            """
        }
        
        return base_styles.get(widget_type, base_styles['QWidget'])
    
    def is_dark_theme(self):
        """Check if current theme is dark"""
        return self._is_dark

# Global theme manager instance
theme_manager = ThemeManager()

def get_theme_manager():
    """Get global theme manager instance"""
    return theme_manager

def apply_theme_to_widget(widget, widget_type='QWidget'):
    """Apply current theme to widget"""
    if widget:
        stylesheet = theme_manager.get_stylesheet(widget_type)
        widget.setStyleSheet(stylesheet)
