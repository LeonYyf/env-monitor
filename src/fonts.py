"""
matplotlib 中文字体自动配置。

matplotlib 的默认字体（DejaVu Sans）不含中文字形，直接画中文标签会显示成
方块乱码。本模块不写死某一个字体，而是在系统字体里自动探测一款真实存在、
能显示中文的字体，跨平台生效：

- macOS  → PingFang / 冬青黑体 / 华文黑体
- Windows → 微软雅黑 / 黑体 / 等线
- Linux  → 思源黑体 / 文泉驿

用法：在创建任何图表之前调用一次 setup_chinese_font() 即可。
"""

import platform

from matplotlib import font_manager
from matplotlib import pyplot as plt

# 按平台优先排序的中文字体候选（名字须与 matplotlib 识别到的字体名一致）
_CJK_FONTS = {
    "Darwin": [
        "PingFang HK", "PingFang SC", "Hiragino Sans GB",
        "STHeiti", "Songti SC", "Arial Unicode MS",
    ],
    "Windows": [
        "Microsoft YaHei", "SimHei", "DengXian", "SimSun", "KaiTi",
    ],
    "Linux": [
        "Noto Sans CJK SC", "Source Han Sans SC",
        "WenQuanYi Zen Hei", "WenQuanYi Micro Hei",
    ],
}


def _available_font_names():
    """返回 matplotlib 当前能在系统里识别到的字体名集合。"""
    return {f.name for f in font_manager.fontManager.ttflist}


# 子串兜底：某些系统（尤其 Windows 打包后的 exe）里字体名会带变体后缀，
# 例如「Microsoft YaHei UI」，精确名匹配不到。按这些关键词做一次子串匹配。
_CJK_KEYWORDS = [
    "YaHei", "微软雅黑", "雅黑", "SimHei", "PingFang", "Hiragino",
    "Songti", "Heiti", "KaiTi", "WenQuanYi", "Noto Sans CJK",
    "JhengHei", "黑体", "宋体",
]


def setup_chinese_font():
    """把 matplotlib 全局字体设为系统里能找到的中文字体。

    先按当前平台候选精确匹配，找不到再扫一遍所有平台候选，
    最后用子串关键词兜底。返回选中的字体名；若一个中文字体都
    找不到返回 None（此时中文仍会乱码）。
    """
    # 当前平台候选优先，其余平台候选接在后面兜底
    candidates = list(_CJK_FONTS.get(platform.system(), []))
    seen = set(candidates)
    for names in _CJK_FONTS.values():
        for name in names:
            if name not in seen:
                seen.add(name)
                candidates.append(name)

    available = _available_font_names()
    chosen = next((name for name in candidates if name in available), None)

    # 精确名没匹配上时，按关键词做子串匹配兜底
    if chosen is None:
        for kw in _CJK_KEYWORDS:
            hit = next((name for name in available if kw.lower() in name.lower()), None)
            if hit:
                chosen = hit
                break

    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = (
        [chosen, "DejaVu Sans"] if chosen else ["DejaVu Sans"]
    )
    plt.rcParams["axes.unicode_minus"] = False
    return chosen
