import pandas as pd
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTableWidget, QTableWidgetItem, QTextEdit,
    QFileDialog, QMessageBox, QHeaderView, QInputDialog,
    QComboBox, QTabWidget, QScrollArea, QFrame,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter

import config
from src.data_store import data_store
from src.reporting.analysis import (
    compute_compliance, compute_room_volume, compute_period_growth,
    VOLUME_DEVIATION_RATIO,
)
from src.reporting.exporter import export_to_excel


class ReportingPage(QWidget):
    def __init__(self):
        super().__init__()
        self.df = None                      
        self.compliance_summary = None      
        self.compliance_exceed = None       #超标明细
        self.volume_summary = None          #房间体积一致性：房间汇总
        self.volume_anomaly = None          #房间体积一致性：异常明细
        self.growth_df = None               #尘埃粒子：逐时段环比变化
        self.growth_threshold = 50.0        #环比增长超过该百分比(%)才标红
        self._red_dot = None                #红色小圆点图标（懒加载缓存）
        self._build_ui()

    def reset(self):
        #清空已加载数据与结果（供「清空数据库」调用）
        self.df = None
        self.compliance_summary = None
        self.compliance_exceed = None
        self.volume_summary = None
        self.volume_anomaly = None
        self.growth_df = None
        self.growth_threshold = 50.0
        self.data_status.setText("尚未加载")
        self.data_status.setStyleSheet("color: #A8A29E;")
        self.load_btn.setEnabled(True)
        self.gen_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.interp_text.clear()
        for t in (self.compliance_table, self.exceed_table,
                  self.volume_table, self.volume_anomaly_table):
            t.setRowCount(0)
            t.setColumnCount(0)
        self.growth_table.setRowCount(0)
        self.growth_table.setColumnCount(0)
        self.growth_threshold_label.setText("标红阈值：未设置")
        #熄灭 tab 上的红点
        self._set_tab_badge(self.comp_tabs, 1, "超标明细", False)
        self._set_tab_badge(self.vol_tabs, 1, "异常明细", False)

    #UI
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        #报告内容较长，用滚动区承载，窄屏出现横向滚动
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        content = QWidget()
        content.setMinimumWidth(900)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        title = QLabel("第四步：结果报告")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(
            "洁净车间专属分析报告：尘埃粒子合规性判定 + 房间体积一致性检查（逐日期定位异常并推断原因），自动生成业务解读，支持导出 Excel。"
        )
        desc.setObjectName("pageDescription")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        #顶部操作栏
        bar = QHBoxLayout()
        self.load_btn = QPushButton("加载数据")
        self.load_btn.setObjectName("secondaryBtn")
        self.load_btn.clicked.connect(self._load_data)
        bar.addWidget(self.load_btn)

        self.data_status = QLabel("尚未加载")
        self.data_status.setStyleSheet("color: #A8A29E;")
        bar.addWidget(self.data_status)
        bar.addStretch()

        bar.addWidget(QLabel("洁净级别："))
        self.class_combo = QComboBox()
        self.class_combo.addItems(config.CLEANROOM_CLASSES)
        self.class_combo.setCurrentText(config.DEFAULT_CLEANROOM_CLASS)
        bar.addWidget(self.class_combo)

        self.gen_btn = QPushButton("生成报告")
        self.gen_btn.setObjectName("primaryBtn")
        self.gen_btn.setEnabled(False)
        self.gen_btn.clicked.connect(self._generate_report)
        bar.addWidget(self.gen_btn)

        self.export_btn = QPushButton("导出 Excel")
        self.export_btn.setObjectName("successBtn")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export_report)
        bar.addWidget(self.export_btn)
        layout.addLayout(bar)

        #板块一：合规性判定
        comp_group = QGroupBox("合规性判定 — 尘埃粒子 vs 国标限值")
        comp_layout = QVBoxLayout(comp_group)
        self.comp_tabs = QTabWidget()
        self.compliance_table = QTableWidget()
        self.compliance_table.setAlternatingRowColors(True)
        self.compliance_table.setMinimumHeight(170)
        self.exceed_table = QTableWidget()
        self.exceed_table.setAlternatingRowColors(True)
        self.exceed_table.setMinimumHeight(170)

        # 环比变化 tab：相邻时段尘埃粒子数增长/下降，超阈值标红
        growth_container = QWidget()
        growth_layout = QVBoxLayout(growth_container)
        growth_layout.setContentsMargins(8, 8, 8, 8)
        growth_bar = QHBoxLayout()
        growth_bar.addWidget(QLabel("相邻时段尘埃粒子数环比变化："))
        self.growth_threshold_label = QLabel("标红阈值：未设置")
        self.growth_threshold_label.setStyleSheet("color: #DC2626; font-weight: 600;")
        growth_bar.addWidget(self.growth_threshold_label)
        self.growth_btn = QPushButton("设置标红阈值(%)")
        self.growth_btn.setObjectName("secondaryBtn")
        self.growth_btn.clicked.connect(self._ask_growth_threshold)
        growth_bar.addWidget(self.growth_btn)
        growth_bar.addStretch()
        growth_layout.addLayout(growth_bar)
        self.growth_table = QTableWidget()
        self.growth_table.setAlternatingRowColors(True)
        self.growth_table.setMinimumHeight(170)
        growth_layout.addWidget(self.growth_table)

        self.comp_tabs.addTab(self.compliance_table, "判定汇总")
        self.comp_tabs.addTab(self.exceed_table, "超标明细")
        self.comp_tabs.addTab(growth_container, "环比变化")
        self.comp_tabs.tabBarClicked.connect(self._on_comp_tab_clicked)
        comp_layout.addWidget(self.comp_tabs)
        layout.addWidget(comp_group)

        # 板块二：房间体积一致性
        vol_group = QGroupBox("房间体积一致性 — 送风量 ÷ 换气次数（应恒定）")
        vol_layout = QVBoxLayout(vol_group)
        self.vol_tabs = QTabWidget()
        self.volume_table = QTableWidget()
        self.volume_table.setAlternatingRowColors(True)
        self.volume_table.setMinimumHeight(170)
        self.volume_anomaly_table = QTableWidget()
        self.volume_anomaly_table.setAlternatingRowColors(True)
        self.volume_anomaly_table.setMinimumHeight(170)
        self.vol_tabs.addTab(self.volume_table, "房间汇总")
        self.vol_tabs.addTab(self.volume_anomaly_table, "异常明细")
        vol_layout.addWidget(self.vol_tabs)
        layout.addWidget(vol_group)

        #板块三：业务解读
        interp_group = QGroupBox("业务解读与结论")
        interp_layout = QVBoxLayout(interp_group)
        self.interp_text = QTextEdit()
        self.interp_text.setPlaceholderText("生成报告后，将在此自动生成业务解读...")
        self.interp_text.setMinimumHeight(200)
        interp_layout.addWidget(self.interp_text)
        layout.addWidget(interp_group)

        layout.addStretch()

        self.scroll.setWidget(content)
        outer.addWidget(self.scroll)

    # 数据加载
    def _load_data(self):
        try:
            df = data_store.get_for_analysis()
            if df is None or df.empty:
                QMessageBox.warning(self, "提示", "暂无可分析数据，请先完成「数据导入」与「数据清洗」。")
                return

            skip = ["id", "import_session_id", "extended_data", "created_at"]
            df = df.drop(columns=[c for c in skip if c in df.columns], errors="ignore")

            # 去重（重复导入产生的重复记录）
            key = [c for c in ["record_date", "room_name", "room_adjacent",
                               "particle_size", "indicator_name"] if c in df.columns]
            df = df.drop_duplicates(subset=key, keep="first")

            if "record_date" in df.columns:
                df["record_date"] = pd.to_datetime(df["record_date"], errors="coerce")

            self.df = df
            self.data_status.setText(f"{len(df)} 行")
            self.data_status.setStyleSheet("color: #0F766E;")
            self.gen_btn.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "加载失败", str(e))

    def load_from_store(self):
        #页面切换进入时自动加载；已加载或无数据时静默跳过
        if self.df is None and data_store.get_for_analysis() is not None:
            self._load_data()

    #生成报告
    def _generate_report(self):
        if self.df is None:
            return

        cls = self.class_combo.currentText()

        #两个判定（后端纯函数）+ 尘埃粒子逐时段环比变化
        self.compliance_summary, self.compliance_exceed = compute_compliance(self.df, cls)
        self.volume_summary, self.volume_anomaly = compute_room_volume(self.df)
        self.growth_df = compute_period_growth(self.df)

        #悬浮提示：合规性——超标明细按 (房间, 粒径) 分组
        comp_tips = {}
        if self.compliance_exceed is not None and not self.compliance_exceed.empty:
            for (room, size), g in self.compliance_exceed.groupby(["房间", "粒径"]):
                tips = [f"{r['日期']}：实测 {r['实测值']}（限值 {r['国标限值']}）"
                        for _, r in g.iterrows()]
                comp_tips[(room, size)] = "【超标原因推测】\n" + "\n".join(tips)

        #悬浮提示：体积——异常明细按房间分组
        vol_tips = {}
        if self.volume_anomaly is not None and not self.volume_anomaly.empty:
            for room, g in self.volume_anomaly.groupby("房间"):
                tips = [f"{r['日期']} · {r['方向']}：{r['判定/可能原因']}"
                        for _, r in g.iterrows()]
                vol_tips[room] = "【异常原因推测】\n" + "\n".join(tips)

        #填充表格（超标/异常的行红色高亮，异常行带悬浮提示）
        self._fill_table(
            self.compliance_table, self.compliance_summary,
            warn_col="是否超标", highlight_cols=["是否超标", "超标次数", "最大值"],
            tooltip_for=lambda row: comp_tips.get((row["房间"], row["粒径"]), ""),
        )
        self._fill_table(self.exceed_table, self.compliance_exceed)
        self._fill_table(
            self.volume_table, self.volume_summary,
            warn_col="是否异常", highlight_cols=["是否异常", "异常次数"],
            tooltip_for=lambda row: vol_tips.get(row["房间"], ""),
        )
        self._fill_table(
            self.volume_anomaly_table, self.volume_anomaly,
            warn_col="方向", highlight_cols=["方向", "偏差(m³)", "判定/可能原因"],
        )

        #tab 红点：有明细才点亮
        self._set_tab_badge(
            self.comp_tabs, 1, "超标明细",
            self.compliance_exceed is not None and not self.compliance_exceed.empty,
        )
        self._set_tab_badge(
            self.vol_tabs, 1, "异常明细",
            self.volume_anomaly is not None and not self.volume_anomaly.empty,
        )

        self._fill_growth_table()

        self._auto_interpret()
        self.export_btn.setEnabled(True)

        # 报告生成成功：标记本步骤完成，侧边栏「结果报告」打勾
        if hasattr(self, "main_window") and self.main_window:
            self.main_window.mark_step_completed(3)

    # 表格渲染辅助
    def _format_status(self, col: str, val) -> str:
        #状态列：把纯文字「是/否」升级为图标 + 文字
        if col == "是否超标":
            return "❌ 超标" if val == "是" else "✅ 正常"
        if col == "是否异常":
            if val == "是":
                return "⚠️ 异常"
            if val == "样本不足":
                return "— 样本不足"
            return "✅ 正常"
        return str(val)

    def _fill_table(self, table: QTableWidget, df: pd.DataFrame,
                    warn_col: str = None, highlight_cols: list = None,
                    tooltip_for=None):
        table.setRowCount(0)
        table.setColumnCount(0)

        if df is None or df.empty:
            return

        cols = list(df.columns)
        table.setRowCount(len(df))
        table.setColumnCount(len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)

        for i, (_, row) in enumerate(df.iterrows()):
            bad_value = row.get(warn_col) if warn_col else None
            is_bad = bad_value in ("是", "偏高", "偏低")
            tooltip = tooltip_for(row) if tooltip_for else ""
            for j, col in enumerate(cols):
                item = QTableWidgetItem(self._format_status(col, row[col]))
                if is_bad and col in (highlight_cols or []):
                    item.setForeground(QColor("#DC2626"))
                    item.setBackground(QColor("#FEE2E2"))
                if tooltip:
                    item.setToolTip(tooltip)
                table.setItem(i, j, item)

    # —— 环比变化：点「环比变化」tab 时弹窗问阈值 ——
    def _on_comp_tab_clicked(self, index: int):
        # tab 顺序：0=判定汇总 1=超标明细 2=环比变化
        if index == 2:
            # 等 tab 切换完成后再弹窗：若在 tabBarClicked 里立刻弹模态框，
            # 会吞掉后续「鼠标松开」事件，导致 tab 切不过去、表格显示不出来。
            QTimer.singleShot(0, self._ask_growth_threshold)

    def _ask_growth_threshold(self):
        # 无环比数据时（未生成报告或没有尘埃粒子数据）不弹窗
        if self.growth_df is None or self.growth_df.empty:
            return
        threshold, ok = QInputDialog.getDouble(
            self, "设置标红阈值",
            "相邻时段尘埃粒子环比增长超过多少（%）需要标红？",
            self.growth_threshold, 0.0, 100000.0, 1,
        )
        if ok:
            self.growth_threshold = threshold
            self._fill_growth_table()

    def _growth_cell_text(self, col: str, val) -> str:
        # 上期值/变化率为空（首个时段）显示「—」
        if pd.isna(val):
            return "—"
        if col == "变化率(%)":
            v = float(val)
            return f"{v:+.1f}%" if v >= 0 else f"{v:.1f}%"
        if col in ("本期值", "上期值"):
            return str(int(round(float(val))))
        return str(val)

    def _fill_growth_table(self):
        self.growth_threshold_label.setText(
            f"标红阈值：环比增长 > {self.growth_threshold:g}%"
        )
        table = self.growth_table
        table.setRowCount(0)
        table.setColumnCount(0)

        if self.growth_df is None or self.growth_df.empty:
            return

        cols = list(self.growth_df.columns)
        table.setRowCount(len(self.growth_df))
        table.setColumnCount(len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)

        for i, (_, row) in enumerate(self.growth_df.iterrows()):
            rate = row.get("变化率(%)")
            # 只有环比增长超过阈值才标红（下降、首时段 NaN 都不标红）
            is_spike = (rate == rate) and (float(rate) > self.growth_threshold)
            for j, col in enumerate(cols):
                item = QTableWidgetItem(self._growth_cell_text(col, row[col]))
                if is_spike:
                    item.setForeground(QColor("#DC2626"))
                    item.setBackground(QColor("#FEE2E2"))
                    if col == "变化率(%)":
                        f = item.font()
                        f.setBold(True)
                        item.setFont(f)
                table.setItem(i, j, item)

    def _set_tab_badge(self, tab_widget: QTabWidget, index: int,
                       base_text: str, has_bad: bool):
        #有异常时给 tab 加红色小圆点图标，无异常时去掉
        tab_widget.setTabText(index, base_text)
        tab_widget.setTabIcon(index, self._red_dot_icon() if has_bad else QIcon())

    def _red_dot_icon(self) -> QIcon:
        #生成一个红色小圆点图标（懒加载缓存）
        if self._red_dot is None:
            pm = QPixmap(10, 10)
            pm.fill(Qt.transparent)
            painter = QPainter(pm)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QColor("#DC2626"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(0, 0, 10, 10)
            painter.end()
            self._red_dot = QIcon(pm)
        return self._red_dot

    #业务解读（自动生成）
    def _auto_interpret(self):
        lines = ["报告概览", ""]
        lines.append(f"- 数据总行数：{len(self.df)}")
        lines.append(f"- 洁净级别：{self.class_combo.currentText()}")

        #板块一：合规性
        lines.append("")
        lines.append("一、合规性判定（尘埃粒子）")
        if self.compliance_summary is not None and not self.compliance_summary.empty:
            bad = self.compliance_summary[self.compliance_summary["是否超标"] == "是"]
            if bad.empty:
                lines.append("所有房间的尘埃粒子浓度均未超过该洁净级别国标限值。")
            else:
                lines.append(f"共 {len(bad)} 个「房间 × 粒径」组合超标：")
                for _, r in bad.iterrows():
                    lines.append(
                        f"  - {r['房间']} · {r['粒径']}：最大值 {r['最大值']}，"
                        f"限值 {r['国标限值']}，超标 {r['超标次数']} 次"
                    )
        else:
            lines.append("未检测到尘埃粒子数据。")

        # 尘埃粒子逐时段环比变化
        if self.growth_df is not None and not self.growth_df.empty:
            spike = self.growth_df[
                self.growth_df["变化率(%)"].notna()
                & (self.growth_df["变化率(%)"] > self.growth_threshold)
            ]
            lines.append("")
            lines.append("尘埃粒子逐时段环比变化：")
            if spike.empty:
                lines.append(
                    f"各时段环比增长均未超过 {self.growth_threshold:g}%，"
                    "未发现相邻时段粒子数暴增。"
                )
            else:
                lines.append(
                    f"共 {len(spike)} 个时段环比增长超过 {self.growth_threshold:g}%"
                    "（已在表格中标红），请重点核查："
                )
                for _, s in spike.iterrows():
                    lines.append(
                        f"  - {s['房间']} · {s['粒径']} · {s['日期']}："
                        f"本期 {int(s['本期值'])}，环比 {float(s['变化率(%)']):+.1f}%"
                    )

        # —— 板块二：体积一致性 ——
        lines.append("")
        lines.append("二、房间体积一致性（送风量 ÷ 换气次数）")
        if self.volume_summary is not None and not self.volume_summary.empty:
            bad = self.volume_summary[self.volume_summary["是否异常"] == "是"]
            if bad.empty:
                lines.append(
                    f"所有房间体积基本恒定（各日期与正常平均值相差均未同时超过 "
                    f"{VOLUME_DEVIATION_M3:.0f} m³ 和 {VOLUME_DEVIATION_RATIO * 100:.0f}%）。"
                )
            else:
                lines.append(
                    f"共 {len(bad)} 个房间存在换气异常（体积与正常平均值相差同时超过 "
                    f"{VOLUME_DEVIATION_RATIO * 100:.0f}%）："
                )
                for _, r in bad.iterrows():
                    lines.append(f"  - {r['房间']}：{r['异常次数']} 次异常")

                #逐条列出异常原因
                if self.volume_anomaly is not None and not self.volume_anomaly.empty:
                    lines.append("")
                    lines.append("异常明细与可能原因：")
                    for _, a in self.volume_anomaly.iterrows():
                        lines.append(
                            f"  - {a['日期']} · {a['房间']}：体积 {a['体积(m³)']} m³"
                            f"（{a['方向']}，正常值 {a['正常平均值(m³)']} m³）→ {a['判定/可能原因']}"
                        )
        else:
            lines.append("未检测到风量数据，无法计算房间体积。")

        #结论建议
        lines.append("")
        lines.append("三、结论与建议")
        lines.append("1. 超标房间请重点核查送风系统、高效过滤器及人员操作。")
        lines.append("2. 体积异常的房间，请按上表原因逐一排查（录入核对 / 风机频率 / 回风阀 / 过滤器 / 风管）。")

        self.interp_text.setPlainText("\n".join(lines))

    #导出
    def _export_report(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出报告", "环境监测数据报告.xlsx", "Excel 文件 (*.xlsx)"
        )
        if not file_path:
            return

        try:
            sections = {}
            if self.compliance_summary is not None and not self.compliance_summary.empty:
                sections["合规性判定"] = self.compliance_summary
            if self.compliance_exceed is not None and not self.compliance_exceed.empty:
                sections["超标明细"] = self.compliance_exceed
            if self.volume_summary is not None and not self.volume_summary.empty:
                sections["体积房间汇总"] = self.volume_summary
            if self.volume_anomaly is not None and not self.volume_anomaly.empty:
                sections["体积异常明细"] = self.volume_anomaly
            if self.growth_df is not None and not self.growth_df.empty:
                sections["尘埃粒子环比变化"] = self.growth_df
            sections["业务解读"] = self.interp_text.toPlainText()

            export_to_excel(sections, file_path)
            QMessageBox.information(self, "导出成功", f"报告已保存到:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))
