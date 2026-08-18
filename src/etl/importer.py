"""
数据导入模块
将 ExcelReader 解析后的长格式 DataFrame 逐条写入数据库。
"""

from typing import Dict, List, Optional, Callable
from pathlib import Path
import hashlib
import pandas as pd
import numpy as np

from src.database.repository import Repository


class Importer:
    """数据导入器 — 长格式 DataFrame → 数据库"""

    def __init__(self, progress_callback: Callable = None):
        """
        progress_callback(percent: int, message: str)
        用于 GUI 进度更新，可选。
        """
        self.progress = progress_callback or (lambda p, m: None)

    def import_sheet(
        self,
        df: pd.DataFrame,
        file_name: str,
        file_hash: str,
        sheet_name: str,
    ) -> int:
        """
        将一个 sheet 的长格式 DataFrame 导入数据库。

        参数:
            df: ExcelReader 解析后的长格式 DataFrame
                必须包含: record_date, room_name, indicator_name, value
                可选: room_adjacent, particle_size, indicator_cn, unit
            file_name: 源文件名
            file_hash: 文件 SHA-256
            sheet_name: Excel 工作表名

        返回: 导入的记录数
        """
        self.progress(0, f"正在准备导入「{sheet_name}」...")

        # 1. 创建导入批次记录
        session_id = Repository.create_import_session(
            file_name=file_name,
            file_hash=file_hash,
            sheet_name=sheet_name,
            column_mapping={
                "columns": list(df.columns),
                "shape": list(df.shape),
            },
        )

        # 2. DataFrame → 记录列表
        self.progress(10, "正在转换数据格式...")
        records = []
        for _, row in df.iterrows():
            if pd.isna(row.get("value")):
                continue
            try:
                record = {
                    "sheet_name": sheet_name,
                    "record_date": row.get("record_date"),
                    "room_name": row.get("room_name", ""),
                    "room_adjacent": row.get("room_adjacent") if pd.notna(row.get("room_adjacent")) else None,
                    "particle_size": row.get("particle_size") if pd.notna(row.get("particle_size")) else None,
                    "indicator_name": row.get("indicator_name", ""),
                    "indicator_cn": row.get("indicator_cn", ""),
                    "value": float(row.get("value")),
                    "unit": row.get("unit", ""),
                }
                records.append(record)
            except (ValueError, TypeError):
                continue

        if not records:
            self.progress(100, f"「{sheet_name}」没有有效数据")
            return 0

        # 3. 批量写入
        total = len(records)
        self.progress(30, f"正在写入 {total} 条记录...")
        batch_size = 500

        for i in range(0, total, batch_size):
            batch = records[i:i + batch_size]
            Repository.insert_measurements(batch, session_id)
            pct = 30 + int(60 * (i + len(batch)) / total)
            self.progress(pct, f"「{sheet_name}」已写入 {min(i + batch_size, total)} / {total} 条...")

        # 4. 更新导入计数
        Repository.update_import_count(session_id, total)

        self.progress(100, f"「{sheet_name}」导入完成，共 {total} 条记录")
        return total

    def import_all_sheets(
        self,
        sheets_data: Dict[str, pd.DataFrame],
        file_path: str,
    ) -> Dict[str, int]:
        """
        导入所有 sheet 的数据。

        参数:
            sheets_data: {sheet_name: DataFrame} 来自 ExcelReader.read_all_sheets()
            file_path: Excel 文件的完整路径

        返回: {sheet_name: record_count}
        """
        # 计算文件哈希
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
        file_hash = sha.hexdigest()

        file_name = Path(file_path).name
        results = {}
        total_sheets = len(sheets_data)

        for i, (sheet_name, df) in enumerate(sheets_data.items()):
            if df.empty:
                self.progress(
                    int((i + 1) / total_sheets * 100),
                    f"「{sheet_name}」为空，跳过"
                )
                results[sheet_name] = 0
                continue

            count = self.import_sheet(
                df=df,
                file_name=file_name,
                file_hash=file_hash,
                sheet_name=sheet_name,
            )
            results[sheet_name] = count

        return results


def check_duplicate_import(file_path: str) -> bool:
    """检查文件是否已经导入过（按 SHA-256 哈希）"""
    # 暂时简化实现，后续可完善
    return False
