import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional


class OutlierHandler:

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.actions_log = []
        self.outlier_mask = None
        
    def detect_outliers_summary(self) -> pd.DataFrame:
        results = []
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

    def remove_by_iqr(self, columns: List[str] = None, factor: float = 1.5) -> "OutlierHandler":
        #IQR方法
        cols = columns or self._get_numeric_columns()
        total_outliers = 0
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

    def remove_by_zscore(self, columns: List[str] = None, threshold: float = 3.0) -> "OutlierHandler":
        #Z-Score方法
        cols = columns or self._get_numeric_columns()
        total_outliers = 0
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

    def winsorize(self, columns: List[str] = None, limits: Tuple[float, float] = (0.05, 0.05)) -> "OutlierHandler":
        #Winsorize（缩尾)
        from scipy.stats.mstats import winsorize

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

    def _get_numeric_columns(self) -> List[str]:
        return self.df.select_dtypes(include=[np.number]).columns.tolist()

    def get_result(self) -> pd.DataFrame:
        return self.df

    def get_log(self) -> List[Dict]:
        return self.actions_log
