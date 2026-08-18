"""
数据库连接管理模块
提供 SQLAlchemy 引擎和会话工厂。
数据存储使用 SQLite 单文件数据库，无需安装 MySQL。
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import config

from .models import Base

# 全局引擎和会话工厂（延迟初始化）
_engine = None
_SessionLocal = None


def get_engine():
    """获取数据库引擎（单例模式），首次调用时自动建表。"""
    global _engine
    if _engine is None:
        db_url = config.get_db_url()
        _engine = create_engine(
            db_url,
            echo=False,  # 设为 True 可查看 SQL 日志
            # SQLite 的 sqlite3 连接默认绑定创建它的线程；
            # 导入/清洗在后台线程运行，必须关掉同线程校验。
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        # 首次启动自动创建所有表（SQLite 无独立建表脚本）
        Base.metadata.create_all(_engine)
    return _engine


def get_session() -> Session:
    """获取一个新的数据库会话"""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine())
    return _SessionLocal()
