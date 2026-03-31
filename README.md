# 🏇 香港赛马分析器 / HK Racing Analyzer

> Data-driven horse racing prediction tool for HKJC races. Data-powered analysis combining historical performance, odds trends, sectional timing, jockey/trainer stats, and expert consensus — delivering top-3 probability distribution and betting recommendations.
>
> 港马数据驱动预测工具，基于历史战绩、赔率走势、配速分段、骑练数据、专家共识等多维数据，提供前3名概率预测与投注建议。

[![GitHub Stars](https://img.shields.io/github/stars/kus-wang/hk-racing-analyzer?style=flat-square)](https://github.com/kus-wang/hk-racing-analyzer)
[![License](https://img.shields.io/github/license/kus-wang/hk-racing-analyzer?style=flat-square)](LICENSE)

---

## 📌 功能特点 / Features

| 中文 | English |
|------|---------|
| 多维度量化分析，权重可配置 | Multi-dimensional quantitative analysis with configurable weights |
| HKJC 官方数据实时抓取 | Real-time HKJC official data scraping |
| 磁盘缓存机制，避免重复请求 | Disk caching to avoid redundant network requests |
| 每日自动化：赛前预测 + 赛后回测 | Daily automation: pre-race predictions + post-race backtesting |
| 自我进化引擎：根据回测结果迭代优化 | Self-evolution engine: iterative optimization based on backtesting |
| HKJC 官方贴士指数参考 | HKJC official Tips Index as core signal |

---

## 🔬 分析维度 / Analysis Dimensions

### 主要维度（Primary）— 权重最高 / Highest Weight

| 维度 / Dimension | 数据来源 / Data Source | 分析要点 / Key Points |
|-----------------|----------------------|----------------------|
| 马匹历史战绩 / Horse History | HKJC 马匹档案 / Horse Profile | 近5/10场成绩、同场地、同距离表现 / Last 5/10 races, same venue & distance |
| 赔率走势 / Odds Trends | HKJC 赔率页面 / Odds Page | 开盘赔率 vs 临场赔率变化 / Opening vs. final odds movement |
| 配速分段 / Sectional Timing | HKJC 赛果页面 / Race Results | 前段速度、后段冲刺、综合分段 / Early speed, late sprint, sectional times |

### 辅助维度（Secondary）— 次要因素 / Secondary Factors

| 维度 / Dimension | 数据来源 / Data Source | 分析要点 / Key Points | 权重 / Weight |
|-----------------|----------------------|----------------------|:--------:|
| 骑师胜率 / Jockey Win Rate | 马匹历史战绩（动态统计）/ Dynamic from history | 骑师骑乘本马历史胜率/前3率 / This jockey's record with this horse | 5% |
| 练马师胜率 / Trainer Win Rate | 马匹历史战绩（动态统计）/ Dynamic from history | 练马师带本马历史胜率/前3率 / This trainer's record with this horse | 4% |
| 档位分析 / Barrier Analysis | 历史统计 / Historical Stats | 同距离不同档位胜率 / Win rate by barrier at same distance | 5% |
| 场地偏好 / Track Preference | 马匹档案 / Horse Profile | 草地/泥地、好地/快地表现 / Turf/Dirt, Good/Fast track performance | — |
| HKJC 贴士指数 / Tips Index | HKJC 官方贴士页面 / Official Tips Index | 市场共识信号，高于外部专家 / Market consensus signal, higher than external experts | 6% |
| 外部专家预测 / Expert Predictions | 网络搜索 / Web Search | 马评人共识度参考 / Expert consensus as supplementary reference | 4% |

> 📊 当前默认总权重分配：历史战绩 31% · 赔率 28% · 配速 15% · 骑师 5% · 练马师 4% · 档位 5% · 贴士指数 6% · 专家 4%
>
> Current default weights: history 31% · odds 28% · pace 15% · jockey 5% · trainer 4% · barrier 5% · tips index 6% · expert 4%

---

## 🚀 快速开始 / Quick Start

### 环境依赖 / Requirements

- Python 3.10+
- `requests`, `beautifulsoup4`, `lxml`
- `playwright`（用于动态 JS 渲染页面的数据抓取）
- OpenClaw + SkillHub（AI Agent 运行时环境）

```bash
# 安装依赖 / Install dependencies
pip install requests beautifulsoup4 lxml playwright
playwright install chromium  # 安装 Chromium 浏览器驱动

# 分析今天沙田第3场 / Analyze Sha Tin Race 3 today
python scripts/analyze_race.py --venue ST --race 3

# 分析指定日期跑马地第5场 / Analyze Happy Valley Race 5 on a specific date
python scripts/analyze_race.py --date 2026/03/30 --venue HV --race 5

# 强制刷新所有缓存重新抓取 / Force refresh all cache and re-scrape
python scripts/analyze_race.py --venue ST --race 3 --force-refresh

# 清除当前场次缓存 / Clear cache for current race
python scripts/analyze_race.py --venue ST --race 3 --clear-cache

# 查看缓存统计 / Show cache statistics
python scripts/analyze_race.py --cache-stats
```

### 缓存说明 / Caching

| 数据类型 / Data Type | TTL | 说明 / Notes |
|---------------------|-----|--------------|
| 历史赛果 / Historical results | 7 天 / days | 赛果不变，长期缓存 / Results never change |
| 当日排位表 / Race card (pre-race) | 30 分钟 / min | 可能临时换马/骑师 / May change due to scratcher |
| 马匹历史 / Horse history | 24 小时 / hrs | 每场赛后更新 / Updated after each race |
| 赔率数据 / Odds data | 5 分钟 / min | 临场实时变化 / Real-time near post time |
| 其他页面 / Other pages | 1 小时 / hr | 兜底 TTL / Fallback TTL |

---

## ⚙️ 自动化任务 / Automation

| 任务名 / Task | 时间 / Time | 功能 / Function |
|--------------|-----------|----------------|
| 赛马日预测 / Racing Day Prediction | 每日 14:30 / Daily 14:30 | 检测明天赛马日 → 批量预测所有场次 → 保存到 `.archive/` |
| 回测与进化分析 / Backtest & Evolution | 每日 09:00 / Daily 09:00 | 抓取昨日实际赛果 → 对比预测 → 生成进化建议到 `.evolution/` |

### 进化工作流 / Evolution Workflow

```
[14:30] 检测赛马日 → 批量预测 → .archive/存档
                  ↓ (次日 09:00)
[09:00] 抓取实际赛果 → 对比预测 → .evolution/进化建议
                  ↓ (用户审阅确认 / User Review)
$ python scripts/apply_evolution.py --report .evolution/xxx.md --apply N
                  ↓ (应用后自动备份 / Auto backup before apply)
$ python scripts/apply_evolution.py --rollback  # 如需回滚 / If needed
```

---

## 📁 目录结构 / Directory Structure

```
hk-racing-analyzer/
├── SKILL.md                      # 中文 Skill 说明（主）/ CN skill documentation
├── SKILL_EN.md                  # English Skill documentation
├── README.md                     # 本文件 / This file
├── RELEASE_NOTES.md              # 更新日志 / Release notes
├── scripts/
│   ├── analyze_race.py            # 主分析脚本（向后兼容入口层）/ Main entry point (backward compatible)
│   ├── daily_scheduler.py         # 每日自动化调度 / Daily automation scheduler
│   ├── apply_evolution.py         # 进化建议应用工具 / Evolution apply tool
│   ├── dump_race.py              # 缓存数据转储（调试）/ Cache dump (debug)
│   ├── main.py                    # CLI 主入口（模块化重构后）/ CLI main entry
│   ├── config.py                  # 配置常量与参数 / Configuration constants
│   ├── weights.py                 # 权重加载与场景自适应 / Weight loading & scenario adaptation
│   ├── probability.py             # Softmax 概率归一化 / Softmax probability normalization
│   ├── scoring.py                 # 各维度评分引擎 / Per-dimension scoring engine
│   ├── cache.py                    # 磁盘缓存管理 / Disk cache management
│   ├── fetch.py                   # HKJC 数据抓取 / HKJC data fetching
│   ├── parse.py                   # HTML 解析与数据提取 / HTML parsing & extraction
│   ├── analyze.py                 # 综合分析与评分汇总 / Analysis & score aggregation
│   └── output.py                  # 报告输出与格式化 / Report generation & formatting
├── references/
│   ├── hkjc_urls.md              # HKJC URL 参考 / HKJC URL reference
│   ├── analysis_weights.md       # 各维度权重配置 / Weight configuration
│   └── expert_sources.md         # 专家预测来源 / Expert sources
├── .archive/                     # [自动生成] 预测存档 / [Auto] Prediction archives
├── .evolution/                  # [自动生成] 进化建议 / [Auto] Evolution proposals
└── .backups/                    # [自动生成] 备份 / [Auto] Backup files
```

---

## 📊 预测报告示例 / Sample Output

```
## 🏇 2026-03-29 沙田 第3场 分析报告

### 📊 前3名概率预测

| 排名 | 马号 | 马名 | 胜出概率 | 评分 |
|------|------|------|----------|------|
| 1 | 8 | 浪漫勇士 | 32% | 87 |
| 2 | 3 | 金钻快线 | 21% | 78 |
| 3 | 5 | 飞龙在天 | 16% | 71 |

### 💡 投注建议

**推荐独赢**: 8号 浪漫勇士
**推荐连赢**: 8, 3
**冷门关注**: ⚡ 5号 飞龙在天（赔率18，状态回升）
```

---

## ⚠️ 免责声明 / Disclaimer

- 本工具仅供娱乐与学习参考，不构成投注建议
- This tool is for entertainment and learning reference only, not betting advice
- 赛马结果受多种不确定因素影响，历史数据不代表未来表现
- Racing results are affected by many uncertain factors; past performance does not guarantee future outcomes
- 请理性参与，量力而行
- Please participate rationally and bet responsibly
- 所有数据来自香港赛马会官方网站 (HKJC)
- All data sourced from the Hong Kong Jockey Club official website

---

## 📝 更新日志 / Changelog

### v1.4.1 — 2026-03-31
- 📝 **文档更新**：SKILL.md 新增 HKJC 贴士指数行（数据来源/分析要点/权重6%）；SKILL_EN.md 同步更新
- 🏗️ **重构：模块化拆分**：`analyze_race.py` 拆分为 10 个独立模块（`config` / `weights` / `probability` / `scoring` / `cache` / `fetch` / `parse` / `analyze` / `output` / `main`）
- ✅ `analyze_race.py` 保留为向后兼容入口层，CLI 用法完全不变
- 🔧 `config.py` 新增 `tips_index` 缓存类型（30分钟TTL）；`cache.py` 优化贴士指数URL识别

### v1.4.0 — 2026-03-31
- 🏗️ **重构：模块化拆分**：`analyze_race.py` 拆分为 10 个独立模块（`config.py` / `weights.py` / `probability.py` / `scoring.py` / `cache.py` / `fetch.py` / `parse.py` / `analyze.py` / `output.py` / `main.py`）
- ✅ `analyze_race.py` 保留为向后兼容入口层，CLI 用法完全不变
- ✅ 每个模块职责单一，便于测试、维护和独立 import
- 🔧 `config.py` 新增 `tips_index` 缓存类型（30分钟TTL）；`cache.py` 优化贴士指数URL识别

### v1.3.1 — 2026-03-31
- 🐛 **修复排序键字段名错误**：`final_score` → `total_score`（预测结果不再固定为 [1,2,3]）
- 🐛 **修复后备马混入 + 马名提取失败**：TR 正则精确匹配 + 链接提取改用 `[^>]*>` 绕过 onclick 干扰
- ✅ 各场马号完全多样化，评分差异明显（37–62 分）
- ✅ 正选马完全独立，马号与马名一一对应

### v1.3.0 — 2026-03-30
- ✅ 每日自动化调度系统（`daily_scheduler.py`）
- ✅ 自我进化分析引擎（赛后回测 → 进化建议）
- ✅ 进化建议应用工具（`apply_evolution.py`，支持备份/回滚）
- ✅ 预测存档机制（`.archive/`）

### v1.2.0 — 2026-03-30
- ✅ 骑师/练马师动态评分（从历史战绩动态统计）
- ✅ 权重调整：历史权重提升，骑练权重降低

### v1.1.0 — 2026-03-30
- ✅ 磁盘缓存系统（TTL 分级，节省重复请求）
- ✅ Softmax 概率归一化
- ✅ 场景自适应权重（normal/newcomer/class_down/class_up）
- ✅ 冷门关注逻辑（赔率 >15 的黑马识别）

### v1.0.0 — 2026-03-xx
- 🚀 初始发布：多维度评分 + HKJC 数据抓取 + 预测报告

---

<p align="center">
  <sub>Built with ❤️ for HKJC racing enthusiasts · Made by <a href="https://github.com/kus-wang">kus-wang</a></sub>
</p>
