"""
探索性数据分析 — 可视化模块
生成统计图表（matplotlib + seaborn），支持中文。
"""

import matplotlib
matplotlib.use("QtAgg")  # PySide6 兼容后端
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from pathlib import Path
import config

# 设置中文字体
plt.rcParams["font.family"] = config.VIZ_DEFAULTS["font_family"]
plt.rcParams["axes.unicode_minus"] = False
sns.set_palette(config.VIZ_DEFAULTS["color_palette"])


class Visualizer:
    """数据可视化器"""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.figsize = config.VIZ_DEFAULTS["figure_size"]
        self.dpi = config.VIZ_DEFAULTS["figure_dpi"]

    # ----------------------------------------------------------------
    # 分布图
    # ----------------------------------------------------------------
    def histogram(self, column: str, bins: int = 30, kde: bool = True) -> plt.Figure:
        """直方图 + KDE 密度曲线"""
        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)
        series = self.df[column].dropna()
        ax.hist(series, bins=bins, density=True, alpha=0.6, color="#0F766E", edgecolor="white")
        if kde:
            from scipy.stats import gaussian_kde
            kde_vals = gaussian_kde(series)(np.linspace(series.min(), series.max(), 200))
            ax.plot(np.linspace(series.min(), series.max(), 200), kde_vals,
                    color="#115E59", linewidth=2, label="KDE 密度")
            ax.legend()
        ax.set_title(f"{column} 分布图", fontsize=14, fontweight="bold")
        ax.set_xlabel(column)
        ax.set_ylabel("频率密度")
        fig.tight_layout()
        return fig

    def box_plot(self, columns: list = None, group_by: str = "location") -> plt.Figure:
        """箱线图 — 按位置分组对比"""
        cols = columns or self.df.select_dtypes(include=[np.number]).columns[:6]
        n = len(cols)

        fig, axes = plt.subplots(1, n, figsize=(5 * n, 5), dpi=self.dpi)
        if n == 1:
            axes = [axes]

        for i, col in enumerate(cols):
            if group_by in self.df.columns:
                sns.boxplot(data=self.df, x=group_by, y=col, ax=axes[i])
            else:
                sns.boxplot(y=self.df[col], ax=axes[i], color="#0F766E")
            axes[i].set_title(col, fontweight="bold")
        fig.tight_layout()
        return fig

    # ----------------------------------------------------------------
    # 时间序列图
    # ----------------------------------------------------------------
    def time_series(self, time_column: str, value_columns: list,
                    group_by: str = None) -> plt.Figure:
        """时间序列折线图"""
        n = len(value_columns)
        fig, axes = plt.subplots(n, 1, figsize=(12, 3.5 * n), dpi=self.dpi, sharex=True)
        if n == 1:
            axes = [axes]

        for i, col in enumerate(value_columns):
            ax = axes[i]
            if group_by and group_by in self.df.columns:
                for label, grp_df in self.df.groupby(group_by):
                    ax.plot(grp_df[time_column], grp_df[col],
                            label=str(label), alpha=0.7, linewidth=1)
                ax.legend()
            else:
                ax.plot(self.df[time_column], self.df[col],
                        color="#0F766E", linewidth=1.2)
            ax.set_ylabel(col)
            ax.set_title(col, fontweight="bold")
            ax.grid(True, alpha=0.3)

        fig.tight_layout()
        return fig

    # ----------------------------------------------------------------
    # 相关性热力图
    # ----------------------------------------------------------------
    def correlation_heatmap(self, columns: list = None) -> plt.Figure:
        """Pearson 相关系数热力图"""
        cols = columns or self.df.select_dtypes(include=[np.number]).columns
        corr = self.df[cols].corr()

        fig, ax = plt.subplots(figsize=(10, 8), dpi=self.dpi)
        mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
        sns.heatmap(corr, mask=mask, annot=True, fmt=".2f", cmap="RdYlBu_r",
                    center=0, square=True, linewidths=0.5,
                    vmin=-1, vmax=1, ax=ax,
                    cbar_kws={"shrink": 0.8, "label": "Pearson 相关系数"})
        ax.set_title("变量相关性热力图", fontsize=16, fontweight="bold", pad=16)
        fig.tight_layout()
        return fig

    # ----------------------------------------------------------------
    # 散点图矩阵
    # ----------------------------------------------------------------
    def scatter_plot(self, x: str, y: str, hue: str = None,
                     add_regression: bool = True) -> plt.Figure:
        """散点图 + 可选回归线"""
        fig, ax = plt.subplots(figsize=self.figsize, dpi=self.dpi)

        if hue and hue in self.df.columns:
            sns.scatterplot(data=self.df, x=x, y=y, hue=hue, alpha=0.6, ax=ax)
        else:
            ax.scatter(self.df[x], self.df[y], alpha=0.5, color="#0F766E", edgecolors="white")

        if add_regression:
            sns.regplot(data=self.df, x=x, y=y, scatter=False,
                        line_kws={"color": "#EF5350", "linewidth": 2}, ax=ax)

        ax.set_xlabel(x)
        ax.set_ylabel(y)
        ax.set_title(f"{y} vs {x}", fontweight="bold")
        fig.tight_layout()
        return fig

    # ----------------------------------------------------------------
    # 配对图
    # ----------------------------------------------------------------
    def pair_plot(self, columns: list = None, hue: str = "location") -> plt.Figure:
        """变量配对散点图矩阵"""
        cols = columns or self.df.select_dtypes(include=[np.number]).columns[:5]
        plot_cols = cols.copy()
        if hue and hue in self.df.columns:
            plot_cols.append(hue)

        g = sns.pairplot(self.df[plot_cols], hue=hue if hue in self.df.columns else None,
                         diag_kind="kde", corner=True,
                         plot_kws={"alpha": 0.6, "s": 40})
        g.fig.suptitle("变量配对关系图", fontsize=16, fontweight="bold", y=1.02)
        return g.fig

    # ----------------------------------------------------------------
    # 保存
    # ----------------------------------------------------------------
    @staticmethod
    def save_figure(fig: plt.Figure, filename: str):
        """保存图表到 data/charts/"""
        path = config.CHART_DIR / filename
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
        return str(path)
