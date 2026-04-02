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
    "history_same_condition": 0.18,  # 同距离+同场地历史战绩（↑ +0.03）
    "history_same_venue": 0.13,  # 同场地（不限距离）历史战绩（↑ +0.03）
    "class_fit": 0.08,  # 班次适配度
    "odds_value": 0.15,  # 临场赔率绝对值
    "odds_drift": 0.13,  # 赔率走势变化幅度
    "sectional": 0.15,  # 配速/分段指数
    "jockey": 0.05,  # 骑师（↓ 次要因素）
    "trainer": 0.04,  # 练马师（↓ 次要因素）
    "barrier": 0.05,  # 档位
    "tips_index": 0.06,  # HKJC 官方贴士指数（高于外部专家预测）
    "expert": 0.04,  # 外部专家预测（降权）
}

# Softmax 温度参数（越大概率越均摊，避免极端偏差）
SOFTMAX_TEMPERATURE = 1.5

# 单匹马概率上限
PROB_CAP = 0.50

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
