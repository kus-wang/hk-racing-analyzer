#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HKJC 赛马分析工具 - API 客户端模块

职责：
1. 通过 subprocess 调用 hkjc_api_client.js
2. 统一处理 API 节流、重试、超时
3. 将 API 原始 JSON 以结构化 parsed 格式写入现有缓存体系
4. 为上层模块提供 meetings / race / odds 三类调用
"""

import json
import subprocess
import sys
import threading
import time
from datetime import datetime


from cache import _cache_path, _cache_set
from config import (
    API_CLIENT_SCRIPT,
    API_DEFAULT_ODDS_TYPES,
    API_MAX_ATTEMPTS,
    API_NODE_RUNTIME,
    API_REQUEST_INTERVAL_SECONDS,
    API_RETRY_DELAY_SECONDS,
    API_TIMEOUT_SECONDS,
)


_RATE_LIMIT_LOCK = threading.Lock()
_LAST_REQUEST_AT = 0.0


def _configure_console_output():
    """避免 Windows 控制台在输出 emoji/特殊字符时抛出编码异常。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(errors="replace")
            except Exception:
                pass


def _log(message: str):
    """安全输出日志，编码不兼容时自动降级替换字符。"""
    text = str(message)
    try:
        print(text)
    except UnicodeEncodeError:
        stream = sys.stdout
        encoding = getattr(stream, "encoding", None) or "utf-8"
        safe_text = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        if hasattr(stream, "buffer"):
            stream.buffer.write((safe_text + "\n").encode(encoding, errors="replace"))
            stream.flush()
        else:
            print(safe_text.encode("ascii", errors="replace").decode("ascii"))


_configure_console_output()


def _normalize_date(date_str: str | None) -> str | None:

    """将 YYYY/MM/DD 或 YYYY-MM-DD 统一转换为 YYYY-MM-DD。"""
    if not date_str:
        return None

    raw = str(date_str).strip().replace("/", "-")
    try:
        return datetime.strptime(raw, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return raw


def _read_cached_parsed(cache_key: str, ttl: int):
    """读取指定缓存键的 parsed 数据。"""
    if not cache_key or not ttl:
        return None

    path = _cache_path(cache_key)
    try:
        with open(path, "r", encoding="utf-8") as f:
            entry = json.load(f)
    except Exception:
        return None

    age = time.time() - entry.get("timestamp", 0)
    if age > ttl:
        return None

    parsed = entry.get("parsed")
    return parsed if isinstance(parsed, dict) else None


def _respect_rate_limit():
    """控制 API 请求频率，避免过于频繁。"""
    global _LAST_REQUEST_AT

    with _RATE_LIMIT_LOCK:
        now = time.time()
        elapsed = now - _LAST_REQUEST_AT
        if elapsed < API_REQUEST_INTERVAL_SECONDS:
            time.sleep(API_REQUEST_INTERVAL_SECONDS - elapsed)
        _LAST_REQUEST_AT = time.time()


def _build_cache_key(command: str, date: str | None, venue: str | None, race_no: int | None, odds_types: list[str] | None) -> str:
    parts = ["api", command]
    if date:
        parts.append(date)
    if venue:
        parts.append(str(venue).upper())
    if race_no is not None:
        parts.append(f"R{int(race_no)}")
    if odds_types:
        parts.append("-".join(odds_types))
    return "_".join(parts)


def _build_cache_url(command: str, date: str | None, venue: str | None, race_no: int | None, odds_types: list[str] | None) -> str:
    params = []
    if date:
        params.append(f"date={date}")
    if venue:
        params.append(f"venue={str(venue).upper()}")
    if race_no is not None:
        params.append(f"race={int(race_no)}")
    if odds_types:
        params.append(f"types={','.join(odds_types)}")

    if command in {"meetings", "race"}:
        base = "api://racecard"
    else:
        base = "api://odds"

    suffix = f"/{command}" if command else ""
    query = f"?{'&'.join(params)}" if params else ""
    return f"{base}{suffix}{query}"


def call_hkjc_api(
    command: str,
    *,
    date: str | None = None,
    venue: str | None = None,
    race_no: int | None = None,
    odds_types: list[str] | None = None,
    force_refresh: bool = False,
    cache_ttl: int | None = None,
):
    """
    调用 Node.js API bridge，返回 result 字段。

    返回：
        dict | None
    """
    date_norm = _normalize_date(date)
    venue_norm = str(venue).upper() if venue else None
    odds_types = odds_types or []

    cache_key = _build_cache_key(command, date_norm, venue_norm, race_no, odds_types)
    cache_url = _build_cache_url(command, date_norm, venue_norm, race_no, odds_types)

    if not force_refresh and cache_ttl:
        cached = _read_cached_parsed(cache_key, cache_ttl)
        if cached is not None:
            _log(f"  💾 缓存命中 [api:{command}]: {cache_key}")
            return cached


    cmd = [API_NODE_RUNTIME, API_CLIENT_SCRIPT, command]
    if date_norm:
        cmd += ["--date", date_norm]
    if venue_norm:
        cmd += ["--venue", venue_norm]
    if race_no is not None:
        cmd += ["--race", str(int(race_no))]
    if odds_types:
        cmd += ["--types", ",".join(odds_types)]

    last_error = None
    for attempt in range(1, API_MAX_ATTEMPTS + 1):
        try:
            _respect_rate_limit()
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=API_TIMEOUT_SECONDS,
            )

            raw_output = (proc.stdout or "").strip()
            if not raw_output:
                raw_output = (proc.stderr or "").strip()
            if not raw_output:
                raise RuntimeError("API 无输出")

            payload = json.loads(raw_output)
            if not payload.get("ok"):
                raise RuntimeError(payload.get("error") or "API 调用失败")

            result = payload.get("result")
            if not isinstance(result, dict):
                raise RuntimeError("API 返回格式异常")

            _cache_set(cache_key, "", parsed=result)
            return result

        except Exception as exc:
            last_error = exc
            if attempt < API_MAX_ATTEMPTS:
                _log(f"  ⚠️  API 调用失败 [第{attempt}次]: {exc}，{API_RETRY_DELAY_SECONDS:.1f}秒后重试...")
                time.sleep(API_RETRY_DELAY_SECONDS)
            else:
                _log(f"  ⚠️  API 调用失败 [已尝试{API_MAX_ATTEMPTS}次]: {exc}")


    return None


def get_meetings(date: str, venue: str | None = None, force_refresh: bool = False, cache_ttl: int | None = None):
    return call_hkjc_api(
        "meetings",
        date=date,
        venue=venue,
        force_refresh=force_refresh,
        cache_ttl=cache_ttl,
    )


def get_race_data(date: str, venue: str, race_no: int, force_refresh: bool = False, cache_ttl: int | None = None):
    return call_hkjc_api(
        "race",
        date=date,
        venue=venue,
        race_no=race_no,
        force_refresh=force_refresh,
        cache_ttl=cache_ttl,
    )


def get_race_odds_data(
    date: str,
    venue: str,
    race_no: int,
    odds_types: list[str] | None = None,
    force_refresh: bool = False,
    cache_ttl: int | None = None,
):
    return call_hkjc_api(
        "odds",
        date=date,
        venue=venue,
        race_no=race_no,
        odds_types=odds_types or list(API_DEFAULT_ODDS_TYPES),
        force_refresh=force_refresh,
        cache_ttl=cache_ttl,
    )
