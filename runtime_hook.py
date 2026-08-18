"""
PyInstaller 运行时钩子（--runtime-hook 指定）。

作用：程序被 PyInstaller 打包成单文件 exe 后，所有代码会解压到一个
临时目录（sys._MEIPASS），退出即删除。若不处理，config.py 里的
BASE_DIR = Path(__file__).parent 会指向临时目录，导致数据库被建在
临时目录里、每次打开都丢数据。

本钩子在主程序运行前执行，直接改写 config 模块的属性，把数据目录
改到 exe 所在目录；同时把 Windows 上的图表字体改成微软雅黑。
全程不改动任何源码。
"""

import sys
import platform
from pathlib import Path

import config


# 打包后：把数据目录从临时目录改到 exe 所在目录，保证数据持久化
if getattr(sys, "frozen", False):
    exe_dir = Path(sys.executable).parent
    config.BASE_DIR = exe_dir
    config.DATA_DIR = exe_dir / "data"
    config.RAW_DATA_DIR = config.DATA_DIR / "raw"
    config.PROCESSED_DATA_DIR = config.DATA_DIR / "processed"
    config.CHART_DIR = config.DATA_DIR / "charts"
    config.REPORT_DIR = config.DATA_DIR / "reports"
    config.DB_PATH = config.DATA_DIR / "env_monitoring.db"

    for d in (config.RAW_DATA_DIR, config.PROCESSED_DATA_DIR,
              config.CHART_DIR, config.REPORT_DIR):
        d.mkdir(parents=True, exist_ok=True)


# Windows 上图表中文用微软雅黑（macOS 字体 Arial Unicode MS 不存在）
if platform.system() == "Windows":
    config.VIZ_DEFAULTS["font_family"] = "Microsoft YaHei"
