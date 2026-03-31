#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HKJC 赛马分析工具 - 缓存管理模块

提供磁盘缓存读写、TTL 过期管理、统计和清理功能。
"""

import os
import json
import hashlib
import time
from datetime import datetime
from config import CACHE_DIR, CACHE_TTL


# ==============================================================================
# 缓存路径 & 类型识别
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
    if "tipsindex" in url_lower or "tips_index" in url_lower:
        return "tips_index"
    if "localresults" in url_lower or "racecard" in url_lower:
        # 若是今天的赛事用短 TTL（赛前排位可能临时变更）
        today = datetime.now().strftime("%Y%m%d")
        url_nodash = url.replace("/", "").replace("-", "")
        if today in url_nodash:
            return "race_card"
        return "race_result"
    return "default"


# ==============================================================================
# 缓存读写
# ==============================================================================

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


# ==============================================================================
# 缓存统计 & 清理
# ==============================================================================

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
        "count": len(files),
        "size_kb": round(total_size / 1024, 1),
        "oldest": datetime.fromtimestamp(oldest_ts).strftime("%Y-%m-%d %H:%M")
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
                date_key = race_date.replace("/", "").replace("-", "")
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
