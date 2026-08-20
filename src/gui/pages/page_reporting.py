import pandas as pd
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QTableWidget, QTableWidgetItem, QTextEdit,
    QFileDialog, QMessageBox, QHeaderView, QInputDialog,
    QComboBox, QTabWidget, QScrollArea, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter

import config
from src.data_store import data_store
from src.reporting.analysis import (
    compute_compliance, compute_room_volume, compute_period_growth,
    compute_air_changes_compliance,
    compute_bacteria_compliance, compute_bacteria_growth,
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
        self.air_change_df = None           #换气次数达标检查
        self.bacteria_summary = None        #浮游菌：合规判定汇总
        self.bacteria_exceed = None         #浮游菌：超标明细
        self.bacteria_growth = None         #浮游菌：逐时段环比变化
        self.growth_threshold = 50.0        #环比增长超过该百分比(%)才标红
        self.bacteria_growth_threshold = 50.0  #浮游菌环比增长超过该百分比(%)才标红
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
        self.air_change_df = None
        self.bacteria_summary = None
        self.bacteria_exceed = None
        self.bacteria_growth = None
        self.growth_threshold = 50.0
        self.bacteria_growth_threshold = 50.0
        self.data_status.setText("尚未加载")
        self.data_status.setStyleSheet("color: #A8A29E;")
        self.load_btn.setEnabled(True)
        self.gen_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.interp_text.clear()
        for t in (self.compliance_table, self.exceed_table,
                  self.volume_table, self.volume_anomaly_table,
                  self.air_change_table,
                  self.bacteria_table, self.bacteria_exceed_table,
                  self.bacteria_growth_table):
            t.setRowCount(0)
            t.setColumnCount(0)
        self.growth_subtabs.clear()
        self.growth_tables.clear()
        self.growth_threshold_label.setText("标红阈值：未设置")
        self.bacteria_growth_threshold_label.setText("标红阈值：未设置")
        #熄灭 tab 上的红点
        self._set_tab_badge(self.comp_tabs, 1, "超标明细", False)
        self._set_tab_badge(self.vol_tabs, 1, "异常明细", False)
        self._set_tab_badge(self.bacteria_tabs, 1, "超标明细", False)

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

        bar.addWidget(QLabel("区域："))
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["全部", "实验区", "车间区", "百级区"])
        self.zone_combo.setCurrentText("全部")
        self.zone_combo.currentIndexChanged.connect(self._on_zone_changed)
        bar.addWidget(self.zone_combo)

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
        self.growth_container = QWidget()
        growth_container = self.growth_container
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
        # 环比变化子表：按数据里实际存在的粒径动态创建（见 _fill_growth_table）
        self.growth_subtabs = QTabWidget()
        self.growth_tables = {}  # 粒径 -> QTableWidget
        growth_layout.addWidget(self.growth_subtabs)

        self.comp_tabs.addTab(self.compliance_table, "判定汇总")
        self.comp_tabs.addTab(self.exceed_table, "超标明细")
        self.comp_tabs.addTab(growth_container, "环比变化")
        comp_layout.addWidget(self.comp_tabs)
        layout.addWidget(comp_group)

        # 板块二：房间体积一致性
        vol_group = QGroupBox("房间体积一致性 — 送风量 ÷ 换气次数 vs 标准体积")
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

        # 板块三：换气次数达标检查
        air_group = QGroupBox("换气次数达标检查 — 是否满足换气次数标准")
        air_layout = QVBoxLayout(air_group)
        air_hint = QLabel("黄色 = 未满足换气标准（实验区≥20 次/h，车间区≥15 次/h）")
        air_hint.setStyleSheet("color: #92400E; font-weight: 600;")
        air_layout.addWidget(air_hint)
        self.air_change_table = QTableWidget()
        self.air_change_table.setAlternatingRowColors(True)
        self.air_change_table.setMinimumHeight(170)
        air_layout.addWidget(self.air_change_table)
        layout.addWidget(air_group)

        # 板块四：浮游菌 — 平均浓度合规与趋势
        bacteria_group = QGroupBox("浮游菌 — 平均浓度合规与趋势")
        bacteria_layout = QVBoxLayout(bacteria_group)
        self.bacteria_tabs = QTabWidget()
        self.bacteria_table = QTableWidget()
        self.bacteria_table.setAlternatingRowColors(True)
        self.bacteria_table.setMinimumHeight(170)
        self.bacteria_exceed_table = QTableWidget()
        self.bacteria_exceed_table.setAlternatingRowColors(True)
        self.bacteria_exceed_table.setMinimumHeight(170)

        # 环比变化 tab：相邻时段浮游菌平均浓度增长/下降，超阈值标红
        self.bacteria_growth_container = QWidget()
        bacteria_growth_container = self.bacteria_growth_container
        bacteria_growth_layout = QVBoxLayout(bacteria_growth_container)
        bacteria_growth_layout.setContentsMargins(8, 8, 8, 8)
        bacteria_growth_bar = QHBoxLayout()
        bacteria_growth_bar.addWidget(QLabel("相邻时段浮游菌平均浓度环比变化："))
        self.bacteria_growth_threshold_label = QLabel("标红阈值：未设置")
        self.bacteria_growth_threshold_label.setStyleSheet("color: #DC2626; font-weight: 600;")
        bacteria_growth_bar.addWidget(self.bacteria_growth_threshold_label)
        self.bacteria_growth_btn = QPushButton("设置标红阈值(%)")
        self.bacteria_growth_btn.setObjectName("secondaryBtn")
        self.bacteria_growth_btn.clicked.connect(self._ask_bacteria_growth_threshold)
        bacteria_growth_bar.addWidget(self.bacteria_growth_btn)
        bacteria_growth_bar.addStretch()
        bacteria_growth_layout.addLayout(bacteria_growth_bar)

        self.bacteria_growth_table = QTableWidget()
        self.bacteria_growth_table.setAlternatingRowColors(True)
        self.bacteria_growth_table.setMinimumHeight(170)
        bacteria_growth_layout.addWidget(self.bacteria_growth_table)

        self.bacteria_tabs.addTab(self.bacteria_table, "判定汇总")
        self.bacteria_tabs.addTab(self.bacteria_exceed_table, "超标明细")
        self.bacteria_tabs.addTab(bacteria_growth_container, "环比变化")
        bacteria_layout.addWidget(self.bacteria_tabs)
        layout.addWidget(bacteria_group)

        #板块五：业务解读
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

        # 三个判定（后端纯函数）+ 尘埃粒子逐时段环比变化 + 浮游菌
        self.compliance_summary, self.compliance_exceed = compute_compliance(self.df)
        self.volume_summary, self.volume_anomaly = compute_room_volume(self.df)
        self.growth_df = compute_period_growth(self.df)
        self.air_change_df = compute_air_changes_compliance(self.df)
        self.bacteria_summary, self.bacteria_exceed = compute_bacteria_compliance(self.df)
        self.bacteria_growth = compute_bacteria_growth(self.df)

        self._render()

        # 报告生成成功：标记本步骤完成，侧边栏「结果报告」打勾
        if hasattr(self, "main_window") and self.main_window:
            self.main_window.mark_step_completed(3)

    # —— 区域筛选：判定本身已按房间自动套标准，这里只按「区域」下拉框过滤显示 ——
    def _zone_rooms(self):
        zone = self.zone_combo.currentText()
        if zone == "全部":
            return None
        if zone == "实验区":
            return set(config.LAB_ROOMS)
        if zone == "车间区":
            return set(config.WORKSHOP_ROOMS)
        if zone == "百级区":
            return set(config.HUNDRED_GRADE_ROOMS)
        return None

    def _filter_by_zone(self, df):
        rooms = self._zone_rooms()
        if df is None or df.empty or rooms is None or "房间" not in df.columns:
            return df
        return df[df["房间"].isin(rooms)]

    def _on_zone_changed(self):
        # 已生成报告时才重绘（否则没有结果可筛）
        if self.compliance_summary is not None:
            self._render()

    def _render(self):
        comp = self._filter_by_zone(self.compliance_summary)
        exceed = self._filter_by_zone(self.compliance_exceed)
        vol = self._filter_by_zone(self.volume_summary)
        vol_anom = self._filter_by_zone(self.volume_anomaly)
        growth = self._filter_by_zone(self.growth_df)
        bacteria = self._filter_by_zone(self.bacteria_summary)
        bacteria_exceed = self._filter_by_zone(self.bacteria_exceed)
        bacteria_growth = self._filter_by_zone(self.bacteria_growth)

        #悬浮提示：合规性——超标明细按 (房间, 粒径) 分组
        comp_tips = {}
        if exceed is not None and not exceed.empty:
            for (room, size), g in exceed.groupby(["房间", "粒径"]):
                tips = [f"{r['日期']}：实测 {r['实测值']}（限值 {r['国标限值']}）"
                        for _, r in g.iterrows()]
                comp_tips[(room, size)] = "【超标原因推测】\n" + "\n".join(tips)

        #悬浮提示：体积——异常明细按房间分组
        vol_tips = {}
        if vol_anom is not None and not vol_anom.empty:
            for room, g in vol_anom.groupby("房间"):
                tips = [f"{r['日期']} · {r['方向']}：{r['判定/可能原因']}"
                        for _, r in g.iterrows()]
                vol_tips[room] = "【异常原因推测】\n" + "\n".join(tips)

        #悬浮提示：浮游菌——超标明细按房间分组
        bacteria_tips = {}
        if bacteria_exceed is not None and not bacteria_exceed.empty:
            for room, g in bacteria_exceed.groupby("房间"):
                tips = [f"{r['日期']}：实测 {r['实测值']}（标准 {r['标准']}）"
                        for _, r in g.iterrows()]
                bacteria_tips[room] = "【超标原因推测】\n" + "\n".join(tips)

        #填充表格（超标/异常的行红色高亮，异常行带悬浮提示）
        self._fill_table(
            self.compliance_table, comp,
            warn_col="是否超标", highlight_cols=["是否超标", "超标次数", "最大值"],
            tooltip_for=lambda row: comp_tips.get((row["房间"], row["粒径"]), ""),
        )
        self._fill_table(self.exceed_table, exceed)
        self._fill_table(
            self.volume_table, vol,
            warn_col="是否异常", highlight_cols=["是否异常", "异常次数"],
            tooltip_for=lambda row: vol_tips.get(row["房间"], ""),
        )
        self._fill_table(
            self.volume_anomaly_table, vol_anom,
            warn_col="方向", highlight_cols=["方向", "偏差(%)", "判定/可能原因"],
        )

        # 浮游菌：合规判定汇总 + 超标明细
        self._fill_table(
            self.bacteria_table, bacteria,
            warn_col="是否超标", highlight_cols=["是否超标", "超标次数", "最大值"],
            tooltip_for=lambda row: bacteria_tips.get(row["房间"], ""),
        )
        self._fill_table(self.bacteria_exceed_table, bacteria_exceed)

        #tab 红点：有明细才点亮
        self._set_tab_badge(
            self.comp_tabs, 1, "超标明细",
            exceed is not None and not exceed.empty,
        )
        self._set_tab_badge(
            self.vol_tabs, 1, "异常明细",
            vol_anom is not None and not vol_anom.empty,
        )
        self._set_tab_badge(
            self.bacteria_tabs, 1, "超标明细",
            bacteria_exceed is not None and not bacteria_exceed.empty,
        )

        self._fill_growth_table()
        self._fill_air_changes_table()
        self._fill_bacteria_growth_table()

        self._auto_interpret(comp, vol, vol_anom, growth)
        self.export_btn.setEnabled(True)

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

    # —— 环比变化：点「设置标红阈值」按钮时弹窗问阈值（不挂在 tab 点击上，避免
    #     模态弹窗打断 tab 切换导致「进不去」） ——
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

    def _ask_bacteria_growth_threshold(self):
        # 无浮游菌环比数据时（未生成报告或没有浮游菌数据）不弹窗
        if self.bacteria_growth is None or self.bacteria_growth.empty:
            return
        threshold, ok = QInputDialog.getDouble(
            self, "设置浮游菌标红阈值",
            "相邻时段浮游菌平均浓度环比增长超过多少（%）需要标红？",
            self.bacteria_growth_threshold, 0.0, 100000.0, 1,
        )
        if ok:
            self.bacteria_growth_threshold = threshold
            self._fill_bacteria_growth_table()

    def _growth_cell_text(self, col: str, val) -> str:
        # 上期值为空（首个时段）显示「—」；变化率首个时段已记为 0%，显示「0%」
        if pd.isna(val):
            return "—"
        if col == "变化率(%)":
            v = float(val)
            if v == 0:
                return "0%"
            return f"+{v:.1f}%" if v > 0 else f"{v:.1f}%"
        if col in ("本期值", "上期值"):
            return str(int(round(float(val))))
        return str(val)

    def _fill_growth_table(self):
        self.growth_threshold_label.setText(
            f"标红阈值：环比增长 > {self.growth_threshold:g}%"
        )
        # 按数据里实际存在的粒径动态重建子表（实现「只分析上传的粒径」）
        self.growth_subtabs.clear()
        self.growth_tables.clear()

        growth = self._filter_by_zone(self.growth_df)
        if growth is None or growth.empty:
            return

        present_sizes = [cn for cn in config.PARTICLE_LIMITS.keys()
                         if (growth["粒径"] == cn).any()]

        for cn in present_sizes:
            table = QTableWidget()
            table.setAlternatingRowColors(True)
            table.setMinimumHeight(170)
            self.growth_subtabs.addTab(table, cn)
            self.growth_tables[cn] = table

            sub = growth[growth["粒径"] == cn]
            # 透视：纵轴=房间，横轴=监测日期，单元格=环比变化率(%)
            mat = sub.pivot_table(index="房间", columns="日期",
                                  values="变化率(%)", aggfunc="first")
            date_cols = sorted(mat.columns)   # 日期已统一成 %Y-%m-%d，字典序即时间序
            mat = mat.reindex(columns=date_cols).sort_index()

            cols = ["房间"] + date_cols
            table.setRowCount(len(mat))
            table.setColumnCount(len(cols))
            table.setHorizontalHeaderLabels(cols)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
            table.horizontalHeader().setStretchLastSection(True)

            for i, room in enumerate(mat.index):
                table.setItem(i, 0, QTableWidgetItem(str(room)))
                for j, d in enumerate(mat.columns):
                    val = mat.iloc[i, j]
                    cell = QTableWidgetItem(self._growth_cell_text("变化率(%)", val))
                    # 只有环比增长超过阈值才标红（下降、首时段 0%、空值不标红）
                    if pd.notna(val) and float(val) > self.growth_threshold:
                        cell.setForeground(QColor("#DC2626"))
                        cell.setBackground(QColor("#FEE2E2"))
                        f = cell.font()
                        f.setBold(True)
                        cell.setFont(f)
                    table.setItem(i, j + 1, cell)

    def _fill_air_changes_table(self):
        self.air_change_table.setRowCount(0)
        self.air_change_table.setColumnCount(0)

        air = self._filter_by_zone(self.air_change_df)
        if air is None or air.empty:
            return

        # 透视：纵轴=房间，横轴=日期，单元格=换气次数
        mat = air.pivot_table(index="房间", columns="日期",
                              values="换气次数", aggfunc="first")
        date_cols = sorted(mat.columns)
        mat = mat.reindex(columns=date_cols).sort_index()

        # 每个房间的标准（实验区≥20 / 车间区≥15）
        std_map = {
            room: config.AIR_CHANGE_STD.get(config.room_zone(room) or "车间区")
            for room in mat.index
        }

        cols = ["房间", "标准"] + date_cols
        self.air_change_table.setRowCount(len(mat))
        self.air_change_table.setColumnCount(len(cols))
        self.air_change_table.setHorizontalHeaderLabels(cols)
        self.air_change_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.air_change_table.horizontalHeader().setStretchLastSection(True)

        for i, room in enumerate(mat.index):
            self.air_change_table.setItem(i, 0, QTableWidgetItem(str(room)))
            std = std_map.get(room)
            self.air_change_table.setItem(i, 1, QTableWidgetItem(f"≥{std}" if std is not None else "—"))
            for j, d in enumerate(mat.columns):
                val = mat.iloc[i, j]
                if pd.isna(val):
                    cell = QTableWidgetItem("—")
                else:
                    cell = QTableWidgetItem(str(int(round(float(val)))))
                    # 低于标准的单元格黄色高亮
                    if std is not None and float(val) < std:
                        cell.setForeground(QColor("#92400E"))
                        cell.setBackground(QColor("#FEF9C3"))
                        f = cell.font()
                        f.setBold(True)
                        cell.setFont(f)
                        cell.setToolTip(f"未满足换气标准（标准≥{std}）")
                self.air_change_table.setItem(i, j + 2, cell)

    def _fill_bacteria_growth_table(self):
        self.bacteria_growth_threshold_label.setText(
            f"标红阈值：环比增长 > {self.bacteria_growth_threshold:g}%"
        )
        self.bacteria_growth_table.setRowCount(0)
        self.bacteria_growth_table.setColumnCount(0)

        bg = self._filter_by_zone(self.bacteria_growth)
        if bg is None or bg.empty:
            return

        # 透视：纵轴=房间，横轴=日期，单元格=环比变化率(%)（相对上一时段涨跌）
        mat = bg.pivot_table(index="房间", columns="日期",
                             values="本期值", aggfunc="first")
        rate_mat = bg.pivot_table(index="房间", columns="日期",
                                  values="变化率(%)", aggfunc="first")
        prev_mat = bg.pivot_table(index="房间", columns="日期",
                                  values="上期值", aggfunc="first")

        date_cols = sorted(mat.columns)
        mat = mat.reindex(columns=date_cols).sort_index()
        rate_mat = rate_mat.reindex(index=mat.index, columns=date_cols)
        prev_mat = prev_mat.reindex(index=mat.index, columns=date_cols)

        cols = ["房间"] + date_cols
        self.bacteria_growth_table.setRowCount(len(mat))
        self.bacteria_growth_table.setColumnCount(len(cols))
        self.bacteria_growth_table.setHorizontalHeaderLabels(cols)
        self.bacteria_growth_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.bacteria_growth_table.horizontalHeader().setStretchLastSection(True)

        for i, room in enumerate(mat.index):
            self.bacteria_growth_table.setItem(i, 0, QTableWidgetItem(str(room)))
            for j, d in enumerate(mat.columns):
                val = mat.iloc[i, j]    # 本期浓度值
                rate = rate_mat.iloc[i, j]  # 环比变化率(%)
                prev = prev_mat.iloc[i, j]  # 上期浓度值
                if pd.isna(val):
                    # 该房间这个日期没有监测（2 月 22/23 两区日期错开）
                    cell = QTableWidgetItem("—")
                else:
                    # 单元格直接显示相对上一时段的涨跌百分比：+X% 上升 / -X% 下降 / 0% 持平
                    cell = QTableWidgetItem(self._growth_cell_text("变化率(%)", rate))
                    if pd.isna(rate):
                        # 上期为 0 时百分比无意义（0 不能作除数）
                        cell.setToolTip(f"上期值为 0，无法计算环比（本期 {float(val):.2f}）")
                    elif float(rate) > self.bacteria_growth_threshold:
                        # 环比增长超过阈值标红加粗
                        cell.setForeground(QColor("#DC2626"))
                        cell.setBackground(QColor("#FEE2E2"))
                        f = cell.font()
                        f.setBold(True)
                        cell.setFont(f)
                        cell.setToolTip(
                            f"环比暴增：上期 {float(prev):.2f} → 本期 {float(val):.2f}，"
                            f"环比 +{float(rate):.1f}%"
                        )
                    elif pd.isna(prev):
                        # 首个监测时段，无上一时段可比较（显示 0% 作为基准）
                        cell.setToolTip("首个监测时段（基准，无上一时段可比较）")
                    else:
                        cell.setToolTip(
                            f"上期 {float(prev):.2f} → 本期 {float(val):.2f}，"
                            f"环比 {float(rate):+.1f}%"
                        )
                self.bacteria_growth_table.setItem(i, j + 1, cell)

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
    def _auto_interpret(self, comp, vol, vol_anom, growth):
        lines = ["报告概览", ""]
        lines.append(f"- 数据总行数：{len(self.df)}")
        lines.append(f"- 显示区域：{self.zone_combo.currentText()}")

        #板块一：合规性
        lines.append("")
        lines.append("一、合规性判定（尘埃粒子）")
        if comp is not None and not comp.empty:
            bad = comp[comp["是否超标"] == "是"]
            if bad.empty:
                lines.append("所有房间的尘埃粒子浓度均未超过对应区域国标限值。")
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
        if growth is not None and not growth.empty:
            spike = growth[
                growth["变化率(%)"].notna()
                & (growth["变化率(%)"] > self.growth_threshold)
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
        lines.append("二、房间体积一致性（送风量 ÷ 换气次数 vs 标准体积）")
        if vol is not None and not vol.empty:
            bad = vol[vol["是否异常"] == "是"]
            if bad.empty:
                lines.append(
                    f"所有房间体积与标准体积相差均未超过 {VOLUME_DEVIATION_RATIO * 100:.0f}%。"
                )
            else:
                lines.append(
                    f"共 {len(bad)} 个房间体积与标准体积相差超过 "
                    f"{VOLUME_DEVIATION_RATIO * 100:.0f}%："
                )
                for _, r in bad.iterrows():
                    lines.append(f"  - {r['房间']}：{r['异常次数']} 次异常")

                #逐条列出异常原因
                if vol_anom is not None and not vol_anom.empty:
                    lines.append("")
                    lines.append("异常明细与可能原因：")
                    for _, a in vol_anom.iterrows():
                        lines.append(
                            f"  - {a['日期']} · {a['房间']}：体积 {a['体积(m³)']} m³"
                            f"（{a['方向']}，标准体积 {a['标准体积(m³)']} m³）→ {a['判定/可能原因']}"
                        )
        else:
            lines.append("未检测到风量数据，无法计算房间体积。")

        # —— 板块三：换气次数达标 ——
        lines.append("")
        lines.append("三、换气次数达标检查")
        air = self._filter_by_zone(self.air_change_df)
        if air is not None and not air.empty:
            fail = air[air["是否达标"] == "否"]
            if fail.empty:
                lines.append("所有房间的换气次数均满足对应标准。")
            else:
                lines.append(f"共 {len(fail)} 条记录未满足换气标准（表格中黄色高亮）：")
                for _, a in fail.iterrows():
                    lines.append(
                        f"  - {a['房间']} · {a['日期']}：换气次数 {a['换气次数']}，"
                        f"标准 {a['标准']}"
                    )
        else:
            lines.append("未检测到换气次数数据。")

        # —— 板块四：浮游菌 ——
        lines.append("")
        lines.append("四、浮游菌平均浓度合规与趋势")
        bac = self._filter_by_zone(self.bacteria_summary)
        if bac is not None and not bac.empty:
            bad = bac[bac["是否超标"] == "是"]
            if bad.empty:
                lines.append("所有房间的浮游菌平均浓度均未超过对应标准。")
            else:
                lines.append(f"共 {len(bad)} 个房间浮游菌超标：")
                for _, r in bad.iterrows():
                    lines.append(
                        f"  - {r['房间']}：最大值 {r['最大值']}，标准 {r['标准']}，"
                        f"超标 {r['超标次数']} 次"
                    )
        else:
            lines.append("未检测到浮游菌数据。")

        # 浮游菌逐时段环比变化
        bacg = self._filter_by_zone(self.bacteria_growth)
        if bacg is not None and not bacg.empty:
            spike = bacg[
                bacg["变化率(%)"].notna()
                & (bacg["变化率(%)"] > self.bacteria_growth_threshold)
            ]
            if not spike.empty:
                lines.append(
                    f"共 {len(spike)} 个时段浮游菌环比增长超过 "
                    f"{self.bacteria_growth_threshold:g}%（已在表格中标红）："
                )
                for _, s in spike.iterrows():
                    lines.append(
                        f"  - {s['房间']} · {s['日期']}：本期 {s['本期值']}，"
                        f"环比 {float(s['变化率(%)']):+.1f}%"
                    )

        #结论建议
        lines.append("")
        lines.append("五、结论与建议")
        lines.append("1. 超标房间请重点核查送风系统、高效过滤器及人员操作。")
        lines.append("2. 体积异常的房间，请按上表原因逐一排查（录入核对 / 风机频率 / 回风阀 / 过滤器 / 风管）。")
        lines.append("3. 换气次数未达标的房间，请核查送风量是否足够、风管是否漏风。")
        lines.append("4. 浮游菌超标或暴增的房间，请核查洁净区消毒、人员进出及采样操作规范。")

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
            if self.air_change_df is not None and not self.air_change_df.empty:
                sections["换气次数达标"] = self.air_change_df
            if self.bacteria_summary is not None and not self.bacteria_summary.empty:
                sections["浮游菌合规判定"] = self.bacteria_summary
            if self.bacteria_exceed is not None and not self.bacteria_exceed.empty:
                sections["浮游菌超标明细"] = self.bacteria_exceed
            if self.bacteria_growth is not None and not self.bacteria_growth.empty:
                sections["浮游菌环比变化"] = self.bacteria_growth
            sections["业务解读"] = self.interp_text.toPlainText()

            export_to_excel(sections, file_path)
            QMessageBox.information(self, "导出成功", f"报告已保存到:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))
