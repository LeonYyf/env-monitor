from PySide6.QtCore import QObject, QEvent, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtWidgets import QPushButton


# 可调参数
_GROW_FACTOR = 1.06        # 悬停放大倍数
_GROW_MS = 150             # 放大/缩回动画时长


class ButtonFeedback(QObject):

    def __init__(self, app):
        super().__init__(app)
        self._app = app
        self._anims = {} 
        self._base = {}
        self._tracked = set()

    def install(self):
        self._app.installEventFilter(self)

    def eventFilter(self, obj, event):
        if isinstance(obj, QPushButton) and obj.isEnabled() and obj.isVisible():
            t = event.type()
            if t == QEvent.Enter:
                self._grow(obj)
            elif t == QEvent.Leave:
                self._shrink(obj)
        return False

    # 放大 / 缩回
    def _grow(self, btn):
        g = btn.geometry()
        if g.width() <= 0 or g.height() <= 0:
            return 
        wid = id(btn)
        if wid not in self._base:
            self._base[wid] = g
        self._animate(btn, self._scaled(self._base[wid], _GROW_FACTOR), _GROW_MS)

    def _shrink(self, btn):
        base = self._base.pop(id(btn), None)
        if base is None:
            return
        self._animate(btn, base, _GROW_MS)

    @staticmethod
    def _scaled(rect: QRect, factor: float) -> QRect:
        w = int(rect.width() * factor)
        h = int(rect.height() * factor)
        x = rect.x() - (w - rect.width()) // 2
        y = rect.y() - (h - rect.height()) // 2
        return QRect(x, y, w, h)

    def _animate(self, btn, end_rect, ms):
        anim = QPropertyAnimation(btn, b"geometry", self)
        anim.setDuration(ms)
        anim.setStartValue(btn.geometry())
        anim.setEndValue(end_rect)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        self._start(btn, anim)

    def _start(self, btn, anim):
        wid = id(btn)
        old = self._anims.get(wid)
        if old is not None:
            try:
                old.stop()
            except RuntimeError:
                pass
        self._anims[wid] = anim
        anim.start()
        self._track(btn)

    def _track(self, btn):
        wid = id(btn)
        if wid in self._tracked:
            return
        self._tracked.add(wid)
        btn.destroyed.connect(lambda _=None, w=wid: self._forget(w))

    def _forget(self, wid):
        anim = self._anims.pop(wid, None)
        if anim is not None:
            try:
                anim.stop()
                anim.setTargetObject(None)
            except RuntimeError:
                pass
            anim.deleteLater()
        self._base.pop(wid, None)
        self._tracked.discard(wid)
