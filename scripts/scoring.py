#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HKJC 赛马分析工具 - 评分函数模块

包含所有多维度评分函数：
- 历史战绩评分（同条件/同场地）
- 赔率评分（绝对值/走势）
- 配速评分
- 骑师/练马师评分
- 贴士指数评分
- 综合评分计算
"""


# ==============================================================================
# 历史战绩评分
# ==============================================================================

def score_history_same_condition(results, venue, distance, tolerance=200):
    """
    评分：同距离+同场地近5场战绩（0-100）。

    results : 历史出赛列表，每项为 {"venue": "ST", "distance": 1400, "position": 1}
    venue   : 本场场地 "ST" / "HV"
    distance: 本场距离（米）
    """
    same = [
        r for r in results
        if r.get("venue") == venue
        and abs(r.get("distance", 0) - distance) <= tolerance
    ]
    same = same[-5:]  # 取最近5场

    if not same:
        return 40  # 中性默认，无同条件记录不惩罚

    positions = [r.get("position", 99) for r in same]
    wins = sum(1 for p in positions if p == 1)
    top3 = sum(1 for p in positions if p <= 3)
    recent = len(same)

    if wins >= 2:
        return 75 + min(15, wins * 5)
    if wins == 1:
        base = 55
        # 近3场有冠则加分
        if any(p == 1 for p in positions[-3:]):
            base += 10
        return base
    if top3 >= 2:
        return 42
    if top3 == 1:
        return 33
    return 15


def score_history_same_venue(results, venue):
    """
    评分：同场地不限距离近5场战绩（0-100）。
    """
    same = [r for r in results if r.get("venue") == venue]
    same = same[-5:]

    if not same:
        return 40

    positions = [r.get("position", 99) for r in same]
    wins = sum(1 for p in positions if p == 1)
    top3 = sum(1 for p in positions if p <= 3)

    if wins >= 2:
        return 72
    if wins == 1:
        return 55
    if top3 >= 2:
        return 40
    if top3 == 1:
        return 30
    return 15


# ==============================================================================
# 班次评分
# ==============================================================================

def score_class_fit(current_rating, class_ceiling, class_floor):
    """
    评分：班次适配度（0-100）。

    current_rating : 马匹当前评分
    class_ceiling  : 班次上限评分
    class_floor    : 班次下限评分
    """
    if current_rating >= class_ceiling + 5:
        return 80  # 明显降班
    elif current_rating >= class_floor:
        return 60  # 正常竞争
    elif current_rating >= class_floor - 3:
        return 45
    else:
        return 25  # 升班，竞争吃力


# ==============================================================================
# 赔率评分
# ==============================================================================

def score_odds_value(odds):
    """
    评分：临场赔率绝对值（0-100）。
    """
    if odds < 3.0:
        return 90
    elif odds < 5.0:
        return 70
    elif odds < 10.0:
        return 50
    elif odds < 20.0:
        return 30
    else:
        return 10


def score_odds_drift(opening_odds, final_odds):
    """
    评分：赔率走势变化幅度（0-100）。
    opening_odds 为 None 时返回中性默认值 50。
    """
    if opening_odds is None or opening_odds <= 0:
        return 50  # 无开盘赔率数据

    change_ratio = (opening_odds - final_odds) / opening_odds  # 正数=缩水，负数=拉长

    if change_ratio > 0.50:
        return 90
    elif change_ratio > 0.20:
        return 70
    elif change_ratio >= -0.20:
        return 50
    elif change_ratio >= -0.50:
        return 30
    else:
        return 10


# ==============================================================================
# 配速评分
# ==============================================================================

def score_sectional(pace_index, running_style, track_condition):
    """
    评分：配速/分段指数（0-100）。

    pace_index     : 后段冲刺指数（实际后300米时间 / 标准后300米时间，<1 越好）
    running_style  : "front" / "closer" / "even"
    track_condition: "fast" / "good" / "soft"
    """
    # 配速指数基础分
    if pace_index <= 0:
        base = 50  # 无数据
    elif pace_index < 0.97:
        base = 85
    elif pace_index < 1.00:
        base = 72
    elif pace_index < 1.03:
        base = 55
    else:
        base = 35

    # 跑法 × 场地状况匹配调整
    fast_track = track_condition in ("fast", "good_to_firm")
    slow_track = track_condition in ("good", "yielding", "soft")

    if running_style == "front" and fast_track:
        base = min(100, base + 10)
    elif running_style == "closer" and slow_track:
        base = min(100, base + 10)
    elif running_style == "front" and slow_track:
        base = max(0, base - 15)
    elif running_style == "closer" and fast_track:
        base = max(0, base - 15)

    return base


# ==============================================================================
# 冷门判断 & 数据充足度
# ==============================================================================

def is_longshot_alert(final_odds, opening_odds, has_same_condition_top3, class_fit_score):
    """
    判断是否满足冷门关注条件。

    返回 True 表示该马值得作为冷门关注。
    """
    if final_odds <= 15:
        return False
    if not has_same_condition_top3:
        return False
    if opening_odds is not None and opening_odds > 0:
        drift = (final_odds - opening_odds) / opening_odds
        if drift > 0.20:  # 赔率拉长超过20%则排除
            return False
    if class_fit_score < 50:
        return False
    return True


def data_confidence(same_condition_count, has_odds_drift):
    """
    返回数据充足度标注。
    """
    if same_condition_count >= 3 and has_odds_drift:
        return "⭐⭐⭐ 高"
    elif same_condition_count >= 1 or has_odds_drift:
        return "⭐⭐ 中"
    else:
        return "⭐ 低"


# ==============================================================================
# 骑师/练马师评分
# ==============================================================================

def score_jockey(jockey_name: str, horse_history: list) -> int:
    """
    评分：骑师（0-100）。

    逻辑：
    1. 优先从该马历史战绩中统计"本骑师骑乘本马"的胜率/前3率
       → 体现骑师与本马的默契程度（马匹适应性）
    2. 若该骑师骑乘本马次数不足2场，退化为：
       统计历史战绩中所有骑师的整体前3率作对比基准，
       再对当前骑师给出相对评分
    3. 无任何历史数据时返回中性默认值 50

    参数：
        jockey_name   : 当前骑师姓名
        horse_history : 该马历史战绩列表（含 "jockey" / "position" 字段）
    """
    if not jockey_name or not horse_history:
        return 50

    # 当前骑师骑乘本马的历史场次
    own_records = [
        r for r in horse_history
        if r.get("jockey", "").strip() == jockey_name.strip()
    ]

    if len(own_records) >= 2:
        # 足够样本：统计本骑师骑乘本马的胜率/前3率
        wins = sum(1 for r in own_records if r.get("position") == 1)
        top3 = sum(1 for r in own_records if r.get("position", 99) <= 3)
        n = len(own_records)
        win_rate = wins / n
        top3_rate = top3 / n

        if win_rate >= 0.40:
            return 88
        elif win_rate >= 0.20:
            return 75
        elif top3_rate >= 0.50:
            return 65
        elif top3_rate >= 0.30:
            return 55
        elif top3_rate >= 0.10:
            return 42
        else:
            return 28

    # 样本不足：退化为全局骑师前3率对比
    # 统计历史中各骑师的前3率
    jockey_stats: dict = {}
    for r in horse_history:
        j = r.get("jockey", "").strip()
        if not j:
            continue
        if j not in jockey_stats:
            jockey_stats[j] = {"total": 0, "top3": 0}
        jockey_stats[j]["total"] += 1
        if r.get("position", 99) <= 3:
            jockey_stats[j]["top3"] += 1

    if not jockey_stats:
        return 50

    # 全部骑师的平均前3率（基准）
    all_top3_rates = [
        v["top3"] / v["total"]
        for v in jockey_stats.values()
        if v["total"] >= 1
    ]
    avg_rate = sum(all_top3_rates) / len(all_top3_rates) if all_top3_rates else 0.25

    # 当前骑师在本马历史中的前3率（可能只有0-1场）
    cur = jockey_stats.get(jockey_name.strip())
    if cur and cur["total"] >= 1:
        cur_rate = cur["top3"] / cur["total"]
        ratio = cur_rate / avg_rate if avg_rate > 0 else 1.0
        if ratio >= 2.0:
            return 70
        elif ratio >= 1.3:
            return 60
        elif ratio >= 0.7:
            return 50
        else:
            return 38
    else:
        # 首次骑乘本马：给中性偏低分，不惩罚但也不加分
        return 46


def score_trainer(trainer_name: str, horse_history: list) -> int:
    """
    评分：练马师（0-100）。

    逻辑与 score_jockey 类似，但练马师与本马长期绑定，
    换练马师属于重大变化，因此权重略低且中性默认更保守。

    参数：
        trainer_name  : 当前练马师姓名
        horse_history : 该马历史战绩列表（含 "trainer" / "position" 字段）
    """
    if not trainer_name or not horse_history:
        return 50

    own_records = [
        r for r in horse_history
        if r.get("trainer", "").strip() == trainer_name.strip()
    ]

    if len(own_records) >= 3:
        wins = sum(1 for r in own_records if r.get("position") == 1)
        top3 = sum(1 for r in own_records if r.get("position", 99) <= 3)
        n = len(own_records)
        win_rate = wins / n
        top3_rate = top3 / n

        if win_rate >= 0.35:
            return 85
        elif win_rate >= 0.15:
            return 70
        elif top3_rate >= 0.50:
            return 62
        elif top3_rate >= 0.30:
            return 52
        elif top3_rate >= 0.10:
            return 40
        else:
            return 28

    # 样本不足 3 场：
    # 练马师通常稳定，若近期有换马师，给轻度下调
    trainer_set = {r.get("trainer", "").strip() for r in horse_history if r.get("trainer")}
    is_new_trainer = trainer_name.strip() not in trainer_set

    if is_new_trainer:
        return 42  # 新练马师，不确定性高
    else:
        # 老练马师但样本不足（本马出赛次数少）
        top3_count = sum(
            1 for r in own_records if r.get("position", 99) <= 3
        )
        return 55 if top3_count >= 1 else 48


# ==============================================================================
# 贴士指数评分
# ==============================================================================

def score_tips_index(tips_value: int) -> int:
    """
    评分：HKJC 官方贴士指数（0-100）。

    HKJC Tips Index 通常范围 80-120，
    - 100 = 基准值
    - >100 = 偏热（市场看好）
    - <100 = 偏冷（市场看淡）

    参数：
        tips_value : 贴士指数（整数，通常 80-120）
    """
    if tips_value is None or tips_value <= 0:
        return 50  # 无数据时返回中性默认值

    # 贴士指数 100 为基准，映射到 50 分
    # 每偏离 5 个点，评分 ±10 分
    offset = tips_value - 100
    score = 50 + (offset / 5) * 10

    # 限制范围 10-100
    return max(10, min(100, round(score)))


def score_tips_index_hkjc(tips_value: float) -> int:
    """
    评分：HKJC 官方贴士指数（0-100）。

    HKJC 贴士指数是小数值格式，数值越低表示越被看好。
    常见范围：
    - 1-5：极热门
    - 5-15：热门
    - 15-30：中性偏热
    - 30-99：偏冷
    - 99：数据缺失或无贴士

    参数：
        tips_value : 贴士指数值（float）
    """
    if tips_value is None or tips_value <= 0 or tips_value >= 99:
        return 50  # 无数据或99表示无贴士，返回中性默认值

    # 评分逻辑：数值越低评分越高
    if tips_value <= 2.0:
        return 95  # 极热门
    elif tips_value <= 3.0:
        return 88  # 非常热门
    elif tips_value <= 5.0:
        return 78  # 热门
    elif tips_value <= 10.0:
        return 65  # 偏热
    elif tips_value <= 20.0:
        return 55  # 中性
    elif tips_value <= 40.0:
        return 40  # 偏冷
    else:
        return 25  # 冷门


# ==============================================================================
# 综合评分计算
# ==============================================================================

def calculate_total_score(horse_data, weights):
    """
    根据权重和各维度评分计算综合分。

    horse_data 字段说明：
        history_same_condition_score : int (0-100)
        history_same_venue_score     : int (0-100)
        class_fit_score              : int (0-100)
        odds_value_score             : int (0-100)
        odds_drift_score             : int (0-100)
        sectional_score              : int (0-100)
        jockey_score                 : int (0-100)
        trainer_score                : int (0-100)
        barrier_score                : int (0-100)
        tips_index_score             : int (0-100)
        expert_score                 : int (0-100)
    """
    field_map = {
        "history_same_condition": "history_same_condition_score",
        "history_same_venue": "history_same_venue_score",
        "class_fit": "class_fit_score",
        "odds_value": "odds_value_score",
        "odds_drift": "odds_drift_score",
        "sectional": "sectional_score",
        "jockey": "jockey_score",
        "trainer": "trainer_score",
        "barrier": "barrier_score",
        "tips_index": "tips_index_score",
        "expert": "expert_score",
    }

    total = 0.0
    for weight_key, score_field in field_map.items():
        w = weights.get(weight_key, 0)
        s = horse_data.get(score_field, 50)  # 默认 50（中性）
        total += w * s

    return round(total, 2)
