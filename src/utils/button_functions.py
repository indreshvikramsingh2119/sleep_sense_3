"""
Button Functions Module - Sleep Sense Application
Contains all button click handlers and menu functionality
"""

import os
from datetime import datetime
import shutil
import subprocess
import webbrowser
import json
import csv
import platform
import tempfile
import sys
from pathlib import Path
from urllib.parse import quote
from PyQt5.QtWidgets import (
    QFileDialog, QMessageBox, QInputDialog, QLineEdit, QPushButton, QMenu, QAction, QWidget, QDialog, QVBoxLayout,
    QHBoxLayout, QListWidget, QLabel, QComboBox, QCheckBox, QGroupBox, QGridLayout, QSpacerItem, QSizePolicy,
    QRadioButton, QButtonGroup, QSpinBox, QTextEdit, QSlider, QTabWidget, QFormLayout, QFrame
)
from PyQt5.QtCore import Qt, QUrl, QRegExp
from PyQt5.QtGui import QTextDocument, QPixmap, QPainter, QColor, QPen, QRegExpValidator
from PyQt5.QtPrintSupport import QPrintDialog, QPrinter
from .app_paths import get_resource_path as get_asset_path

_APP_ROOT = Path(__file__).resolve().parents[2]
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

ANALYSIS_PARAMS_IMPORT_ERROR = None
try:
    from ai_models.sleep_apnea import detect_apnea_from_airflow as apnea_detector
except Exception as import_error:
    apnea_detector = None
    ANALYSIS_PARAMS_IMPORT_ERROR = str(import_error)


def _detector_default(key, fallback):
    """Read one built-in default from the detector, falling back if unavailable."""
    if apnea_detector is None:
        return fallback
    try:
        return apnea_detector.get_default_analysis_parameters().get(key, fallback)
    except Exception:
        return fallback


class ButtonFunctions:
    """Class containing all button and menu functionality"""
    
    def __init__(self, parent_window):
        self.parent = parent_window
    
    def create_custom_menu_buttons(self, layout):
        """Create custom menu buttons as clickable buttons instead of system menu bar"""
        
        # File Menu Button
        file_btn = QPushButton('File')
        file_btn.setObjectName("menuButton")
        file_btn.setMinimumWidth(80)
        file_btn.setMinimumHeight(35)
        file_btn.setStyleSheet("""
            QPushButton#menuButton {
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
                border: 1px solid #ccc;
                border-radius: 6px;
                background-color: #f8f9fa;
            }
            QPushButton#menuButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
            QPushButton#menuButton:pressed {
                background-color: #dee2e6;
            }
        """)
        file_btn.clicked.connect(lambda: self.show_menu_popup(file_btn, 'file'))
        layout.addWidget(file_btn)
        
        # Edit Menu Button
        # edit_btn = QPushButton('Edit')
        # edit_btn.setObjectName("menuButton")
        # edit_btn.setMinimumWidth(80)
        # edit_btn.setMinimumHeight(35)
        # edit_btn.setStyleSheet("""
        #     QPushButton#menuButton {
        #         padding: 8px 16px;
        #         font-size: 13px;
        #         font-weight: 500;
        #         border: 1px solid #ccc;
        #         border-radius: 6px;
        #         background-color: #f8f9fa;
        #     }
        #     QPushButton#menuButton:hover {
        #         background-color: #e9ecef;
        #         border-color: #adb5bd;
        #     }
        #     QPushButton#menuButton:pressed {
        #         background-color: #dee2e6;
        #     }
        # """)
        # edit_btn.clicked.connect(lambda: self.show_menu_popup(edit_btn, 'edit'))
        # layout.addWidget(edit_btn)
        
        # Tools Menu Button
        tools_btn = QPushButton('Tools')
        tools_btn.setObjectName("menuButton")
        tools_btn.setMinimumWidth(80)
        tools_btn.setMinimumHeight(35)
        tools_btn.setStyleSheet("""
            QPushButton#menuButton {
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
                border: 1px solid #ccc;
                border-radius: 6px;
                background-color: #f8f9fa;
            }
            QPushButton#menuButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
            QPushButton#menuButton:pressed {
                background-color: #dee2e6;
            }
        """)
        tools_btn.clicked.connect(lambda: self.show_menu_popup(tools_btn, 'tools'))
        layout.addWidget(tools_btn)
        
        # Help Menu Button
        help_btn = QPushButton('Help')
        help_btn.setObjectName("menuButton")
        help_btn.setMinimumWidth(80)
        help_btn.setMinimumHeight(35)
        help_btn.setStyleSheet("""
            QPushButton#menuButton {
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
                border: 1px solid #ccc;
                border-radius: 6px;
                background-color: #f8f9fa;
            }
            QPushButton#menuButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
            QPushButton#menuButton:pressed {
                background-color: #dee2e6;
            }
        """)
        help_btn.clicked.connect(lambda: self.show_menu_popup(help_btn, 'help'))
        layout.addWidget(help_btn)
        
        layout.addStretch()
    
    def show_menu_popup(self, button, menu_type):
        """Show popup menu for custom menu buttons"""
        from PyQt5.QtWidgets import QMenu
        
        menu = QMenu(self.parent)
        # Apply professional styling to the menu
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 8px;
                padding: 4px 0px;
                font-size: 13px;
                font-weight: 500;
                color: #374151;
            }
            QMenu::item {
                background-color: transparent;
                padding: 8px 16px;
                margin: 2px 3px;
                border-radius: 6px;
                color: #374151;
            }
            QMenu::item:selected {
                background-color: #3b82f6;
                color: #ffffff;
            }
            QMenu::item:pressed {
                background-color: #2563eb;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: #e5e7eb;
                margin: 4px 12px;
            }
            QMenu::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #d1d5db;
                border-radius: 3px;
                background-color: #ffffff;
            }
            QMenu::indicator:checked {
                background-color: #3b82f6;
                border-color: #3b82f6;
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEwIDNMNC41IDguNUwyIDEiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+Cjwvc3ZnPgo=);
            }
        """)
        
        if menu_type == 'file':
            # custom file menu matching requested image
            menu.addSeparator()
            # menu.addAction('Database', self.file_database)
            # menu.addAction('Archive', self.file_open_archive)
            # save_action = menu.addAction('Save report locally', self.file_save_report_locally)
            # Example: disable if no report available
            # save_action.setEnabled(bool(getattr(self.parent, 'has_report', True)))
            # menu.addAction('Print report', self.file_print_report)
            
            menu.addSeparator()
            # dup_action = menu.addAction('Duplicate', self.file_duplicate)
            # dup_action.setEnabled(True)  # will validate inside handler
            # Export submenu
            # export_menu = QMenu('Export', menu)
            # export_menu.addAction('Export as CSV', lambda: self.file_export('csv'))
            # export_menu.addAction('Export as JSON', lambda: self.file_export('json'))
            # menu.addMenu(export_menu)
            # menu.addAction('Import recording', self.file_import_recording)
            
            menu.addSeparator()
            send_report_action = menu.addAction('Send report by email', self.file_send_report_email)
            send_report_action.setEnabled(True)  # enabled if report exists (checked inside)
            # send_rec_action = menu.addAction('Send recording by email', self.file_send_recording_email)
            # send_rec_action.setEnabled(True)
            menu.addSeparator()
            menu.addAction('Exit App', self.parent.close)
            
        # elif menu_type == 'edit':
        #     menu.addAction('Undo', self.edit_undo, 'Ctrl+Z')
        #     menu.addAction('Redo', self.edit_redo, 'Ctrl+Y')
        #     menu.addSeparator()
        #     
        #     
        elif menu_type == 'tools':
            menu.addAction('Re-analyze', self.tools_reanalyze)
            menu.addAction('Analysis parameters', self.tools_settings_analysis_parameters)
            menu.addSeparator()
        #     menu.addAction('New event group', self.tools_new_event_group)
        #     menu.addAction('Delete event group', self.tools_delete_event_group)
        #     menu.addAction('Edit event group', self.tools_edit_event_group)
        #     menu.addSeparator()
        #     settings_menu = menu.addMenu('Settings')
        #     settings_menu.addAction('Report', self.tools_settings_report)
        #     settings_menu.addAction('Analysis parameters', self.tools_settings_analysis_parameters)
        #     settings_menu.addAction('EDF export', self.tools_settings_edf_export)
        #     
        elif menu_type == 'help':
            menu.addAction('Clinical Guide', self.help_clinical_guide)
            menu.addAction('Patient instructions', self.help_patient_instructions)
            menu.addAction('Program info', self.help_program_info)
            menu.addAction('Recording info', self.help_recording_info)
            menu.addAction('Device info', self.help_device_info)
        
        # Show menu below the button with correct positioning
        button_rect = button.rect()
        # Get the global position of the button's bottom-left corner
        global_pos = button.mapToGlobal(button_rect.bottomLeft())
        # Ensure menu appears directly below button without offset
        menu.exec_(global_pos)
    
    def create_menu_bar(self):
        """Create application menu bar with File and Help menus"""
        menubar = self.parent.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu('File')
        
        new_action = QAction('New', self.parent)
        new_action.setShortcut('Ctrl+N')
        new_action.setStatusTip('Create new session')
        new_action.triggered.connect(self.file_new)
        file_menu.addAction(new_action)
        
        open_action = QAction('Open', self.parent)
        open_action.setShortcut('Ctrl+O')
        open_action.setStatusTip('Open existing file')
        open_action.triggered.connect(self.file_open)
        file_menu.addAction(open_action)
        
        save_action = QAction('Save', self.parent)
        save_action.setShortcut('Ctrl+S')
        save_action.setStatusTip('Save current session')
        save_action.triggered.connect(self.file_save)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        export_action = QAction('Export Data', self.parent)
        export_action.setShortcut('Ctrl+E')
        export_action.setStatusTip('Export monitoring data')
        export_action.triggered.connect(self.file_export)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('Exit', self.parent)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.setStatusTip('Exit application')
        exit_action.triggered.connect(self.parent.close)
        file_menu.addAction(exit_action)
        
        # Edit Menu
        # edit_menu = menubar.addMenu('Edit')
        # 
        # undo_action = QAction('Undo', self.parent)
        # undo_action.setShortcut('Ctrl+Z')
        # undo_action.setStatusTip('Undo last action')
        # undo_action.triggered.connect(self.edit_undo)
        # edit_menu.addAction(undo_action)
        # 
        # redo_action = QAction('Redo', self.parent)
        # redo_action.setShortcut('Ctrl+Y')
        # redo_action.setStatusTip('Redo last action')
        # redo_action.triggered.connect(self.edit_redo)
        # edit_menu.addAction(redo_action)
        # 
        # edit_menu.addSeparator()
        # 
        # copy_action = QAction('Copy', self.parent)
        # copy_action.setShortcut('Ctrl+C')
        # copy_action.setStatusTip('Copy selection')
        # copy_action.triggered.connect(self.edit_copy)
        # edit_menu.addAction(copy_action)
        # 
        # paste_action = QAction('Paste', self.parent)
        # paste_action.setShortcut('Ctrl+V')
        # paste_action.setStatusTip('Paste from clipboard')
        # paste_action.triggered.connect(self.edit_paste)
        # edit_menu.addAction(paste_action)
        # 
        # Tools Menu
        # tools_menu = menubar.addMenu('Tools')
        # 
        # 
        # 
        # settings_action = QAction('Settings', self.parent)
        # settings_action.setShortcut('Ctrl+,')
        # settings_action.setStatusTip('Open application settings')
        # settings_action.triggered.connect(self.tools_settings)
        # tools_menu.addAction(settings_action)
        # 
        # tools_menu.addSeparator()
        # 
        # data_import_action = QAction('Import Data', self.parent)
        # data_import_action.setStatusTip('Import patient data')
        # data_import_action.triggered.connect(self.tools_import_data)
        # tools_menu.addAction(data_import_action)
        # 
        # data_analysis_action = QAction('Data Analysis', self.parent)
        # data_analysis_action.setStatusTip('Open data analysis tools')
        # data_analysis_action.triggered.connect(self.tools_data_analysis)
        # tools_menu.addAction(data_analysis_action)
        # 
        # report_generator_action = QAction('Generate Report', self.parent)
        # report_generator_action.setStatusTip('Generate medical report')
        # report_generator_action.triggered.connect(self.tools_generate_report)
        # tools_menu.addAction(report_generator_action)
        # 
        # Help Menu
        help_menu = menubar.addMenu('Help')
        # 
        documentation_action = QAction('Documentation', self.parent)
        documentation_action.setShortcut('F1')
        documentation_action.setStatusTip('Open documentation')
        documentation_action.triggered.connect(self.help_documentation)
        help_menu.addAction(documentation_action)
        # 
        about_action = QAction('About', self.parent)
        about_action.setStatusTip('About Sleep Sense')
        about_action.triggered.connect(self.help_about)
        help_menu.addAction(about_action)
    
    # File Menu Actions
    def file_new(self):
        print("File -> New clicked")
        # TODO: Implement new session functionality
    
    def file_open(self):
        print("File -> Open clicked")
        # TODO: Implement file open functionality
    
    def file_save(self):
        print("File -> Save clicked")
        # TODO: Implement file save functionality
    
    # def file_export(self):
    #     print("File -> Export Data clicked")
    #     # TODO: Implement data export functionality
    
    # Edit Menu Actions
    # def edit_undo(self):
    #     print("Edit -> Undo clicked")
    #     # TODO: Implement undo functionality
    
    # def edit_redo(self):
    #     print("Edit -> Redo clicked")
    #     # TODO: Implement redo functionality
    
    # def edit_copy(self):
    #     print("Edit -> Copy clicked")
    #     # TODO: Implement copy functionality
    
    # def edit_paste(self):
    #     print("Edit -> Paste clicked")
    #     # TODO: Implement paste functionality
    
    # Tools Menu Actions
    # def tools_settings(self):
    #     print("Tools -> Settings clicked")
    #     # TODO: Implement settings dialog
    
    # def tools_import_data(self):
    #     print("Tools -> Import Data clicked")
    #     # TODO: Implement data import functionality
    
    # def tools_data_analysis(self):
    #     print("Tools -> Data Analysis clicked")
    #     # TODO: Implement data analysis tools
    
    # def tools_generate_report(self):
    #     print("Tools -> Generate Report clicked")
    #     # TODO: Implement report generation
    
    # def tools_analysis_parameters(self):
    #     """Analysis Parameters"""
    #     print("Tools -> Analysis Parameters clicked")
    #     # TODO: Implement analysis parameters functionality
    
    def tools_reanalyze(self):
        """Re-analyze - run detection again on the currently loaded CSV."""
        monitor_chart = getattr(self.parent, "monitor_chart", None)
        if monitor_chart is None or not getattr(monitor_chart, "loaded_csv_path", None):
            msg_box = QMessageBox(self.parent)
            msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            msg_box.setWindowTitle("No Data Loaded")
            msg_box.setText("Please upload PSG data before running Re-analyze.")
            msg_box.setIconPixmap(self._upload_psg_icon_pixmap())
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
            msg_box.setStandardButtons(QMessageBox.Ok)
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

        warning_box = QMessageBox(self.parent)
        warning_box.setWindowFlags(warning_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        warning_box.setIcon(QMessageBox.Warning)
        warning_box.setWindowTitle("Warning")
        warning_box.setText(
            "Analysis deletes former analysis events and will create new ones. "
            "These can be saved in the current report or in a new report."
        )
        warning_box.setStyleSheet("""
            QMessageBox {
                background-color: #f8fbff;
            }
            QMessageBox QLabel {
                color: #111827;
                font-size: 13px;
                font-weight: 500;
            }
        """)
        new_report_btn = warning_box.addButton("New report", QMessageBox.AcceptRole)
        current_report_btn = warning_box.addButton("Current report", QMessageBox.AcceptRole)
        cancel_btn = warning_box.addButton("Cancel", QMessageBox.RejectRole)
        warning_box.setDefaultButton(current_report_btn)

        primary_button_style = """
            QPushButton {
                min-width: 112px;
                min-height: 28px;
                padding: 6px 16px;
                border-radius: 6px;
                border: 1px solid #1d4ed8;
                background-color: #2563eb;
                color: white;
                font-size: 12px;
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
        """
        cancel_button_style = """
            QPushButton {
                min-width: 84px;
                min-height: 28px;
                padding: 6px 16px;
                border-radius: 6px;
                border: 1px solid #9ca3af;
                background-color: #f3f4f6;
                color: #374151;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #e5e7eb;
                border: 1px solid #6b7280;
            }
            QPushButton:pressed {
                background-color: #d1d5db;
                border: 1px solid #4b5563;
            }
        """

        if new_report_btn is not None:
            new_report_btn.setAutoDefault(False)
            new_report_btn.setMinimumWidth(112)
            new_report_btn.setMinimumHeight(28)
            new_report_btn.setStyleSheet(primary_button_style)
            new_report_btn.adjustSize()

        if current_report_btn is not None:
            current_report_btn.setAutoDefault(False)
            current_report_btn.setMinimumWidth(124)
            current_report_btn.setMinimumHeight(28)
            current_report_btn.setStyleSheet(primary_button_style)
            current_report_btn.adjustSize()

        if cancel_btn is not None:
            cancel_btn.setAutoDefault(False)
            cancel_btn.setMinimumWidth(84)
            cancel_btn.setMinimumHeight(28)
            cancel_btn.setStyleSheet(cancel_button_style)
            cancel_btn.adjustSize()

        warning_box.exec_()

        clicked = warning_box.clickedButton()
        if clicked is cancel_btn or clicked is None:
            print("Tools -> Re-analyze cancelled")
            return

        if clicked is new_report_btn:
            self._reanalyze_as_new_report(monitor_chart)
            return

        monitor_chart.run_rule_ai_apnea_detection()
        self._show_reanalyze_summary(monitor_chart, "current report")

    def _reanalyze_as_new_report(self, monitor_chart):
        """"New report": ask (only if manual events exist) whether to drop
        them, apply that choice, re-detect, then save.

        confirm_and_save_raw_data() archives whatever is currently in
        monitor_chart.manual_label_overrides alongside the saved copy (see
        _archive_manual_label_overrides_snapshot in sleep_monitor_chart.py).
        So: "keep them" here means they travel with the new saved session
        and show up again when it is reopened later; "delete them" clears
        them first, so the save is clean and the live view is clean too.
        """
        # has_any_manual_events() checks BOTH kinds of manual edits -
        # relabeled auto-events, removed auto events, and freely-drawn
        # selection boxes. Fall back to the old manual_label_overrides-only
        # check if it's missing.
        if hasattr(monitor_chart, "has_any_manual_events"):
            has_manual_edits = monitor_chart.has_any_manual_events()
        else:
            has_manual_edits = bool(getattr(monitor_chart, "manual_label_overrides", None))
        if has_manual_edits:
            delete_manual_events = self._ask_delete_manual_events_for_new_report()
            if delete_manual_events and hasattr(monitor_chart, "_clear_manual_events_in_memory"):
                # In-memory only - NOT clear_all_manual_label_overrides(),
                # which also saves the (now empty) state to disk. That
                # would wipe the ORIGINAL recording's own permanent
                # manual events, which must never happen: only the new
                # report being created here should end up without them.
                monitor_chart._clear_manual_events_in_memory()

        monitor_chart.run_rule_ai_apnea_detection()

        if hasattr(monitor_chart, "confirm_and_save_raw_data"):
            # Saving is async (QThread). Once it finishes,
            # _on_save_done() in sleep_monitor_chart.py archives whatever
            # manual-event state exists at that moment onto the new saved
            # copy, THEN clears the live view back to auto-events-only -
            # so the screen you're looking at right now will update to a
            # clean view a moment after this call returns, without ever
            # touching the original recording's own sidecar on disk.
            monitor_chart.confirm_and_save_raw_data()

        self._show_reanalyze_summary(monitor_chart, "new report")

    def _ask_delete_manual_events_for_new_report(self):
        """Yes/No: should the new report drop this recording's manual events?

        Returns True for "delete them", False for "keep them". Defaults to
        keeping them (the non-destructive choice) if the dialog is dismissed
        without a clear answer.
        """
        confirm_box = QMessageBox(self.parent)
        confirm_box.setWindowFlags(confirm_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        confirm_box.setIcon(QMessageBox.Question)
        confirm_box.setWindowTitle("Manual Events")
        confirm_box.setText(
            "This recording has manual changes: events you relabelled, "
            "events you added, and auto-detected events you removed.\n\n"
            "Delete these manual changes for this new report?\n\n"
            "Yes, delete - save fresh auto-detected events only. The events "
            "you removed will come back, relabelled events return to their "
            "original label, and the events you added will not be saved.\n\n"
            "No, keep them - the new report matches exactly what you see "
            "now: removed events stay removed, your labels stay, and the "
            "events you added are saved too."
        )
        yes_btn = confirm_box.addButton("Yes, delete", QMessageBox.YesRole)
        no_btn = confirm_box.addButton("No, keep them", QMessageBox.NoRole)
        confirm_box.setDefaultButton(no_btn)
        confirm_box.exec_()
        return confirm_box.clickedButton() is yes_btn

    def _show_reanalyze_summary(self, monitor_chart, report_choice):
        event_count = 0
        auto_result = getattr(monitor_chart, "auto_rule_ai_result", None)
        if isinstance(auto_result, dict):
            event_count = len(auto_result.get("events", []))
        print(f"Tools -> Re-analyze complete ({report_choice}), {event_count} events detected")

        QMessageBox.information(
            self.parent,
            "Re-analyze Complete",
            f"Re-analysis finished.\n\n{event_count} event(s) detected.\n"
            f"Saved in: {report_choice}.",
        )

    def tools_settings_analysis_parameters(self):
        """Open the Analysis parameters dialog and apply changes to the detector."""
        monitor_chart = getattr(self.parent, "monitor_chart", None)
        if monitor_chart is None or not getattr(monitor_chart, "loaded_csv_path", None):
            msg_box = QMessageBox(self.parent)
            msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            msg_box.setWindowTitle("No Data Loaded")
            msg_box.setText("Please upload PSG data before changing analysis parameters.")
            msg_box.setIconPixmap(self._upload_psg_icon_pixmap())
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
            msg_box.setStandardButtons(QMessageBox.Ok)
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

        dialog = AnalysisParametersDialog(self.parent)
        if dialog.exec_() != QDialog.Accepted:
            print("Tools -> Analysis parameters cancelled")
            return

        parameters = dialog.get_parameters()
        if parameters is None:
            msg_box = QMessageBox(self.parent)
            msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("Invalid Values")
            msg_box.setText("Please enter valid numbers for all fields.")
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
            msg_box.setStandardButtons(QMessageBox.Ok)
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

        if apnea_detector is None:
            QMessageBox.warning(
                self.parent,
                "Detector Not Available",
                f"Could not load the detection module, so parameters were not applied.\n\n{ANALYSIS_PARAMS_IMPORT_ERROR}",
            )
            return

        apnea_detector.apply_analysis_parameters(parameters)
        print(f"Tools -> Analysis parameters applied: {parameters}")

        # Hypopnea / Snoring / Desaturation / CSR tab values.
        # Kept separate so the apnea detector only receives the constants it
        # knows; they are applied only if the detector exposes a setter, and
        # are always cached on the window for the rest of the app to read.
        extra_parameters = dialog.get_extra_parameters()
        if extra_parameters is not None:
            self.parent.analysis_extra_parameters = extra_parameters
            if monitor_chart is not None:
                monitor_chart.analysis_extra_parameters = extra_parameters
            if hasattr(apnea_detector, "apply_extra_analysis_parameters"):
                try:
                    apnea_detector.apply_extra_analysis_parameters(extra_parameters)
                except Exception as extra_error:
                    print(f"Extra analysis parameters not applied: {extra_error}")
            print(f"Tools -> Extra analysis parameters: {extra_parameters}")
        msg_box = QMessageBox(self.parent)
        msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        msg_box.setWindowTitle("Analysis Parameters")
        msg_box.setText("New parameters applied. Run Re-analyze to use them on the current data.")
        msg_box.setIconPixmap(self._analysis_parameters_applied_icon_pixmap())
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
        msg_box.setStandardButtons(QMessageBox.Ok)
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

    def _upload_psg_icon_pixmap(self):
        """Create a blue upload/PSG-style icon for warning dialogs."""
        pixmap = QPixmap(36, 36)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#3b82f6"))
        painter.drawRoundedRect(4, 4, 28, 28, 8, 8)

        pen = QPen(QColor("white"))
        pen.setWidth(2)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)

        painter.drawLine(18, 24, 18, 12)
        painter.drawLine(18, 12, 14, 16)
        painter.drawLine(18, 12, 22, 16)
        painter.drawLine(11, 26, 25, 26)
        painter.end()
        return pixmap

    def _analysis_parameters_applied_icon_pixmap(self):
        """Create a blue info icon for the analysis-parameters confirmation dialog."""
        pixmap = QPixmap(36, 36)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#2563eb"))
        painter.drawEllipse(4, 4, 28, 28)

        pen = QPen(QColor("white"))
        pen.setWidth(3)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)

        painter.drawLine(18, 14, 18, 15)
        painter.drawLine(18, 19, 18, 24)
        painter.drawLine(18, 11, 18, 11)
        painter.end()
        return pixmap
    
    # def tools_new_event_group(self):
    #     """New event group"""
    #     print("Tools -> New event group clicked")
    #     # TODO: Implement new event group functionality
    
    # def tools_delete_event_group(self):
    #     """Delete event group"""
    #     print("Tools -> Delete event group clicked")
    #     # TODO: Implement delete event group functionality
    
    # def tools_edit_event_group(self):
    #     """Edit event group"""
    #     print("Tools -> Edit event group clicked")
    #     # TODO: Implement edit event group functionality
    
        
    # def tools_settings_report(self):
    #     """Report"""
    #     print("Tools -> Settings -> Report clicked")
    #     dialog = ReportSettingsDialog(self.parent)
    #     if dialog.exec_() == QDialog.Accepted:
    #         print("Report settings applied")
    #         # TODO: Apply report settings
    
    # def tools_settings_analysis_parameters(self):
    #     """Analysis parameters"""
    #     print("Tools -> Settings -> Analysis parameters clicked")
    #     dialog = AnalysisParametersDialog(self.parent)
    #     dialog.exec_()
    
    # def tools_settings_edf_export(self):
    #     """EDF export"""
    #     print("Tools -> Settings -> EDF export clicked")
    #     dialog = EDFExportDialog(self.parent)
    #     if dialog.exec_() == QDialog.Accepted:
    #         print("EDF export settings applied")
    #         # TODO: Apply EDF export settings
    
    # def tools_settings_general(self):
    #     """General settings"""
    #     print("Tools -> Settings -> General clicked")
    #     # TODO: Implement general settings dialog
    
    # def tools_settings_data(self):
    #     """Data settings"""
    #     print("Tools -> Settings -> Data clicked")
    #     # TODO: Implement data settings dialog
    
    # def tools_settings_display(self):
    #     """Display settings"""
    #     print("Tools -> Settings -> Display clicked")
    #     # TODO: Implement display settings dialog
    
    # def tools_settings_export(self):
    #     """Export settings"""
    #     print("Tools -> Settings -> Export clicked")
    #     # TODO: Implement export settings dialog
    
    # def tools_reanalysis(self):
    #     """Reanalysis"""
    #     print("Tools -> Reanalysis clicked")
    #     # TODO: Implement reanalysis functionality
    
    # Help Menu Actions
    def help_clinical_guide(self):
        print("Help -> Clinical Guide clicked")
        QMessageBox.information(self.parent, "Clinical Guide", "Clinical guide will be added here.")
    
    def help_patient_instructions(self):
        print("Help -> Patient instructions clicked")
        QMessageBox.information(self.parent, "Patient Instructions", "Patient instructions will be added here.")
    
    def help_program_info(self):
        print("Help -> Program info clicked")
        QMessageBox.information(self.parent, "Program Info", "Program information will be added here.")
    
    def help_recording_info(self):
        print("Help -> Recording info clicked")
        QMessageBox.information(self.parent, "Recording Info", "Recording information will be added here.")
    
    def help_device_info(self):
        print("Help -> Device info clicked")
        QMessageBox.information(self.parent, "Device Info", "Device information will be added here.")
    
    def help_documentation(self):
        print("Help -> Documentation clicked")
        QMessageBox.information(self.parent, "Documentation", "Documentation will be added here.")
    
    def help_about(self):
        print("Help -> About clicked")
        QMessageBox.information(self.parent, "About", "Sleep Sense application information will be added here.")
    
    def file_load_data(self):
        """Load PSG data from CSV file using file dialog"""
        if not getattr(self.parent, "current_patient_db_id", None):
            QMessageBox.warning(
                self.parent,
                "No Patient Selected",
                "Please select a patient from the database before uploading data.",
            )
            return

        if hasattr(self.parent, 'load_psg_data_from_file'):
            self.parent.load_psg_data_from_file()
        else:
            QMessageBox.warning(self.parent, "Load Data", "Load data function not available")

    # def file_database(self):
    #     """Open patient database window - same as red database button"""
    #     # Check if parent has monitor_chart with selection active and block if needed
    #     if (hasattr(self.parent, 'monitor_chart') and 
    #         hasattr(self.parent.monitor_chart, 'block_if_selection_active') and 
    #         self.parent.monitor_chart.block_if_selection_active()):
    #         return
    #     
    #     # Call the same open_database method as the red toolbar button
    #     if hasattr(self.parent, 'open_database'):
    #         self.parent.open_database()
    #     else:
    #         print("Parent does not have open_database method")
    
    # def file_open_archive(self):
    #     """Open archive window - same as blue archive button"""
    #     # Check if parent has monitor_chart with selection active and block if needed
    #     if (hasattr(self.parent, 'monitor_chart') and 
    #         hasattr(self.parent.monitor_chart, 'block_if_selection_active') and 
    #         self.parent.monitor_chart.block_if_selection_active()):
    #         return
    #
    #     # Call the same open_archive method as the blue toolbar button
    #     if hasattr(self.parent, 'open_archive'):
    #         self.parent.open_archive()
    #     else:
    #         print("Parent does not have open_archive method")
    
    def file_archive(self):
        """Archive a selected file into an Archive folder with timestamp"""
        path, _ = QFileDialog.getOpenFileName(self.parent, "Select file to archive", os.path.expanduser("~"))
        if not path:
            return
        archive_dir = os.path.join(os.path.dirname(path), "Archive")
        os.makedirs(archive_dir, exist_ok=True)
        base = os.path.basename(path)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = os.path.join(archive_dir, f"{timestamp}-{base}")
        try:
            shutil.move(path, dest)
            QMessageBox.information(self.parent, "Archive", f"Archived to:\n{dest}")
        except Exception as e:
            QMessageBox.critical(self.parent, "Archive Error", str(e))
    
    # def file_save_report_locally(self):
    #     """Save current report HTML/text to a file chosen by the user"""
    #     suggested_name = "sleep_report.html"
    #     filename, _ = QFileDialog.getSaveFileName(self.parent, "Save report locally", suggested_name, "HTML files (*.html);;Text files (*.txt);;All files (*)")
    #     if not filename:
    #         return
    #     # Try to get report from parent; fallback to placeholder text
    #     report_html = None
    #     if hasattr(self.parent, "get_report_html"):
    #         try:
    #             report_html = self.parent.get_report_html()
    #         except Exception:
    #             report_html = None
    #     if report_html:
    #         mode = "w"
    #         try:
    #             with open(filename, mode, encoding="utf-8") as f:
    #                 f.write(report_html)
    #             QMessageBox.information(self.parent, "Save Report", f"Report saved to:\n{filename}")
    #         except Exception as e:
    #             QMessageBox.critical(self.parent, "Save Error", str(e))
    #     else:
    #         text, ok = QInputDialog.getMultiLineText(self.parent, "Save Report", "No report available from application. Enter text to save:")
    #         if ok and text:
    #             try:
    #                 with open(filename, "w", encoding="utf-8") as f:
    #                     f.write(text)
    #                 QMessageBox.information(self.parent, "Save Report", f"Report saved to:\n{filename}")
    #             except Exception as e:
    #                 QMessageBox.critical(self.parent, "Save Error", str(e))
    
    # def file_print_report(self):
    #     """Print current report (HTML or plain text)"""
    #     # Get report content
    #     report_html = None
    #     report_text = None
    #     if hasattr(self.parent, "get_report_html"):
    #         try:
    #             report_html = self.parent.get_report_html()
    #         except Exception:
    #             report_html = None
    #     if not report_html and hasattr(self.parent, "get_report_text"):
    #         try:
    #             report_text = self.parent.get_report_text()
    #         except Exception:
    #             report_text = None
    #     if not report_html and not report_text:
    #         QMessageBox.information(self.parent, "Print Report", "No report available to print.")
    #         return
    #     doc = QTextDocument()
    #     if report_html:
    #         doc.setHtml(report_html)
    #     else:
    #         doc.setPlainText(report_text)
    #     printer = QPrinter()
    #     dlg = QPrintDialog(printer, self.parent)
    #     if dlg.exec_() == QPrintDialog.Accepted:
    #         doc.print_(printer)
    #         QMessageBox.information(self.parent, "Print", "Print job sent.")
    
    def file_print_patient_instructions(self, mode='short'):
        """Print built-in patient instruction templates"""
        if mode == 'short':
            text = "Patient Instructions (Short)\n\n- Follow the pre-sleep routine.\n- Avoid caffeine 6 hours before bedtime.\n- Contact support if symptoms persist."
        else:
            text = ("Patient Instructions (Full)\n\n"
                    "- Follow the pre-sleep routine strictly.\n- Avoid caffeine, nicotine, and alcohol before bedtime.\n- Ensure a dark, cool and quiet bedroom.\n- Follow any device-specific instructions provided by your clinician.")
        doc = QTextDocument()
        doc.setPlainText(text)
        printer = QPrinter()
        dlg = QPrintDialog(printer, self.parent)
        if dlg.exec_() == QPrintDialog.Accepted:
            doc.print_(printer)
            QMessageBox.information(self.parent, "Print", "Instructions sent to printer.")
    
    def file_duplicate(self):
        """Duplicate a chosen file next to the original with a timestamp suffix"""
        path, _ = QFileDialog.getOpenFileName(self.parent, "Select file to duplicate", os.path.expanduser("~"))
        if not path:
            return
        base = os.path.basename(path)
        dest = os.path.join(os.path.dirname(path), f"{os.path.splitext(base)[0]}-copy{os.path.splitext(base)[1]}")
        # ensure unique
        if os.path.exists(dest):
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            dest = os.path.join(os.path.dirname(path), f"{os.path.splitext(base)[0]}-copy-{timestamp}{os.path.splitext(base)[1]}")
        try:
            shutil.copy2(path, dest)
            QMessageBox.information(self.parent, "Duplicate", f"Created duplicate:\n{dest}")
        except Exception as e:
            QMessageBox.critical(self.parent, "Duplicate Error", str(e))

    
    # def file_export(self, fmt='csv'):
    #     """Export current dataset as CSV or JSON if parent exposes get_current_data()"""
    #     if not hasattr(self.parent, "get_current_data"):
    #         QMessageBox.information(self.parent, "Export", "Export not available: application does not expose data.")
    #         return
    #     data = None
    #     try:
    #         data = self.parent.get_current_data()
    #     except Exception as e:
    #         QMessageBox.critical(self.parent, "Export Error", str(e))
    #         return
    #     if not data:
    #         QMessageBox.information(self.parent, "Export", "No data available to export.")
    #         return
    #     if fmt == 'csv':
    #         filename, _ = QFileDialog.getSaveFileName(self.parent, "Export as CSV", "export.csv", "CSV files (*.csv)")
    #         if not filename:
    #             return
    #         try:
    #             # assume data is list of dicts
    #             with open(filename, "w", newline='', encoding="utf-8") as f:
    #                 writer = csv.DictWriter(f, fieldnames=list(data[0].keys()))
    #                 writer.writeheader()
    #                 writer.writerows(data)
    #             QMessageBox.information(self.parent, "Export", f"Exported CSV to:\n{filename}")
    #         except Exception as e:
    #             QMessageBox.critical(self.parent, "Export Error", str(e))
    #     else:
    #         filename, _ = QFileDialog.getSaveFileName(self.parent, "Export as JSON", "export.json", "JSON files (*.json)")
    #         if not filename:
    #             return
    #         try:
    #             with open(filename, "w", encoding="utf-8") as f:
    #                 json.dump(data, f, indent=2)
    #             QMessageBox.information(self.parent, "Export", f"Exported JSON to:\n{filename}")
    #         except Exception as e:
    #             QMessageBox.critical(self.parent, "Export Error", str(e))
    
    # def file_import_recording(self):
    #     """Import a recording file into application's recordings folder (creates folder if needed)"""
    #     path, _ = QFileDialog.getOpenFileName(self.parent, "Import recording", os.path.expanduser("~"))
    #     if not path:
    #         return
    #     recordings_dir = getattr(self.parent, "recordings_dir", os.path.join(os.path.expanduser("~"), "sleep_recordings"))
    #     os.makedirs(recordings_dir, exist_ok=True)
    #     try:
    #         dest = os.path.join(recordings_dir, os.path.basename(path))
    #         shutil.copy2(path, dest)
    #         QMessageBox.information(self.parent, "Import Recording", f"Imported to:\n{dest}")
    #     except Exception as e:
    #         QMessageBox.critical(self.parent, "Import Error", str(e))
    
    def _generate_pdf_from_html(self, html_content, output_path):
        """Generate PDF from HTML content using QWebEngineView"""
        try:
            from PyQt5.QtWebEngineWidgets import QWebEngineView

            # Create a temporary web view to render HTML
            web_view = QWebEngineView()
            web_view.setHtml(html_content)
            
            # Wait for page to load (simple approach)
            # In production, you'd use QWebEnginePage.loadFinished signal
            import time
            time.sleep(2)  # Give time for rendering

            # Create printer
            printer = QPrinter(QPrinter.HighResolution)
            printer.setOutputFormat(QPrinter.PdfFormat)
            printer.setOutputFileName(output_path)
            printer.setPageSize(QPrinter.A4)
            
            # Print to PDF
            web_view.page().print(printer, lambda success: None)
            
            return True
        except Exception as e:
            print(f"Error generating PDF: {e}")
            return False
    
    def _open_gmail_compose(self, subject, body, attachment_path=None):
        """Open Gmail compose in browser with subject and body pre-filled"""
        try:
            # Gmail compose URL with subject and body
            gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&su={quote(subject)}&body={quote(body)}"
            
            # Open Gmail in browser
            webbrowser.open(gmail_url)
            
            if attachment_path:
                # Show message about attaching the file
                QMessageBox.information(
                    self.parent, 
                    "Gmail Opened",
                    f"Gmail has been opened in your browser.\n\n"
                    f"Please attach the file:\n{attachment_path}\n\n"
                    f"If you're not logged in, you'll be redirected to the login page first."
                )
                
                # Also open file location to help user find the file
                try:
                    if platform.system() == "Darwin":  # macOS
                        subprocess.run(["open", "-R", attachment_path])
                    elif platform.system() == "Windows":
                        subprocess.run(["explorer", "/select,", attachment_path])
                    else:  # Linux
                        subprocess.run(["xdg-open", os.path.dirname(attachment_path)])
                except:
                    pass
            else:
                QMessageBox.information(
                    self.parent,
                    "Gmail Opened",
                    "Gmail has been opened in your browser.\n\nIf you're not logged in, you'll be redirected to the login page first."
                )
                
        except Exception as e:
            QMessageBox.warning(self.parent, "Email", f"Could not open Gmail:\n{e}")
    
    def file_send_report_email(self):
        """Generate PDF report and open Gmail compose for sending"""
        # Generate PDF from report
        pdf_path = None
        if hasattr(self.parent, "get_report_html"):
            try:
                html = self.parent.get_report_html()
                pdf_path = os.path.join(tempfile.gettempdir(), f"sleep_report_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf")
                
                # Try to generate PDF
                if self._generate_pdf_from_html(html, pdf_path):
                    QMessageBox.information(self.parent, "PDF Generated", f"Report saved as PDF:\n{pdf_path}")
                else:
                    # Fallback: save as HTML
                    html_path = os.path.join(tempfile.gettempdir(), f"sleep_report_{datetime.now().strftime('%Y%m%d%H%M%S')}.html")
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(html)
                    pdf_path = html_path
                    QMessageBox.information(self.parent, "HTML Saved", f"Report saved as HTML:\n{html_path}")
                    
            except Exception as e:
                QMessageBox.warning(self.parent, "Error", f"Could not generate report:\n{e}")
                return
        
        subject = "Sleep Sense Report"
        body = "Please find the sleep report attached."
        self._open_gmail_compose(subject, body, pdf_path)
    
    # def file_send_recording_email(self):
    #     """Prompt user to select a recording and open Gmail compose for sending"""
    #     path, _ = QFileDialog.getOpenFileName(self.parent, "Select recording to send", os.path.expanduser("~"))
    #     if not path:
    #         return
    #     
    #     subject = "Recording from Sleep Sense"
    #     body = "Please find the recording attached."
    #     self._open_gmail_compose(subject, body, path)

    def get_settings(self):
        """Get current settings"""
        return {
            'resolution': self.resolution_combo.currentText(),
            'signal_cursor': self.signal_cursor_checkbox.isChecked(),
            'hide_channels': self.hide_channels_checkbox.isChecked()
        }


class ReportSettingsDialog(QDialog):
    """Dialog for customizing report settings"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setWindowTitle("Report")
        self.setFixedSize(500, 600)
        self.init_ui()
    
    def init_ui(self):
        """Initialize the dialog UI"""
        layout = QVBoxLayout()
        
        # Measurement system group
        measurement_group = QGroupBox("Measurement system")
        measurement_layout = QVBoxLayout()
        
        self.metric_radio = QRadioButton("Metric")
        self.imperial_radio = QRadioButton("Imperial")
        self.metric_radio.setChecked(True)
        
        measurement_layout.addWidget(self.metric_radio)
        measurement_layout.addWidget(self.imperial_radio)
        measurement_group.setLayout(measurement_layout)
        
        # Logo settings
        logo_group = QGroupBox("Show logo on report")
        logo_layout = QHBoxLayout()
        
        self.show_logo_checkbox = QCheckBox()
        logo_file_button = QPushButton("Select file")
        
        
        logo_layout.addWidget(self.show_logo_checkbox)
        logo_layout.addWidget(logo_file_button)
        logo_group.setLayout(logo_layout)
        
        # Print settings
        print_group = QGroupBox("Print several reports")
        print_layout = QHBoxLayout()
        
        self.print_checkbox = QCheckBox()
        self.print_spinbox = QSpinBox()
        self.print_spinbox.setRange(1, 100)
        self.print_spinbox.setValue(1)
        
        print_layout.addWidget(self.print_checkbox)
        print_layout.addWidget(self.print_spinbox)
        print_group.setLayout(print_layout)
        
        # Extended report
        self.extended_report_checkbox = QCheckBox("Extended report")
        
        # Desaturation settings
        desat_group = QGroupBox("Display value for")
        desat_layout = QVBoxLayout()
        
        self.desat_88_checkbox = QCheckBox("'Desaturation below 88%'")
        self.desat_89_checkbox = QCheckBox("'Desaturation below 89%'")
        
        desat_layout.addWidget(self.desat_88_checkbox)
        desat_layout.addWidget(self.desat_89_checkbox)
        desat_group.setLayout(desat_layout)
        
        # Template settings
        self.prescription_checkbox = QCheckBox("Add prescription template")
        
        referral_group = QGroupBox("Add referral template")
        referral_layout = QVBoxLayout()
        
        self.referral_checkbox = QCheckBox()
        referral_radio_layout = QHBoxLayout()
        
        self.referral_always_radio = QRadioButton("always")
        self.referral_ahi_radio = QRadioButton("AHI >= 5")
        self.referral_always_radio.setChecked(True)
        
        referral_radio_layout.addWidget(self.referral_always_radio)
        referral_radio_layout.addWidget(self.referral_ahi_radio)
        
        referral_layout.addWidget(self.referral_checkbox)
        referral_layout.addLayout(referral_radio_layout)
        referral_group.setLayout(referral_layout)
        
        # Quick buttons
        self.quick_buttons_checkbox = QCheckBox("Show quick buttons in report view")
        
        # Physician info
        physician_group = QGroupBox("Name of physician (to be referred to ...)")
        physician_layout = QVBoxLayout()
        
        physician_input_layout = QHBoxLayout()
        self.physician_text = QLineEdit()
        select_doctor_button = QPushButton("Select doctor")
        
        physician_input_layout.addWidget(self.physician_text)
        physician_input_layout.addWidget(select_doctor_button)
        
        physician_layout.addLayout(physician_input_layout)
        physician_group.setLayout(physician_layout)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        advanced_button = QPushButton("Advanced settings")
        
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        advanced_button.clicked.connect(self.show_advanced_settings)
        
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(advanced_button)
        
        # Add all to main layout
        layout.addWidget(measurement_group)
        layout.addWidget(logo_group)
        layout.addWidget(print_group)
        layout.addWidget(self.extended_report_checkbox)
        layout.addWidget(desat_group)
        layout.addWidget(self.prescription_checkbox)
        layout.addWidget(referral_group)
        layout.addWidget(self.quick_buttons_checkbox)
        layout.addWidget(physician_group)
        layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def show_advanced_settings(self):
        """Show advanced settings dialog"""
        QMessageBox.information(self, "Advanced Settings", "Advanced settings dialog would open here")
    
    def get_settings(self):
        """Get current report settings"""
        return {
            'measurement_system': 'metric' if self.metric_radio.isChecked() else 'imperial',
            'show_logo': self.show_logo_checkbox.isChecked(),
            'print_reports': self.print_checkbox.isChecked(),
            'print_count': self.print_spinbox.value(),
            'extended_report': self.extended_report_checkbox.isChecked(),
            'desat_88': self.desat_88_checkbox.isChecked(),
            'desat_89': self.desat_89_checkbox.isChecked(),
            'prescription': self.prescription_checkbox.isChecked(),
            'referral': self.referral_checkbox.isChecked(),
            'referral_condition': 'always' if self.referral_always_radio.isChecked() else 'ahi_5',
            'quick_buttons': self.quick_buttons_checkbox.isChecked(),
            'physician_name': self.physician_text.text()
        }


class EDFExportDialog(QDialog):
    """Dialog for EDF export settings"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setWindowTitle("EDF export")
        self.setFixedSize(600, 700)
        self.init_ui()
    
    def init_ui(self):
        """Initialize dialog UI"""
        main_layout = QVBoxLayout()
        
        # --- Choose channels for export ---
        channels_group = QGroupBox("Choose channels for export")
        channels_layout = QVBoxLayout()
        channels_grid_layout = QGridLayout()
        
        self.channel_checkboxes = {}
        channels = ["Battery", "Flow", "Snoring", "Effort", "Pulse", "Saturation"]
        for i, channel in enumerate(channels):
            checkbox = QCheckBox(channel)
            checkbox.setChecked(True)
            self.channel_checkboxes[channel] = checkbox
            channels_grid_layout.addWidget(checkbox, i // 3, i % 3)
        
        channels_buttons_layout = QHBoxLayout()
        channels_buttons_layout.addStretch()
        choose_all_channels_button = QPushButton("choose all")
        choose_all_channels_button.clicked.connect(lambda: self._set_all_checkboxes(self.channel_checkboxes, True))
        channels_buttons_layout.addWidget(choose_all_channels_button)
        
        channels_layout.addLayout(channels_grid_layout)
        channels_layout.addLayout(channels_buttons_layout)
        channels_group.setLayout(channels_layout)
        main_layout.addWidget(channels_group)
        
        # --- Choose events for export ---
        events_group = QGroupBox("Choose events for export")
        events_layout = QVBoxLayout()
        events_grid_layout = QGridLayout()
        
        self.event_checkboxes = {}
        events = [
            "Recording interruption", "Flowlimitation & Snoring", "Desaturation",
            "Start of evaluation", "Cheyne Stokes Respiration", "Analysis exclusion saturation",
            "End of evaluation", "Missing finger sensor", "Start of evaluation saturation",
            "Signal too small", "Missing XPod", "Start of evaluation pulse",
            "Unclassified apnea", "Invalid data XPod", "Mixed apnea",
            "Hypopnea", "Invalid data battery", "Central apnea",
            "Flow limitation", "Invalid data flow", "Obstructive apnea",
            "Snoring", "Invalid data pulse", "Signal too small (effort)",
            "Inspiratory flow", "Invalid data saturation", "Invalid Data Effort",
            "Analysis exclusion flow", "Baseline Saturation", "Analysis exclusion saturation",
            "Start of evaluation saturation", "Start of evaluation pulse", ""
        ]
        
        for i, event in enumerate(events):
            if event:  # Skip empty string
                checkbox = QCheckBox(event)
                checkbox.setChecked(True)
                self.event_checkboxes[event] = checkbox
                events_grid_layout.addWidget(checkbox, i // 3, i % 3)
        
        events_buttons_layout = QHBoxLayout()
        events_buttons_layout.addStretch()
        choose_all_events_button = QPushButton("choose all")
        choose_all_events_button.clicked.connect(lambda: self._set_all_checkboxes(self.event_checkboxes, True))
        events_buttons_layout.addWidget(choose_all_events_button)
        
        events_layout.addLayout(events_grid_layout)
        events_layout.addLayout(events_buttons_layout)
        events_group.setLayout(events_layout)
        main_layout.addWidget(events_group)
        
        # --- Bottom buttons ---
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        standard_parameter_button = QPushButton("Standard parameter")
        
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        standard_parameter_button.clicked.connect(self.load_standard_parameters)
        
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(standard_parameter_button)
        
        main_layout.addStretch()
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
    
    def _set_all_checkboxes(self, checkbox_dict, checked):
        """Set all checkboxes to checked/unchecked"""
        for checkbox in checkbox_dict.values():
            checkbox.setChecked(checked)
    
    def load_standard_parameters(self):
        """Load standard parameter"""
        self._set_all_checkboxes(self.channel_checkboxes, True)
        self._set_all_checkboxes(self.event_checkboxes, True)
        QMessageBox.information(self, "Standard parameter", "Standard parameter loaded")
    
    def get_export_settings(self):
        """Get current export settings"""
        selected_channels = [ch for ch, cb in self.channel_checkboxes.items() if cb.isChecked()]
        selected_events = [ev for ev, cb in self.event_checkboxes.items() if cb.isChecked()]
        return {
            'channels': selected_channels,
            'events': selected_events
        }




class AnalysisParametersDialog(QDialog):
    """Dialog for analysis parameters settings"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setWindowTitle("Analysis parameters")
        self.setMinimumWidth(760)
        self.setMinimumHeight(520)
        self.init_ui()

    def init_ui(self):
        """Initialize the dialog UI"""
        self.setStyleSheet("""
            QDialog {
                background-color: #f7f9fc;
            }
            QLabel#subtitleLabel {
                color: #6b7280;
                font-size: 12px;
            }
            QLabel#sectionTitle {
                color: #2563eb;
                font-size: 13px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }
            QLabel#rowLabel {
                color: #111827;
                font-size: 13px;
                font-weight: 500;
            }
            QLabel#toLabel, QLabel#unitLabel {
                color: #6b7280;
                font-size: 12px;
            }
            QFrame#sectionFrame {
                background-color: #ffffff;
                border: 1px solid #e2e5ea;
                border-radius: 8px;
            }
            QLabel[severity="hypopnea"] {
                background-color: #d97706;
                border-radius: 5px;
            }
            QLabel[severity="apnea"] {
                background-color: #dc2626;
                border-radius: 5px;
            }
            QLineEdit {
                border: 1.5px solid #d1d5db;
                border-radius: 6px;
                padding: 4px 6px;
                background-color: #fbfcfe;
                color: #111827;
            }
            QLineEdit:focus {
                border: 1.5px solid #2563eb;
                background-color: #ffffff;
            }
            QPushButton#okButton {
                background-color: #2563eb;
                color: white;
                border: 1px solid #1e40af;
                border-radius: 6px;
                padding: 7px 22px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton#okButton:hover {
                background-color: #3b82f6;
            }
            QPushButton#cancelButton {
                background-color: #f3f4f6;
                color: #374151;
                border: 1px solid #9ca3af;
                border-radius: 6px;
                padding: 7px 16px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton#cancelButton:hover {
                background-color: #e5e7eb;
            }
            QPushButton#standardButton {
                background-color: #ffffff;
                color: #2563eb;
                border: 1.5px solid #bfdbfe;
                border-radius: 6px;
                padding: 7px 16px;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton#standardButton:hover {
                background-color: #eff6ff;
            }
            QTabWidget::pane {
                border: 1px solid #e2e5ea;
                border-radius: 8px;
                background-color: #ffffff;
                top: -1px;
            }
            QTabBar::tab {
                background-color: #eef2f7;
                color: #374151;
                border: 1px solid #e2e5ea;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 8px 20px;
                margin-right: 2px;
                font-size: 12px;
                font-weight: 600;
                min-width: 92px;
            }
            QTabBar::tab:selected {
                background-color: #2563eb;
                color: #ffffff;
                border: 1px solid #1e40af;
                border-bottom: none;
            }
            QTabBar::tab:hover:!selected {
                background-color: #dbe4f0;
            }
            QGroupBox {
                border: 1px solid #e2e5ea;
                border-radius: 8px;
                margin-top: 12px;
                padding: 12px 10px 10px 10px;
                background-color: #ffffff;
                font-size: 12px;
                font-weight: 600;
                color: #2563eb;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0px 6px;
            }
            QCheckBox {
                color: #111827;
                font-size: 13px;
                font-weight: 500;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
                border: 1.5px solid #9ca3af;
                border-radius: 3px;
                background-color: #ffffff;
            }
            QCheckBox::indicator:checked {
                background-color: #2563eb;
                border: 1.5px solid #1e40af;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(22, 20, 22, 16)
        main_layout.setSpacing(10)

        # ------------------------------------------------------------------
        # 4 tabs: Apnea | Hypopnea | Snoring | Desaturation
        # CSR tab is hidden for now.
        # ------------------------------------------------------------------
        self.tabs = QTabWidget()

        self.apnea_tab = QWidget()
        self.hypopnea_tab = QWidget()
        self.snoring_tab = QWidget()
        self.desaturation_tab = QWidget()

        self.tabs.addTab(self.apnea_tab, "Apnea")
        self.tabs.addTab(self.hypopnea_tab, "Hypopnea")
        self.tabs.addTab(self.snoring_tab, "Snoring")
        self.tabs.addTab(self.desaturation_tab, "Desaturation")

        apnea_layout = QVBoxLayout(self.apnea_tab)
        apnea_layout.setContentsMargins(16, 14, 16, 12)
        apnea_layout.setSpacing(8)
        self.setup_apnea_tab(apnea_layout)

        self.setup_hypopnea_tab()
        self.setup_snoring_tab()
        self.setup_desaturation_tab()

        main_layout.addWidget(self.tabs)

        # Buttons
        button_layout = QHBoxLayout()

        standard_button = QPushButton("standard parameters")
        standard_button.setObjectName("standardButton")
        standard_button.clicked.connect(self.standard_parameter)
        button_layout.addWidget(standard_button)

        button_layout.addStretch()

        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("cancelButton")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        ok_button = QPushButton("OK")
        ok_button.setObjectName("okButton")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)

        main_layout.addLayout(button_layout)

    def setup_apnea_tab(self, layout):
        current = {}
        if apnea_detector is not None:
            try:
                current = apnea_detector.get_analysis_parameters()
            except Exception:
                current = {}

        if apnea_detector is None:
            warning_label = QLabel(
                f"Detector module not available — showing default values only.\n({ANALYSIS_PARAMS_IMPORT_ERROR})"
            )
            warning_label.setStyleSheet("color: #b91c1c; font-size: 12px;")
            warning_label.setWordWrap(True)
            layout.addWidget(warning_label)

        subtitle = QLabel(
            "AASM-based thresholds used by the apnea detector. "
            "Changes apply the next time you run Re-analyze."
        )
        subtitle.setObjectName("subtitleLabel")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        hypopnea_percent = current.get("AASM_HYPOPNEA_DROP_PERCENT", 30.0)
        apnea_percent = current.get("AASM_APNEA_DROP_PERCENT", 75.0)
        obstructive_effort_percent = float(current.get("OBSTRUCTIVE_APNEA_EFFORT_THRESHOLD", 0.20)) * 100.0
        central_effort_percent = float(current.get("CENTRAL_APNEA_EFFORT_THRESHOLD", 0.60)) * 100.0
        central_amplitude_percent = float(current.get("CENTRAL_APNEA_AMPLITUDE_CONFIRM_RATIO", 0.08)) * 100.0
        min_sec = current.get("MIN_EVENT_SEC", 10.0)
        max_sec = current.get("MAX_EVENT_SEC", 120.0)

        def _severity_dot(severity):
            dot = QLabel()
            dot.setFixedSize(10, 10)
            dot.setProperty("severity", severity)
            return dot

        def _row(title, severity, default_value):
            row = QHBoxLayout()
            row.addWidget(_severity_dot(severity))
            label = QLabel(title)
            label.setObjectName("rowLabel")
            label.setFixedWidth(230)
            label.setWordWrap(True)
            row.addWidget(label)
            edit = QLineEdit(str(default_value))
            edit.setFixedWidth(56)
            edit.setValidator(_numeric_validator(edit))
            row.addWidget(edit)
            row.addStretch()
            return row, edit

        def _numeric_validator(parent_widget):
            # Only digits and a single decimal point are allowed while typing.
            return QRegExpValidator(QRegExp(r"^\d{0,6}(\.\d{0,3})?$"), parent_widget)

        classification_frame = QFrame()
        classification_frame.setObjectName("sectionFrame")
        classification_layout = QVBoxLayout(classification_frame)
        classification_layout.setContentsMargins(16, 14, 16, 10)
        classification_layout.setSpacing(6)

        section_title = QLabel("EVENT CLASSIFICATION — AASM")
        section_title.setObjectName("sectionTitle")
        classification_layout.addWidget(section_title)

        hypopnea_row, self.hypopnea_threshold = _row("Hypopnea threshold (%)", "hypopnea", hypopnea_percent)
        apnea_row, self.apnea_threshold = _row("Apnea threshold (%)", "apnea", apnea_percent)
        apnea_flow_note = QLabel("= flow reduction of airflow from baseline")
        apnea_flow_note.setObjectName("unitLabel")
        apnea_row.addWidget(apnea_flow_note)
        obstructive_effort_row, self.obstructive_effort_threshold = _row(
            "Threshold for obstructive apnea (%)", "apnea", obstructive_effort_percent
        )
        central_effort_row, self.central_effort_threshold = _row(
            "Threshold for central apnea (%)", "apnea", central_effort_percent
        )
        central_amplitude_row, self.central_amplitude_threshold = _row(
            "Amplitude threshold for central apnea (%)", "apnea", central_amplitude_percent
        )
        classification_layout.addLayout(hypopnea_row)
        classification_layout.addLayout(apnea_row)
        classification_layout.addLayout(obstructive_effort_row)
        classification_layout.addLayout(central_effort_row)
        classification_layout.addLayout(central_amplitude_row)

        layout.addWidget(classification_frame)

        duration_frame = QFrame()
        duration_frame.setObjectName("sectionFrame")
        duration_layout = QVBoxLayout(duration_frame)
        duration_layout.setContentsMargins(16, 14, 16, 10)
        duration_layout.setSpacing(6)

        duration_title = QLabel("EVENT DURATION")
        duration_title.setObjectName("sectionTitle")
        duration_layout.addWidget(duration_title)

        duration_row1 = QHBoxLayout()
        min_label = QLabel("Min. event duration")
        min_label.setObjectName("rowLabel")
        min_label.setFixedWidth(230)
        duration_row1.addWidget(min_label)
        self.min_duration = QLineEdit(str(min_sec))
        self.min_duration.setFixedWidth(56)
        self.min_duration.setValidator(_numeric_validator(self.min_duration))
        duration_row1.addWidget(self.min_duration)
        min_unit = QLabel("seconds")
        min_unit.setObjectName("unitLabel")
        duration_row1.addWidget(min_unit)
        duration_row1.addStretch()
        duration_layout.addLayout(duration_row1)

        duration_row2 = QHBoxLayout()
        max_label = QLabel("Max. event duration")
        max_label.setObjectName("rowLabel")
        max_label.setFixedWidth(230)
        duration_row2.addWidget(max_label)
        self.max_duration = QLineEdit(str(max_sec))
        self.max_duration.setFixedWidth(56)
        self.max_duration.setValidator(_numeric_validator(self.max_duration))
        duration_row2.addWidget(self.max_duration)
        max_unit = QLabel("seconds")
        max_unit.setObjectName("unitLabel")
        duration_row2.addWidget(max_unit)
        duration_row2.addStretch()
        duration_layout.addLayout(duration_row2)

        layout.addWidget(duration_frame)
        layout.addStretch()

    def setup_hypopnea_tab(self):
        """Setup the hypopnea tab."""
        layout = QVBoxLayout(self.hypopnea_tab)

        classic_group = QGroupBox("Classic definition")
        classic_layout = QVBoxLayout()

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Threshold:"))
        self.hypopnea_classic_threshold = QLineEdit("50")
        self.hypopnea_classic_threshold.setFixedWidth(50)
        row1.addWidget(self.hypopnea_classic_threshold)

        row1.addWidget(QLabel("%  [1-90]   = flow reduction of"))

        self.hypopnea_classic_flow_reduction = QLineEdit("50")
        self.hypopnea_classic_flow_reduction.setFixedWidth(50)
        row1.addWidget(self.hypopnea_classic_flow_reduction)

        row1.addWidget(QLabel("%"))
        row1.addStretch()

        classic_layout.addLayout(row1)
        classic_group.setLayout(classic_layout)
        layout.addWidget(classic_group)

        aasm_group = QGroupBox("")
        aasm_layout = QVBoxLayout()

        row2 = QHBoxLayout()

        self.hypopnea_aasm_checkbox = QCheckBox("AASM definition")
        self.hypopnea_aasm_checkbox.setChecked(True)
        row2.addWidget(self.hypopnea_aasm_checkbox)

        row2.addSpacing(20)

        row2.addWidget(QLabel("Threshold:"))
        self.hypopnea_aasm_threshold = QLineEdit("70")
        self.hypopnea_aasm_threshold.setFixedWidth(50)
        row2.addWidget(self.hypopnea_aasm_threshold)

        row2.addWidget(QLabel("%  [1-90]   = flow reduction of"))

        self.hypopnea_aasm_flow_reduction = QLineEdit("30")
        self.hypopnea_aasm_flow_reduction.setFixedWidth(50)
        row2.addWidget(self.hypopnea_aasm_flow_reduction)

        row2.addWidget(QLabel("%"))
        row2.addStretch()

        aasm_layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addSpacing(30)
        row3.addWidget(QLabel("Signal quality switch:"))

        self.hypopnea_aasm_signal_quality = QLineEdit("5")
        self.hypopnea_aasm_signal_quality.setFixedWidth(50)
        row3.addWidget(self.hypopnea_aasm_signal_quality)

        row3.addWidget(QLabel("[0-20]"))
        row3.addStretch()

        aasm_layout.addLayout(row3)

        aasm_group.setLayout(aasm_layout)
        layout.addWidget(aasm_group)

        duration_group = QGroupBox("")
        duration_layout = QHBoxLayout()

        duration_layout.addWidget(QLabel("Min. duration:"))
        self.hypopnea_min_duration = QLineEdit("10")
        self.hypopnea_min_duration.setFixedWidth(50)
        duration_layout.addWidget(self.hypopnea_min_duration)

        duration_layout.addWidget(QLabel("s  [1-20]"))
        duration_layout.addSpacing(30)

        duration_layout.addWidget(QLabel("Max. duration:"))
        self.hypopnea_max_duration = QLineEdit("100")
        self.hypopnea_max_duration.setFixedWidth(50)
        duration_layout.addWidget(self.hypopnea_max_duration)

        duration_layout.addWidget(QLabel("s  [1-120]"))
        duration_layout.addStretch()

        duration_group.setLayout(duration_layout)
        layout.addWidget(duration_group)

        resp_group = QGroupBox("")
        resp_layout = QHBoxLayout()

        resp_layout.addWidget(QLabel("Maximum respiratory mean time when linking apneas/hypopneas:"))

        self.hypopnea_respiratory_mean_time = QLineEdit("1.0")
        self.hypopnea_respiratory_mean_time.setFixedWidth(60)
        resp_layout.addWidget(self.hypopnea_respiratory_mean_time)

        resp_layout.addWidget(QLabel("s  [0.0 - 1.5]"))
        resp_layout.addStretch()

        resp_group.setLayout(resp_layout)
        layout.addWidget(resp_group)

        note = QLabel("Time value of 0 means linking is turned off")
        note.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(note)

        layout.addStretch()

    def get_extra_parameters(self):
        """Get the non-Apnea tab values for app-level caching."""
        try:
            return {
                "hypopnea": {
                    "classic_threshold": float(self.hypopnea_classic_threshold.text()),
                    "classic_flow_reduction": float(self.hypopnea_classic_flow_reduction.text()),
                    "aasm_enabled": self.hypopnea_aasm_checkbox.isChecked(),
                    "aasm_threshold": float(self.hypopnea_aasm_threshold.text()),
                    "aasm_flow_reduction": float(self.hypopnea_aasm_flow_reduction.text()),
                    "aasm_signal_quality_switch": float(self.hypopnea_aasm_signal_quality.text()),
                    "min_duration": float(self.hypopnea_min_duration.text()),
                    "max_duration": float(self.hypopnea_max_duration.text()),
                    "respiratory_mean_time": float(self.hypopnea_respiratory_mean_time.text()),
                },
                "snoring": {
                    "threshold": float(self.snoring_threshold.text()),
                    "min_duration": float(self.snoring_min_duration.text()),
                    "max_duration": float(self.snoring_max_duration.text()),
                    "mean_time": float(self.snoring_mean_time.text()),
                },
                "desaturation": {
                    "threshold": float(self.desaturation_threshold.text()),
                },
            }
        except ValueError:
            return None

        # -------- Classic Definition --------
        classic_group = QGroupBox("Classic definition")
        classic_layout = QVBoxLayout()

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Threshold:"))
        self.hypopnea_classic_threshold = QLineEdit("50")
        self.hypopnea_classic_threshold.setFixedWidth(50)
        row1.addWidget(self.hypopnea_classic_threshold)

        row1.addWidget(QLabel("%  [1-90]   = flow reduction of"))

        self.hypopnea_classic_flow_reduction = QLineEdit("50")
        self.hypopnea_classic_flow_reduction.setFixedWidth(50)
        row1.addWidget(self.hypopnea_classic_flow_reduction)

        row1.addWidget(QLabel("%"))
        row1.addStretch()

        classic_layout.addLayout(row1)
        classic_group.setLayout(classic_layout)
        layout.addWidget(classic_group)

        # -------- AASM Definition --------
        aasm_group = QGroupBox("")
        aasm_layout = QVBoxLayout()

        row2 = QHBoxLayout()

        self.hypopnea_aasm_checkbox = QCheckBox("AASM definition")
        self.hypopnea_aasm_checkbox.setChecked(True)
        row2.addWidget(self.hypopnea_aasm_checkbox)

        row2.addSpacing(20)

        row2.addWidget(QLabel("Threshold:"))
        self.hypopnea_aasm_threshold = QLineEdit("70")
        self.hypopnea_aasm_threshold.setFixedWidth(50)
        row2.addWidget(self.hypopnea_aasm_threshold)

        row2.addWidget(QLabel("%  [1-90]   = flow reduction of"))

        self.hypopnea_aasm_flow_reduction = QLineEdit("30")
        self.hypopnea_aasm_flow_reduction.setFixedWidth(50)
        row2.addWidget(self.hypopnea_aasm_flow_reduction)

        row2.addWidget(QLabel("%"))
        row2.addStretch()

        aasm_layout.addLayout(row2)

        # Signal quality row
        row3 = QHBoxLayout()
        row3.addSpacing(30)
        row3.addWidget(QLabel("Signal quality switch:"))

        self.hypopnea_aasm_signal_quality = QLineEdit("5")
        self.hypopnea_aasm_signal_quality.setFixedWidth(50)
        row3.addWidget(self.hypopnea_aasm_signal_quality)

        row3.addWidget(QLabel("[0-20]"))
        row3.addStretch()

        aasm_layout.addLayout(row3)

        aasm_group.setLayout(aasm_layout)
        layout.addWidget(aasm_group)

        # -------- Duration --------
        duration_group = QGroupBox("")
        duration_layout = QHBoxLayout()

        duration_layout.addWidget(QLabel("Min. duration:"))
        self.hypopnea_min_duration = QLineEdit("10")
        self.hypopnea_min_duration.setFixedWidth(50)
        duration_layout.addWidget(self.hypopnea_min_duration)

        duration_layout.addWidget(QLabel("s  [1-20]"))

        duration_layout.addSpacing(30)

        duration_layout.addWidget(QLabel("Max. duration:"))
        self.hypopnea_max_duration = QLineEdit("100")
        self.hypopnea_max_duration.setFixedWidth(50)
        duration_layout.addWidget(self.hypopnea_max_duration)

        duration_layout.addWidget(QLabel("s  [1-120]"))

        duration_layout.addStretch()

        duration_group.setLayout(duration_layout)
        layout.addWidget(duration_group)

        # -------- Respiratory --------
        resp_group = QGroupBox("")
        resp_layout = QHBoxLayout()

        resp_layout.addWidget(QLabel("Maximum respiratory mean time when linking apneas/hypopneas:"))

        self.hypopnea_respiratory_mean_time = QLineEdit("1.0")
        self.hypopnea_respiratory_mean_time.setFixedWidth(60)
        resp_layout.addWidget(self.hypopnea_respiratory_mean_time)

        resp_layout.addWidget(QLabel("s  [0.0 - 1.5]"))
        resp_layout.addStretch()

        resp_group.setLayout(resp_layout)
        layout.addWidget(resp_group)

        # Footer note
        note = QLabel("Time value of 0 means linking is turned off")
        note.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(note)

        layout.addStretch()
    
    def setup_snoring_tab(self):
        layout = QVBoxLayout(self.snoring_tab)

        main_row = QHBoxLayout()

        # -------- LEFT COLUMN --------
        left_col = QVBoxLayout()

        # Row 1
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Threshold for\n-> snoring:"))

        self.snoring_threshold = QLineEdit("6.0")
        self.snoring_threshold.setFixedWidth(50)
        row1.addWidget(self.snoring_threshold)

        row1.addWidget(QLabel("%  [1.5 - 10.0]"))
        row1.addStretch()
        left_col.addLayout(row1)

        # Row 2
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Min. length of a\nsnoring event:"))

        self.snoring_min_duration = QLineEdit("0.3")
        self.snoring_min_duration.setFixedWidth(50)
        row2.addWidget(self.snoring_min_duration)

        row2.addWidget(QLabel("s  [0.3 - 0.9]"))
        row2.addStretch()
        left_col.addLayout(row2)

        # -------- RIGHT COLUMN --------
        right_col = QVBoxLayout()

        # Row 3
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Max. duration of a\nsnoring event:"))

        self.snoring_max_duration = QLineEdit("3.5")
        self.snoring_max_duration.setFixedWidth(50)
        row3.addWidget(self.snoring_max_duration)

        row3.addWidget(QLabel("s  [2.0 - 5.0]"))
        row3.addStretch()
        right_col.addLayout(row3)

        # Row 4
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Max. resp. snoring\nmean time:"))

        self.snoring_mean_time = QLineEdit("0.5")
        self.snoring_mean_time.setFixedWidth(50)
        row4.addWidget(self.snoring_mean_time)

        row4.addWidget(QLabel("s  [0.0 - 2.0]"))
        row4.addStretch()
        right_col.addLayout(row4)

        # Add both columns
        main_row.addLayout(left_col)
        main_row.addSpacing(40)
        main_row.addLayout(right_col)

        layout.addLayout(main_row)

        # -------- Bottom Note --------
        note = QLabel("Time value of 0 means linking is turned off")
        note.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(note)

        layout.addStretch()
    
    def setup_desaturation_tab(self):
        layout = QVBoxLayout(self.desaturation_tab)

        main_row = QHBoxLayout()

        # Multi-line label
        label = QLabel("Threshold for oxygen\ndesaturation:")
        main_row.addWidget(label)

        # Input box
        self.desaturation_threshold = QLineEdit(str(_detector_default("AASM_HYPOPNEA_SPO2_DESAT_MIN", 3.0)))
        self.desaturation_threshold.setFixedWidth(50)
        main_row.addWidget(self.desaturation_threshold)

        # Unit + range
        main_row.addWidget(QLabel("%  [3 - 5]"))

        main_row.addStretch()

        layout.addLayout(main_row)
        layout.addStretch()
    
    # def setup_csr_tab(self):
    #     layout = QVBoxLayout(self.csr_tab)
    #
    #     # Checkbox (top)
    #     self.csr_checkbox = QCheckBox("Run CSR analysis")
    #     self.csr_checkbox.setChecked(True)
    #     layout.addWidget(self.csr_checkbox)
    #
    #     main_row = QHBoxLayout()
    #
    #     # Label (single line like image)
    #     label = QLabel("Threshold for CSR detection")
    #     main_row.addWidget(label)
    #
    #     # Input box (value corrected)
    #     self.csr_threshold = QLineEdit("0.5")
    #     self.csr_threshold.setFixedWidth(50)
    #     main_row.addWidget(self.csr_threshold)
    #
    #     # Range text
    #     range_label = QLabel("[0.2 - 0.8]")
    #     main_row.addWidget(range_label)
    #
    #     # Push everything left like image
    #     main_row.addStretch()
    #
    #     layout.addLayout(main_row)
    #     layout.addStretch()
    
    def standard_parameter(self):
        """Reset the Apnea fields to the detector's built-in default values."""
        defaults = {}
        if apnea_detector is not None:
            try:
                defaults = apnea_detector.get_default_analysis_parameters()
            except Exception:
                defaults = {}

        hypopnea_percent = defaults.get("AASM_HYPOPNEA_DROP_PERCENT", 30.0)
        apnea_percent = defaults.get("AASM_APNEA_DROP_PERCENT", 75.0)
        obstructive_effort_percent = float(defaults.get("OBSTRUCTIVE_APNEA_EFFORT_THRESHOLD", 0.20)) * 100.0
        central_effort_percent = float(defaults.get("CENTRAL_APNEA_EFFORT_THRESHOLD", 0.60)) * 100.0
        central_amplitude_percent = float(defaults.get("CENTRAL_APNEA_AMPLITUDE_CONFIRM_RATIO", 0.08)) * 100.0
        desat_percent = defaults.get("AASM_HYPOPNEA_SPO2_DESAT_MIN", 3.0)
        min_sec = defaults.get("MIN_EVENT_SEC", 10.0)
        max_sec = defaults.get("MAX_EVENT_SEC", 120.0)

        self.hypopnea_threshold.setText(str(hypopnea_percent))
        self.apnea_threshold.setText(str(apnea_percent))
        self.obstructive_effort_threshold.setText(str(round(obstructive_effort_percent, 1)))
        self.central_effort_threshold.setText(str(round(central_effort_percent, 1)))
        self.central_amplitude_threshold.setText(str(round(central_amplitude_percent, 1)))
        self.min_duration.setText(str(min_sec))
        self.max_duration.setText(str(max_sec))

        # The other tabs are reset here too. Resetting only the Apnea tab left
        # Hypopnea / Snoring / Desaturation showing whatever the user last
        # typed, so "Standard parameter" did not restore a standard setup.
        self.hypopnea_classic_threshold.setText("50")
        self.hypopnea_classic_flow_reduction.setText("50")
        self.hypopnea_aasm_checkbox.setChecked(True)
        self.hypopnea_aasm_threshold.setText("70")
        self.hypopnea_aasm_flow_reduction.setText("30")
        self.hypopnea_aasm_signal_quality.setText("5")
        self.hypopnea_min_duration.setText("10")
        self.hypopnea_max_duration.setText("100")
        self.hypopnea_respiratory_mean_time.setText("1.0")

        self.snoring_threshold.setText("6.0")
        self.snoring_min_duration.setText("0.3")
        self.snoring_max_duration.setText("3.5")
        self.snoring_mean_time.setText("0.5")

        self.desaturation_threshold.setText(str(desat_percent))

        msg_box = QMessageBox(self)
        msg_box.setWindowFlags(msg_box.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.setWindowTitle("Standard parameter")
        msg_box.setText("Default analysis parameters loaded.")
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
        msg_box.setStandardButtons(QMessageBox.Ok)
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

    def get_parameters(self):
        """Get current Apnea field values, mapped to the detector's real AASM constant names."""
        try:
            return {
                "AASM_HYPOPNEA_DROP_PERCENT": float(self.hypopnea_threshold.text()),
                "AASM_APNEA_DROP_PERCENT": float(self.apnea_threshold.text()),
                "OBSTRUCTIVE_APNEA_EFFORT_THRESHOLD": float(self.obstructive_effort_threshold.text()) / 100.0,
                "CENTRAL_APNEA_EFFORT_THRESHOLD": float(self.central_effort_threshold.text()) / 100.0,
                "CENTRAL_APNEA_AMPLITUDE_CONFIRM_RATIO": float(self.central_amplitude_threshold.text()) / 100.0,
                "MIN_EVENT_SEC": float(self.min_duration.text()),
                "MAX_EVENT_SEC": float(self.max_duration.text()),
                # The Desaturation tab drives BOTH detector constants: the
                # hypopnea confirmation threshold and the standalone
                # desaturation (ODI) scorer. Sending only one of them would let
                # the report and the chart disagree about what counts as a 3%
                # fall. Unknown keys are ignored by apply_analysis_parameters.
                "AASM_HYPOPNEA_SPO2_DESAT_MIN": float(self.desaturation_threshold.text()),
                "DESAT_DROP_PERCENT": float(self.desaturation_threshold.text()),
            }
        except ValueError:
            return None
