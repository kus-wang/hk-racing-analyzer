---
name: hk-racing-analyzer
description: 香港赛马数据分析和预测工具。基于历史战绩、赔率走势、配速分段等数据进行量化分析，采用 HKJC API 优先、页面抓取回退的双通道策略，给出前3名概率分布和投注建议。触发关键词：分析沙田/跑马地第X场、赛马预测、马匹分析、HKJC赛马、今天赛马分析、比较X号和Y号、今天赛果。使用场景：用户想分析某场赛马比赛、预测比赛结果、查看马匹历史战绩、马匹对比、了解今天赛果。

---

# 香港赛马分析器 (HK Racing Analyzer)

数据驱动的赛马预测工具，结合历史数据分析和AI辅助判断。

## 核心功能

1. **赛事数据分析** - 以 HKJC GraphQL API 为主、官方页面抓取为后备，分析各参赛马匹
2. **预测分析** - 基于多维度数据给出前3名概率分布
3. **智能投注推荐** - 基于概率分布+赔率性价比，自动判断每场最优玩法（WIN/PLACE/Q/TRIO）

## 分析维度

| 维度 | 数据来源 | 分析要点 |
|------|----------|----------|
| **马匹历史战绩** | HKJC马匹档案页面 | 近5场/10场成绩、同场地表现、同距离表现（含时间衰减）；API 暂不可替代 |
| **赔率走势** | HKJC API + 赔率页面回退 | 开盘赔率 vs 临场赔率、赔率变化趋势；独赢20档精细评分+位置赔率加成+隐含胜率融合（v1.4.11）|
| **配速/分段** | HKJC赛果页面 / 历史页面 | API 仅提供 finalPosition，配速与 running positions 仍取页面数据 |
| **骑师胜率** | HKJC API 排位表 + 马匹历史战绩 | API 提供当场骑师/练马师，历史战绩动态统计胜率 |
| **练马师胜率** | HKJC API 排位表 + 马匹历史战绩 | API 提供当场练马师，历史战绩动态统计胜率 |
| **档位分析** | HKJC API 排位表 + 历史统计 | API 提供 barrier/评分/负磅；跑马地内档优势明显 |
| **场地偏好** | 马匹档案 | 草地/泥地、好地/快地表现（含在同条件历史中）|
| **轻磅加分** | 排位表负磅 | 负磅<120磅加分，跑马地短途额外加成 |
| **TJ组合加分** | 排位表骑练组合 | 顶级骑师+练马师组合白名单加分 |


> 维度权重由 `weights.py` 根据场地/距离/班次动态计算，详见 `references/analysis_weights.md`。

### 外部参考（可选）

使用 `web_search` 搜索专家马评，提取共识观点作为辅助参考。搜索关键词：`"沙田赛马 第X场 预测"` / `"跑马地 今晚 马评"` / `"马经 推荐"`

> 专家预测仅供参考，重点关注有数据支撑的分析。

## 工作流程

### Step 1: 解析用户请求

从用户输入中提取日期（默认今天）、场地（ST/HV）、场次号、功能意图（预测/对比/赛果）。

**日期自然语言支持**：`今天`/`明天`/`下周X`/`YYYY/MM/DD` → 对应日期
**场地映射**：`沙田`/`ST` → ST；`跑马地`/`HV`/`今晚` → HV
**功能意图**：`分析`/`预测`/`推荐` → 预测分析；`比较`/`对比`/`X号和Y号` → 马匹对比；`赛果`/`结果` → 赛果查询

**示例**：
- "分析今天沙田第3场" → 日期=今天, 场地=ST, 场次=3, 意图=预测
- "比较3号和7号" → 日期=今天, 意图=对比, 马号=[3, 7]
- "今天沙田第2场谁赢了" → 日期=今天, 场地=ST, 场次=2, 意图=赛果

### Step 2: 获取赛事数据（带缓存，API 优先）

脚本内置磁盘缓存，避免重复抓取。缓存位置：`.cache/<url_hash>.json`

#### 数据通路（v1.6.0）

1. 优先调用 `scripts/api_client.py` → `scripts/hkjc_api_client.js` → `hkjc-api` GraphQL 接口
2. 单次 API 调用最多尝试 **2 次**（含首次），失败后等待 **500ms** 再试
3. 任意两次 API 请求之间至少间隔 **500ms**，避免访问过频
4. 若 API 在可接受次数内仍失败，自动降级到原有页面抓取（Playwright / HTTP）
5. API 命中的缓存优先保存为结构化 JSON（`parsed`），减少 HTML 体积与重复解析

#### API 可覆盖范围

- ✅ 排位表核心字段：马号、马名、档位、负磅、评分、骑师、练马师、后备马标记
- ✅ 赔率池：WIN / PLA / QIN / QPL / TRI
- ✅ 赛马日检测：场地 + 总场次数
- ⚠️ 赛果：仅保留 `finalPosition` 名次；详细完成时间/头马距离仍依赖页面
- ❌ 仍需页面抓取：马匹历史战绩、贴士指数、running positions

| 数据类型 | TTL | 说明 |
|----------|-----|------|
| 历史赛果（已结束） | 7 天 | 赛果不变，长期缓存；优先取 API 名次 |
| 当日赛前排位表 | 30 分钟 | API JSON 优先缓存，可能临时换马/换骑 |
| 马匹历史战绩 | 24 小时 | 每场赛后更新一次，仍抓 Horse.aspx |
| 赔率数据 | 5 分钟 | API 赔率池优先，临场实时变化 |
| 贴士指数 | 30 分钟 | 页面抓取，赛前更新 |


### Step 3: 数据分析

运行分析脚本：

```bash
python scripts/analyze_race.py --date YYYY/MM/DD --venue ST/HV --race N
```

脚本自动完成：优先通过 API 获取参赛马匹/赔率/赛马日信息 → 获取历史战绩 → API 失败时自动回退到页面抓取 → 计算综合评分 → 输出 Softmax 概率分布。


如需外部参考，使用 `web_search` 搜索专家马评（见上方"外部参考"）。

### Step 4: 生成报告

脚本输出 Markdown 格式分析报告，包含前3名概率预测、投注风格定位、全场分项评分、冷门关注、最推荐投注方案。

> 详细报告模板、投注推荐逻辑、马匹对比流程、赛果查询功能均已移至 `references/workflow.md`。

## 快速开始

```bash
# 分析今天沙田第3场（第二次运行使用缓存，秒级完成）
python scripts/analyze_race.py --venue ST --race 3

# 分析指定日期跑马地第5场
python scripts/analyze_race.py --date 2026/03/30 --venue HV --race 5

# 临场前强制刷新赔率
python scripts/analyze_race.py --venue ST --race 3 --force-refresh

# 查看缓存统计
python scripts/analyze_race.py --cache-stats
```

## 注意事项

1. **数据时效性** - 赔率数据实时变化，分析结果仅供参考
2. **历史不代表未来** - 过往战绩仅供参考，不保证未来表现
3. **风险提示** - 赛马投注有风险，请理性参与
4. **数据来源** - 所有数据来自香港赛马会官网 (HKJC)

## Resources

### scripts/

| 文件 | 职责 |
|------|------|
| `main.py` | CLI 解析、主流程编排 |
| `analyze.py` | 单匹马多维度综合评分 |
| `scoring.py` | 所有评分函数（历史/赔率/配速/骑师/贴士等）|
| `api_client.py` | Python 侧 API bridge：subprocess 调用 Node 客户端、统一处理 500ms 节流/重试/结构化缓存 |
| `hkjc_api_client.js` | Node.js 侧 HKJC GraphQL bridge：封装 meetings / race / odds 三类命令 |
| `fetch.py` | API 优先的数据抓取：排位表/赔率优先走 GraphQL，失败后回退 Playwright/HTTP；历史/贴士仍走页面 |
| `parse.py` | 页面回退路径所需的排位表、马匹历史战绩、赛果 HTML 解析 |
| `cache.py` | 磁盘缓存读写、TTL过期、统计清理（API JSON 写入 parsed） |
| `output.py` | Markdown报告格式化、投注风格自动标注 |
| `config.py` | URL常量、API bridge 配置、缓存TTL、权重默认值、场地/状况映射 |
| `weights.py` | 场景/场地/距离适配的动态权重计算 |
| `probability.py` | Softmax归一化概率计算 |
| `analyze_race.py` | **入口兼容层**（直接调用 main.py，CLI用法不变）|
| `daily_scheduler.py` | **自动化调度编排器**（~390行）：批量预测流程编排 + 主流程入口 |
| `scheduler_cache.py` | HTML fallback 专用缓存与页面抓取（由调度器专用）|
| `race_day.py` | 赛马日检测：优先使用 API 判断指定日期是否有赛事，失败后回退页面 |
| `race_results.py` | 实际赛果抓取：优先用 API 取 finalPosition，失败后回退 HTML 解析 |

| `evolution_report.py` | 回测精度计算 + 进化建议生成 + Markdown 报告渲染 |
| `betting.py` | 投注推荐模块：场型判断、价值指数、冷门建议接口、回测命中验证（v1.5.0）|
| `apply_evolution.py` | 进化建议应用工具（含备份/回滚）|
| `dump_race.py` | 调试工具：转储缓存原始数据 |

### references/

- `hkjc_urls.md` - HKJC 网站 URL + GraphQL API 参考

- `analysis_weights.md` - 各维度权重配置（含骑师/练马师动态评分标准、场景自适应规则）
- `expert_sources.md` - 专家预测参考来源
- `workflow.md` - **详细流程手册**：报告模板、投注逻辑、CLI用法、马匹对比/赛果查询完整流程

### 自动生成目录

- `.archive/` - 预测存档 + 回测报告
- `.evolution/` - 进化建议报告 + 应用历史
- `.backups/` - analyze_race.py 历史备份（每次应用进化建议前自动创建）

## 自动化任务

| 任务名 | 时间 | 功能 |
|--------|------|------|
| 赛马日预测 | 每日 14:30 | 检测明天是否赛马日，若是则批量预测所有场次 |
| 赛马回测+进化分析 | 每日 23:30 | 抓取当日实际赛果，对比预测，生成进化建议报告 |

## 进化建议工作流

```
[每日 14:30] 检测赛马日 → 批量预测 → 保存存档
                ↓（当日 23:30）
[每日 23:30] 抓取实际赛果 → 对比预测 → 生成进化建议报告
                ↓（用户审阅后）
[手动确认]  python apply_evolution.py --list
            python apply_evolution.py --report .evolution/xxx.md --apply N
                ↓（应用后）
[自动备份]  .backups/analyze_race_YYYYMMDD_HHMMSS.py
            若效果不好：python apply_evolution.py --rollback
```
