"""
Button Functions Module - Sleep Sense Application
Contains all button click handlers and menu functionality
"""

import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QFileDialog, QMessageBox, QInputDialog, QLineEdit, QPushButton, QMenu, QAction
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
            menu.addAction('New', self.file_new, 'Ctrl+N')
            menu.addAction('Open', self.file_open, 'Ctrl+O')
            menu.addAction('Save', self.file_save, 'Ctrl+S')
            menu.addSeparator()
            menu.addAction('Export Data', self.file_export, 'Ctrl+E')
            menu.addSeparator()
            menu.addAction('Exit', self.parent.close, 'Ctrl+Q')
            
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
            
        elif menu_type == 'tools':
            menu.addAction('Settings', self.tools_settings, 'Ctrl+,')
            menu.addSeparator()
            menu.addAction('Import Data', self.tools_import_data)
            menu.addAction('Data Analysis', self.tools_data_analysis)
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
    
    # Help Menu Actions
    def help_documentation(self):
        print("Help -> Documentation clicked")
        # TODO: Open documentation
    
    def help_about(self):
        print("Help -> About clicked")
        # TODO: Show about dialog