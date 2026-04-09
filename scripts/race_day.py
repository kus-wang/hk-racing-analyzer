#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
赛马分析工具 — 赛马日检测模块
============================
职责：检测指定日期是否为赛马日，返回场地和场次数。
由 daily_scheduler.py 调用。
"""

import re

from api_client import get_meetings
from config import CACHE_TTL
from scheduler_cache import fetch_html

# HKJC URL
HKJC_BASE = "https://racing.hkjc.com"
RACE_DATE_URL = HKJC_BASE + "/racing/information/Chinese/Racing/RaceCard.aspx"

# 缓存 TTL（秒）
CACHE_SECONDS = CACHE_TTL["race_card"]
VENUE_NAME_MAP = {"ST": "沙田", "HV": "跑马地"}



def _parse_total_races_from_api(meeting: dict) -> int:
    """从 API meeting 对象中提取总场次数。"""
    total = meeting.get("totalNumberOfRace")
    if total:
        try:
            return int(total)
        except (TypeError, ValueError):
            pass

    races = meeting.get("races") or []
    race_nos = [int(r.get("no")) for r in races if str(r.get("no") or "").isdigit()]
    return max(race_nos) if race_nos else 0



def _detect_race_day_by_api(date_str: str):
    """
    优先用 HKJC API 检测赛马日。

    重要：HKJC GraphQL raceMeetings API 有时会忽略 date 参数，返回"下一个可用赛事"。
    因此在返回前，会用第一场的 postTime 与目标日期进行严格校验。
    """
    """优先用 HKJC API 检测赛马日。"""
    payload = get_meetings(date_str, force_refresh=False, cache_ttl=CACHE_SECONDS)
    if not payload:
        return None

    meetings = payload.get("raceMeetings") or payload.get("activeMeetings") or []
    if not meetings:
        return None

    for meeting in meetings:
        venue_code = (
            str(meeting.get("venueCode") or "").upper().strip()
            or str((meeting.get("raceCourse") or {}).get("displayCode") or "").upper().strip()
        )
        if venue_code not in VENUE_NAME_MAP:
            continue

        # ── 关键校验：API 有时会忽略 date 参数，用 postTime 校验 ──
        races = meeting.get("races") or []
        if races:
            first_post_time = races[0].get("postTime", "")
            # postTime 格式：2026-04-12T12:30:00+08:00，截取日期部分
            post_date = first_post_time[:10]  # "YYYY-MM-DD"
            # 将目标日期 "YYYY/MM/DD" 转为 "YYYY-MM-DD" 进行比较
            target_iso = date_str.replace("/", "-")
            if post_date != target_iso:
                # API 返回的赛事不在目标日期，跳过
                continue

        total_races = _parse_total_races_from_api(meeting)
        if total_races <= 0:
            continue

        return {
            "date": date_str,
            "venue": venue_code,
            "venue_name": VENUE_NAME_MAP.get(venue_code, venue_code),
            "total_races": total_races,
        }

    return None



def detect_race_day(date_str: str) -> dict | None:
    """
    检测指定日期（YYYY/MM/DD）是否为赛马日。

    Returns:
        {"date": ..., "venue": "ST"|"HV", "venue_name": ..., "total_races": N}
        或 None（非赛马日）。
    """
    from daily_scheduler import log

    log(f"🔍 检测 {date_str} 是否为赛马日...")

    api_result = _detect_race_day_by_api(date_str)
    if api_result:
        log(
            f"  ✅ {date_str} 是赛马日！场地：{api_result['venue_name']}，"
            f"共 {api_result['total_races']} 场（来源：HKJC API）"
        )
        return api_result

    log("  ℹ️  HKJC API 未确认赛事，回退到页面检测...")

    for venue_code, venue_name in [("ST", "沙田"), ("HV", "跑马地")]:
        url = f"{RACE_DATE_URL}?RaceDate={date_str}&Venue={venue_code}&RaceNo=1"
        ckey = f"racecard_{date_str}_{venue_code}"
        html = fetch_html(url, ckey, CACHE_SECONDS)

        if not html:
            continue

        if "没有赛事资料" in html or "没有相关资料" in html or "No Race Information" in html:
            continue
        if "RaceNo" not in html and "马名" not in html and "HorseNo" not in html:
            continue

        actual_venues = re.findall(r"Racecourse=(ST|HV)", html)
        if actual_venues and actual_venues[0] != venue_code:
            log(f"  ⚠️ 请求 {venue_name}，但页面实际为 {actual_venues[0]}，跳过")
            continue

        total_races = _parse_total_races(html)
        if total_races and total_races > 0:
            log(f"  ✅ {date_str} 是赛马日！场地：{venue_name}，共 {total_races} 场（来源：页面）")
            return {
                "date": date_str,
                "venue": venue_code,
                "venue_name": venue_name,
                "total_races": total_races,
            }

    log(f"  ❌ {date_str} 不是赛马日，跳过。")
    return None



def _parse_total_races(html: str) -> int:
    """
    从排位表 HTML 中提取总场次数。
    返回整数（默认 10）。
    """
    race_nos = set(re.findall(r"RaceNo=(\d+)", html))
    if race_nos:
        return max(int(n) for n in race_nos)

    matches = re.findall(r"第\s*(\d+)\s*场", html)
    if matches:
        return max(int(m) for m in matches)

    return 10
