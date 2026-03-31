#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
香港赛马分析脚本
基于历史战绩（同条件精准匹配）、赔率走势、配速分段等数据进行量化分析
"""

import sys
import io

# Windows PowerShell 下强制 UTF-8 输出，避免 emoji 编码报错
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import argparse
import json
import re
import math
import os
import hashlib
import time
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import quote

# HKJC 网站 URL 模板
HKJC_BASE      = "https://racing.hkjc.com"
RACE_CARD_URL  = HKJC_BASE + "/zh-hk/local/information/racecard"
HORSE_URL      = HKJC_BASE + "/zh-hk/local/information/horse?HorseNo="

# ==============================================================================
# 缓存配置
# ==============================================================================

# 缓存根目录（脚本所在目录的上级 .cache 文件夹）
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(os.path.dirname(_SCRIPT_DIR), ".cache")

# 各类缓存的 TTL（秒）
CACHE_TTL = {
    # 赛事结果/排位表：赛后24小时内不会再变，缓存7天
    "race_result":  7 * 24 * 3600,
    # 赛前排位表（当天赛事）：可能临时换马/换骑，缓存30分钟
    "race_card":    30 * 60,
    # 马匹历史战绩：每场赛后更新一次，缓存1天
    "horse_history": 24 * 3600,
    # 赔率数据：临场实时变化，缓存5分钟
    "odds":         5 * 60,
    # 通用网页（兜底）
    "default":      60 * 60,
}

# ==============================================================================
# 权重配置（与 references/analysis_weights.md 保持同步）
# ==============================================================================

DEFAULT_WEIGHTS = {
    "history_same_condition": 0.18,   # 同距离+同场地历史战绩（↑ +0.03）
    "history_same_venue":     0.13,   # 同场地（不限距离）历史战绩（↑ +0.03）
    "class_fit":              0.08,   # 班次适配度
    "odds_value":             0.15,   # 临场赔率绝对值
    "odds_drift":             0.13,   # 赔率走势变化幅度
    "sectional":              0.15,   # 配速/分段指数
    "jockey":                 0.05,   # 骑师（↓ 次要因素）
    "trainer":                0.04,   # 练马师（↓ 次要因素）
    "barrier":                0.05,   # 档位
    "expert":                 0.04,   # 专家预测
}

# Softmax 温度参数（越大概率越均摊，避免极端偏差）
SOFTMAX_TEMPERATURE = 1.5

# 单匹马概率上限
PROB_CAP = 0.50


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
        weights["history_same_venue"]     = 0.00
        weights["class_fit"]              = 0.15
        weights["expert"]                 = 0.00
        weights["jockey"]                 = 0.15
        weights["trainer"]                = 0.13
        # sectional / odds 保持默认

    elif race_scenario == "class_down":
        weights["class_fit"]              = 0.15
        weights["odds_drift"]             = 0.18
        weights["expert"]                 = 0.00
        weights["history_same_condition"] = 0.10
        weights["history_same_venue"]     = 0.07

    elif race_scenario == "class_up":
        weights["history_same_condition"] = 0.08
        weights["history_same_venue"]     = 0.09
        weights["odds_drift"]             = 0.18
        weights["expert"]                 = 0.00

    # ── 场地调整 ────────────────────────────────
    if venue == "HV":
        weights["barrier"]            = weights.get("barrier", 0.05) + 0.03
        weights["history_same_venue"] = max(0, weights.get("history_same_venue", 0.10) - 0.03)

    # ── 距离调整 ────────────────────────────────
    if distance >= 1800:
        weights["sectional"]  = weights.get("sectional", 0.15) + 0.05
        weights["odds_value"] = max(0, weights.get("odds_value", 0.15) - 0.05)

    # ── 泥地调整 ────────────────────────────────
    if track_type == "dirt":
        weights["history_same_condition"] = 0.05   # 专看泥地成绩
        weights["history_same_venue"]     = 0.00
        weights["class_fit"]              = weights.get("class_fit", 0.08) + 0.05

    # 确保权重合计为 1.0（浮点精度修正）
    total = sum(weights.values())
    if abs(total - 1.0) > 0.01:
        # 按比例归一化
        weights = {k: v / total for k, v in weights.items()}

    return weights


# ==============================================================================
# 概率计算（Softmax + 上限约束）
# ==============================================================================

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


# ==============================================================================
# 评分函数
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
    wins   = sum(1 for p in positions if p == 1)
    top3   = sum(1 for p in positions if p <= 3)
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
        wins  = sum(1 for r in own_records if r.get("position") == 1)
        top3  = sum(1 for r in own_records if r.get("position", 99) <= 3)
        n     = len(own_records)
        win_rate  = wins / n
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
        wins  = sum(1 for r in own_records if r.get("position") == 1)
        top3  = sum(1 for r in own_records if r.get("position", 99) <= 3)
        n     = len(own_records)
        win_rate  = wins / n
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
        expert_score                 : int (0-100)
    """
    field_map = {
        "history_same_condition": "history_same_condition_score",
        "history_same_venue":     "history_same_venue_score",
        "class_fit":              "class_fit_score",
        "odds_value":             "odds_value_score",
        "odds_drift":             "odds_drift_score",
        "sectional":              "sectional_score",
        "jockey":                 "jockey_score",
        "trainer":                "trainer_score",
        "barrier":                "barrier_score",
        "expert":                 "expert_score",
    }

    total = 0.0
    for weight_key, score_field in field_map.items():
        w = weights.get(weight_key, 0)
        s = horse_data.get(score_field, 50)  # 默认 50（中性）
        total += w * s

    return round(total, 2)


# ==============================================================================
# 网络请求与解析（保持原有结构，补充错误处理）
# ==============================================================================

def parse_args():
    parser = argparse.ArgumentParser(description="香港赛马分析工具")
    parser.add_argument("--date", type=str, default=None,
                        help="赛事日期，格式 YYYY/MM/DD，默认今天")
    parser.add_argument("--venue", type=str, required=False,
                        choices=["ST", "HV", "沙田", "跑马地"],
                        help="场地: ST/沙田 或 HV/跑马地")
    parser.add_argument("--race", type=int, required=False,
                        help="场次号")
    parser.add_argument("--distance", type=int, default=1400,
                        help="赛事距离（米），默认 1400")
    parser.add_argument("--track", type=str, default="turf",
                        choices=["turf", "dirt"],
                        help="赛道类型: turf/草地 或 dirt/泥地")
    parser.add_argument("--condition", type=str, default="good",
                        choices=["fast", "good_to_firm", "good", "yielding", "soft"],
                        help="场地状况")
    parser.add_argument("--scenario", type=str, default="normal",
                        choices=["normal", "newcomer", "class_down", "class_up"],
                        help="赛事场景")
    parser.add_argument("--output", type=str, default="markdown",
                        choices=["json", "markdown"],
                        help="输出格式")
    # ── 缓存控制 ────────────────────────────────────────────────
    parser.add_argument("--force-refresh", action="store_true",
                        help="忽略缓存，强制重新抓取所有数据")
    parser.add_argument("--clear-cache", action="store_true",
                        help="清除当前场次的缓存后重新分析")
    parser.add_argument("--cache-stats", action="store_true",
                        help="仅显示缓存统计信息，不执行分析")
    return parser.parse_args()


def normalize_venue(venue):
    if venue in ["ST", "沙田"]:
        return "ST"
    elif venue in ["HV", "跑马地"]:
        return "HV"
    return venue


def get_today_date():
    return datetime.now().strftime("%Y/%m/%d")


# ==============================================================================
# 缓存层
# ==============================================================================

def _cache_path(url: str) -> str:
    """根据 URL 生成缓存文件路径（用 SHA256 短哈希作文件名）。"""
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{url_hash}.json")


def _classify_url(url: str) -> str:
    """根据 URL 特征判断缓存类型，返回对应的 TTL key。"""
    url_lower = url.lower()
    if "odds" in url_lower:
        return "odds"
    if "horse.aspx" in url_lower or "/horse?" in url_lower:
        return "horse_history"
    if "localresults" in url_lower or "racecard" in url_lower:
        # 若是今天的赛事用短 TTL（赛前排位可能临时变更）
        today = datetime.now().strftime("%Y%m%d")
        url_nodash = url.replace("/", "").replace("-", "")
        if today in url_nodash:
            return "race_card"
        return "race_result"
    return "default"


def _cache_get(url: str):
    """
    尝试从磁盘读取缓存。
    命中且未过期 → 返回 HTML 字符串；否则 → 返回 None。
    """
    path = _cache_path(url)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            entry = json.load(f)
        ttl = CACHE_TTL.get(_classify_url(url), CACHE_TTL["default"])
        age = time.time() - entry.get("timestamp", 0)
        if age > ttl:
            return None  # 已过期
        return entry.get("content")
    except Exception:
        return None


def _cache_set(url: str, content: str) -> None:
    """将网页内容写入磁盘缓存。"""
    path = _cache_path(url)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"url": url, "timestamp": time.time(), "content": content},
                      f, ensure_ascii=False)
    except Exception as e:
        print(f"  ⚠️  缓存写入失败: {e}")


def cache_stats() -> dict:
    """返回缓存目录统计：文件数、总大小（KB）、最旧条目时间。"""
    if not os.path.isdir(CACHE_DIR):
        return {"count": 0, "size_kb": 0, "oldest": None}
    files = [os.path.join(CACHE_DIR, fn)
             for fn in os.listdir(CACHE_DIR) if fn.endswith(".json")]
    total_size = sum(os.path.getsize(f) for f in files)
    oldest_ts = None
    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8") as fp:
                ts = json.load(fp).get("timestamp", 0)
            if oldest_ts is None or ts < oldest_ts:
                oldest_ts = ts
        except Exception:
            pass
    return {
        "count":   len(files),
        "size_kb": round(total_size / 1024, 1),
        "oldest":  datetime.fromtimestamp(oldest_ts).strftime("%Y-%m-%d %H:%M")
                   if oldest_ts else None,
    }


def cache_clear(race_date: str = None, venue: str = None, race_no: int = None) -> int:
    """
    清理缓存。
    - 无参数          → 删除所有已过期条目
    - 传入 race_date  → 精确删除该场次相关缓存（可附加 venue / race_no）
    返回删除的文件数。
    """
    if not os.path.isdir(CACHE_DIR):
        return 0
    deleted = 0
    for fn in os.listdir(CACHE_DIR):
        if not fn.endswith(".json"):
            continue
        fpath = os.path.join(CACHE_DIR, fn)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                entry = json.load(f)
            cached_url = entry.get("url", "")

            if race_date:
                date_key  = race_date.replace("/", "").replace("-", "")
                url_clean = cached_url.replace("/", "").replace("-", "")
                if date_key not in url_clean:
                    continue
                if venue and venue.upper() not in cached_url.upper():
                    continue
                if race_no and f"RaceNo={race_no}" not in cached_url:
                    continue
                os.remove(fpath)
                deleted += 1
                continue

            # 通用：删除过期条目
            ttl = CACHE_TTL.get(_classify_url(cached_url), CACHE_TTL["default"])
            if time.time() - entry.get("timestamp", 0) > ttl:
                os.remove(fpath)
                deleted += 1
        except Exception:
            try:
                os.remove(fpath)
                deleted += 1
            except Exception:
                pass
    return deleted


# ==============================================================================
# 带缓存的网络请求
# ==============================================================================

def fetch_url(url, timeout=15, force_refresh=False):
    """
    抓取 URL 内容，自动读写磁盘缓存。

    force_refresh=True  → 跳过缓存，强制重新请求并刷新缓存。
    """
    # 1. 尝试读缓存
    if not force_refresh:
        cached = _cache_get(url)
        if cached is not None:
            ttl_key = _classify_url(url)
            print(f"  💾 缓存命中 [{ttl_key}]: {url[:80]}...")
            return cached

    # 2. 发起网络请求
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
        "Referer": "https://racing.hkjc.com/",
    }
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as response:
            content = response.read().decode("utf-8", errors="ignore")
        # 3. 写入缓存
        _cache_set(url, content)
        ttl_key = _classify_url(url)
        print(f"  🌐 网络请求 [{ttl_key}]: {url[:80]}...")
        return content
    except (URLError, HTTPError) as e:
        print(f"  ⚠️  抓取失败 {url}: {e}")
        return None


# ==============================================================================
# 马匹历史战绩抓取与解析
# ==============================================================================

# 马场文字 → 场地代码映射
_VENUE_MAP = {
    "沙田": "ST", "sha tin": "ST", "st": "ST",
    "跑马地": "HV", "跑馬地": "HV", "happy valley": "HV", "hv": "HV",
}

# 场地状况中文 → 英文规范值
_CONDITION_MAP = {
    "快": "fast", "好地快": "good_to_firm", "好": "good",
    "略黏": "yielding", "黏": "soft", "濕慢": "soft",
}


def _clean_text(html_fragment: str) -> str:
    """去除 HTML 标签，返回纯文本（合并空白）。"""
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html_fragment)).strip()


def parse_horse_history(html: str) -> dict:
    """
    解析 HKJC Horse.aspx 页面，返回马匹历史战绩及基本信息。

    返回结构：
    {
        "current_rating": int,          # 最後評分
        "history": [
            {
                "date":      "2023/04/30",
                "venue":     "ST",       # ST / HV
                "distance":  1200,       # 米
                "condition": "good",     # fast/good_to_firm/good/yielding/soft
                "race_class": "4",       # 班次
                "barrier":   8,          # 档位
                "rating":    52,         # 当场评分
                "position":  14,         # 名次（DNF/DQ 等 → 99）
                "odds":      182.0,      # 独赢赔率
                "running_positions": [13, 13, 14],  # 沿途走位
                "finish_time": "1:11.42",
            },
            ...
        ]
    }
    """
    result = {"current_rating": 40, "history": []}

    # ── 最後評分 ────────────────────────────────────────────────
    # 两种页面结构：旧格式用 "最後評分" / 新格式用 class 内嵌
    rating_m = re.search(
        r'最後評分[^<]*</td>\s*<td[^>]*>\s*(\d+)',
        html
    )
    if not rating_m:
        # 尝试兜底：找 "最後評分" 附近的第一个数字
        idx_r = html.find('最後評分')
        if idx_r > 0:
            num_m = re.search(r'>\s*(\d+)\s*<', html[idx_r:idx_r+300])
            if num_m:
                result["current_rating"] = int(num_m.group(1))
    else:
        result["current_rating"] = int(rating_m.group(1))

    # ── 往绩表：找 class=bigborder 的 table ──────────────────────
    # 表头关键字：'場次'
    table_start = html.find('class=bigborder')
    if table_start == -1:
        table_start = html.find('class="bigborder"')
    if table_start == -1:
        return result

    # 找到该 table 的结束
    table_open = html.rfind('<table', 0, table_start + 20)
    table_end = html.find('</table>', table_open)
    if table_end == -1:
        return result
    table_html = html[table_open: table_end + len('</table>')]

    # ── 逐 <tr> 解析 ────────────────────────────────────────────
    tr_pattern = re.compile(r'<tr\b[^>]*>(.*?)</tr>', re.DOTALL | re.IGNORECASE)
    td_pattern = re.compile(r'<td\b[^>]*>(.*?)</td>', re.DOTALL | re.IGNORECASE)

    for tr_m in tr_pattern.finditer(table_html):
        tr_html = tr_m.group(1)
        tds_raw  = [m.group(1) for m in td_pattern.finditer(tr_html)]
        if len(tds_raw) < 12:
            continue  # 跳过表头行 / 马季分隔行

        tds = [_clean_text(td) for td in tds_raw]

        def g(i, default=""):
            return tds[i] if i < len(tds) else default

        # 列顺序：[0]场次 [1]名次 [2]日期 [3]马场 [4]途程 [5]场地状况
        #         [6]班次 [7]档位 [8]评分 [9]练马师 [10]骑师
        #         [11]头马距离 [12]赔率 [13]负磅 [14]走位 [15]时间 [16]体重

        # 日期：支持 DD/MM/YYYY 和 DD/MM/YY 两种格式
        raw_date = g(2)
        date_m = re.match(r'(\d{1,2})/(\d{2})/(\d{2,4})', raw_date)
        if not date_m:
            continue
        day, month, year = date_m.group(1), date_m.group(2), date_m.group(3)
        if len(year) == 2:
            year = ("20" + year) if int(year) <= 50 else ("19" + year)
        race_date = f"{year}/{month}/{day.zfill(2)}"

        # 场地
        venue_raw = g(3).lower()
        venue = "ST"
        for k, v in _VENUE_MAP.items():
            if k.lower() in venue_raw:
                venue = v
                break

        # 途程
        try:
            distance = int(re.sub(r'[^\d]', '', g(4)))
        except (ValueError, IndexError):
            distance = 0

        # 场地状况
        cond_raw = g(5)
        condition = _CONDITION_MAP.get(cond_raw, "good")

        # 班次
        race_class = g(6)

        # 档位
        try:
            barrier = int(re.sub(r'[^\d]', '', g(7)).strip() or "0")
        except ValueError:
            barrier = 0

        # 评分
        try:
            rating = int(re.sub(r'[^\d]', '', g(8)).strip() or "0")
        except ValueError:
            rating = 0

        # 名次
        pos_raw = g(1)
        try:
            position = int(re.sub(r'[^\d]', '', pos_raw).strip() or "99")
        except ValueError:
            position = 99  # DNF / DQ

        # 赔率
        try:
            odds = float(re.sub(r'[^\d.]', '', g(12)).strip() or "0") or None
        except ValueError:
            odds = None

        # 走位（如 "13 13 14" 或 "8 9 7 1"）
        run_pos_raw = g(14)
        run_positions = []
        if run_pos_raw:
            parts = re.findall(r'\d+', run_pos_raw)
            run_positions = [int(p) for p in parts]

        # 骑师 / 练马师
        jockey  = g(10)
        trainer = g(9)

        # 完成时间
        finish_time = g(15)

        result["history"].append({
            "date":               race_date,
            "venue":              venue,
            "distance":           distance,
            "condition":          condition,
            "race_class":         race_class,
            "barrier":            barrier,
            "rating":             rating,
            "position":           position,
            "odds":               odds,
            "running_positions":  run_positions,
            "finish_time":        finish_time,
            "jockey":             jockey,
            "trainer":            trainer,
        })

    return result


def fetch_horse_history(horse_id: str, force_refresh: bool = False) -> dict:
    """
    抓取并解析指定马匹的历史战绩页面。

    参数：
        horse_id      : HKJC 马匹 ID，如 "HK_2021_G361"
        force_refresh : 忽略缓存强制重新抓取

    返回：parse_horse_history() 的结果字典；抓取失败时返回默认空结构。
    """
    url = (
        "https://racing.hkjc.com/racing/information/Chinese/Horse/Horse.aspx"
        f"?HorseId={horse_id}"
    )
    html = fetch_url(url, timeout=20, force_refresh=force_refresh)
    if not html:
        return {"current_rating": 40, "history": []}
    return parse_horse_history(html)


def parse_race_entries(html, race_no=None):
    """
    从 HKJC 排位表 (RaceCard) 页面 HTML 解析参赛马匹信息。

    页面结构（zh-hk/local/information/racecard）：
    - 每匹马一行 <tr class="f_fs11">，包含 horseid= 链接
    - td 列顺序（27列）：
        [0]马号  [1]班次  [2](空)  [3]马名  [4]烙号
        [5]负磅  [6]骑师  [7](空)  [8]档位  [9]练马师
        [10]?   [11]评分  [12]评分变化  ...
        [18]性别 [19]总奖金 ...
    """
    horses = []

    # 定位所有含 horseid 的 tr 行（排位表用 class="f_fs11"）
    tr_pattern = re.compile(
        r'<tr[^>]*class="[^"]*f_fs\d+[^"]*"[^>]*>(.*?)</tr>',
        re.DOTALL | re.IGNORECASE
    )
    td_pattern = re.compile(r'<td[^>]*>(.*?)</td>', re.DOTALL | re.IGNORECASE)

    for tr_m in tr_pattern.finditer(html):
        tr_content = tr_m.group(1)
        if 'horseid=' not in tr_content.lower():
            continue

        # 提取 horseid 和马名
        horse_link = re.search(r'horseid=([A-Za-z0-9_]+)', tr_content, re.IGNORECASE)
        name_link  = re.search(r'href="/zh-hk/local/information/horse\?horseid=[^"]+[^>]*>([^<]+)</a>', tr_content)
        if not horse_link:
            continue
        horse_id   = horse_link.group(1).strip()
        horse_name = name_link.group(1).strip() if name_link else ""

        # 提取骑师 (jockeyid=)
        jockey_m = re.search(r'jockeyid=([A-Za-z0-9_]+)', tr_content, re.IGNORECASE)
        if jockey_m:
            jockey_text = re.search(
                r'jockeyid=' + jockey_m.group(1) + r'[^>]*>([^<]+)</a>',
                tr_content
            )
            jockey = jockey_text.group(1).strip() if jockey_text else ""
        else:
            jockey = ""

        # 提取练马师 (trainerid=)
        trainer_m = re.search(r'trainerid=([A-Za-z0-9_]+)', tr_content, re.IGNORECASE)
        if trainer_m:
            trainer_text = re.search(
                r'trainerid=' + trainer_m.group(1) + r'[^>]*>([^<]+)</a>',
                tr_content
            )
            trainer = trainer_text.group(1).strip() if trainer_text else ""
        else:
            trainer = ""

        # 解析所有 td 纯文本，维持列索引
        tds_raw = [td_m.group(1) for td_m in td_pattern.finditer(tr_content)]
        tds = [re.sub(r'<[^>]+>', ' ', td).strip() for td in tds_raw]

        def get_td(idx, default=""):
            return tds[idx] if idx < len(tds) else default

        # TD[0]=马号，TD[8]=档位，TD[5]=负磅（排位表无赔率）
        try:
            horse_no = int(get_td(0, "0").strip())
        except (ValueError, IndexError):
            horse_no = len(horses) + 1

        try:
            barrier = int(get_td(8, "0").strip())
        except (ValueError, IndexError):
            barrier = 0

        # 负磅
        try:
            weight = float(get_td(5, "0").replace(",", ""))
        except (ValueError, IndexError):
            weight = 0

        horses.append({
            "id":      horse_id,
            "name":    horse_name,
            "no":      horse_no,
            "barrier": barrier,
            "jockey":  jockey,
            "trainer": trainer,
            "weight":  weight,
            "final_odds":   None,   # 排位表无赔率，赛后补充
            "opening_odds": None,
            "history":         [],
            "current_rating":  40,
            # 各维度评分（默认 50 = 数据缺失中性值）
            "history_same_condition_score": 40,
            "history_same_venue_score":     40,
            "class_fit_score":              50,
            "odds_value_score":             50,
            "odds_drift_score":             50,
            "sectional_score":              50,
            "jockey_score":                 50,
            "trainer_score":                50,
            "barrier_score":                50,
            "expert_score":                 50,
            "total_score":                  0,
            "probability":                  0,
            "confidence":                   "⭐ 低",
            "longshot_alert":               False,
        })

    return horses


def analyze_horse(horse, venue, distance, track_condition):
    """对单匹马进行多维度评分"""
    # 赔率评分
    if horse["final_odds"]:
        horse["odds_value_score"] = score_odds_value(horse["final_odds"])
        horse["odds_drift_score"] = score_odds_drift(
            horse["opening_odds"], horse["final_odds"]
        )

    # 历史战绩评分
    history = horse.get("history", [])
    horse["history_same_condition_score"] = score_history_same_condition(
        history, venue, distance
    )
    horse["history_same_venue_score"] = score_history_same_venue(history, venue)

    # 班次适配度：用实际抓取的 current_rating 及动态班次区间
    rating = horse.get("current_rating", 40)
    class_ceiling = horse.get("class_ceiling", 40)
    class_floor   = horse.get("class_floor", 21)
    horse["class_fit_score"] = score_class_fit(rating, class_ceiling, class_floor)

    # 从历史走位推导惯用跑法（front / closer / even）
    if not horse.get("running_style"):
        run_styles = []
        for r in history[-5:]:   # 最近5场
            rp = r.get("running_positions", [])
            n_runners = 14  # 默认估算
            if rp:
                first_pos = rp[0]
                last_pos  = rp[-1]
                if first_pos <= 3:
                    run_styles.append("front")
                elif last_pos < first_pos - 2:
                    run_styles.append("closer")
                else:
                    run_styles.append("even")
        if run_styles:
            # 取众数
            from collections import Counter
            horse["running_style"] = Counter(run_styles).most_common(1)[0][0]
        else:
            horse["running_style"] = "even"

    # 配速评分：用历史推导的 running_style
    horse["sectional_score"] = score_sectional(
        pace_index=horse.get("pace_index", 1.0),
        running_style=horse.get("running_style", "even"),
        track_condition=track_condition,
    )

    # 档位评分：沙田草地 1400m 内档(1-4)略占优势
    barrier = horse.get("barrier", 0)
    if barrier:
        if 1 <= barrier <= 4:
            horse["barrier_score"] = 65
        elif 5 <= barrier <= 8:
            horse["barrier_score"] = 55
        elif 9 <= barrier <= 12:
            horse["barrier_score"] = 45
        else:
            horse["barrier_score"] = 38

    # 骑师 / 练马师评分（基于历史战绩统计，次要因素）
    horse["jockey_score"]  = score_jockey(
        horse.get("jockey", ""), history
    )
    horse["trainer_score"] = score_trainer(
        horse.get("trainer", ""), history
    )

    # 数据充足度
    same_condition_count = sum(
        1 for r in history
        if r.get("venue") == venue and abs(r.get("distance", 0) - distance) <= 200
    )
    horse["confidence"] = data_confidence(
        same_condition_count, horse["opening_odds"] is not None
    )

    # 冷门关注
    has_top3 = any(
        r.get("position", 99) <= 3
        for r in history
        if r.get("venue") == venue and abs(r.get("distance", 0) - distance) <= 200
    )
    horse["longshot_alert"] = is_longshot_alert(
        final_odds=horse.get("final_odds") or 99,
        opening_odds=horse.get("opening_odds"),
        has_same_condition_top3=has_top3,
        class_fit_score=horse["class_fit_score"],
    )

    return horse


def format_markdown_output(race_info, horses):
    """生成 Markdown 格式分析报告（含历史战绩摘要与分项评分）"""
    venue_name = "沙田" if race_info["venue"] == "ST" else "跑马地"
    lines = []

    lines.append(f"## 🏇 {race_info['date']} {venue_name} 第{race_info['race']}场 分析报告\n")
    lines.append("### ⚠️ 风险提示")
    lines.append("> 本分析基于历史数据，仅供技术参考，**不构成任何投注建议**。赛马投注有风险，请理性参与。\n")

    sorted_horses = sorted(horses, key=lambda x: x["total_score"], reverse=True)

    # ── 前3名概率预测 ──────────────────────────────────────────────
    lines.append("### 📊 前3名概率预测\n")
    lines.append("| 排名 | 马号 | 马名 | 评分 | 胜出概率 | 数据充足度 | 惯用跑法 | 历史战绩 | 分析要点 |")
    lines.append("|:--:|:--:|:--|:--:|:--:|:--:|:--:|:--|:--|")

    for i, h in enumerate(sorted_horses[:3], 1):
        # 历史战绩摘要
        hist = h.get("history", [])
        hist_summary = f"{len(hist)}场" if hist else "无记录"
        wins  = sum(1 for r in hist if r.get("position") == 1)
        top3  = sum(1 for r in hist if r.get("position", 99) <= 3)
        if hist:
            hist_summary = f"{len(hist)}场 {wins}冠{top3}连"

        # 跑法
        run_style_map = {"front": "领跑", "closer": "后上", "even": "中间"}
        run_style = run_style_map.get(h.get("running_style", "even"), "中间")

        # 分析要点
        reason = f"赔率{h.get('final_odds', '-')}"
        if h["history_same_condition_score"] >= 60:
            reason += "，同条件有佳绩"
        if h["odds_drift_score"] >= 70:
            reason += "，赔率走势积极"
        if h.get("longshot_alert"):
            reason += "，⚡冷门关注"

        lines.append(
            f"| {i} | {h['no']} | {h['name']} | {h['total_score']:.1f} "
            f"| **{h['probability']:.1f}%** | {h['confidence']} "
            f"| {run_style} | {hist_summary} | {reason} |"
        )

    # ── 全场分项评分表 ──────────────────────────────────────────────
    lines.append("\n### 📋 全场分项评分（各维度0-100）\n")
    lines.append("| 马号 | 马名 | 综合 | 历史同条件 | 历史同场 | 班次适配 | 赔率 | 赔率走势 | 配速 | 档位 | 数据 |")
    lines.append("|:--:|:--|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|")

    for h in sorted_horses:
        lines.append(
            f"| {h['no']} | {h['name']} | {h['total_score']:.1f} "
            f"| {h['history_same_condition_score']} "
            f"| {h['history_same_venue_score']} "
            f"| {h['class_fit_score']} "
            f"| {h['odds_value_score']} "
            f"| {h['odds_drift_score']} "
            f"| {h['sectional_score']} "
            f"| {h['barrier_score']} "
            f"| {h['confidence']} |"
        )

    # ── 冷门关注 ──────────────────────────────────────────────────
    alerts = [h for h in horses if h.get("longshot_alert")]
    if alerts:
        lines.append("\n### 🔍 冷门关注\n")
        for h in alerts:
            lines.append(
                f"- **{h['no']}号 {h['name']}**（赔率 {h.get('final_odds', '-')}）："
                f"有同条件前3记录，赔率未拉长，班次适配度 {h['class_fit_score']}"
            )

    # ── 投注建议 ──────────────────────────────────────────────────
    lines.append("\n### 💡 投注建议（仅供参考）\n")
    if sorted_horses:
        w = sorted_horses[0]
        lines.append(f"**推荐独赢**: {w['no']}号 {w['name']}（概率 {w['probability']:.1f}%，评分 {w['total_score']:.1f}）")
    if len(sorted_horses) >= 2:
        q0, q1 = sorted_horses[0], sorted_horses[1]
        lines.append(f"**推荐连赢**: {q0['no']}, {q1['no']}（{q0['name']} + {q1['name']}）")
    if len(sorted_horses) >= 3:
        lines.append(
            f"**推荐三重彩**: {sorted_horses[0]['no']}, {sorted_horses[1]['no']}, {sorted_horses[2]['no']}"
        )

    lines.append("\n---")
    lines.append(f"*数据来源：香港赛马会 (HKJC) | 分析时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}*")

    return "\n".join(lines)



# ==============================================================================
# 主程序
# ==============================================================================

def main():
    args = parse_args()

    # ── 仅显示缓存统计 ───────────────────────────────────────────
    if args.cache_stats:
        stats = cache_stats()
        print(f"📦 缓存目录: {CACHE_DIR}")
        print(f"   文件数  : {stats['count']}")
        print(f"   总大小  : {stats['size_kb']} KB")
        print(f"   最旧条目: {stats['oldest'] or '无'}")
        return

    # venue / race 在非 --cache-stats 模式下必须提供
    if not args.venue or not args.race:
        print("❌ 请提供 --venue 和 --race 参数（或使用 --cache-stats 查看缓存状态）")
        return

    race_date = args.date if args.date else get_today_date()
    venue = normalize_venue(args.venue)
    race_no = args.race
    distance = args.distance
    track_type = args.track
    track_condition = args.condition
    scenario = args.scenario
    force_refresh = args.force_refresh

    # ── 清除当前场次缓存 ─────────────────────────────────────────
    if args.clear_cache:
        n = cache_clear(race_date=race_date, venue=venue, race_no=race_no)
        print(f"🗑️  已清除 {n} 个缓存文件（{race_date} {venue} 第{race_no}场）")
        force_refresh = True   # 清除后自动强制刷新

    print(f"🏇 分析赛事: {race_date} {venue} 第{race_no}场  {distance}m {track_type} [{scenario}]")
    if force_refresh:
        print("🔄 强制刷新模式：跳过缓存，重新抓取所有数据")
    else:
        stats = cache_stats()
        print(f"💾 缓存状态: {stats['count']} 个文件 / {stats['size_kb']} KB  (目录: {CACHE_DIR})")

    # 获取适配权重
    weights = get_weights(venue, distance, track_type, scenario)
    print(f"📐 权重配置: {json.dumps({k: round(v, 3) for k, v in weights.items()}, ensure_ascii=False)}")

    # 获取赛事数据（带缓存）
    # 排位表 URL 格式：racedate=YYYY/MM/DD&Racecourse=ST&RaceNo=N
    url = (
        f"{RACE_CARD_URL}"
        f"?racedate={quote(race_date)}&Racecourse={venue}&RaceNo={race_no}"
    )
    html = fetch_url(url, force_refresh=force_refresh)

    if not html:
        print("❌ 无法获取赛事数据，请检查日期/场地/场次是否正确。")
        return

    # 解析参赛马匹
    horses = parse_race_entries(html, race_no=race_no)
    if not horses:
        print("⚠️  未能解析出参赛马匹，页面结构可能已变更。")
        return
    print(f"✅ 找到 {len(horses)} 匹参赛马匹")

    # ── 抓取每匹马历史战绩（带缓存，一次性批量）──────────────────
    print(f"\n📚 正在抓取 {len(horses)} 匹参赛马匹的历史战绩...")
    for i, horse in enumerate(horses, 1):
        horse_id = horse.get("id", "")
        if not horse_id:
            continue
        print(f"  [{i:2d}/{len(horses)}] {horse['name']} ({horse_id})")
        hist_data = fetch_horse_history(horse_id, force_refresh=force_refresh)
        horse["history"]        = hist_data.get("history", [])
        horse["current_rating"] = hist_data.get("current_rating", 40)
        # 简短摘要
        h_count = len(horse["history"])
        same_cond = sum(
            1 for r in horse["history"]
            if r.get("venue") == venue and abs(r.get("distance", 0) - distance) <= 200
        )
        if h_count > 0:
            print(f"         历史共 {h_count} 场，同条件 {same_cond} 场，当前评分 {horse['current_rating']}")
        else:
            print(f"         暂无历史战绩")
    print()

    # 各维度评分
    for horse in horses:
        horse = analyze_horse(horse, venue, distance, track_condition)
        horse["total_score"] = calculate_total_score(horse, weights)

    # 概率计算（Softmax + 上限约束）
    scores = [h["total_score"] for h in horses]
    probs = softmax_probability(scores)
    for horse, prob in zip(horses, probs):
        horse["probability"] = prob

    # 输出结果
    race_info = {"date": race_date, "venue": venue, "race": race_no}

    if args.output == "markdown":
        print("\n" + format_markdown_output(race_info, horses))
    else:
        print(json.dumps({
            "race_info": race_info,
            "weights_used": weights,
            "horses": horses,
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
