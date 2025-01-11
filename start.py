import os
import sys
from PyQt5.QtWidgets import QApplication
from src.gui.main_window import MainWindow
import src.resources_rc

if __name__ == "__main__":
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    os.environ['PROJECT_ROOT'] = PROJECT_ROOT
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
