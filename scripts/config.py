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

# HKJC GraphQL API Node.js bridge 配置（v1.6.0）
API_NODE_RUNTIME = os.environ.get("HKJC_API_NODE", "node")
API_CLIENT_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hkjc_api_client.js")

API_MAX_ATTEMPTS = 2                  # 最多 2 次尝试（含首次）
API_RETRY_DELAY_SECONDS = 0.5         # 失败后等待 500ms 再重试
API_REQUEST_INTERVAL_SECONDS = 0.5    # 任意两次 API 请求之间至少间隔 500ms
API_TIMEOUT_SECONDS = 25
API_DEFAULT_ODDS_TYPES = ("WIN", "PLA", "QIN", "QPL", "TRI")


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
    # ── v1.6.6 权重调整（2026-04-16）：
    # 1. odds_drift 18%→0%：临场赔率走势数据暂时无法获取，保留评分逻辑但归零权重。
    # 2. odds_value 22%→30%：赔率绝对值是最直接的市场共识信号，提升占比。
    # 3. 其余9项各+1%：权重更均衡，避免过度依赖单一维度。
    "history_same_condition": 0.15,  # 同距离+同场地历史战绩（↑ +0.02）
    "history_same_venue": 0.18,  # 同场地（不限距离）历史战绩（↑ +0.01）
    "class_fit": 0.08,  # 班次适配度（↑ +0.01）
    "odds_value": 0.30,  # 赔率综合评分（↑ +0.08）
    "odds_drift": 0.00,  # 赔率走势变化幅度（↓ -0.18，保留逻辑，暂无数据）
    "sectional": 0.09,  # 配速/分段指数（↑ +0.01）
    "jockey": 0.06,  # 骑师（↑ +0.02）
    "trainer": 0.04,  # 练马师（↑ +0.01）
    "barrier": 0.05,  # 档位（↑ +0.01）
    "tips_index": 0.05,  # HKJC 官方贴士指数（↑ +0.01）
    "expert": 0.00,  # 外部专家预测（移除：信息来源不稳定）
}

# Softmax 温度参数（越大概率越均摊，避免极端偏差）
# v1.4.11：2.0→4.0 调整
# v1.4.12：引入动态温度（probability.py 的 dynamic_temperature()），
#          此处的默认值作为无赔率数据时的回退值（fallback）。
# 场内赔率离散度档位（probability.py dynamic_temperature()）：
#   ratio > 20 → T=6.5（超悬殊场）
#   ratio > 10 → T=5.5（大差异场）
#   ratio > 5  → T=5.0（正常场，即此默认值）
#   ratio <= 5 → T=4.5（均衡场，无明显共识）
# v1.6.4：整体 +0.5，改善高分马高估问题。
SOFTMAX_TEMPERATURE = 4.5

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

# ==============================================================================
# 顶级TJ组合白名单配置 (v1.6.3 新增)
# ==============================================================================
# 顶级骑师+练马师组合有更好的协同效应，满足条件时给予额外加分。
# 格式：(jockey_prefix, trainer_prefix, bonus)
# 匹配方式：前缀匹配（不区分大小写）

TOP_TJ_COMBOS = [
    ("Z Purton", "J Size", 10),
    ("V R Richards", "J Size", 9),
    ("Z Purton", "C Fownes", 8),
    ("K H Yeung", "P F Yiu", 7),
    ("H T Mo", "K W Lui", 7),
    ("C L Chau", "K W Lui", 6),
    ("A Badenoch", "C S Shum", 6),
    ("J J M Cavieres", "D J Whyte", 6),
    ("M Chadwick", "A S Cruz", 6),
]
