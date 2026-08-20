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
    "particle_1um":       ["1µm尘埃粒子", "个/m³", "≥1µm颗粒数"],
    "particle_5um":       ["5µm尘埃粒子", "个/m³", "≥5µm颗粒数"],
    "supply_air_volume":  ["送风量", "m³/h", "送风量"],
    "air_changes":        ["换气次数", "次/h", "换气次数"],
    "bacteria_concentration": ["浮游菌平均浓度", "个/m³", "浮游菌平均浓度"],
}

SHEET_PARTICLE = "尘埃粒子"
SHEET_AIRFLOW = "风量"

# —— 洁净区房间区域划分（按房间名，不按列号，兼容列顺序变化）——
# 实验区（严格标准）：微生物/无菌/阳性对照 实验室
LAB_ROOMS = [
    "微生物实验室二更", "微生物实验室缓冲间", "微生物实验室洁具间", "微生物实验室",
    "无菌实验室二更", "无菌实验室缓冲间", "无菌实验室洁具间", "无菌实验室",
    "阳性对照间二更", "阳性对照间缓冲间", "阳性对照间洁具间", "阳性对照间",
]
# 车间区（宽松标准）：车间及辅助房间
WORKSHOP_ROOMS = [
    "车间女二更", "车间男二更", "车间缓冲间", "整衣间", "洗衣间",
    "车间洁具间", "器具处理间", "器具清洗间", "废弃物缓冲间", "洁净走廊",
    "加工间", "烘干间", "组装车间", "精洗间", "物料传递间", "内包车间",
]


def room_zone(room_name: str):
    # 返回房间所属区域："实验区" / "车间区"；未知房间返回 None
    if room_name in LAB_ROOMS:
        return "实验区"
    if room_name in WORKSHOP_ROOMS:
        return "车间区"
    return None


# 百级区（超净操作台/安全柜）：浮游菌标准最严（≤5 个/m³）
HUNDRED_GRADE_ROOMS = [
    "微生物实验室百级工作台", "无菌实验室百级工作台", "生物安全柜",
]

# 浮游菌限值标准：按区域（单位 个/m³）
BACTERIA_STD = {"百级区": 5, "实验区": 100, "车间区": 500}


def bacteria_zone(room_name: str):
    # 返回房间所属区域（浮游菌三档）："百级区" / "实验区" / "车间区"；未知返回 None
    if room_name in HUNDRED_GRADE_ROOMS:
        return "百级区"
    if room_name in LAB_ROOMS:
        return "实验区"
    if room_name in WORKSHOP_ROOMS:
        return "车间区"
    return None


# 尘埃粒子国标限值：粒径 × 区域（单位 个/m³）
PARTICLE_LIMITS = {
    "0.5µm尘埃粒子": {"实验区": 35000, "车间区": 3500000},
    "1µm尘埃粒子":   {"实验区": 83200, "车间区": 832000},
    "5µm尘埃粒子":   {"实验区": 2000,  "车间区": 20000},
}

# 换气次数标准：按区域（单位 次/h）
AIR_CHANGE_STD = {"实验区": 20, "车间区": 15}

# 房间标准体积（m³）：来自新版 Excel「房间体积」列，写死用于体积一致性判定
ROOM_VOLUMES = {
    "车间男二更": 64.22, "车间女二更": 85.36, "车间缓冲间": 51.50, "洁净走廊": 161.12,
    "精洗间": 225, "物料传递间": 102.52, "内包车间": 171.68, "组装车间": 1062.41,
    "烘干间": 46.88, "加工间": 172.02, "洗衣间": 34.20, "整衣间": 45.30,
    "车间洁具间": 27.90, "器具处理间": 49.80, "器具清洗间": 34.66, "废弃物缓冲间": 13.80,
    "阳性对照间二更": 7, "阳性对照间缓冲间": 7, "阳性对照间洁具间": 7.28, "阳性对照间": 26.8,
    "无菌实验室二更": 7, "无菌实验室缓冲间": 7, "无菌实验室洁具间": 7.28, "无菌实验室": 24.62,
    "微生物实验室二更": 7, "微生物实验室缓冲间": 7, "微生物实验室洁具间": 7.28, "微生物实验室": 32.03,
}
