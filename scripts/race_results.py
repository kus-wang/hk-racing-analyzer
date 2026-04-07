#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
赛马分析工具 — 实际赛果抓取模块
==============================
职责：抓取 HKJC 赛果页面，解析名次/马号/马名。
由 daily_scheduler.py 调用。

缓存 TTL：7 天（赛果一旦确定不会变化）
"""

import re
from scheduler_cache import fetch_html

# HKJC URL
HKJC_BASE     = "https://racing.hkjc.com"
RESULT_URL    = HKJC_BASE + "/racing/information/Chinese/Racing/LocalResults.aspx"
CACHE_TTL     = 7 * 24 * 3600  # 赛果 7 天


def fetch_actual_results(race_info: dict) -> dict:
    """
    抓取指定赛马日的所有场次实际结果。

    Returns:
        {"1": [{"pos": 1, "no": "3", "name": "马名"}, ...], ...}
    """
    from daily_scheduler import log

    date_str     = race_info["date"]
    venue        = race_info["venue"]
    venue_name   = race_info.get("venue_name", venue)
    total_races  = race_info["total_races"]

    log(f"\n📊 抓取实际赛果：{date_str} {venue_name}")

    results = {}
    for race_no in range(1, total_races + 1):
        url  = f"{RESULT_URL}?RaceDate={date_str}&Venue={venue}&RaceNo={race_no}"
        ckey = f"result_{date_str}_{venue}_{race_no}"
        html = fetch_html(url, ckey, CACHE_TTL)

        if not html:
            log(f"  场次 {race_no}：⚠ 抓取失败")
            continue

        parsed = _parse_result_html(html)
        if parsed:
            results[str(race_no)] = parsed
            top3 = [h["no"] for h in parsed[:3]]
            log(f"  场次 {race_no}：实际前3 = {top3}")
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

    # ── 方案 A：逐行解析 <tr> 块（主力方案） ──
    tr_blocks = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    for tr in tr_blocks:
        tds_raw = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL)
        if len(tds_raw) < 3:
            continue
        # 去除 HTML 标签，保留文本
        tds = [re.sub(r'<[^>]+>', ' ', td).strip() for td in tds_raw]
        tds = [re.sub(r'\s+', ' ', t).strip() for t in tds]

        # 第0列：名次（取末尾数字）
        pos_text = tds[0]
        pos_m = re.search(r'(\d+)\s*$', pos_text)
        if not pos_m:
            continue

        # 第1列：马号（纯数字1-2位）
        no_text = tds[1]
        if not re.match(r'^\d{1,2}$', no_text):
            continue

        # 第2列：马名（含代码如"爆熱 (G368)"）
        name_text = tds[2]
        name_m = re.match(r'^(.+?)\s*(?:&nbsp;)?\s*\([A-Z]\d+\)', name_text)
        name = name_m.group(1).strip() if name_m else name_text.strip()
        if not name or len(name) > 20:
            continue

        try:
            pos = int(pos_m.group(1))
            no  = str(int(no_text))
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

    # ── 方案 B：备用正则（旧格式兼容） ──
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
                    no  = str(int(no_str))
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
