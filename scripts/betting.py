#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HKJC 赛马分析工具 - 投注推荐模块 (v1.5.0)

核心职责：
1. 根据概率分布 + 赔率性价比，自动判断每场最优投注玩法
2. 只推荐一种最佳玩法（WIN / PLACE / Q / TRIO）
3. 提供独立冷门建议接口（不进报告，供实时问答使用）
4. 回测时追踪推荐玩法的命中情况
"""

# ──────────────────────────────────────────────────────────────
# 价值指数计算
# ──────────────────────────────────────────────────────────────

def compute_value_index(model_prob: float, win_odds: float | None) -> float | None:
    """
    计算价值指数：模型概率 vs 市场隐含概率的比值。

    逻辑：
      隐含胜率 = 1 / 赔率 × 0.92（扣除 HKJC 约 8% 抽水）
      value_index = model_prob% / (隐含胜率 × 100)
      > 1.2 → 🔥 超值
      0.8~1.2 → 普通
      < 0.8 → ⚠️ 市场高估

    参数：
        model_prob : 模型胜出概率（百分比，如 35.2）
        win_odds   : 独赢赔率（float），None 则返回 None

    返回：
        value_index（float）或 None
    """
    if not win_odds or win_odds <= 0 or model_prob <= 0:
        return None

    implied_prob = (1.0 / win_odds) * 0.92 * 100  # 转为百分比
    if implied_prob <= 0:
        return None

    return round(model_prob / implied_prob, 2)


# ──────────────────────────────────────────────────────────────
# 场型判断 + 最优玩法推荐
# ──────────────────────────────────────────────────────────────

# 玩法常量
BET_WIN       = "WIN"
BET_PLACE     = "PLACE"
BET_DUO_PLACE = "DUO_PLACE"  # v1.6.5: 双马位置（场型A/B推荐，比Q宽松）
BET_Q         = "Q"
BET_TRIO      = "TRIO"

# 玩法中文名
BET_NAMES = {
    BET_WIN:       "独赢",
    BET_PLACE:     "位置",
    BET_DUO_PLACE: "双马位置",
    BET_Q:         "连赢",
    BET_TRIO:      "三重彩",
}

# 场型中文名
SCENE_NAMES = {
    "A": "高置信独赢场",
    "B": "双强对决场",
    "C": "标准三强场",
    "D": "开放冷门场",
}


def determine_bet_type(sorted_horses: list) -> dict:
    """
    根据概率分布形态 + 赔率性价比，判断每场最推荐的一种投注玩法。

    参数：
        sorted_horses : 已按 probability（或 total_score）降序排列的马列表。
                        每匹马需含字段：
                          - no / horse_no : 马号
                          - name : 马名
                          - probability : 模型概率（百分比）
                          - final_odds : 独赢赔率（可选）

    返回：
        {
            "bet_type":     "WIN" | "PLACE" | "DUO_PLACE" | "Q" | "TRIO",
            "bet_name":     "独赢" | "位置" | "双马位置" | "连赢" | "三重彩",
            "selections":   [马号列表]，推荐选马
            "selection_names": [马名列表]，
            "scene":        "A" | "B" | "C" | "D"，
            "scene_name":   场型中文名,
            "prob_coverage": 前N马概率和（百分比）,
            "value_index":  首选马的价值指数（可能为 None）,
            "reason":       一句话推荐理由,
        }

    场型判断优先级：
        A：高置信独赢场 — top1 概率 ≥ 28% 且价值指数 ≥ 1.05 且赔率 ≤ 6
        B：双强对决场 — top1+top2 概率和 ≥ 55% 且 概率差 < 15%
        C：标准三强场 — top3 概率和 ≥ 60%（默认最常见）
        D：开放冷门场 — 以上都不满足

    推荐策略（v1.6.5：位置优先，命中率第一）：
        D → PLACE 首选第1马（命中率最高）
        C → PLACE 首选第1马（放弃 Q，改用更稳的位置）
        B → DUO_PLACE（第1+第2马都在前3即中，比 Q 宽松）
        A → WIN 仅超级强势马（概率≥40%且领先≥20%且赔率2-4）
        A → DUO_PLACE 其他高置信场景
        Q → 仅在极罕见极高置信场保留（前两名概率和 ≥ 88% 且概率差 < 5%）

    降级规则：
        WIN → 若赔率 < 2.0（期望值过低），降级为 PLACE
        DUO_PLACE → 若首选马赔率 > 8，降级为 PLACE
    """
    if not sorted_horses or len(sorted_horses) < 3:
        return _default_bet(sorted_horses)

    top1 = sorted_horses[0]
    top2 = sorted_horses[1]
    top3 = sorted_horses[2]

    p1 = top1.get("probability", 0)
    p2 = top2.get("probability", 0)
    p3 = top3.get("probability", 0)

    odds1 = _get_odds(top1)
    odds2 = _get_odds(top2)

    vi1 = compute_value_index(p1, odds1)
    vi2 = compute_value_index(p2, odds2)

    top2_sum = p1 + p2
    top3_sum = p1 + p2 + p3

    no1 = _get_no(top1)
    no2 = _get_no(top2)
    no3 = _get_no(top3)

    # ── 场型 A：高置信独赢场 ──
    if p1 >= 28 and odds1 and odds1 <= 6.0:
        vi_val = vi1 if vi1 else 1.0
        prob_gap = p1 - p2
        # 超级强势单马 → WIN（极高置信+显著领先+合理赔率）
        if p1 >= 40 and prob_gap >= 20 and 2.0 <= odds1 <= 4.0:
            return _make_bet(
                BET_WIN, [no1], [_get_name(top1)], "A", p1,
                vi1, f"#{no1} 超级强势（{p1:.1f}%），领先 #{no2} {prob_gap:.1f}%，赔率 {odds1}，独赢"
            )
        # 其他高置信场景 → DUO_PLACE（仅在赔率适中时推荐）
        if odds1 <= 8:
            return _make_bet(
                BET_DUO_PLACE, [no1, no2], [_get_name(top1), _get_name(top2)], "A", top2_sum,
                vi1, f"#{no1}+{no2} 双强格局（{p1:.1f}% + {p2:.1f}%），双马位置更稳"
            )
        # 赔率偏高，降级为位置
        return _make_bet(
            BET_PLACE, [no1], [_get_name(top1)], "A", p1,
            vi1, f"#{no1} 概率 {p1:.1f}% 但赔率 {odds1} 偏高，位置更稳"
        )

    # ── 场型 B：双强对决场 → DUO_PLACE（放弃 Q）──
    if top2_sum >= 55 and abs(p1 - p2) < 15:
        # 两匹马赔率都不高时，推 DUO_PLACE
        if not odds1 or not odds2 or odds1 <= 10:
            return _make_bet(
                BET_DUO_PLACE, [no1, no2], [_get_name(top1), _get_name(top2)], "B", top2_sum,
                vi1, f"#{no1}({p1:.1f}%)+#{no2}({p2:.1f}%) 双强对决，双马位置更稳"
            )
        # 赔率偏高，降级为位置
        return _make_bet(
            BET_PLACE, [no1], [_get_name(top1)], "B", p1,
            vi1, f"#{no1} 概率 {p1:.1f}%，赔率 {odds1} 偏高，位置保守"
        )

    # ── 场型 C：标准三强场 → 位置（放弃 Q）──
    if top3_sum >= 60:
        # 首选第1马做位置，命中率最高
        return _make_bet(
            BET_PLACE, [no1], [_get_name(top1)], "C", top3_sum,
            vi1, f"#{no1} 概率 {p1:.1f}%，首选位置稳健"
        )

    # ── 场型 D：开放冷门场 → 位置（默认）──
    return _make_bet(
        BET_PLACE, [no1],
        [_get_name(top1)],
        "D", top3_sum, vi1,
        f"格局开放（前三概率和仅 {top3_sum:.1f}%），位置保守避险"
    )


# ──────────────────────────────────────────────────────────────
# 冷门建议接口（独立，不进报告）
# ──────────────────────────────────────────────────────────────

def get_longshot_tip(sorted_horses: list) -> dict | None:
    """
    返回本场最有冷门潜力的马（独立接口，供实时问答使用）。

    条件：
      - 赔率 > 8
      - value_index > 1.3（模型认为市场低估）
      - 有 longshot_alert 标记优先

    参数：
        sorted_horses : 已排序的马列表

    返回：
        {"no": 马号, "name": 马名, "odds": 赔率, "value_index": 价值指数}
        或 None（无冷门推荐）
    """
    if not sorted_horses:
        return None

    candidates = []
    for h in sorted_horses:
        odds = _get_odds(h)
        if not odds or odds <= 8:
            continue

        prob = h.get("probability", 0)
        vi = compute_value_index(prob, odds)
        if vi is None or vi <= 1.3:
            continue

        # v1.4.13: win_place_ratio_score < 38（独赢/位置比值高 > 4.0），
        # 说明市场认为"能进前3但难赢"，这类马独赢更有价值
        wpr_score = h.get("win_place_ratio_score", 50)
        if wpr_score < 38:  # 低于38说明比值高，不是真正冷门
            continue

        # longshot_alert 的马优先
        priority = 1 if h.get("longshot_alert") else 0
        candidates.append({
            "no": _get_no(h),
            "name": _get_name(h),
            "odds": odds,
            "value_index": vi,
            "probability": prob,
            "priority": priority,
        })

    if not candidates:
        return None

    # 优先 longshot_alert，其次按价值指数降序
    candidates.sort(key=lambda x: (x["priority"], x["value_index"]), reverse=True)
    return candidates[0]


# ──────────────────────────────────────────────────────────────
# 回测命中验证
# ──────────────────────────────────────────────────────────────

def check_bet_hit(bet_rec: dict, actual_top: list) -> dict:
    """
    验证推荐投注是否命中。

    参数：
        bet_rec    : determine_bet_type() 的返回值
        actual_top : 实际结果列表 [{"no": "3", "name": "...", "pos": 1}, ...]

    返回：
        {
            "bet_type":    玩法,
            "selections":  推荐马号列表,
            "actual_top3": 实际前3马号列表,
            "hit":         bool 是否命中,
            "hit_detail":  str 命中说明,
        }

    命中规则：
        WIN   : 推荐[no1] == 实际第1
        PLACE : 推荐[no1] in 实际前3
        Q     : set(推荐[no1,no2]) ⊆ set(实际前2) — 连赢规则：必须是第1+第2名（顺序不限）
        TRIO  : set(推荐[no1,no2,no3]) == set(实际前3) — 顺序不限
    """
    if not bet_rec or not actual_top:
        return {"bet_type": None, "hit": False, "hit_detail": "数据缺失"}

    bet_type   = bet_rec.get("bet_type")
    selections = [str(s) for s in bet_rec.get("selections", [])]
    actual_nos = [str(h["no"]) for h in actual_top[:4]]  # 取前4（Q需前2，PLACE需前3）
    actual_top3 = set(actual_nos[:3])
    winner = actual_nos[0] if actual_nos else None

    if bet_type == BET_WIN:
        hit = len(selections) > 0 and selections[0] == winner
        return {
            "bet_type": bet_type,
            "selections": selections,
            "actual_top3": list(actual_top3),
            "hit": hit,
            "hit_detail": f"独赢 #{selections[0]} {'命中' if hit else f'未中（冠军 #{winner}）'}",
        }

    elif bet_type == BET_PLACE:
        hit = len(selections) > 0 and selections[0] in actual_top3
        return {
            "bet_type": bet_type,
            "selections": selections,
            "actual_top3": list(actual_top3),
            "hit": hit,
            "hit_detail": f"位置 #{selections[0]} {'命中' if hit else f'未中（前3: {list(actual_top3)}）'}",
        }

    elif bet_type == BET_DUO_PLACE:
        # v1.6.3: 双马位置 — 推荐的两匹马都在实际前3名即命中
        sel_set = set(selections)
        hit = sel_set.issubset(actual_top3) and len(sel_set) == 2
        return {
            "bet_type": bet_type,
            "selections": selections,
            "actual_top3": list(actual_top3),
            "hit": hit,
            "hit_detail": (
                f"双马位置 {selections} {'命中' if hit else '未中'}"
                f"（实际前3: {list(actual_top3)}）"
            ),
        }

    elif bet_type == BET_Q:
        sel_set = set(selections)
        # 连赢规则：推荐的两匹马必须是实际第1名+第2名（顺序不限）
        actual_top2 = set(actual_nos[:2])
        hit = sel_set.issubset(actual_top2) and len(sel_set) == 2
        return {
            "bet_type": bet_type,
            "selections": selections,
            "actual_top3": list(actual_top3),
            "hit": hit,
            "hit_detail": (
                f"连赢 {selections} {'命中' if hit else '未中'}"
                f"（实际前2: {list(actual_nos[:2])}）"
            ),
        }

    elif bet_type == BET_TRIO:
        sel_set = set(selections)
        hit = sel_set == actual_top3 and len(sel_set) == 3
        return {
            "bet_type": bet_type,
            "selections": selections,
            "actual_top3": list(actual_top3),
            "hit": hit,
            "hit_detail": (
                f"三重彩 {selections} {'命中' if hit else '未中'}"
                f"（实际前3: {list(actual_top3)}）"
            ),
        }

    return {"bet_type": bet_type, "selections": selections, "hit": False, "hit_detail": "未知玩法"}


# ──────────────────────────────────────────────────────────────
# 报告输出辅助
# ──────────────────────────────────────────────────────────────

def format_bet_recommendation_line(bet_rec: dict) -> str:
    """
    将投注推荐格式化为一行报告文本。

    示例输出：
        💰 推荐投注：[TRIO] 三重彩 #3 #7 #11 | 概率覆盖 71.2% | 场型：标准三强场
        💰 推荐投注：[WIN] 独赢 #3 大将军 | 价值指数 🔥1.31 | 场型：高置信独赢场
    """
    if not bet_rec:
        return ""

    bet_type   = bet_rec.get("bet_type", "")
    bet_name   = bet_rec.get("bet_name", "")
    selections = bet_rec.get("selections", [])
    names      = bet_rec.get("selection_names", [])
    coverage   = bet_rec.get("prob_coverage", 0)
    scene_name = bet_rec.get("scene_name", "")
    vi         = bet_rec.get("value_index")

    # 构建选马文本
    sel_text = " ".join(f"#{s}" for s in selections)
    name_text = " ".join(names) if names else ""
    if name_text:
        sel_text = f"{sel_text} {name_text}"

    # 价值指数标签
    vi_text = ""
    if vi is not None:
        if vi >= 1.2:
            vi_text = f" | 价值指数 🔥{vi}"
        elif vi >= 0.8:
            vi_text = f" | 价值指数 {vi}"
        else:
            vi_text = f" | 价值指数 ⚠️{vi}"

    return (
        f"💰 推荐投注：[{bet_type}] {bet_name} {sel_text}"
        f" | 概率覆盖 {coverage:.1f}% | 场型：{scene_name}{vi_text}"
    )


# ──────────────────────────────────────────────────────────────
# 内部辅助函数
# ──────────────────────────────────────────────────────────────

def _get_no(horse: dict) -> str:
    return str(horse.get("no") or horse.get("horse_no") or "")


def _get_name(horse: dict) -> str:
    return horse.get("name", "")


def _get_odds(horse: dict) -> float | None:
    odds = horse.get("final_odds")
    if odds is not None and odds > 0:
        return float(odds)
    return None


def _make_bet(bet_type, selections, selection_names, scene, coverage, vi, reason):
    return {
        "bet_type":         bet_type,
        "bet_name":         BET_NAMES.get(bet_type, bet_type),
        "selections":       selections,
        "selection_names":  selection_names,
        "scene":            scene,
        "scene_name":       SCENE_NAMES.get(scene, "未知"),
        "prob_coverage":    round(coverage, 1),
        "value_index":      vi,
        "reason":           reason,
    }


def _default_bet(sorted_horses):
    if sorted_horses:
        h = sorted_horses[0]
        return _make_bet(
            BET_PLACE, [_get_no(h)], [_get_name(h)],
            "D", 0, None, "数据不足，保守推荐位置"
        )
    return _make_bet(BET_PLACE, [], [], "D", 0, None, "无马匹数据")
