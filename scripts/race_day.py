#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
赛马分析工具 — 赛马日检测模块
============================
职责：检测指定日期是否为赛马日，返回场地和场次数。
由 daily_scheduler.py 调用。
"""

import re
from scheduler_cache import fetch_html

# HKJC URL
HKJC_BASE     = "https://racing.hkjc.com"
RACE_DATE_URL = HKJC_BASE + "/racing/information/Chinese/Racing/RaceCard.aspx"

# 缓存 TTL（秒）
CACHE_TTL = 30 * 60  # 排位表 30 分钟


def detect_race_day(date_str: str) -> dict | None:
    """
    检测指定日期（YYYY/MM/DD）是否为赛马日。

    Returns:
        {"date": ..., "venue": "ST"|"HV", "venue_name": ..., "total_races": N}
        或 None（非赛马日）。
    """
    from daily_scheduler import log

    log(f"🔍 检测 {date_str} 是否为赛马日...")

    # 依次检测沙田和跑马地
    for venue_code, venue_name in [("ST", "沙田"), ("HV", "跑马地")]:
        url   = f"{RACE_DATE_URL}?RaceDate={date_str}&Venue={venue_code}&RaceNo=1"
        ckey  = f"racecard_{date_str}_{venue_code}"
        html  = fetch_html(url, ckey, CACHE_TTL)

        if not html:
            continue

        # 检测是否存在赛事数据
        if "没有赛事资料" in html or "没有相关资料" in html or "No Race Information" in html:
            continue
        if "RaceNo" not in html and "马名" not in html and "HorseNo" not in html:
            continue

        # 验证实际场地（HKJC 旧版 API 可能忽略 Venue 参数）
        actual_venues = re.findall(r"Racecourse=(ST|HV)", html)
        if actual_venues and actual_venues[0] != venue_code:
            log(f"  ⚠️ 请求 {venue_name}，但页面实际为 {actual_venues[0]}，跳过")
            continue

        total_races = _parse_total_races(html)
        if total_races and total_races > 0:
            log(f"  ✅ {date_str} 是赛马日！场地：{venue_name}，共 {total_races} 场")
            return {
                "date":        date_str,
                "venue":       venue_code,
                "venue_name":  venue_name,
                "total_races": total_races,
            }

    log(f"  ❌ {date_str} 不是赛马日，跳过。")
    return None


def _parse_total_races(html: str) -> int:
    """
    从排位表 HTML 中提取总场次数。
    返回整数（默认 10）。
    """
    # 方案A：从导航链接提取
    race_nos = set(re.findall(r"RaceNo=(\d+)", html))
    if race_nos:
        return max(int(n) for n in race_nos)

    # 方案B：搜索「第X场」文字
    matches = re.findall(r"第\s*(\d+)\s*场", html)
    if matches:
        return max(int(m) for m in matches)

    # 默认值（香港赛马通常 8-11 场）
    return 10
