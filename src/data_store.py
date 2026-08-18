# 跨页面共享的内存数据。
#
# 导入页把「已导入数据」写入这里，清洗页读取并回写清洗结果，
# EDA 页和报告页读取清洗结果，避免每页都从数据库重复查询。
#


class DataStore:
    def __init__(self):
        self.raw_df = None       # 导入后的原始长格式数据（含 sheet_name 列）
        self.cleaned_df = None   # 清洗后的数据

    def set_imported(self, df):
        self.raw_df = df.copy() if df is not None else None
        self.cleaned_df = None

    def set_cleaned(self, df):
        self.cleaned_df = df.copy() if df is not None else None

    def get_for_cleaning(self):
        return self.raw_df

    def get_for_analysis(self):
        # 优先清洗结果，没有则退回原始数据
        return self.cleaned_df if self.cleaned_df is not None else self.raw_df

    def reset(self):
        self.raw_df = None
        self.cleaned_df = None


data_store = DataStore()
