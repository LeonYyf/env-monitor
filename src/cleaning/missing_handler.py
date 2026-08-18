import pandas as pd


class MissingHandler:

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()

    def detect_missing(self) -> pd.DataFrame:
        total = len(self.df)
        results = []
        for col in self.df.columns:
            missing = self.df[col].isna().sum()
            if missing > 0:
                results.append({
                    "列名": col,
                    "缺失数量": missing,
                    "缺失比例": f"{missing / total * 100:.1f}%",
                    "数据类型": str(self.df[col].dtype),
                })
        return pd.DataFrame(results)
