# 让 matplotlib 图表跟随容器尺寸缩放，始终填满可用空间，避免在窄窗口 / Windows 下被裁切。
from PySide6.QtWidgets import QSizePolicy
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas


class AdaptiveCanvas(FigureCanvas):

    def __init__(self, fig, min_height: int = 200):
        super().__init__(fig)
        self._min_height = min_height
        self._last_w = -1
        self._last_h = -1
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(min_height)
        self.setMinimumWidth(320)

    def resizeEvent(self, event):
        # 先交给父类，让 Qt 把新尺寸写入控件，再同步 figure 尺寸。
        super().resizeEvent(event)
        self._sync_figure_size()

    def _sync_figure_size(self):
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return
        # 尺寸变化小于阈值就跳过：拖拽窗口时 Qt 会连发大量只差 1~2 像素的
        # resize 事件，逐个完整重绘既卡顿也无必要；只有实际变了才重绘。
        if abs(w - self._last_w) < 8 and abs(h - self._last_h) < 8:
            return
        self._last_w, self._last_h = w, h
        dpi = self.figure.get_dpi()
        self.figure.set_size_inches(w / dpi, h / dpi)
        self.draw_idle()
