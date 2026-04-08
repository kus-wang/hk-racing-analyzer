#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
临时 wrapper：运行 daily_scheduler backtest 并将输出写到日志文件
用法：python _run_backtest.py
"""
import subprocess
import sys
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
log_path = os.path.join(script_dir, "_backtest_output.txt")

with open(log_path, "w", encoding="utf-8") as f:
    proc = subprocess.run(
        [sys.executable, os.path.join(script_dir, "daily_scheduler.py"), "--mode", "backtest"],
        stdout=f,
        stderr=subprocess.STDOUT,
        cwd=os.path.dirname(script_dir),
        encoding="utf-8",
        errors="replace",
        text=True,
    )

with open(log_path, encoding="utf-8", errors="replace") as f:
    content = f.read()

print(content)
print(f"\n=== EXIT CODE: {proc.returncode} ===")
