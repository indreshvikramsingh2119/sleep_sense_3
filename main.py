"""
Main Entry Point - Sleep Sense Dashboard Application
Medical Grade PyQt5 Sleep Monitoring System
"""

import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont

from src.components.dashboard import SleepSenseDashboard


def main():
    """Main function to run the Sleep Sense Dashboard application"""
    app = QApplication(sys.argv)
    app.setApplicationName("Sleep Sense")
    
    # Set default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    # Create and show the main dashboard window
    window = SleepSenseDashboard()
    window.show()
    
    # Start the application event loop
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()        
  