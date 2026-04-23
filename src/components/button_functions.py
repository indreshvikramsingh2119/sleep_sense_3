"""
Button Functions Module - Sleep Sense Application
Contains all button click handlers and menu functionality
"""

import os
from datetime import datetime
from PyQt5.QtWidgets import (
    QFileDialog, QMessageBox, QInputDialog, QLineEdit
)
from PyQt5.QtGui import QTextDocument
from PyQt5.QtPrintSupport import QPrintDialog, QPrinter


class ButtonFunctions:
    """Class containing all button and menu functionality"""
    
    def __init__(self, parent_window):
        self.parent = parent_window
    
    # File Menu Functions
    def file_database(self):
        """Handle Database menu option"""
        # Simulate database connection/management
        msg = QMessageBox(self.parent)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Database Management")
        msg.setText("Database functionality would be implemented here.")
        msg.setInformativeText("This would connect to patient database, manage records, etc.")
        msg.exec_()
        print("File -> Database clicked")
    
    def file_archive(self):
        """Handle Archive menu option"""
        # Allow user to select files to archive
        files, _ = QFileDialog.getOpenFileNames(
            self.parent,
            "Select Files to Archive",
            "",
            "Data Files (*.json *.csv *.edf *.txt);;All Files (*)"
        )
        if files:
            msg = QMessageBox(self.parent)
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Archive Files")
            msg.setText(f"Selected {len(files)} file(s) for archiving:")
            msg.setInformativeText("\n".join([f"• {os.path.basename(f)}" for f in files[:5]]))
            if len(files) > 5:
                msg.setInformativeText(msg.informativeText() + f"\n... and {len(files) - 5} more")
            msg.exec_()
        print("File -> Archive clicked")
    
    def file_save_report_locally(self):
        """Handle Save report locally menu option"""
        # Get current patient ID or use default
        patient_id = getattr(self.parent.patient_info.patient_id_input, 'currentText', lambda: "--------")()
        if patient_id == "--------":
            patient_id = "UNKNOWN"
        
        # Generate default filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"sleep_report_{patient_id}_{timestamp}.json"
        
        # Save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self.parent,
            "Save Report Locally",
            default_filename,
            "JSON Files (*.json);;CSV Files (*.csv);;All Files (*)"
        )
        
        if file_path:
            try:
                # Generate sample report data
                report_data = {
                    "patient_id": patient_id,
                    "timestamp": datetime.now().isoformat(),
                    "report_type": "sleep_monitoring",
                    "data": {
                        "sleep_duration": "7.5 hours",
                        "sleep_quality": "Good",
                        "spo2_average": "98%",
                        "events": [
                            {"time": "23:30", "type": "Sleep Onset"},
                            {"time": "06:45", "type": "Wake Up"}
                        ]
                    }
                }
                
                # Save the file
                import json
                with open(file_path, 'w') as f:
                    json.dump(report_data, f, indent=2)
                
                QMessageBox.information(self.parent, "Report Saved", f"Report saved successfully to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self.parent, "Error", f"Failed to save report:\n{str(e)}")
        
        print("File -> Save report locally clicked")
    
    def file_print_report(self):
        """Handle Print report menu option"""
        # Create a simple HTML report for printing
        patient_id = getattr(self.parent.patient_info.patient_id_input, 'currentText', lambda: "--------")()
        html_content = f"""
        <html>
        <head><title>Sleep Report</title></head>
        <body>
            <h1>Sleep Monitoring Report</h1>
            <p><strong>Patient ID:</strong> {patient_id}</p>
            <p><strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <h2>Summary</h2>
            <p>This is a sample sleep monitoring report for printing purposes.</p>
            <p>Actual report data would be included here.</p>
        </body>
        </html>
        """
        
        # Create print dialog
        printer = QPrinter()
        print_dialog = QPrintDialog(printer, self.parent)
        
        if print_dialog.exec_() == QPrintDialog.Accepted:
            try:
                document = QTextDocument()
                document.setHtml(html_content)
                document.print_(printer)
                QMessageBox.information(self.parent, "Print Complete", "Report sent to printer successfully.")
            except Exception as e:
                QMessageBox.critical(self.parent, "Print Error", f"Failed to print report:\n{str(e)}")
        
        print("File -> Print report clicked")
    
    def file_print_patient_instructions(self):
        """Handle Print patient instructions menu option"""
        # Create patient instructions
        instructions_html = """
        <html>
        <head><title>Patient Instructions</title></head>
        <body>
            <h1>Patient Instructions - Sleep Monitoring</h1>
            <h2>Before the Test:</h2>
            <ul>
                <li>Avoid caffeine for 12 hours before the test</li>
                <li>Avoid alcohol for 24 hours before the test</li>
                <li>Take usual medications unless advised otherwise</li>
                <li>Arrive 15 minutes early for setup</li>
            </ul>
            <h2>During the Test:</h2>
            <ul>
                <li>Relax and try to sleep normally</li>
                <li>Inform staff if you need assistance</li>
                <li>Try to minimize movement during sleep</li>
            </ul>
            <h2>After the Test:</h2>
            <ul>
                <li>Results will be available within 3-5 business days</li>
                <li>Follow up with your physician</li>
                <li>Continue any prescribed treatments</li>
            </ul>
        </body>
        </html>
        """
        
        # Create print dialog
        printer = QPrinter()
        print_dialog = QPrintDialog(printer, self.parent)
        
        if print_dialog.exec_() == QPrintDialog.Accepted:
            try:
                document = QTextDocument()
                document.setHtml(instructions_html)
                document.print_(printer)
                QMessageBox.information(self.parent, "Print Complete", "Patient instructions sent to printer successfully.")
            except Exception as e:
                QMessageBox.critical(self.parent, "Print Error", f"Failed to print instructions:\n{str(e)}")
        
        print("File -> Print patient instructions clicked")
    
    def file_view_external_data(self):
        """Handle View external data menu option"""
        # Select external data file
        file_path, _ = QFileDialog.getOpenFileName(
            self.parent,
            "Select External Data File",
            "",
            "Data Files (*.json *.csv *.edf *.txt *.xml);;All Files (*)"
        )
        
        if file_path:
            try:
                # Read and display file content
                with open(file_path, 'r') as f:
                    content = f.read()
                
                # Create a dialog to show the content
                dialog = QMessageBox(self.parent)
                dialog.setWindowTitle("External Data Viewer")
                dialog.setText(f"External Data File: {os.path.basename(file_path)}")
                dialog.setDetailedText(content[:1000] + "..." if len(content) > 1000 else content)
                dialog.setIcon(QMessageBox.Information)
                dialog.exec_()
                
            except Exception as e:
                QMessageBox.critical(self.parent, "Error", f"Failed to read external data file:\n{str(e)}")
        
        print("File -> View external data clicked")
    
    def file_duplicate(self):
        """Handle Duplicate menu option"""
        # Get current patient data for duplication
        patient_id = getattr(self.parent.patient_info.patient_id_input, 'currentText', lambda: "--------")()
        
        if patient_id == "--------":
            QMessageBox.warning(self.parent, "No Data", "No patient data available to duplicate.")
            return
        
        # Ask for new patient ID
        new_id, ok = QInputDialog.getText(self.parent, "Duplicate Record", "Enter new Patient ID:")
        
        if ok and new_id:
            # Simulate duplication process
            QMessageBox.information(self.parent, "Duplicate Complete", 
                f"Patient record duplicated successfully.\n"
                f"Original: {patient_id}\n"
                f"New: {new_id}")
        
        print("File -> Duplicate clicked")
    
    def file_export(self):
        """Handle Export menu option"""
        # Export dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self.parent,
            "Export Data",
            f"sleep_data_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "CSV Files (*.csv);;JSON Files (*.json);;Excel Files (*.xlsx);;All Files (*)"
        )
        
        if file_path:
            try:
                # Generate sample export data
                if file_path.endswith('.csv'):
                    import csv
                    with open(file_path, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(['Patient ID', 'Timestamp', 'SpO2', 'Pulse', 'Event'])
                        writer.writerow(['PATIENT001', datetime.now().isoformat(), '98', '72', 'Normal'])
                        writer.writerow(['PATIENT001', (datetime.now().timestamp() + 3600), '97', '75', 'Movement'])
                else:
                    import json
                    export_data = {
                        "export_timestamp": datetime.now().isoformat(),
                        "patient_records": [
                            {
                                "patient_id": "PATIENT001",
                                "data": {"spo2": [98, 97, 99], "pulse": [72, 75, 70]}
                            }
                        ]
                    }
                    with open(file_path, 'w') as f:
                        json.dump(export_data, f, indent=2)
                
                QMessageBox.information(self.parent, "Export Complete", f"Data exported successfully to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self.parent, "Export Error", f"Failed to export data:\n{str(e)}")
        
        print("File -> Export clicked")
    
    def file_import_recording(self):
        """Handle Import recording menu option"""
        # Import recording dialog
        files, _ = QFileDialog.getOpenFileNames(
            self.parent,
            "Import Recording Files",
            "",
            "Recording Files (*.wav *.mp3 *.edf *.csv *.json);;All Files (*)"
        )
        
        if files:
            try:
                # Simulate importing recordings
                imported_files = []
                for file_path in files:
                    # Simulate processing
                    filename = os.path.basename(file_path)
                    imported_files.append(filename)
                
                QMessageBox.information(self.parent, "Import Complete", 
                    f"Successfully imported {len(imported_files)} recording(s):\n" + 
                    "\n".join([f"• {f}" for f in imported_files[:5]]) +
                    (f"\n... and {len(imported_files) - 5} more" if len(imported_files) > 5 else ""))
                
            except Exception as e:
                QMessageBox.critical(self.parent, "Import Error", f"Failed to import recordings:\n{str(e)}")
        
        print("File -> Import recording clicked")
    
    def file_send_report_by_email(self):
        """Handle Send report by email menu option"""
        # Get recipient email
        email, ok = QInputDialog.getText(self.parent, "Send Report by Email", 
                                       "Enter recipient email address:", 
                                       QLineEdit.Normal)
        
        if ok and email:
            # Simple email validation
            if "@" not in email or "." not in email:
                QMessageBox.warning(self.parent, "Invalid Email", "Please enter a valid email address.")
                return
            
            # Simulate sending email
            QMessageBox.information(self.parent, "Email Sent", 
                f"Report sent successfully to:\n{email}\n\n"
                f"Note: This is a simulation. In a real application, "
                f"this would integrate with an email service.")
        
        print("File -> Send report by email clicked")
    
    # Edit Menu Functions
    def edit_undo(self):
        """Handle Undo menu option"""
        msg = QMessageBox(self.parent)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Undo Action")
        msg.setText("Undo Last Action")
        msg.setInformativeText("""
        Undo Functionality
        
        Last Actions Available for Undo:
        • Patient data modification
        • Event annotation changes
        • Signal processing adjustments
        • Report generation settings
        
        Undo History:
        1. Added event annotation at 03:45 AM
        2. Modified SpO2 threshold to 88%
        3. Changed time window to 120s
        4. Updated patient information
        
        Undo Options:
        • Undo single action
        • Undo multiple actions
        • Restore to specific time point
        • Clear all recent changes
        
        Current State:
        • 4 actions available for undo
        • Data backup created 5 minutes ago
        • All changes are reversible
        
        Note:
        Undo actions are preserved until the application is closed or a new session is started.
        """)
        msg.exec_()
        print("Edit -> Undo clicked")
    
    def edit_redo(self):
        print("Edit -> Redo clicked")
        # TODO: Implement redo functionality
    
    def edit_copy(self):
        print("Edit -> Copy clicked")
        # TODO: Implement copy functionality
    
    def edit_paste(self):
        print("Edit -> Paste clicked")
        # TODO: Implement paste functionality
    
    # View Menu Functions
    def view_fullscreen(self, checked):
        """Handle Fullscreen menu option"""
        if checked:
            self.parent.showFullScreen()
        else:
            self.parent.showNormal()
        print(f"View -> Fullscreen {'enabled' if checked else 'disabled'}")
    
    def view_report_view(self):
        """Handle Report view menu option"""
        msg = QMessageBox(self.parent)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Report View")
        msg.setText("Sleep Monitoring Report View")
        msg.setInformativeText("""
        Report View
        
        Available Reports:
        • Sleep Quality Summary
        • SpO2 Analysis Report
        • Heart Rate Variability
        • Movement Pattern Analysis
        • Apnea Detection Report
        • Sleep Stage Analysis
        
        Report Features:
        • Interactive charts and graphs
        • Detailed statistical analysis
        • Comparison with previous studies
        • Export to PDF/Excel
        • Email sharing capability
        
        Generate New Report:
        Select a report type and date range to generate a comprehensive analysis.
        """)
        msg.exec_()
        print("View -> Report view clicked")
    
    def view_signal_view(self):
        """Handle Signal view menu option"""
        msg = QMessageBox(self.parent)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Signal View")
        msg.setText("Signal View Configuration")
        msg.setInformativeText("""
        Signal View Options
        
        Available Signals:
        • SpO2 (Oxygen Saturation)
        • Pulse Rate (Heart Rate)
        • Body Movement
        • Airflow Pattern
        • Snoring Detection
        • Thoracic Movement
        • Abdominal Movement
        • Body Position
        
        View Modes:
        • Real-time Monitoring
        • Historical Data View
        • Overlay Comparison
        • Signal Quality Analysis
        • Event Correlation View
        
        Display Options:
        • Time scale adjustment
        • Amplitude scaling
        • Color customization
        • Grid display
        • Annotation tools
        """)
        msg.exec_()
        print("View -> Signal view clicked")
    
    def view_event_list(self):
        """Handle Event list menu option"""
        msg = QMessageBox(self.parent)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Event List")
        msg.setText("Sleep Events List")
        msg.setInformativeText("""
        Detected Sleep Events
        
        Recent Events:
        • 02:30 AM - Apnea Event (Duration: 15s)
        • 03:15 AM - Movement Episode (Duration: 45s)
        • 03:45 AM - SpO2 Drop (Min: 85%)
        • 04:20 AM - Position Change (Supine to Left)
        • 05:10 AM - Snoring Episode (Duration: 2min)
        
        Event Types:
        • Apnea/Hypopnea Events
        • Desaturation Events
        • Movement Episodes
        • Position Changes
        • Snoring Detection
        • Heart Rate Variations
        
        Event Analysis:
        • Total events: 47
        • Severe events: 8
        • Average duration: 23 seconds
        • Most frequent: Position changes (15)
        
        Actions:
        • Export event list
        • Generate event report
        • Filter by event type
        • Annotate events
        """)
        msg.exec_()
        print("View -> Event list clicked")
    
    def view_quick_start(self):
        """Handle Quick start menu option"""
        msg = QMessageBox(self.parent)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Quick Start")
        msg.setText("Sleep Sense Quick Start Guide")
        msg.setInformativeText("""
        Quick Start Guide
        
        Step 1: Patient Setup
        • Enter patient ID and demographics
        • Select study parameters
        • Configure monitoring duration
        • Set alarm thresholds
        
        Step 2: Equipment Check
        • Verify sensor connections
        • Check signal quality
        • Test alarm functionality
        • Calibrate devices
        
        Step 3: Start Monitoring
        • Click "Start Recording" button
        • Monitor real-time signals
        • Verify data acquisition
        • Observe signal quality
        
        Step 4: During Study
        • Monitor for signal issues
        • Document patient events
        • Respond to alarms
        • Maintain equipment
        
        Step 5: Complete Study
        • Stop recording
        • Save data files
        • Generate initial report
        • Backup to secure location
        
        Need Help?
        Press F1 for detailed documentation or contact technical support.
        """)
        msg.exec_()
        print("View -> Quick start clicked")
    
    def view_zoom_in(self):
        print("View -> Zoom In clicked")
        # TODO: Implement zoom in functionality
    
    def view_zoom_out(self):
        print("View -> Zoom Out clicked")
        # TODO: Implement zoom out functionality
    
    def view_reset_zoom(self):
        print("View -> Reset Zoom clicked")
        # TODO: Implement reset zoom functionality
    
    # Tools Menu Functions
    def tools_reanalyze(self):
        """Handle Re-analyze menu option"""
        msg = QMessageBox(self.parent)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Re-analyze Data")
        msg.setText("Sleep Data Re-analysis")
        msg.setInformativeText("""
        <h3>Re-analysis Configuration</h3>
        
        <b>Analysis Options:</b><br>
        • Re-process raw signal data<br>
        • Update event detection thresholds<br>
        • Recalculate sleep stages<br>
        • Refresh statistical analysis<br>
        • Update correlation matrices<br>
        
        <b>Parameters to Re-analyze:</b><br>
        • Apnea detection sensitivity<br>
        • Movement threshold levels<br>
        • SpO2 desaturation criteria<br>
        • Heart rate variability<br>
        • Sleep stage transitions<br>
        
        <b>Output Options:</b><br>
        • Generate new report<br>
        • Compare with previous analysis<br>
        • Highlight changes detected<br>
        • Export updated data<br>
        • Update patient summary<br>
        
        <b>Processing Time:</b><br>
        Estimated time: 3-5 minutes depending on data size
        
        <b>Note:</b><br>
        Original data will be preserved. New analysis will be saved as separate version.
        """)
        msg.exec_()
        print("Tools -> Re-analyze clicked")
    
    def tools_new_event_group(self):
        """Handle New event group menu option"""
        msg = QMessageBox(self.parent)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("New Event Group")
        msg.setText("Create New Event Group")
        msg.setInformativeText("""
        <h3>Event Group Configuration</h3>
        
        <b>Group Type:</b><br>
        • Apnea Events Group<br>
        • Movement Events Group<br>
        • Position Change Group<br>
        • Desaturation Events Group<br>
        • Custom Event Group<br>
        
        <b>Group Properties:</b><br>
        • Group name and description<br>
        • Event type filter<br>
        • Time range selection<br>
        • Severity level filter<br>
        • Color coding scheme<br>
        
        <b>Analysis Options:</b><br>
        • Statistical summary<br>
        • Frequency analysis<br>
        • Duration distribution<br>
        • Correlation with other events<br>
        • Trend analysis<br>
        
        <b>Actions Available:</b><br>
        • Add events to group<br>
        • Remove events from group<br>
        • Merge with existing groups<br>
        • Export group data<br>
        • Generate group report<br>
        
        <b>Usage:</b><br>
        Event groups help organize similar events for better analysis and reporting.
        """)
        msg.exec_()
        print("Tools -> New event group clicked")
    
    def tools_delete_event_group(self):
        """Handle Delete event group menu option"""
        msg = QMessageBox(self.parent)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Delete Event Group")
        msg.setText("Delete Event Group")
        msg.setInformativeText("""
        <h3>Delete Event Group Confirmation</h3>
        
        <b>Available Groups for Deletion:</b><br>
        • Apnea Events Group (47 events)<br>
        • Movement Events Group (23 events)<br>
        • Position Changes Group (15 events)<br>
        • Custom Analysis Group (8 events)<br>
        
        <b>Deletion Effects:</b><br>
        • All events in group will be ungrouped<br>
        • Individual events will remain in database<br>
        • Group analysis will be lost<br>
        • Related reports will be updated<br>
        
        <b>Recovery Options:</b><br>
        • Undo deletion within 24 hours<br>
        • Restore from backup<br>
        • Re-create group manually<br>
        
        <b>Warning:</b><br>
        This action cannot be undone after 24 hours. Consider exporting group data before deletion.
        """)
        msg.exec_()
        print("Tools -> Delete event group clicked")
    
    def tools_edit_event_group(self):
        """Handle Edit event group menu option"""
        msg = QMessageBox(self.parent)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Edit Event Group")
        msg.setText("Edit Event Group")
        msg.setInformativeText("""
        <h3>Edit Event Group Properties</h3>
        
        <b>Select Group to Edit:</b><br>
        • Apnea Events Group<br>
        • Movement Events Group<br>
        • Position Changes Group<br>
        • Custom Analysis Group<br>
        
        <b>Editable Properties:</b><br>
        • Group name and description<br>
        • Event inclusion criteria<br>
        • Filter parameters<br>
        • Color scheme<br>
        • Analysis settings<br>
        
        <b>Modification Options:</b><br>
        • Add/remove events from group<br>
        • Change group classification<br>
        • Update analysis parameters<br>
        • Modify display settings<br>
        • Export modified group<br>
        
        <b>Validation:</b><br>
        • Check event consistency<br>
        • Verify time continuity<br>
        • Validate medical criteria<br>
        • Ensure data integrity<br>
        
        <b>Save Options:</b><br>
        • Save as new version<br>
        • Replace existing group<br>
        • Create backup before changes<br>
        """)
        msg.exec_()
        print("Tools -> Edit event group clicked")
    
    def tools_settings(self):
        """Handle Settings menu option"""
        print("Tools -> Settings clicked")
        # TODO: Implement settings dialog
    
    def tools_send_event_log_by_email(self):
        """Handle Send Event Log by email menu option"""
        print("Tools -> Send Event Log by email clicked")
        # TODO: Implement send event log by email functionality
    
    def tools_database_transfer(self):
        """Handle Database Transfer menu option"""
        print("Tools -> Database Transfer clicked")
        # TODO: Implement database transfer functionality
    
    def tools_import_data(self):
        print("Tools -> Import Data clicked")
        # TODO: Implement data import functionality
    
    def tools_data_analysis(self):
        print("Tools -> Data Analysis clicked")
        # TODO: Implement data analysis tools
    
    def tools_generate_report(self):
        print("Tools -> Generate Report clicked")
        # TODO: Implement report generation
    
    # Help Menu Functions
    def help_clinical_guide(self):
        """Handle Clinical Guide menu option"""
        msg = QMessageBox(self.parent)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Clinical Guide")
        msg.setText("Sleep Monitoring Clinical Guide")
        msg.setInformativeText("""
        <h3>Clinical Guidelines for Sleep Monitoring</h3>
        
        <b>Normal Sleep Patterns:</b><br>
        • Adults: 7-9 hours per night<br>
        • Regular sleep schedule recommended<br>
        • Consistent bedtime and wake time
        
        <b>Common Sleep Disorders:</b><br>
        • Sleep Apnea: Pauses in breathing during sleep<br>
        • Insomnia: Difficulty falling or staying asleep<br>
        • Narcolepsy: Excessive daytime sleepiness<br>
        • Restless Leg Syndrome: Uncomfortable leg sensations
        
        <b>Monitoring Parameters:</b><br>
        • SpO2: Oxygen saturation (Normal: 95-100%)<br>
        • Pulse Rate: Heart rate (Normal: 60-100 bpm)<br>
        • Body Movement: Sleep quality indicator<br>
        • Airflow: Breathing patterns
        
        <b>When to Refer:</b><br>
        • SpO2 consistently below 90%<br>
        • Irregular breathing patterns<br>
        • Excessive movement during sleep<br>
        • Daytime sleepiness affecting daily life
        """)
        msg.exec_()
        print("Help -> Clinical Guide clicked")
    
    def help_patient_instructions(self):
        """Handle Patient instructions menu option"""
        msg = QMessageBox(self.parent)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Patient Instructions")
        msg.setText("Sleep Study Instructions for Patients")
        msg.setInformativeText("""
        <h3>Before Your Sleep Study</h3>
        
        <b>Preparation:</b><br>
        • Avoid caffeine for 12 hours before study<br>
        • No alcohol for 24 hours before study<br>
        • Take regular medications unless advised otherwise<br>
        • Shower and avoid lotions/perfumes<br>
        • Bring comfortable sleepwear
        
        <b>During the Study:</b><br>
        • Relax and sleep as naturally as possible<br>
        • Inform staff if you need assistance<br>
        • Try to minimize movement<br>
        • Use the restroom before sensors are attached
        
        <b>What to Expect:</b><br>
        • Small sensors will be attached to your body<br>
        • Elastic bands around chest and abdomen<br>
        • Finger probe for oxygen monitoring<br>
        • No needles or painful procedures<br>
        • You can sleep in any comfortable position
        
        <b>After the Study:</b><br>
        • Results available in 3-5 business days<br>
        • Follow-up appointment with your doctor<br>
        • Continue any prescribed treatments<br>
        • Call with any questions or concerns
        """)
        msg.exec_()
        print("Help -> Patient instructions clicked")
    
    def help_program_info(self):
        """Handle Program info menu option"""
        msg = QMessageBox(self.parent)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Program Information")
        msg.setText("Sleep Sense Monitoring Program")
        msg.setInformativeText("""
        <h3>Sleep Sense - Medical Sleep Monitoring System</h3>
        
        <b>Version:</b> 1.0.0<br>
        <b>Release Date:</b> April 2026<br>
        <b>Developer:</b> Medical Sleep Solutions<br>
        
        <b>Program Features:</b><br>
        • Real-time sleep monitoring<br>
        • Multi-parameter signal analysis<br>
        • Clinical report generation<br>
        • Patient data management<br>
        • Export capabilities<br>
        • Email integration
        
        <b>System Requirements:</b><br>
        • Operating System: Windows/macOS/Linux<br>
        • Memory: 4GB RAM minimum<br>
        • Storage: 500MB available space<br>
        • Display: 1024x768 resolution minimum
        
        <b>Technical Support:</b><br>
        • Email: support@sleepsense.medical<br>
        • Phone: 1-800-SLEEP-HELP<br>
        • Online: www.sleepsense.medical/support
        
        <b>Licensing:</b><br>
        • Medical use license required<br>
        • Annual subscription available<br>
        • Training included with license<br>
        • Technical support included
        """)
        msg.exec_()
        print("Help -> Program info clicked")
    
    def help_recording_info(self):
        """Handle Recording info menu option"""
        msg = QMessageBox(self.parent)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Recording Information")
        msg.setText("Recording Information - Currently Unavailable")
        msg.setInformativeText("""
        <h3>Recording Information</h3>
        
        This feature is currently under development and will be available in a future update.
        
        <b>Coming Soon:</b><br>
        • Detailed recording specifications<br>
        • Data format information<br>
        • Recording quality guidelines<br>
        • Troubleshooting guide<br>
        • Best practices documentation
        
        For immediate assistance with recording-related questions, please contact technical support.
        """)
        msg.exec_()
        print("Help -> Recording info clicked")
    
    def help_device_info(self):
        """Handle Device info menu option"""
        msg = QMessageBox(self.parent)
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Device Information")
        msg.setText("Device Information - Currently Unavailable")
        msg.setInformativeText("""
        <h3>Device Information</h3>
        
        This feature is currently under development and will be available in a future update.
        
        <b>Coming Soon:</b><br>
        • Connected device status<br>
        • Device specifications<br>
        • Compatibility information<br>
        • Calibration procedures<br>
        • Maintenance guidelines
        
        For immediate assistance with device-related questions, please contact technical support.
        """)
        msg.exec_()
        print("Help -> Device info clicked")
    
    def help_documentation(self):
        print("Help -> Documentation clicked")
        # TODO: Open documentation
    
    def help_about(self):
        print("Help -> About clicked")
        # TODO: Show about dialog
    
    # Additional File Menu Functions
    def file_new(self):
        print("File -> New clicked")
        # TODO: Implement new session functionality
    
    def file_open(self):
        print("File -> Open clicked")
        # TODO: Implement file open functionality
    
    def file_save(self):
        print("File -> Save clicked")
        # TODO: Implement file save functionality
