import os
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from src.gui.main_window import MainWindow
import src.resources_rc

if __name__ == "__main__":
    # Enable High DPI scaling
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    os.environ['PROJECT_ROOT'] = PROJECT_ROOT
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
