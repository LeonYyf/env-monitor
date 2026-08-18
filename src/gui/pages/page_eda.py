import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

import config
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTableWidget, QTableWidgetItem, QCheckBox,
    QComboBox, QTabWidget, QHeaderView, QMessageBox,
    QScrollArea, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from src.gui.chart_canvas import AdaptiveCanvas
from src.data_store import data_store
from src.fonts import setup_chinese_font

# 设置中文字体（跨平台自动探测，避免中文标签显示成方块乱码）
setup_chinese_font()
sns.set_palette(config.VIZ_DEFAULTS["color_palette"])


class EDAPage(QWidget):
    def __init__(self):
        super().__init__()
        self.df = None
        self.df_all = None
        self.indicators = []    # 可选指标列表
        self.rooms = []         # 房间列表
        self.var_checkboxes = {}
        self._chart_generated = False
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

        title = QLabel("探索分析")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        desc = QLabel("统计描述 + 可视化图表。左侧选择变量与房间，右侧查看该房间的图表（超出国标限值的粒子浓度会红色标记）。")
        desc.setObjectName("pageDescription")
        layout.addWidget(desc)

        #数据加载
        load_group = QGroupBox("数据")
        load_layout = QHBoxLayout(load_group)
        self.load_btn = QPushButton("加载数据")
        self.load_btn.setObjectName("secondaryBtn")
        self.load_btn.clicked.connect(self._load_data)
        load_layout.addWidget(self.load_btn)
        self.data_status = QLabel("尚未加载")
        self.data_status.setStyleSheet("color: #A8A29E;")
        load_layout.addWidget(self.data_status)
        load_layout.addStretch()
        layout.addWidget(load_group)

        #主体：左侧固定宽度操作面板 + 右侧弹性结果区
        main = QHBoxLayout()
        main.setSpacing(16)
        main.addWidget(self._build_left_panel())
        main.addWidget(self._build_right_panel(), 1)
        layout.addLayout(main, 1)

        self.scroll.setWidget(content)
        outer.addWidget(self.scroll)

        #底部导航：进入结果报告
        bottom = QHBoxLayout()
        bottom.setContentsMargins(32, 12, 32, 16)
        bottom.addStretch()
        self.next_report_btn = QPushButton("进入结果报告")
        self.next_report_btn.setObjectName("primaryBtn")
        self.next_report_btn.clicked.connect(self._go_to_report)
        bottom.addWidget(self.next_report_btn)
        outer.addLayout(bottom)

    def _go_to_report(self):
        #进入结果报告页：标记本步骤完成、解锁侧边栏，并跳转
        if hasattr(self, "main_window") and self.main_window:
            self.main_window.mark_step_completed(2)
            self.main_window.switch_to_page(3)

    def _build_left_panel(self):
        left = QWidget()
        left.setFixedWidth(280)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        #数据表选择（尘埃粒子 / 风量），房间按所选表过滤
        sheet_group = QGroupBox("数据表")
        sheet_layout = QVBoxLayout(sheet_group)
        sheet_layout.addWidget(QLabel("选择要分析的表："))
        self.sheet_combo = QComboBox()
        self.sheet_combo.addItem("请先加载数据")
        self.sheet_combo.setEnabled(False)
        self.sheet_combo.currentIndexChanged.connect(self._on_sheet_changed)
        sheet_layout.addWidget(self.sheet_combo)
        left_layout.addWidget(sheet_group)

        #变量选择
        var_group = QGroupBox("变量")
        var_layout = QVBoxLayout(var_group)
        var_layout.addWidget(QLabel("选择要分析的指标："))
        self.checkbox_container = QWidget()
        self.checkbox_layout = QVBoxLayout(self.checkbox_container)
        self.checkbox_layout.setAlignment(Qt.AlignTop)
        self.checkbox_layout.setContentsMargins(0, 0, 0, 0)
        var_layout.addWidget(self.checkbox_container)
        left_layout.addWidget(var_group)

        #房间选择
        room_group = QGroupBox("房间")
        room_layout = QVBoxLayout(room_group)
        room_layout.addWidget(QLabel("选择要查看的房间："))
        self.room_combo = QComboBox()
        self.room_combo.addItem("请先加载数据")
        self.room_combo.setEnabled(False)
        self.room_combo.currentIndexChanged.connect(self._on_room_changed)
        room_layout.addWidget(self.room_combo)
        left_layout.addWidget(room_group)

        #统计分析
        stats_group = QGroupBox("统计分析")
        stats_layout = QVBoxLayout(stats_group)
        stats_layout.addWidget(QLabel("洁净级别（粒子国标）："))
        self.class_combo = QComboBox()
        self.class_combo.addItems(config.CLEANROOM_CLASSES)
        self.class_combo.setCurrentText(config.DEFAULT_CLEANROOM_CLASS)
        stats_layout.addWidget(self.class_combo)
        self.run_stats_btn = QPushButton("生成统计描述")
        self.run_stats_btn.setObjectName("primaryBtn")
        self.run_stats_btn.setEnabled(False)
        self.run_stats_btn.clicked.connect(self._run_statistics)
        stats_layout.addWidget(self.run_stats_btn)
        left_layout.addWidget(stats_group)

        #可视化
        viz_group = QGroupBox("可视化")
        viz_layout = QVBoxLayout(viz_group)
        viz_layout.addWidget(QLabel("图表类型："))
        self.chart_combo = QComboBox()
        self.chart_combo.addItems([
            "送风量 vs 换气次数（双轴）",
            "直方图（分布）",
            "箱线图（指标对比）",
            "时间序列（趋势）",
            "相关性热力图",
        ])
        viz_layout.addWidget(self.chart_combo)
        self.run_chart_btn = QPushButton("生成图表")
        self.run_chart_btn.setObjectName("primaryBtn")
        self.run_chart_btn.setEnabled(False)
        self.run_chart_btn.clicked.connect(self._run_charts)
        viz_layout.addWidget(self.run_chart_btn)
        left_layout.addWidget(viz_group)

        left_layout.addStretch()
        return left

    def _build_right_panel(self):
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.result_hint = QLabel("选择变量与房间后点击「生成图表」，查看该房间的图表")
        self.result_hint.setObjectName("fileMetaLabel")
        self.result_hint.setWordWrap(True)
        right_layout.addWidget(self.result_hint)
        self.result_tabs = QTabWidget()
        self.result_tabs.setDocumentMode(True)
        right_layout.addWidget(self.result_tabs, 1)
        return right

    # 数据加载
    def _load_data(self):
        try:
            df = data_store.get_for_analysis()
            if df is None or df.empty:
                QMessageBox.warning(self, "提示", "暂无可分析数据，请先完成「数据导入」与「数据清洗」。")
                return

            skip = ["id", "import_session_id", "extended_data", "created_at"]
            df = df.drop(columns=[c for c in skip if c in df.columns], errors="ignore")

            #去重（重复导入产生的重复记录）
            key = [c for c in ["record_date", "room_name", "room_adjacent",
                               "particle_size", "indicator_name"] if c in df.columns]
            df = df.drop_duplicates(subset=key, keep="first")

            if "record_date" in df.columns:
                df["record_date"] = pd.to_datetime(df["record_date"], errors="coerce")

            #派生指标：房间体积 = 送风量 ÷ 换气次数（单位 m³），加入可分析列表
            df = self._add_volume_indicator(df)

            self.df_all = df

            #填充「数据表」下拉框：全部 + 实际存在的 sheet
            sheets = sorted(df["sheet_name"].dropna().unique().tolist()) if "sheet_name" in df.columns else []
            self.sheet_combo.blockSignals(True)
            self.sheet_combo.clear()
            self.sheet_combo.addItems(["全部"] + sheets)
            self.sheet_combo.setCurrentIndex(0)
            self.sheet_combo.setEnabled(True)
            self.sheet_combo.blockSignals(False)

            #按当前所选数据表过滤，并填充变量/房间
            self._apply_sheet_filter()

            self.load_btn.setEnabled(False)
            self._update_buttons()

        except Exception as e:
            QMessageBox.critical(self, "加载失败", str(e))

    def load_from_store(self):
        #页面切换进入时自动加载；已加载或无数据时静默跳过
        if self.df_all is None and data_store.get_for_analysis() is not None:
            self._load_data()

    def _populate_variables(self):
        while self.checkbox_layout.count():
            item = self.checkbox_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.var_checkboxes.clear()
        for ind in self.indicators:
            cb = QCheckBox(ind)
            cb.setChecked(True)
            cb.toggled.connect(lambda checked: self._update_buttons())
            self.checkbox_layout.addWidget(cb)
            self.var_checkboxes[ind] = cb

    def _add_volume_indicator(self, df):
        #派生指标：房间体积 = 送风量 ÷ 换气次数（单位 m³）
        if df.empty or "indicator_cn" not in df.columns:
            return df
        cn = set(df["indicator_cn"].dropna())
        if "送风量" not in cn or "换气次数" not in cn:
            return df

        wide = df.pivot_table(
            index=["record_date", "room_name"],
            columns="indicator_cn", values="value", aggfunc="mean"
        )
        if "送风量" not in wide.columns or "换气次数" not in wide.columns:
            return df

        volume = (wide["送风量"] / wide["换气次数"])\
            .replace([np.inf, -np.inf], np.nan).dropna()\
            .rename("value").reset_index()
        if volume.empty:
            return df

        volume["indicator_name"] = "room_volume"
        volume["indicator_cn"] = "送风量/换气次数"
        volume["unit"] = "m³"
        # 补齐 df 中其余列（room_adjacent / particle_size 等），用 None 填充
        for col in df.columns:
            if col not in volume.columns:
                volume[col] = None
        # 体积指标来自「风量」表，标记其所属表，便于按数据表过滤
        volume["sheet_name"] = "风量"

        return pd.concat([df, volume[df.columns]], ignore_index=True)

    def _populate_rooms(self):
        """填充房间下拉框（按当前所选数据表过滤后的房间）"""
        self.rooms = sorted(self.df["room_name"].dropna().unique().tolist())
        self.room_combo.blockSignals(True)
        self.room_combo.clear()
        self.room_combo.addItems(self.rooms or ["暂无房间"])
        self.room_combo.setEnabled(bool(self.rooms))
        self.room_combo.blockSignals(False)

    def _on_room_changed(self):
        #切换房间后，若已生成过图表，自动刷新为当前房间的图表
        if self._chart_generated:
            self._run_charts()

    def _apply_sheet_filter(self):
        #按当前选择的「数据表」过滤数据，并刷新变量/房间列表
        if self.df_all is None:
            return
        sheet = self.sheet_combo.currentText()
        if sheet and sheet != "全部":
            self.df = self.df_all[self.df_all["sheet_name"] == sheet]
        else:
            self.df = self.df_all

        self.indicators = sorted(self.df["indicator_cn"].dropna().unique().tolist())
        self._populate_variables()
        self._populate_rooms()

        self.data_status.setText(
            f"已加载 {len(self.df)} 行, {len(self.indicators)} 个指标, {len(self.rooms)} 个房间"
        )
        self.data_status.setStyleSheet("color: #0F766E;")

    def _on_sheet_changed(self):
        #切换数据表后刷新房间/变量列表，并清空旧图表
        if self.df_all is None:
            return
        self._apply_sheet_filter()
        self._chart_generated = False
        self.result_tabs.clear()
        self.result_hint.setText("已切换数据表，请重新选择房间并生成图表")

    def _get_selected_indicators(self):
        return [ind for ind, cb in self.var_checkboxes.items() if cb.isChecked()]

    def _update_buttons(self):
        #未选变量时置灰 + 悬停提示；选好变量后实心主色
        has_data = self.df is not None
        has_vars = bool(self._get_selected_indicators())
        for btn in (self.run_stats_btn, self.run_chart_btn):
            btn.setEnabled(has_data)
            btn.setProperty("inactive", has_data and not has_vars)
            if not has_data:
                btn.setToolTip("请先加载数据")
            elif not has_vars:
                btn.setToolTip("请先选择变量")
            else:
                btn.setToolTip("")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def reset(self):
        #清空已加载的数据与结果
        self.df = None
        self.df_all = None
        self.indicators = []
        self.rooms = []
        self.var_checkboxes = {}
        self._chart_generated = False
        #清空变量复选框
        while self.checkbox_layout.count():
            item = self.checkbox_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        #清空房间下拉框
        self.room_combo.clear()
        self.room_combo.addItem("请先加载数据")
        self.room_combo.setEnabled(False)
        #重置数据表下拉框
        self.sheet_combo.blockSignals(True)
        self.sheet_combo.clear()
        self.sheet_combo.addItem("请先加载数据")
        self.sheet_combo.setEnabled(False)
        self.sheet_combo.blockSignals(False)
        self.data_status.setText("尚未加载")
        self.data_status.setStyleSheet("color: #A8A29E;")
        self.load_btn.setEnabled(True)
        self._update_buttons()
        self.result_tabs.clear()
        self.result_hint.setText("选择变量与房间后点击「生成图表」，结果将显示在这里")

    # 统计描述
    def _run_statistics(self):
        indicators = self._get_selected_indicators()
        if not indicators:
            QMessageBox.warning(self, "提示", "请先选择变量。")
            return
        cls = self.class_combo.currentText()
        stats_df = self._compute_stats(indicators, cls)
        if stats_df.empty:
            QMessageBox.warning(self, "提示", "所选变量没有可用数据。")
            return
        self._show_stats_table(stats_df)
        self.result_hint.setText(f"统计描述 · {len(indicators)} 个指标 · 洁净级别：{cls}")

    def _compute_stats(self, indicators, cls) -> pd.DataFrame:
        results = []
        for ind in indicators:
            sub = self.df[self.df["indicator_cn"] == ind]["value"].dropna()
            if len(sub) == 0:
                continue
            n = len(sub)
            unit = ""
            if "unit" in self.df.columns:
                units = self.df.loc[self.df["indicator_cn"] == ind, "unit"]
                unit = units.iloc[0] if len(units) and pd.notna(units.iloc[0]) else ""

            row = {
                "指标": ind,
                "样本数": n,
                "均值": round(sub.mean(), 2),
                "标准差": round(sub.std(ddof=0), 2),
                "最小值": round(sub.min(), 2),
                "中位数": round(sub.median(), 2),
                "最大值": round(sub.max(), 2),
                "单位": unit,
            }

            #粒子指标：对比国标限值
            limit = config.PARTICLE_LIMITS.get(ind, {}).get(cls)
            if limit is not None:
                exceed = int((sub > limit).sum())
                row["国标限值"] = limit
                row["超标数"] = exceed
                row["超标率"] = f"{exceed / n * 100:.1f}%"
                row["是否超标"] = "是" if exceed > 0 else "否"
            else:
                row["国标限值"] = "—"
                row["超标数"] = "—"
                row["超标率"] = "—"
                row["是否超标"] = "—"
            results.append(row)
        return pd.DataFrame(results)

    def _show_stats_table(self, stats_df):
        table = QTableWidget()
        cols = list(stats_df.columns)
        table.setRowCount(len(stats_df))
        table.setColumnCount(len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.setAlternatingRowColors(True)

        for i, (_, row) in enumerate(stats_df.iterrows()):
            is_exceed = row.get("是否超标") == "是"
            for j, col in enumerate(cols):
                item = QTableWidgetItem(str(row[col]))
                if is_exceed and col in ("最大值", "是否超标"):
                    item.setForeground(QColor("#DC2626"))
                    item.setBackground(QColor("#FEE2E2"))
                table.setItem(i, j, item)

        self._show_tab(table, "统计描述")

    # 可视化（按房间生成图表）
    def _run_charts(self):
        room = self.room_combo.currentText()
        if not room or room in ("请先加载数据", "暂无房间"):
            QMessageBox.warning(self, "提示", "请先加载数据并选择房间。")
            return

        chart_type = self.chart_combo.currentText()
        wide = self._room_wide(room)
        if wide.empty:
            QMessageBox.warning(self, "提示", f"房间「{room}」没有可用数据。")
            return

        #双轴对比图固定用「送风量 + 换气次数」，不需要勾选变量
        if chart_type == "送风量 vs 换气次数（双轴）":
            self._clear_result_tabs()
            try:
                fig = self._room_dual_axis(room, wide)
            except Exception as e:
                QMessageBox.warning(self, "生成失败", f"生成图表时出错：{e}")
                return
            self._show_tab(AdaptiveCanvas(fig), room)
            self._chart_generated = True
            self.result_hint.setText(f"图表：{chart_type} · 房间：{room}")
            return

        indicators = self._get_selected_indicators()
        if not indicators:
            QMessageBox.warning(self, "提示", "请先选择变量。")
            return

        available = [c for c in indicators
                     if c in wide.columns and wide[c].notna().any()]
        if not available:
            QMessageBox.warning(self, "提示", f"房间「{room}」缺少所选变量的数据。")
            return

        self._clear_result_tabs()
        try:
            if chart_type == "直方图（分布）":
                fig = self._room_histogram(room, wide, available)
            elif chart_type == "箱线图（指标对比）":
                fig = self._room_boxplot(room, wide, available)
            elif chart_type == "时间序列（趋势）":
                fig = self._room_timeseries(room, wide, available)
            else:  #相关性热力图
                fig = self._room_heatmap(room, wide, available)

            self._show_tab(AdaptiveCanvas(fig), room)
            self._chart_generated = True
            self.result_hint.setText(f"图表：{chart_type} · 房间：{room}（{len(available)} 个变量）")
        except Exception as e:
            QMessageBox.warning(self, "生成失败", f"生成图表时出错：{e}")

    def _room_wide(self, room) -> pd.DataFrame:
        #单个房间的长格式
        sub = self.df[self.df["room_name"] == room]
        wide = sub.pivot_table(
            index="record_date", columns="indicator_cn",
            values="value", aggfunc="mean"
        ).sort_index()
        return wide

    def _room_histogram(self, room, wide, indicators):
        #一个房间内各所选变量的分布直方图
        n = len(indicators)
        fig, axes = plt.subplots(1, n, figsize=(min(5 * n, 16), 4.5), dpi=100, constrained_layout=True)
        if n == 1:
            axes = [axes]
        for ax, ind in zip(axes, indicators):
            series = wide[ind].dropna()
            ax.hist(series, bins=30, color="#0F766E", edgecolor="white", alpha=0.7)
            ax.set_title(ind, fontweight="bold")
            ax.set_xlabel(ind)
            ax.set_ylabel("频次")
        fig.suptitle(f"{room} · 分布直方图", fontsize=14, fontweight="bold")
        return fig

    def _room_boxplot(self, room, wide, indicators):
        #一个房间内各所选变量的箱线图对比
        data = [wide[ind].dropna().values for ind in indicators]
        fig, ax = plt.subplots(figsize=(min(4.5 * len(indicators), 16), 4.5), dpi=100, constrained_layout=True)
        bp = ax.boxplot(data, patch_artist=True)
        ax.set_xticks(range(1, len(data) + 1), indicators)
        for patch in bp["boxes"]:
            patch.set_facecolor("#99F6E4")
            patch.set_edgecolor("#0F766E")
        ax.set_title(f"{room} · 指标箱线图", fontsize=14, fontweight="bold")
        ax.set_ylabel("数值")
        ax.grid(True, axis="y", alpha=0.3)
        return fig

    def _room_timeseries(self, room, wide, indicators):
        #一个房间内各所选变量随时间的变化趋势
        fig, ax = plt.subplots(figsize=(11, 6), dpi=100, constrained_layout=True)
        for ind in indicators:
            ax.plot(wide.index, wide[ind],
                    marker="o", markersize=3, linewidth=1.5, label=ind)
        ax.set_xlabel("日期", labelpad=12)
        ax.set_ylabel("数值")
        ax.set_title(f"{room} · 时间序列趋势", fontsize=14, fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        return fig

    def _room_heatmap(self, room, wide, indicators):
        #一个房间内各变量之间的相关性热力图
        if len(indicators) < 2:
            raise ValueError("相关性热力图至少需要选择 2 个变量")
        corr = wide[indicators].corr()
        fig, ax = plt.subplots(figsize=(9, 7), dpi=100, constrained_layout=True)
        mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
        sns.heatmap(corr, mask=mask, annot=True, fmt=".2f", cmap="RdYlBu_r",
                    center=0, square=True, linewidths=0.5, vmin=-1, vmax=1, ax=ax,
                    cbar_kws={"shrink": 0.8, "label": "Pearson 相关系数"})
        ax.set_title(f"{room} · 变量相关性热力图", fontsize=14, fontweight="bold", pad=12)
        return fig

    def _room_dual_axis(self, room, wide):
        #送风量与换气次数的双轴折线图
        supply = "送风量"
        changes = "换气次数"
        if supply not in wide.columns or changes not in wide.columns:
            raise ValueError("该房间缺少「送风量」或「换气次数」数据")

        s = wide[supply].dropna()
        c = wide[changes].dropna()
        valid = s.index.intersection(c.index)
        s, c = s.loc[valid], c.loc[valid]
        if len(valid) < 2:
            raise ValueError("有效数据点不足，无法绘制双轴对比")

        #体积 = 送风量 ÷ 换气次数，取中位数（更抗个别异常值）
        volume = (s / c).replace([np.inf, -np.inf], np.nan).dropna()
        ratio = float(volume.median())
        if not np.isfinite(ratio) or ratio <= 0:
            raise ValueError("无法计算有效房间体积（送风量或换气次数数据异常）")

        fig, ax1 = plt.subplots(figsize=(11, 6), dpi=100, constrained_layout=True)
        ax1.plot(valid, s, color="#0F766E", marker="o", markersize=4,
                 linewidth=1.8, label="送风量（左轴）")
        ax1.set_xlabel("日期", labelpad=12)
        ax1.set_ylabel("送风量 (m³/h)", color="#0F766E")
        ax1.tick_params(axis="y", labelcolor="#0F766E")
        ax1.grid(True, alpha=0.3)

        ax2 = ax1.twinx()
        ax2.plot(valid, c, color="#B45309", marker="s", markersize=4,
                 linewidth=1.8, linestyle="--", label="换气次数（右轴）")
        ax2.set_ylabel("换气次数 (次/h)", color="#B45309")
        ax2.tick_params(axis="y", labelcolor="#B45309")

        #关键：右轴范围 = 左轴范围 ÷ 体积，两轴都从 0 起，让两条折线贴合
        y_max = float(s.max())
        ax1.set_ylim(0, y_max * 1.1)
        ax2.set_ylim(0, y_max * 1.1 / ratio)

        #合并左右轴的图例
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="best")

        ax1.set_title(f"{room} · 送风量 vs 换气次数（体积≈{ratio:.1f} m³）",
                      fontsize=14, fontweight="bold")
        plt.setp(ax1.get_xticklabels(), rotation=30, ha="right")
        return fig

    #结果展示辅助
    def _close_result_figures(self):
        #反复「生成图表」时，先关掉旧图表对应的 figure：QTabWidget 移除
        #控件不会释放底层 matplotlib Figure，不关闭会一直残留在全局池里，
        #导致内存随操作次数持续上涨。
        for i in range(self.result_tabs.count()):
            w = self.result_tabs.widget(i)
            if hasattr(w, "figure"):
                plt.close(w.figure)

    def _clear_result_tabs(self):
        self._close_result_figures()
        self.result_tabs.clear()

    def _show_tab(self, widget, name):
        for i in range(self.result_tabs.count()):
            if self.result_tabs.tabText(i) == name:
                old = self.result_tabs.widget(i)
                if hasattr(old, "figure"):
                    plt.close(old.figure)
                self.result_tabs.removeTab(i)
                break
        self.result_tabs.addTab(widget, name)
        self.result_tabs.setCurrentIndex(self.result_tabs.count() - 1)
