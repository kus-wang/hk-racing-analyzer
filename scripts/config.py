#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HKJC 赛马分析工具 - 配置模块

包含所有常量配置、URL 模板、缓存 TTL 等。
"""

import os

# ==============================================================================
# HKJC 网站 URL 模板
# ==============================================================================

HKJC_BASE = "https://racing.hkjc.com"
RACE_CARD_URL = HKJC_BASE + "/zh-hk/local/information/racecard"
HORSE_URL = HKJC_BASE + "/zh-hk/local/information/horse?HorseNo="
TIPS_INDEX_URL = HKJC_BASE + "/racing/chinese/tipsindex/tips_index.asp"
LOCAL_RESULTS_URL = HKJC_BASE + "/racing/information/Chinese/Racing/LocalResults.aspx"

# HKJC 投注赔率页面 URL 模板
# 格式：https://bet.hkjc.com/ch/racing/wp/{YYYY-MM-DD}/{VENUE}/{RACE_NO}
BETTING_ODDS_URL_TEMPLATE = "https://bet.hkjc.com/ch/racing/wp/{date}/{venue}/{race_no}"

# ==============================================================================
# 缓存配置
# ==============================================================================

# 缓存根目录（脚本所在目录的上级 .cache 文件夹）
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(os.path.dirname(_SCRIPT_DIR), ".cache")

# 各类缓存的 TTL（秒）
CACHE_TTL = {
    # 赛事结果/排位表：赛后24小时内不会再变，缓存7天
    "race_result": 7 * 24 * 3600,
    # 赛前排位表（当天赛事）：可能临时换马/换骑，缓存30分钟
    "race_card": 30 * 60,
    # 马匹历史战绩：每场赛后更新一次，缓存1天
    "horse_history": 24 * 3600,
    # 赔率数据：临场实时变化，缓存5分钟
    "odds": 5 * 60,
    # 贴士指数：每场赛前更新，缓存30分钟
    "tips_index": 30 * 60,
    # 通用网页（兜底）
    "default": 60 * 60,
}

# ==============================================================================
# 权重配置（与 references/analysis_weights.md 保持同步）
# ==============================================================================

DEFAULT_WEIGHTS = {
    # ── v1.4.11 权重调整（2026-04-05）：赔率权重 30%→40%
    #   理由：实盘赔率已能正确抓取（v1.4.10），即时赔率是市场共识，
    #   在赛前1-2小时是最高质量的预测信号，权重应显著提高。
    "history_same_condition": 0.13,  # 同距离+同场地历史战绩（↓ -0.03，历史数据补充赔率共识）
    "history_same_venue": 0.15,  # 同场地（不限距离）历史战绩（↓ -0.03）
    "class_fit": 0.07,  # 班次适配度（↓ -0.01）
    "odds_value": 0.22,  # 赔率综合评分：独赢分档+位置加成+全场标准化（↑ +0.07）
    "odds_drift": 0.18,  # 赔率走势变化幅度（↑ +0.03，提高市场信号）
    "sectional": 0.08,  # 配速/分段指数（↓ -0.02，待实测数据接入后恢复10%）
    "jockey": 0.04,  # 骑师（↓ -0.01，次要因素）
    "trainer": 0.03,  # 练马师（↓ -0.01，次要因素）
    "barrier": 0.04,  # 档位（↓ -0.01）
    "tips_index": 0.06,  # HKJC 官方贴士指数（不变）
    "expert": 0.00,  # 外部专家预测（移除：信息来源不稳定）
}

# Softmax 温度参数（越大概率越均摊，避免极端偏差）
# v1.4.11：2.0→4.0 调整
# 背景：
# - 赔率权重提高（30%→40%）使 odds_score 分量增大
# - score_implied_probability() 修复后：不再全场 max 标准化，
#   改为直接返回隐含胜率（1.8 odds → 评分 47，13 odds → 7）
# - odds_market_score = odds_value(40%) × 0.4 + implied_prob(60%) × 0.6
#   → #1: 65.4, #14: 19.8, #4: 25.0（score gap ≈ 45 分）
# T=4.0 配合 odds_market_score gap=45 使 Softmax 输出：
#   #1 ≈ 54%, #14 ≈ 19%, #4 ≈ 11%
# 这与 1.8 favourite 在 14 匹马场的市场实际概率（约 48-52%）吻合，
# 且模型叠加了同场地历史、贴士指数等正向信号后，给到 54% 是合理的高置信度。
SOFTMAX_TEMPERATURE = 4.0

# 单匹马概率上限
# v1.4.11：0.50→0.88 调整
# T=4.0 下 #1 ≈ 54%，cap=0.88 不会被触发，保留防止极端情况的上限约束。
PROB_CAP = 0.88

# ==============================================================================
# 场地/状况映射
# ==============================================================================

# 马场文字 → 场地代码映射
VENUE_MAP = {
    "沙田": "ST", "sha tin": "ST", "st": "ST",
    "跑马地": "HV", "跑馬地": "HV", "happy valley": "HV", "hv": "HV",
}

# 场地状况中文 → 英文规范值
CONDITION_MAP = {
    "快": "fast", "好地快": "good_to_firm", "好": "good",
    "略黏": "yielding", "黏": "soft", "濕慢": "soft",
}
