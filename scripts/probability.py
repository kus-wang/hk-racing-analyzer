#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HKJC 赛马分析工具 - 概率计算模块

使用 Softmax 归一化计算各马匹胜出概率。
"""

import math
from config import SOFTMAX_TEMPERATURE, PROB_CAP


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
