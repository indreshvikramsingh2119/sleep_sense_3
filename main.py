"""
Main Entry Point - Sleep Sense Dashboard Application
Medical Grade PyQt5 Sleep Monitoring System
"""

import sys     
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFont 
from PyQt5.QtCore import Qt

from db_utils import init_db
from src.components.dashboard import SleepSenseDashboard
   
def main():

    """Main function to run the Sleep Sense Dashboard application"""
    # Set Qt attributes for WebEngine support before importing WebEngine widgets
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts) 

    init_db()

    app = QApplication(sys.argv)
    app.setApplicationName("Sleep Sense")

    # Set default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = SleepSenseDashboard()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
