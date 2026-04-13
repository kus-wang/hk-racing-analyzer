#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
赛马分析工具 — 进化报告生成模块
==============================
职责：
  1. 对比预测存档与实际赛果，计算精度指标
  2. 生成结构化进化建议
  3. 渲染 Markdown 进化报告

由 daily_scheduler.py 调用。
"""

import os
import sys
from datetime import datetime

# 引入 config 读取实际参数值
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from config import SOFTMAX_TEMPERATURE

# ──────────────────────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────────────────────

def log(msg: str):
    from daily_scheduler import log as _log
    _log(msg)


# ──────────────────────────────────────────────────────────────
# Step 1 — 精度计算
# ──────────────────────────────────────────────────────────────

def compare_and_evolve(prediction_archive: dict, actual_results: dict) -> dict:
    """
    对比预测与实际结果，计算精度指标，返回回测报告。

    Args:
        prediction_archive: run_batch_predictions() 保存的存档
        actual_results:     fetch_actual_results() 返回的结果

    Returns:
        完整的 backtest_report 字典（含 meta、race_reports、evolution_suggestions）
    """
    meta       = prediction_archive.get("meta", {})
    races      = prediction_archive.get("races", {})
    date_str   = meta.get("date", "unknown")

    log(f"\n🔬 对比分析：{date_str}")

    # 动态导入（避免循环）
    from betting import check_bet_hit

    race_reports       = []
    total_top1_hits    = 0
    total_top3_hits    = 0
    total_races_done   = 0
    total_bet_hits     = 0
    bet_type_stats     = {}   # {"WIN": {"total": N, "hits": N}, ...}

    for race_no_str, pred in races.items():
        actual      = actual_results.get(race_no_str, [])
        if not actual:
            log(f"  场次 {race_no_str}：无实际结果，跳过")
            continue

        top3_pred   = pred.get("top3_predicted", [])
        top3_actual = [h["no"] for h in actual[:3] if h["pos"] <= 3]
        winner      = actual[0]["no"] if actual else None

        # 命中计算
        top1_hit      = (len(top3_pred) > 0 and str(top3_pred[0]) == str(winner))
        top3_hits_cnt = len(set(str(p) for p in top3_pred)
                           & set(str(a) for a in top3_actual))

        total_races_done += 1
        if top1_hit:
            total_top1_hits += 1
        total_top3_hits += top3_hits_cnt

        # ── 投注推荐命中验证 ──
        bet_rec   = pred.get("betting_recommendation")
        bet_result = None
        if bet_rec:
            bet_result    = check_bet_hit(bet_rec, actual)
            bet_type_key  = bet_rec.get("bet_type", "UNKNOWN")
            if bet_type_key not in bet_type_stats:
                bet_type_stats[bet_type_key] = {"total": 0, "hits": 0}
            bet_type_stats[bet_type_key]["total"] += 1
            if bet_result and bet_result.get("hit"):
                bet_type_stats[bet_type_key]["hits"] += 1
                total_bet_hits += 1

        # 评分偏差分析
        scores        = pred.get("scores", {})
        overestimated  = []
        underestimated = []

        if scores:
            sorted_pred = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            pred_ranking = {no: rank + 1 for rank, (no, _) in enumerate(sorted_pred)}

            for actual_h in actual[:3]:
                no = str(actual_h["no"])
                pred_rank = pred_ranking.get(no, 99)
                if pred_rank > 5:
                    underestimated.append({
                        "no": no, "pred_rank": pred_rank, "actual_pos": actual_h["pos"]
                    })

            for no, rank in pred_ranking.items():
                if rank <= 3 and str(no) not in [str(a["no"]) for a in actual[:3]]:
                    overestimated.append({"no": no, "pred_rank": rank})

        race_reports.append({
            "race_no":        race_no_str,
            "top3_predicted": [str(x) for x in top3_pred],
            "top3_actual":    top3_actual,
            "winner":         winner,
            "top1_hit":       top1_hit,
            "top3_hits":      top3_hits_cnt,
            "overestimated":  overestimated,
            "underestimated": underestimated,
            "bet_recommendation": bet_rec,
            "bet_result":         bet_result,
        })

        bet_status = "✅" if (bet_result and bet_result.get("hit")) else "❌"
        status     = "✅" if top1_hit else ("🔶" if top3_hits_cnt >= 2 else "❌")
        log(f"  场次 {race_no_str}：{status} 预测={top3_pred} 实际={top3_actual} "
            f"独赢命中={top1_hit} 投注={bet_status}")

    if total_races_done == 0:
        log("  ⚠ 无可对比场次")
        return {}

    top1_rate     = total_top1_hits  / total_races_done
    top3_rate     = total_top3_hits  / (total_races_done * 3)
    bet_hit_rate  = total_bet_hits  / total_races_done if total_races_done > 0 else 0

    log(f"\n📈 整体精度：独赢命中率 {top1_rate:.1%}，前3命中率 {top3_rate:.1%}")
    log(f"💰 投注推荐命中率：{bet_hit_rate:.1%}（{total_bet_hits}/{total_races_done}）")

    # 生成进化建议
    suggestions = _generate_evolution_suggestions(
        race_reports, top1_rate, top3_rate, bet_type_stats
    )

    return {
        "meta": {
            "date":           date_str,
            "venue":          meta.get("venue"),
            "venue_name":     meta.get("venue_name"),
            "total_races":   total_races_done,
            "top1_hit_count": total_top1_hits,
            "top3_hit_count": total_top3_hits,
            "top1_rate":     round(top1_rate, 4),
            "top3_rate":     round(top3_rate, 4),
            "bet_hit_count": total_bet_hits,
            "bet_hit_rate":  round(bet_hit_rate, 4),
            "bet_type_stats": bet_type_stats,
            "analyzed_at":   datetime.now().isoformat(),
        },
        "race_reports":          race_reports,
        "evolution_suggestions": suggestions,
    }


# ──────────────────────────────────────────────────────────────
# Step 2 — 进化建议生成
# ──────────────────────────────────────────────────────────────

def _generate_evolution_suggestions(
    race_reports: list,
    top1_rate: float,
    top3_rate: float,
    bet_type_stats: dict = None,
) -> list:
    """
    根据回测数据生成权重/逻辑优化建议（结构化格式）。
    不直接修改任何文件，结果供用户审阅后手动应用。
    """
    suggestions = []

    total_over  = sum(len(r["overestimated"])  for r in race_reports)
    total_under = sum(len(r["underestimated"]) for r in race_reports)
    total_races = len(race_reports)

    # 建议1：高估模式
    if total_over > total_races * 1.5:
        suggestions.append({
            "type":      "weight_adjust",
            "priority":  "high",
            "dimension": "general",
            "title":     "预测过于激进，高分马命中率偏低",
            "detail":    (
                f"共 {total_over} 匹马被高估（预测前3但未入前3）。"
                f"建议提高 Softmax 动态温度各档位（config fallback 4.0 → 4.5），"
                "使概率分布更均匀，降低极端预测的频率。"
            ),
            "code_change": {
                "file":    "probability.py",
                "param":   "dynamic_temperature() tiers",
                "current": "4.0/4.5/5.0/6.0",
                "proposed": "4.5/5.0/5.5/6.5",
            }
        })

    # 建议2：低估模式
    if total_under > total_races * 1.0:
        suggestions.append({
            "type":      "weight_adjust",
            "priority":  "medium",
            "dimension": "general",
            "title":     "冷门马低估严重，实际前3中有多匹预测靠后的马",
            "detail":    (
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

    # 建议3：独赢命中率阈值
    if top1_rate < 0.15:
        suggestions.append({
            "type":      "logic_review",
            "priority":  "high",
            "dimension": "top1",
            "title":     f"独赢命中率 {top1_rate:.1%} 低于基准（15%）",
            "detail":    (
                "独赢命中率持续低于随机基准（~1/马匹数量）。"
                "建议检查：① 赔率数据是否为临场值（非开盘）；"
                "② 历史战绩是否已按时间衰减加权；"
                "③ 配速分项是否仍仅基于跑法推导（缺实测数据）。"
            ),
            "code_change": None,
        })

    # 建议4：前3命中率阈值
    if top3_rate < 0.30:
        suggestions.append({
            "type":      "weight_adjust",
            "priority":  "medium",
            "dimension": "top3",
            "title":     f"前3命中率 {top3_rate:.1%} 低于基准（33%）",
            "detail":    (
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

    # 建议5：样本量提示
    if total_races < 3:
        suggestions.append({
            "type":      "info",
            "priority":  "low",
            "dimension": "general",
            "title":     f"当前累计仅 {total_races} 场回测，建议积累至 10 场后再调整权重",
            "detail":    (
                "权重优化需要足够的样本量。单日数据可能存在偶然性。"
                "建议观察 2-3 个赛马日（累计 20-30 场）后，再根据统计趋势调整。"
            ),
            "code_change": None,
        })

    # 建议6：投注推荐玩法命中率分析
    if bet_type_stats and total_races >= 3:
        bet_names_map = {"WIN": "独赢", "PLACE": "位置", "Q": "连赢", "TRIO": "三重彩"}
        low_rate_types = []
        for bt, stats in bet_type_stats.items():
            if stats["total"] >= 3:
                rate = stats["hits"] / stats["total"]
                if rate < 0.25:
                    name = bet_names_map.get(bt, bt)
                    low_rate_types.append(
                        f"{name}（{stats['hits']}/{stats['total']}，{rate:.0%}）"
                    )

        if low_rate_types:
            suggestions.append({
                "type":      "logic_review",
                "priority":  "medium",
                "dimension": "betting",
                "title":     f"投注推荐玩法命中率偏低：{', '.join(low_rate_types)}",
                "detail":    (
                    "部分投注玩法命中率持续偏低。"
                    "可能原因：① 场型判断阈值需要调整；"
                    "② 价值指数过滤不够严格；"
                    "③ 特定玩法本身命中率低（如三重彩理论命中率约5-8%），属于正常现象。"
                    "建议：观察更多场次后再决定是否调整场型判断参数。"
                ),
                "code_change": None,
            })

    return suggestions


# ──────────────────────────────────────────────────────────────
# Step 3 — Markdown 报告渲染
# ──────────────────────────────────────────────────────────────

def write_evolution_report(backtest_report: dict) -> str:
    """
    将 backtest_report 字典渲染为 Markdown，保存到 .evolution/ 目录，
    并打印到 stdout。

    Returns:
        报告文件路径。
    """
    _SKILL_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    EVOLUTION_DIR = os.path.join(_SKILL_DIR, ".evolution")
    os.makedirs(EVOLUTION_DIR, exist_ok=True)

    if not backtest_report:
        log("无回测数据，跳过报告生成")
        return ""

    meta       = backtest_report.get("meta", {})
    race_reports = backtest_report.get("race_reports", [])
    suggestions  = backtest_report.get("evolution_suggestions", [])

    date_str  = meta.get("date", "unknown")
    bet_names_map = {"WIN": "独赢", "PLACE": "位置", "Q": "连赢", "TRIO": "三重彩"}

    lines = [
        f"# 🔬 赛马预测回测报告 — {date_str} {meta.get('venue_name', '')}",
        "",
        f"> 预测场次：{meta.get('total_races', 0)}场 | "
        f"独赢命中：{meta.get('top1_hit_count', 0)}/{meta.get('total_races', 0)} "
        f"({meta.get('top1_rate', 0):.1%}) | "
        f"前3命中（平均每场）：{meta.get('top3_rate', 0):.1%} | "
        f"投注推荐命中：{meta.get('bet_hit_count', 0)}/{meta.get('total_races', 0)} "
        f"({meta.get('bet_hit_rate', 0):.1%})",
        "",
        "---",
        "",
        "## 📊 逐场对比",
        "",
        "| 场次 | 预测前3 | 实际前3 | 独赢 | 前3 | 投注推荐 | 投注命中 |",
        "|------|---------|---------|------|-----|----------|---------|",
    ]

    for r in race_reports:
        top1_icon = "✅" if r["top1_hit"] else "❌"
        bet_rec    = r.get("bet_recommendation")
        bet_result = r.get("bet_result")

        if bet_rec and bet_result:
            bt      = bet_rec.get("bet_type", "")
            bt_name = bet_names_map.get(bt, bt)
            sels    = " ".join(f"#{s}" for s in bet_rec.get("selections", []))
            bet_col     = f"{bt_name} {sels}"
            bet_hit_icon = "✅" if bet_result.get("hit") else "❌"
        else:
            bet_col     = "-"
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

    # ── 投注统计板块 ──
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
            total   = stats["total"]
            hits    = stats["hits"]
            rate    = f"{hits / total:.1%}" if total > 0 else "-"
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
            f"**类型**：{sug.get('type', '—')}  |  "
            f"**维度**：{sug.get('dimension', '—')}  |  "
            f"**优先级**：{sug.get('priority', '—')}",
            "",
            sug.get("detail", ""),
            "",
        ]
        cc = sug.get("code_change")
        if cc:
            lines += ["**具体改动**：", ""]
            if "param" in cc:
                lines.append(f"# 文件：{cc.get('file', '')}")
                lines.append(f"# 参数：{cc['param']}")
                lines.append(f"# 当前值：{cc.get('current')}")
                lines.append(f"# 建议值：{cc.get('proposed')}")
            elif "patch" in cc:
                lines.append(f"# 文件：{cc.get('file', '')}")
                lines.append(cc["patch"])
            lines += ["", ""]

    lines += [
        "---",
        "",
        f"*报告生成时间：{meta.get('analyzed_at', datetime.now().isoformat())}*",
        "",
        "> 如需将某条建议应用到 Skill，请回复：「应用建议 N」",
        "",
    ]

    report_text = "\n".join(lines)

    safe_date   = date_str.replace("/", "-")
    report_file = os.path.join(EVOLUTION_DIR, f"evolution_{safe_date}_{meta.get('venue', '')}.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_text)

    log(f"\n📝 进化报告已保存：{report_file}")
    print("\n" + "=" * 60)
    print(report_text)
    print("=" * 60)

    return report_file
