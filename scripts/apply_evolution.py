#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
进化建议应用工具
==============
用途：用户查看 .evolution/ 目录下的回测报告后，
      确认某条建议（如「应用建议 2」），由此脚本安全地
      将改动写入 analyze_race.py（带自动备份）。

用法：
  python apply_evolution.py --report .evolution/evolution_2026-03-31_ST.md --apply 2
  python apply_evolution.py --list                  # 列出所有待审阅的进化报告
  python apply_evolution.py --history               # 查看已应用的历史记录

⚠️  此脚本只修改 analyze_race.py，绝不直接修改 SKILL.md 或 analysis_weights.md。
    修改 SKILL.md / analysis_weights.md 需用户手动确认。
"""

import sys
import io
import os
import json
import re
import shutil
import argparse
from datetime import datetime

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
_SKILL_DIR    = os.path.dirname(_SCRIPT_DIR)
ARCHIVE_DIR   = os.path.join(_SKILL_DIR, ".archive")
EVOLUTION_DIR = os.path.join(_SKILL_DIR, ".evolution")
BACKUP_DIR    = os.path.join(_SKILL_DIR, ".backups")
HISTORY_FILE  = os.path.join(_SKILL_DIR, ".evolution", "applied_history.json")
ANALYZE_SCRIPT = os.path.join(_SCRIPT_DIR, "analyze_race.py")

os.makedirs(BACKUP_DIR, exist_ok=True)
os.makedirs(EVOLUTION_DIR, exist_ok=True)


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ──────────────────────────────────────────────────────────────
# 列出所有进化报告
# ──────────────────────────────────────────────────────────────

def list_reports():
    reports = sorted([
        f for f in os.listdir(EVOLUTION_DIR)
        if f.startswith("evolution_") and f.endswith(".md")
    ], reverse=True)

    if not reports:
        print("📭 暂无进化报告。等待第一次回测后自动生成。")
        return

    print(f"\n📋 共找到 {len(reports)} 份进化报告：\n")
    for i, r in enumerate(reports, 1):
        full = os.path.join(EVOLUTION_DIR, r)
        size = os.path.getsize(full)
        mtime = datetime.fromtimestamp(os.path.getmtime(full)).strftime("%Y-%m-%d %H:%M")
        print(f"  {i}. {r}  ({size//1024}KB, {mtime})")
    print()
    print("查看最新报告：")
    print(f"  python apply_evolution.py --report .evolution/{reports[0]}")


# ──────────────────────────────────────────────────────────────
# 应用某条建议
# ──────────────────────────────────────────────────────────────

def apply_suggestion(report_path: str, suggestion_index: int):
    """
    从回测报告 JSON（与 .md 同目录，同名 .json）中提取指定建议，
    安全应用到 analyze_race.py。
    """
    # 先找对应的 JSON 存档（回测报告）
    json_path = None
    if report_path.endswith(".md"):
        # 从 .md 文件名推断日期和场地 → 找对应的 backtest JSON
        m = re.search(r"evolution_(\d{4}-\d{2}-\d{2})_(ST|HV)", os.path.basename(report_path))
        if m:
            date_slug, venue = m.group(1), m.group(2)
            date_str = date_slug.replace("-", "/")
            candidate = os.path.join(ARCHIVE_DIR, f"{date_slug}_{venue}_backtest.json")
            if os.path.exists(candidate):
                json_path = candidate

    if not json_path:
        # 回退：直接从 .md 报告中解析建议（文本解析）
        log("⚠ 未找到对应 JSON 回测文件，尝试从 Markdown 解析建议...")
        sug = _parse_suggestion_from_md(report_path, suggestion_index)
    else:
        with open(json_path, encoding="utf-8") as f:
            backtest = json.load(f)
        suggestions = backtest.get("evolution_suggestions", [])
        if suggestion_index < 1 or suggestion_index > len(suggestions):
            log(f"❌ 建议编号 {suggestion_index} 无效（共 {len(suggestions)} 条）")
            return
        sug = suggestions[suggestion_index - 1]

    if not sug:
        log("❌ 无法解析建议内容")
        return

    print(f"\n📌 准备应用建议 {suggestion_index}：{sug.get('title', '')}")
    print(f"   类型：{sug.get('type')}  优先级：{sug.get('priority')}")
    print(f"   详情：{sug.get('detail', '')[:200]}...")

    cc = sug.get("code_change")
    if not cc:
        log("ℹ️ 此建议无具体代码改动（仅提示性建议），无需自动应用。")
        return

    print(f"\n   将修改：{cc.get('file')} / {cc.get('param') or cc.get('func')}")
    print(f"   当前值：{cc.get('current')}")
    print(f"   建议值：{cc.get('proposed')}")

    confirm = input("\n确认应用此改动？[y/N] ").strip().lower()
    if confirm != "y":
        log("已取消。")
        return

    # 备份
    _backup_analyze_script()

    # 应用改动
    success = _apply_code_change(cc)
    if success:
        _record_applied(sug, suggestion_index, report_path)
        log(f"✅ 建议 {suggestion_index} 已成功应用！")
        log(f"   备份位置：{BACKUP_DIR}")
        log("   如需回滚：python apply_evolution.py --rollback")
    else:
        log("❌ 应用失败，analyze_race.py 未被修改。")


def _backup_analyze_script():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = os.path.join(BACKUP_DIR, f"analyze_race_{ts}.py")
    shutil.copy2(ANALYZE_SCRIPT, backup)
    log(f"  📦 已备份：{backup}")
    return backup


def _apply_code_change(cc: dict) -> bool:
    """将 code_change 结构安全地应用到 analyze_race.py。"""
    if not os.path.exists(ANALYZE_SCRIPT):
        log(f"❌ 找不到文件：{ANALYZE_SCRIPT}")
        return False

    with open(ANALYZE_SCRIPT, encoding="utf-8") as f:
        content = f.read()

    param = cc.get("param")
    current_val = cc.get("current")
    proposed_val = cc.get("proposed")

    if param == "SOFTMAX_TEMPERATURE" and isinstance(proposed_val, (int, float)):
        old = f"SOFTMAX_TEMPERATURE = {current_val}"
        new = f"SOFTMAX_TEMPERATURE = {proposed_val}  # 由进化建议更新 {datetime.now().strftime('%Y-%m-%d')}"
        if old not in content:
            log(f"  ⚠ 未找到 '{old}'，尝试模糊匹配...")
            pattern = r"(SOFTMAX_TEMPERATURE\s*=\s*[\d.]+)"
            replacement = f"SOFTMAX_TEMPERATURE = {proposed_val}  # 由进化建议更新 {datetime.now().strftime('%Y-%m-%d')}"
            new_content = re.sub(pattern, replacement, content)
        else:
            new_content = content.replace(old, new, 1)
        content = new_content

    elif param == "DEFAULT_WEIGHTS" and isinstance(proposed_val, dict):
        # 逐个替换权重值
        for key, new_val in proposed_val.items():
            old_val = current_val.get(key) if isinstance(current_val, dict) else None
            if old_val is not None:
                # 匹配 "key": 0.xx 格式
                pattern = rf'("{key}"\s*:\s*){re.escape(str(old_val))}'
                replacement = rf'\g<1>{new_val}  # 进化更新'
                new_content = re.sub(pattern, replacement, content)
                if new_content != content:
                    content = new_content
                    log(f"    ✓ {key}: {old_val} → {new_val}")
                else:
                    log(f"    ⚠ {key} 未找到精确匹配，跳过")

    else:
        log(f"  ⚠ 暂不支持自动应用此类型改动（param={param}），请手动修改。")
        log(f"  建议值：{proposed_val}")
        return False

    with open(ANALYZE_SCRIPT, "w", encoding="utf-8") as f:
        f.write(content)

    return True


def _record_applied(sug: dict, index: int, report_path: str):
    """记录已应用的建议到历史文件。"""
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, encoding="utf-8") as f:
            history = json.load(f)

    history.append({
        "applied_at":  datetime.now().isoformat(),
        "index":       index,
        "title":       sug.get("title"),
        "type":        sug.get("type"),
        "report_path": report_path,
        "code_change": sug.get("code_change"),
    })

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def _parse_suggestion_from_md(md_path: str, index: int) -> dict | None:
    """从 Markdown 报告中提取指定编号的建议（降级方案）。"""
    if not os.path.exists(md_path):
        return None
    with open(md_path, encoding="utf-8") as f:
        content = f.read()
    # 简单提取标题
    sections = re.split(r"###\s+[🔴🟡🟢ℹ️]+\s+建议\s+\d+：", content)
    if len(sections) > index:
        block = sections[index]
        title_match = re.search(r"建议\s+" + str(index) + r"：(.+)", content)
        title = title_match.group(1).strip() if title_match else "未知"
        return {"title": title, "detail": block[:300], "code_change": None, "type": "unknown"}
    return None


# ──────────────────────────────────────────────────────────────
# 查看应用历史
# ──────────────────────────────────────────────────────────────

def show_history():
    if not os.path.exists(HISTORY_FILE):
        print("📭 暂无应用历史。")
        return
    with open(HISTORY_FILE, encoding="utf-8") as f:
        history = json.load(f)
    print(f"\n📜 已应用 {len(history)} 条进化建议：\n")
    for h in history:
        print(f"  [{h['applied_at'][:10]}] 建议{h['index']}: {h['title']}")
        cc = h.get("code_change")
        if cc:
            print(f"    → {cc.get('param') or cc.get('func')}: {cc.get('current')} → {cc.get('proposed')}")
    print()


# ──────────────────────────────────────────────────────────────
# 回滚
# ──────────────────────────────────────────────────────────────

def rollback():
    backups = sorted([
        f for f in os.listdir(BACKUP_DIR)
        if f.startswith("analyze_race_") and f.endswith(".py")
    ], reverse=True)

    if not backups:
        print("📭 无可用备份。")
        return

    latest = backups[0]
    print(f"\n🔄 最近备份：{latest}")
    confirm = input("确认回滚到此备份？[y/N] ").strip().lower()
    if confirm == "y":
        shutil.copy2(os.path.join(BACKUP_DIR, latest), ANALYZE_SCRIPT)
        log(f"✅ 已回滚到 {latest}")
    else:
        log("已取消。")


# ──────────────────────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="进化建议应用工具")
    parser.add_argument("--list",     action="store_true", help="列出所有进化报告")
    parser.add_argument("--history",  action="store_true", help="查看已应用历史")
    parser.add_argument("--rollback", action="store_true", help="回滚最近一次改动")
    parser.add_argument("--report",   help="指定报告文件路径（.md）")
    parser.add_argument("--apply",    type=int, help="应用指定编号的建议")
    args = parser.parse_args()

    if args.list:
        list_reports()
    elif args.history:
        show_history()
    elif args.rollback:
        rollback()
    elif args.report and args.apply:
        apply_suggestion(args.report, args.apply)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
