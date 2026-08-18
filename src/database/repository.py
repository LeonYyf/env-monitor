#
# 数据库操作仓库 — 高层数据访问接口
# 封装常用的 CRUD 操作，GUI 层通过此模块访问数据。
#

from typing import Optional, List, Dict, Any
from datetime import datetime
import pandas as pd
from sqlalchemy import text

from .connection import get_session, get_engine
from .models import ImportSession, MeasurementRecord, CleaningLog


class Repository:
    # 统一数据访问仓库

    # ================================================================
    # 导入批次
    # ================================================================
    @staticmethod
    def create_import_session(file_name: str, file_hash: str,
                              sheet_name: str = None, record_count: int = 0,
                              column_mapping: dict = None) -> int:
        # 创建导入记录，返回 session_id
        session_obj = get_session()
        try:
            s = ImportSession(
                file_name=file_name,
                file_hash=file_hash,
                sheet_name=sheet_name,
                record_count=record_count,
                column_mapping=column_mapping,
            )
            session_obj.add(s)
            session_obj.commit()
            return s.id
        finally:
            session_obj.close()

    @staticmethod
    def update_import_count(session_id: int, count: int):
        # 更新导入记录数
        session_obj = get_session()
        try:
            s = session_obj.query(ImportSession).get(session_id)
            if s:
                s.record_count = count
                session_obj.commit()
        finally:
            session_obj.close()

    @staticmethod
    def list_import_sessions() -> pd.DataFrame:
        # 列出所有导入批次
        engine = get_engine()
        return pd.read_sql(
            "SELECT id, file_name, sheet_name, record_count, imported_at "
            "FROM import_sessions ORDER BY imported_at DESC",
            con=engine
        )

    # ================================================================
    # 测量数据
    # ================================================================
    @staticmethod
    def insert_measurements(records: List[Dict[str, Any]], session_id: int):
        # 批量插入测量记录（长格式）
        session_obj = get_session()
        try:
            for r in records:
                mr = MeasurementRecord(
                    import_session_id=session_id,
                    sheet_name=r.get("sheet_name", ""),
                    record_date=r.get("record_date"),
                    room_name=r.get("room_name", ""),
                    room_adjacent=r.get("room_adjacent"),
                    particle_size=r.get("particle_size"),
                    indicator_name=r.get("indicator_name", ""),
                    indicator_cn=r.get("indicator_cn"),
                    value=r.get("value"),
                    unit=r.get("unit"),
                )
                session_obj.add(mr)
            session_obj.commit()
        finally:
            session_obj.close()

    @staticmethod
    def get_all_measurements(sheet_name: str = None) -> pd.DataFrame:
        # 获取所有测量数据（返回 DataFrame）
        engine = get_engine()
        if sheet_name:
            return pd.read_sql(
                text("SELECT * FROM measurement_records WHERE sheet_name = :sheet "
                     "ORDER BY record_date, room_name"),
                con=engine, params={"sheet": sheet_name}
            )
        return pd.read_sql(
            "SELECT * FROM measurement_records ORDER BY record_date, room_name",
            con=engine
        )

    @staticmethod
    def get_measurements_by_indicator(indicator_name: str,
                                      sheet_name: str = None) -> pd.DataFrame:
        # 按指标获取数据 — 返回透视后的 DataFrame（行=日期×房间, 列=指标值）
        engine = get_engine()
        sql = ("SELECT * FROM measurement_records WHERE indicator_name = :ind "
               "ORDER BY record_date, room_name")
        params = {"ind": indicator_name}
        if sheet_name:
            sql = ("SELECT * FROM measurement_records "
                   "WHERE indicator_name = :ind AND sheet_name = :sheet "
                   "ORDER BY record_date, room_name")
            params["sheet"] = sheet_name
        return pd.read_sql(text(sql), con=engine, params=params)

    @staticmethod
    def get_rooms() -> List[str]:
        # 获取所有房间名称
        engine = get_engine()
        df = pd.read_sql(
            "SELECT DISTINCT room_name FROM measurement_records ORDER BY room_name",
            con=engine
        )
        return df["room_name"].tolist()

    @staticmethod
    def get_indicators() -> List[Dict[str, str]]:
        # 获取所有指标名称
        engine = get_engine()
        df = pd.read_sql(
            "SELECT DISTINCT indicator_name, indicator_cn, unit "
            "FROM measurement_records ORDER BY indicator_name",
            con=engine
        )
        return df.to_dict("records")

    @staticmethod
    def get_measurement_count(sheet_name: str = None) -> int:
        # 获取记录总数
        session_obj = get_session()
        try:
            q = session_obj.query(MeasurementRecord)
            if sheet_name:
                q = q.filter(MeasurementRecord.sheet_name == sheet_name)
            return q.count()
        finally:
            session_obj.close()

    @staticmethod
    def get_columns_with_data() -> List[str]:
        # 获取 measurement_records 中有数据的列名
        skip_cols = {"id", "import_session_id", "created_at"}
        engine = get_engine()
        df = pd.read_sql("SELECT * FROM measurement_records LIMIT 1", con=engine)
        cols = [c for c in df.columns if c not in skip_cols]
        return cols

    # ================================================================
    # 清空测量数据（本系统不存储历史数据，数据库只保留当前数据集）
    # ================================================================
    @staticmethod
    def count_measurements() -> int:
        # 统计 measurement_records 当前记录数。
        session_obj = get_session()
        try:
            return session_obj.query(MeasurementRecord).count()
        finally:
            session_obj.close()

    @staticmethod
    def clear_measurements() -> int:
        # 清空 measurement_records 表，返回清空前的记录数。
        #
        # 只清空测量数据本身；import_sessions / cleaning_log 等辅助表保持不变。
        #
        engine = get_engine()
        n = Repository.count_measurements()
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM measurement_records"))
        return n

    # ================================================================
    # 清洗日志
    # ================================================================
    @staticmethod
    def log_cleaning_action(record_id: int, step_name: str, method_used: str,
                            column_affected: str = None, old_value: str = None,
                            new_value: str = None):
        # 记录清洗操作
        session_obj = get_session()
        try:
            log = CleaningLog(
                record_id=record_id,
                step_name=step_name,
                method_used=method_used,
                column_affected=column_affected,
                old_value=old_value,
                new_value=new_value,
            )
            session_obj.add(log)
            session_obj.commit()
        finally:
            session_obj.close()
