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
import time
from datetime import datetime
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed

# Windows PowerShell 下强制 UTF-8 输出，避免 emoji 编码报错
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from config import RACE_CARD_URL
from weights import get_weights
from probability import softmax_probability, dynamic_temperature
from cache import cache_stats, cache_clear
from fetch import fetch_url_with_playwright, fetch_tips_index, fetch_horse_history, fetch_race_odds
from parse import parse_race_entries, validate_race_entries
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
                        help="场地状况 (fast/good_to_firm/good/yielding/soft 或中文: 快/好地快/好/略黏/黏)")
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


def normalize_condition(condition):
    """将中文或英文场地状况转换为规范英文值"""
    if not condition:
        return "good"

    condition_lower = condition.lower().strip()

    # 中文映射
    condition_map = {
        "快": "fast",
        "好地快": "good_to_firm",
        "快地": "good_to_firm",
        "好": "good",
        "略黏": "yielding",
        "黏": "soft",
        "湿慢": "soft",
        "濕慢": "soft",
    }

    # 如果是中文
    if condition in condition_map:
        return condition_map[condition]

    # 如果已经是英文规范值，直接返回
    valid_conditions = ["fast", "good_to_firm", "good", "yielding", "soft"]
    if condition_lower in valid_conditions:
        return condition_lower

    # 默认值
    return "good"


def get_today_date():
    return datetime.now().strftime("%Y/%m/%d")


def _fetch_single_horse_history(horse, venue, distance, force_refresh):
    """
    并行抓取单匹马历史战绩（供 ThreadPoolExecutor 调用）。

    返回：(horse_id, hist_data) 元组
    """
    horse_id = horse.get("id", "")
    if not horse_id:
        return (horse_id, {"history": [], "current_rating": 40})

    hist_data = fetch_horse_history(horse_id, force_refresh=force_refresh)
    return (horse_id, hist_data)


def infer_class_range(horses):
    """
    根据参赛马的评分分布，动态推断赛事班次区间。

    香港赛马班次结构（经验规律）：
        第4班：40分或以下
        第3班：41-60分
        第2班：61-80分
        第1班：81分或以上

    推断逻辑：
    1. 找到所有马的最高评分和最低评分
    2. 参考常见班次边界，推断班次区间
    3. 设置 class_ceiling 和 class_floor

    返回：更新后的 horses 列表
    """
    if not horses:
        return horses

    ratings = [h.get("current_rating", 40) for h in horses]
    min_rating = min(ratings) if ratings else 40
    max_rating = max(ratings) if ratings else 40

    if max_rating <= 40:
        class_floor = 0
        class_ceiling = 40
        class_name = "4"
    elif max_rating <= 52:
        if min_rating <= 40:
            class_floor = 0
            class_ceiling = max(40, max_rating + 5)
            class_name = "3/4"
        else:
            class_floor = 35
            class_ceiling = max_rating + 5
            class_name = "3"
    elif max_rating <= 65:
        class_floor = 35
        class_ceiling = max_rating + 5
        class_name = "2/3"
    elif max_rating <= 80:
        class_floor = 55
        class_ceiling = max_rating + 5
        class_name = "2"
    else:
        class_floor = 75
        class_ceiling = max_rating + 5
        class_name = "1"

    class_ceiling = min(class_ceiling, 120)
    class_floor = max(class_floor, 0)

    for horse in horses:
        horse["class_ceiling"] = class_ceiling
        horse["class_floor"] = class_floor
        horse["class_name"] = class_name

    avg_rating = sum(ratings) / len(ratings) if ratings else 40
    print(f"  Class Range: {class_name} | Rating: {class_floor}-{class_ceiling} | Min/Max/Avg: {min_rating}/{max_rating}/{avg_rating:.1f}")

    return horses


def fetch_all_horse_history(horses, venue, distance, force_refresh, max_workers=8):
    """
    并行抓取所有马匹历史战绩。

    参数：
        horses       : 马匹列表
        venue        : 场地代码
        distance     : 赛事距离
        force_refresh: 是否强制刷新
        max_workers  : 最大并行线程数

    返回：更新后的马匹列表
    """
    total = len(horses)
    start_time = time.time()
    completed = 0
    failed_ids = []

    print(f"\n📚 正在并行抓取 {total} 匹参赛马匹的历史战绩（{max_workers} 线程）...")

    # 建立 horse_id -> horse 索引
    horse_map = {h.get("id", ""): h for h in horses}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_horse = {
            executor.submit(
                _fetch_single_horse_history,
                horse,
                venue,
                distance,
                force_refresh
            ): horse
            for horse in horses
        }

        # 收集结果
        for future in as_completed(future_to_horse):
            completed += 1
            horse_id, hist_data = future.result()

            if horse_id and horse_id in horse_map:
                horse = horse_map[horse_id]
                horse["history"] = hist_data.get("history", [])
                horse["current_rating"] = hist_data.get("current_rating", 40)

                # 进度输出（每完成一个就更新）
                h_count = len(horse["history"])
                same_cond = sum(
                    1 for r in horse["history"]
                    if r.get("venue") == venue and abs(r.get("distance", 0) - distance) <= 200
                )
                print(
                    f"  [{completed:2d}/{total}] ✅ {horse['name']} "
                    f"({h_count}场历史, 评分{horse['current_rating']})"
                )
            else:
                failed_ids.append(horse_id)
                print(f"  [{completed:2d}/{total}] ❌ 抓取失败")

    elapsed = time.time() - start_time
    print(f"\n⏱️  历史战绩抓取完成: {completed} 匹 / 耗时 {elapsed:.1f}秒")
    if failed_ids:
        print(f"   失败马匹: {', '.join(failed_ids)}")

    return horses


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
    track_condition = normalize_condition(args.condition)
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
    race_payload = fetch_url_with_playwright(
        url,
        force_refresh=force_refresh,
        use_api_first=True,
        race_date=race_date,
        venue=venue,
        race_no=race_no,
    )

    if not race_payload:
        print("❌ 无法获取赛事数据，请检查日期/场地/场次是否正确。")
        return

    data_source = "页面抓取"
    if isinstance(race_payload, dict) and race_payload.get("source") == "api":
        all_horses = race_payload.get("horses", [])
        data_source = "HKJC API"
    else:
        html = race_payload
        all_horses = parse_race_entries(html, race_no=race_no)

    if not all_horses:
        print("⚠️  未能解析出参赛马匹，页面结构可能已变更。")
        return

    is_valid, warnings = validate_race_entries(all_horses, race_no=race_no)
    if warnings:
        for warning in warnings:
            print(f"⚠️  {warning}")
    if not is_valid and data_source == "页面抓取":
        return

    regular_horses = [h for h in all_horses if not h.get("is_reserve", False)]
    reserve_horses = [h for h in all_horses if h.get("is_reserve", False)]

    print(f"✅ 找到 {len(all_horses)} 匹参赛马匹（正选 {len(regular_horses)} 匹，后备 {len(reserve_horses)} 匹） | 来源：{data_source}")


    # 打印后备马信息
    if reserve_horses:
        reserve_names = [f"#{h['no']} {h['name']}" for h in reserve_horses]
        print(f"📋 后备马（正选退赛时递补）: {', '.join(reserve_names)}")

    # 动态推断班次区间（基于正选马）
    regular_horses = infer_class_range(regular_horses)

    # ── 抓取 HKJC 官方贴士指数 ─────────────────────────────────
    # ⚠️ 注意：tips_index 页面（tips_index.asp）无日期参数，总是显示"下一个赛马日"的贴士。
    # 若该页面的日期与目标场次日期不符，贴士数据无效——丢弃以避免错误信号。
    print(f"\n📊 正在抓取 HKJC 官方贴士指数...")
    tips_data = fetch_tips_index(force_refresh=force_refresh)
    tips_valid = False  # 默认无效，等日期校验通过后改为 True
    if tips_data.get("tips"):
        # 日期校验：检查 tips_index 页面是否显示目标日期的赛事
        tips_date = tips_data.get("race_info", {}).get("date", "")
        if tips_date:
            # tips_index 日期格式为 "DD/MM/YYYY"，转换为 "YYYY/MM/DD" 以便比较
            try:
                from datetime import datetime
                tips_date_normalized = datetime.strptime(tips_date, "%d/%m/%Y").strftime("%Y/%m/%d")
            except Exception:
                tips_date_normalized = tips_date
            if tips_date_normalized != race_date:
                print(f"⚠️  贴士指数日期不匹配（页面:{tips_date_normalized} ≠ 目标:{race_date}），忽略贴士数据")
                tips_data = {"tips": {}, "race_info": {}, "last_updated": None}
            else:
                tips_valid = True
        else:
            # race_info 为空（正则匹配失败），无法校验日期，谨慎起见也丢弃
            print("⚠️  贴士指数赛事信息提取失败（页面结构变更或正则不匹配），忽略贴士数据")
            tips_data = {"tips": {}, "race_info": {}, "last_updated": None}

    if tips_valid:
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

    # ── 抓取投注赔率 ─────────────────────────────────────────────
    print(f"💰 正在抓取投注赔率数据...")
    odds_data = fetch_race_odds(
        race_date=race_date,
        venue=venue,
        race_no=race_no,
        force_refresh=force_refresh
    )
    odds_status = odds_data.get("status", "unavailable")
    if odds_status == "ok":
        win_count = len(odds_data.get("win", {}))
        place_count = len(odds_data.get("place", {}))
        quinella_count = len(odds_data.get("quinella", {}))
        print(f"✅ 赔率已获取 | 独赢:{win_count} 位置:{place_count} 连赢:{quinella_count}")
        if odds_data.get("last_updated"):
            print(f"   更新时间: {odds_data['last_updated']}")
        # 打印独赢赔率摘要
        if odds_data.get("win"):
            win_sorted = sorted(odds_data["win"].items(), key=lambda x: x[1])
            top3 = [f"#{k[1:]}={v:.1f}" for k, v in win_sorted[:3]]
            print(f"   热门独赢（前3）: {', '.join(top3)}")
    else:
        print("⚠️  赔率未开盘或抓取失败（正常现象：赛前通常无赔率）")
    print()

    # ── 并行抓取每匹正选马历史战绩 ─────────────────────────────────
    regular_horses = fetch_all_horse_history(
        regular_horses,
        venue=venue,
        distance=distance,
        force_refresh=force_refresh,
        max_workers=8  # 并行8个线程
    )

    # ── 导入 analyze_horse（避免循环导入）───────────────────────
    from analyze import analyze_horse

    # ── 将赔率数据注入到每匹马（v1.4.12 增强：含全场赔率字典）─────────
    win_odds_map = odds_data.get("win", {})           # {"#1": 1.8, "#2": 21.0, ...}
    place_odds_map = odds_data.get("place", {})       # {"#1": 1.4, "#2": 4.0, ...}
    for horse in regular_horses:
        horse_key = f"#{horse['no']}"
        # v1.4.12 fix: 预测时将抓取到的赔率同时作为 opening_odds 存储，
        # 用于回测时 drift 对比（赛前预测快照 vs 赛前最终赔率）。
        # 若同一场次先后多次预测，最早一次的赔率才是真正的"开盘赔率"；
        # 此处取当前抓取的赔率，下次预测/回测时即可作为 opening_odds 参考。
        final_odds = win_odds_map.get(horse_key)
        horse["final_odds"] = final_odds              # 临场独赢赔率
        horse["place_odds"] = place_odds_map.get(horse_key)  # 位置赔率
        horse["opening_odds"] = final_odds            # v1.4.12: 当前赔率即为快照赔率
        horse["all_win_odds"] = win_odds_map              # 全场独赢赔率字典

    # 各维度评分（传入贴士指数数据）
    for horse in regular_horses:
        horse = analyze_horse(horse, venue, distance, track_condition, tips_data=tips_data)
        horse["total_score"] = calculate_total_score(horse, weights)

    # 概率计算（Softmax + 上限约束）
    # v1.4.12: 根据场内赔率离散度动态调整温度参数
    scores = [h["total_score"] for h in regular_horses]
    dyn_temp = dynamic_temperature(win_odds_map)
    print(f"🌡️  Softmax 温度（动态）: T={dyn_temp}（赔率离散度判断）")
    probs = softmax_probability(scores, temperature=dyn_temp)
    for horse, prob in zip(regular_horses, probs):
        horse["probability"] = prob

    # 输出结果（包含后备马作为信息参考）
    race_info = {"date": race_date, "venue": venue, "race": race_no}

    if args.output == "markdown":
        print("\n" + format_markdown_output(race_info, regular_horses, reserve_horses=reserve_horses))
    else:
        print(json.dumps({
            "race_info": race_info,
            "weights_used": weights,
            "regular_horses": regular_horses,  # 正选马预测结果
            "reserve_horses": reserve_horses,  # 后备马信息（仅基本信息）
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
