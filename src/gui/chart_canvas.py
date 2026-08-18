#让 matplotlib 图表自适应控件尺寸、填满可用空间。
#
#旧的 FixedAspectCanvas 会在 resize 时用 setFixedHeight() 按宽高比锁死高度，
#一旦容器给的空间比这个高度小，图表底部就会被裁切（遮挡）。这里改成：
#   1. 尺寸策略设为 Expanding，让控件跟随容器伸缩；
#   2. 不锁高度，figure 的缩放交给 matplotlib 的 FigureCanvasQTAgg 基类
#      （它内部用「事件尺寸 × device_pixel_ratio」正确适配高分屏）。
#
#关键：重写 sizeHint() 返回一个固定值，切断「figure 尺寸变化 → sizeHint 变化
#→ Qt 布局再次 resize → 再改 figure 尺寸」的反馈循环。否则在 constrained_layout
#图形 + 高分屏下会出现图表越拉越长、甚至递归栈溢出的问题。
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtCore import QSize
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas


class AdaptiveCanvas(FigureCanvas):

    def __init__(self, fig, min_height: int = 240):
        super().__init__(fig)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(min_height)
        self.setMinimumWidth(320)

    def sizeHint(self):
        # 固定返回值，避免 sizeHint 跟随 figure 尺寸变化而触发布局反馈循环。
        return QSize(800, 480)
