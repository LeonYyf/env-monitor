import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from src.gui.main_window import MainWindow
from src.gui.feedback import ButtonFeedback


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("环境监测数据分析系统")
    app.setOrganizationName("EnvMonitor")

    font = QFont("PingFang SC", 13)
    app.setFont(font)

    ButtonFeedback(app).install()

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
