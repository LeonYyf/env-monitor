import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from src.gui.main_window import MainWindow
from src.gui.feedback import ButtonFeedback


def main():
    # Windows 高分屏：按真实缩放比例渲染（不取整），让 matplotlib 图表与窗口
    # 缩放口径一致、不模糊也不被裁切；macOS 默认已启用高分屏，此设置两边都安全。
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
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
