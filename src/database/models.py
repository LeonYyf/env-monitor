"""
SQLAlchemy ORM 模型定义
映射到 SQLite 中的 3 张表。
"""
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text, JSON,
    ForeignKey, Index
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()


class ImportSession(Base):
    """Excel 导入批次记录"""
    __tablename__ = "import_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String(500), nullable=False, comment="原始文件名")
    file_hash = Column(String(64), nullable=False, comment="SHA-256")
    sheet_name = Column(String(200), comment="Excel 工作表名")
    imported_at = Column(DateTime, default=datetime.now, comment="导入时间")
    record_count = Column(Integer, comment="导入记录数")
    column_mapping = Column(JSON, comment="原始列映射信息")
    notes = Column(Text, comment="备注")

    # 关联
    records = relationship("MeasurementRecord", back_populates="session",
                           cascade="all, delete-orphan")


class MeasurementRecord(Base):
    """核心测量数据 — 长格式，适应任意指标"""
    __tablename__ = "measurement_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    import_session_id = Column(Integer, ForeignKey("import_sessions.id"), nullable=False)
    sheet_name = Column(String(50), nullable=False, comment="数据来源sheet")
    record_date = Column(Date, nullable=False, comment="测量日期")
    room_name = Column(String(100), nullable=False, comment="房间名称")
    room_adjacent = Column(String(50), comment="相邻区域")
    particle_size = Column(String(10), comment="粒径（0.5µm / 5µm）")
    indicator_name = Column(String(100), nullable=False, comment="指标英文字段名")
    indicator_cn = Column(String(100), comment="指标中文名")
    value = Column(Float, nullable=False, comment="数值")
    unit = Column(String(20), comment="单位")
    created_at = Column(DateTime, default=datetime.now)

    # 关联
    session = relationship("ImportSession", back_populates="records")

    __table_args__ = (
        Index("idx_date", "record_date"),
        Index("idx_room", "room_name"),
        Index("idx_indicator", "indicator_name"),
        Index("idx_sheet", "sheet_name"),
        Index("idx_session", "import_session_id"),
    )


class CleaningLog(Base):
    """数据清洗操作日志"""
    __tablename__ = "cleaning_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_id = Column(Integer, ForeignKey("measurement_records.id"), comment="关联记录")
    step_name = Column(String(200), nullable=False, comment="清洗步骤")
    method_used = Column(String(200), comment="使用的方法")
    column_affected = Column(String(100), comment="影响的列")
    old_value = Column(Text, comment="清洗前值")
    new_value = Column(Text, comment="清洗后值")
    applied_at = Column(DateTime, default=datetime.now)
