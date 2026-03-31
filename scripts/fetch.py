#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HKJC 赛马分析工具 - 数据抓取模块

提供 HTTP 请求、Playwright 动态渲染抓取、马匹历史战绩和贴士指数获取功能。
"""

import re
import json
import os
import time
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from config import RACE_CARD_URL, TIPS_INDEX_URL
from cache import _cache_get, _cache_set, _classify_url


# ==============================================================================
# HTTP 请求
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


def fetch_url_with_playwright(url, timeout=30, force_refresh=False):
    """
    使用 Playwright 抓取需要 JS 渲染的页面内容。

    适用于：
    - 排位表页面 (racecard)：马匹数据通过 JS 动态加载
    - 其他使用 JavaScript 渲染内容的页面

    返回：
        HTML 字符串，或 None（失败时）
    """
    # 尝试读缓存
    if not force_refresh:
        cached = _cache_get(url)
        if cached is not None and 'horseid=' in cached.lower():
            print(f"  💾 缓存命中 [playwright]: {url[:80]}...")
            return cached

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ⚠️  Playwright 未安装，回退到普通 fetch")
        return fetch_url(url, timeout=timeout, force_refresh=force_refresh)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=timeout * 1000)
            page.wait_for_timeout(5000)  # 等待 JS 执行
            html = page.content()
            browser.close()

        print(f"  🌐 Playwright 获取 [racecard]: {url[:80]}...")

        # 验证是否获取到马匹数据
        if 'horseid=' not in html.lower():
            print(f"  ⚠️  Playwright 获取的页面无马匹数据，可能 JS 加载失败")

        # 写入缓存
        _cache_set(url, html)
        return html

    except Exception as e:
        print(f"  ⚠️  Playwright 获取失败: {e}，回退到普通 fetch")
        return fetch_url(url, timeout=timeout, force_refresh=True)


# ==============================================================================
# 马匹历史战绩
# ==============================================================================

def fetch_horse_history(horse_id: str, force_refresh: bool = False) -> dict:
    """
    抓取并解析指定马匹的历史战绩页面。

    参数：
        horse_id      : HKJC 马匹 ID，如 "HK_2021_G361"
        force_refresh : 忽略缓存强制重新抓取

    返回：parse_horse_history() 的结果字典；抓取失败时返回默认空结构。
    """
    from parse import parse_horse_history

    url = (
        "https://racing.hkjc.com/racing/information/Chinese/Horse/Horse.aspx"
        f"?HorseId={horse_id}"
    )
    html = fetch_url(url, timeout=20, force_refresh=force_refresh)
    if not html:
        return {"current_rating": 40, "history": []}
    return parse_horse_history(html)


# ==============================================================================
# 贴士指数
# ==============================================================================

def fetch_tips_index(force_refresh: bool = False) -> dict:
    """
    抓取并解析 HKJC 官方贴士指数页面（使用 Playwright 动态加载）。

    Tips Index URL: https://racing.hkjc.com/racing/chinese/tipsindex/tips_index.asp

    返回结构：
    {
        "tips": {
            "#马号": tips_index_value (float, 如 3.0, 16.5, 99 等)
        },
        "race_info": {
            "date": "01/04/2026",
            "venue": "沙田",
            "time": "6:45 PM",
            "track": "全天候跑道",
            "distance": "1200米",
            "condition": "好地",
            "rating_range": "040-000",
            "class": "第五班"
        },
        "last_updated": "HH:MM"
    }

    注意：HKJC 贴士指数是小数值格式（如 3.0, 16.5），代表该马的赔率预测。
    数值越低表示越被看好。
    """
    url = TIPS_INDEX_URL

    # 尝试从缓存读取
    cache_file = _cache_path_local(url)
    if not force_refresh and os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                entry = json.load(f)
            if time.time() - entry.get("timestamp", 0) < 30 * 60:  # 缓存30分钟
                print(f"  💾 缓存命中 [tips_index]: {url[:60]}...")
                return entry.get("content", {})
        except Exception:
            pass

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ⚠️  Playwright 未安装，使用静态解析方式")
        return _fetch_tips_index_static(url)

    tips = {}
    race_info = {}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000)
            page.wait_for_timeout(3000)  # 等待 JS 执行
            html = page.content()
            browser.close()

        print(f"  🌐 Playwright 获取 [tips_index]: {url[:60]}...")

        # 提取赛事信息
        race_m = re.search(
            r'(\d{2}/\d{2}/\d{4})\s+([^,]+),\s*([^,]+),\s*([^,]+),\s*"?([^,"]*)"?,\s*(\d+米),\s*([^,]+),\s*評分:\s*([^\s,]+),\s*賽事班次:\s*(.+)',
            html
        )
        if race_m:
            race_info = {
                "date": race_m.group(1),
                "venue": race_m.group(2).strip(),
                "time": race_m.group(3).strip(),
                "track": race_m.group(4).strip(),
                "distance": race_m.group(6),
                "condition": race_m.group(7).strip(),
                "rating_range": race_m.group(8),
                "class": race_m.group(9).strip(),
            }

        # 解析贴士指数表格
        td_pattern = re.compile(r'<td[^>]*>(.*?)</td>', re.DOTALL)
        tr_pattern = re.compile(r'<tr[^>]*>(.*?)</tr>', re.DOTALL)

        found_header = False
        for tr_m in tr_pattern.finditer(html):
            tr_content = tr_m.group(1)
            tds = td_pattern.findall(tr_content)
            clean_tds = [re.sub(r'<[^>]+>', '', td).strip().replace('&nbsp;', '') for td in tds]
            clean_tds = [t for t in clean_tds if t]

            if len(clean_tds) < 7:
                continue

            # 检测表头行
            if '馬號' in clean_tds[0] or '马号' in clean_tds[0]:
                found_header = True
                continue

            if not found_header:
                continue

            # 马号在第0列
            try:
                horse_no = int(clean_tds[0])
            except (ValueError, IndexError):
                continue

            # 初步贴士指数在第7列（索引从0开始）
            tips_raw = clean_tds[7] if len(clean_tds) > 7 else ""
            try:
                tips_value = float(tips_raw)
                if tips_value > 0:
                    tips[f"#{horse_no}"] = tips_value
            except (ValueError, IndexError):
                pass

        # 提取更新时间
        time_m = re.search(r'更新(?:时间)?[:：]?\s*(\d{1,2}:\d{2})', html)
        last_updated = time_m.group(1) if time_m else None

        result = {"tips": tips, "race_info": race_info, "last_updated": last_updated}

        # 写入缓存
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"url": url, "timestamp": time.time(), "content": result}, f, ensure_ascii=False)

        return result

    except Exception as e:
        print(f"  ⚠️  Playwright 获取失败: {e}，回退到静态解析")
        return _fetch_tips_index_static(url)


def _cache_path_local(url: str) -> str:
    """贴士指数缓存路径（独立函数）"""
    import hashlib
    from config import CACHE_DIR
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{url_hash}.json")


def _fetch_tips_index_static(url: str) -> dict:
    """
    静态解析方式获取贴士指数（备用，当 Playwright 不可用时使用）。

    使用 fetch_url 获取 HTML，然后用正则表达式解析。
    注意：HKJC 贴士指数页面是 JS 动态渲染，静态解析可能无法获取完整数据。
    """
    html = fetch_url(url, timeout=15, force_refresh=False)
    if not html:
        return {"tips": {}, "race_info": {}, "last_updated": None}

    tips = {}
    race_info = {}

    # 提取赛事信息（简化版）
    race_m = re.search(
        r'(\d{2}/\d{2}/\d{4})\s+([^,]+),\s*([^,]+),\s*(\d+米)',
        html
    )
    if race_m:
        race_info = {
            "date": race_m.group(1),
            "venue": race_m.group(2).strip(),
            "time": race_m.group(3).strip(),
            "distance": race_m.group(4),
        }

    # 解析表格数据
    td_pattern = re.compile(r'<td[^>]*>(.*?)</td>', re.DOTALL)
    tr_pattern = re.compile(r'<tr[^>]*>(.*?)</tr>', re.DOTALL)

    found_header = False
    for tr_m in tr_pattern.finditer(html):
        tr_content = tr_m.group(1)
        tds = td_pattern.findall(tr_content)
        clean_tds = [re.sub(r'<[^>]+>', '', td).strip().replace('&nbsp;', '') for td in tds]
        clean_tds = [t for t in clean_tds if t]

        if len(clean_tds) < 7:
            continue

        if '馬號' in clean_tds[0] or '马号' in clean_tds[0]:
            found_header = True
            continue

        if not found_header:
            continue

        try:
            horse_no = int(clean_tds[0])
        except (ValueError, IndexError):
            continue

        tips_raw = clean_tds[7] if len(clean_tds) > 7 else ""
        try:
            tips_value = float(tips_raw)
            if tips_value > 0:
                tips[f"#{horse_no}"] = tips_value
        except (ValueError, IndexError):
            pass

    time_m = re.search(r'更新(?:时间)?[:：]?\s*(\d{1,2}:\d{2})', html)
    last_updated = time_m.group(1) if time_m else None

    return {"tips": tips, "race_info": race_info, "last_updated": last_updated}
