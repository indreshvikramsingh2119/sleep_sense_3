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
    QFileDialog, QMessageBox, QInputDialog, QLineEdit, QPushButton, QMenu, QAction, QWidget
)
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
            fullscreen_action = menu.addAction('Fullscreen', self.view_fullscreen, 'F11')
            fullscreen_action.setCheckable(True)
            fullscreen_action.setChecked(self.parent.isFullScreen())
            menu.addSeparator()
            menu.addAction('Zoom In', self.view_zoom_in, 'Ctrl++')
            menu.addAction('Zoom Out', self.view_zoom_out, 'Ctrl+-')
            menu.addAction('Reset Zoom', self.view_reset_zoom, 'Ctrl+0')
            menu.addSeparator()
            menu.addAction('Report view', self.view_report_view)
            menu.addAction('Signal view', self.view_signal_view)
            menu.addAction('Event list', self.view_event_list)
            menu.addAction('Quick start', self.view_quick_start)
            
        elif menu_type == 'tools':
            menu.addAction('Settings', self.tools_settings, 'Ctrl+,')
            menu.addSeparator()
            menu.addAction('Import Data', self.tools_import_data)
            menu.addAction('Data Analysis', self.tools_data_analysis)
            menu.addAction('Reanalysis', self.tools_reanalysis)
            menu.addAction('Generate Report', self.tools_generate_report)
            
        elif menu_type == 'help':
            menu.addAction('Documentation', self.help_documentation, 'F1')
            menu.addAction('About', self.help_about)
        
        # Show menu below the button
        button_rect = button.geometry()
        menu_pos = button.mapToGlobal(button_rect.bottomLeft())
        menu.exec_(menu_pos)
    
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
    
    def tools_reanalysis(self):
        print("Tools -> Reanalysis clicked")
        # TODO: Implement reanalysis functionality
    
    # Help Menu Actions
    def help_documentation(self):
        print("Help -> Documentation clicked")
        # TODO: Open documentation
    
    def help_about(self):
        print("Help -> About clicked")
        # TODO: Show about dialog
    
    def file_database(self):
        """Open patient database window - same as red database button"""
        # Call the same open_database method as the red toolbar button
        if hasattr(self.parent, 'open_database'):
            self.parent.open_database()
        else:
            print("Parent does not have open_database method")
    
    def file_open_archive(self):
        """Open archive window - same as blue archive button"""
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
