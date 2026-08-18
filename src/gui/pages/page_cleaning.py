import numpy as np
import pandas as pd
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QRadioButton, QButtonGroup, QTextEdit,
    QTableWidget, QTableWidgetItem, QProgressBar,
    QMessageBox, QSplitter, QHeaderView,
    QScrollArea, QFrame, QDialog,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor

from src.database.repository import Repository
from src.cleaning.pipeline import CleaningPipeline


#预览表高亮配色：缺失值=红、异常值=绿
_MISSING_BG = "#FECACA"
_OUTLIER_BG = "#BBF7D0"


class CleaningWorker(QThread):
    #后台清洗线程
    progress = Signal(int, str)
    step_done = Signal(str, dict)  # step_key, result_dict
    finished = Signal(bool, str, object)  # success, message, cleaned_df
    error = Signal(str)

    def __init__(self, df, steps_with_choices):
        super().__init__()
        self.df = df
        self.steps_with_choices = steps_with_choices  # [(step_key, choice), ...]

    def run(self):
        try:
            pipeline = CleaningPipeline(self.df)
            for i, (step_key, choice) in enumerate(self.steps_with_choices):
                self.progress.emit(
                    int((i / len(self.steps_with_choices)) * 100),
                    f"正在执行: {step_key} ({choice})..."
                )
                result = pipeline.run_step(step_key, choice)
                self.step_done.emit(step_key, result)

            self.progress.emit(100, "清洗完成！")
            self.finished.emit(True, "数据清洗完成！", pipeline.df)
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False, f"清洗失败：{e}", None)


class CleaningPage(QWidget):
    def __init__(self):
        super().__init__()
        self.cleaned_df = None
        self.original_df = None
        self.pipeline = None
        self.current_step_index = 0
        self.step_choices = {}
        self.completed_steps = set()  #已完成的子步骤索引
        self._cleaning_done = False 
        self.step_names = ["1. 缺失值", "2. 异常值", "3. 时间格式", "4. 去重"]

        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content = QWidget()
        content.setMinimumWidth(1000)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        #标题
        title = QLabel("数据清洗")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        desc = QLabel("从数据库加载测量数据，按 4 个步骤向导式清洗：缺失值 / 异常值 / 时间格式 / 去重。")
        desc.setObjectName("pageDescription")
        layout.addWidget(desc)

        #数据库清洗模式
        layout.addLayout(self._build_db_mode(), 1)

        self.scroll.setWidget(content)
        outer.addWidget(self.scroll)

    #数据库清洗模式 UI
    def _build_db_mode(self):
        layout = QVBoxLayout()

        self.step_buttons = []
        step_bar = QHBoxLayout()
        for i, name in enumerate(self.step_names):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setEnabled(False)
            btn.setStyleSheet(self._step_btn_style("pending"))
            btn.clicked.connect(lambda checked, idx=i: self._show_step(idx))
            step_bar.addWidget(btn)
            self.step_buttons.append(btn)
        step_bar.addStretch()
        layout.addLayout(step_bar)

        #数据加载
        load_group = QGroupBox("加载数据")
        load_layout = QHBoxLayout(load_group)
        load_layout.addWidget(QLabel("从数据库加载测量数据以供清洗："))
        self.load_btn = QPushButton("加载数据")
        self.load_btn.setObjectName("secondaryBtn")
        self.load_btn.clicked.connect(self._load_data)
        load_layout.addWidget(self.load_btn)
        self.data_status = QLabel("尚未加载")
        self.data_status.setStyleSheet("color: #A8A29E;")
        load_layout.addWidget(self.data_status)
        load_layout.addStretch()
        layout.addWidget(load_group)

        splitter = QSplitter(Qt.Horizontal)

        # 左侧：方法选择 + 操作
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 8, 0)

        self.method_group = QGroupBox("选择处理方法")
        self.method_layout = QVBoxLayout(self.method_group)
        self.method_label = QLabel("请先加载数据")
        self.method_label.setWordWrap(True)
        self.method_layout.addWidget(self.method_label)
        self.method_button_group = QButtonGroup()
        self.method_buttons = []
        self.method_layout.addStretch()
        left_layout.addWidget(self.method_group)

        #操作按钮：应用此步骤 + 全部执行
        apply_layout = QHBoxLayout()
        self.apply_btn = QPushButton("应用此步骤")
        self.apply_btn.setObjectName("primaryBtn")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._apply_current_step)
        apply_layout.addWidget(self.apply_btn)

        self.run_all_btn = QPushButton("全部执行")
        self.run_all_btn.setObjectName("secondaryBtn")
        self.run_all_btn.setEnabled(False)
        self.run_all_btn.clicked.connect(self._run_all)
        apply_layout.addWidget(self.run_all_btn)
        left_layout.addLayout(apply_layout)

        left_layout.addStretch()

        splitter.addWidget(left_widget)

        #右侧：数据视图 + 日志
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 0, 0, 0)

        preview_group = QGroupBox("数据视图")
        preview_layout = QVBoxLayout(preview_group)

        preview_header = QHBoxLayout()
        self.preview_info = QLabel("加载数据后显示预览")
        self.preview_info.setObjectName("fileMetaLabel")
        preview_header.addWidget(self.preview_info)
        preview_header.addStretch()
        self.view_data_btn = QPushButton("查看完整数据")
        self.view_data_btn.setObjectName("secondaryBtn")
        self.view_data_btn.setEnabled(False)
        self.view_data_btn.clicked.connect(self._open_data_view)
        preview_header.addWidget(self.view_data_btn)
        preview_layout.addLayout(preview_header)

        self.preview_table = QTableWidget()
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setMinimumHeight(400)  # 至少 15 行
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        preview_layout.addWidget(self.preview_table)
        right_layout.addWidget(preview_group)

        # 操作日志
        log_group = QGroupBox("操作日志")
        log_layout = QVBoxLayout(log_group)
        self.log_output = QTextEdit()
        self.log_output.setObjectName("logOutput")
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(150)
        log_layout.addWidget(self.log_output)
        right_layout.addWidget(log_group)

        splitter.addWidget(right_widget)
        splitter.setSizes([380, 820])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        #底部进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        #底部导航
        bottom = QHBoxLayout()
        self.prev_btn = QPushButton("上一步")
        self.prev_btn.setObjectName("secondaryBtn")
        self.prev_btn.clicked.connect(self._prev_step)
        bottom.addWidget(self.prev_btn)
        bottom.addStretch()
        self.next_btn = QPushButton("下一步")
        self.next_btn.setObjectName("primaryBtn")
        self.next_btn.clicked.connect(self._next_step)
        self.next_btn.setEnabled(False)
        bottom.addWidget(self.next_btn)
        layout.addLayout(bottom)

        return layout

    #数据加载
    def _load_data(self):
        try:
            self.original_df = Repository.get_all_measurements()
            if self.original_df.empty:
                QMessageBox.warning(self, "提示", "数据库中暂无数据，请先完成「数据导入」步骤。")
                return

            #移除非数据列
            skip_cols = ["id", "import_session_id", "extended_data", "created_at"]
            df = self.original_df.drop(columns=[c for c in skip_cols if c in self.original_df.columns], errors="ignore")
            self.original_df = df

            self.pipeline = CleaningPipeline(df)
            self.data_status.setText(f"已加载 {len(df)} 行, {len(df.columns)} 列")
            self.data_status.setStyleSheet("color: #0F766E;")

            #启用功能
            self.load_btn.setEnabled(False)
            self.run_all_btn.setEnabled(True)
            self.view_data_btn.setEnabled(True)
            for btn in self.step_buttons:
                btn.setEnabled(True)

            #显示第一步
            self.current_step_index = 0
            self._show_step(0)
            self._log("数据加载完成，请开始选择清洗方法。")

        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"从数据库加载数据时出错：{e}")

    def reset(self):
        #清空已加载的数据与清洗状态
        self.cleaned_df = None
        self.original_df = None
        self.pipeline = None
        self.current_step_index = 0
        self.step_choices = {}
        self.completed_steps = set()
        self._cleaning_done = False

        #数据状态
        self.data_status.setText("尚未加载")
        self.data_status.setStyleSheet("color: #A8A29E;")

        #按钮复位
        self.load_btn.setEnabled(True)
        self.run_all_btn.setEnabled(False)
        self.view_data_btn.setEnabled(False)
        self.apply_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        self.next_btn.setText("下一步")
        self.prev_btn.setEnabled(False)

        #子步骤按钮复位
        for i, btn in enumerate(self.step_buttons):
            btn.setEnabled(False)
            btn.setText(self.step_names[i])
            btn.setStyleSheet(self._step_btn_style("pending"))
            btn.setChecked(False)

        #方法选择区清空
        for btn in self.method_buttons:
            self.method_layout.removeWidget(btn)
            btn.deleteLater()
        self.method_buttons.clear()
        self.method_button_group = QButtonGroup()
        self.method_label.setText("请先加载数据")

        # 预览与日志清空
        self.preview_table.clear()
        self.preview_table.setRowCount(0)
        self.preview_table.setColumnCount(0)
        self.preview_info.setText("加载数据后显示预览")
        self.log_output.clear()

    #步骤导航
    def _show_step(self, index: int):
        if not self.pipeline:
            return

        self.current_step_index = index
        step_def = CleaningPipeline.STEPS[index]
        step_key = step_def["key"]

        self._refresh_step_buttons()

        #更新方法选择区
        self.method_group.setTitle(f"{step_def['name']} — 选择处理方法")
        self.method_label.setText(step_def["description"])

        #清除旧选项
        for btn in self.method_buttons:
            self.method_layout.removeWidget(btn)
            btn.deleteLater()
        self.method_buttons.clear()
        self.method_button_group = QButtonGroup()

        #生成摘要和选项
        summary = self.pipeline._make_summary(step_key)
        if summary:
            self.method_label.setText(
                f"{step_def['description']}\n\n{summary.get('message', '')}"
            )

        #添加选项按钮（选择后实时预览效果）
        for opt in step_def["options"]:
            rb = QRadioButton(opt["label"])
            rb.setToolTip(opt["desc"])
            rb.setProperty("opt_id", opt["id"])
            rb.clicked.connect(self._on_method_changed)
            self.method_button_group.addButton(rb)
            self.method_layout.insertWidget(self.method_layout.count() - 1, rb)
            self.method_buttons.append(rb)

        #默认选中第一个
        if self.method_buttons:
            self.method_buttons[0].setChecked(True)

        #恢复已保存的选择
        if step_key in self.step_choices:
            saved_choice = self.step_choices[step_key]
            for btn in self.method_buttons:
                if btn.property("opt_id") == saved_choice:
                    btn.setChecked(True)

        #已完成的步骤不可重复应用
        self.apply_btn.setEnabled(index not in self.completed_steps)

        #底部导航
        self.prev_btn.setEnabled(index > 0)
        self.next_btn.setEnabled(index < len(self.step_names) - 1)

        #数据预览
        self._update_preview(self.pipeline.df)

    def _prev_step(self):
        if self.current_step_index > 0:
            self._show_step(self.current_step_index - 1)

    def _next_step(self):
        if self._cleaning_done:
            # 清洗已完成，「下一步」= 进入探索分析页
            if hasattr(self, "main_window") and self.main_window:
                self.main_window.switch_to_page(2)
            return
        if self.current_step_index < len(self.step_names) - 1:
            self._show_step(self.current_step_index + 1)

    def _refresh_step_buttons(self):
        for i, btn in enumerate(self.step_buttons):
            if i in self.completed_steps:
                btn.setText(f"✓ {self.step_names[i]}")
                btn.setStyleSheet(self._step_btn_style("completed"))
                btn.setChecked(False)
            elif i == self.current_step_index:
                btn.setText(self.step_names[i])
                btn.setStyleSheet(self._step_btn_style("active"))
                btn.setChecked(True)
            else:
                btn.setText(self.step_names[i])
                btn.setStyleSheet(self._step_btn_style("pending"))
                btn.setChecked(False)

    #执行
    def _get_current_choice(self) -> str:
        checked = self.method_button_group.checkedButton()
        if checked:
            return checked.property("opt_id")
        return CleaningPipeline.STEPS[self.current_step_index]["options"][0]["id"]

    def _on_method_changed(self):
        #选择处理方法后实时预览效果
        if not self.pipeline:
            return
        step_key = CleaningPipeline.STEPS[self.current_step_index]["key"]
        choice = self._get_current_choice()
        checked = self.method_button_group.checkedButton()
        label = checked.text() if checked else choice
        try:
            temp = CleaningPipeline(self.pipeline.df.copy())
            result = temp.run_step(step_key, choice)
            if result.get("ok"):
                self._update_preview(result["after"])
                self.preview_info.setText(f"{self.preview_info.text()} · 预览「{label}」")
        except Exception:
            pass  # 预览失败不打断操作

    def _apply_current_step(self):
        #执行当前步骤
        if not self.pipeline:
            return

        step_key = CleaningPipeline.STEPS[self.current_step_index]["key"]
        choice = self._get_current_choice()
        self.step_choices[step_key] = choice
        self.completed_steps.add(self.current_step_index)

        self._log(f"执行 {step_key}，方法: {choice}")
        result = self.pipeline.run_step(step_key, choice)

        if result["ok"]:
            self.pipeline.df = result["after"]
            self._update_preview(result["after"])
            for log_entry in result.get("step_log", []):
                self._log(str(log_entry))

            step_name = CleaningPipeline.STEPS[self.current_step_index]["name"]
            self._log(f"步骤「{step_name}」已完成")
            self._refresh_step_buttons()

            #自动跳到下一步
            if self.current_step_index < len(self.step_names) - 1:
                self._show_step(self.current_step_index + 1)
            else:
                #最后一步完成
                self._finish_cleaning()
                QMessageBox.information(self, "完成", "数据清洗全部完成！点击「进入探索分析」继续。")

    def _finish_cleaning(self):
        #清洗全部完成：标记步骤完成、解锁侧边栏
        self.cleaned_df = self.pipeline.df
        self._cleaning_done = True
        self.apply_btn.setEnabled(False)
        self.next_btn.setText("进入探索分析")
        self.next_btn.setEnabled(True)
        self._log("全部 4 个步骤已完成，可进入「探索分析」。")
        if hasattr(self, "main_window") and self.main_window:
            self.main_window.mark_step_completed(1)

    def _run_all(self):
        #一键执行所有步骤（使用默认选择）
        reply = QMessageBox.question(
            self, "确认",
            "将使用默认方法（仅高亮缺失值 + IQR异常值 + 自动时间解析 + 跳过去重）\n\n"
            "执行全部清洗步骤。确认继续？",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.progress_bar.setVisible(True)
        self.run_all_btn.setEnabled(False)

        steps = [(s["key"], s["options"][0]["id"]) for s in CleaningPipeline.STEPS]
        self.worker = CleaningWorker(self.original_df.copy(), steps)
        self.worker.progress.connect(lambda p, m: self.progress_bar.setValue(p))
        self.worker.step_done.connect(self._on_step_done)
        self.worker.finished.connect(self._on_cleaning_finished)
        self.worker.error.connect(lambda e: self._log(f"{e}"))
        self.worker.start()

    def _on_step_done(self, step_key: str, result: dict):
        if result.get("ok"):
            self._log(f"{step_key} 完成")
            for entry in result.get("step_log", []):
                self._log(f"   {entry}")

    def _on_cleaning_finished(self, success: bool, message: str, df):
        self.progress_bar.setVisible(False)
        self.run_all_btn.setEnabled(True)
        self._log(message)

        if success and df is not None:
            self.cleaned_df = df
            self.pipeline.df = df
            self.completed_steps = set(range(len(self.step_names)))
            self.current_step_index = len(self.step_names) - 1
            self._refresh_step_buttons()
            self._update_preview(df)
            self._finish_cleaning()
            QMessageBox.information(self, "完成", f"{message}\n\n是否进入「探索分析」步骤？")
            self.main_window.switch_to_page(2)

    #辅助
    def _open_data_view(self):
        #打开完整数据视图对话框（红 = 缺失值，绿 = 异常值）
        if not self.pipeline or self.pipeline.df is None:
            return
        df = self.pipeline.df

        dialog = QDialog(self)
        dialog.setWindowTitle("完整数据视图")
        dialog.resize(1100, 720)
        dlg_layout = QVBoxLayout(dialog)

        info = QLabel(f"共 {len(df)} 行 × {len(df.columns)} 列（红 = 缺失值，绿 = 异常值，最多显示前 500 行）")
        info.setObjectName("fileMetaLabel")
        dlg_layout.addWidget(info)

        table = QTableWidget()
        table.setAlternatingRowColors(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table.horizontalHeader().setDefaultSectionSize(150)
        table.horizontalHeader().setStretchLastSection(True)
        self._fill_table(table, df, max_rows=500)
        dlg_layout.addWidget(table)

        close_btn = QPushButton("关闭")
        close_btn.setObjectName("primaryBtn")
        close_btn.clicked.connect(dialog.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        dlg_layout.addLayout(btn_row)

        dialog.exec()

    @staticmethod
    def _format_cell(val) -> str:
        if pd.isna(val):
            return ""
        if isinstance(val, pd.Timestamp):
            return val.strftime("%Y-%m-%d %H:%M:%S")
        return str(val)

    def _compute_issue_masks(self, df: pd.DataFrame):
        missing = df.isna()

        outlier = pd.DataFrame(False, index=df.index, columns=df.columns)
        for col in df.select_dtypes(include=[np.number]).columns:
            series = df[col].dropna()
            if len(series) == 0:
                continue
            q1, q3 = series.quantile(0.25), series.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0:
                continue
            lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            outlier[col] = (df[col] < lo) | (df[col] > hi)

        return missing, outlier

    def _fill_table(self, table: QTableWidget, df: pd.DataFrame, max_rows: int = None,
                    masks: tuple = None):
        #填充表格并按问题类型高亮：缺失值=红、异常值=绿。
        if df is None or df.empty:
            table.setRowCount(0)
            table.setColumnCount(0)
            return

        if masks is None:
            masks = self._compute_issue_masks(df)
        missing_mask, outlier_mask = masks

        display = df.head(max_rows) if max_rows else df
        n_rows = len(display)
        #掩码与 df 对齐，前 n_rows 行就是 display 对应的子集
        missing_mask = missing_mask.iloc[:n_rows]
        outlier_mask = outlier_mask.iloc[:n_rows]

        table.setRowCount(n_rows)
        table.setColumnCount(len(df.columns))
        table.setHorizontalHeaderLabels([str(c) for c in df.columns])

        for i, (_, row) in enumerate(display.iterrows()):
            for j, col in enumerate(df.columns):
                val = row[col]
                item = QTableWidgetItem()
                if missing_mask.iloc[i, j]:
                    item.setText("")
                    item.setBackground(QColor(_MISSING_BG))
                    item.setToolTip("缺失值")
                elif outlier_mask.iloc[i, j]:
                    item.setText(self._format_cell(val))
                    item.setBackground(QColor(_OUTLIER_BG))
                    item.setToolTip("异常值")
                else:
                    item.setText(self._format_cell(val))
                table.setItem(i, j, item)

    def _update_preview(self, df: pd.DataFrame):
        masks = self._compute_issue_masks(df) if (df is not None and not df.empty) else None
        self._fill_table(self.preview_table, df, max_rows=15, masks=masks)
        if df is None or df.empty:
            return
        missing = int(masks[0].to_numpy().sum())
        outlier = int(masks[1].to_numpy().sum())
        self.preview_info.setText(
            f"共 {len(df)} 行 × {len(df.columns)} 列 · "
            f"缺失值 {missing}（红）· 异常值 {outlier}（绿）"
        )

    def _log(self, message: str):
        self.log_output.append(message)

    def _step_btn_style(self, state: str) -> str:
        if state == "active":
            return ("QPushButton { background-color: #0F766E; color: #FFFFFF; "
                    "border-radius: 16px; padding: 8px 16px; font-weight: 600; font-size: 13px; border: none; }")
        elif state == "completed":
            return ("QPushButton { background-color: #CCFBF1; color: #0F766E; "
                    "border-radius: 16px; padding: 8px 16px; font-weight: 600; font-size: 13px; border: none; }")
        else:
            return ("QPushButton { background-color: #F5F5F4; color: #A8A29E; "
                    "border-radius: 16px; padding: 8px 16px; font-size: 13px; border: none; }")
