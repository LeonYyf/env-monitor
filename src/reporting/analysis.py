import pandas as pd
import numpy as np
import config

VOLUME_DEVIATION_RATIO = 0.05   # 相对阈值：与标准体积相差超过 5% 判异常
VOLUME_INPUT_ERROR_RATIO = 9.0  # 异常值 > 9 倍标准体积 → 疑似人工输入数据错误
VOLUME_LOW_INPUT_ERROR_RATIO = 0.15  # 体积低于标准体积 15%（即比标准低 85% 以上）→ 疑似人工输入错误


def _fmt_date(d):
    try:
        return pd.to_datetime(d).strftime("%Y-%m-%d")
    except Exception:
        return str(d)


def compute_compliance(df: pd.DataFrame):
    particle_cn = list(config.PARTICLE_LIMITS.keys())
    particle = df[df["indicator_cn"].isin(particle_cn)]

    summary_rows = []
    exceed_rows = []

    for cn in particle_cn:
        sub = particle[particle["indicator_cn"] == cn]
        for room, g in sub.groupby("room_name"):
            # 每个房间按其所在区域取对应限值；未知房间按车间区兜底（宽松，避免误报）
            zone = config.room_zone(room) or "车间区"
            limit = config.PARTICLE_LIMITS.get(cn, {}).get(zone)
            if limit is None:
                continue  # 该粒径在此区域未配置限值，跳过

            vals = g["value"].dropna()
            n = len(vals)
            exceed_mask = vals > limit
            n_exceed = int(exceed_mask.sum())

            summary_rows.append({
                "房间": room,
                "区域": zone,
                "粒径": cn,
                "国标限值": limit,
                "样本数": n,
                "最大值": round(vals.max(), 0) if n else "—",
                "超标次数": n_exceed,
                "超标率": f"{n_exceed / n * 100:.1f}%" if n else "0%",
                "是否超标": "是" if n_exceed > 0 else "否",
            })

            # 超标明细
            if n_exceed > 0:
                for _, r in g[exceed_mask].iterrows():
                    exceed_rows.append({
                        "日期": _fmt_date(r.get("record_date")),
                        "房间": room,
                        "区域": zone,
                        "粒径": cn,
                        "实测值": round(r["value"], 0),
                        "国标限值": limit,
                        "超限倍数": round(r["value"] / limit, 2),
                    })

    summary = pd.DataFrame(summary_rows)
    exceed = pd.DataFrame(exceed_rows)

    # 排序：超标的排前面，次数多的在前
    if not summary.empty:
        summary["_bad"] = (summary["是否超标"] == "是").astype(int)
        summary = summary.sort_values(
            ["_bad", "超标次数"], ascending=[False, False]
        ).drop(columns="_bad").reset_index(drop=True)

    if not exceed.empty:
        exceed = exceed.sort_values(
            "超限倍数", ascending=False
        ).reset_index(drop=True)

    return summary, exceed


def compute_period_growth(df: pd.DataFrame):
    """尘埃粒子逐时段环比变化。

    每个「房间 × 粒径」按监测日期排序，计算每个时段相对上一时段的
    增长/下降百分比：(本期值 − 上期值) ÷ 上期值 × 100%。
    首个时段没有上一时段，变化率记为 0%（表示无变化，作为基准）。
    """
    particle_cn = list(config.PARTICLE_LIMITS.keys())
    particle = df[df["indicator_cn"].isin(particle_cn)]
    if particle.empty:
        return pd.DataFrame()

    # 同一「房间 × 粒径 × 日期」可能有多条记录，取均值作为该时段水平
    daily = (
        particle
        .groupby(["room_name", "indicator_cn", "record_date"], as_index=False)["value"]
        .mean()
    )

    rows = []
    for (room, size), sub in daily.groupby(["room_name", "indicator_cn"]):
        sub = sub.sort_values("record_date")
        vals = sub["value"].astype(float).tolist()
        dates = sub["record_date"].tolist()

        for i in range(len(sub)):
            cur = float(vals[i])
            if i == 0:
                rows.append({
                    "房间": room,
                    "粒径": size,
                    "日期": _fmt_date(dates[i]),
                    "本期值": round(cur),
                    "上期值": float("nan"),
                    "变化率(%)": 0.0,   # 首个时段无上一时段，环比记为 0%
                })
            else:
                prev = float(vals[i - 1])
                # 上一时段为 0 时百分比无意义，记 NaN（前端显示「—」）
                rate = (cur - prev) / prev * 100 if prev else float("nan")
                rows.append({
                    "房间": room,
                    "粒径": size,
                    "日期": _fmt_date(dates[i]),
                    "本期值": round(cur),
                    "上期值": round(prev),
                    "变化率(%)": round(rate, 1) if rate == rate else float("nan"),
                })

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(["房间", "粒径", "日期"]).reset_index(drop=True)
    return result


def compute_room_volume(df: pd.DataFrame):
    flow = df[df["indicator_cn"].isin(["送风量", "换气次数"])]
    if flow.empty:
        return pd.DataFrame(), pd.DataFrame()

    # 宽表：行 = (日期, 房间)，列 = 送风量 / 换气次数
    wide = flow.pivot_table(
        index=["record_date", "room_name"],
        columns="indicator_cn",
        values="value",
        aggfunc="mean",
    )

    if "送风量" not in wide.columns or "换气次数" not in wide.columns:
        return pd.DataFrame(), pd.DataFrame()

    # 体积 = 送风量 ÷ 换气次数（m³ = m³/h ÷ 次/h），转成带日期×房间的长表
    vol_df = (
        (wide["送风量"] / wide["换气次数"])
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
        .rename("体积")
        .reset_index()
    )
    if vol_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    summary_rows = []
    anomaly_rows = []

    for room, g in vol_df.groupby("room_name"):
        n = len(g)

        # 标准体积来自代码里写死的房间体积（新版 Excel「房间体积」列）；
        # 未配置标准体积的房间无法判定。
        standard_volume = config.ROOM_VOLUMES.get(room)
        if standard_volume is None:
            summary_rows.append({
                "房间": room,
                "样本数": n,
                "标准体积(m³)": "—",
                "异常次数": "—",
                "是否异常": "未配置标准体积",
            })
            continue

        n_anomaly = 0
        for _, r in g.iterrows():
            v = float(r["体积"])
            diff = v - standard_volume
            rel_diff = abs(diff) / standard_volume if standard_volume else 0.0
            # 相对偏差超 5% 才算异常
            if rel_diff <= VOLUME_DEVIATION_RATIO:
                continue  # 正常

            n_anomaly += 1
            direction = "偏高" if diff > 0 else "偏低"

            if diff > 0:
                if v > VOLUME_INPUT_ERROR_RATIO * standard_volume:
                    cause = "疑似人工输入数据错误（体积超标准值 9 倍以上）"
                else:
                    cause = "疑似过度清洁/过度耗电：可能风机频率开太高，或回风阀堵塞"
            else:
                if v < VOLUME_LOW_INPUT_ERROR_RATIO * standard_volume:
                    cause = "疑似人工输入错误（体积低于标准85%以上）"
                else:
                    cause = "疑似过滤器阻力变大/堵塞、风管系统漏风，或风机频率调得低"

            anomaly_rows.append({
                "日期": _fmt_date(r.get("record_date")),
                "房间": room,
                "体积(m³)": round(v, 1),
                "标准体积(m³)": round(standard_volume, 1),
                "偏差(%)": round(rel_diff*100, 1),
                "方向": direction,
                "判定/可能原因": cause,
            })

        summary_rows.append({
            "房间": room,
            "样本数": n,
            "标准体积(m³)": round(standard_volume, 1),
            "异常次数": n_anomaly,
            "是否异常": "是" if n_anomaly > 0 else "否",
        })

    summary = pd.DataFrame(summary_rows)
    anomaly = pd.DataFrame(anomaly_rows)

    # 排序：异常房间排前面；异常明细按 /房间 + 日期/ 排列
    if not summary.empty:
        summary["_bad"] = (summary["是否异常"] == "是").astype(int)
        summary = summary.sort_values(
            ["_bad", "异常次数"], ascending=[False, False]
        ).drop(columns="_bad").reset_index(drop=True)

    if not anomaly.empty:
        anomaly = anomaly.sort_values(["房间", "日期"]).reset_index(drop=True)

    return summary, anomaly


def compute_air_changes_compliance(df: pd.DataFrame):
    """换气次数达标检查。

    逐房间逐日期取换气次数，与该房间所在区域的标准（实验区≥20 / 车间区≥15）
    比较，低于标准即「未达标」。输出长表，供结果报告页透视展示与黄色高亮。
    """
    air = df[df["indicator_cn"] == "换气次数"]
    if air.empty:
        return pd.DataFrame()

    rows = []
    for (room, date), g in air.groupby(["room_name", "record_date"]):
        val = float(g["value"].mean())
        zone = config.room_zone(room) or "车间区"  # 未知房间按车间区兜底
        std = config.AIR_CHANGE_STD.get(zone)
        if std is None:
            continue
        rows.append({
            "房间": room,
            "区域": zone,
            "日期": _fmt_date(date),
            "换气次数": round(val, 1),
            "标准": f"≥{std}",
            "是否达标": "是" if val >= std else "否",
        })

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(["房间", "日期"]).reset_index(drop=True)
    return result


def compute_bacteria_compliance(df: pd.DataFrame):
    """浮游菌平均浓度合规判定。

    逐房间取平均浓度，与该房间所在区域标准（百级区≤5 / 实验区≤100 / 车间区≤500）
    比较。输出 summary（房间汇总）与 exceed（超标明细）两张表。
    """
    bacteria = df[df["indicator_cn"] == "浮游菌平均浓度"]
    if bacteria.empty:
        return pd.DataFrame(), pd.DataFrame()

    summary_rows = []
    exceed_rows = []

    for room, g in bacteria.groupby("room_name"):
        zone = config.bacteria_zone(room) or "车间区"  # 未知房间按车间区兜底（宽松，避免误报）
        std = config.BACTERIA_STD.get(zone)
        if std is None:
            continue

        vals = g["value"].dropna()
        n = len(vals)
        exceed_mask = vals > std
        n_exceed = int(exceed_mask.sum())

        summary_rows.append({
            "房间": room,
            "区域": zone,
            "标准": std,
            "样本数": n,
            "最大值": round(vals.max(), 2) if n else "—",
            "平均值": round(vals.mean(), 2) if n else "—",
            "超标次数": n_exceed,
            "超标率": f"{n_exceed / n * 100:.1f}%" if n else "0%",
            "是否超标": "是" if n_exceed > 0 else "否",
        })

        if n_exceed > 0:
            for _, r in g[exceed_mask].iterrows():
                exceed_rows.append({
                    "日期": _fmt_date(r.get("record_date")),
                    "房间": room,
                    "区域": zone,
                    "实测值": round(r["value"], 2),
                    "标准": std,
                    "超标倍数": round(r["value"] / std, 2),
                })

    summary = pd.DataFrame(summary_rows)
    exceed = pd.DataFrame(exceed_rows)

    if not summary.empty:
        summary["_bad"] = (summary["是否超标"] == "是").astype(int)
        summary = summary.sort_values(
            ["_bad", "超标次数"], ascending=[False, False]
        ).drop(columns="_bad").reset_index(drop=True)

    if not exceed.empty:
        exceed = exceed.sort_values("超标倍数", ascending=False).reset_index(drop=True)

    return summary, exceed


def compute_bacteria_growth(df: pd.DataFrame):
    """浮游菌平均浓度逐时段环比变化。

    每个房间按监测日期排序，计算相邻时段的环比增长/下降百分比，
    首个时段无上一时段，变化率记为 0%（基准）。
    """
    bacteria = df[df["indicator_cn"] == "浮游菌平均浓度"]
    if bacteria.empty:
        return pd.DataFrame()

    daily = (
        bacteria
        .groupby(["room_name", "record_date"], as_index=False)["value"]
        .mean()
    )

    rows = []
    for room, sub in daily.groupby("room_name"):
        sub = sub.sort_values("record_date")
        vals = sub["value"].astype(float).tolist()
        dates = sub["record_date"].tolist()

        for i in range(len(sub)):
            cur = float(vals[i])
            if i == 0:
                rows.append({
                    "房间": room,
                    "日期": _fmt_date(dates[i]),
                    "本期值": round(cur, 2),
                    "上期值": float("nan"),
                    "变化率(%)": 0.0,
                })
            else:
                prev = float(vals[i - 1])
                rate = (cur - prev) / prev * 100 if prev else float("nan")
                rows.append({
                    "房间": room,
                    "日期": _fmt_date(dates[i]),
                    "本期值": round(cur, 2),
                    "上期值": round(prev, 2),
                    "变化率(%)": round(rate, 1) if rate == rate else float("nan"),
                })

    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(["房间", "日期"]).reset_index(drop=True)
    return result
