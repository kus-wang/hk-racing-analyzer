#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
赛马分析工具 — 调度器缓存模块
=============================
职责：HTTP 缓存管理 + HTML 抓取。
由 daily_scheduler.py 专用，不对外暴露。

缓存键格式：md5(url) → .cache/<hash>.json
TTL 由调用方指定（秒）。
"""

import os
import json
import time
import hashlib
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError


# ──────────────────────────────────────────────────────────────
# 路径
# ──────────────────────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR  = os.path.dirname(_SCRIPT_DIR)
CACHE_DIR   = os.path.join(_SKILL_DIR, ".cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# ──────────────────────────────────────────────────────────────
# 缓存操作
# ──────────────────────────────────────────────────────────────

def _cache_path(key: str) -> str:
    h = hashlib.md5(key.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{h}.json")


def cache_get(key: str, ttl: int) -> dict | None:
    """
    读取缓存，key 未过期则返回缓存数据，否则返回 None。
    缓存数据格式：{"html": "...", "url": "...", "ts": float}
    """
    p = _cache_path(key)
    if not os.path.exists(p):
        return None
    if time.time() - os.path.getmtime(p) > ttl:
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def cache_set(key: str, data: dict):
    """写入缓存。"""
    p = _cache_path(key)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ──────────────────────────────────────────────────────────────
# HTML 抓取（带缓存）
# ──────────────────────────────────────────────────────────────

def fetch_html(url: str, cache_key: str = None, ttl: int = None) -> str:
    """
    抓取 HTML 页面，支持缓存。

    Args:
        url:        目标 URL
        cache_key:  缓存键（省略则不缓存）
        ttl:        缓存有效期（秒），省略则不使用缓存

    Returns:
        HTML 字符串，失败返回空字符串。
    """
    from daily_scheduler import log  # 避免循环导入

    if cache_key and ttl:
        cached = cache_get(cache_key, ttl)
        if cached:
            return cached.get("html", "")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        if cache_key:
            cache_set(cache_key, {"html": html, "url": url, "ts": time.time()})
        return html
    except Exception as e:
        log(f"  ⚠ 抓取失败：{url}  ({e})")
        return ""
