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
        # v1.6.6: odds_value 40%（市场共识） + tips_index 13%（官方信号）+ 骑师13% + 练马师13% = 79%
        weights["history_same_condition"] = 0.00
        weights["history_same_venue"] = 0.00
        weights["class_fit"] = 0.16
        weights["odds_value"] = 0.40   # 初出马完全依赖市场定价
        weights["odds_drift"] = 0.00    # 保留逻辑，暂无数据
        weights["sectional"] = 0.05
        weights["tips_index"] = 0.10   # 官方贴士对初出马有参考价值（v1.6.6：从13%降至10%）
        weights["expert"] = 0.00
        weights["jockey"] = 0.11
        weights["trainer"] = 0.13
        weights["barrier"] = 0.05

    elif race_scenario == "class_down":
        weights["class_fit"] = 0.16
        weights["odds_value"] = 0.20  # 降班马赔率信号更强
        weights["odds_drift"] = 0.20   # 市场对降班马反应灵敏
        weights["tips_index"] = 0.03  # 降班马降低官方贴士权重
        weights["expert"] = 0.00
        weights["history_same_condition"] = 0.08
        weights["history_same_venue"] = 0.05

    elif race_scenario == "class_up":
        weights["history_same_condition"] = 0.06
        weights["history_same_venue"] = 0.07
        weights["odds_value"] = 0.20
        weights["odds_drift"] = 0.00   # v1.6.6: 临场赔率走势暂无数据，归零
        weights["tips_index"] = 0.03  # 升班马降低官方贴士权重
        weights["expert"] = 0.00

    # ── 场地调整 ────────────────────────────────
    if venue == "HV":
        weights["barrier"] = weights.get("barrier", 0.04) + 0.04  # HV 内档更重要
        weights["history_same_venue"] = max(0, weights.get("history_same_venue", 0.15) - 0.03)

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
