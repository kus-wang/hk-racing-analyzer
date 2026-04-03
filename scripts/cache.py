#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HKJC 赛马分析工具 - 缓存管理模块

提供磁盘缓存读写、TTL 过期管理、统计和清理功能。

优化（v1.4.8）：
- Zlib 压缩存储：HTML 原始内容压缩后存储，节省 70-80% 空间
- 结构化数据优先：parsed 字段直接存解析结果，避免回读时重复解析
- 向后兼容：自动识别并解压旧版未压缩条目
"""

import os
import json
import hashlib
import time
import zlib
import base64
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
# 缓存压缩/解压工具
# ==============================================================================

def _compress(content: str) -> str:
    """将字符串内容压缩为 base64 编码的字符串。"""
    compressed = zlib.compress(content.encode("utf-8"), level=6)
    return base64.b64encode(compressed).decode("ascii")


def _decompress(compressed_str: str) -> str:
    """解压 base64 编码的压缩字符串。"""
    try:
        compressed = base64.b64decode(compressed_str.encode("ascii"))
        return zlib.decompress(compressed).decode("utf-8")
    except Exception:
        return None


# ==============================================================================
# 缓存读写
# ==============================================================================

def _cache_get(url: str, cache_key: str = None):
    """
    尝试从磁盘读取缓存。

    参数：
        url       : 用于判断 TTL 类型（若 cache_key 未提供）
        cache_key : 可选，直接指定缓存文件 key（用于 odds 等自定义 key 场景）

    命中且未过期 → 返回 HTML 字符串或结构化数据；
    结构化数据优先（parsed 字段）→ 其次返回原始 HTML（content 字段）。

    找不到 / 已过期 / 解析失败 → 返回 None。
    """
    path = _cache_path(cache_key if cache_key else url)
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            entry = json.load(f)

        ttl = CACHE_TTL.get(_classify_url(url), CACHE_TTL["default"])
        age = time.time() - entry.get("timestamp", 0)
        if age > ttl:
            return None  # 已过期

        # 优先返回结构化 parsed 数据
        if "parsed" in entry and entry["parsed"] is not None:
            return entry["parsed"]

        # 其次返回原始 HTML（支持压缩或未压缩）
        content = entry.get("content", "")
        if not content:
            return None

        # 旧版未压缩条目：直接返回
        if not entry.get("_compressed", False):
            return content

        # 新版压缩条目：解压后返回
        decompressed = _decompress(content)
        return decompressed if decompressed else content

    except Exception:
        return None


def _cache_set(url: str, content: str, parsed=None) -> None:
    """
    将网页内容写入磁盘缓存。

    参数：
        content : 原始 HTML 字符串（会被压缩存储）
        parsed  : 结构化解析结果（dict/list 等），可选，优先被读回
    """
    path = _cache_path(url)
    timestamp = time.time()

    # 构造缓存条目
    entry = {
        "url": url,
        "timestamp": timestamp,
        "_compressed": True,          # 标记：内容已压缩
        "_version": "1.4.8",          # 版本标记，便于将来迁移
    }

    # 结构化数据优先存储（不压缩，JSON 体积小）
    if parsed is not None:
        entry["parsed"] = parsed

    # 原始 HTML 压缩存储
    if content:
        entry["content"] = _compress(content)

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entry, f, ensure_ascii=False)
    except Exception as e:
        print(f"  缓存写入失败: {e}")


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
