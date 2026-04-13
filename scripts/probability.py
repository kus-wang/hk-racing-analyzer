#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HKJC 赛马分析工具 - 概率计算模块

使用 Softmax 归一化计算各马匹胜出概率。
"""

import math
from config import SOFTMAX_TEMPERATURE, PROB_CAP


def dynamic_temperature(win_odds_map: dict) -> float:
    """
    v1.4.12 新增：根据场内赔率离散度动态调整 Softmax 温度参数。

    逻辑：
    - 场内赔率"越悬殊"（最热门与最冷门差异大），说明市场对热门马过度追捧，
      此时应提高 T（更均摊），避免热门马独吞全部概率。
    - 赔率分布"越均匀"（各马差不多），市场无明显倾向，
      此时降低 T（稍微聚焦），让模型能给出明确判断。

    赔率离散度 = 全场最高赔率 / 全场最低赔率（剔除 None/0）

    档位：
        ratio > 20  → T = 6.5（悬殊场：超级大热门 vs 极大冷门）
        ratio > 10  → T = 5.5（大差异场：明显热门）
        ratio > 5   → T = 5.0（正常场：默认值）
        ratio <= 5  → T = 4.5（均衡场：各马赔率相近，市场无明显共识）

    v1.6.4 调整：整体 +0.5（进化建议1），改善高分马高估问题（2026-04-12 沙田回测：18匹马预测前3但未入前3）。

    无赔率数据时返回默认值 SOFTMAX_TEMPERATURE（config.py中配置）。

    参数：
        win_odds_map : 独赢赔率字典 {"#1": 1.8, "#2": 21.0, ...}
    """
    if not win_odds_map:
        return SOFTMAX_TEMPERATURE

    valid_odds = [v for v in win_odds_map.values() if v and v > 0]
    if len(valid_odds) < 2:
        return SOFTMAX_TEMPERATURE

    min_odds = min(valid_odds)
    max_odds = max(valid_odds)

    if min_odds <= 0:
        return SOFTMAX_TEMPERATURE

    ratio = max_odds / min_odds

    if ratio > 20:
        return 6.5
    elif ratio > 10:
        return 5.5
    elif ratio > 5:
        return 5.0
    else:
        return 4.5


def softmax_probability(scores, temperature=SOFTMAX_TEMPERATURE, cap=PROB_CAP):
    """
    使用 Softmax 归一化计算各马匹胜出概率。

    参数：
        scores      : 各马匹综合评分列表（float）
        temperature : 温度参数，越大概率越均摊（建议 1.2-2.0）
        cap         : 单匹马概率上限（默认 0.50）

    返回：
        各马匹胜出概率列表（百分比，合计 100%）
    """
    if not scores:
        return []

    # Softmax
    max_score = max(scores)  # 数值稳定性处理
    exp_scores = [math.exp((s - max_score) / temperature) for s in scores]
    total_exp = sum(exp_scores)
    probs = [e / total_exp for e in exp_scores]

    # 上限约束
    probs = [min(p, cap) for p in probs]

    # 重新归一化
    total_prob = sum(probs)
    if total_prob > 0:
        probs = [p / total_prob for p in probs]

    return [round(p * 100, 1) for p in probs]

