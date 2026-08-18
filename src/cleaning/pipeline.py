import pandas as pd
from typing import Callable, Dict, List, Optional, Any

from .missing_handler import MissingHandler
from .outlier_handler import OutlierHandler
from .formatter import Formatter


class CleaningPipeline:
    # 4个清洗步骤
    STEPS = [
        {
            "key": "missing",
            "name": "缺失值处理",
            "description": "检测数据中的缺失值（仅高亮标红，不填充、不删除）",
            "options": [
                {"id": "highlight", "label": "仅高亮（不填充）", "desc": "只在预览中把缺失值标红显示，不修改任何数据"},
            ],
        },
        {
            "key": "outliers",
            "name": "异常值处理",
            "description": "检测并处理偏离正常范围的异常值",
            "options": [
                {"id": "iqr", "label": "IQR 方法（推荐）", "desc": "Q1-1.5×IQR ~ Q3+1.5×IQR 之外视为异常，替换为NaN"},
                {"id": "zscore", "label": "Z-Score 方法", "desc": "|Z|>3 视为异常（假设正态分布），替换为NaN"},
                {"id": "clip", "label": "自定义范围截断", "desc": "按业务常识设置上下限，超出截断到边界"},
                {"id": "winsorize", "label": "Winsorize 缩尾", "desc": "将两端5%的极值替换为边界值，更保守"},
                {"id": "skip", "label": "跳过", "desc": "不做异常值处理"},
            ],
        },
        {
            "key": "timeformat",
            "name": "时间格式统一",
            "description": "将所有时间字段统一为标准格式 YYYY-MM-DD HH:MM:SS",
            "options": [
                {"id": "auto", "label": "自动解析（推荐）", "desc": "使用 pandas 自动检测并转换时间格式"},
                {"id": "auto_extract", "label": "自动解析+提取特征", "desc": "转换时间并额外提取：小时、周几、月份、是否周末"},
            ],
        },
        {
            "key": "dedup",
            "name": "去重处理",
            "description": "删除重复记录",
            "options": [
                {"id": "skip", "label": "跳过（推荐）", "desc": "不做去重处理"},
                {"id": "keep_first", "label": "保留第一条", "desc": "重复记录中保留最早出现的那条"},
                {"id": "keep_last", "label": "保留最后一条", "desc": "重复记录中保留最后出现的那条"},
                {"id": "time_loc", "label": "按时间+位置去重", "desc": "同一时间同一地点不应有重复记录"},
            ],
        },
    ]

    def __init__(self, df: pd.DataFrame, user_callback: Callable = None):
        self.original_df = df.copy()
        self.df = df.copy()
        self.user_callback = user_callback or self._default_callback
        self.full_log = []
        self.step_results = {}  # 每步的结果

    def run(self, selected_steps: List[str] = None) -> tuple:
        if selected_steps is None:
            selected_steps = [s["key"] for s in self.STEPS]

        for step_def in self.STEPS:
            step_key = step_def["key"]
            if step_key not in selected_steps:
                continue

            # 生成当前步骤的信息
            summary = self._make_summary(step_key)
            if summary is None:
                continue

            # 询问用户方法
            choice = self.user_callback(step_def, summary)

            # 执行
            self._execute_step(step_key, choice)

        return self.df, self.full_log

    def run_step(self, step_key: str, choice: str) -> Dict:
        step_def = next((s for s in self.STEPS if s["key"] == step_key), None)
        if step_def is None:
            return {"ok": False, "error": f"未知步骤: {step_key}"}

        before = self.df.copy()
        summary = self._make_summary(step_key)
        log = self._execute_step(step_key, choice)

        return {
            "ok": True,
            "step_log": log,
            "before": before,
            "after": self.df.copy(),
            "summary": summary,
        }

    def _make_summary(self, step_key: str) -> Optional[Dict]:
        if step_key == "missing":
            handler = MissingHandler(self.df)
            missing_info = handler.detect_missing()
            if missing_info.empty:
                return {"status": "clean", "message": "未检测到缺失值，此步骤可跳过",
                        "missing_table": None, "missing_count": 0}
            return {"status": "found", "message":
                    f"检测到 {len(missing_info)} 列存在缺失值，共 {missing_info['缺失数量'].sum()} 个",
                    "missing_table": missing_info,
                    "missing_count": int(missing_info["缺失数量"].sum())}

        elif step_key == "outliers":
            handler = OutlierHandler(self.df)
            outlier_info = handler.detect_outliers_summary()
            total_outliers = outlier_info["异常值数量"].sum() if not outlier_info.empty else 0
            if total_outliers == 0:
                return {"status": "clean", "message": "未检测到异常值（IQR方法），此步骤可跳过",
                        "outlier_table": None, "outlier_count": 0}
            return {"status": "found", "message":
                    f"检测到 {total_outliers} 个异常值（分布在 {len(outlier_info)} 列）",
                    "outlier_table": outlier_info, "outlier_count": int(total_outliers)}

        elif step_key == "timeformat":
            time_cols = [c for c in self.df.columns if
                         self.df[c].dtype == object and
                         any(kw in c.lower() for kw in ["time", "date", "时间", "日期"])]
            if not time_cols:
                time_cols = [c for c in self.df.columns if self.df[c].dtype == object]
            return {"status": "found", "message": f"检测到 {len(time_cols)} 个可能的文本时间列",
                    "time_columns": time_cols}

        elif step_key == "dedup":
            dup_count = self.df.duplicated().sum()
            if dup_count == 0:
                return {"status": "clean", "message": "未检测到重复行，此步骤可跳过",
                        "dup_count": 0}
            return {"status": "found", "message": f"检测到 {dup_count} 条重复记录",
                    "dup_count": int(dup_count)}

        return None

    def _execute_step(self, step_key: str, choice: str) -> List[Dict]:
        
        log = []

        if step_key == "missing":
            # 仅高亮不填充
            missing_count = int(self.df.isna().sum().sum())
            log = [{"步骤": "缺失值-仅高亮",
                    "说明": f"检测到 {missing_count} 个缺失值，未填充（预览中标红）"}]

        elif step_key == "outliers":
            handler = OutlierHandler(self.df)
            if choice == "iqr":
                handler.remove_by_iqr()
            elif choice == "zscore":
                handler.remove_by_zscore()
            elif choice == "clip":
                handler.clip_by_bounds({})
            elif choice == "winsorize":
                handler.winsorize()
            elif choice == "skip":
                pass
            else:
                handler.remove_by_iqr()
            self.df = handler.get_result()
            log = handler.get_log()

        elif step_key == "timeformat":
            handler = Formatter(self.df)
            summary = self._make_summary("timeformat")
            time_cols = summary.get("time_columns", [])
            time_col = time_cols[0] if time_cols else None

            if time_col:
                handler.unify_time_format(time_col)
                if choice == "auto_extract":
                    handler.extract_time_features(time_col)
            self.df = handler.get_result()
            log = handler.get_log()

        elif step_key == "dedup":
            handler = Formatter(self.df)
            if choice == "keep_first":
                handler.deduplicate(keep="first")
            elif choice == "keep_last":
                handler.deduplicate(keep="last")
            elif choice == "time_loc":
                summary = self._make_summary("timeformat")
                time_cols = summary.get("time_columns", [])
                time_col = time_cols[0] if time_cols else None
                if time_col:
                    handler.deduplicate_time_location(time_col)
                else:
                    handler.deduplicate(keep="first")
            elif choice == "skip":
                pass
            self.df = handler.get_result()
            log = handler.get_log()

        self.full_log.extend(log)
        return log

    @staticmethod
    def _default_callback(step_def: Dict, summary: Dict) -> str:
        return step_def["options"][0]["id"]
