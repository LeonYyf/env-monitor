#
# Excel 文件读取与解析模块
# 专门处理洁净车间环境监测 Excel 数据。
# 支持两种 Sheet 格式：
# - 尘埃粒子（WIDE: 房间作为列头）
# - 风量（WIDE+水平重复: 房间为行,多组日期列）
#

import hashlib
import pandas as pd
from pathlib import Path
from typing import Tuple, Dict, List, Optional
import config


class ExcelReader:
    # 洁净车间 Excel 文件读取器

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        self.xl = None

    # ----------------------------------------------------------------
    # 文件信息
    # ----------------------------------------------------------------
    def compute_hash(self) -> str:
        # 计算文件 SHA-256（用于检测重复导入）
        sha = hashlib.sha256()
        with open(self.file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()

    def detect_file_type(self) -> str:
        # 检测文件类型
        suffix = self.file_path.suffix.lower()
        if suffix in (".xlsx",):
            return "xlsx"
        elif suffix in (".xls",):
            return "xls"
        elif suffix in (".csv",):
            return "csv"
        else:
            raise ValueError(f"不支持的文件格式: {suffix}")

    def get_sheet_names(self) -> List[str]:
        # 获取所有工作表名
        ft = self.detect_file_type()
        if ft == "csv":
            return ["Sheet1"]
        elif ft == "xlsx":
            self.xl = pd.ExcelFile(self.file_path, engine="openpyxl")
        elif ft == "xls":
            self.xl = pd.ExcelFile(self.file_path, engine="xlrd")
        return list(self.xl.sheet_names) if self.xl else []

    # ----------------------------------------------------------------
    # 核心：读取 + 自动识别 Sheet 类型 → 统一长格式
    # ----------------------------------------------------------------
    def read_all_sheets(self) -> Dict[str, pd.DataFrame]:
        #
        # 读取所有 sheet，自动识别格式并转换为统一的长格式。
        # 返回: {sheet_name: DataFrame (长格式)}
        #
        if self.xl is None:
            self.get_sheet_names()

        results = {}
        for sheet in self.xl.sheet_names:
            # 读取原始数据（不含表头解析）
            raw = pd.read_excel(self.xl, sheet_name=sheet, header=None)

            if "尘埃粒子" in sheet:
                results[sheet] = self._parse_particle(raw)
            elif "风量" in sheet or "换气次数" in sheet:
                results[sheet] = self._parse_airflow(raw)
            elif "浮游菌" in sheet:
                results[sheet] = self._parse_bacteria(raw)
            else:
                # 其余 sheet 本轮不识别，直接跳过，不影响程序运行
                continue

        return results

    # ----------------------------------------------------------------
    # 尘埃粒子 Sheet 解析
    # ----------------------------------------------------------------
    def _parse_particle(self, raw: pd.DataFrame) -> pd.DataFrame:
        #
        # 输入（WIDE 格式，无表头行）：
        # 0              | 1(微生物二更) | 2(微生物缓冲间) | ...
        # 2026.1.4 0.5µm   | 11267         | 10364           | ...
        # 2026.1.4 5µm     | 0             | 0               | ...
        #
        # 输出（LONG 格式）：
        # record_date | room_name   | particle_size | indicator_name  | value | unit
        # 2026-01-04  | 微生物二更   | 0.5µm         | particle_05um  | 11267 | 个/m³
        # 2026-01-04  | 微生物二更   | 5µm           | particle_5um   | 0     | 个/m³
        # ...
        #
        # 第 0 行是列头，数据从第 1 行开始
        headers = [str(c).strip() for c in raw.iloc[0].values]
        df = raw.iloc[1:].copy()
        df.columns = headers

        # 找出「日期/粒径」列：其单元格形如 "2026.1.4 0.5µm"（含日期）。
        # 不假设它一定在第一列——不同文件的列顺序可能不同。
        date_col = None
        for col in df.columns:
            if df[col].astype(str).str.contains(
                r'\d{4}\.\d{1,2}\.\d{1,2}', regex=True, na=False
            ).any():
                date_col = col
                break
        if date_col is None:
            date_col = headers[0]  # 兜底：默认第一列

        # 房间名 = 表头中除日期列以外的所有列（按表头顺序动态读取）
        room_names = [h for h in headers if h != date_col]

        # 解析日期列 — 分离日期和粒径
        # 格式: "2026.1.4 0.5µm" 或 "2026.1.4 5µm"
        date_str = df[date_col].astype(str).str.strip()

        # 提取日期部分: "2026.1.4"
        date_part = date_str.str.extract(r'(\d{4}\.\d{1,2}\.\d{1,2})')[0]
        df['record_date'] = pd.to_datetime(date_part, errors='coerce')

        # 提取粒径部分: "0.5µm" / "1µm" / "5µm"（兼容 um/µm 两种写法）
        size_part = date_str.str.extract(r'(0\.5µm|1µm|5µm|0\.5um|1um|5um)')[0]
        df['particle_size'] = size_part.str.replace('um', 'µm', regex=False)

        # 跳过「标准」行与空行：这些行第一列不是日期，record_date 解析为 NaT，
        # 直接剔除，只保留含合法日期的数据行（标准行不参与分析）。
        df = df[df['record_date'].notna()].copy()

        # WIDE → LONG：把每个房间列变成行
        id_vars = ['record_date', 'particle_size']
        long = df.melt(
            id_vars=id_vars,
            value_vars=room_names,
            var_name='room_name',
            value_name='value'
        )

        # 转换数值
        long["value"] = pd.to_numeric(long["value"], errors="coerce")

        # 映射 indicator_name
        long["indicator_name"] = long["particle_size"].map({
            "0.5µm": "particle_05um",
            "1µm": "particle_1um",
            "5µm": "particle_5um",
        })
        long["indicator_cn"] = long["particle_size"].map({
            "0.5µm": "0.5µm尘埃粒子",
            "1µm": "1µm尘埃粒子",
            "5µm": "5µm尘埃粒子",
        })
        long["unit"] = "个/m³"

        # 删除辅助列，只保留最终用到的
        result = long[[
            "record_date", "room_name", "particle_size",
            "indicator_name", "indicator_cn", "value", "unit"
        ]].copy()
        result["room_adjacent"] = None  # 尘埃粒子 sheet 无此字段
        result = result.dropna(subset=["value"])

        return result

    # ----------------------------------------------------------------
    # 风量 Sheet 解析
    # ----------------------------------------------------------------
    def _parse_airflow(self, raw: pd.DataFrame) -> pd.DataFrame:
        #
        # 输入（水平重复格式）：
        # Row 0: 日期 | 房间 | 相邻 | 送风量 | 换气次数 | 日期 | 送风量 | 换气次数 | ... (重复多组)
        # Row 1: NaN  | 名称 | 房间 | (m³/h) | NaN     | NaN  | (m³/h) | NaN     | ... (单位行)
        # Row 2+: 2026.1.8 | 车间男二更 | 一更 | 1125 | 18.0 | 2026.2.5 | 1092 | ...
        #
        # 解析方式：按表头文字（日期 / 房间 / 相邻 / 送风量 / 换气次数）定位各列，
        # 再按「第 g 个日期」配「第 g 组送风量/换气次数」。列顺序、组数、房间名
        # 因文件而异都能正确识别，无需硬编码。
        #
        # 输出（LONG 格式）：
        # record_date | room_name | room_adjacent | indicator_name      | value | unit
        # 2026-01-08  | 车间男二更 | 一更          | supply_air_volume   | 1125  | m³/h
        # 2026-01-08  | 车间男二更 | 一更          | air_changes         | 18.0  | 次/h
        # ...
        #
        # 第 0 行是表头，第 1 行是单位说明，数据从第 2 行开始
        headers = [str(c).strip() if pd.notna(c) else "" for c in raw.iloc[0].values]
        data_rows = raw.iloc[2:].copy()

        # 按表头文字定位各列（不依赖固定顺序）
        def _col_indices(name: str) -> List[int]:
            return [i for i, h in enumerate(headers) if h == name]

        room_idx = _col_indices("房间")
        adj_idx = _col_indices("相邻")
        date_idx = _col_indices("日期")
        supply_idx = _col_indices("送风量")
        air_idx = _col_indices("换气次数")

        if not room_idx:
            raise ValueError("风量表未找到「房间」列，无法解析")
        room_col = room_idx[0]
        adj_col = adj_idx[0] if adj_idx else None

        # 组数 = 送风量列数；日期 / 换气次数列数应与之一致
        n_groups = len(supply_idx)
        if n_groups == 0:
            raise ValueError("风量表未找到「送风量」列，无法解析")
        if len(air_idx) != n_groups or len(date_idx) != n_groups:
            raise ValueError(
                f"风量表列数量不匹配：日期 {len(date_idx)} 列、"
                f"送风量 {len(supply_idx)} 列、换气次数 {len(air_idx)} 列，"
                "三者数量应一致。"
            )

        frames = []
        # 第 g 组 = 第 g 个「日期」列 + 第 g 个「送风量」列 + 第 g 个「换气次数」列
        for g in range(n_groups):
            subset = pd.DataFrame({
                "room_name": data_rows.iloc[:, room_col].astype(str).str.strip(),
                "room_adjacent": (
                    data_rows.iloc[:, adj_col].astype(str).str.strip()
                    if adj_col is not None else ""
                ),
                "date_str": data_rows.iloc[:, date_idx[g]].astype(str).str.strip(),
                "supply_air": data_rows.iloc[:, supply_idx[g]],
                "air_changes": data_rows.iloc[:, air_idx[g]],
            })

            # 只保留有日期的行（日期列不为空且不是 NaN）
            subset = subset[
                subset["date_str"].notna() &
                (subset["date_str"] != "nan") &
                (subset["date_str"] != "")
            ].copy()

            if len(subset) == 0:
                continue

            # 解析日期（pandas 自动识别 "2026.1.8" / "2026-01-08" 等格式）
            subset["record_date"] = pd.to_datetime(
                subset["date_str"], errors="coerce"
            )

            # 转换数值
            subset["supply_air"] = pd.to_numeric(subset["supply_air"], errors="coerce")
            subset["air_changes"] = pd.to_numeric(subset["air_changes"], errors="coerce")

            subset = subset.dropna(subset=["record_date"])
            frames.append(subset)

        if not frames:
            return pd.DataFrame()

        combined = pd.concat(frames, ignore_index=True)

        # WIDE → LONG：把 送风量/换气次数 两列变成 indicator 维度
        long = combined.melt(
            id_vars=["record_date", "room_name", "room_adjacent"],
            value_vars=["supply_air", "air_changes"],
            var_name="indicator",
            value_name="value"
        )

        # 映射 indicator_name
        indicator_map = {
            "supply_air": ("supply_air_volume", "送风量", "m³/h"),
            "air_changes": ("air_changes", "换气次数", "次/h"),
        }
        long["indicator_name"] = long["indicator"].map(
            lambda x: indicator_map.get(x, (x, x, ""))[0]
        )
        long["indicator_cn"] = long["indicator"].map(
            lambda x: indicator_map.get(x, (x, x, ""))[1]
        )
        long["unit"] = long["indicator"].map(
            lambda x: indicator_map.get(x, (x, x, ""))[2]
        )

        long["particle_size"] = None  # 风量 sheet 无此字段

        # 删除空值和辅助列
        result = long.dropna(subset=["value"]).copy()
        result = result[[
            "record_date", "room_name", "room_adjacent", "particle_size",
            "indicator_name", "indicator_cn", "value", "unit"
        ]]

        return result

    # ----------------------------------------------------------------
    # 浮游菌 Sheet 解析
    # ----------------------------------------------------------------
    def _parse_bacteria(self, raw: pd.DataFrame) -> pd.DataFrame:
        #
        # 输入（水平重复格式，与「风量」表类似）：
        # Row 0: 日期 | 监测区域 | 标准 | 采样量 | 菌落数×3 | 平均浓度 | 日期 | 菌落数×3 | 平均浓度 | ... (重复多组)
        # Row 1: 空行
        # Row 2+: 2026.1.4 | 微生物实验室 | ≤100个/m³ | 500L | 1 | 2 | 1 | 2.667 | 2026.2.23 | ...
        #
        # 解析方式：按表头文字（日期 / 监测区域 / 平均浓度）定位各列，
        # 第 g 组 = 第 g 个「日期」列 + 第 g 个「平均浓度」列。
        # 「标准」「采样量」「菌落数」列不参与分析，直接忽略。
        #
        # 输出（LONG 格式，只保留平均浓度一个指标）：
        # record_date | room_name | indicator_name          | value | unit
        # 2026-01-04  | 微生物实验室 | bacteria_concentration | 2.667 | 个/m³
        #
        headers = [str(c).strip() if pd.notna(c) else "" for c in raw.iloc[0].values]
        data = raw.iloc[2:].copy()   # 第 0 行表头、第 1 行空行，数据从第 2 行起

        # 按表头文字定位各列（不依赖固定顺序）
        def _col_indices(name: str, exact: bool = False) -> List[int]:
            if exact:
                return [i for i, h in enumerate(headers) if h == name]
            return [i for i, h in enumerate(headers) if name in h]

        room_idx = _col_indices("监测区域")
        date_idx = _col_indices("日期", exact=True)
        avg_idx = _col_indices("平均浓度")

        if not room_idx:
            raise ValueError("浮游菌表未找到「监测区域」列，无法解析")
        room_col = room_idx[0]

        n_groups = len(avg_idx)
        if n_groups == 0:
            raise ValueError("浮游菌表未找到「平均浓度」列，无法解析")
        if len(date_idx) != n_groups:
            raise ValueError(
                f"浮游菌表列数量不匹配：日期 {len(date_idx)} 列、"
                f"平均浓度 {len(avg_idx)} 列，二者数量应一致。"
            )

        # 丢弃没有房间名的行（组装车间纵向合并产生的空行、底部公式说明行）
        data = data[data.iloc[:, room_col].notna()].copy()
        data.iloc[:, room_col] = data.iloc[:, room_col].astype(str).str.strip()

        # 日期是纵向合并单元格（只在每组首行有值），向下填充
        for c in date_idx:
            data.iloc[:, c] = data.iloc[:, c].ffill()

        frames = []
        # 第 g 组 = 第 g 个「日期」列 + 第 g 个「平均浓度」列
        for g in range(n_groups):
            subset = pd.DataFrame({
                "room_name": data.iloc[:, room_col],
                "date_str": data.iloc[:, date_idx[g]].astype(str).str.strip(),
                "value": data.iloc[:, avg_idx[g]],
            })

            subset["record_date"] = pd.to_datetime(subset["date_str"], errors="coerce")
            subset["value"] = pd.to_numeric(subset["value"], errors="coerce")
            subset = subset.dropna(subset=["record_date", "value"])
            frames.append(subset)

        if not frames:
            return pd.DataFrame()

        combined = pd.concat(frames, ignore_index=True)

        combined["room_adjacent"] = None
        combined["particle_size"] = None
        combined["indicator_name"] = "bacteria_concentration"
        combined["indicator_cn"] = "浮游菌平均浓度"
        combined["unit"] = "个/m³"

        result = combined[[
            "record_date", "room_name", "room_adjacent", "particle_size",
            "indicator_name", "indicator_cn", "value", "unit"
        ]]

        return result

    # ----------------------------------------------------------------
    # 工具方法
    # ----------------------------------------------------------------
    def get_preview(self, sheet_name: str, rows: int = 10) -> pd.DataFrame:
        # 获取原始数据的预览（不做格式转换）
        raw = pd.read_excel(self.xl, sheet_name=sheet_name, header=None)
        return raw.head(rows)

    @staticmethod
    def get_indicator_info(indicator_name: str) -> Dict[str, str]:
        # 获取指标的详细信息（中文名、单位、描述）
        info = config.KNOWN_INDICATORS.get(indicator_name)
        if info:
            return {
                "chinese_name": info[0],
                "unit": info[1],
                "description": info[2],
            }
        return {
            "chinese_name": indicator_name,
            "unit": "",
            "description": "",
        }
