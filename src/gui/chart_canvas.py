#让 matplotlib 图表跟随容器尺寸缩放，始终填满可用空间，避免在窄窗口 / Windows 下被裁切。
from PySide6.QtWidgets import QSizePolicy
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas


class AdaptiveCanvas(FigureCanvas):

    def __init__(self, fig, min_height: int = 200):
        super().__init__(fig)
        self._min_height = min_height
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(min_height)
        self.setMinimumWidth(320)

    def resizeEvent(self, event):
        # 控件尺寸变化时，按当前像素尺寸反推 figure 的英寸大小，
        # 让图表（含坐标轴标签、图例）重新排版填满空间，不再被遮挡。
        super().resizeEvent(event)
        w = self.width()
        h = self.height()
        if w > 0 and h > 0:
            dpi = self.figure.get_dpi()
            self.figure.set_size_inches(w / dpi, h / dpi)
            self.draw_idle()
