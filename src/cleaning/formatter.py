import pandas as pd
from typing import Dict, List
from datetime import datetime


class Formatter:

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.actions_log = []
        
    def unify_time_format(self, time_column: str, target_format: str = None) -> "Formatter":
        if time_column not in self.df.columns:
            self.actions_log.append({
                "步骤": "时间格式统一",
                "状态": "跳过",
                "原因": f"列 '{time_column}' 不存在",
            })
            return self

        before_nulls = self.df[time_column].isna().sum()
        self.df[time_column] = pd.to_datetime(
            self.df[time_column], errors="coerce"
        )
        after_nulls = self.df[time_column].isna().sum()
        new_nulls = after_nulls - before_nulls

        self.actions_log.append({
            "步骤": "时间格式统一",
            "列": time_column,
            "方法": "pd.to_datetime",
            "成功解析数": len(self.df) - after_nulls,
            "无法解析数": new_nulls,
            "最终格式": "YYYY-MM-DD HH:MM:SS",
        })
        return self

    def extract_time_features(self, time_column: str) -> "Formatter":
        """
        从时间列中提取特征：
        hour(小时), day_of_week(周几), month(月份), is_weekend(是否周末)
        这些特征可用于后续回归建模（如"时段对温度的影响"）
        """
        if time_column not in self.df.columns:
            return self

        if not pd.api.types.is_datetime64_any_dtype(self.df[time_column]):
            self.df[time_column] = pd.to_datetime(self.df[time_column], errors="coerce")

        self.df["hour"] = self.df[time_column].dt.hour
        self.df["day_of_week"] = self.df[time_column].dt.dayofweek
        self.df["month"] = self.df[time_column].dt.month
        self.df["is_weekend"] = self.df["day_of_week"].apply(lambda x: 1 if x >= 5 else 0)

        self.actions_log.append({
            "步骤": "时间特征提取",
            "新增列": "hour, day_of_week, month, is_weekend",
            "说明": "用于后续回归建模",
        })
        return self

    def deduplicate(self, subset: List[str] = None, keep: str = "first") -> "Formatter":
        """
        去重处理
        keep: 'first'=保留第一条, 'last'=保留最后一条, False=全部删除
        subset: 按哪些列判断重复，None=所有列完全相同才算重复
        """
        before = len(self.df)
        self.df = self.df.drop_duplicates(subset=subset, keep=keep)
        after = len(self.df)
        removed = before - after

        self.actions_log.append({
            "步骤": "去重",
            "方法": f"keep={keep}",
            "去重依据": ", ".join(subset) if subset else "所有列",
            "删除行数": removed,
            "保留行数": after,
        })
        return self

    def deduplicate_time_location(self, time_column: str, location_column: str = "location") -> "Formatter":
        """
        按时间+位置去重（同一时间同一地点不应有重复记录）
        """
        subset = [time_column]
        if location_column in self.df.columns:
            subset.append(location_column)
        return self.deduplicate(subset=subset, keep="first")

    def get_result(self) -> pd.DataFrame:
        return self.df

    def get_log(self) -> List[Dict]:
        return self.actions_log
