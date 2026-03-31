#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
香港赛马分析脚本（v1.4.0 - 模块化重构版）

基于历史战绩（同条件精准匹配）、赔率走势、配速分段等数据进行量化分析。

模块化结构（v1.4.0）：
- config.py   : 配置常量（URL、缓存TTL、权重默认值）
- weights.py  : 权重计算
- probability.py: 概率计算（Softmax）
- scoring.py  : 评分函数
- cache.py    : 缓存管理
- fetch.py    : 数据抓取
- parse.py    : HTML解析
- analyze.py  : 马匹分析
- output.py   : 输出格式化
- main.py     : 主程序入口

直接运行此文件或运行 main.py 效果相同。
"""

# 入口兼容层：直接调用 main 模块
from main import main

if __name__ == "__main__":
    main()
