import pandas as pd
import numpy as np
import config

VOLUME_DEVIATION_RATIO = 0.05   # 相对阈值：同时相差超过 5%（两者都超才判异常，避免大车间误报）
VOLUME_INPUT_ERROR_RATIO = 9.0  # 异常值 > 9 倍正常平均值 → 疑似人工输入数据错误


def _fmt_date(d):
    try:
        return pd.to_datetime(d).strftime("%Y-%m-%d")
    except Exception:
        return str(d)


def compute_compliance(df: pd.DataFrame, cleanroom_class: str):
    particle_cn = list(config.PARTICLE_LIMITS.keys())
    particle = df[df["indicator_cn"].isin(particle_cn)]

    summary_rows = []
    exceed_rows = []

    for cn in particle_cn:
        limit = config.PARTICLE_LIMITS.get(cn, {}).get(cleanroom_class)
        if limit is None:
            continue  # 该级别未配置此粒径限值，跳过

        sub = particle[particle["indicator_cn"] == cn]
        for room, g in sub.groupby("room_name"):
            vals = g["value"].dropna()
            n = len(vals)
            exceed_mask = vals > limit
            n_exceed = int(exceed_mask.sum())

            summary_rows.append({
                "房间": room,
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
        vals = g["体积"].astype(float).tolist()
        n = len(vals)

        # 样本太少（去掉一个最大、一个最小后没有剩余），无法判断波动
        if n < 3:
            summary_rows.append({
                "房间": room,
                "样本数": n,
                "正常平均值(m³)": "—",
                "异常次数": "—",
                "是否异常": "样本不足",
            })
            continue

        # 去极值平均：去掉一个最大值、一个最小值
        normal_avg = float(np.mean(sorted(vals)[1:-1]))

        n_anomaly = 0
        for _, r in g.iterrows():
            v = float(r["体积"])
            diff = v - normal_avg
            abs_diff = abs(diff)
            rel_diff = abs_diff / normal_avg if normal_avg else 0.0
            # 相对偏差超 5% 才算异常
            if rel_diff <= VOLUME_DEVIATION_RATIO:
                continue  # 正常

            n_anomaly += 1
            direction = "偏高" if diff > 0 else "偏低"

            if diff > 0:
                if v > VOLUME_INPUT_ERROR_RATIO * normal_avg:
                    cause = "疑似人工输入数据错误（体积超正常值 9 倍以上）"
                else:
                    cause = "疑似过度清洁/过度耗电：可能风机频率开太高，或回风阀堵塞"
            else:
                cause = "疑似过滤器阻力变大/堵塞、风管系统漏风，或风机频率调得低"

            anomaly_rows.append({
                "日期": _fmt_date(r.get("record_date")),
                "房间": room,
                "体积(m³)": round(v, 1),
                "正常平均值(m³)": round(normal_avg, 1),
                "偏差(%)": round(rel_diff*100, 1),
                "方向": direction,
                "判定/可能原因": cause,
            })

        summary_rows.append({
            "房间": room,
            "样本数": n,
            "正常平均值(m³)": round(normal_avg, 1),
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
