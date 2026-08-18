import os
from collections import Counter

import pandas as pd
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QTableWidget, QTableWidgetItem, QTabWidget,
    QProgressBar, QMessageBox, QHeaderView, QFrame, QStackedWidget,
    QScrollArea, QDialog, QLineEdit,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent

from src.etl.excel_reader import ExcelReader
from src.etl.importer import Importer
from src.database.repository import Repository


def human_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    elif n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    else:
        return f"{n / 1024 ** 2:.2f} MB"


class DropZone(QFrame):
    file_dropped = Signal(list)     #选中文件后发出路径列表
    clear_requested = Signal()      #点击「清除文件」时发出

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(300)   #空态时撑得醒目一些；选中文件后会收缩
        self._build_ui()

    # 构建界面
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 14, 20, 20)
        outer.setSpacing(8)

        #顶部行：右侧「清除文件」按钮（选中文件后才显示）
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addStretch(1)
        self.clear_btn = QPushButton("清除文件")
        self.clear_btn.setObjectName("secondaryBtn")
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.setVisible(False)
        self.clear_btn.clicked.connect(lambda *_: self.clear_requested.emit())
        top.addWidget(self.clear_btn)
        outer.addLayout(top)

        #内容区（空态 / 已选态 切换）
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_empty())
        self.stack.addWidget(self._build_filled())
        outer.addWidget(self.stack, 1)

    def _build_empty(self):
        #空态：提示 + 浏览按钮（居中）
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignCenter)

        hint = QLabel("拖拽 Excel 文件到这里")
        hint.setObjectName("dropHint")
        hint.setAlignment(Qt.AlignCenter)

        sub = QLabel("可一次拖入多个文件，或点击下方按钮选择（支持 .xlsx / .xls）")
        sub.setObjectName("dropSubHint")
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)

        browse_btn = QPushButton("浏览文件")
        browse_btn.setObjectName("secondaryBtn")
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.clicked.connect(self._on_browse)

        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignCenter)
        btn_row.addWidget(browse_btn)

        layout.addStretch(1)
        layout.addWidget(hint)
        layout.addWidget(sub)
        layout.addSpacing(8)
        layout.addLayout(btn_row)
        layout.addStretch(1)
        return page

    def _build_filled(self):
        #已选态：文件信息列表（名称 / 大小 / Sheet）
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        self.file_name_label = QLabel("")
        self.file_name_label.setObjectName("fileNameLabel")

        self.file_meta_label = QLabel("")
        self.file_meta_label.setObjectName("fileMetaLabel")

        self.sheet_summary_label = QLabel("")
        self.sheet_summary_label.setObjectName("sheetSummaryLabel")
        self.sheet_summary_label.setWordWrap(True)

        layout.addWidget(self.file_name_label)
        layout.addWidget(self.file_meta_label)
        layout.addSpacing(8)
        layout.addWidget(self.sheet_summary_label)
        layout.addStretch(1)
        return page

    # 浏览按钮（支持多选）
    def _on_browse(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择 Excel 文件（可多选）", "",
            "Excel 文件 (*.xlsx *.xls);;所有文件 (*)"
        )
        if paths:
            self.file_dropped.emit(paths)

    # 对外接口
    def show_files_info(self, files):
        #填入文件信息并切到「已选态」。files = [(file_path, [(sheet, count), ...])]
        n = len(files)
        total_rows = sum(cnt for _, summaries in files for _, cnt in summaries)
        total_sheets = sum(len(s) for _, s in files)

        if n == 1:
            path, summaries = files[0]
            self.file_name_label.setText(os.path.basename(path))
            self.file_meta_label.setText(f"文件大小：{human_size(os.path.getsize(path))}")
            lines = [f"• {sn} — {cnt} 条" for sn, cnt in summaries]
            self.sheet_summary_label.setText(
                f"识别到 {len(summaries)} 个 Sheet：\n" + "\n".join(lines)
            )
        else:
            self.file_name_label.setText(f"已加载 {n} 个文件")
            self.file_meta_label.setText(f"共 {total_sheets} 个 Sheet · 共 {total_rows} 条记录")
            lines = []
            for path, summaries in files:
                name = os.path.basename(path)
                size = human_size(os.path.getsize(path))
                if summaries:
                    sheet_str = "、".join(f"{sn}（{cnt} 条）" for sn, cnt in summaries)
                    lines.append(f"• {name}（{size}）— {sheet_str}")
                else:
                    lines.append(f"• {name}（{size}）— 无数据")
            self.sheet_summary_label.setText("\n".join(lines))

        #选中文件后，上传区收缩到内容高度，把空间让给下方预览
        self.setMinimumHeight(0)
        cap = min(220 + (n - 1) * 90, 520)
        self.setMaximumHeight(cap)
        self.stack.setCurrentIndex(1)
        self.clear_btn.setVisible(True)

    def reset_to_empty(self):
        """撤回已选文件，恢复到初始的空态"""
        self.stack.setCurrentIndex(0)
        self.setMinimumHeight(300)
        self.setMaximumHeight(16777215)   #恢复默认最大高度
        self.clear_btn.setVisible(False)

    # 拖放事件（支持一次拖入多个文件）
    def _set_dragging(self, dragging: bool):
        #切换拖拽高亮
        self.setProperty("dragging", dragging)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_dragging(True)

    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self._set_dragging(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent):
        self._set_dragging(False)
        paths = []
        for url in event.mimeData().urls():
            p = url.toLocalFile()
            if p and p.lower().endswith((".xlsx", ".xls", ".csv")):
                paths.append(p)
        if paths:
            self.file_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()


class ImportWorker(QThread):
    #后台导入线程：把已解析的数据写入数据库
    progress_signal = Signal(int, str)
    finished_signal = Signal(bool, str)

    def __init__(self, parsed_files):
        super().__init__()
        #parsed_files = [(file_path, {sheet_name: long_format_df}), ...]
        self.parsed_files = parsed_files

    def run(self):
        try:
            n = len(self.parsed_files)
            per_file_results = {}

            for idx, (file_path, sheets_data) in enumerate(self.parsed_files):
                base = os.path.basename(file_path)
                self.progress_signal.emit(int(idx / n * 100), f"正在写入 {base}...")

                def cb(pct, msg, _idx=idx, _n=n):
                    global_pct = int((_idx + pct / 100) / _n * 100)
                    self.progress_signal.emit(global_pct, msg)

                importer = Importer(progress_callback=cb)
                per_file_results[base] = importer.import_all_sheets(sheets_data, file_path)

            #汇总
            total = sum(sum(v.values()) for v in per_file_results.values())
            lines = []
            for base, results in per_file_results.items():
                for sheet, count in results.items():
                    lines.append(f"  • {base} / {sheet}: {count} 条")
            details = "\n".join(lines)

            self.progress_signal.emit(100, "导入完成")
            self.finished_signal.emit(True, f"导入完成！共 {total} 条记录\n{details}")
        except Exception as e:
            self.finished_signal.emit(False, f"导入失败：{e}")


class ImportPage(QWidget):
    def __init__(self):
        super().__init__()
        self.parsed_files = []     #[(file_path, {sheet_name: long_format_df})]
        self._imported = False     #当前这批文件是否已导入成功
        self._build_ui()

    #构建界面
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 20)
        layout.setSpacing(12)

        #头部：只有标题，操作按钮已各自归位
        header = QHBoxLayout()
        title = QLabel("数据导入")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch(1)
        layout.addLayout(header)

        desc = QLabel("把洁净车间环境监测 Excel 文件拖进来（可一次多个），系统会自动识别「尘埃粒子」和「风量」Sheet。")
        desc.setObjectName("pageDescription")
        layout.addWidget(desc)

        #中间内容区：放进滚动区，内容再多也能滚，不会被顶出屏幕
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 8, 0)   # 右边留 8px 给滚动条
        content_layout.setSpacing(16)

        #拖拽上传区（右上角内嵌「清除文件」按钮）
        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self._on_files_selected)
        self.drop_zone.clear_requested.connect(self._on_clear_files)
        content_layout.addWidget(self.drop_zone)

        #导入进度区
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setVisible(False)
        content_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        content_layout.addWidget(self.progress_bar)

        #导入概览卡片（导入成功后显示）
        self.overview_card = self._build_overview_card()
        self.overview_card.setVisible(False)
        content_layout.addWidget(self.overview_card)

        # 预览区（选中文件后显示）
        self.sheet_tabs = QTabWidget()
        self.sheet_tabs.setVisible(False)
        self.sheet_tabs.setMinimumHeight(280)   # 给预览一个可用高度
        content_layout.addWidget(self.sheet_tabs)

        content_layout.addStretch(1)   # 内容顶到顶部，下方留白
        self.scroll.setWidget(content)
        layout.addWidget(self.scroll, 1)

        #底部操作栏：两个按钮同一行，水平并排
        #「清空数据库」在左侧（危险操作，弱化）；「导入到数据库」在右侧（主操作，醒目）
        self.clear_db_btn = QPushButton("清空数据库")
        self.clear_db_btn.setObjectName("dangerBtn")
        self.clear_db_btn.setCursor(Qt.PointingHandCursor)
        self.clear_db_btn.setToolTip("删除数据库中的全部测量数据（不可恢复）")
        self.clear_db_btn.clicked.connect(self._on_clear_database)

        self.import_btn = QPushButton("导入到数据库")
        self.import_btn.setObjectName("primaryBtn")
        self.import_btn.setCursor(Qt.PointingHandCursor)
        self.import_btn.setMinimumWidth(220)
        self.import_btn.setMinimumHeight(44)
        self.import_btn.clicked.connect(self._start_import)

        action_row = QHBoxLayout()
        action_row.addWidget(self.clear_db_btn)
        action_row.addStretch(1)
        action_row.addWidget(self.import_btn)
        layout.addLayout(action_row)
        self._set_import_state("idle")

    # 概览卡片
    def _build_overview_card(self):
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        title = QLabel("导入概览")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        tiles = QHBoxLayout()
        tiles.setSpacing(32)

        self.stat_total_value = QLabel("—")
        self.stat_rooms_value = QLabel("—")
        self.stat_indicators_value = QLabel("—")
        for v in (self.stat_total_value, self.stat_rooms_value, self.stat_indicators_value):
            v.setObjectName("statValue")

        tiles.addWidget(self._make_stat_tile(self.stat_total_value, "总记录数"))
        tiles.addWidget(self._make_stat_tile(self.stat_rooms_value, "房间数"))
        tiles.addWidget(self._make_stat_tile(self.stat_indicators_value, "指标数"))
        tiles.addStretch(1)
        layout.addLayout(tiles)

        self.stat_date = QLabel("")
        self.stat_date.setObjectName("fileMetaLabel")
        layout.addWidget(self.stat_date)

        return card

    def _make_stat_tile(self, value_label, label_text):
        #一个统计块：上面大数字，下面小标签
        tile = QWidget()
        v = QVBoxLayout(tile)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        label = QLabel(label_text)
        label.setObjectName("statLabel")
        v.addWidget(value_label)
        v.addWidget(label)
        return tile

    def _compute_overview(self):
        #从已解析的数据汇总出概览指标
        dfs = [df for _, sheets in self.parsed_files for df in sheets.values() if not df.empty]
        if not dfs:
            return None
        combined = pd.concat(dfs, ignore_index=True)
        dmin = combined["record_date"].min()
        dmax = combined["record_date"].max()
        dmin_s = dmin.strftime("%Y-%m-%d") if hasattr(dmin, "strftime") else str(dmin)
        dmax_s = dmax.strftime("%Y-%m-%d") if hasattr(dmax, "strftime") else str(dmax)
        return {
            "total": len(combined),
            "rooms": combined["room_name"].nunique(),
            "indicators": combined["indicator_name"].nunique(),
            "date_min": dmin_s,
            "date_max": dmax_s,
        }

    def _populate_overview(self):
        overview = self._compute_overview()
        if overview is None:
            return
        self.stat_total_value.setText(f"{overview['total']:,} 条")
        self.stat_rooms_value.setText(str(overview["rooms"]))
        self.stat_indicators_value.setText(str(overview["indicators"]))
        self.stat_date.setText(f"日期范围：{overview['date_min']} ~ {overview['date_max']}")
        self.overview_card.setVisible(True)

    #文件选中（拖入 / 浏览共用，支持多文件）
    def _set_import_state(self, state: str):
        #切换「导入到数据库」按钮的状态。
        texts = {
            "idle": "导入到数据库",
            "ready": "导入到数据库",
            "working": "正在导入...",
            "done": "✓ 已导入",
        }
        self.import_btn.setProperty("state", state)
        self.import_btn.setText(texts[state])
        self.import_btn.setEnabled(state in ("ready", "done"))
        self.import_btn.style().unpolish(self.import_btn)
        self.import_btn.style().polish(self.import_btn)

    def _confirm_clear_database(self, n: int) -> bool:
        #强确认：要求输入「清空」二字才允许执行。返回是否确认。
        dlg = QDialog(self)
        dlg.setWindowTitle("清空数据库")
        dlg.setModal(True)
        dlg.setMinimumWidth(420)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        msg = QLabel(
            "确定要清空全部数据库记录？\n"
            f"该操作不可恢复，将删除 measurement_records 中的全部 {n:,} 条测量记录。"
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        hint = QLabel("请在下方输入「清空」以确认：")
        hint.setObjectName("fileMetaLabel")
        layout.addWidget(hint)

        edit = QLineEdit()
        edit.setPlaceholderText("输入「清空」")
        layout.addWidget(edit)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel = QPushButton("取消")
        cancel.setObjectName("secondaryBtn")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(cancel)

        ok = QPushButton("确认清空")
        ok.setObjectName("dangerBtn")
        ok.setCursor(Qt.PointingHandCursor)
        ok.setEnabled(False)
        ok.clicked.connect(dlg.accept)
        btn_row.addWidget(ok)
        layout.addLayout(btn_row)

        def on_text(text: str):
            ok.setEnabled(text.strip() == "清空")
        edit.textChanged.connect(on_text)

        return dlg.exec() == QDialog.Accepted

    def _on_clear_database(self):
        #清空数据库中的测量数据
        try:
            n = Repository.count_measurements()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法读取数据库：{e}")
            return

        if n == 0:
            QMessageBox.information(self, "提示", "数据库中的测量数据已经是空的，无需清空。")
            return

        if not self._confirm_clear_database(n):
            return

        try:
            Repository.clear_measurements()
        except Exception as e:
            QMessageBox.critical(self, "清空失败", f"清空测量数据时出错：{e}")
            return

        #重置本页状态（撤回已选文件、导入按钮回到 idle、隐藏概览）
        self._on_clear_files()
        #重置主窗口进度（所有步骤回到未完成）
        if hasattr(self, "main_window") and self.main_window:
            self.main_window.reset_progress()

        QMessageBox.information(self, "完成", "测量数据已清空，请重新导入数据。")

    def _on_clear_files(self):
        #撤回已选文件，回到初始状态
        self.parsed_files = []
        self.drop_zone.reset_to_empty()
        self.sheet_tabs.clear()
        self.sheet_tabs.setVisible(False)
        self.overview_card.setVisible(False)
        self.status_label.setVisible(False)
        self.progress_bar.setVisible(False)
        self._imported = False
        self._set_import_state("idle")

    def _on_files_selected(self, file_paths):
        parsed_files = []
        failed = []

        for path in file_paths:
            try:
                reader = ExcelReader(path)
                sheets = reader.read_all_sheets()
                parsed_files.append((path, sheets))
            except Exception as e:
                failed.append((path, str(e)))

        if not parsed_files:
            QMessageBox.critical(self, "错误", "无法读取所选文件。")
            return

        #房间名直接采用文件里的原始写法，不做任何改名/归一化，
        #保证「选择要查看的房间」与文件里的一字不差。
        self.parsed_files = parsed_files

        #重置上一次导入留下的状态
        self.status_label.setVisible(False)
        self.progress_bar.setVisible(False)
        self.overview_card.setVisible(False)

        #上传区显示文件信息
        files_info = [
            (path, [(name, len(df)) for name, df in sheets.items() if not df.empty])
            for path, sheets in parsed_files
        ]
        self.drop_zone.show_files_info(files_info)

        #预览
        self._update_preview_tabs()

        #高亮导入按钮（就绪态）——「清除文件」按钮已随上传区切换显示
        self._imported = False
        self._set_import_state("ready")

        #有读取失败的文件时提示
        if failed:
            names = "\n".join(f"  • {os.path.basename(p)}" for p, _ in failed)
            QMessageBox.warning(self, "部分文件读取失败", f"以下文件无法读取：\n{names}")

    def _update_preview_tabs(self):
        self.sheet_tabs.clear()

        multiple = len(self.parsed_files) > 1
        name_counter = Counter()
        for _, sheets in self.parsed_files:
            name_counter.update(sheets.keys())

        for path, sheets in self.parsed_files:
            for sheet_name, df in sheets.items():
                if df.empty:
                    continue
                if multiple or name_counter[sheet_name] > 1:
                    label = f"{os.path.basename(path)} · {sheet_name}"
                else:
                    label = sheet_name
                self._add_preview_tab(label, df)

        if self.sheet_tabs.count() > 0:
            self.sheet_tabs.setVisible(True)

    def _add_preview_tab(self, label, df):
        #为一个 sheet 创建一个预览标签页
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)

        info_text = f"共 {len(df)} 条记录 | {df['room_name'].nunique()} 个房间 | "
        if "particle_size" in df.columns and df["particle_size"].notna().any():
            info_text += "粒径: " + ", ".join(df["particle_size"].dropna().unique())
        info_text += f" | 指标: " + ", ".join(df["indicator_name"].unique())
        info_label = QLabel(info_text)
        info_label.setObjectName("fileMetaLabel")
        tab_layout.addWidget(info_label)

        preview = df.head(15)
        table = QTableWidget()
        table.setRowCount(len(preview))
        table.setColumnCount(len(preview.columns))
        table.setHorizontalHeaderLabels(list(preview.columns))
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        for i, (_, row) in enumerate(preview.iterrows()):
            for j, col in enumerate(preview.columns):
                val = row[col]
                if pd.isna(val):
                    text = ""
                elif isinstance(val, pd.Timestamp):
                    text = val.strftime("%Y-%m-%d")
                else:
                    text = str(val)
                table.setItem(i, j, QTableWidgetItem(text))

        tab_layout.addWidget(table)
        self.sheet_tabs.addTab(tab_widget, label)

    #导入
    def _start_import(self):
        if not self.parsed_files:
            QMessageBox.warning(self, "提示", "请先选择文件并完成数据解析。")
            return

        #保证「同一个文件」：导入新文件前清空旧数据（替换而非累加）。
        #这样后续的数据清洗 / 探索分析 / 结果报告读到的都只有当前文件的数据。
        try:
            existing = Repository.count_measurements()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法读取数据库：{e}")
            return

        if existing > 0:
            reply = QMessageBox.question(
                self, "替换旧数据",
                f"数据库当前已有 {existing:,} 条测量数据。\n"
                "导入新文件将清空旧数据并替换为当前文件，是否继续？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if reply != QMessageBox.Yes:
                return

        try:
            Repository.clear_measurements()
        except Exception as e:
            QMessageBox.critical(self, "清空失败", f"清空旧数据时出错：{e}")
            return

        #重置下游页面缓存（清洗/分析/建模/检验/报告），避免残留上一个文件的结果
        if hasattr(self, "main_window") and self.main_window:
            self.main_window.reset_downstream()

        #导入中：按钮进入 working 态（禁用），显示进度
        self._set_import_state("working")
        self.status_label.setVisible(True)
        self.status_label.setText("正在写入...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self.worker = ImportWorker(parsed_files=self.parsed_files)
        self.worker.progress_signal.connect(self._on_import_progress)
        self.worker.finished_signal.connect(self._on_import_finished)
        self.worker.start()

    def _on_import_progress(self, percent: int, message: str):
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)

    def _on_import_finished(self, success: bool, message: str):
        self.progress_bar.setVisible(False)
        self.status_label.setText(message)
        if success:
            #导入成功：按钮进入完成态（与侧边栏绿一致）
            self._imported = True
            self._set_import_state("done")
            #显示概览卡片 + 解锁下一步
            self._populate_overview()
            if hasattr(self, "main_window") and self.main_window:
                self.main_window.mark_step_completed(0)
            QMessageBox.information(self, "导入完成", message)
        else:
            #导入失败：按钮回到就绪态，可重试
            self._set_import_state("ready")
            QMessageBox.critical(self, "导入失败", message)
