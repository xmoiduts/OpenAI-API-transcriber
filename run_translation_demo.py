import sys
import os

# 确保可以导入src模块
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from PyQt5.QtWidgets import QApplication
from src.gui.line_translation_tab_demo import LineTranslationDemo

if __name__ == "__main__":
    app = QApplication(sys.argv)
    demo = LineTranslationDemo()
    demo.show()
    sys.exit(app.exec_()) 