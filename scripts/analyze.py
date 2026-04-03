#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HKJC 赛马分析工具 - 马匹分析模块

提供单匹马多维度评分功能。
"""

from collections import Counter
from scoring import (
    score_history_same_condition,
    score_history_same_venue,
    score_class_fit,
    score_odds_value,
    score_odds_drift,
    score_sectional,
    score_jockey,
    score_trainer,
    score_tips_index_hkjc,
    is_longshot_alert,
    data_confidence,
)


def analyze_horse(horse, venue, distance, track_condition, tips_data=None):
    """
    对单匹马进行多维度评分。

    参数：
        horse       : 马匹数据字典
        venue       : 场地代码 "ST" / "HV"
        distance    : 赛事距离（米）
        track_condition: 赛道状况
        tips_data   : HKJC 贴士指数数据字典 {"tips": {"#马号": 值, ...}, ...}
    """
    # 赔率评分
    if horse["final_odds"]:
        horse["odds_value_score"] = score_odds_value(horse["final_odds"])
        horse["odds_drift_score"] = score_odds_drift(
            horse["opening_odds"], horse["final_odds"]
        )

    # HKJC 官方贴士指数评分
    if tips_data and tips_data.get("tips"):
        horse_no = f"#{horse['no']}"
        tips_value = tips_data["tips"].get(horse_no)
        if tips_value is None:
            # 尝试用马名匹配
            tips_value = tips_data["tips"].get(horse["name"])
        if tips_value:
            horse["tips_index"] = tips_value
            horse["tips_index_score"] = score_tips_index_hkjc(tips_value)
        else:
            horse["tips_index_score"] = 50  # 无贴士数据，返回中性默认值

    # 历史战绩评分
    history = horse.get("history", [])
    horse["history_same_condition_score"] = score_history_same_condition(
        history, venue, distance
    )
    horse["history_same_venue_score"] = score_history_same_venue(history, venue)

    # 班次适配度：用实际抓取的 current_rating 及动态班次区间
    rating = horse.get("current_rating", 40)
    class_ceiling = horse.get("class_ceiling", 40)
    class_floor = horse.get("class_floor", 21)
    horse["class_fit_score"] = score_class_fit(rating, class_ceiling, class_floor)

    # 从历史走位推导惯用跑法（front / closer / even）
    if not horse.get("running_style"):
        run_styles = []
        for r in history[-5:]:  # 最近5场
            rp = r.get("running_positions", [])
            if rp:
                first_pos = rp[0]
                last_pos = rp[-1]
                if first_pos <= 3:
                    run_styles.append("front")
                elif last_pos < first_pos - 2:
                    run_styles.append("closer")
                else:
                    run_styles.append("even")
        if run_styles:
            # 取众数
            horse["running_style"] = Counter(run_styles).most_common(1)[0][0]
        else:
            horse["running_style"] = "even"

    # 配速评分：用历史推导的 running_style
    horse["sectional_score"] = score_sectional(
        pace_index=horse.get("pace_index", 1.0),
        running_style=horse.get("running_style", "even"),
        track_condition=track_condition,
    )

    # 档位评分：沙田草地 1400m 内档(1-4)略占优势
    barrier = horse.get("barrier", 0)
    if barrier:
        if 1 <= barrier <= 4:
            horse["barrier_score"] = 65
        elif 5 <= barrier <= 8:
            horse["barrier_score"] = 55
        elif 9 <= barrier <= 12:
            horse["barrier_score"] = 45
        else:
            horse["barrier_score"] = 38

    # 骑师 / 练马师评分（基于历史战绩统计，次要因素）
    horse["jockey_score"] = score_jockey(
        horse.get("jockey", ""), history
    )
    horse["trainer_score"] = score_trainer(
        horse.get("trainer", ""), history
    )

    # 数据充足度
    same_condition_count = sum(
        1 for r in history
        if r.get("venue") == venue and abs(r.get("distance", 0) - distance) <= 200
    )
    horse["confidence"] = data_confidence(
        same_condition_count, horse["opening_odds"] is not None
    )

    # 冷门关注
    has_top3 = any(
        r.get("position", 99) <= 3
        for r in history
        if r.get("venue") == venue and abs(r.get("distance", 0) - distance) <= 200
    )
    horse["longshot_alert"] = is_longshot_alert(
        final_odds=horse.get("final_odds") or 99,
        opening_odds=horse.get("opening_odds"),
        has_same_condition_top3=has_top3,
        class_fit_score=horse["class_fit_score"],
    )

    return horse
