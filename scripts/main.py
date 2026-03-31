#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HKJC 赛马分析工具 - 主程序模块

提供 CLI 入口、参数解析和主分析流程。
"""

import sys
import io
import json
import argparse
from datetime import datetime
from urllib.parse import quote

# Windows PowerShell 下强制 UTF-8 输出，避免 emoji 编码报错
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from config import RACE_CARD_URL
from weights import get_weights
from probability import softmax_probability
from cache import cache_stats, cache_clear
from fetch import fetch_url_with_playwright, fetch_tips_index, fetch_horse_history
from parse import parse_race_entries
from scoring import calculate_total_score
from output import format_markdown_output


def parse_args():
    parser = argparse.ArgumentParser(description="香港赛马分析工具")
    parser.add_argument("--date", type=str, default=None,
                        help="赛事日期，格式 YYYY/MM/DD，默认今天")
    parser.add_argument("--venue", type=str, required=False,
                        choices=["ST", "HV", "沙田", "跑马地"],
                        help="场地: ST/沙田 或 HV/跑马地")
    parser.add_argument("--race", type=int, required=False,
                        help="场次号")
    parser.add_argument("--distance", type=int, default=1400,
                        help="赛事距离（米），默认 1400")
    parser.add_argument("--track", type=str, default="turf",
                        choices=["turf", "dirt"],
                        help="赛道类型: turf/草地 或 dirt/泥地")
    parser.add_argument("--condition", type=str, default="good",
                        choices=["fast", "good_to_firm", "good", "yielding", "soft"],
                        help="场地状况")
    parser.add_argument("--scenario", type=str, default="normal",
                        choices=["normal", "newcomer", "class_down", "class_up"],
                        help="赛事场景")
    parser.add_argument("--output", type=str, default="markdown",
                        choices=["json", "markdown"],
                        help="输出格式")
    # ── 缓存控制 ────────────────────────────────────────────────
    parser.add_argument("--force-refresh", action="store_true",
                        help="忽略缓存，强制重新抓取所有数据")
    parser.add_argument("--clear-cache", action="store_true",
                        help="清除当前场次的缓存后重新分析")
    parser.add_argument("--cache-stats", action="store_true",
                        help="仅显示缓存统计信息，不执行分析")
    return parser.parse_args()


def normalize_venue(venue):
    if venue in ["ST", "沙田"]:
        return "ST"
    elif venue in ["HV", "跑马地"]:
        return "HV"
    return venue


def get_today_date():
    return datetime.now().strftime("%Y/%m/%d")


def main():
    args = parse_args()

    # ── 仅显示缓存统计 ───────────────────────────────────────────
    if args.cache_stats:
        stats = cache_stats()
        print(f"📦 缓存目录: {__import__('config').CACHE_DIR}")
        print(f"   文件数  : {stats['count']}")
        print(f"   总大小  : {stats['size_kb']} KB")
        print(f"   最旧条目: {stats['oldest'] or '无'}")
        return

    # venue / race 在非 --cache-stats 模式下必须提供
    if not args.venue or not args.race:
        print("❌ 请提供 --venue 和 --race 参数（或使用 --cache-stats 查看缓存状态）")
        return

    race_date = args.date if args.date else get_today_date()
    venue = normalize_venue(args.venue)
    race_no = args.race
    distance = args.distance
    track_type = args.track
    track_condition = args.condition
    scenario = args.scenario
    force_refresh = args.force_refresh

    # ── 清除当前场次缓存 ─────────────────────────────────────────
    if args.clear_cache:
        n = cache_clear(race_date=race_date, venue=venue, race_no=race_no)
        print(f"🗑️  已清除 {n} 个缓存文件（{race_date} {venue} 第{race_no}场）")
        force_refresh = True  # 清除后自动强制刷新

    print(f"🏇 分析赛事: {race_date} {venue} 第{race_no}场  {distance}m {track_type} [{scenario}]")
    if force_refresh:
        print("🔄 强制刷新模式：跳过缓存，重新抓取所有数据")
    else:
        stats = cache_stats()
        print(f"💾 缓存状态: {stats['count']} 个文件 / {stats['size_kb']} KB  (目录: {__import__('config').CACHE_DIR})")

    # 获取适配权重
    weights = get_weights(venue, distance, track_type, scenario)
    print(f"📐 权重配置: {json.dumps({k: round(v, 3) for k, v in weights.items()}, ensure_ascii=False)}")

    # 获取赛事数据（带缓存）
    # 排位表 URL 格式：racedate=YYYY/MM/DD&Racecourse=ST&RaceNo=N
    # 排位表页面需要 JS 渲染，使用 Playwright 获取
    url = (
        f"{RACE_CARD_URL}"
        f"?racedate={quote(race_date)}&Racecourse={venue}&RaceNo={race_no}"
    )
    html = fetch_url_with_playwright(url, force_refresh=force_refresh)

    if not html:
        print("❌ 无法获取赛事数据，请检查日期/场地/场次是否正确。")
        return

    # 解析参赛马匹
    horses = parse_race_entries(html, race_no=race_no)
    if not horses:
        print("⚠️  未能解析出参赛马匹，页面结构可能已变更。")
        return
    print(f"✅ 找到 {len(horses)} 匹参赛马匹")

    # ── 抓取 HKJC 官方贴士指数 ─────────────────────────────────
    print(f"\n📊 正在抓取 HKJC 官方贴士指数...")
    tips_data = fetch_tips_index(force_refresh=force_refresh)
    if tips_data.get("tips"):
        print(f"✅ 获取到 {len(tips_data['tips'])} 条贴士数据")
        if tips_data.get("race_info"):
            ri = tips_data["race_info"]
            print(f"   赛事: {ri.get('date', '')} {ri.get('venue', '')} {ri.get('distance', '')}")
        if tips_data.get("last_updated"):
            print(f"   更新时间: {tips_data['last_updated']}")
        for horse_no, value in sorted(tips_data["tips"].items(), key=lambda x: x[0]):
            print(f"   {horse_no}: {value:.1f}")
    else:
        print("⚠️  未获取到贴士数据（可能页面结构变更或网络问题）")
    print()

    # ── 抓取每匹马历史战绩（带缓存，一次性批量）──────────────────
    print(f"\n📚 正在抓取 {len(horses)} 匹参赛马匹的历史战绩...")
    for i, horse in enumerate(horses, 1):
        horse_id = horse.get("id", "")
        if not horse_id:
            continue
        print(f"  [{i:2d}/{len(horses)}] {horse['name']} ({horse_id})")
        hist_data = fetch_horse_history(horse_id, force_refresh=force_refresh)
        horse["history"] = hist_data.get("history", [])
        horse["current_rating"] = hist_data.get("current_rating", 40)
        # 简短摘要
        h_count = len(horse["history"])
        same_cond = sum(
            1 for r in horse["history"]
            if r.get("venue") == venue and abs(r.get("distance", 0) - distance) <= 200
        )
        if h_count > 0:
            print(f"         历史共 {h_count} 场，同条件 {same_cond} 场，当前评分 {horse['current_rating']}")
        else:
            print(f"         暂无历史战绩")
    print()

    # ── 导入 analyze_horse（避免循环导入）───────────────────────
    from analyze import analyze_horse

    # 各维度评分（传入贴士指数数据）
    for horse in horses:
        horse = analyze_horse(horse, venue, distance, track_condition, tips_data=tips_data)
        horse["total_score"] = calculate_total_score(horse, weights)

    # 概率计算（Softmax + 上限约束）
    scores = [h["total_score"] for h in horses]
    probs = softmax_probability(scores)
    for horse, prob in zip(horses, probs):
        horse["probability"] = prob

    # 输出结果
    race_info = {"date": race_date, "venue": venue, "race": race_no}

    if args.output == "markdown":
        print("\n" + format_markdown_output(race_info, horses))
    else:
        print(json.dumps({
            "race_info": race_info,
            "weights_used": weights,
            "horses": horses,
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
