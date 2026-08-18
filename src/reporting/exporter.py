"""
报告导出模块
支持导出为 Excel (.xlsx)
"""

import pandas as pd
from pathlib import Path
from typing import Dict, Union


def export_to_excel(sections: Dict[str, Union[pd.DataFrame, str]], file_path: str):
    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        for sheet_name, content in sections.items():
            # Sheet 名最长31字符
            safe_name = sheet_name[:31]

            if isinstance(content, pd.DataFrame):
                content.to_excel(writer, sheet_name=safe_name, index=False)
            elif isinstance(content, str):
                lines = content.split("\n")
                text_df = pd.DataFrame({"内容": lines})
                text_df.to_excel(writer, sheet_name=safe_name, index=False)

    return file_path


def export_dataframe_to_csv(df: pd.DataFrame, file_path: str):
    df.to_csv(file_path, index=False, encoding="utf-8-sig")
    return file_path
