# 🏇 香港赛马分析器 / HK Racing Analyzer

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Node.js](https://img.shields.io/badge/Node.js-18+-orange.svg)](https://nodejs.org)

> 数据驱动的香港赛马预测工具，基于历史战绩、赔率走势、配速分段等多维数据，提供前3名概率预测与投注建议。
> 
> A data-driven horse racing prediction tool for HKJC races — delivering top-3 probability distribution and betting recommendations.

---

## ✨ 核心功能 / Features

| 功能 / Feature | 描述 / Description |
|----------------|---------------------|
| **多维度分析 / Multi-dimensional** | 10个加权维度：赔率综合(22%)、赔率走势(18%)、同距离同场地历史(13%)、同场地历史(17%)、配速(8%)、骑师(4%)、练马师(3%)、档位(4%)、班次适配(7%)、贴士指数(4%) |
| **HKJC API 优先架构 / API-First** | GraphQL API 优先 + 官方页面自动回退，实时获取赛事数据 / GraphQL API priority with automatic page-scraping fallback |
| **智能投注推荐 / Smart Betting** | 自动判断场型，推荐最优投注方式（独赢/位置/连赢/三重彩）/ Auto-detects race type and recommends optimal bet type |
| **自我进化引擎 / Self-Evolution** | 对比预测与实际赛果，生成权重优化建议 / Compares predictions with actual results, generates optimization suggestions |
| **智能缓存 / Smart Caching** | 分层 TTL 缓存 + Zlib 压缩，空间节省 80-90% / Layered TTL caching with Zlib compression |
| **后备马支持 / Reserve Horses** | 正选退赛时后备马自动递补 / Automatic substitution tracking when declared runners withdraw |

---

## 🚀 快速开始 / Quick Start

### 环境要求 / Prerequisites

- Python 3.10+
- Node.js 18+
- Playwright（动态页面抓取 / for dynamic page scraping）

### 安装 / Installation

```bash
# 克隆仓库 / Clone the repository
git clone https://github.com/kus-wang/hk-racing-analyzer.git
cd hk-racing-analyzer

# 安装 Python 依赖 / Install Python dependencies
pip install -r requirements.txt

# 安装 Node.js 依赖 / Install Node.js dependencies
npm install

# 安装 Playwright 浏览器 / Install Playwright browser
playwright install chromium
```

### 使用示例 / Usage

```bash
# 分析今天沙田第3场 / Analyze today's Sha Tin Race 3
python scripts/analyze_race.py --venue ST --race 3

# 分析指定日期跑马地第5场 / Analyze Happy Valley Race 5 on a specific date
python scripts/analyze_race.py --date 2026/03/30 --venue HV --race 5

# 强制刷新所有缓存 / Force refresh all caches
python scripts/analyze_race.py --venue ST --race 3 --force-refresh

# 查看缓存统计 / View cache statistics
python scripts/analyze_race.py --cache-stats
```

---

## 📊 输出示例 / Sample Output

```
## 🏇 2026-03-29 沙田 第3场 / Sha Tin Race 3

### 前3名概率预测 / Top-3 Probability Prediction

| 排名 / Rank | 马号 / # | 马名 / Horse | 概率 / Prob | 评分 / Score |
|-------------|----------|--------------|-------------|--------------|
| 1 | 8 | 浪漫勇士 / Romantic Warrior | 32% | 87 |
| 2 | 3 | 金钻快线 / Golden Bolt | 21% | 78 |
| 3 | 5 | 飞龙在天 / Flying Dragon | 16% | 71 |

### 投注建议 / Betting Recommendations
- **独赢 / WIN**: #8 浪漫勇士 / Romantic Warrior
- **连赢 / QUINELLA**: 8, 3
- **冷门关注 / Dark Horse**: #5 (赔率 18，状态回升 / odds 18, form improving)
```

---

## 🏗️ 架构 / Architecture

### 双通道数据策略 / Dual-Channel Data Strategy

```
┌─────────────────┐     ┌─────────────────┐
│   HKJC API      │────▶│  GraphQL Bridge │
│  (优先/Primary) │     │  (api_client)   │
└─────────────────┘     └────────┬────────┘
                                 │
                    ┌────────────┴────────────┐
                    │    结构化缓存 / Cache     │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   分析引擎 / Analyzer    │
                    └────────────┬────────────┘
                                 │
┌─────────────────┐     ┌────────┴────────┐
│  页面抓取        │────▶│  HTML 解析器     │
│  (回退/Fallback)│     │  (Playwright)   │
└─────────────────┘     └─────────────────┘
```

### 项目结构 / Project Structure

```
hk-racing-analyzer/
├── scripts/
│   ├── main.py                 # CLI 入口 / CLI entry point
│   ├── analyze_race.py         # 主分析脚本 / Main analysis script
│   ├── api_client.py           # Python API 桥接 / Python API bridge
│   ├── hkjc_api_client.js      # Node.js GraphQL 桥接 / Node.js GraphQL bridge
│   ├── fetch.py                # 数据抓取（API优先）/ Data fetching (API-first)
│   ├── parse.py                # HTML 解析 / HTML parsing
│   ├── analyze.py              # 评分逻辑 / Scoring logic
│   ├── scoring.py              # 维度评分函数 / Dimension scoring functions
│   ├── probability.py          # Softmax 归一化 / Softmax normalization
│   ├── betting.py              # 投注推荐 / Betting recommendations
│   ├── output.py               # 报告格式化 / Report formatting
│   ├── cache.py                # 磁盘缓存 / Disk caching
│   ├── config.py               # 配置 / Configuration
│   ├── weights.py              # 动态权重计算 / Dynamic weight calculation
│   ├── daily_scheduler.py      # 自动化调度 / Automation scheduler
│   ├── race_day.py             # 赛马日检测 / Race day detection
│   ├── race_results.py         # 赛果抓取 / Results fetching
│   └── evolution_report.py     # 回测与进化 / Backtesting & evolution
├── references/                 # 文档与参考资料 / Documentation & references
├── .archive/                   # 预测存档 / Prediction archives
├── .evolution/                 # 进化报告 / Evolution reports
└── .cache/                     # 数据缓存 / Data cache
```

---

## ⚙️ 自动化 / Automation

| 任务 / Task | 时间 / Schedule | 功能 / Function |
|-------------|-----------------|-----------------|
| 赛马日预测 / Race Day Prediction | 每日 14:30 / Daily 14:30 | 检测赛马日 → 批量预测 → 存档 / Detect race day → batch predict → archive |
| 回测与进化 / Backtest & Evolution | 每日 23:30 / Daily 23:30 | 抓取赛果 → 对比预测 → 生成进化建议 / Fetch results → compare → generate suggestions |

### 进化工作流 / Evolution Workflow

```
[14:30] 检测赛马日 → 批量预测 → .archive/
              ↓
[23:30] 抓取实际赛果 → 对比预测 → .evolution/ (建议/suggestions)
              ↓
[手动/Manual] 审阅并应用: python scripts/apply_evolution.py --apply N
```

---

## 📖 文档 / Documentation

| 文档 / Document | 说明 / Description |
|-----------------|-------------------|
| [SKILL.md](SKILL.md) | 中文 Skill 文档 / Chinese documentation |
| [SKILL_EN.md](SKILL_EN.md) | 英文 Skill 文档 / English documentation |
| [RELEASE_NOTES.md](RELEASE_NOTES.md) | 完整更新日志 / Full changelog |
| [references/](references/) | HKJC URL、权重配置、工作流 / URLs, weight configs, workflow docs |

---

## 🛠️ 配置 / Configuration

编辑 `scripts/config.py` 可调整：

- 各维度权重分配 / Weight distribution across dimensions
- 数据类型缓存 TTL / Cache TTL by data type
- 输出格式 (JSON / markdown) / Output format
- 自动化调度时间 / Automation schedule

---

## 📝 更新日志 / Changelog

| 版本 / Version | 日期 / Date | 主要更新 / Highlights |
|---------------|-------------|----------------------|
| [v1.6.0](RELEASE_NOTES.md#v160--2026-04-08) | 2026-04-08 | HKJC API 优先架构：排位表/赔率/赛马日检测/赛果名次先走 GraphQL，失败自动回退页面 / HKJC API-first architecture with automatic page fallback |
| [v1.5.2](RELEASE_NOTES.md#v152--2026-04-07) | 2026-04-07 | 重构：daily_scheduler.py 拆分为 5 个模块，代码量削减 64% / Refactored scheduler into 5 modules, 64% code reduction |
| [v1.5.0](RELEASE_NOTES.md#v150--2026-04-07) | 2026-04-07 | 智能投注推荐模块：场型判断+最优玩法推荐 / Smart betting recommendation module |
| [v1.4.0](RELEASE_NOTES.md#v140--2026-03-31) | 2026-03-31 | 模块化重构 + 每日自动化 + 自我进化引擎 / Modular refactor, daily automation, self-evolution engine |

查看完整更新日志 / See full changelog: [RELEASE_NOTES.md](RELEASE_NOTES.md)

---

## ⚠️ 免责声明 / Disclaimer

- 本工具仅供**娱乐与学习参考**，不构成投注建议 / This tool is for **entertainment and educational purposes only**, not betting advice
- 赛马结果受多种不确定因素影响，**历史数据不代表未来表现** / Racing results depend on uncertain factors; **past performance does not guarantee future outcomes**
- 请**理性参与，量力而行** / Please **bet responsibly and within your means**
- 所有数据来自 [香港赛马会](https://racing.hkjc.com) 官方网站 / All data sourced from the [Hong Kong Jockey Club](https://racing.hkjc.com) official website

---

## 📜 许可证 / License

[MIT](LICENSE) © kus-wang

---

<p align="center">
  Built with ❤️ for HKJC racing enthusiasts / 为香港赛马爱好者而建
</p>
