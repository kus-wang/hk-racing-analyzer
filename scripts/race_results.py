#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
赛马分析工具 — 实际赛果抓取模块
==============================
职责：抓取 HKJC 赛果数据，解析名次/马号/马名。
由 daily_scheduler.py 调用。

缓存 TTL：7 天（赛果一旦确定不会变化）
"""

import re

from api_client import get_race_data
from config import CACHE_TTL
from scheduler_cache import fetch_html

# HKJC URL
HKJC_BASE = "https://racing.hkjc.com"
RESULT_URL = HKJC_BASE + "/racing/information/Chinese/Racing/LocalResults.aspx"
CACHE_SECONDS = CACHE_TTL["race_result"]



def _parse_result_api(race_payload: dict) -> list | None:
    """
    从 HKJC API race payload 中提取名次，仅保留 finalPosition。
    
    实测发现：历史已完赛场次（如 2026-04-06 ST、2026-04-01 ST）的 finalPosition
    可能为空、0 或不可靠。因此，本函数仅返回有效的确定名次（1-14），
    若有效名次不足总参赛马数的一半，则视为不可靠，返回 None 触发页面回退。
    """
    race = (race_payload or {}).get("race") or {}
    runners = race.get("runners") or []
    placements = []

    for runner in runners:
        # finalPosition 可能为 null、""、"0"、"999" 等无效值
        pos_text = str(runner.get("finalPosition") or "").strip()
        if not pos_text.isdigit():
            continue
        pos_val = int(pos_text)
        if not (1 <= pos_val <= 14):  # 香港赛事最多 14 匹马
            continue

        no_text = str(runner.get("no") or "").strip()
        if not no_text.isdigit():
            continue
        horse_no = int(no_text)
        if not (1 <= horse_no <= 14):
            continue

        horse_info = runner.get("horse") or {}
        name = (
            runner.get("name_ch")
            or horse_info.get("name_ch")
            or runner.get("name_en")
            or horse_info.get("name_en")
            or ""
        ).strip()
        if not name:
            continue

        placements.append({
            "pos": pos_val,
            "no": str(horse_no),
            "name": name,
        })

    if not placements:
        return None

    # 防重复马号
    seen = set()
    unique = []
    for item in sorted(placements, key=lambda x: (x["pos"], int(x["no"]))):
        if item["no"] in seen:
            continue
        seen.add(item["no"])
        unique.append(item)

    # 数据可靠性检查：获取到有效名次的马匹数必须达到总马数的一半以上
    # 否则视为 API 数据不全，回退到页面解析
    n_total = len(runners)
    n_valid = len(unique)
    if n_total > 0 and n_valid * 2 < n_total:
        return None

    return unique or None




def fetch_actual_results(race_info: dict) -> dict:
    """
    抓取指定赛马日的所有场次实际结果。

    Returns:
        {"1": [{"pos": 1, "no": "3", "name": "马名"}, ...], ...}
    """
    from daily_scheduler import log

    date_str = race_info["date"]
    venue = race_info["venue"]
    venue_name = race_info.get("venue_name", venue)
    total_races = race_info["total_races"]

    log(f"\n📊 抓取实际赛果：{date_str} {venue_name}")

    results = {}
    for race_no in range(1, total_races + 1):
        api_payload = get_race_data(
            date_str,
            venue,
            race_no,
            force_refresh=True,  # v1.6.6: backtest 强制刷新，防止赛前 finalPosition=0 缓存污染赛后数据
            cache_ttl=CACHE_SECONDS,
        )
        parsed = _parse_result_api(api_payload) if api_payload else None

        if parsed:
            results[str(race_no)] = parsed
            top3 = [h["no"] for h in parsed[:3]]
            log(f"  场次 {race_no}：实际前3 = {top3}（来源：HKJC API）")
            continue

        url = f"{RESULT_URL}?RaceDate={date_str}&Venue={venue}&RaceNo={race_no}"
        ckey = f"result_{date_str}_{venue}_{race_no}"
        html = fetch_html(url, ckey, CACHE_SECONDS)

        if not html:
            log(f"  场次 {race_no}：⚠ 抓取失败")
            continue

        parsed = _parse_result_html(html)
        if parsed:
            results[str(race_no)] = parsed
            top3 = [h["no"] for h in parsed[:3]]
            log(f"  场次 {race_no}：实际前3 = {top3}（来源：页面）")
        else:
            log(f"  场次 {race_no}：⚠ 解析失败")

    return results



def _parse_result_html(html: str) -> list | None:
    """
    从赛果页面 HTML 中解析名次、马号、马名。

    HKJC 赛果页 <tr> 结构（2025/26 赛季）：
      <td style="white-space: nowrap;">[名次或含相机链接]</td>
      <td>马号</td>
      <td class="f_fs13 f_tal"><a>马名</a>&nbsp;(代码)</td>
      ... 骑师 练马师 磅重 ...

    Returns:
        [{"pos": 1, "no": "3", "name": "马名"}, ...]，按名次升序。
        失败返回 None。
    """
    placements = []

    tr_blocks = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    for tr in tr_blocks:
        tds_raw = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL)
        if len(tds_raw) < 3:
            continue

        tds = [re.sub(r'<[^>]+>', ' ', td).strip() for td in tds_raw]
        tds = [re.sub(r'\s+', ' ', t).strip() for t in tds]

        pos_text = tds[0]
        pos_m = re.search(r'(\d+)\s*$', pos_text)
        if not pos_m:
            continue

        no_text = tds[1]
        if not re.match(r'^\d{1,2}$', no_text):
            continue

        name_text = tds[2]
        name_m = re.match(r'^(.+?)\s*(?:&nbsp;)?\s*\([A-Z]\d+\)', name_text)
        name = name_m.group(1).strip() if name_m else name_text.strip()
        if not name or len(name) > 20:
            continue

        try:
            pos = int(pos_m.group(1))
            no = str(int(no_text))
            if 1 <= pos <= 20 and name:
                placements.append({"pos": pos, "no": no, "name": name})
        except ValueError:
            continue

    if placements:
        seen = set()
        unique = []
        for p in sorted(placements, key=lambda x: x["pos"]):
            if p["no"] not in seen:
                seen.add(p["no"])
                unique.append(p)
        if unique:
            return unique

    fallback_patterns = [
        r"<tr[^>]*>\s*<td[^>]*>(\d+)</td>\s*<td[^>]*>(\d+)</td>\s*<td[^>]*>([^<]+)</td>",
        r"<td[^>]*f_tac[^>]*>(\d+)</td>[^<]*<td[^>]*>(\d+)</td>[^<]*<td[^>]*>([^<]{2,20})</td>",
    ]
    for pat in fallback_patterns:
        matches = re.findall(pat, html)
        if matches:
            placements = []
            for m in matches:
                pos_str, no_str, name = m[0].strip(), m[1].strip(), m[2].strip()
                try:
                    pos = int(pos_str)
                    no = str(int(no_str))
                    if 1 <= pos <= 20 and name:
                        placements.append({"pos": pos, "no": no, "name": name})
                except ValueError:
                    continue
            if placements:
                seen = set()
                unique = []
                for p in sorted(placements, key=lambda x: x["pos"]):
                    if p["no"] not in seen:
                        seen.add(p["no"])
                        unique.append(p)
                if unique:
                    return unique

    return None
