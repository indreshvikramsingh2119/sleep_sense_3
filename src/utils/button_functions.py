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
from PyQt5.QtWidgets import (
    QFileDialog, QMessageBox, QInputDialog, QLineEdit, QPushButton, QMenu, QAction, QWidget, QDialog, QVBoxLayout,
    QHBoxLayout, QListWidget, QLabel, QComboBox, QCheckBox, QGroupBox, QGridLayout, QSpacerItem, QSizePolicy,
    QRadioButton, QButtonGroup, QSpinBox, QTextEdit, QSlider, QTabWidget, QFormLayout, QFrame
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextDocument
from PyQt5.QtPrintSupport import QPrintDialog, QPrinter


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
        edit_btn = QPushButton('Edit')
        edit_btn.setObjectName("menuButton")
        edit_btn.setMinimumWidth(80)
        edit_btn.setMinimumHeight(35)
        edit_btn.setStyleSheet("""
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
        edit_btn.clicked.connect(lambda: self.show_menu_popup(edit_btn, 'edit'))
        layout.addWidget(edit_btn)
        
        # View Menu Button
        view_btn = QPushButton('View')
        view_btn.setObjectName("menuButton")
        view_btn.setMinimumWidth(80)
        view_btn.setMinimumHeight(35)
        view_btn.setStyleSheet("""
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
        view_btn.clicked.connect(lambda: self.show_menu_popup(view_btn, 'view'))
        layout.addWidget(view_btn)
        
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
                min-width: 180px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            }
            QMenu::item {
                background-color: transparent;
                padding: 8px 16px;
                margin: 2px 8px;
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
            menu.addAction('Database', self.file_database)
            menu.addAction('Archive', self.file_open_archive)
            save_action = menu.addAction('Save report locally', self.file_save_report_locally)
            # Example: disable if no report available
            save_action.setEnabled(bool(getattr(self.parent, 'has_report', True)))
            menu.addAction('Print report', self.file_print_report)
            
            # Print patient instructions submenu
            instr_menu = QMenu('Print patient instructions', menu)
            instr_menu.addAction('Short', lambda: self.file_print_patient_instructions('short'))
            instr_menu.addAction('Full', lambda: self.file_print_patient_instructions('full'))
            menu.addMenu(instr_menu)
            
            menu.addSeparator()
            menu.addAction('View external data', self.file_view_external_data)
            dup_action = menu.addAction('Duplicate', self.file_duplicate)
            dup_action.setEnabled(True)  # will validate inside handler
            # Export submenu
            export_menu = QMenu('Export', menu)
            export_menu.addAction('Export as CSV', lambda: self.file_export('csv'))
            export_menu.addAction('Export as JSON', lambda: self.file_export('json'))
            menu.addMenu(export_menu)
            menu.addAction('Import recording', self.file_import_recording)
            
            menu.addSeparator()
            send_report_action = menu.addAction('Send report by email', self.file_send_report_email)
            send_report_action.setEnabled(True)  # enabled if report exists (checked inside)
            send_rec_action = menu.addAction('Send recording by email', self.file_send_recording_email)
            send_rec_action.setEnabled(True)
            menu.addSeparator()
            menu.addAction('Exit', self.parent.close)
            
        elif menu_type == 'edit':
            menu.addAction('Undo', self.edit_undo, 'Ctrl+Z')
            menu.addAction('Redo', self.edit_redo, 'Ctrl+Y')
            menu.addSeparator()
            menu.addAction('Copy', self.edit_copy, 'Ctrl+C')
            menu.addAction('Paste', self.edit_paste, 'Ctrl+V')
            
        elif menu_type == 'view':
            # Add Quick start with house icon
            quick_start_action = menu.addAction('Quick start', self.view_quick_start)
            # Load and set icon
            from PyQt5.QtGui import QIcon
            from PyQt5.QtCore import QFile
            icon_path = os.path.join(os.path.dirname(__file__), '..', '..', 'icons', 'home.svg')
            if os.path.exists(icon_path):
                quick_start_action.setIcon(QIcon(icon_path))
            
        elif menu_type == 'tools':
            menu.addAction('Re-analyze', self.tools_reanalyze)
            menu.addSeparator()
            menu.addAction('New event group', self.tools_new_event_group)
            menu.addAction('Delete event group', self.tools_delete_event_group)
            menu.addAction('Edit event group', self.tools_edit_event_group)
            menu.addSeparator()
            settings_menu = menu.addMenu('Settings')
            settings_menu.addAction('Signal view', self.tools_settings_signal_view)
            settings_menu.addAction('Report', self.tools_settings_report)
            settings_menu.addAction('Analysis parameters', self.tools_settings_analysis_parameters)
            settings_menu.addAction('EDF export', self.tools_settings_edf_export)
            menu.addAction('Send Event Log by email', self.tools_send_event_log_email)
            menu.addAction('Database Transfer', self.tools_database_transfer)
            
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
        """Create application menu bar with File, Edit, View, Tools, Help menus"""
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
        edit_menu = menubar.addMenu('Edit')
        
        undo_action = QAction('Undo', self.parent)
        undo_action.setShortcut('Ctrl+Z')
        undo_action.setStatusTip('Undo last action')
        undo_action.triggered.connect(self.edit_undo)
        edit_menu.addAction(undo_action)
        
        redo_action = QAction('Redo', self.parent)
        redo_action.setShortcut('Ctrl+Y')
        redo_action.setStatusTip('Redo last action')
        redo_action.triggered.connect(self.edit_redo)
        edit_menu.addAction(redo_action)
        
        edit_menu.addSeparator()
        
        copy_action = QAction('Copy', self.parent)
        copy_action.setShortcut('Ctrl+C')
        copy_action.setStatusTip('Copy selection')
        copy_action.triggered.connect(self.edit_copy)
        edit_menu.addAction(copy_action)
        
        paste_action = QAction('Paste', self.parent)
        paste_action.setShortcut('Ctrl+V')
        paste_action.setStatusTip('Paste from clipboard')
        paste_action.triggered.connect(self.edit_paste)
        edit_menu.addAction(paste_action)
        
        # View Menu
        view_menu = menubar.addMenu('View')
        
        fullscreen_action = QAction('Fullscreen', self.parent)
        fullscreen_action.setShortcut('F11')
        fullscreen_action.setStatusTip('Toggle fullscreen mode')
        fullscreen_action.setCheckable(True)
        fullscreen_action.triggered.connect(self.view_fullscreen)
        view_menu.addAction(fullscreen_action)
        
        view_menu.addSeparator()
        
        zoom_in_action = QAction('Zoom In', self.parent)
        zoom_in_action.setShortcut('Ctrl++')
        zoom_in_action.setStatusTip('Zoom in charts')
        zoom_in_action.triggered.connect(self.view_zoom_in)
        view_menu.addAction(zoom_in_action)
        
        zoom_out_action = QAction('Zoom Out', self.parent)
        zoom_out_action.setShortcut('Ctrl+-')
        zoom_out_action.setStatusTip('Zoom out charts')
        zoom_out_action.triggered.connect(self.view_zoom_out)
        view_menu.addAction(zoom_out_action)
        
        reset_zoom_action = QAction('Reset Zoom', self.parent)
        reset_zoom_action.setShortcut('Ctrl+0')
        reset_zoom_action.setStatusTip('Reset chart zoom')
        reset_zoom_action.triggered.connect(self.view_reset_zoom)
        view_menu.addAction(reset_zoom_action)

        # Add the new view items to menubar View menu
        view_menu.addSeparator()
        report_view_action = QAction('Report view', self.parent)
        report_view_action.setStatusTip('Show report view')
        report_view_action.triggered.connect(self.view_report_view)
        view_menu.addAction(report_view_action)

        

        signal_view_action = QAction('Signal view', self.parent)
        signal_view_action.setStatusTip('Show signal view')
        signal_view_action.triggered.connect(self.view_signal_view)
        view_menu.addAction(signal_view_action)

        event_list_action = QAction('Event list', self.parent)
        event_list_action.setStatusTip('Show event list')
        event_list_action.triggered.connect(self.view_event_list)
        view_menu.addAction(event_list_action)

        quick_start_action = QAction('Quick start', self.parent)
        quick_start_action.setStatusTip('Show quick start')
        quick_start_action.triggered.connect(self.view_quick_start)
        view_menu.addAction(quick_start_action)
         
        # Tools Menu
        tools_menu = menubar.addMenu('Tools')
        
        settings_action = QAction('Settings', self.parent)
        settings_action.setShortcut('Ctrl+,')
        settings_action.setStatusTip('Open application settings')
        settings_action.triggered.connect(self.tools_settings)
        tools_menu.addAction(settings_action)
        
        tools_menu.addSeparator()
        
        data_import_action = QAction('Import Data', self.parent)
        data_import_action.setStatusTip('Import patient data')
        data_import_action.triggered.connect(self.tools_import_data)
        tools_menu.addAction(data_import_action)
        
        data_analysis_action = QAction('Data Analysis', self.parent)
        data_analysis_action.setStatusTip('Open data analysis tools')
        data_analysis_action.triggered.connect(self.tools_data_analysis)
        tools_menu.addAction(data_analysis_action)
        
        report_generator_action = QAction('Generate Report', self.parent)
        report_generator_action.setStatusTip('Generate medical report')
        report_generator_action.triggered.connect(self.tools_generate_report)
        tools_menu.addAction(report_generator_action)
        
        # Help Menu
        help_menu = menubar.addMenu('Help')
        
        documentation_action = QAction('Documentation', self.parent)
        documentation_action.setShortcut('F1')
        documentation_action.setStatusTip('Open documentation')
        documentation_action.triggered.connect(self.help_documentation)
        help_menu.addAction(documentation_action)
        
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
    
    def file_export(self):
        print("File -> Export Data clicked")
        # TODO: Implement data export functionality
    
    # Edit Menu Actions
    def edit_undo(self):
        print("Edit -> Undo clicked")
        # TODO: Implement undo functionality
    
    def edit_redo(self):
        print("Edit -> Redo clicked")
        # TODO: Implement redo functionality
    
    def edit_copy(self):
        print("Edit -> Copy clicked")
        # TODO: Implement copy functionality
    
    def edit_paste(self):
        print("Edit -> Paste clicked")
        # TODO: Implement paste functionality
    
    # View Menu Actions
    def view_fullscreen(self, checked):
        if checked:
            self.parent.showFullScreen()
        else:
            self.parent.showNormal()
        print(f"View -> Fullscreen {'enabled' if checked else 'disabled'}")
    
    def view_zoom_in(self):
        print("View -> Zoom In clicked")
        # TODO: Implement zoom in functionality
    
    def view_zoom_out(self):
        print("View -> Zoom Out clicked")
        # TODO: Implement zoom out functionality
    
    def view_reset_zoom(self):
        print("View -> Reset Zoom clicked")
        # TODO: Implement reset zoom functionality
    
    # Tools Menu Actions
    def tools_settings(self):
        print("Tools -> Settings clicked")
        # TODO: Implement settings dialog
    
    def tools_import_data(self):
        print("Tools -> Import Data clicked")
        # TODO: Implement data import functionality
    
    def tools_data_analysis(self):
        print("Tools -> Data Analysis clicked")
        # TODO: Implement data analysis tools
    
    def tools_generate_report(self):
        print("Tools -> Generate Report clicked")
        # TODO: Implement report generation
    
    def tools_analysis_parameters(self):
        """Analysis Parameters"""
        print("Tools -> Analysis Parameters clicked")
        # TODO: Implement analysis parameters functionality
    
    def tools_reanalyze(self):
        """Re-analyze"""
        print("Tools -> Re-analyze clicked")
        # TODO: Implement re-analyze functionality
    
    def tools_new_event_group(self):
        """New event group"""
        print("Tools -> New event group clicked")
        # TODO: Implement new event group functionality
    
    def tools_delete_event_group(self):
        """Delete event group"""
        print("Tools -> Delete event group clicked")
        # TODO: Implement delete event group functionality
    
    def tools_edit_event_group(self):
        """Edit event group"""
        print("Tools -> Edit event group clicked")
        # TODO: Implement edit event group functionality
    
    def tools_send_event_log_email(self):
        """Send Event Log by email"""
        print("Tools -> Send Event Log by email clicked")
        # TODO: Implement send event log by email functionality
    
    def tools_database_transfer(self):
        """Database Transfer"""
        print("Tools -> Database Transfer clicked")
        # TODO: Implement database transfer functionality
    
        
    def tools_settings_signal_view(self):
        """Signal view"""
        print("Tools -> Settings -> Signal view clicked")
        dialog = SignalViewDialog(self.parent)
        if dialog.exec_() == QDialog.Accepted:
            print("Signal view settings applied")
            # TODO: Apply signal view settings
    
    def tools_settings_report(self):
        """Report"""
        print("Tools -> Settings -> Report clicked")
        dialog = ReportSettingsDialog(self.parent)
        if dialog.exec_() == QDialog.Accepted:
            print("Report settings applied")
            # TODO: Apply report settings
    
    def tools_settings_analysis_parameters(self):
        """Analysis parameters"""
        print("Tools -> Settings -> Analysis parameters clicked")
        dialog = AnalysisParametersDialog(self.parent)
        dialog.exec_()
    
    def tools_settings_edf_export(self):
        """EDF export"""
        print("Tools -> Settings -> EDF export clicked")
        dialog = EDFExportDialog(self.parent)
        if dialog.exec_() == QDialog.Accepted:
            print("EDF export settings applied")
            # TODO: Apply EDF export settings
    
    def tools_settings_general(self):
        """General settings"""
        print("Tools -> Settings -> General clicked")
        # TODO: Implement general settings dialog
    
    def tools_settings_data(self):
        """Data settings"""
        print("Tools -> Settings -> Data clicked")
        # TODO: Implement data settings dialog
    
    def tools_settings_display(self):
        """Display settings"""
        print("Tools -> Settings -> Display clicked")
        # TODO: Implement display settings dialog
    
    def tools_settings_export(self):
        """Export settings"""
        print("Tools -> Settings -> Export clicked")
        # TODO: Implement export settings dialog
    
    def tools_reanalysis(self):
        """Reanalysis"""
        print("Tools -> Reanalysis clicked")
        # TODO: Implement reanalysis functionality
    
    # Help Menu Actions
    def help_clinical_guide(self):
        print("Help -> Clinical Guide clicked")
        # TODO: Open clinical guide
    
    def help_patient_instructions(self):
        print("Help -> Patient instructions clicked")
        # TODO: Open patient instructions
    
    def help_program_info(self):
        print("Help -> Program info clicked")
        # TODO: Show program information
    
    def help_recording_info(self):
        print("Help -> Recording info clicked")
        # TODO: Show recording information
    
    def help_device_info(self):
        print("Help -> Device info clicked")
        # TODO: Show device information
    
    def help_documentation(self):
        print("Help -> Documentation clicked")
        # TODO: Open documentation
    
    def help_about(self):
        print("Help -> About clicked")
        # TODO: Show about dialog
    
    def file_database(self):
        """Open patient database window - same as red database button"""
        # Check if parent has monitor chart with selection active and block if needed
        if (hasattr(self.parent, 'monitor_chart') and 
            hasattr(self.parent.monitor_chart, 'block_if_selection_active') and 
            self.parent.monitor_chart.block_if_selection_active()):
            return
        
        # Call the same open_database method as the red toolbar button
        if hasattr(self.parent, 'open_database'):
            self.parent.open_database()
        else:
            print("Parent does not have open_database method")
    
    def file_open_archive(self):
        """Open archive window - same as blue archive button"""
        # Check if parent has monitor chart with selection active and block if needed
        if (hasattr(self.parent, 'monitor_chart') and 
            hasattr(self.parent.monitor_chart, 'block_if_selection_active') and 
            self.parent.monitor_chart.block_if_selection_active()):
            return
        
        # Call the same open_archive method as the blue toolbar button
        if hasattr(self.parent, 'open_archive'):
            self.parent.open_archive()
        else:
            print("Parent does not have open_archive method")
    
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
    
    def file_save_report_locally(self):
        """Save current report HTML/text to a file chosen by the user"""
        suggested_name = "sleep_report.html"
        filename, _ = QFileDialog.getSaveFileName(self.parent, "Save report locally", suggested_name, "HTML files (*.html);;Text files (*.txt);;All files (*)")
        if not filename:
            return
        # Try to get report from parent; fallback to placeholder text
        report_html = None
        if hasattr(self.parent, "get_report_html"):
            try:
                report_html = self.parent.get_report_html()
            except Exception:
                report_html = None
        if report_html:
            mode = "w"
            try:
                with open(filename, mode, encoding="utf-8") as f:
                    f.write(report_html)
                QMessageBox.information(self.parent, "Save Report", f"Report saved to:\n{filename}")
            except Exception as e:
                QMessageBox.critical(self.parent, "Save Error", str(e))
        else:
            text, ok = QInputDialog.getMultiLineText(self.parent, "Save Report", "No report available from application. Enter text to save:")
            if ok and text:
                try:
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(text)
                    QMessageBox.information(self.parent, "Save Report", f"Report saved to:\n{filename}")
                except Exception as e:
                    QMessageBox.critical(self.parent, "Save Error", str(e))
    
    def file_print_report(self):
        """Print current report (HTML or plain text)"""
        # Get report content
        report_html = None
        report_text = None
        if hasattr(self.parent, "get_report_html"):
            try:
                report_html = self.parent.get_report_html()
            except Exception:
                report_html = None
        if not report_html and hasattr(self.parent, "get_report_text"):
            try:
                report_text = self.parent.get_report_text()
            except Exception:
                report_text = None
        if not report_html and not report_text:
            QMessageBox.information(self.parent, "Print Report", "No report available to print.")
            return
        doc = QTextDocument()
        if report_html:
            doc.setHtml(report_html)
        else:
            doc.setPlainText(report_text)
        printer = QPrinter()
        dlg = QPrintDialog(printer, self.parent)
        if dlg.exec_() == QPrintDialog.Accepted:
            doc.print_(printer)
            QMessageBox.information(self.parent, "Print", "Print job sent.")
    
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
    
    def file_view_external_data(self):
        """Open an external data file with the system default application"""
        path, _ = QFileDialog.getOpenFileName(self.parent, "Open external data", os.path.expanduser("~"))
        if not path:
            return
        try:
            if platform.system() == "Darwin":
                subprocess.run(["open", path])
            elif platform.system() == "Windows":
                os.startfile(path)
            else:
                subprocess.run(["xdg-open", path])
        except Exception as e:
            QMessageBox.warning(self.parent, "Open File", f"Could not open file:\n{e}")
    
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

    
    def file_export(self, fmt='csv'):
        """Export current dataset as CSV or JSON if parent exposes get_current_data()"""
        if not hasattr(self.parent, "get_current_data"):
            QMessageBox.information(self.parent, "Export", "Export not available: application does not expose data.")
            return
        data = None
        try:
            data = self.parent.get_current_data()
        except Exception as e:
            QMessageBox.critical(self.parent, "Export Error", str(e))
            return
        if not data:
            QMessageBox.information(self.parent, "Export", "No data available to export.")
            return
        if fmt == 'csv':
            filename, _ = QFileDialog.getSaveFileName(self.parent, "Export as CSV", "export.csv", "CSV files (*.csv)")
            if not filename:
                return
            try:
                # assume data is list of dicts
                with open(filename, "w", newline='', encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=list(data[0].keys()))
                    writer.writeheader()
                    writer.writerows(data)
                QMessageBox.information(self.parent, "Export", f"Exported CSV to:\n{filename}")
            except Exception as e:
                QMessageBox.critical(self.parent, "Export Error", str(e))
        else:
            filename, _ = QFileDialog.getSaveFileName(self.parent, "Export as JSON", "export.json", "JSON files (*.json)")
            if not filename:
                return
            try:
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                QMessageBox.information(self.parent, "Export", f"Exported JSON to:\n{filename}")
            except Exception as e:
                QMessageBox.critical(self.parent, "Export Error", str(e))
    
    def file_import_recording(self):
        """Import a recording file into application's recordings folder (creates folder if needed)"""
        path, _ = QFileDialog.getOpenFileName(self.parent, "Import recording", os.path.expanduser("~"))
        if not path:
            return
        recordings_dir = getattr(self.parent, "recordings_dir", os.path.join(os.path.expanduser("~"), "sleep_recordings"))
        os.makedirs(recordings_dir, exist_ok=True)
        try:
            dest = os.path.join(recordings_dir, os.path.basename(path))
            shutil.copy2(path, dest)
            QMessageBox.information(self.parent, "Import Recording", f"Imported to:\n{dest}")
        except Exception as e:
            QMessageBox.critical(self.parent, "Import Error", str(e))
    
    def _open_mailto(self, subject="", body="", attach_path=None):
        """Open default mail client with subject/body. Attachment handled by user (or via platform-specific logic)."""
        # Basic mailto
        mailto = f"mailto:?subject={webbrowser.quote(subject)}&body={webbrowser.quote(body)}"
        try:
            webbrowser.open(mailto)
            QMessageBox.information(self.parent, "Email", "Email client opened. Attach files manually if required.")
        except Exception as e:
            QMessageBox.warning(self.parent, "Email", f"Could not open mail client:\n{e}")
    
    def file_send_report_email(self):
        """Prepare email for report; opens mail client with subject/body"""
        # Try to locate a saved report or generate a temporary one
        report_path = None
        if hasattr(self.parent, "get_report_html"):
            try:
                html = self.parent.get_report_html()
                tmp = os.path.join(tempfile.gettempdir(), f"sleep_report_{datetime.now().strftime('%Y%m%d%H%M%S')}.html")
                with open(tmp, "w", encoding="utf-8") as f:
                    f.write(html)
                report_path = tmp
            except Exception:
                report_path = None
        subject = "Sleep Sense Report"
        body = "Please find the sleep report attached (attach manually if not attached automatically)."
        self._open_mailto(subject, body, attach_path=report_path)
    
    def file_send_recording_email(self):
        """Prompt user to select a recording to attach and open mail client"""
        path, _ = QFileDialog.getOpenFileName(self.parent, "Select recording to send", os.path.expanduser("~"))
        if not path:
            return
        subject = "Recording from Sleep Sense"
        body = "Please find the recording attached (attach manually if not attached automatically)."
        self._open_mailto(subject, body, attach_path=path)

    def _activate_view(self, key, friendly_name):
        """Try multiple ways to ask the parent dashboard to show a named view/tab/page.
        Tries common handler names, pages dicts, stacked widgets and findChild fallback.
        """
        # 1) Common explicit methods
        candidates = [
            f"show_{key}_view", f"show_{key}", f"open_{key}_view", f"open_{key}",
            "open_view", "show_page", "navigate_to", "set_current_view", "set_view"
        ]
        for name in candidates:
            if hasattr(self.parent, name):
                try:
                    func = getattr(self.parent, name)
                    # try calling with common signature options
                    try:
                        func()
                    except TypeError:
                        try:
                            func(key)
                        except TypeError:
                            func(friendly_name)
                    return True
                except Exception:
                    # continue trying other methods
                    pass

        # 2) pages dict or attribute
        pages = getattr(self.parent, "pages", None)
        if isinstance(pages, dict):
            page = pages.get(key) or pages.get(friendly_name) or pages.get(key.lower())
            if page:
                try:
                    page.show()
                    try:
                        page.setFocus()
                    except Exception:
                        pass
                    return True
                except Exception:
                    pass

        # 3) stacked widget patterns (common names)
        stacked = getattr(self.parent, "stacked_widget", None) or getattr(self.parent, "stacked", None) or getattr(self.parent, "central_stack", None)
        if stacked is not None:
            try:
                # try to find a child page by objectName
                for i in range(stacked.count()):
                    w = stacked.widget(i)
                    if w.objectName().lower() in (key.lower(), friendly_name.lower()):
                        stacked.setCurrentIndex(i)
                        return True
                    # also check readable windowTitle / accessibleName
                    if getattr(w, "windowTitle", None) and w.windowTitle().lower() in (key.lower(), friendly_name.lower()):
                        stacked.setCurrentIndex(i)
                        return True
                # fallback: if stacked has setCurrentWidget and parent has attribute named key
                target = getattr(self.parent, key, None)
                if target is not None:
                    stacked.setCurrentWidget(target)
                    return True
            except Exception:
                pass

        # 4) try findChild on parent
        try:
            found = None
            try:
                found = self.parent.findChild(QWidget, key)
            except Exception:
                found = None
            if not found:
                try:
                    found = self.parent.findChild(QWidget, friendly_name)
                except Exception:
                    found = None
            if found:
                found.show()
                try:
                    found.setFocus()
                except Exception:
                    pass
                return True
        except Exception:
            pass

        # Nothing worked
        QMessageBox.information(self.parent, friendly_name, f"Could not locate '{friendly_name}' view in the current UI.")
        return False

    # New view handlers
    def view_report_view(self):
        self._activate_view('report', 'Report view')

    def view_signal_view(self):
        self._activate_view('signal', 'Signal view')

    def view_event_list(self):
        self._activate_view('event_list', 'Event list')

    def view_quick_start(self):
        self._activate_view('quick_start', 'Quick start')


class SignalViewDialog(QDialog):
    """Dialog for customizing signal view settings"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Customize signal view")
        self.setFixedSize(400, 300)
        self.init_ui()
    
    def init_ui(self):
        """Initialize the dialog UI"""
        layout = QVBoxLayout()
        
        # Create Only window group
        only_window_group = QGroupBox("Only window")
        only_window_layout = QGridLayout()
        
        # Resolution dropdown
        resolution_label = QLabel("Resolution:")
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["10 sec.", "20 sec.", "30 sec.", "60 sec."])
        self.resolution_combo.setCurrentText("10 sec.")
        
        # Channels and Events buttons
        channels_button = QPushButton("Channels...")
        events_button = QPushButton("Events...")
        
        only_window_layout.addWidget(resolution_label, 0, 0)
        only_window_layout.addWidget(self.resolution_combo, 0, 1)
        only_window_layout.addWidget(channels_button, 1, 0)
        only_window_layout.addWidget(events_button, 1, 1)
        
        only_window_group.setLayout(only_window_layout)
        
        # Checkboxes
        self.signal_cursor_checkbox = QCheckBox("Signal cursor")
        self.hide_channels_checkbox = QCheckBox("Hide channels with no data")
        self.hide_channels_checkbox.setChecked(True)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        standard_values_button = QPushButton("Standard values")
        
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        standard_values_button.clicked.connect(self.reset_to_standard_values)
        
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(standard_values_button)
        
        # Add all to main layout
        layout.addWidget(only_window_group)
        layout.addWidget(self.signal_cursor_checkbox)
        layout.addWidget(self.hide_channels_checkbox)
        layout.addStretch()
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def reset_to_standard_values(self):
        """Reset to standard values"""
        self.resolution_combo.setCurrentText("10 sec.")
        self.signal_cursor_checkbox.setChecked(False)
        self.hide_channels_checkbox.setChecked(True)
    
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
        """Load standard parameters"""
        self._set_all_checkboxes(self.channel_checkboxes, True)
        self._set_all_checkboxes(self.event_checkboxes, True)
        QMessageBox.information(self, "Standard Parameters", "Standard parameters loaded")
    
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
        self.setWindowTitle("Analysis parameters")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self.init_ui()
    
    def init_ui(self):
        """Initialize the dialog UI"""
        main_layout = QVBoxLayout(self)
        
        # Tab Widget
        self.tab_widget = QTabWidget(self)
        main_layout.addWidget(self.tab_widget)
        
        # Create tabs
        self.apnea_tab = QWidget()
        self.hypopnea_tab = QWidget()
        self.snoring_tab = QWidget()
        self.desaturation_tab = QWidget()
        self.csr_tab = QWidget()
        
        self.tab_widget.addTab(self.apnea_tab, "Apnea")
        self.tab_widget.addTab(self.hypopnea_tab, "Hypopnea")
        self.tab_widget.addTab(self.snoring_tab, "Snoring")
        self.tab_widget.addTab(self.desaturation_tab, "Desaturation")
        self.tab_widget.addTab(self.csr_tab, "CSR")
        
        # Setup Apnea tab (main tab with all fields from image)
        self.setup_apnea_tab()
        self.setup_hypopnea_tab()
        self.setup_snoring_tab()
        self.setup_desaturation_tab()
        self.setup_csr_tab()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        standard_button = QPushButton("standard parameter")
        standard_button.clicked.connect(self.standard_parameter)
        button_layout.addWidget(standard_button)
        
        main_layout.addLayout(button_layout)
    
    def setup_apnea_tab(self):
        layout = QVBoxLayout(self.apnea_tab)

        # -------- Top Threshold Row --------
        top_row = QHBoxLayout()

        top_row.addWidget(QLabel("Threshold:"))

        self.classic_threshold = QLineEdit("20")
        self.classic_threshold.setFixedWidth(50)
        top_row.addWidget(self.classic_threshold)

        top_row.addWidget(QLabel("% [1-90]   = flow reduction of"))

        self.classic_flow_reduction = QLineEdit("80")
        self.classic_flow_reduction.setFixedWidth(50)
        top_row.addWidget(self.classic_flow_reduction)

        top_row.addWidget(QLabel("%"))
        top_row.addStretch()

        layout.addLayout(top_row)

        # -------- Duration --------
        duration_layout = QVBoxLayout()

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Min. duration:"))

        self.min_duration = QLineEdit("10")
        self.min_duration.setFixedWidth(50)
        row1.addWidget(self.min_duration)

        row1.addWidget(QLabel("s  [1-20]"))
        row1.addStretch()

        duration_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Max. duration:"))

        self.max_duration = QLineEdit("80")
        self.max_duration.setFixedWidth(50)
        row2.addWidget(self.max_duration)

        row2.addWidget(QLabel("s  [1-100]"))
        row2.addStretch()

        duration_layout.addLayout(row2)

        layout.addLayout(duration_layout)

        # -------- Separator Line --------
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # -------- Apnea Type Section --------
        section_label = QLabel("Determining the apnea type in conjunction with the respiratory drive signal:")
        layout.addWidget(section_label)

        # Row 1
        row3 = QHBoxLayout()
        row3.addSpacing(20)
        row3.addWidget(QLabel("Threshold for obstructive apnea:"))

        self.obstructive_threshold = QLineEdit("20")
        self.obstructive_threshold.setFixedWidth(50)
        row3.addWidget(self.obstructive_threshold)

        row3.addWidget(QLabel("% [0-49]"))
        row3.addStretch()

        layout.addLayout(row3)

        # Row 2
        row4 = QHBoxLayout()
        row4.addSpacing(20)
        row4.addWidget(QLabel("Threshold for central apnea:"))

        self.central_threshold = QLineEdit("60")
        self.central_threshold.setFixedWidth(50)
        row4.addWidget(self.central_threshold)

        row4.addWidget(QLabel("% [50-80]"))
        row4.addStretch()

        layout.addLayout(row4)

        # Row 3
        row5 = QHBoxLayout()
        row5.addSpacing(20)
        row5.addWidget(QLabel("Amplitude threshold for central apnea:"))

        self.central_amplitude = QLineEdit("8")
        self.central_amplitude.setFixedWidth(50)
        row5.addWidget(self.central_amplitude)

        row5.addWidget(QLabel("% [2-30]"))
        row5.addStretch()

        layout.addLayout(row5)

        layout.addStretch()
    
    def setup_hypopnea_tab(self):
        """Setup Hypopnea tab EXACT like reference UI"""
        layout = QVBoxLayout(self.hypopnea_tab)

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
        self.desaturation_threshold = QLineEdit("4")
        self.desaturation_threshold.setFixedWidth(50)
        main_row.addWidget(self.desaturation_threshold)

        # Unit + range
        main_row.addWidget(QLabel("%  [3 - 5]"))

        main_row.addStretch()

        layout.addLayout(main_row)
        layout.addStretch()
    
    def setup_csr_tab(self):
        layout = QVBoxLayout(self.csr_tab)

        # Checkbox (top)
        self.csr_checkbox = QCheckBox("Run CSR analysis")
        self.csr_checkbox.setChecked(True)
        layout.addWidget(self.csr_checkbox)

        main_row = QHBoxLayout()

        # Label (single line like image)
        label = QLabel("Threshold for CSR detection")
        main_row.addWidget(label)

        # Input box (value corrected)
        self.csr_threshold = QLineEdit("0.5")
        self.csr_threshold.setFixedWidth(50)
        main_row.addWidget(self.csr_threshold)

        # Range text
        range_label = QLabel("[0.2 - 0.8]")
        main_row.addWidget(range_label)

        # Push everything left like image
        main_row.addStretch()

        layout.addLayout(main_row)
        layout.addStretch()
    
    def standard_parameter(self):
        """Load standard parameters"""
        # Set default ResMed values
        self.classic_threshold.setText("20")
        self.classic_flow_reduction.setText("80")
        self.min_duration.setText("10")
        self.max_duration.setText("80")
        self.obstructive_threshold.setText("20")
        self.central_threshold.setText("60")
        self.central_amplitude.setText("8")
        
        QMessageBox.information(self, "ResMed Parameters", "ResMed standard parameters loaded")
    
    def get_parameters(self):
        """Get current analysis parameters"""
        return {
            'classic_threshold': self.classic_threshold.text(),
            'classic_flow_reduction': self.classic_flow_reduction.text(),
            'min_duration': self.min_duration.text(),
            'max_duration': self.max_duration.text(),
            'obstructive_threshold': self.obstructive_threshold.text(),
            'central_threshold': self.central_threshold.text(),
            'central_amplitude': self.central_amplitude.text()
        }
