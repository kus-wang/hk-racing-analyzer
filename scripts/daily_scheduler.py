#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
香港赛马 — 每日自动化调度脚本
============================
职责：
  1. 检测明天/今天是否为赛马日
  2. 赛马日前一天 → 批量预测所有场次，保存预测存档
  3. 赛马日当天赛后 → 抓取实际结果，对比前一天预测，计算精度
  4. 根据回测结果生成「自我进化建议报告」（供用户审阅，不直接修改 Skill）

用法（由 WorkBuddy 定时任务调用）：
  python daily_scheduler.py

流程判断：
  - 当前时间 < 11:00 → 检测今天是否赛马日，若是则当天赛事已赛完（昨晚跑马地），运行回测
  - 当前时间 11:00-22:00 → 检测明天是否赛马日，若是则预测明天所有场次
  - 当前时间 > 22:00 → 检测今天赛事是否已全部结束，若是则运行回测
  （实际通过 --mode 参数控制，由 automation prompt 决定）
"""

import sys
import io
import os
import json
import re
import math
import hashlib
import time
import argparse
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ──────────────────────────────────────────────────────────────
# 路径配置
# ──────────────────────────────────────────────────────────────
_SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR    = os.path.dirname(_SCRIPT_DIR)
CACHE_DIR     = os.path.join(_SKILL_DIR, ".cache")
ARCHIVE_DIR   = os.path.join(_SKILL_DIR, ".archive")      # 预测存档
COMPLETED_DIR = os.path.join(ARCHIVE_DIR, "completed")    # 已回测完成的存档
EVOLUTION_DIR = os.path.join(_SKILL_DIR, ".evolution")    # 进化建议报告

for d in [CACHE_DIR, ARCHIVE_DIR, COMPLETED_DIR, EVOLUTION_DIR]:
    os.makedirs(d, exist_ok=True)

HKJC_BASE      = "https://racing.hkjc.com"
RACE_DATE_URL  = HKJC_BASE + "/racing/information/Chinese/Racing/RaceCard.aspx"
RESULT_URL     = HKJC_BASE + "/racing/information/Chinese/Racing/LocalResults.aspx"

# 缓存 TTL（秒）
CACHE_TTL = {
    "race_card":    30 * 60,
    "race_result":  7  * 24 * 3600,
    "horse_history": 24 * 3600,
    "default":      60 * 60,
}

# ──────────────────────────────────────────────────────────────
# 通用工具
# ──────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _cache_path(key: str) -> str:
    h = hashlib.md5(key.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{h}.json")


def cache_get(key: str, ttl: int) -> dict | None:
    p = _cache_path(key)
    if not os.path.exists(p):
        return None
    age = time.time() - os.path.getmtime(p)
    if age > ttl:
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def cache_set(key: str, data: dict):
    p = _cache_path(key)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_html(url: str, cache_key: str = None, ttl: int = None) -> str:
    """抓取 HTML，支持缓存。返回 HTML 字符串，失败返回空字符串。"""
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


# ──────────────────────────────────────────────────────────────
# Step 1 — 检测指定日期是否为赛马日
# ──────────────────────────────────────────────────────────────

def detect_race_day(date_str: str) -> dict | None:
    """
    检测指定日期（YYYY/MM/DD）是否为赛马日。
    返回 {"date": ..., "venue": "ST"|"HV", "total_races": N} 或 None（非赛马日）。
    """
    log(f"🔍 检测 {date_str} 是否为赛马日...")

    # 依次检测沙田和跑马地
    for venue_code, venue_name in [("ST", "沙田"), ("HV", "跑马地")]:
        url = f"{RACE_DATE_URL}?RaceDate={date_str}&Venue={venue_code}&RaceNo=1"
        ckey = f"racecard_{date_str}_{venue_code}"
        html = fetch_html(url, ckey, CACHE_TTL["race_card"])

        if not html:
            continue

        # 检测是否存在赛事数据（排位表特征标志）
        if "没有赛事资料" in html or "没有相关资料" in html or "No Race Information" in html:
            continue
        if "RaceNo" not in html and "马名" not in html and "HorseNo" not in html:
            continue

        # 验证实际场地（HKJC 旧版 API 可能忽略 Venue 参数，返回当天唯一有赛事的场地）
        actual_venues = re.findall(r"Racecourse=(ST|HV)", html)
        if actual_venues and actual_venues[0] != venue_code:
            log(f"  ⚠️ 请求 {venue_name}，但页面实际为 {actual_venues[0]}，跳过")
            continue

        # 提取总场次数
        total_races = _parse_total_races(html, date_str, venue_code)
        if total_races and total_races > 0:
            log(f"  ✅ {date_str} 是赛马日！场地：{venue_name}，共 {total_races} 场")
            return {"date": date_str, "venue": venue_code, "venue_name": venue_name, "total_races": total_races}

    log(f"  ❌ {date_str} 不是赛马日，跳过。")
    return None


def _parse_total_races(html: str, date_str: str, venue: str) -> int:
    """从排位表 HTML 中提取总场次数。"""
    # HKJC 页面通常包含场次导航链接，如 RaceNo=1 到 RaceNo=11
    race_nos = set(re.findall(r"RaceNo=(\d+)", html))
    if race_nos:
        return max(int(n) for n in race_nos)

    # 备用：搜索「第X场」文字
    matches = re.findall(r"第\s*(\d+)\s*场", html)
    if matches:
        return max(int(m) for m in matches)

    # 无法解析时返回默认值（香港赛马通常 8-11 场）
    return 10


# ──────────────────────────────────────────────────────────────
# Step 2 — 批量预测（调用 analyze_race.py）
# ──────────────────────────────────────────────────────────────

def run_batch_predictions(race_info: dict) -> dict:
    """
    对指定赛马日的所有场次运行预测，返回预测存档字典。
    存档格式：
    {
      "meta": {"date": ..., "venue": ..., "total_races": ..., "predicted_at": ...},
      "races": {
        "1": {"horses": [...], "top3_predicted": [马号, 马号, 马号], "scores": {...}},
        ...
      }
    }
    """
    date_str    = race_info["date"]
    venue       = race_info["venue"]
    total_races = race_info["total_races"]

    log(f"\n🏇 开始批量预测：{date_str} {race_info['venue_name']} 共 {total_races} 场")

    archive = {
        "meta": {
            "date": date_str,
            "venue": venue,
            "venue_name": race_info["venue_name"],
            "total_races": total_races,
            "predicted_at": datetime.now().isoformat(),
        },
        "races": {}
    }

    analyze_script = os.path.join(_SCRIPT_DIR, "analyze_race.py")

    for race_no in range(1, total_races + 1):
        log(f"  → 预测第 {race_no}/{total_races} 场...")
        result = _run_single_prediction(analyze_script, date_str, venue, race_no)
        if result:
            archive["races"][str(race_no)] = result
            top3 = result.get("top3_predicted", [])
            # 投注建议（简洁显示）
            bet = result.get("betting_recommendation")
            if bet:
                bet_name = {"WIN": "独赢", "PLACE": "位置", "Q": "连赢", "TRIO": "三重彩"}.get(bet.get("bet_type", ""), bet.get("bet_type", ""))
                sels = " ".join(f"#{s}" for s in bet.get("selections", []))
                log(f"     预测前3：{top3}  |  推荐：{bet_name} {sels}")
            else:
                log(f"     预测前3：{top3}")
        else:
            log(f"     ⚠ 第 {race_no} 场预测失败，跳过")

    # 保存预测存档
    archive_file = _archive_path(date_str, venue, "prediction")
    with open(archive_file, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)
    log(f"\n✅ 预测存档已保存：{archive_file}")

    return archive


def _run_single_prediction(script_path: str, date_str: str, venue: str, race_no: int) -> dict | None:
    """
    调用 analyze_race.py 对单场进行预测，解析 JSON 输出。
    """
    import subprocess
    cmd = [
        sys.executable, script_path,
        "--date", date_str,
        "--venue", venue,
        "--race", str(race_no),
        "--output", "json",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        output = proc.stdout.strip()
        if not output:
            return None

        # analyze_race.py 的 --output json 模式会在 JSON 前后混入日志行
        # 需要从输出中提取 JSON 块（以 { 开头，以 } 结尾的最大块）
        json_str = _extract_json_block(output)
        if not json_str:
            log(f"     ⚠ 未找到 JSON 块")
            return _fallback_parse_output(output)

        # 尝试解析 JSON 输出
        data = json.loads(json_str)

        # 提取前3预测（按 total_score 降序的前3个马号）
        # analyze_race.py 输出字段为 regular_horses，兼容旧版 horses
        horses = data.get("regular_horses") or data.get("horses", [])
        sorted_horses = sorted(horses, key=lambda h: h.get("total_score", 0), reverse=True)
        top3 = [h.get("horse_no") or h.get("no") for h in sorted_horses[:3]]

        # v1.4.13: 生成投注推荐
        from betting import determine_bet_type
        bet_rec = determine_bet_type(sorted_horses)

        return {
            "horses": horses,
            "top3_predicted": top3,
            "scores": {
                str(h.get("horse_no") or h.get("no")): h.get("total_score", 0)
                for h in horses
            },
            "probabilities": {
                str(h.get("horse_no") or h.get("no")): h.get("probability", 0)
                for h in horses
            },
            # v1.4.12: 保存预测时各马赔率快照，供回测时作为 opening_odds 参考
            "predicted_odds_snapshot": {
                str(h.get("horse_no") or h.get("no")): h.get("final_odds")
                for h in horses
                if h.get("final_odds") is not None
            },
            # v1.4.13: 投注推荐
            "betting_recommendation": bet_rec,
            "raw_output": data,
        }
    except subprocess.TimeoutExpired:
        log(f"     ⚠ 超时（120s），跳过")
        return None
    except json.JSONDecodeError as e:
        log(f"     ⚠ JSON 解析失败：{e}")
        # 尝试从 stdout 中正则提取前3名
        return _fallback_parse_output(proc.stdout if 'proc' in dir() else "")
    except Exception as e:
        log(f"     ⚠ 异常：{e}")
        return None


def _extract_json_block(text: str) -> str | None:
    """
    从混合输出（日志 + JSON）中提取最大的 JSON 对象块。
    查找第一个 '{' 到最后一个 '}' 之间的内容。
    """
    start = text.find('{')
    end   = text.rfind('}')
    if start == -1 or end == -1 or end <= start:
        return None
    candidate = text[start:end+1]
    # 验证是合法 JSON
    try:
        json.loads(candidate)
        return candidate
    except json.JSONDecodeError:
        # 逐行尝试找到合法 JSON 段
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith('{'):
                for j in range(len(lines), i, -1):
                    block = "\n".join(lines[i:j])
                    try:
                        json.loads(block)
                        return block
                    except json.JSONDecodeError:
                        continue
    return None


def _fallback_parse_output(text: str) -> dict | None:
    """从 markdown 格式输出中提取预测前3名（降级方案）。"""
    if not text:
        return None
    # 匹配表格行：| 1 | 3 | 马名 | 25% | ...
    rows = re.findall(r"\|\s*\d+\s*\|\s*(\d+)\s*\|", text)
    if rows:
        return {"top3_predicted": rows[:3], "horses": [], "scores": {}, "probabilities": {}}
    return None


# ──────────────────────────────────────────────────────────────
# Step 3 — 抓取实际赛果
# ──────────────────────────────────────────────────────────────

def fetch_actual_results(race_info: dict) -> dict:
    """
    抓取指定赛马日的实际赛果，返回结果字典。
    格式：{"1": [{"pos":1,"no":"3","name":"马名"}, ...], ...}
    """
    date_str    = race_info["date"]
    venue       = race_info["venue"]
    total_races = race_info["total_races"]

    log(f"\n📊 抓取实际赛果：{date_str} {race_info['venue_name']}")

    results = {}
    for race_no in range(1, total_races + 1):
        url   = f"{RESULT_URL}?RaceDate={date_str}&Venue={venue}&RaceNo={race_no}"
        ckey  = f"result_{date_str}_{venue}_{race_no}"
        html  = fetch_html(url, ckey, CACHE_TTL["race_result"])
        if html:
            parsed = _parse_result_html(html)
            if parsed:
                results[str(race_no)] = parsed
                top3_actual = [h["no"] for h in parsed[:3]]
                log(f"  场次 {race_no}：实际前3 = {top3_actual}")
            else:
                log(f"  场次 {race_no}：⚠ 解析失败")
        else:
            log(f"  场次 {race_no}：⚠ 抓取失败")

    return results


def _parse_result_html(html: str) -> list | None:
    """
    从赛果页面 HTML 中解析名次、马号、马名。
    返回 [{"pos":1,"no":"3","name":"马名"}, ...]，按名次排序。

    HKJC 赛果页 <tr> 结构（2025/26 赛季）：
      <td style="white-space: nowrap;">[名次或含相机链接]</td>
      <td>\n马号\n</td>
      <td class="f_fs13 f_tal" ...><a ...>马名</a>&nbsp;(代码)</td>
      ... 骑师 练马师 磅重 等更多 td ...
    """
    placements = []

    # ── 方案 A：逐行解析 <tr> 块（主力方案） ──
    tr_blocks = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
    for tr in tr_blocks:
        # 提取所有 <td> 的文本内容（去除子标签）
        tds_raw = re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL)
        if len(tds_raw) < 3:
            continue
        tds = [re.sub(r'<[^>]+>', ' ', td).strip() for td in tds_raw]
        tds = [re.sub(r'\s+', ' ', t).strip() for t in tds]

        # 第0列：名次（可能含相机图标文字，取最后的数字）
        pos_text = tds[0]
        pos_m = re.search(r'(\d+)\s*$', pos_text)
        if not pos_m:
            continue

        # 第1列：马号（纯数字）
        no_text = tds[1]
        if not re.match(r'^\d{1,2}$', no_text):
            continue

        # 第2列：马名（含代码如"爆熱 (G368)"，取括号前的名字）
        name_text = tds[2]
        name_m = re.match(r'^(.+?)\s*(?:&nbsp;)?\s*\([A-Z]\d+\)', name_text)
        if name_m:
            name = name_m.group(1).strip()
        else:
            # 没有代码就直接用，但要排除骑师/练马师（通常名字较短且为汉字）
            name = name_text.strip()
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
        # 去重 + 按名次排序
        seen = set()
        unique = []
        for p in sorted(placements, key=lambda x: x["pos"]):
            if p["no"] not in seen:
                seen.add(p["no"])
                unique.append(p)
        if unique:
            return unique

    # ── 方案 B：备用简单正则（旧格式兼容） ──
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


# ──────────────────────────────────────────────────────────────
# Step 4 — 精度计算 + 自我进化分析
# ──────────────────────────────────────────────────────────────

def compare_and_evolve(prediction_archive: dict, actual_results: dict) -> dict:
    """
    对比预测与实际结果，计算精度指标，生成自我进化建议。
    返回完整的回测报告字典。
    """
    meta    = prediction_archive.get("meta", {})
    races   = prediction_archive.get("races", {})
    date_str = meta.get("date", "unknown")

    log(f"\n🔬 对比分析：{date_str}")

    race_reports = []
    total_top1_hits  = 0
    total_top3_hits  = 0
    total_races_done = 0
    total_bet_hits   = 0           # v1.4.13: 投注推荐命中总数
    bet_type_stats   = {}           # v1.4.13: 按玩法统计 {"WIN": {"total": N, "hits": N}, ...}

    # v1.4.13: 导入投注验证
    from betting import check_bet_hit

    # 逐场对比
    for race_no_str, pred in races.items():
        actual = actual_results.get(race_no_str, [])
        if not actual:
            log(f"  场次 {race_no_str}：无实际结果，跳过")
            continue

        top3_pred   = pred.get("top3_predicted", [])
        top3_actual = [h["no"] for h in actual[:3] if h["pos"] <= 3]
        winner      = actual[0]["no"] if actual else None

        # v1.4.12: 提取预测时赔率快照，用于 drift 统计分析
        odds_snapshot = pred.get("predicted_odds_snapshot", {})
        odds_available = len(odds_snapshot) > 0

        # 命中计算
        top1_hit  = (len(top3_pred) > 0 and str(top3_pred[0]) == str(winner))
        top3_hits = len(set(str(p) for p in top3_pred) & set(str(a) for a in top3_actual))

        total_races_done += 1
        if top1_hit:
            total_top1_hits += 1
        total_top3_hits += top3_hits

        # ── v1.4.13: 投注推荐命中验证 ──
        bet_rec = pred.get("betting_recommendation")
        bet_result = None
        if bet_rec:
            bet_result = check_bet_hit(bet_rec, actual)
            bet_type_key = bet_rec.get("bet_type", "UNKNOWN")
            if bet_type_key not in bet_type_stats:
                bet_type_stats[bet_type_key] = {"total": 0, "hits": 0}
            bet_type_stats[bet_type_key]["total"] += 1
            if bet_result and bet_result.get("hit"):
                bet_type_stats[bet_type_key]["hits"] += 1
                total_bet_hits += 1

        # 评分偏差分析（哪些马被高估/低估）
        scores = pred.get("scores", {})
        overestimated = []   # 预测排名高但实际未入前3
        underestimated = []  # 预测排名低但实际前3

        if scores:
            sorted_pred = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            pred_ranking = {no: rank+1 for rank, (no, _) in enumerate(sorted_pred)}

            for actual_h in actual[:3]:
                no = str(actual_h["no"])
                pred_rank = pred_ranking.get(no, 99)
                if pred_rank > 5:
                    underestimated.append({"no": no, "pred_rank": pred_rank, "actual_pos": actual_h["pos"]})

            for no, rank in pred_ranking.items():
                if rank <= 3 and str(no) not in [str(a["no"]) for a in actual[:3]]:
                    overestimated.append({"no": no, "pred_rank": rank})

        race_report = {
            "race_no":       race_no_str,
            "top3_predicted": [str(x) for x in top3_pred],
            "top3_actual":   top3_actual,
            "winner":        winner,
            "top1_hit":      top1_hit,
            "top3_hits":     top3_hits,
            "overestimated": overestimated,
            "underestimated": underestimated,
            # v1.4.13: 投注推荐回测
            "bet_recommendation": bet_rec,
            "bet_result":         bet_result,
        }
        race_reports.append(race_report)

        bet_status = "✅" if (bet_result and bet_result.get("hit")) else "❌"
        status = "✅" if top1_hit else ("🔶" if top3_hits >= 2 else "❌")
        log(f"  场次 {race_no_str}：{status} 预测={top3_pred} 实际={top3_actual} 独赢命中={top1_hit} 投注={bet_status}")

    # 整体精度
    if total_races_done == 0:
        log("  ⚠ 无可对比场次")
        return {}

    top1_rate  = total_top1_hits  / total_races_done
    top3_rate  = total_top3_hits  / (total_races_done * 3)
    bet_hit_rate = total_bet_hits / total_races_done if total_races_done > 0 else 0

    log(f"\n📈 整体精度：独赢命中率 {top1_rate:.1%}，前3命中率 {top3_rate:.1%}")
    log(f"💰 投注推荐命中率：{bet_hit_rate:.1%}（{total_bet_hits}/{total_races_done}）")

    # 生成进化建议
    evolution_suggestions = _generate_evolution_suggestions(
        race_reports, top1_rate, top3_rate, bet_type_stats
    )

    backtest_report = {
        "meta": {
            "date":             date_str,
            "venue":            meta.get("venue"),
            "venue_name":       meta.get("venue_name"),
            "total_races":      total_races_done,
            "top1_hit_count":   total_top1_hits,
            "top3_hit_count":   total_top3_hits,
            "top1_rate":        round(top1_rate, 4),
            "top3_rate":        round(top3_rate, 4),
            "bet_hit_count":    total_bet_hits,
            "bet_hit_rate":     round(bet_hit_rate, 4),
            "bet_type_stats":   bet_type_stats,
            "analyzed_at":      datetime.now().isoformat(),
        },
        "race_reports":          race_reports,
        "evolution_suggestions": evolution_suggestions,
    }

    return backtest_report


def _generate_evolution_suggestions(race_reports: list, top1_rate: float, top3_rate: float, bet_type_stats: dict = None) -> list:
    """
    根据回测数据生成具体的权重/逻辑优化建议。
    这是「自我进化」的核心 —— 不直接修改，而是输出结构化建议供用户审阅。
    """
    suggestions = []

    # 统计系统性偏差
    total_over  = sum(len(r["overestimated"])  for r in race_reports)
    total_under = sum(len(r["underestimated"]) for r in race_reports)
    total_races = len(race_reports)

    # ── 建议1：高估/低估模式 ──
    if total_over > total_races * 1.5:
        suggestions.append({
            "type":       "weight_adjust",
            "priority":   "high",
            "dimension":  "general",
            "title":      "预测过于激进，高分马命中率偏低",
            "detail":     (
                f"共 {total_over} 匹马被高估（预测前3但未入前3）。"
                "建议提高 Softmax 温度参数（当前 1.5 → 建议 2.0），"
                "使概率分布更均匀，降低极端预测的频率。"
            ),
            "code_change": {
                "file":    "analyze_race.py",
                "param":   "SOFTMAX_TEMPERATURE",
                "current": 1.5,
                "proposed": 2.0,
            }
        })

    if total_under > total_races * 1.0:
        suggestions.append({
            "type":       "weight_adjust",
            "priority":   "medium",
            "dimension":  "general",
            "title":      "冷门马低估严重，实际前3中有多匹预测靠后的马",
            "detail":     (
                f"共 {total_under} 匹马被低估（实际前3但预测排名>5）。"
                "可能原因：历史战绩权重过高，压制了当前状态较好的马。"
                "建议：降低历史战绩中「同条件」权重 -2%（18%→16%），"
                "提高赔率走势权重 +2%（13%→15%），更多参考市场即时信号。"
            ),
            "code_change": {
                "file":    "analyze_race.py",
                "param":   "DEFAULT_WEIGHTS",
                "current": {"history_same_condition": 0.18, "odds_drift": 0.13},
                "proposed": {"history_same_condition": 0.16, "odds_drift": 0.15},
            }
        })

    # ── 建议2：整体精度阈值触发 ──
    if top1_rate < 0.15:
        suggestions.append({
            "type":       "logic_review",
            "priority":   "high",
            "dimension":  "top1",
            "title":      f"独赢命中率 {top1_rate:.1%} 低于基准（15%）",
            "detail":     (
                "独赢命中率持续低于随机基准（~1/马匹数量）。"
                "建议检查：① 赔率数据是否为临场值（非开盘）；"
                "② 历史战绩是否已按时间衰减加权（近期成绩权重应更高）；"
                "③ 配速分项是否仍仅基于跑法推导（缺实测数据）。"
            ),
            "code_change": None,
        })

    if top3_rate < 0.30:
        suggestions.append({
            "type":       "weight_adjust",
            "priority":   "medium",
            "dimension":  "top3",
            "title":      f"前3命中率 {top3_rate:.1%} 低于基准（33%）",
            "detail":     (
                "前3命中率低于理论随机基准（33%）。"
                "当前配速评分（15%）依赖跑法推导，缺乏实测分段时间数据，"
                "可能引入系统性噪声。建议：临时将配速权重从 15% 降至 10%，"
                "释放的 5% 补充至历史战绩「同场地」（13%→18%），"
                "待配速实测数据接入后再恢复。"
            ),
            "code_change": {
                "file":    "analyze_race.py",
                "param":   "DEFAULT_WEIGHTS",
                "current": {"sectional": 0.15, "history_same_venue": 0.13},
                "proposed": {"sectional": 0.10, "history_same_venue": 0.18},
            }
        })

    # ── 建议3：时间衰减优化（固定建议，数据量达到阈值时触发）──
    if total_races >= 5:
        suggestions.append({
            "type":       "new_feature",
            "priority":   "medium",
            "dimension":  "history",
            "title":      "建议引入历史战绩时间衰减加权",
            "detail":     (
                "当前历史战绩对近期与6个月前成绩等权处理。"
                "建议加入时间衰减系数：近30天×1.0，31-90天×0.8，91-180天×0.6，>180天×0.4。"
                "预期对「近期状态好」但历史积累少的马改善评分准确性。"
            ),
            "code_change": {
                "file":   "analyze_race.py",
                "func":   "score_history()",
                "patch":  (
                    "在 score_history() 中对每条 hist 记录增加 time_weight：\n"
                    "  days_ago = (today - race_date).days\n"
                    "  if days_ago <= 30:   tw = 1.0\n"
                    "  elif days_ago <= 90:  tw = 0.8\n"
                    "  elif days_ago <= 180: tw = 0.6\n"
                    "  else:                tw = 0.4\n"
                    "  score += position_points * tw"
                ),
            }
        })

    # ── 建议4：样本量不足提示 ──
    if total_races < 3:
        suggestions.append({
            "type":       "info",
            "priority":   "low",
            "dimension":  "general",
            "title":      f"当前累计仅 {total_races} 场回测，建议积累至 10 场后再调整权重",
            "detail":     (
                "权重优化需要足够的样本量。单日数据可能存在偶然性。"
                "建议观察 2-3 个赛马日（累计 20-30 场）后，再根据统计趋势调整。"
            ),
            "code_change": None,
        })

    # ── v1.4.13 建议5：投注推荐玩法命中率分析 ──
    if bet_type_stats and total_races >= 3:
        bet_names_map = {"WIN": "独赢", "PLACE": "位置", "Q": "连赢", "TRIO": "三重彩"}
        low_rate_types = []
        for bt, stats in bet_type_stats.items():
            if stats["total"] >= 3:
                rate = stats["hits"] / stats["total"]
                if rate < 0.25:
                    name = bet_names_map.get(bt, bt)
                    low_rate_types.append(f"{name}（{stats['hits']}/{stats['total']}，{rate:.0%}）")

        if low_rate_types:
            suggestions.append({
                "type":       "logic_review",
                "priority":   "medium",
                "dimension":  "betting",
                "title":      f"投注推荐玩法命中率偏低：{', '.join(low_rate_types)}",
                "detail":     (
                    "部分投注玩法命中率持续偏低。"
                    "可能原因：① 场型判断阈值需要调整（如三强场概率阈值从60%提高到65%）；"
                    "② 价值指数过滤不够严格；"
                    "③ 特定玩法本身命中率低（如三重彩理论命中率约5-8%），属于正常现象。"
                    "建议：观察更多场次后再决定是否调整场型判断参数。"
                ),
                "code_change": None,
            })

    return suggestions


# ──────────────────────────────────────────────────────────────
# Step 5 — 输出进化报告（Markdown）
# ──────────────────────────────────────────────────────────────

def write_evolution_report(backtest_report: dict) -> str:
    """将回测报告渲染为 Markdown，保存到 .evolution/ 目录，并打印到 stdout。"""
    if not backtest_report:
        log("无回测数据，跳过报告生成")
        return ""

    meta        = backtest_report.get("meta", {})
    race_reports = backtest_report.get("race_reports", [])
    suggestions  = backtest_report.get("evolution_suggestions", [])

    date_str = meta.get("date", "unknown")
    lines = [
        f"# 🔬 赛马预测回测报告 — {date_str} {meta.get('venue_name','')}",
        "",
        f"> 预测场次：{meta.get('total_races', 0)}场 | "
        f"独赢命中：{meta.get('top1_hit_count',0)}/{meta.get('total_races',0)} "
        f"({meta.get('top1_rate',0):.1%}) | "
        f"前3命中（平均每场）：{meta.get('top3_rate',0):.1%} | "
        f"投注推荐命中：{meta.get('bet_hit_count',0)}/{meta.get('total_races',0)} "
        f"({meta.get('bet_hit_rate',0):.1%})",
        "",
        "---",
        "",
        "## 📊 逐场对比",
        "",
        "| 场次 | 预测前3 | 实际前3 | 独赢 | 前3 | 投注推荐 | 投注命中 |",
        "|------|---------|---------|------|-----|----------|---------|",
    ]

    # v1.4.13: 投注推荐玩法中文名映射
    bet_names_map = {"WIN": "独赢", "PLACE": "位置", "Q": "连赢", "TRIO": "三重彩"}

    for r in race_reports:
        top1_icon = "✅" if r["top1_hit"] else "❌"
        # 投注推荐列
        bet_rec = r.get("bet_recommendation")
        bet_result = r.get("bet_result")
        if bet_rec and bet_result:
            bt = bet_rec.get("bet_type", "")
            bt_name = bet_names_map.get(bt, bt)
            sels = bet_rec.get("selections", [])
            sel_text = " ".join(f"#{s}" for s in sels)
            bet_col = f"{bt_name} {sel_text}"
            bet_hit_icon = "✅" if bet_result.get("hit") else "❌"
        else:
            bet_col = "-"
            bet_hit_icon = "-"
        lines.append(
            f"| 第{r['race_no']}场 "
            f"| {', '.join(r['top3_predicted'])} "
            f"| {', '.join(r['top3_actual'])} "
            f"| {top1_icon} "
            f"| {r['top3_hits']}/3 "
            f"| {bet_col} "
            f"| {bet_hit_icon} |"
        )

    # ── v1.4.13: 投注推荐统计板块 ──
    bet_type_stats = meta.get("bet_type_stats", {})
    if bet_type_stats:
        lines += [
            "",
            "---",
            "",
            "## 💰 投注推荐回测统计",
            "",
            "| 玩法 | 推荐场次 | 命中场次 | 命中率 |",
            "|------|---------|---------|--------|",
        ]
        for bt, stats in bet_type_stats.items():
            bt_name = bet_names_map.get(bt, bt)
            total = stats["total"]
            hits = stats["hits"]
            rate = f"{hits / total:.1%}" if total > 0 else "-"
            lines.append(f"| {bt_name} | {total} | {hits} | {rate} |")

        lines.append("")

    lines += [
        "",
        "---",
        "",
        "## 🧬 自我进化建议",
        "",
        "> ⚠️ 以下建议**仅供参考**，需用户确认后才能写入正式 Skill。",
        "",
    ]

    priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢", "info": "ℹ️"}

    for i, sug in enumerate(suggestions, 1):
        icon = priority_icon.get(sug.get("priority", "low"), "•")
        lines += [
            f"### {icon} 建议 {i}：{sug['title']}",
            "",
            f"**类型**：{sug.get('type','—')}  |  **维度**：{sug.get('dimension','—')}  |  **优先级**：{sug.get('priority','—')}",
            "",
            sug.get("detail", ""),
            "",
        ]
        cc = sug.get("code_change")
        if cc:
            lines += [
                "**具体改动**：",
                "",
                f"```python",
                f"# 文件：{cc.get('file','')}"
            ]
            if "param" in cc:
                lines.append(f"# 参数：{cc['param']}")
                lines.append(f"# 当前值：{cc.get('current')}")
                lines.append(f"# 建议值：{cc.get('proposed')}")
            elif "patch" in cc:
                lines.append(cc["patch"])
            lines += ["```", ""]

    lines += [
        "---",
        "",
        f"*报告生成时间：{meta.get('analyzed_at', datetime.now().isoformat())}*",
        "",
        "> 如需将某条建议应用到 Skill，请回复：「应用建议 N」",
        "",
    ]

    report_text = "\n".join(lines)

    # 保存文件
    safe_date = date_str.replace("/", "-")
    report_file = os.path.join(EVOLUTION_DIR, f"evolution_{safe_date}_{meta.get('venue','')}.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_text)

    log(f"\n📝 进化报告已保存：{report_file}")
    print("\n" + "=" * 60)
    print(report_text)
    print("=" * 60)

    return report_file


# ──────────────────────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────────────────────

def _archive_path(date_str: str, venue: str, suffix: str) -> str:
    safe_date = date_str.replace("/", "-")
    return os.path.join(ARCHIVE_DIR, f"{safe_date}_{venue}_{suffix}.json")


def load_prediction_archive(date_str: str, venue: str) -> dict | None:
    """加载指定日期的预测存档（优先从原位置加载，若已归档则从 completed 目录加载）。"""
    # 先检查原位置
    p = _archive_path(date_str, venue, "prediction")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    # 若已归档，从 completed 目录加载
    completed_p = os.path.join(COMPLETED_DIR, os.path.basename(p))
    if os.path.exists(completed_p):
        with open(completed_p, encoding="utf-8") as f:
            return json.load(f)
    return None


def _archive_completed_prediction(date_str: str, venue: str) -> bool:
    """
    将已回测完成的预测存档移入 completed 目录进行归档隔离。
    防止已完成的预测存档被后续回测任务重复加载或污染。
    """
    src = _archive_path(date_str, venue, "prediction")
    if not os.path.exists(src):
        log(f"  ⚠ 预测存档不存在，无需归档：{src}")
        return False
    
    dst = os.path.join(COMPLETED_DIR, os.path.basename(src))
    try:
        # 如果目标已存在，先删除（避免覆盖失败）
        if os.path.exists(dst):
            os.remove(dst)
        os.rename(src, dst)
        log(f"  ✅ 预测存档已归档：{dst}")
        return True
    except Exception as e:
        log(f"  ⚠ 归档失败：{e}")
        return False


# ──────────────────────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="赛马每日自动调度")
    parser.add_argument(
        "--mode",
        choices=["predict", "backtest", "auto"],
        default="auto",
        help=(
            "predict  = 预测明天的赛事（在赛马日前一天运行）\n"
            "backtest = 回测今天的赛事结果（在赛马日赛后运行）\n"
            "auto     = 自动判断当前时间决定运行哪个模式"
        )
    )
    parser.add_argument("--date", help="指定日期 YYYY/MM/DD（默认自动推断）")
    args = parser.parse_args()

    now  = datetime.now()
    mode = args.mode

    if mode == "auto":
        # 下午 12 点前：检测今天是否赛马日，若是则准备回测（赛事已于前晚结束）
        # 下午 12-20 点：检测明天是否赛马日，若是则预测
        # 晚上 20 点后：检测今天是否赛马日，若是则运行回测
        hour = now.hour
        if hour < 12:
            mode = "backtest"
        elif hour < 20:
            mode = "predict"
        else:
            mode = "backtest"
        log(f"⏱ 当前时间 {now.strftime('%H:%M')}，自动模式 → {mode}")

    if mode == "predict":
        # 检测明天是否赛马日
        if args.date:
            target_date = args.date
        else:
            tomorrow = now + timedelta(days=1)
            target_date = tomorrow.strftime("%Y/%m/%d")

        race_info = detect_race_day(target_date)
        if race_info:
            run_batch_predictions(race_info)
        else:
            log(f"明天（{target_date}）不是赛马日，无需预测。结束。")

    elif mode == "backtest":
        # 检测今天/昨天是否有预测存档 + 实际赛果
        if args.date:
            target_date = args.date
        else:
            # 先试今天，再试昨天
            today_str = now.strftime("%Y/%m/%d")
            yesterday_str = (now - timedelta(days=1)).strftime("%Y/%m/%d")

            # 检测今天是否赛马日（先看是否有存档）
            race_info = None
            archive   = load_prediction_archive(today_str, "ST") or load_prediction_archive(today_str, "HV")

            if archive:
                target_date = today_str
                race_info   = archive["meta"]
            else:
                archive = load_prediction_archive(yesterday_str, "ST") or load_prediction_archive(yesterday_str, "HV")
                if archive:
                    target_date = yesterday_str
                    race_info   = archive["meta"]
                else:
                    log("未找到预测存档，跳过回测。（可能今天/昨天均非赛马日）")
                    return

        if not race_info:
            race_info = detect_race_day(target_date)
            if not race_info:
                log(f"{target_date} 不是赛马日，无法回测。")
                return

        if not archive:
            archive = load_prediction_archive(target_date, race_info.get("venue", "ST"))
            if not archive:
                log(f"未找到 {target_date} 的预测存档，无法回测（可能当天未运行预测模式）。")
                return

        actual_results = fetch_actual_results(race_info)
        if not actual_results:
            log("未能获取实际赛果，可能赛事尚未结束或网页结构变化。")
            return

        backtest_report = compare_and_evolve(archive, actual_results)

        # 保存回测报告 JSON
        report_file = _archive_path(target_date, race_info.get("venue","ST"), "backtest")
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(backtest_report, f, ensure_ascii=False, indent=2)

        # 输出 Markdown 进化报告
        write_evolution_report(backtest_report)

        # 归档：将预测存档移入 completed 目录，防止污染后续预测
        _archive_completed_prediction(target_date, race_info.get("venue", "ST"))


if __name__ == "__main__":
    main()
