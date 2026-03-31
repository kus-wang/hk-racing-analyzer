#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HKJC 赛马分析工具 - 权重计算模块

根据场地、距离、赛道类型和赛事场景返回适配的权重配置。
"""

from config import DEFAULT_WEIGHTS


def get_weights(venue="ST", distance=1400, track_type="turf", race_scenario="normal"):
    """
    根据场地、距离、赛道类型和赛事场景返回适合的权重字典。

    race_scenario 可选值：
        "normal"     - 普通场次（默认）
        "newcomer"   - 初出马（无历史战绩）
        "class_down" - 降班马
        "class_up"   - 升班马
    """
    weights = dict(DEFAULT_WEIGHTS)

    # ── 场景调整 ────────────────────────────────
    if race_scenario == "newcomer":
        weights["history_same_condition"] = 0.00
        weights["history_same_venue"] = 0.00
        weights["class_fit"] = 0.15
        weights["tips_index"] = 0.08  # 新马更依赖官方贴士
        weights["expert"] = 0.00
        weights["jockey"] = 0.15
        weights["trainer"] = 0.13
        # sectional / odds 保持默认

    elif race_scenario == "class_down":
        weights["class_fit"] = 0.15
        weights["odds_drift"] = 0.18
        weights["tips_index"] = 0.04  # 降班马降低官方贴士权重
        weights["expert"] = 0.00
        weights["history_same_condition"] = 0.10
        weights["history_same_venue"] = 0.07

    elif race_scenario == "class_up":
        weights["history_same_condition"] = 0.08
        weights["history_same_venue"] = 0.09
        weights["odds_drift"] = 0.18
        weights["tips_index"] = 0.04  # 升班马降低官方贴士权重
        weights["expert"] = 0.00

    # ── 场地调整 ────────────────────────────────
    if venue == "HV":
        weights["barrier"] = weights.get("barrier", 0.05) + 0.03
        weights["history_same_venue"] = max(0, weights.get("history_same_venue", 0.10) - 0.03)

    # ── 距离调整 ────────────────────────────────
    if distance >= 1800:
        weights["sectional"] = weights.get("sectional", 0.15) + 0.05
        weights["odds_value"] = max(0, weights.get("odds_value", 0.15) - 0.05)

    # ── 泥地调整 ────────────────────────────────
    if track_type == "dirt":
        weights["history_same_condition"] = 0.05  # 专看泥地成绩
        weights["history_same_venue"] = 0.00
        weights["class_fit"] = weights.get("class_fit", 0.08) + 0.05

    # 确保权重合计为 1.0（浮点精度修正）
    total = sum(weights.values())
    if abs(total - 1.0) > 0.01:
        # 按比例归一化
        weights = {k: v / total for k, v in weights.items()}

    return weights
