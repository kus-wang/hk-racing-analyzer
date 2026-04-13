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
| **多维度分析 / Multi-dimensional** | 12个评分维度：赔率综合(22%)、赔率走势(18%)、同距离同场地历史(13%)、同场地历史(17%)、配速(8%)、骑师(4%)、练马师(3%)、档位(4%)、班次适配(7%)、贴士指数(4%)、轻磅马加分(独立)、TJ组合加分(独立) |
| **HKJC API 优先架构 / API-First** | GraphQL API 优先 + 官方页面自动回退，实时获取赛事数据 / GraphQL API priority with automatic page-scraping fallback |
| **投注推荐：位置优先 / PLACE-FIRST** | C场→位置、B场→双马位置、A场→DUO_PLACE/WIN、D场→位置；Q（连赢）基本移除，仅极高置信时保留 / C→PLACE, B→DUO_PLACE, A→DUO_PLACE/WIN, D→PLACE; Q largely removed |
| **Softmax 动态温度 / Dynamic T** | 均衡场4.5、正常场5.0、大差异场5.5、超悬殊场6.5；整体+0.5使概率分布更平滑 / Balanced T=4.5, Normal T=5.0, Diverged T=5.5, Extreme T=6.5 |
| **轻磅马加分 / Weight Bonus** | 负磅<115磅+8分、<120磅+5分、<125磅+3分；跑马地短途额外加成 / Negative weight bonus with HV short-distance boost |
| **TJ组合加分 / TJ Combo Bonus** | 顶级骑师+练马师白名单组合额外加分（如 Z Purton+J Size +10分）/ Top Jockey+Trainer combo whitelist bonus |
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
| 2 | 3 | 精明时空 / Smart Timespace | 21% | 79 |
| 3 | 5 | 金玉良言 / Golden Words | 17% | 72 |

### 💰 推荐投注 / Betting Recommendation

- **推荐方案**: 位置 #8 | 概率覆盖 53.2% | 场型：稳妥型
- **价值指数**: #8 独赢 1.8 → 超值 🔥

### 📈 各维度评分 / Dimension Scores

| 马号 | 历史场地 | 历史同条件 | 赔率综合 | 赔率走势 | 骑师 | 练马师 |
|------|---------|-----------|---------|---------|------|-------|
| 8 | 88 | 85 | 96 | 72 | 68 | 70 |
| 3 | 75 | 78 | 82 | 65 | 72 | 68 |
| 5 | 65 | 72 | 74 | 80 | 70 | 75 |
```

---

## 🗂️ 项目结构 / Project Structure

```
hk-racing-analyzer/
├── SKILL.md              # Skill 入口文档（中文）/ Skill entry documentation
├── SKILL_EN.md           # Skill entry documentation（English）
├── scripts/              # 核心 Python 分析模块
│   ├── analyze_race.py   # CLI 入口（兼容层）/ CLI entry (compatibility)
│   ├── main.py           # 主流程编排 / Main orchestration
│   ├── analyze.py        # 马匹多维度评分 / Multi-dimension horse scoring
│   ├── scoring.py        # 评分函数库 / Scoring function library
│   ├── probability.py    # Softmax 概率归一化 / Softmax probability
│   ├── weights.py        # 动态权重计算 / Dynamic weight calculation
│   ├── betting.py        # 投注推荐策略 / Betting recommendation strategy
│   ├── output.py         # Markdown 报告输出 / Markdown report output
│   ├── fetch.py          # HTTP/Playwright 抓取 / Data fetching
│   ├── parse.py          # HTML 解析 / HTML parsing
│   ├── cache.py          # 磁盘缓存管理 / Disk cache management
│   ├── config.py         # 配置常量 / Configuration constants
│   ├── api_client.py     # Python API 客户端 / Python API client
│   ├── hkjc_api_client.js # Node.js GraphQL bridge
│   ├── race_day.py       # 赛马日检测 / Race day detection
│   ├── race_results.py   # 赛果抓取 / Race results fetching
│   ├── daily_scheduler.py # 每日调度 / Daily scheduler
│   ├── scheduler_cache.py # 调度缓存 / Scheduler cache
│   ├── evolution_report.py # 进化报告 / Evolution report
│   └── apply_evolution.py # 进化建议应用 / Evolution apply tool
├── .archive/             # 预测存档 / Prediction archives
├── .evolution/           # 进化建议报告 / Evolution reports
├── .backups/             # 每次进化应用的代码备份 / Code backups
└── references/           # 参考文档 / Reference documents
```

---

## ⚙️ 评分维度权重 / Scoring Dimension Weights

> ⚠️ 以下为默认值，实际使用 `weights.py` 动态计算（场地/距离/赛制自适应）

| 维度 / Dimension | 权重 / Weight | 说明 / Note |
|-----------------|:-------------:|-------------|
| 赔率综合评分 / Odds Value | 22% | 独赢20档精细评分 + 位置赔率加成 |
| 赔率走势 / Odds Drift | 18% | 市场资金流向信号 |
| 同距离同场地历史 / Same Distance+Venue | 13% | 时间衰减加权（近30天×1.0） |
| 同场地历史 / Same Venue | 17% | 时间衰减加权 |
| 配速指数 / Sectional Pace | 8% | 跑法×场地状况匹配 |
| 班次适配 / Class Fit | 7% | 当前班次区间匹配 |
| 贴士指数 / Tips Index | 4% | HKJC 官方贴士 |
| 骑师 / Jockey | 4% | 动态评分（历史胜率） |
| 练马师 / Trainer | 3% | 动态评分（历史胜率） |
| 档位 / Barrier | 4% | 跑马地/弯道影响 |

> 附加：轻磅马加分（独立，不占权重上限）/ TJ组合加分（独立）

---

## 💰 投注推荐策略 / Betting Strategy

| 场型 / Race Type | 条件 / Condition | 推荐玩法 / Recommendation |
|-----------------|------------------|--------------------------|
| **C（标准三强场）** | Top3 概率和 ≥ 60% | **PLACE 位置**（命中率最高，约33%） |
| **B（双强对决场）** | Top1+Top2 概率和 ≥ 55%，概率差 < 15% | **DUO_PLACE 双马位置**（两匹均进前3即中） |
| **A（高置信场）** | Top1 ≥ 28%，value_index ≥ 1.05，赔率 ≤ 6 | DUO_PLACE / WIN（仅赔率≤8时推荐DUO_PLACE，>8降级） |
| **D（开放冷门场）** | 以上不满足 | **PLACE 位置**（保守保底） |

**连赢 Q 玩法**：基本移除，仅在极高置信（Top1+Top2 ≥ 88% 且概率差 < 5%）时保留。

**价值指数**：model_prob / (1/odds × 0.92)，>1.2 为超值 🔥，<0.8 为市场高估 ⚠️

---

## 🧬 Softmax 动态温度 / Dynamic Softmax Temperature

| 赔率离散度（max/min odds）| 温度 T | 场景 / Scenario |
|:------------------------:|:------:|-----------------|
| > 20（超悬殊场） | **6.5** | 极大热门 vs 极大冷门 |
| > 10（大差异场） | **5.5** | 明显热门 |
| > 5（正常场） | **5.0** | 默认推荐 |
| ≤ 5（均衡场） | **4.5** | 各马赔率相近，无明显共识 |

无赔率数据时回退使用默认值 T=4.5。

---

## 🔧 高级用法 / Advanced Usage

```bash
# 批量预测（daily_scheduler）
python scripts/daily_scheduler.py --mode predict --date 2026/04/12

# 批量回测 + 进化分析
python scripts/daily_scheduler.py --mode backtest --date 2026/04/08

# 应用进化建议（带自动备份）
python scripts/apply_evolution.py --apply

# 回滚最近一次进化
python scripts/apply_evolution.py --rollback

# 查看进化历史
python scripts/apply_evolution.py --history

# 马匹对比分析
python scripts/analyze_race.py --venue ST --race 3 --compare 3 7

# 查询赛果
python scripts/analyze_race.py --venue ST --date 2026/03/30 --results
```

---

## 📝 更新日志 / Changelog

> [!IMPORTANT]
> **v1.6.4+ 需要 Playwright**：新版 API 优先架构依赖 Playwright 渲染动态页面。
> 如遇 `pip install -r requirements.txt` 后仍报错，请运行 `playwright install chromium`。

| 版本 / Version | 日期 / Date | 变更 / Changes |
|:--------------:|:-----------:|----------------|
| **v1.6.5** | 2026-04-12 | **投注策略重构：位置优先，命中率第一**。<br>历史回测显示 Q 命中率 0%、DUO_PLACE 约 20%、PLACE 理论值 33%。C场改推位置（降级三重彩），B场改推双马位置，A场 DUO_PLACE/WIN 保持（赔率>8降级位置），D场不变。连赢Q基本移除，仅极高置信时保留。`betting.py` 核心重构。 |
| **v1.6.4** | 2026-04-12 | **Softmax 动态温度整体+0.5**。2026-04-12 沙田回测显示18匹马被高估，低分马命中率偏低。四档温度调整：超悬殊场6.0→6.5，大差异场5.0→5.5，正常场4.5→5.0，均衡场4.0→4.5。fallback值4.0→4.5。`probability.py` + `config.py` 同步更新。 |
| **v1.6.3** | 2026-04-09 | **新增评分维度：轻磅马加分 + TJ组合加分**。<br>负磅越低加分越多，跑马地短途额外加成；顶级骑师+练马师白名单额外加分。<br>**投注策略保守化**：A场改推DUO_PLACE（替代WIN），C场改推Q（替代TRIO），新增DUO_PLACE双马位置玩法。<br>**Bug修复**：`fetch_tips_index` 批量预测第2-11场全空（race_info UnboundLocalError + 缓存无解压），`detect_race_day` API日期忽略，`tips_index` 日期校验。`scoring.py` + `betting.py` + `fetch.py` + `main.py` + `race_day.py`。 |
| **v1.6.2** | 2026-04-09 | Softmax 温度均衡场3.0→4.0、正常场4.0→4.5；概率优势不足(<15%)时A场型降级位置；无效odds_drift权重(变化<5%)动态转移至odds_value。 |
| **v1.6.1** | 2026-04-09 | 修复 backtest 历史日期场地误判：存档优先校验venue，自动发现存档优先查找昨天。 |
| **v1.6.0** | 2026-04-08 | **🚀 架构升级：HKJC GraphQL API 优先 + 页面抓取回退**。<br>新增 `api_client.py` + `hkjc_api_client.js`，覆盖排位表/赔率/赛马日检测/赛果名次；Windows 控制台编码修复；赛果API finalPosition严格校验。 |
| **v1.5.2** | 2026-04-07 | `daily_scheduler.py` 拆分为5个模块（调度编排/缓存/赛马日检测/赛果/进化报告），削减64%行数。 |
| **v1.5.1** | 2026-04-07 | 修复 opening_odds 端到端链路（odds_drift权重18%恢复生效）；新增独赢/位置赔率比值冷门信号评分。 |
| **v1.5.0** | 2026-04-07 | **💰 智能投注推荐模块**：`determine_bet_type()` / `compute_value_index()` / `get_longshot_tip()` / `check_bet_hit()`；赛马日场地检测误判修复；批量预测控制台输出补全。 |
| **v1.4.12** | 2026-04-07 | 修复 opening_odds 全链路；tips_index权重6%→4%；hist_same_condition首胜奖励+10→+3；Softmax动态温度（4档T值）。 |
| **v1.4.11** | 2026-04-05 | 赔率权重30%→40%（赔率综合22%+走势18%）；Softmax T=2.0→4.0，PROB_CAP 0.50→0.88；全场赔率数据注入。 |
| **v1.4.10** | 2026-04-05 | Playwright DOM提取赔率（修复JS动态渲染问题）。 |
| **v1.4.9** | 2026-04-05 | 修复批量预测存档全空（缓存返回dict导致TypeError + 字段名兼容）。 |
| **v1.4.8** | 2026-04-03 | Zlib压缩缓存+结构化parsed字段，节省80-90%空间。 |
| **v1.4.7** | 2026-04-03 | 投注赔率抓取（bet.hkjc.com，五种玩法）；修复fetch_tips_index NameError。 |
| **v1.4.6** | 2026-04-03 | 后备马解析与展示；validate_race_entries() 完整性校验。 |
| **v1.4.5** | 2026-04-03 | Playwright单例复用 + 8线程并行历史抓取（耗时~120s→~20s）；中文场地条件支持；动态班次区间推断。 |
| **v1.4.4** | 2026-04-02 | 投注建议模块重构（AI自主判断六种玩法）；回测时间09:00→23:30。 |
| **v1.4.3** | 2026-04-02 | 进化建议全量应用：Softmax T=1.5→2.0；历史权重重构；配速临时降权；时间衰减加权。 |
| **v1.4.2** | 2026-04-01 | 预测存档归档隔离（completed/目录）；修复每日回测缓存污染问题。 |
| **v1.4.1** | 2026-03-31 | SKILL文档完善；`analyze_race.py`拆分为9个模块（1778行→9个职责模块）。 |
| **v1.3.1** | 2026-03-31 | 贴士指数JS动态渲染；排位表正则修复；排序键final_score→total_score；后备马混入修复。 |
| **v1.3.0** | 2026-03-30 | 每日自动化调度系统（预测+回测+进化分析）；自我进化引擎；预测存档机制。 |
| **v1.2.0** | 2026-03-30 | 骑师/练马师动态评分（历史胜率统计）；历史战绩新增jockey/trainer字段。 |
| **v1.1.0** | 2026-03-30 | 磁盘缓存系统（分层TTL）；Softmax概率归一化；场景自适应权重；跑法自动推导。 |
| **v1.0.0** | 2026-03-xx | 初始发布：基础分析框架、多维度评分、Markdown报告。 |

---

## 📚 相关文档 / References

| 文档 | 说明 |
|------|------|
| `SKILL.md` | OpenClaw Skill 入口（中文） |
| `SKILL_EN.md` | OpenClaw Skill 入口（English） |
| `references/workflow.md` | 完整工作流程详解（CLI用法/投注逻辑/马匹对比/赛果查询） |
| `references/analysis_weights.md` | 各评分维度权重详解 |
| `references/analysis_weights_en.md` | Scoring weights reference (English) |
| `OPTIMIZATION_PLAN.md` | 长期优化路线图 |

---

## 📄 License

MIT License — 详见 `LICENSE` 文件。
