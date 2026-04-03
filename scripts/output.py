#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HKJC 赛马分析工具 - 输出格式化模块

提供 Markdown 和 JSON 格式的分析报告输出。
"""

from datetime import datetime


def format_markdown_output(race_info, horses, reserve_horses=None):
    """生成 Markdown 格式分析报告（含历史战绩摘要与分项评分）

    参数：
        race_info       : 赛事信息字典
        horses          : 正选马列表（已评分）
        reserve_horses  : 后备马列表（基本信息，不评分）
    """
    venue_name = "沙田" if race_info["venue"] == "ST" else "跑马地"
    lines = []

    lines.append(f"## 🏇 {race_info['date']} {venue_name} 第{race_info['race']}场 分析报告\n")
    lines.append("### ⚠️ 风险提示")
    lines.append("> 本分析基于历史数据，仅供技术参考，**不构成任何投注建议**。赛马投注有风险，请理性参与。\n")

    sorted_horses = sorted(horses, key=lambda x: x["total_score"], reverse=True)

    # ── 前3名概率预测 ──────────────────────────────────────────────
    lines.append("### 📊 前3名概率预测\n")
    lines.append("| 排名 | 马号 | 马名 | 评分 | 胜出概率 | 贴士指数 | 数据充足度 | 惯用跑法 | 历史战绩 | 分析要点 |")
    lines.append("|:--:|:--:|:--|:--:|:--:|:--:|:--:|:--:|:--|:--|")

    for i, h in enumerate(sorted_horses[:3], 1):
        # 历史战绩摘要
        hist = h.get("history", [])
        hist_summary = f"{len(hist)}场" if hist else "无记录"
        wins = sum(1 for r in hist if r.get("position") == 1)
        top3 = sum(1 for r in hist if r.get("position", 99) <= 3)
        if hist:
            hist_summary = f"{len(hist)}场 {wins}冠{top3}连"

        # 跑法
        run_style_map = {"front": "领跑", "closer": "后上", "even": "中间"}
        run_style = run_style_map.get(h.get("running_style", "even"), "中间")

        # 贴士指数显示
        tips_val = h.get("tips_index")
        tips_display = f"{tips_val:.1f}" if tips_val else "-"

        # 分析要点
        reason = f"赔率{h.get('final_odds', '-')}"
        if h["history_same_condition_score"] >= 60:
            reason += "，同条件有佳绩"
        if h["odds_drift_score"] >= 70:
            reason += "，赔率走势积极"
        if tips_val and tips_val < 5:
            reason += f"，贴士热门({tips_val:.1f})"
        elif tips_val and tips_val >= 99:
            reason += "，无贴士"
        if h.get("longshot_alert"):
            reason += "，⚡冷门关注"

        lines.append(
            f"| {i} | {h['no']} | {h['name']} | {h['total_score']:.1f} "
            f"| **{h['probability']:.1f}%** | {tips_display} "
            f"| {h['confidence']} | {run_style} | {hist_summary} | {reason} |"
        )

    # ── 全场分项评分表 ──────────────────────────────────────────────
    lines.append("\n### 📋 全场分项评分（各维度0-100）\n")
    lines.append("| 马号 | 马名 | 综合 | 历史同条件 | 历史同场 | 班次适配 | 赔率 | 赔率走势 | 配速 | 档位 | 贴士指数 | 专家 |")
    lines.append("|:--:|:--|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|")

    for h in sorted_horses:
        lines.append(
            f"| {h['no']} | {h['name']} | {h['total_score']:.1f} "
            f"| {h['history_same_condition_score']} "
            f"| {h['history_same_venue_score']} "
            f"| {h['class_fit_score']} "
            f"| {h['odds_value_score']} "
            f"| {h['odds_drift_score']} "
            f"| {h['sectional_score']} "
            f"| {h['barrier_score']} "
            f"| {h['tips_index_score']} "
            f"| {h['expert_score']} |"
        )

    # ── 冷门关注 ──────────────────────────────────────────────────
    alerts = [h for h in horses if h.get("longshot_alert")]
    if alerts:
        lines.append("\n### 🔍 冷门关注\n")
        for h in alerts:
            lines.append(
                f"- **{h['no']}号 {h['name']}**（赔率 {h.get('final_odds', '-')}）："
                f"有同条件前3记录，赔率未拉长，班次适配度 {h['class_fit_score']}"
            )

    # ── 后备马信息 ────────────────────────────────────────────────
    if reserve_horses:
        lines.append("\n### 📋 后备马（正选退赛时递补）\n")
        lines.append("| 马号 | 马名 | 评分 | 练马师 |")
        lines.append("|:--:|:--|:--:|:--|")
        for h in reserve_horses:
            lines.append(
                f"| {h['no']} | {h['name']} | {h.get('current_rating', '-')} | {h.get('trainer', '-')} |"
            )
        lines.append("\n> ⚠️ 后备马不参与预测评分，仅作信息参考。若正选马退赛，后备马将递补参与竞猜。")

    # ── 投注建议 ──────────────────────────────────────────────────
    # 投注判断逻辑见 SKILL.md（AI 根据概率分布自主推荐）
    lines.append("\n### 💡 投注建议（仅供参考）\n")
    if sorted_horses:
        w = sorted_horses[0]
        lines.append(f"**推荐独赢**: {w['no']}号 {w['name']}（概率 {w['probability']:.1f}%，评分 {w['total_score']:.1f}）")
    if len(sorted_horses) >= 2:
        q0, q1 = sorted_horses[0], sorted_horses[1]
        lines.append(f"**推荐连赢**: {q0['no']}, {q1['no']}（{q0['name']} + {q1['name']}）")
    if len(sorted_horses) >= 3:
        lines.append(
            f"**推荐三重彩**: {sorted_horses[0]['no']}, {sorted_horses[1]['no']}, {sorted_horses[2]['no']}"
        )

    lines.append("\n---")
    lines.append(f"*数据来源：香港赛马会 (HKJC) | 分析时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}*")

    return "\n".join(lines)
