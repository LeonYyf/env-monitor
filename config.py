import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"               
PROCESSED_DATA_DIR = DATA_DIR / "processed"    
CHART_DIR = DATA_DIR / "charts"               
REPORT_DIR = DATA_DIR / "reports"             

for d in [RAW_DATA_DIR, PROCESSED_DATA_DIR, CHART_DIR, REPORT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "env_monitoring.db"

def get_db_url():
    return f"sqlite:///{DB_PATH.as_posix()}"

CLEANING_DEFAULTS = {
    "missing_method": "median",         
    "outlier_method": "iqr",
    "outlier_threshold": 1.5,
    "zscore_threshold": 3.0,
    "dedup_method": "keep_first",
    "time_format": "%Y-%m-%d %H:%M:%S",
}

VIZ_DEFAULTS = {
    "figure_dpi": 100,
    "figure_size": (10, 6),
    "color_palette": "Set2",
    "font_family": "Arial Unicode MS",
}

KNOWN_INDICATORS = {
    "particle_05um":      ["0.5µm尘埃粒子", "个/m³", "≥0.5µm颗粒数"],
    "particle_5um":       ["5µm尘埃粒子", "个/m³", "≥5µm颗粒数"],
    "supply_air_volume":  ["送风量", "m³/h", "送风量"],
    "air_changes":        ["换气次数", "次/h", "换气次数"],
}

SHEET_PARTICLE = "尘埃粒子"
SHEET_AIRFLOW = "风量"       

CLEANROOM_CLASSES = ["百级 (ISO 5)", "千级 (ISO 6)", "万级 (ISO 7)", "十万级 (ISO 8)"]

PARTICLE_LIMITS = {
    "0.5µm尘埃粒子": {
        "百级 (ISO 5)": 3520,
        "千级 (ISO 6)": 35200,
        "万级 (ISO 7)": 352000,
        "十万级 (ISO 8)": 3520000,
    },
    "5µm尘埃粒子": {
        "百级 (ISO 5)": 29,
        "千级 (ISO 6)": 293,
        "万级 (ISO 7)": 2930,
        "十万级 (ISO 8)": 29300,
    },
}
DEFAULT_CLEANROOM_CLASS = "万级 (ISO 7)"
