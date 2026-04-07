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
| **智能缓存 / Smart Caching** | 分层 TTL，Zlib 压缩存储，支持 `--force-refresh` |
| **模块化架构 / Modular Architecture** | daily_scheduler.py 拆分为 5 个模块（调度、缓存、赛马日检测、赛果、进化报告）|
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
├── scripts/
│   ├── main.py                # 模块化 CLI / Modular CLI
│   ├── analyze_race.py        # 主入口 / Main entry
│   ├── daily_scheduler.py     # 调度编排器 / Scheduler (~390行)
│   ├── scheduler_cache.py     # HTTP 缓存 / Cache (~100行)
│   ├── race_day.py            # 赛马日检测 / Race day (~80行)
│   ├── race_results.py        # 赛果抓取 / Results (~150行)
│   ├── evolution_report.py    # 进化报告 / Evolution (~460行)
│   ├── apply_evolution.py     # 进化建议工具 / Evolution tool
│   ├── config.py              # 配置 / Config
│   ├── weights.py             # 权重 / Weights
│   ├── scoring.py             # 评分 / Scoring
│   ├── probability.py         # 概率 / Probability
│   ├── betting.py             # 投注推荐 / Betting
│   ├── cache.py               # 缓存 / Cache
│   ├── fetch.py               # 数据抓取 / Fetcher
│   ├── parse.py               # 解析 / Parser
│   ├── analyze.py             # 分析 / Analyzer
│   ├── output.py              # 输出 / Output
│   └── dump_race.py           # 调试 / Debug
├── references/                # 参考资料 / References
└── .archive/ .evolution/      # 自动生成 / Auto-generated
```

---

## 💾 缓存策略 / Caching Strategy

| 数据类型 / Data Type | TTL |
|----------------------|-----|
| 历史赛果 / Results | 7 天 |
| 排位表 / Race card | 30 分钟 |
| 马匹历史 / Horse history | 24 小时 |
| 赔率 / Odds | 5 分钟 |
| 贴士指数 / Tips index | 30 分钟 |

- Zlib 压缩存储，缓存空间减少 80-90%
- 支持 `--force-refresh` 强制刷新

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
| [v1.5.2](RELEASE_NOTES.md#v152--2026-04-07) | 2026-04-07 | 重构：daily_scheduler.py 拆分为 5 个模块（调度编排器、缓存管理、赛马日检测、赛果抓取、进化报告），代码量削减 64% / Refactor: daily_scheduler.py split into 5 modules, code reduced 64% |
| [v1.5.1](RELEASE_NOTES.md#v151--2026-04-07) | 2026-04-07 | 修复 opening_odds 全空问题；新增独赢/位置赔率比值冷门信号 / Fix opening_odds NULL issue; add win/place ratio dark horse signal |
| [v1.5.0](RELEASE_NOTES.md#v150--2026-04-07) | 2026-04-07 | 智能投注推荐模块：场型判断+最优玩法推荐 / Smart betting recommendation module |
| [v1.4.12](RELEASE_NOTES.md#v1412--2026-04-07) | 2026-04-07 | 深度进化：tips_index 权重调整、首胜奖励调整、Softmax 温度动态化 / Deep evolution: tips_index weight, first-win bonus, dynamic Softmax |
| [v1.4.11](RELEASE_NOTES.md#v1411--2026-04-05) | 2026-04-05 | 赔率权重提升至 40%，成为预测主导信号 / Odds weight increased to 40% |
| [v1.4.10](RELEASE_NOTES.md#v1410--2026-04-05) | 2026-04-05 | Bug修复：赔率抓取改用 Playwright / Bug fix: odds scraping with Playwright |
| [v1.4.9](RELEASE_NOTES.md#v149--2026-04-05) | 2026-04-05 | Bug修复：批量预测存档全空 / Bug fix: empty batch predictions |
| [v1.4.8](RELEASE_NOTES.md#v148--2026-04-03) | 2026-04-03 | 缓存系统优化：Zlib 压缩 / Cache optimization: Zlib compression |
| [v1.4.7](RELEASE_NOTES.md#v147--2026-04-03) | 2026-04-03 | 投注赔率功能补全 / Betting odds complete |
| [v1.4.6](RELEASE_NOTES.md#v146--2026-04-03) | 2026-04-03 | 后备马解析与展示 / Reserve horse parsing |
| [v1.4.5](RELEASE_NOTES.md#v145--2026-04-03) | 2026-04-03 | Playwright 单例复用 + 并行抓取 / Playwright singleton + parallel fetch |
| [v1.4.4](RELEASE_NOTES.md#v144--2026-04-02) | 2026-04-02 | 投注建议模块重构 / Betting recommendation refactor |
| [v1.4.3](RELEASE_NOTES.md#v143--2026-04-02) | 2026-04-02 | 进化建议应用 / Evolution suggestions applied |
| [v1.4.2](RELEASE_NOTES.md#v142--2026-04-01) | 2026-04-01 | 回测时间改为 23:30 / Backtest time changed to 23:30 |
| [v1.4.1](RELEASE_NOTES.md#v141--2026-03-31) | 2026-03-31 | 新增贴士指数 / Added Tips Index |
| [v1.4.0](RELEASE_NOTES.md#v140--2026-03-31) | 2026-03-31 | 模块化重构 / Modular refactor |
| v1.3.0 | 2026-03-30 | 每日自动化调度 + 自我进化引擎 / Daily automation + self-evolution |
| v1.2.0 | 2026-03-30 | 骑师/练马师动态评分 / Dynamic jockey/trainer scoring |
| v1.1.0 | 2026-03-30 | 磁盘缓存系统 + Softmax / Disk cache + Softmax |
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
