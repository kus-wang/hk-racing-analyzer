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
from config import (
    RACE_CARD_URL,
    TIPS_INDEX_URL,
    LOCAL_RESULTS_URL,
    BETTING_ODDS_URL_TEMPLATE,
    CACHE_TTL,
    API_DEFAULT_ODDS_TYPES,
)
from cache import _cache_get, _cache_set, _classify_url, _cache_path
from api_client import get_race_data, get_race_odds_data



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


def _safe_int(value, default=0):
    """安全地将字符串/数字转换为 int。"""
    if value is None:
        return default
    digits = re.sub(r"[^\d-]", "", str(value)).strip()
    if not digits:
        return default
    try:
        return int(digits)
    except ValueError:
        return default



def _safe_float(value, default=0.0):
    """安全地将字符串/数字转换为 float。"""
    if value is None:
        return default
    cleaned = re.sub(r"[^\d.-]", "", str(value)).strip()
    if not cleaned:
        return default
    try:
        return float(cleaned)
    except ValueError:
        return default



def _build_horse_entry(
    horse_id: str,
    horse_name: str,
    horse_no: int,
    barrier: int,
    jockey_name: str,
    jockey_code: str,
    trainer_name: str,
    trainer_code: str,
    weight: float,
    current_rating: int,
    is_reserve: bool,
):
    """构造与 parse_race_entries() 一致的马匹结构。"""
    return {
        "id": horse_id,
        "name": horse_name,
        "no": horse_no,
        "barrier": barrier,
        "jockey": jockey_name,
        "jockey_code": jockey_code,
        "trainer": trainer_name,
        "trainer_code": trainer_code,
        "weight": weight,
        "current_rating": current_rating,
        "is_reserve": is_reserve,
        "final_odds": None,
        "opening_odds": None,
        "tips_index": None,
        "history": [],
        "history_same_condition_score": 40,
        "history_same_venue_score": 40,
        "class_fit_score": 50,
        "odds_value_score": 50,
        "odds_drift_score": 50,
        "sectional_score": 50,
        "jockey_score": 50,
        "trainer_score": 50,
        "barrier_score": 50,
        "tips_index_score": 50,
        "expert_score": 50,
        "total_score": 0,
        "probability": 0,
        "confidence": "⭐ 低",
        "longshot_alert": False,
    }



def fetch_race_entries_api(race_date: str, venue: str, race_no: int, force_refresh: bool = False) -> dict | None:
    """
    使用 HKJC GraphQL API 获取单场排位表，并转换为主流程使用的标准结构。

    返回：
        {
            "source": "api",
            "meeting": {...},
            "race": {...},
            "horses": [...]
        }
        或 None（失败时）
    """
    api_payload = get_race_data(
        race_date,
        venue,
        race_no,
        force_refresh=force_refresh,
        cache_ttl=CACHE_TTL["race_card"],
    )
    if not api_payload:
        return None

    race = api_payload.get("race") or {}
    meeting = api_payload.get("meeting") or {}
    runners = race.get("runners") or []
    if not runners:
        return None

    horses = []
    seen_ids = set()
    for runner in runners:
        horse_info = runner.get("horse") or {}
        jockey_info = runner.get("jockey") or {}
        trainer_info = runner.get("trainer") or {}

        horse_id = str(horse_info.get("id") or runner.get("id") or "").strip()
        horse_name = (
            runner.get("name_ch")
            or horse_info.get("name_ch")
            or runner.get("name_en")
            or horse_info.get("name_en")
            or ""
        ).strip()
        horse_no = _safe_int(runner.get("no"), 0)

        if not horse_id or not horse_name or not horse_no:
            continue
        if horse_id in seen_ids:
            continue
        seen_ids.add(horse_id)

        standby_no = str(runner.get("standbyNo") or "").strip()
        status_text = str(runner.get("status") or "").strip().upper()
        is_reserve = bool(standby_no) or status_text in {"R", "RESERVE", "STANDBY"}

        horses.append(_build_horse_entry(
            horse_id=horse_id,
            horse_name=horse_name,
            horse_no=horse_no,
            barrier=_safe_int(runner.get("barrierDrawNumber"), 0),
            jockey_name=(jockey_info.get("name_ch") or jockey_info.get("name_en") or "").strip(),
            jockey_code=str(jockey_info.get("code") or "").strip(),
            trainer_name=(trainer_info.get("name_ch") or trainer_info.get("name_en") or "").strip(),
            trainer_code=str(trainer_info.get("code") or "").strip(),
            weight=_safe_float(runner.get("handicapWeight"), 0.0),
            current_rating=_safe_int(runner.get("currentRating"), 40),
            is_reserve=is_reserve,
        ))

    if not horses:
        return None

    return {
        "source": "api",
        "meeting": meeting,
        "race": race,
        "horses": horses,
    }



def fetch_url_with_playwright(
    url,
    timeout=30,
    force_refresh=False,
    use_api_first=True,
    race_date=None,
    venue=None,
    race_no=None,
):
    """
    获取排位表数据：优先使用 HKJC API，失败后降级到 Playwright 页面抓取。

    返回：
        - API 成功：dict（含 horses/race/meeting/source）
        - 页面抓取成功：HTML 字符串
        - 失败：None
    """
    if use_api_first and race_date and venue and race_no is not None:
        api_payload = fetch_race_entries_api(
            race_date=race_date,
            venue=venue,
            race_no=race_no,
            force_refresh=force_refresh,
        )
        if api_payload:
            print(f"  🌐 HKJC API 获取 [racecard]: {race_date} {venue} 第{race_no}场")
            return api_payload
        print("  ⚠️  HKJC API 未返回有效排位表，回退到 Playwright")

    if not force_refresh:
        cached = _cache_get(url)
        if isinstance(cached, str) and 'horseid=' in cached.lower():
            print(f"  💾 缓存命中 [playwright]: {url[:80]}...")
            return cached

    try:
        page = PlaywrightManager.new_page()
        if page is None:
            print("  ⚠️  Playwright 不可用，回退到普通 fetch")
            return fetch_url(url, timeout=timeout, force_refresh=force_refresh)

        page.goto(url, timeout=timeout * 1000)
        page.wait_for_timeout(5000)
        html = page.content()

        print(f"  🌐 Playwright 获取 [racecard]: {url[:80]}...")

        if 'horseid=' not in html.lower():
            print("  ⚠️  Playwright 获取的页面无马匹数据，可能 JS 加载失败")

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
    cached_or_html = fetch_url(url, timeout=20, force_refresh=force_refresh)
    if not cached_or_html:
        return {"current_rating": 40, "history": []}

    # v1.4.9 fix: 若缓存命中且已含 parsed dict，直接返回，避免 re.search 报 TypeError
    if isinstance(cached_or_html, dict):
        return cached_or_html

    html = cached_or_html

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

    # 尝试从缓存读取（使用 _cache_get 获取已解压的 content）
    if not force_refresh:
        try:
            cached = _cache_get(url)
            if cached is not None:
                # _cache_get 已处理压缩和 parsed 字段，应返回 dict
                if isinstance(cached, dict):
                    print(f"  💾 缓存命中 [tips_index]: {url[:60]}...")
                    return cached
                # 兜底：若返回了非 dict（旧缓存），当无数据处理
                print(f"  ⚠️  缓存类型异常 ({type(cached).__name__})，重新抓取")
                # fall through to fresh fetch
        except Exception:
            pass

    tips = {}  # 初始化贴士字典
    race_info = {}  # 初始化 race_info（避免正则不匹配时 UnboundLocalError）
    cache_file = _cache_path(url)  # 保留以供缓存写入

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

def _normalize_single_odds_key(comb_string: str) -> str | None:
    """将单马号组合转换为 #N 形式。"""
    no = _safe_int(comb_string, 0)
    return f"#{no}" if no > 0 else None



def _normalize_combo_odds_key(comb_string: str) -> str | None:
    """将组合马号转换为 N,N 或 N,N,N 形式。"""
    nums = [_safe_int(part, 0) for part in str(comb_string).split(",")]
    nums = [str(n) for n in nums if n > 0]
    return ",".join(nums) if nums else None



def _convert_api_odds_result(pm_pools: list, race_no: int, venue: str, date: str) -> dict:
    """将 HKJC API 的赔率池结构转换为现有赔率 dict。"""
    result = _empty_odds_result(race_no=race_no, venue=venue, date=date)
    result["source"] = "hkjc-api"

    pool_map = {
        "WIN": ("win", _normalize_single_odds_key),
        "PLA": ("place", _normalize_single_odds_key),
        "QIN": ("quinella", _normalize_combo_odds_key),
        "QPL": ("quinella_place", _normalize_combo_odds_key),
        "TRI": ("trio", _normalize_combo_odds_key),
    }

    for pool in pm_pools or []:
        odds_type = str(pool.get("oddsType") or "").upper().strip()
        target = pool_map.get(odds_type)
        if not target:
            continue

        field_name, key_builder = target
        for node in pool.get("oddsNodes") or []:
            odds_value = _safe_float(node.get("oddsValue"), 0.0)
            if odds_value <= 0:
                continue
            combo_key = key_builder(node.get("combString") or "")
            if combo_key:
                result[field_name][combo_key] = odds_value

    has_any_odds = any([
        result["win"],
        result["place"],
        result["quinella"],
        result["quinella_place"],
        result["trio"],
    ])
    result["status"] = "ok" if has_any_odds else "unavailable"
    return result



def fetch_race_odds(
    race_date: str,
    venue: str,
    race_no: int,
    force_refresh: bool = False,
    use_api_first: bool = True,
) -> dict:
    """
    抓取 HKJC 投注赔率数据：优先使用 API，失败后回退到 Playwright 页面。
    """
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
    odds_cache_url = f"odds_{date_iso}_{venue}_{race_no}"

    if not force_refresh:
        cached = _cache_get(url, cache_key=odds_cache_url)
        if isinstance(cached, dict) and cached.get("status"):
            print(f"  💾 缓存命中 [odds]: {url[:70]}...")
            return cached

    if use_api_first:
        api_payload = get_race_odds_data(
            race_date,
            venue,
            race_no,
            odds_types=list(API_DEFAULT_ODDS_TYPES),
            force_refresh=force_refresh,
            cache_ttl=CACHE_TTL["odds"],
        )
        if api_payload is not None:
            api_result = _convert_api_odds_result(
                api_payload.get("pmPools") or [],
                race_no=race_no,
                venue=venue,
                date=date_iso,
            )
            _save_odds_cache(odds_cache_url, api_result)
            if api_result.get("status") == "ok":
                print(f"  🌐 HKJC API 获取 [odds]: {date_iso} {venue} 第{race_no}场")
            else:
                print(f"  ℹ️  HKJC API 已响应，但当前无可用赔率（可能未开盘）")
            return api_result

        print("  ⚠️  HKJC API 赔率获取失败，回退到 Playwright")

    result = _fetch_odds_with_playwright(url, race_no=race_no, venue=venue, date=date_iso)
    _save_odds_cache(odds_cache_url, result)
    return result


def _fetch_odds_with_playwright(url: str, race_no: int, venue: str, date: str) -> dict:

    """
    使用 Playwright 提取 HKJC 赔率页面的投注数据。

    赔率页面通过 JS 动态渲染，直接用 HTTP 请求只能拿到空壳 HTML。
    本函数通过 Playwright 获取渲染后的页面内容，再从 DOM 表格直接提取数据。

    返回结构同 fetch_race_odds()。
    """
    import re as _re

    def _empty():
        return {
            "race_no": race_no, "venue": venue, "date": date,
            "win": {}, "place": {}, "quinella": {}, "trio": {},
            "quinella_place": {}, "last_updated": None,
            "source": "bet.hkjc.com", "status": "unavailable",
        }

    try:
        page = PlaywrightManager.new_page()
        if page is None:
            print(f"  ⚠️  Playwright 不可用，赔率抓取失败")
            return _empty()

        print(f"  🌐 Playwright 获取 [odds]: {url[:70]}...")
        page.goto(url, timeout=30000)
        page.wait_for_timeout(6000)  # 等待 JS 动态渲染完成

        # ── 方案A：直接从 DOM 表格提取独赢/位置赔率 ───────────────────────
        # HKJC 赔率页面结构：<table> 包含马号/马名/档位/骑师/独赢/位置 等列
        win_odds = {}
        place_odds = {}

        tables = page.query_selector_all("table")
        for tbl in tables:
            rows = tbl.query_selector_all("tr")
            header_cols = None  # 列索引映射

            for row in rows:
                cells = row.query_selector_all("td")
                if not cells:
                    continue

                # 提取单元格文本
                cell_texts = []
                for c in cells:
                    t = c.inner_text().strip()
                    # 清理多余的空白
                    t = _re.sub(r'\s+', ' ', t)
                    cell_texts.append(t)

                text_all = " ".join(cell_texts)

                # 检测表头行（含有马号/独赢/位置关键字）
                if header_cols is None:
                    if any(k in text_all for k in ['馬號', '馬号', '马号']):
                        header_cols = {}
                        for idx, ct in enumerate(cell_texts):
                            ct_up = ct.upper()
                            if any(k in ct_up for k in ['馬號', '馬号', 'HORSE NO', 'NO.']):
                                header_cols[idx] = 'horse_no'
                            elif '獨贏' in ct or 'WIN' in ct_up:
                                header_cols[idx] = 'win'
                            elif '位置' in ct or 'PLACE' in ct_up:
                                header_cols[idx] = 'place'
                    continue

                # 数据行：从已知的列索引提取马号和赔率
                if header_cols:
                    horse_no = None
                    win_val = None
                    place_val = None

                    for idx, ct in enumerate(cell_texts):
                        col_type = header_cols.get(idx)
                        if col_type == 'horse_no':
                            # 马号列：提取纯数字
                            m = _re.search(r'^(\d+)$', ct.strip())
                            if m:
                                horse_no = m.group(1)
                        elif col_type == 'win':
                            # 独赢赔率：提取数字（含小数点）
                            m = _re.search(r'^([\d.]+)$', ct.strip())
                            if m:
                                try:
                                    win_val = float(m.group(1))
                                except ValueError:
                                    pass
                        elif col_type == 'place':
                            # 位置赔率
                            m = _re.search(r'^([\d.]+)$', ct.strip())
                            if m:
                                try:
                                    place_val = float(m.group(1))
                                except ValueError:
                                    pass

                    if horse_no and win_val:
                        win_odds[f"#{horse_no}"] = win_val
                    if horse_no and place_val:
                        place_odds[f"#{horse_no}"] = place_val

        # 判断是否成功获取到赔率数据
        if not win_odds:
            # ── 方案B：回退到解析 page.content() 的 HTML ────────────────
            print(f"  ⚠️  DOM 表格提取失败，尝试解析渲染后 HTML...")
            html = page.content()
            from parse import parse_race_odds
            parsed = parse_race_odds(html, race_no=race_no, venue=venue, date=date)
            if parsed.get("status") == "ok" and parsed.get("win"):
                return parsed
            print(f"  ⚠️  赔率页面 JS 渲染失败或无数据，返回空")
            return _empty()

        print(f"  ✅ 赔率已获取 | 独赢:{len(win_odds)} 位置:{len(place_odds)}")
        return {
            "race_no": race_no,
            "venue": venue,
            "date": date,
            "win": win_odds,
            "place": place_odds,
            "quinella": {},
            "trio": {},
            "quinella_place": {},
            "last_updated": None,
            "source": "bet.hkjc.com",
            "status": "ok",
        }

    except Exception as e:
        print(f"  ⚠️  Playwright 赔率抓取失败: {e}，返回空数据")
        return _empty()


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
