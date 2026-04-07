# 🏇 香港赛马分析器 / HK Racing Analyzer

> Data-driven horse racing prediction tool for HKJC races — delivering top-3 probability distribution and betting recommendations.
>
> 港马数据驱动预测工具，基于历史战绩、赔率走势、配速分段、骑练数据、专家共识等多维数据，提供前3名概率预测与投注建议。


---

## ✨ 为什么选择这个工具？/ Why This Tool?

Like traditional handicapping, but **quantitative and automated** — combines 8+ data dimensions, self-evolves through backtesting, and scrapes real-time HKJC data.

类似传统评马师的思路，但**量化且自动化** — 结合8+个数据维度，通过回测自我进化，实时抓取HKJC数据。

> *"A tool that thinks like a professional tipster, but runs like a machine."*
> *"一个像专业马评人一样思考，但像机器一样运行的工具。"*

---

## 🏁 快速开始 / Quick Start

```bash
# 安装依赖 / Install dependencies
pip install requests beautifulsoup4 lxml playwright
playwright install chromium

# 分析今天沙田第3场 / Analyze today's Sha Tin Race 3
python scripts/analyze_race.py --venue ST --race 3

# 分析指定日期跑马地第5场 / Analyze Happy Valley Race 5 on a specific date
python scripts/analyze_race.py --date 2026/03/30 --venue HV --race 5

# 强制刷新所有缓存 / Force refresh all cache
python scripts/analyze_race.py --venue ST --race 3 --force-refresh

# 查看缓存统计 / Show cache statistics
python scripts/analyze_race.py --cache-stats
```

**环境要求 / Requirements**: Python 3.10+, OpenClaw + SkillHub (可选，用于 AI Agent 自动化 / optional, for AI agent automation)

---

## 📊 核心功能 / Features

| 功能 / Feature | 描述 / Description |
|----------------|---------------------|
| **多维度分析 / Multi-dimensional** | 10个加权维度：赔率综合(22%)、赔率走势(18%)、同距离同场地历史(13%)、同场地历史(17%)、配速(8%)、骑师(4%)、练马师(3%)、档位(4%)、班次适配(7%)、贴士指数(4%) |
| **后备马信息 / Reserve Horses** | 正选退赛时后备马自动递补，信息完整展示于分析报告中 |
| **HKJC 实时数据 / Real-time Data** | 抓取官方 HKJC 页面 — 排位表、赔率、赛果、马匹档案、投注赔率(bet.hkjc.com) |
| **投注赔率 / Betting Odds** | 独赢/位置/连赢/三重彩/位置Q 五种投注方式赔率抓取与分析；独赢赔率 20 档精细评分 + 隐含胜率融合 |
| **智能缓存 / Smart Caching** | 分层 TTL (5分钟–7天)，Zlib 压缩存储，结构化数据优先，空间减少 80-90% |
| **每日自动化 / Daily Automation** | 14:30 预测，23:30 回测 |
| **自我进化引擎 / Self-Evolution** | 对比预测与实际赛果，生成权重优化建议 |
| **可配置权重 / Configurable Weights** | 场景自适应：normal / newcomer / class_up / class_down |

---

## 📁 项目结构 / Project Structure

```
hk-racing-analyzer/
├── SKILL.md / SKILL_EN.md    # Skill 文档 / Skill documentation
├── README.md                  # 本文件 / This file
├── RELEASE_NOTES.md           # 完整更新日志 / Full changelog
├── requirements.txt           # Python 依赖 / Python dependencies
├── SECURITY_AUDIT_v1.5.0.md   # 安全审计报告 / Security audit report
├── scripts/
│   ├── main.py                # 模块化 CLI (v1.4+) / Modular CLI
│   ├── analyze_race.py        # 主入口 / Main entry
│   ├── daily_scheduler.py     # 自动化调度 / Automation runner
│   ├── apply_evolution.py     # 进化建议工具 / Evolution suggester
│   ├── config.py              # 配置常量 / Constants & parameters
│   ├── weights.py             # 权重加载 / Weight loading
│   ├── scoring.py             # 评分引擎 / Per-dimension scoring
│   ├── probability.py         # Softmax 概率计算 / Probability calculation
│   ├── betting.py             # 投注推荐模块 / Betting recommendation
│   ├── cache.py               # 磁盘缓存 / Disk cache manager
│   ├── fetch.py               # HKJC 数据抓取 / Data fetcher
│   ├── parse.py               # HTML 解析 / HTML parser
│   ├── analyze.py             # 评分汇总 / Score aggregation
│   ├── output.py              # 报告输出 / Report formatter
│   └── dump_race.py           # 调试工具 / Debug utility
├── references/                # URL 参考、权重配置 / URL refs, weight configs
│   ├── analysis_weights.md    # 权重配置 / Weight configuration
│   ├── expert_sources.md      # 专家数据源 / Expert sources
│   └── hkjc_urls.md           # HKJC URL 整理 / URL reference
├── assets/                    # 静态资源 / Static assets
└── .archive/ .evolution/      # 自动生成输出 / Auto-generated output
```

---

## 💾 缓存策略 / Caching Strategy

| 数据类型 / Data Type | TTL | 说明 / Notes |
|----------------------|-----|--------------|
| 历史赛果 / Historical results | 7 天 / days | 赛果不变 / Never changes |
| 当日排位表 / Race card | 30 分钟 / min | 可能换马/骑师 / May change |
| 马匹历史 / Horse history | 24 小时 / hrs | 每场赛后更新 / Updated after race |
| 赔率数据 / Odds data | 5 分钟 / min | 临场实时变化 / Real-time |
| 投注赔率 / Betting odds | 5 分钟 / min | 独赢/位置/连赢/三重彩/位置Q |
| 贴士指数 / Tips index | 30 分钟 / min | 每场赛前更新 / Updated before each race |

**v1.5.0 优化 / v1.5.0 Optimizations:**
- **智能投注推荐 / Smart Betting Recommendations**: 场型判断 + 最优玩法推荐 (WIN/Q/TRIO/PLACE)、价值指数计算、冷门建议接口、回测命中验证
- **动态 Softmax 温度 / Dynamic Softmax Temperature**: T 根据场内赔率离散度 3.0-6.0 自动调整
- **赔率快照 / Odds Snapshot**: 新增 predicted_odds_snapshot 解决 opening_odds 全空问题

**v1.4.12 优化 / v1.4.12 Optimizations:**
- **tips_index 权重调整**: 6% → 4%
- **首胜奖励调整**: +10 → +3
- **动态 Softmax 温度 / Dynamic Softmax**: T=3.0-6.0 根据赔率离散度自动调整

**v1.4.11 优化 / v1.4.11 Optimizations:**
- **赔率权重提升 / Odds Weight Increase**: 赔率系合计从 30% → 40%，成为预测主导信号
- **赔率评分增强 / Enhanced Odds Scoring**: 独赢赔率 20 档精细评分 + 位置赔率加成 + 隐含胜率融合
- **Softmax 参数调整 / Softmax Tuning**: Temperature 2.0 → 4.0，概率分布更平滑

**v1.4.8 优化 / v1.4.8 Optimizations:**
- **Zlib 压缩存储 / Zlib Compression**: HTML 压缩率 70-80%（200KB → 40-60KB）
- **结构化数据优先 / Structured Data Priority**: 解析后数据直接存储（~5KB vs 原始 HTML ~200KB），热路径不再重复解析
- **综合效果 / Overall Effect**: 缓存空间减少 80-90%

---

## ⚙️ 自动化任务 / Automation

| 任务 / Task | 时间 / Time | 功能 / Function |
|-------------|-------------|-----------------|
| 赛马日预测 / Racing Day Prediction | 每日 14:30 | 检测赛马日 → 批量预测 → 存档到 `.archive/` |
| 回测与进化 / Backtest & Evolution | 每日 23:30 | 抓取昨日赛果 → 对比预测 → 生成进化建议到 `.evolution/` |

```bash
# 进化工作流 / Evolution workflow
[14:30] 检测赛马日 → 批量预测 → .archive/
[23:30] 抓取实际赛果 → 对比预测 → .evolution/ (建议)
# 用户审阅后应用: python scripts/apply_evolution.py --apply N
# 如需回滚: python scripts/apply_evolution.py --rollback
```

---

## 📝 输出示例 / Sample Output

```
## 🏇 2026-03-29 沙田 第3场 / Sha Tin Race 3

### 前3名概率预测 / Top-3 Probability

| 排名 / Rank | 马号 / # | 马名 / Horse | 概率 / Prob | 评分 / Score |
|-------------|----------|--------------|-------------|--------------|
| 1 | 8 | 浪漫勇士 / Romantic Warrior | 32% | 87 |
| 2 | 3 | 金钻快线 / Golden Bolt | 21% | 78 |
| 3 | 5 | 飞龙在天 / Flying Dragon | 16% | 71 |

### 投注建议 / Betting Recommendations
- **独赢 / Win**: #8 浪漫勇士
- **连赢 / Quinella**: 8, 3
- **冷门关注 / Dark Horse**: #5 (赔率/odds 18，状态回升/form improving)
```

---

## 🔧 配置 / Configuration

编辑 `scripts/config.py` 调整：

- 各维度权重分配 / Weight distribution across dimensions
- 数据类型缓存 TTL / Cache TTL by data type
- 输出格式 (JSON / markdown)
- 自动化调度时间 / Automation schedule

---

## 📖 文档 / Documentation

- [SKILL.md](SKILL.md) — 中文 Skill 文档
- [SKILL_EN.md](SKILL_EN.md) — English documentation
- [RELEASE_NOTES.md](RELEASE_NOTES.md) — 完整更新日志 / Full changelog
- [references/](references/) — HKJC URL、权重配置 / URLs, weight configs

---

## 📝 更新日志 / Changelog

| 版本 / Version | 日期 / Date | 主要更新 / Main Changes |
|---------------|-------------|------------------------|
| [v1.5.0](RELEASE_NOTES.md#v150--2026-04-07) | 2026-04-07 | 智能投注推荐模块：场型判断+最优玩法推荐(WIN/Q/TRIO/PLACE)、价值指数计算、冷门建议接口、回测命中验证；预测报告新增「最推荐投注方案」；回测新增投注推荐回测统计板块；Bug修复：赛马日场地检测误判（通过场地验证从返回HTML提取实际Racecourse比对修复） / Smart betting recommendation module: race-type judgment + optimal play recommendation (WIN/Q/TRIO/PLACE), value index calculation, longshot tip interface, backtest hit verification; prediction report adds "Recommended Betting Scheme"; backtest adds betting recommendation statistics; Bug fix: race day venue detection false positive (venue verification by extracting actual Racecourse from returned HTML) |
| [v1.4.12](RELEASE_NOTES.md#v1412--2026-04-07) | 2026-04-07 | 基于2026-04-06沙田回测的深度进化：修复opening_odds全空问题(新增predicted_odds_snapshot)、tips_index权重6%→4%、hist_same_condition首胜奖励+10→+3、Softmax温度动态化(T根据场内赔率离散度3.0-6.0自动调整) / Deep evolution based on 2026-04-06 Sha Tin backtest: fix opening_odds all-NULL (add predicted_odds_snapshot), tips_index weight 6%→4%, first-win bonus +10→+3, dynamic Softmax temperature (T=3.0-6.0 based on odds dispersion) |
| [v1.4.10](RELEASE_NOTES.md#v1410--2026-04-05) | 2026-04-05 | Bug修复：赔率抓取失败（改用Playwright DOM提取）/ Bug fix: odds scraping (switched to Playwright DOM extraction) |
| [v1.4.9](RELEASE_NOTES.md#v149--2026-04-05) | 2026-04-05 | Bug修复：批量预测存档全空（缓存解析+字段名问题）/ Bug fix: empty batch predictions (cache parsing + field name issues) |
| [v1.4.8](RELEASE_NOTES.md#v148--2026-04-03) | 2026-04-03 | 缓存系统优化：Zlib压缩+结构化存储，空间减少80-90%；投注赔率功能补全：独赢/位置/连赢/三重彩/位置Q完整解析 / Cache optimization: Zlib compression + structured storage, 80-90% space reduction; Betting odds complete: Win/Place/Quinella/Trio/QP |
| [v1.4.7](RELEASE_NOTES.md#v147--2026-04-03) | 2026-04-03 | Bug修复+代码清理；Skill文档增强（触发词/自然语言/投注风格/对比功能/赛果查询）；新增投注风格自动标注+赛果查询模块 / Bug fixes, code cleanup, skill docs enhancement, betting style classification, race results query |
| [v1.4.6](RELEASE_NOTES.md#v146--2026-04-03) | 2026-04-03 | 后备马解析与展示：正选退赛时后备马自动递补，展示于报告中（不参与预测评分）/ Reserve horse parsing & display: emergency horses shown in report |
| [v1.4.5](RELEASE_NOTES.md#v145--2026-04-03) | 2026-04-03 | Playwright单例复用+并行历史抓取(8线程)；中文condition参数；动态班次推断；权重优化(历史33%/赔率30%/配速10%) / Playwright singleton + parallel history fetch; Chinese condition input; dynamic class inference; weight optimization |
| [v1.4.4](RELEASE_NOTES.md#v144--2026-04-02) | 2026-04-02 | 投注建议模块重构：独赢/位置/连赢/三重彩智能推荐逻辑 / Betting recommendation refactor: smart Win/Place/Quinella/Trio logic |
| [v1.4.3](RELEASE_NOTES.md#v143--2026-04-02) | 2026-04-02 | 进化建议全量应用：Softmax温度1.5→2.0，历史时间衰减加权，配速临时降权 / Evolution suggestions applied: Softmax temp, time decay, pace weight reduction |
| [v1.4.2](RELEASE_NOTES.md#v142--2026-04-01) | 2026-04-01 | 回测时间改为 23:30 / Backtest time changed to 23:30；新增预测存档归档隔离 / Archive isolation |
| [v1.4.1](RELEASE_NOTES.md#v141--2026-03-31) | 2026-03-31 | 新增 HKJC 贴士指数 / Added Tips Index |
| [v1.4.0](RELEASE_NOTES.md#v140--2026-03-31) | 2026-03-31 | 模块化重构：拆分为10个独立模块 / Modular refactor into 10 modules |
| [v1.3.1](RELEASE_NOTES.md#v131--2026-03-31) | 2026-03-31 | 修复排序键字段名错误 / Fixed sort key field name |
| [v1.3.0](RELEASE_NOTES.md#v130--2026-03-30) | 2026-03-30 | 每日自动化调度 + 自我进化引擎 / Daily automation + self-evolution engine |
| [v1.2.0](RELEASE_NOTES.md#v120--2026-03-30) | 2026-03-30 | 骑师/练马师动态评分 / Dynamic jockey/trainer scoring |
| [v1.1.0](RELEASE_NOTES.md#v110--2026-03-30) | 2026-03-30 | 磁盘缓存系统 + Softmax 概率归一化 / Disk cache + Softmax normalization |
| v1.0.0 | 2026-03-xx | 初始发布 / Initial release |

*查看完整更新日志 / See full changelog: [RELEASE_NOTES.md](RELEASE_NOTES.md)*

---

## ⚠️ 免责声明 / Disclaimer

- 本工具仅供**娱乐与学习参考**，不构成投注建议
- This tool is for **entertainment and learning reference only**, not betting advice
- 赛马结果受多种不确定因素影响，**历史数据不代表未来表现**
- Racing results depend on uncertain factors; **past performance does not guarantee future outcomes**
- 请**理性参与，量力而行**
- Please **bet responsibly and within your means**
- 所有数据来自 [香港赛马会](https://racing.hkjc.com) 官方网站
- All data sourced from the [Hong Kong Jockey Club](https://racing.hkjc.com) official website

---

## 📜 许可证 / License

[MIT](LICENSE) © kus-wang

---

<p align="center">
  Built with ❤️ for HKJC racing enthusiasts / 为香港赛马爱好者而建
</p>
