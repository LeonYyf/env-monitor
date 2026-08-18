"""
探索性数据分析 — 统计描述模块
"""

import pandas as pd
import numpy as np
from scipy import stats as sp_stats


def compute_statistics(df: pd.DataFrame, columns: list = None) -> pd.DataFrame:
    """
    计算所有数值列的统计描述

    返回字段：计数、均值、标准差、最小值、Q1、中位数、Q3、最大值、
             偏度、峰度、缺失数、缺失率
    """
    if columns is None:
        columns = df.select_dtypes(include=[np.number]).columns.tolist()

    results = []
    total = len(df)

    for col in columns:
        if col not in df.columns:
            continue
        series = df[col].dropna()
        n = len(series)

        if n == 0:
            continue

        stats_dict = {
            "变量": col,
            "样本数": n,
            "缺失数": total - n,
            "缺失率": f"{(total - n) / total * 100:.1f}%",
            "均值": round(series.mean(), 2),
            "标准差": round(series.std(ddof=0), 2),
            "最小值": round(series.min(), 2),
            "Q1": round(series.quantile(0.25), 2),
            "中位数": round(series.median(), 2),
            "Q3": round(series.quantile(0.75), 2),
            "最大值": round(series.max(), 2),
        }

        # 偏度和峰度
        if n >= 3:
            stats_dict["偏度"] = round(series.skew(), 2)
            stats_dict["峰度"] = round(series.kurtosis(), 2)
        else:
            stats_dict["偏度"] = "N/A"
            stats_dict["峰度"] = "N/A"

        # 正态性检验（Shapiro-Wilk）
        if 3 <= n <= 5000:
            try:
                _, p = sp_stats.shapiro(series.sample(min(n, 5000)))
                stats_dict["正态性p值"] = round(p, 4)
            except Exception:
                stats_dict["正态性p值"] = "N/A"
        else:
            stats_dict["正态性p值"] = "N/A"

        results.append(stats_dict)

    return pd.DataFrame(results)


def compute_correlation_matrix(df: pd.DataFrame, columns: list = None) -> pd.DataFrame:
    """计算相关系数矩阵（Pearson）"""
    if columns is None:
        columns = df.select_dtypes(include=[np.number]).columns.tolist()
    return df[columns].corr(method="pearson")


def compare_groups(df: pd.DataFrame, value_column: str,
                   group_column: str = "location") -> dict:
    """
    按分组比较变量（如：实验室 vs 生产车间）
    返回: {分组名: {均值, 标准差, ...}}
    """
    if group_column not in df.columns:
        return {}

    results = {}
    for group_name, group_df in df.groupby(group_column):
        series = group_df[value_column].dropna()
        if len(series) == 0:
            continue
        results[str(group_name)] = {
            "样本数": len(series),
            "均值": round(series.mean(), 2),
            "标准差": round(series.std(ddof=0), 2),
            "最小值": round(series.min(), 2),
            "最大值": round(series.max(), 2),
        }
    return results
