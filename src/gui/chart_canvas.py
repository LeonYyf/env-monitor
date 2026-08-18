#让 matplotlib 图表在 Qt 中保持原始宽高比，避免被垂直拉伸变形。
from PySide6.QtWidgets import QSizePolicy
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas


class FixedAspectCanvas(FigureCanvas):

    def __init__(self, fig, min_height: int = 200):
        super().__init__(fig)
        w = float(fig.get_figwidth())
        h = float(fig.get_figheight())
        self._aspect = w / h if h > 0 else 1.6
        self._min_height = min_height
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(min_height)

    def resizeEvent(self, event):
        #按宽度锁定高度，保持宽高比，避免图表被垂直拉伸
        width = event.size().width()
        if width > 0:
            target_h = max(int(round(width / self._aspect)), self._min_height)
            if target_h != self.height():
                self.setFixedHeight(target_h)
        super().resizeEvent(event)
