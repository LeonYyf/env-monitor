from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QStackedWidget,
    QLabel, QStatusBar, QMessageBox,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon

from .styles import GLOBAL_STYLESHEET, COLORS
from .pages.page_import import ImportPage
from .pages.page_cleaning import CleaningPage
from .pages.page_eda import EDAPage
from .pages.page_reporting import ReportingPage
from src.data_store import data_store

# 阶段列表（名称 + 状态栏说明）
STAGES = [
    ("数据导入", "将 Excel 表格导入数据库"),
    ("数据清洗", "缺失值 / 异常值 / 时间格式 / 去重"),
    ("探索分析", "统计描述 + 可视化图表"),
    ("结果报告", "汇总表 + 业务解读 + 导出"),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("环境监测数据分析系统 — 实验室 & 生产车间")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 680)

        # 步骤 i < completed_count  → 已完成
        # 步骤 i == completed_count → 当前可做
        # 步骤 i > completed_count → 未解锁
        self.completed_count = 0

        self.setStyleSheet(GLOBAL_STYLESHEET)

        self._build_sidebar()
        self._build_pages()
        self._build_statusbar()

        self.sidebar.setCurrentRow(0)
        self._refresh_sidebar()

    def _build_sidebar(self):
        #构建左侧导航栏
        self.sidebar = QListWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(220)
        self.sidebar.setIconSize(QSize(24, 24))
        self.sidebar.setSpacing(4)

        for i, (name, _) in enumerate(STAGES):
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, i)
            item.setSizeHint(QSize(200, 52))
            self.sidebar.addItem(item)

        self.sidebar.currentRowChanged.connect(self._on_page_changed)

        # 侧边栏顶部标题
        sidebar_widget = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        title_label = QLabel("环境监测")
        title_label.setStyleSheet(
            f"font-size: 18px; font-weight: bold; color: {COLORS['text_on_dark']}; "
            f"padding: 20px 16px 0px 16px; background-color: {COLORS['sidebar_bg']}; border: none;"
        )
        sidebar_layout.addWidget(title_label)

        subtitle_label = QLabel("数据分析系统")
        subtitle_label.setStyleSheet(
            f"font-size: 12px; color: {COLORS['sidebar_text_muted']}; "
            f"padding: 2px 16px 16px 16px; background-color: {COLORS['sidebar_bg']}; border: none;"
        )
        sidebar_layout.addWidget(subtitle_label)
        sidebar_layout.addWidget(self.sidebar)

        # 底部版本信息
        version_label = QLabel("v1.0.0")
        version_label.setStyleSheet(
            f"color: {COLORS['sidebar_text_muted']}; font-size: 11px; padding: 12px; "
            f"background-color: {COLORS['sidebar_bg']}; border: none;"
        )
        version_label.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(version_label)

        self.sidebar_container = sidebar_widget

    def mark_step_completed(self, step_index: int):
        #标记某一步骤完成，解锁下一步并刷新侧边栏状态
        if step_index >= self.completed_count:
            self.completed_count = step_index + 1
            self._refresh_sidebar()

    def reset_progress(self):
        #清空进度
        self.reset_downstream()
        self.set_status("数据库已清空，请重新导入数据")

    def reset_downstream(self):
        #导入新文件前重置下游页面缓存
        data_store.reset()
        self.completed_count = 0
        self._refresh_sidebar()
        for page in self.pages[1:]:
            if hasattr(page, "reset"):
                page.reset()

    def _refresh_sidebar(self):
        #根据 completed_count 更新侧边栏：已完成（✓）/ 当前 / 未解锁（置灰禁点）
        for i in range(self.sidebar.count()):
            item = self.sidebar.item(i)
            name = STAGES[i][0]
            if i < self.completed_count:
                item.setText(f"✓  {name}")
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            elif i == self.completed_count:
                item.setText(name)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            else:
                item.setText(name)
                item.setFlags(Qt.NoItemFlags)

    # 右侧内容区
    def _build_pages(self):
        #构建4个页面
        self.stack = QStackedWidget()
        self.stack.setObjectName("pageStack")

        self.pages = [
            ImportPage(),
            CleaningPage(),
            EDAPage(),
            ReportingPage(),
        ]

        for page in self.pages:
            self.stack.addWidget(page)

        # 将页面与主窗口关联
        for page in self.pages:
            page.main_window = self

        # 切换页面时，自动让目标页从共享内存加载数据（幂等）
        self.stack.currentChanged.connect(self._on_stack_current_changed)

        # 主布局
        central = QWidget()
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.sidebar_container)
        main_layout.addWidget(self.stack, 1)

        self.setCentralWidget(central)

    def _build_statusbar(self):
        #底部状态栏
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪")
        self.setStatusBar(self.status_bar)

    # 页面切换
    def _on_page_changed(self, index: int):
        #侧边栏点击切换页面
        if 0 <= index < len(self.pages):
            self.stack.setCurrentIndex(index)
            step = index + 1
            self.status_bar.showMessage(f"步骤 {step}/{len(STAGES)} · {STAGES[index][0]}")

    def switch_to_page(self, index: int):
        #外部切换到指定页面
        self.sidebar.setCurrentRow(index)
        self.stack.setCurrentIndex(index)

    def _on_stack_current_changed(self, index: int):
        #进入某页时自动从共享内存加载数据（无该方法的页面跳过）
        if 0 <= index < len(self.pages):
            page = self.pages[index]
            if hasattr(page, "load_from_store"):
                page.load_from_store()

    def show_message(self, title: str, message: str, msg_type: str = "info"):
        #弹出提示对话框
        if msg_type == "error":
            QMessageBox.critical(self, title, message)
        elif msg_type == "warning":
            QMessageBox.warning(self, title, message)
        else:
            QMessageBox.information(self, title, message)

    def set_status(self, message: str):
        #更新状态栏消息
        self.status_bar.showMessage(message)
