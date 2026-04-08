#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
香港赛马 — 每日自动化调度脚本
============================
职责：
  1. 检测明天/今天是否为赛马日
  2. 赛马日前一天 → 批量预测所有场次，保存预测存档
  3. 赛马日当天赛后 → 抓取实际结果，对比预测，计算精度，生成进化报告

用法（由 WorkBuddy 定时任务调用）：
  python daily_scheduler.py --mode predict   # 批量预测
  python daily_scheduler.py --mode backtest # 回测
  python daily_scheduler.py                  # 自动判断

模块结构：
  scheduler_cache.py  — HTTP 缓存 + HTML 抓取
  race_day.py         — 赛马日检测
  race_results.py     — 实际赛果抓取 + 解析
  evolution_report.py — 精度计算 + 进化建议生成 + Markdown 报告
"""

import os
import sys
import io
import json
import argparse
from datetime import datetime, timedelta

if sys.platform == "win32":
    # 仅在 stdout 是真实终端（有 buffer 属性且未被重定向）时才重包装
    # 避免在 subprocess capture_output 或管道重定向时因 TextIOWrapper 双重包装崩溃
    try:
        if hasattr(sys.stdout, "buffer") and sys.stdout.buffer is not None:
            import io as _io
            new_stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
            sys.stdout = new_stdout
    except Exception:
        pass
    try:
        if hasattr(sys.stderr, "buffer") and sys.stderr.buffer is not None:
            import io as _io
            new_stderr = _io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
            sys.stderr = new_stderr
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────
# 路径配置
# ──────────────────────────────────────────────────────────────
_SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR    = os.path.dirname(_SCRIPT_DIR)
ARCHIVE_DIR   = os.path.join(_SKILL_DIR, ".archive")      # 预测存档
COMPLETED_DIR = os.path.join(ARCHIVE_DIR, "completed")     # 已回测完成的存档
EVOLUTION_DIR = os.path.join(_SKILL_DIR, ".evolution")     # 进化建议报告

for d in [ARCHIVE_DIR, COMPLETED_DIR, EVOLUTION_DIR]:
    os.makedirs(d, exist_ok=True)

# ──────────────────────────────────────────────────────────────
# 日志
# ──────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ──────────────────────────────────────────────────────────────
# 存档工具
# ──────────────────────────────────────────────────────────────

def _archive_path(date_str: str, venue: str, suffix: str) -> str:
    safe_date = date_str.replace("/", "-")
    return os.path.join(ARCHIVE_DIR, f"{safe_date}_{venue}_{suffix}.json")


def load_prediction_archive(date_str: str, venue: str) -> dict | None:
    """
    加载指定日期的预测存档（优先原位置，若已归档则从 completed 目录加载）。
    """
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
    将已回测完成的预测存档移入 completed 目录，防止被后续回测重复加载。
    """
    src = _archive_path(date_str, venue, "prediction")
    if not os.path.exists(src):
        log(f"  ⚠ 预测存档不存在，无需归档：{src}")
        return False

    dst = os.path.join(COMPLETED_DIR, os.path.basename(src))
    try:
        if os.path.exists(dst):
            os.remove(dst)
        os.rename(src, dst)
        log(f"  ✅ 预测存档已归档：{dst}")
        return True
    except Exception as e:
        log(f"  ⚠ 归档失败：{e}")
        return False


# ──────────────────────────────────────────────────────────────
# 批量预测（编排层）
# ──────────────────────────────────────────────────────────────

def run_batch_predictions(race_info: dict) -> dict:
    """
    对指定赛马日的所有场次运行预测，返回预测存档字典。
    存档格式：
      {
        "meta": {"date": ..., "venue": ..., "total_races": ..., "predicted_at": ...},
        "races": {
          "1": {"horses": [...], "top3_predicted": [...], ...},
          ...
        }
      }
    """
    from race_day import detect_race_day  # noqa: F401（模块级导入用于 --mode predict 独立调用）
    import subprocess

    date_str    = race_info["date"]
    venue       = race_info["venue"]
    total_races = race_info["total_races"]

    log(f"\n🏇 开始批量预测：{date_str} {race_info['venue_name']} 共 {total_races} 场")

    archive = {
        "meta": {
            "date":        date_str,
            "venue":       venue,
            "venue_name":  race_info["venue_name"],
            "total_races": total_races,
            "predicted_at": datetime.now().isoformat(),
        },
        "races": {}
    }

    analyze_script = os.path.join(_SCRIPT_DIR, "analyze_race.py")

    for race_no in range(1, total_races + 1):
        result = _run_single_prediction(analyze_script, date_str, venue, race_no, total_races)
        if result:
            archive["races"][str(race_no)] = result
            _log_prediction_result(result)
        else:
            log(f"     ⚠ 第 {race_no}/{total_races} 场预测失败，跳过")

    archive_file = _archive_path(date_str, venue, "prediction")
    with open(archive_file, "w", encoding="utf-8") as f:
        json.dump(archive, f, ensure_ascii=False, indent=2)
    log(f"\n✅ 预测存档已保存：{archive_file}")

    return archive


def _run_single_prediction(
    script_path: str, date_str: str, venue: str, race_no: int, total_races: int
) -> dict | None:
    """
    调用 analyze_race.py 对单场进行预测，解析 JSON 输出。
    """
    import subprocess
    log(f"  → 预测第 {race_no}/{total_races} 场...")

    cmd = [
        sys.executable, script_path,
        "--date",  date_str,
        "--venue", venue,
        "--race",  str(race_no),
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

        # 从混合输出中提取 JSON（以 { 开头，以 } 结尾的最大块）
        json_str = _extract_json_block(output)
        if not json_str:
            log(f"     ⚠ 未找到 JSON 块")
            return _fallback_parse_output(output)

        data = json.loads(json_str)

        # 提取前3预测（按 total_score 降序）
        horses = data.get("regular_horses") or data.get("horses", [])
        sorted_horses = sorted(horses, key=lambda h: h.get("total_score", 0), reverse=True)
        top3 = [h.get("horse_no") or h.get("no") for h in sorted_horses[:3]]

        # 生成投注推荐
        from betting import determine_bet_type
        bet_rec = determine_bet_type(sorted_horses)

        # v1.4.13 fix: 用 predicted_odds_snapshot 回填各马的 opening_odds，
        # 使 odds_drift_score 在回测时能正确计算（之前 18% drift 权重一直空转）
        odds_snapshot = data.get("predicted_odds_snapshot", {})
        for h in horses:
            no = str(h.get("horse_no") or h.get("no") or "")
            if no in odds_snapshot:
                h["opening_odds"] = odds_snapshot[no]

        return {
            "horses":                   horses,
            "top3_predicted":           top3,
            "scores": {
                str(h.get("horse_no") or h.get("no")): h.get("total_score", 0)
                for h in horses
            },
            "probabilities": {
                str(h.get("horse_no") or h.get("no")): h.get("probability", 0)
                for h in horses
            },
            "predicted_odds_snapshot": {
                str(h.get("horse_no") or h.get("no")): h.get("final_odds")
                for h in horses if h.get("final_odds") is not None
            },
            "betting_recommendation": bet_rec,
            "raw_output":             data,
        }

    except subprocess.TimeoutExpired:
        log(f"     ⚠ 超时（120s），跳过")
        return None
    except json.JSONDecodeError as e:
        log(f"     ⚠ JSON 解析失败：{e}")
        return _fallback_parse_output(proc.stdout if 'proc' in dir() else "")
    except Exception as e:
        log(f"     ⚠ 异常：{e}")
        return None


def _log_prediction_result(result: dict):
    """打印单场预测结果的简洁摘要。"""
    top3 = result.get("top3_predicted", [])
    bet  = result.get("betting_recommendation")
    if bet:
        bet_map   = {"WIN": "独赢", "PLACE": "位置", "Q": "连赢", "TRIO": "三重彩"}
        bet_name  = bet_map.get(bet.get("bet_type", ""), bet.get("bet_type", ""))
        sels      = " ".join(f"#{s}" for s in bet.get("selections", []))
        log(f"     预测前3：{top3}  |  推荐：{bet_name} {sels}")
    else:
        log(f"     预测前3：{top3}")


def _extract_json_block(text: str) -> str | None:
    """从混合输出（日志 + JSON）中提取最大的合法 JSON 对象块。"""
    import json as _json
    start = text.find('{')
    end   = text.rfind('}')
    if start == -1 or end == -1 or end <= start:
        return None
    candidate = text[start:end + 1]
    try:
        _json.loads(candidate)
        return candidate
    except _json.JSONDecodeError:
        # 逐行尝试找合法 JSON 段
        lines = text.splitlines()
        for i in range(len(lines)):
            if lines[i].strip().startswith('{'):
                for j in range(len(lines), i, -1):
                    block = "\n".join(lines[i:j])
                    try:
                        _json.loads(block)
                        return block
                    except _json.JSONDecodeError:
                        continue
    return None


def _fallback_parse_output(text: str) -> dict | None:
    """从 markdown 格式输出中提取预测前3名（降级方案）。"""
    import re
    if not text:
        return None
    rows = re.findall(r"\|\s*\d+\s*\|\s*(\d+)\s*\|", text)
    if rows:
        return {"top3_predicted": rows[:3], "horses": [], "scores": {}, "probabilities": {}}
    return None


# ──────────────────────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────────────────────

def main():
    from race_day       import detect_race_day
    from race_results   import fetch_actual_results
    from evolution_report import compare_and_evolve, write_evolution_report

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
    args  = parser.parse_args()
    now   = datetime.now()
    mode  = args.mode

    if mode == "auto":
        hour = now.hour
        if hour < 12:
            mode = "backtest"
        elif hour < 20:
            mode = "predict"
        else:
            mode = "backtest"
        log(f"⏱ 当前时间 {now.strftime('%H:%M')}，自动模式 → {mode}")

    # ── 预测模式 ──
    if mode == "predict":
        if args.date:
            target_date = args.date
            race_info = detect_race_day(target_date)
            if race_info:
                run_batch_predictions(race_info)
            else:
                log(f"{target_date} 不是赛马日，无需预测。结束。")
        else:
            # 依次检测今天和明天
            today_str     = now.strftime("%Y/%m/%d")
            tomorrow_str  = (now + timedelta(days=1)).strftime("%Y/%m/%d")

            race_info = detect_race_day(today_str)
            target_label = f"今天（{today_str}）"
            target_date = today_str

            if not race_info:
                race_info = detect_race_day(tomorrow_str)
                target_label = f"明天（{tomorrow_str}）"
                target_date = tomorrow_str

            if race_info:
                run_batch_predictions(race_info)
            else:
                log(f"{target_label}不是赛马日，无需预测。结束。")

    # ── 回测模式 ──
    elif mode == "backtest":
        if args.date:
            target_date = args.date
        else:
            today_str     = now.strftime("%Y/%m/%d")
            yesterday_str = (now - timedelta(days=1)).strftime("%Y/%m/%d")

            archive = (
                load_prediction_archive(today_str, "ST")
                or load_prediction_archive(today_str, "HV")
                or load_prediction_archive(yesterday_str, "ST")
                or load_prediction_archive(yesterday_str, "HV")
            )
            if archive:
                target_date = archive["meta"].get("date", today_str)
            else:
                log("未找到预测存档，跳过回测。（可能今天/昨天均非赛马日）")
                return

        # 获取 race_info
        archive = None
        race_info = detect_race_day(target_date)
        if not race_info:
            log(f"{target_date} 不是赛马日，无法回测。")
            return

        archive = load_prediction_archive(target_date, race_info.get("venue", "ST"))
        if not archive:
            log(f"未找到 {target_date} 的预测存档，无法回测（可能当天未运行预测模式）。")
            return

        # 抓取实际赛果
        actual_results = fetch_actual_results(race_info)
        if not actual_results:
            log("未能获取实际赛果，可能赛事尚未结束或网页结构变化。")
            return

        # 对比分析
        backtest_report = compare_and_evolve(archive, actual_results)

        # 保存回测 JSON
        report_file = _archive_path(target_date, race_info.get("venue", "ST"), "backtest")
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(backtest_report, f, ensure_ascii=False, indent=2)

        # 输出 Markdown 进化报告
        write_evolution_report(backtest_report)

        # 归档已完成预测存档
        _archive_completed_prediction(target_date, race_info.get("venue", "ST"))


if __name__ == "__main__":
    main()
