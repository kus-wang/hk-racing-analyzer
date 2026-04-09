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

from datetime import date as _date, datetime as _dt


def _time_weight(race_date_str: str) -> float:
    """
    计算历史战绩时间衰减系数（建议5，2026-04-02 引入）。

    近30天  × 1.0
    31-90天 × 0.8
    91-180天× 0.6
    >180天  × 0.4

    race_date_str 支持格式：
      "YYYY/MM/DD", "YYYY-MM-DD", "DD/MM/YYYY", 或整数/None（无法解析时返回 0.7）
    """
    if not race_date_str:
        return 0.7
    try:
        s = str(race_date_str).strip()
        # 尝试 YYYY/MM/DD 或 YYYY-MM-DD
        for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                d = _dt.strptime(s, fmt).date()
                break
            except ValueError:
                continue
        else:
            return 0.7  # 无法解析
        days = (_date.today() - d).days
        if days <= 30:
            return 1.0
        elif days <= 90:
            return 0.8
        elif days <= 180:
            return 0.6
        else:
            return 0.4
    except Exception:
        return 0.7


# ==============================================================================
# 历史战绩评分
# ==============================================================================

def score_history_same_condition(results, venue, distance, tolerance=200):
    """
    评分：同距离+同场地近5场战绩（0-100）。

    results : 历史出赛列表，每项为 {"venue": "ST", "distance": 1400, "position": 1,
                                     "date": "YYYY/MM/DD"}（date 可选）
    venue   : 本场场地 "ST" / "HV"
    distance: 本场距离（米）

    建议5（2026-04-02）：引入时间衰减加权，近期成绩权重更高。
    """
    same = [
        r for r in results
        if r.get("venue") == venue
        and abs(r.get("distance", 0) - distance) <= tolerance
    ]
    same = same[-5:]  # 取最近5场

    if not same:
        return 40  # 中性默认，无同条件记录不惩罚

    # 时间衰减加权：计算等效胜场数和前3场数
    weighted_wins = 0.0
    weighted_top3 = 0.0
    total_weight = 0.0

    for r in same:
        tw = _time_weight(r.get("date") or r.get("race_date"))
        pos = r.get("position", 99)
        weighted_wins += (1 if pos == 1 else 0) * tw
        weighted_top3 += (1 if pos <= 3 else 0) * tw
        total_weight += tw

    if total_weight <= 0:
        return 40

    # 规一化到 n=len(same) 的等效值，保持原评分尺度
    n = len(same)
    norm = total_weight / n  # 平均时间权重（约 0.4-1.0）
    wins = weighted_wins / norm
    top3 = weighted_top3 / norm

    # 近3场原始名次（无衰减，用于"近期有冠"判断）
    positions_raw = [r.get("position", 99) for r in same]

    if wins >= 2:
        return 75 + min(15, int(wins) * 5)
    if wins >= 1:
        base = 55
        if any(p == 1 for p in positions_raw[-3:]):
            base += 3   # v1.4.12: 近3场有冠军加成 10→3，避免"单胜马"被过度拉高至65分
        return base
    if top3 >= 2:
        return 42
    if top3 >= 1:
        return 33
    return 15


def score_history_same_venue(results, venue):
    """
    评分：同场地不限距离近5场战绩（0-100）。

    建议5（2026-04-02）：引入时间衰减加权。
    """
    same = [r for r in results if r.get("venue") == venue]
    same = same[-5:]

    if not same:
        return 40

    weighted_wins = 0.0
    weighted_top3 = 0.0
    total_weight = 0.0

    for r in same:
        tw = _time_weight(r.get("date") or r.get("race_date"))
        pos = r.get("position", 99)
        weighted_wins += (1 if pos == 1 else 0) * tw
        weighted_top3 += (1 if pos <= 3 else 0) * tw
        total_weight += tw

    if total_weight <= 0:
        return 40

    n = len(same)
    norm = total_weight / n
    wins = weighted_wins / norm
    top3 = weighted_top3 / norm

    if wins >= 2:
        return 72
    if wins >= 1:
        return 55
    if top3 >= 2:
        return 40
    if top3 >= 1:
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

def score_odds_value(win_odds, place_odds=None):
    """
    评分：临场赔率综合评分（0-100）。

    v1.4.11 重大增强：

    - 独赢赔率：主要信号，细分更多档位（15档 → 20档）
    - 位置赔率：辅助信号，若独赢 > 8 且位置赔率偏低（<3.5），说明市场认为它进前3稳定
    - 隐含胜率标准化：跨场次比较时使用隐含胜率而非绝对赔率值

    参数：
        win_odds  : 独赢赔率（float）
        place_odds: 位置赔率（float，可选）
    """
    if not win_odds or win_odds <= 0:
        return 50  # 无数据返回中性默认值

    base = 50

    # ── 独赢赔率分档（20档精细评分）───────────────────────────────
    if win_odds < 1.5:
        base = 98  # 超级大热门
    elif win_odds < 2.0:
        base = 93  # 极大热门
    elif win_odds < 2.5:
        base = 88  # 大热门
    elif win_odds < 3.0:
        base = 82  # 热门
    elif win_odds < 3.5:
        base = 77  # 偏热
    elif win_odds < 4.0:
        base = 72  # 轻微热门
    elif win_odds < 5.0:
        base = 66  # 中上
    elif win_odds < 6.0:
        base = 60  # 中游偏热
    elif win_odds < 7.0:
        base = 55  # 中游
    elif win_odds < 8.5:
        base = 50  # 中游偏冷
    elif win_odds < 10.0:
        base = 45  # 轻微冷门
    elif win_odds < 12.0:
        base = 39  # 冷门
    elif win_odds < 15.0:
        base = 33  # 偏大冷
    elif win_odds < 20.0:
        base = 26  # 大冷门
    elif win_odds < 30.0:
        base = 18  # 极大冷
    elif win_odds < 50.0:
        base = 10  # 超级冷
    else:
        base = 5   # 超远冷

    # ── 位置赔率加成（辅助信号）──────────────────────────────────
    # 逻辑：若某马独赢不低（>8）但位置赔率低（<3.5），
    # 说明市场认为它进前三稳定，可信度高，给 +5 分
    if place_odds and place_odds > 0 and win_odds > 8.0:
        # 隐含位置胜率 ≈ 1/(place_odds*3)，简化判断：place_odds < 3.5 → 市场看好位置
        if place_odds < 3.0:
            base += 7   # 位置强烈看好
        elif place_odds < 3.5:
            base += 4   # 位置看好

    return min(100, max(0, base))


def score_implied_probability(win_odds, all_win_odds: dict = None) -> int:
    """
    评分：将赔率转换为隐含胜率（0-100）。

    v1.4.11 新增，v1.4.11 修复 bug。


    逻辑：
    - 隐含胜率 = 1 / 赔率 × 0.92（扣除 HKJC 约 8% 抽水）
    - 直接将隐含胜率映射为 0-100 分（1.8 odds → 约 51 分）
    - 不做全场 max 标准化（否则全场最佳马得 100 分，gap 过大 → Softmax 概率失真）

    参数：
        win_odds    : 本马独赢赔率（float）
        all_win_odds: 全场独赢赔率字典（当前版本未使用，保留参数兼容）
    """
    if not win_odds or win_odds <= 0:
        return 50

    # 隐含胜率 = 1/赔率，修正 HKJC 约 8% 抽水
    implied = (1.0 / float(win_odds)) * 0.92

    # 映射到 0-100 分（50 = 中性，隐含胜率 50% → 评分 46）
    score = round(implied * 92, 0)  # 隐含胜率 51% → 评分 47
    return min(100, max(0, int(score)))


def score_odds_drift(opening_odds, final_odds):
    """
    评分：赔率走势变化幅度（0-100）。

    v1.4.11 增强：若无开盘赔率但有全场赔率数据，

    使用"赔率场内排名变化"作为替代信号。

    opening_odds 为 None 时返回中性默认值 50。
    """
    if opening_odds is None or opening_odds <= 0:
        return 50  # 无开盘赔率数据，使用中性默认

    change_ratio = (opening_odds - final_odds) / opening_odds  # 正数=缩水，负数=拉长

    if change_ratio > 0.50:
        return 92  # 强烈资金涌入
    elif change_ratio > 0.30:
        return 80  # 明显资金涌入
    elif change_ratio > 0.20:
        return 70  # 轻微看好
    elif change_ratio >= -0.20:
        return 50  # 市场平稳
    elif change_ratio >= -0.35:
        return 32  # 轻微看淡
    elif change_ratio >= -0.50:
        return 20  # 明显资金流出
    else:
        return 8   # 强烈看淡


# ==============================================================================
# 冷门信号：独赢/位置赔率比值（v1.4.13 新增）
# ==============================================================================

def score_win_place_ratio(win_odds, place_odds):
    """
    评分：独赢赔率与位置赔率的比值（0-100）。

    v1.4.13 新增。

    逻辑：
    - ratio = win_odds / place_odds（理论值：独赢=位置赔率的1/3，因为3匹马都能赢位置）
    - LOW ratio (< 2.5)：市场将独赢和位置定价接近 → 强烈看好赢 → 高分
    - MEDIUM ratio (2.5-4.0)：正常市场定价 → 中性
    - HIGH ratio (> 4.0)：市场认为"能进前3但赢不了" → 低分（是位置热门但独赢冷）

    这个比值独立于 odds_value 评分——即使某马独赢10倍（odds_value 低），
    若 ratio 也高达6倍，说明市场强烈认为它进不了前3，是真正的弱马。

    参数：
        win_odds  : 独赢赔率（float）
        place_odds: 位置赔率（float）
    """
    if not win_odds or not place_odds or win_odds <= 0 or place_odds <= 0:
        return 50  # 数据不足，返回中性

    ratio = win_odds / place_odds

    if ratio < 2.0:
        return 78  # 独赢≈位置，市场极度看好赢
    elif ratio < 2.5:
        return 68  # 略低，强烈看好赢
    elif ratio <= 4.0:
        return 50  # 正常市场定价
    elif ratio <= 5.5:
        return 38  # 偏高，市场认为"能位置但难赢"
    else:
        return 25  # 极高，市场认为几乎不可能赢


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

def score_weight_bonus(weight: float, venue: str = "ST", distance: int = 1400) -> int:
    """
    评分：轻磅马加分 (v1.6.3 新增)

    负磅越低，马匹负重越轻，尤其在跑马地短途赛和转弯多的赛道有利。
    借鉴对方 skill 思路：负磅 < 120磅给予加分。

    参数：
        weight   : 负磅（磅）
        venue    : 本场场地 "ST" / "HV"
        distance : 本场距离（米）

    返回：
        int: 加分值 (-5 ~ +11)
    """
    if not weight or weight <= 0:
        return 0

    base_bonus = 0
    venue_bonus = 0

    # 基础负磅评分
    if weight < 115:
        base_bonus = 8   # 超轻磅，显著优势
    elif weight < 120:
        base_bonus = 5   # 轻磅，明显优势
    elif weight < 125:
        base_bonus = 3   # 轻微轻磅
    elif weight > 135:
        base_bonus = -5  # 重磅负担
    elif weight > 130:
        base_bonus = -2  # 轻微重磅

    # 跑马地短途赛额外加成（HV转弯多，轻磅更有优势）
    if venue == "HV" and distance <= 1200:
        venue_bonus = 3
    elif venue == "HV" and distance <= 1650:
        venue_bonus = 1

    return base_bonus + venue_bonus


def score_tj_combo_bonus(jockey_name: str, trainer_name: str, top_combos: list = None) -> int:
    """
    评分：顶级练马师+骑师组合加分 (v1.6.3 新增)

    借鉴对方 skill 思路：顶级TJ组合有更好的协同效应。

    参数：
        jockey_name  : 骑师姓名
        trainer_name : 练马师姓名
        top_combos   : 顶级TJ组合列表，每项为 (jockey_prefix, trainer_prefix, bonus)

    返回：
        int: 加分值 (0 ~ +10)
    """
    if not jockey_name or not trainer_name:
        return 0

    if not top_combos:
        # 默认顶级组合（可根据需要扩展）
        top_combos = [
            # (jockey_prefix, trainer_prefix, bonus)
            ("Z Purton", "J Size", 10),
            ("Z Purton", "C Fownes", 8),
            ("K H Yeung", "P F Yiu", 7),
            ("V R Richards", "J Size", 9),
            ("H T Mo", "K W Lui", 7),
            ("C L Chau", "K W Lui", 6),
            ("A Badenoch", "C S Shum", 6),
            ("J J M Cavieres", "D J Whyte", 6),
            ("M Chadwick", "A S Cruz", 6),
        ]

    jockey_lower = jockey_name.lower().strip()
    trainer_lower = trainer_name.lower().strip()

    for j_prefix, t_prefix, bonus in top_combos:
        if jockey_lower.startswith(j_prefix.lower()) and trainer_lower.startswith(t_prefix.lower()):
            return bonus

    return 0


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

def calculate_total_score(horse_data, weights, top_combos: list = None):
    """
    根据权重和各维度评分计算综合分。

    v1.4.11 增强：赔率综合评分 = odds_value_score × 0.4 + implied_prob_score × 0.6

    - odds_value_score：独赢绝对值分档 + 位置赔率加成
    - implied_prob_score：全场标准化隐含胜率（市场共识归一化）
    两者融合得到"赔率市场共识评分"，作为 odds_value 权重的主信号。

    v1.6.3 新增：轻磅马加分 + 顶级TJ组合加分
    - weight_bonus：负磅 < 120磅时加分，跑马地短途额外加成
    - tj_combo_bonus：顶级骑练组合加分（默认白名单）

    horse_data 字段说明：
        history_same_condition_score : int (0-100)
        history_same_venue_score     : int (0-100)
        class_fit_score              : int (0-100)
        odds_value_score             : int (0-100)
        implied_prob_score           : int (0-100)  # v1.4.11 新增
        odds_drift_score             : int (0-100)
        sectional_score              : int (0-100)
        jockey_score                 : int (0-100)
        trainer_score                : int (0-100)
        barrier_score                : int (0-100)
        tips_index_score             : int (0-100)
        expert_score                 : int (0-100)
        weight                       : float (磅)  # v1.6.3 新增
        venue                        : str        # v1.6.3 新增
        distance                     : int        # v1.6.3 新增
        jockey_name                 : str        # v1.6.3 新增
        trainer_name                : str        # v1.6.3 新增
    """
    # ── v1.4.11 赔率综合评分融合逻辑 ──────────────────────────────
    # odds_value_score    : 独赢赔率绝对值分档(20档) + 位置赔率加成
    # implied_prob_score  : 隐含胜率映射（1.8 odds → 评分47，13 odds → 7）
    # 融合公式：odds_market = odds_abs × 0.4 + odds_implied × 0.6
    # → 1.8 odds → 75分，13 odds → 20分（score gap ≈ 55 分）
    # cap 机制：odds_market 超过 cap 时按比例压缩，防止 gap 过大使 Softmax 失真
    # cap=0.50 → effective odds weight ≈ 22% × 0.50 = 11%（从 22% 有效压缩）
    # 说明：cap 值越大，有效赔率权重越高，但概率也会更集中于热门马。
    odds_abs     = horse_data.get("odds_value_score", 50)
    odds_implied = horse_data.get("implied_prob_score", odds_abs)
    odds_blended = round(odds_abs * 0.4 + odds_implied * 0.6, 2)

    # cap 压缩：限制 odds_blended 最高为基线的 (1/cap_ratio) 倍
    cap_ratio = 0.50  # 0.40=极保守，0.50=适中，0.70=赔率主导
    baseline = 50.0   # 中性分数
    if odds_blended > baseline:
        max_allowed = baseline + (odds_blended - baseline) * cap_ratio
        odds_blended = min(odds_blended, max_allowed)

    horse_data["odds_market_score"] = round(odds_blended, 1)

    # ── v1.6.3 新增：轻磅马加分 + 顶级TJ组合加分 ──────────────────────────
    # 轻磅加分：负磅越低越有利，尤其HV短途
    weight = horse_data.get("weight")
    venue = horse_data.get("venue", "ST")
    distance = horse_data.get("distance", 1400)
    weight_bonus = score_weight_bonus(weight, venue, distance)
    horse_data["weight_bonus_score"] = weight_bonus

    # 顶级TJ组合加分
    jockey_name = horse_data.get("jockey_name", "")
    trainer_name = horse_data.get("trainer_name", "")
    tj_bonus = score_tj_combo_bonus(jockey_name, trainer_name, top_combos)
    horse_data["tj_combo_bonus_score"] = tj_bonus

    # ── v1.6.2 新增：动态权重转移 —— odds_drift 变化 < 5% 时转移权重至 odds_value ──
    # 获取原始赔率数据计算变化率
    opening = horse_data.get("opening_odds")
    final = horse_data.get("final_odds")
    adjusted_weights = dict(weights)  # 复制一份可修改的权重

    if opening and final and opening > 0:
        drift_ratio = abs(opening - final) / opening  # 绝对变化率
        if drift_ratio < 0.05:  # 变化 < 5%
            drift_weight = weights.get("odds_drift", 0)
            if drift_weight > 0:
                # 将 odds_drift 权重转移到 odds_value（避免无效权重浪费）
                adjusted_weights["odds_drift"] = 0
                adjusted_weights["odds_value"] = adjusted_weights.get("odds_value", 0) + drift_weight
                # 标记说明
                horse_data["_weight_transfer_reason"] = (
                    f"odds_drift 变化率 {drift_ratio:.1%} < 5%，权重 {drift_weight}% 转移至 odds_value"
                )

    field_map = {
        "history_same_condition": "history_same_condition_score",
        "history_same_venue": "history_same_venue_score",
        "class_fit": "class_fit_score",
        "odds_value": "odds_market_score",   # v1.4.11: 使用融合后的赔率综合评分
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
        w = adjusted_weights.get(weight_key, 0)  # v1.6.2: 使用调整后的权重
        s = horse_data.get(score_field, 50)  # 默认 50（中性）
        total += w * s

    # ── v1.6.3 新增：加分项直接加入总分 ──────────────────────────────────
    # weight_bonus: 轻磅加分 (-5 ~ +11)
    # tj_combo_bonus: 顶级TJ组合加分 (0 ~ +10)
    total += horse_data.get("weight_bonus_score", 0)
    total += horse_data.get("tj_combo_bonus_score", 0)

    return round(total, 2)
