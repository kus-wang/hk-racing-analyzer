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
import atexit
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from config import RACE_CARD_URL, TIPS_INDEX_URL, LOCAL_RESULTS_URL, BETTING_ODDS_URL_TEMPLATE, CACHE_TTL
from cache import _cache_get, _cache_set, _classify_url, _cache_path


# ==============================================================================
# Playwright 单例管理（全局复用浏览器实例）
# ==============================================================================

class PlaywrightManager:
    """
    Playwright 单例管理器，避免重复启动/关闭浏览器实例。

    使用方式：
        browser, page = PlaywrightManager.get_page()
        page.goto(url)
        html = page.content()
        # 不要关闭！由管理器统一管理生命周期
    """
    _instance = None
    _browser = None
    _playwright = None
    _page_count = 0
    _initialized = False

    @classmethod
    def _init(cls):
        """初始化 Playwright（延迟加载，仅在首次使用时）"""
        if cls._initialized:
            return
        try:
            from playwright.sync_api import sync_playwright
            cls._playwright = sync_playwright().start()
            cls._browser = cls._playwright.chromium.launch(headless=True)
            cls._initialized = True
            print("  🚀 Playwright 浏览器实例已启动（全局复用）")
            # 注册退出时清理
            atexit.register(cls.cleanup)
        except ImportError:
            print("  ⚠️  Playwright 未安装")
            raise

    @classmethod
    def get_browser(cls):
        """获取浏览器实例"""
        if not cls._initialized:
            cls._init()
        return cls._browser

    @classmethod
    def new_page(cls):
        """创建新页面（复用浏览器实例）"""
        browser = cls.get_browser()
        if browser is None:
            return None
        page = browser.new_page()
        cls._page_count += 1
        return page

    @classmethod
    def cleanup(cls):
        """清理 Playwright 资源（进程退出时自动调用）"""
        if cls._browser:
            try:
                cls._browser.close()
                print(f"  🔒 Playwright 浏览器实例已关闭（共创建 {cls._page_count} 个页面）")
            except Exception:
                pass
            cls._browser = None
        if cls._playwright:
            try:
                cls._playwright.stop()
            except Exception:
                pass
            cls._playwright = None
        cls._initialized = False


# ==============================================================================
# HTTP 请求
# ==============================================================================

def fetch_url(url, timeout=15, force_refresh=False, max_retries=3):
    """
    抓取 URL 内容，自动读写磁盘缓存。

    force_refresh=True  → 跳过缓存，强制重新请求并刷新缓存。
    max_retries         → 网络请求失败时的最大重试次数（默认3次）
    """
    # 1. 尝试读缓存
    if not force_refresh:
        cached = _cache_get(url)
        if cached is not None:
            ttl_key = _classify_url(url)
            print(f"  💾 缓存命中 [{ttl_key}]: {url[:80]}...")
            return cached

    # 2. 发起网络请求（带重试机制）
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
        "Referer": "https://racing.hkjc.com/",
    }

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout) as response:
                content = response.read().decode("utf-8", errors="ignore")
            # 3. 写入缓存
            _cache_set(url, content)
            ttl_key = _classify_url(url)
            if attempt > 1:
                print(f"  🌐 网络请求 [第{attempt}次重试成功, {ttl_key}]: {url[:80]}...")
            else:
                print(f"  🌐 网络请求 [{ttl_key}]: {url[:80]}...")
            return content
        except (URLError, HTTPError) as e:
            last_error = e
            if attempt < max_retries:
                wait_time = 2 ** (attempt - 1)  # 指数退避: 1s, 2s, 4s
                print(f"  ⚠️  抓取失败 [第{attempt}次]: {url[:60]}... ({e})，{wait_time}秒后重试...")
                time.sleep(wait_time)
            else:
                print(f"  ⚠️  抓取失败 [已重试{max_retries}次]: {url[:60]}... ({e})")
                return None


def fetch_url_with_playwright(url, timeout=30, force_refresh=False):
    """
    使用 Playwright 抓取需要 JS 渲染的页面内容。

    适用于：
    - 排位表页面 (racecard)：马匹数据通过 JS 动态加载
    - 其他使用 JavaScript 渲染内容的页面

    返回：
        HTML 字符串，或 None（失败时）

    注意：浏览器实例全局复用，无需手动关闭页面。
    """
    # 尝试读缓存
    if not force_refresh:
        cached = _cache_get(url)
        if cached is not None and 'horseid=' in cached.lower():
            print(f"  💾 缓存命中 [playwright]: {url[:80]}...")
            return cached

    try:
        page = PlaywrightManager.new_page()
        if page is None:
            print("  ⚠️  Playwright 不可用，回退到普通 fetch")
            return fetch_url(url, timeout=timeout, force_refresh=force_refresh)

        page.goto(url, timeout=timeout * 1000)
        page.wait_for_timeout(5000)  # 等待 JS 执行
        html = page.content()
        # 注意：不关闭页面，由管理器统一复用

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

    # 解析并更新缓存（v1.4.8: 同时存储结构化数据）
    parsed = parse_horse_history(html)
    _cache_set(url, html, parsed=parsed)
    return parsed


# ==============================================================================
# 赛果
# ==============================================================================

def fetch_race_results(date: str, venue: str = "ST", force_refresh: bool = False) -> dict:
    """
    抓取指定日期+场地的赛果页面 HTML。

    参数：
        date          : 日期字符串，格式 YYYY/MM/DD（如 "2026/04/01"）
        venue         : 场地代码，ST（沙田）或 HV（跑马地）
        force_refresh : 忽略缓存强制重新抓取

    返回：
        原始 HTML 字符串；抓取失败时返回空字符串。
    """
    # HKJC LocalResults.aspx 接受 MeetingDate 参数，格式为 DD/MM/YYYY
    # 场地通过页面内筛选，查询时不带 venue 参数，由 HTML 内嵌
    from datetime import datetime as _dt
    try:
        dt = _dt.strptime(date, "%Y/%m/%d")
    except (ValueError, TypeError):
        dt = _dt.now()

    date_param = dt.strftime("%d/%m/%Y")
    url = f"{LOCAL_RESULTS_URL}?MeetingDate={date_param}"

    html = fetch_url(url, timeout=20, force_refresh=force_refresh)
    if not html:
        return ""

    # v1.4.8: 解析后同时缓存结构化数据（节省后续重复解析的开销）
    from parse import parse_race_results
    parsed = parse_race_results(html)
    _cache_set(url, html, parsed=parsed)
    return html


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
    cache_file = _cache_path(url)
    if not force_refresh and os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                entry = json.load(f)
            if time.time() - entry.get("timestamp", 0) < 30 * 60:  # 缓存30分钟
                print(f"  💾 缓存命中 [tips_index]: {url[:60]}...")
                return entry.get("content", {})
        except Exception:
            pass

    tips = {}  # 初始化贴士字典

    try:
        page = PlaywrightManager.new_page()
        if page is None:
            print("  ⚠️  Playwright 不可用，使用静态解析方式")
            return _fetch_tips_index_static(url)

        page.goto(url, timeout=30000)
        page.wait_for_timeout(3000)  # 等待 JS 执行
        html = page.content()
        # 注意：不关闭页面，由管理器统一复用

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


# ==============================================================================
# 投注赔率
# ==============================================================================

def fetch_race_odds(
    race_date: str,
    venue: str,
    race_no: int,
    force_refresh: bool = False
) -> dict:
    """
    抓取 HKJC 投注赔率页面并解析各投注方式的赔率数据。

    URL 格式：https://bet.hkjc.com/ch/racing/wp/{YYYY-MM-DD}/{VENUE}/{RACE_NO}
    例如：  https://bet.hkjc.com/ch/racing/wp/2026-04-06/ST/1

    参数：
        race_date    : 日期字符串，格式 YYYY/MM/DD（如 "2026/04/06"）
        venue        : 场地代码，ST（沙田）或 HV（跑马地）
        race_no      : 场次号
        force_refresh: 忽略缓存强制重新抓取

    返回结构：
    {
        "race_no": 1,
        "venue": "ST",
        "date": "2026-04-06",
        "win":       {"#1": 8.5, "#2": 12.0, ...},           # 独赢赔率
        "place":     {"#1": 2.8, "#2": 3.5, ...},           # 位置赔率
        "quinella":  {"1,2": 45.0, "1,3": 52.0, ...},       # 连赢赔率
        "trio":      {"1,2,3": 180.0, ...},                 # 三重彩赔率
        "quinella_place": {"1,2": 18.0, ...},               # 位置Q赔率
        "last_updated": "14:30",
        "source":    "bet.hkjc.com",
    }

    注：若赛事未开盘（赛前），所有赔率字段为空字典 {}
    """
    # 日期格式转换 YYYY/MM/DD → YYYY-MM-DD
    from datetime import datetime as _dt
    try:
        dt = _dt.strptime(race_date, "%Y/%m/%d")
    except (ValueError, TypeError):
        dt = _dt.now()
    date_iso = dt.strftime("%Y-%m-%d")

    url = BETTING_ODDS_URL_TEMPLATE.format(
        date=date_iso,
        venue=venue,
        race_no=race_no
    )

    # 赔率页面使用独立缓存 key，避免与排位表混淆
    odds_cache_url = f"odds_{date_iso}_{venue}_{race_no}"

    # v1.4.8: 使用统一缓存接口，支持自定义 key 和结构化数据
    if not force_refresh:
        cached = _cache_get(url, cache_key=odds_cache_url)
        if cached is not None:
            # _cache_get 已处理 TTL，在 parsed 模式下直接返回结构化数据
            if isinstance(cached, dict) and cached.get("status"):
                print(f"  💾 缓存命中 [odds]: {url[:70]}...")
                return cached

    # 抓取 HTML
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
        "Referer": "https://bet.hkjc.com/",
    }

    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=20) as response:
            html = response.read().decode("utf-8", errors="ignore")
        print(f"  🌐 获取赔率页面: {url}")
    except Exception as e:
        print(f"  ⚠️  赔率页面抓取失败: {e}，返回空数据")
        result = _empty_odds_result(race_no, venue, date_iso)
        _save_odds_cache(odds_cache_url, result)
        return result

    # 解析赔率数据
    from parse import parse_race_odds
    result = parse_race_odds(html, race_no=race_no, venue=venue, date=date_iso)

    # 写入缓存
    _save_odds_cache(odds_cache_url, result)
    return result


def _empty_odds_result(race_no: int, venue: str, date: str) -> dict:
    """返回空赔率数据结构（赛事未开盘或抓取失败时使用）"""
    return {
        "race_no": race_no,
        "venue": venue,
        "date": date,
        "win": {},
        "place": {},
        "quinella": {},
        "trio": {},
        "quinella_place": {},
        "last_updated": None,
        "source": "bet.hkjc.com",
        "status": "unavailable",
    }


def _save_odds_cache(cache_key: str, content: dict):
    """
    将赔率结果写入缓存文件（v1.4.8: 使用统一 _cache_set）。

    赔率数据本身就是结构化 dict，直接作为 parsed 存储，
    不再额外存储原始 HTML（赔率页面 JSON 无需保留原文）。
    """
    _cache_set(cache_key, "", parsed=content)
