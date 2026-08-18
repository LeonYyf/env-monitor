import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional


class OutlierHandler:

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.actions_log = []
        self.outlier_mask = None

    # ------------------------------------------------------------------
    # 分组判定：长表数据里「value」列混合了所有指标的取值（换气次数≈19、
    # 送风量≈3200、粒子数可达百万级），若直接对 value 列整体算 IQR 会
    # 张冠李戴。因此必须按「房间 × 指标」分组，各自独立判定异常值。
    # ------------------------------------------------------------------
    def _is_long_format(self) -> bool:
        """是否长表结构（含 indicator_cn + value）。"""
        return ("indicator_cn" in self.df.columns and "value" in self.df.columns)

    def _group_keys(self) -> List[str]:
        """长表的分组键：优先「房间 × 指标」，退化为「指标」。"""
        keys = []
        if "room_name" in self.df.columns:
            keys.append("room_name")
        if "indicator_cn" in self.df.columns:
            keys.append("indicator_cn")
        return keys

    def _iter_value_groups(self):
        """按分组键产出 (标签, 索引数组, 该组的 value 序列)。"""
        for name, idx in self.df.groupby(self._group_keys(), dropna=False).groups.items():
            if not isinstance(name, tuple):
                name = (name,)
            label = " × ".join(str(n) for n in name)
            yield label, idx, self.df.loc[idx, "value"]

    def _get_numeric_columns(self) -> List[str]:
        return self.df.select_dtypes(include=[np.number]).columns.tolist()

    # ------------------------------------------------------------------
    # 检测
    # ------------------------------------------------------------------
    def detect_outliers_summary(self) -> pd.DataFrame:
        results = []

        if self._is_long_format():
            # 长表：按「房间 × 指标」分组判定
            for label, idx, series in self._iter_value_groups():
                s = series.dropna()
                if len(s) < 4:
                    continue
                Q1 = s.quantile(0.25)
                Q3 = s.quantile(0.75)
                IQR = Q3 - Q1
                if IQR <= 0:
                    continue
                lower = Q1 - 1.5 * IQR
                upper = Q3 + 1.5 * IQR
                outliers = s[(s < lower) | (s > upper)]
                results.append({
                    "列名": label,
                    "Q1": round(Q1, 2),
                    "Q3": round(Q3, 2),
                    "IQR": round(IQR, 2),
                    "下限": round(lower, 2),
                    "上限": round(upper, 2),
                    "异常值数量": len(outliers),
                    "异常值比例": f"{len(outliers)/len(s)*100:.1f}%",
                    "异常值范围": f"{outliers.min():.2f} ~ {outliers.max():.2f}" if len(outliers) > 0 else "无",
                })
        else:
            # 通用：逐数值列判定（原逻辑）
            for col in self._get_numeric_columns():
                series = self.df[col].dropna()
                if len(series) == 0:
                    continue
                Q1 = series.quantile(0.25)
                Q3 = series.quantile(0.75)
                IQR = Q3 - Q1
                lower = Q1 - 1.5 * IQR
                upper = Q3 + 1.5 * IQR
                outliers = series[(series < lower) | (series > upper)]
                results.append({
                    "列名": col,
                    "Q1": round(Q1, 2),
                    "Q3": round(Q3, 2),
                    "IQR": round(IQR, 2),
                    "下限": round(lower, 2),
                    "上限": round(upper, 2),
                    "异常值数量": len(outliers),
                    "异常值比例": f"{len(outliers)/len(series)*100:.1f}%",
                    "异常值范围": f"{outliers.min():.2f} ~ {outliers.max():.2f}" if len(outliers) > 0 else "无",
                })
        return pd.DataFrame(results)

    # ------------------------------------------------------------------
    # IQR 去除
    # ------------------------------------------------------------------
    def remove_by_iqr(self, columns: List[str] = None, factor: float = 1.5) -> "OutlierHandler":
        total_outliers = 0

        if self._is_long_format():
            for label, idx, series in self._iter_value_groups():
                s = series.dropna()
                if len(s) < 4:
                    continue
                Q1 = s.quantile(0.25)
                Q3 = s.quantile(0.75)
                IQR = Q3 - Q1
                if IQR <= 0:
                    continue
                lower = Q1 - factor * IQR
                upper = Q3 + factor * IQR
                mask = (self.df.loc[idx, "value"] < lower) | (self.df.loc[idx, "value"] > upper)
                n = int(mask.sum())
                if n > 0:
                    total_outliers += n
                    self.df.loc[idx[mask], "value"] = np.nan
                    self.actions_log.append({
                        "步骤": "异常值-IQR去除",
                        "列": label,
                        "方法": f"IQR_factor={factor}",
                        "下限": f"{lower:.2f}",
                        "上限": f"{upper:.2f}",
                        "标记数": n,
                    })
        else:
            cols = columns or self._get_numeric_columns()
            for col in cols:
                if col not in self.df.columns or self.df[col].dtype not in [np.float64, np.int64, float, int]:
                    continue
                series = self.df[col].dropna()
                if len(series) == 0:
                    continue
                Q1 = series.quantile(0.25)
                Q3 = series.quantile(0.75)
                IQR = Q3 - Q1
                lower = Q1 - factor * IQR
                upper = Q3 + factor * IQR
                outlier_count = ((self.df[col] < lower) | (self.df[col] > upper)).sum()
                if outlier_count > 0:
                    total_outliers += outlier_count
                    self.df.loc[(self.df[col] < lower) | (self.df[col] > upper), col] = np.nan
                    self.actions_log.append({
                        "步骤": "异常值-IQR去除",
                        "列": col,
                        "方法": f"IQR_factor={factor}",
                        "下限": f"{lower:.2f}",
                        "上限": f"{upper:.2f}",
                        "标记数": outlier_count,
                    })

        if total_outliers > 0:
            self.actions_log.append({
                "步骤": "异常值-IQR去除",
                "方法": "汇总",
                "总标记数": total_outliers,
                "说明": "异常值已替换为NaN，可在缺失值处理步骤中进一步处理",
            })
        return self

    # ------------------------------------------------------------------
    # Z-Score 去除
    # ------------------------------------------------------------------
    def remove_by_zscore(self, columns: List[str] = None, threshold: float = 3.0) -> "OutlierHandler":
        total_outliers = 0

        if self._is_long_format():
            for label, idx, series in self._iter_value_groups():
                s = series.dropna()
                if len(s) < 4 or s.std() == 0:
                    continue
                z_scores = np.abs((s - s.mean()) / s.std())
                outlier_indices = s.index[z_scores > threshold]
                n = len(outlier_indices)
                if n > 0:
                    total_outliers += n
                    self.df.loc[outlier_indices, "value"] = np.nan
                    self.actions_log.append({
                        "步骤": "异常值-ZScore去除",
                        "列": label,
                        "方法": f"ZScore_threshold={threshold}",
                        "标记数": n,
                    })
        else:
            cols = columns or self._get_numeric_columns()
            for col in cols:
                if col not in self.df.columns or self.df[col].dtype not in [np.float64, np.int64, float, int]:
                    continue
                series = self.df[col].dropna()
                if len(series) == 0 or series.std() == 0:
                    continue
                z_scores = np.abs((series - series.mean()) / series.std())
                outlier_indices = series.index[z_scores > threshold]
                outlier_count = len(outlier_indices)
                if outlier_count > 0:
                    total_outliers += outlier_count
                    self.df.loc[outlier_indices, col] = np.nan
                    self.actions_log.append({
                        "步骤": "异常值-ZScore去除",
                        "列": col,
                        "方法": f"ZScore_threshold={threshold}",
                        "标记数": outlier_count,
                    })

        if total_outliers > 0:
            self.actions_log.append({
                "步骤": "异常值-ZScore去除",
                "方法": "汇总",
                "总标记数": total_outliers,
            })
        return self

    # ------------------------------------------------------------------
    # 自定义上下限截断
    # ------------------------------------------------------------------
    def clip_by_bounds(self, columns_bounds: Dict[str, Tuple[float, float]]) -> "OutlierHandler":
        """
        根据自定义上下限截断
        columns_bounds: {"temperature": (0, 50), "humidity": (0, 100), ...}
        超出范围的值被截断到边界值
        """
        total = 0
        for col, (low, high) in columns_bounds.items():
            if col not in self.df.columns:
                continue
            before_outliers = ((self.df[col] < low) | (self.df[col] > high)).sum()
            self.df[col] = self.df[col].clip(lower=low, upper=high)
            total += before_outliers
            self.actions_log.append({
                "步骤": "异常值-截断",
                "列": col,
                "方法": f"clip({low}, {high})",
                "截断数": before_outliers,
            })
        return self

    # ------------------------------------------------------------------
    # Winsorize 缩尾
    # ------------------------------------------------------------------
    def winsorize(self, columns: List[str] = None, limits: Tuple[float, float] = (0.05, 0.05)) -> "OutlierHandler":
        from scipy.stats.mstats import winsorize

        if self._is_long_format():
            for label, idx, series in self._iter_value_groups():
                s = series.dropna()
                if len(s) == 0:
                    continue
                self.df.loc[s.index, "value"] = winsorize(s, limits=limits)
                self.actions_log.append({
                    "步骤": "异常值-Winsorize",
                    "列": label,
                    "方法": f"limits={limits}",
                })
        else:
            cols = columns or self._get_numeric_columns()
            for col in cols:
                if col not in self.df.columns or self.df[col].dtype not in [np.float64, np.int64, float, int]:
                    continue
                series = self.df[col].dropna()
                if len(series) == 0:
                    continue
                self.df.loc[series.index, col] = winsorize(series, limits=limits)
                self.actions_log.append({
                    "步骤": "异常值-Winsorize",
                    "列": col,
                    "方法": f"limits={limits}",
                })
        return self

    def get_result(self) -> pd.DataFrame:
        return self.df

    def get_log(self) -> List[Dict]:
        return self.actions_log
