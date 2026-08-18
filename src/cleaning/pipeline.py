import pandas as pd
from typing import Callable, Dict, List, Optional, Any

from .missing_handler import MissingHandler


class CleaningPipeline:
    # 3 个清洗步骤（去重已移除）
    STEPS = [
        {
            "key": "missing",
            "name": "缺失值处理",
            "description": "检测数据中的缺失值：可跳过、删除含缺失值的列、或统一填充",
            "options": [
                {"id": "skip", "label": "跳过（默认）", "desc": "不做任何处理，缺失值保留"},
                {"id": "drop_cols", "label": "删除缺失值所在列", "desc": "删除所有含有缺失值的列"},
                {"id": "fill", "label": "统一填充缺失值", "desc": "把所有缺失值填充为同一个指定内容"},
            ],
        },
        {
            "key": "outliers",
            "name": "异常值处理",
            "description": "通过手动输入的上下阈值判断异常值，并打上绿色高亮（不改数据）",
            "options": [
                {"id": "skip", "label": "跳过（默认）", "desc": "不做任何高亮"},
                {"id": "manual", "label": "手动输入阈值", "desc": "输入上下限，数值列中超出范围的值打上绿色高亮"},
            ],
        },
        {
            "key": "timeformat",
            "name": "时间格式统一",
            "description": "将时间字段统一为标准格式（不包含时分秒）",
            "options": [
                {"id": "standard", "label": "统一为标准格式（默认）", "desc": "转为 YYYY-MM-DD，去掉时分秒"},
                {"id": "keep", "label": "保持不变", "desc": "不修改时间格式"},
            ],
        },
    ]

    def __init__(self, df: pd.DataFrame, user_callback: Callable = None):
        self.original_df = df.copy()
        self.df = df.copy()
        self.user_callback = user_callback or self._default_callback
        self.full_log = []
        self.step_results = {}  # 每步的结果
        self.outlier_bounds = None  # (lower, upper) 用于绿色高亮；None=不高亮

    def run(self, selected_steps: List[str] = None) -> tuple:
        if selected_steps is None:
            selected_steps = [s["key"] for s in self.STEPS]

        for step_def in self.STEPS:
            step_key = step_def["key"]
            if step_key not in selected_steps:
                continue

            summary = self._make_summary(step_key)
            if summary is None:
                continue

            choice = self.user_callback(step_def, summary)
            self._execute_step(step_key, choice)

        return self.df, self.full_log

    def run_step(self, step_key: str, choice: str, params: Dict = None) -> Dict:
        step_def = next((s for s in self.STEPS if s["key"] == step_key), None)
        if step_def is None:
            return {"ok": False, "error": f"未知步骤: {step_key}"}

        before = self.df.copy()
        summary = self._make_summary(step_key)
        log = self._execute_step(step_key, choice, params or {})

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
            cols = "、".join(missing_info["列名"].astype(str))
            return {"status": "found", "message":
                    f"检测到 {len(missing_info)} 列存在缺失值（{cols}），共 {int(missing_info['缺失数量'].sum())} 个",
                    "missing_table": missing_info,
                    "missing_count": int(missing_info["缺失数量"].sum())}

        elif step_key == "outliers":
            num_cols = self.df.select_dtypes(include=["number"]).columns.tolist()
            if not num_cols:
                return {"status": "clean", "message": "没有可判断的数值列", "num_cols": []}
            return {"status": "found", "message":
                    "选择「手动输入阈值」后将提示输入上下限，数值列中超出范围的值会打上绿色高亮（数据本身不变）。",
                    "num_cols": num_cols}

        elif step_key == "timeformat":
            # 优先按列名识别时间列（record_date 等），不依赖 dtype
            time_cols = [c for c in self.df.columns if
                         any(kw in c.lower() for kw in ["time", "date", "时间", "日期"])]
            if not time_cols:
                time_cols = [c for c in self.df.columns if self.df[c].dtype == object]
            return {"status": "found", "message": f"检测到 {len(time_cols)} 个时间列",
                    "time_columns": time_cols}

        return None

    def _execute_step(self, step_key: str, choice: str, params: Dict = None) -> List[Dict]:
        params = params or {}
        log = []

        if step_key == "missing":
            missing_count = int(self.df.isna().sum().sum())
            if choice == "drop_cols":
                # 删除所有含有缺失值的列
                cols_with_missing = [c for c in self.df.columns if self.df[c].isna().any()]
                self.df = self.df.drop(columns=cols_with_missing)
                dropped = "、".join(cols_with_missing) if cols_with_missing else "无"
                log = [{"步骤": "缺失值-删除列",
                        "删除列": dropped,
                        "说明": f"已删除 {len(cols_with_missing)} 个含缺失值的列"}]
            elif choice == "fill":
                fill_value = params.get("fill_value", "")
                self.df = self.df.fillna(fill_value)
                log = [{"步骤": "缺失值-统一填充",
                        "填充值": str(fill_value),
                        "说明": f"已将 {missing_count} 个缺失值统一填充为「{fill_value}」"}]
            else:  # skip
                log = [{"步骤": "缺失值-跳过",
                        "说明": f"检测到 {missing_count} 个缺失值，未处理（预览中标红）"}]

        elif step_key == "outliers":
            # 本步骤只记录阈值用于绿色高亮，不修改任何数据
            if choice == "manual":
                lower = params.get("lower")
                upper = params.get("upper")
                self.outlier_bounds = (lower, upper)
                log = [{"步骤": "异常值-手动阈值",
                        "下限": lower, "上限": upper,
                        "说明": "已按上下阈值标出异常值（绿色高亮），数据本身不变"}]
            else:  # skip
                self.outlier_bounds = None
                log = [{"步骤": "异常值-跳过", "说明": "不做高亮"}]

        elif step_key == "timeformat":
            summary = self._make_summary("timeformat")
            time_cols = summary.get("time_columns", [])
            if choice == "standard":
                if not time_cols:
                    log = [{"步骤": "时间格式统一", "状态": "跳过", "原因": "未检测到时间列"}]
                else:
                    converted = []
                    for col in time_cols:
                        self.df[col] = self._to_date_only(self.df[col])
                        converted.append(col)
                    log = [{"步骤": "时间格式统一",
                            "转换列": "、".join(converted),
                            "最终格式": "YYYY-MM-DD（不含时分秒）"}]
            else:  # keep
                log = [{"步骤": "时间格式-保持不变", "说明": "未修改时间格式"}]

        self.full_log.extend(log)
        return log

    @staticmethod
    def _to_date_only(series: pd.Series) -> pd.Series:
        # 统一转为 YYYY-MM-DD（去掉时分秒）；无法解析的原样保留为缺失
        s = pd.to_datetime(series, errors="coerce")
        out = s.dt.strftime("%Y-%m-%d")
        # NaT 位置统一置为 None，避免出现 "NaT" 字符串
        out = out.where(s.notna(), None)
        return out

    @staticmethod
    def _default_callback(step_def: Dict, summary: Dict) -> str:
        return step_def["options"][0]["id"]
