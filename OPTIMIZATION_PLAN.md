# 📋 HK Racing Analyzer — 优化计划

> 本文档记录 Skill 中已确认可行但尚未实施的优化方向，按优先级排列。
> 每次优化完成后，从"待处理"移至"已完成"并附上实施日期。

---

## ✅ 已完成

| # | 优化项 | 版本 | 日期 | 备注 |
|---|--------|------|------|------|
| 0 | `daily_scheduler.py` 重构拆分 | v1.5.2 | 2026-04-07 | 1095行→5个模块，主调度器393行 |
| 1a | opening odds snapshot 端到端修复 | v1.5.1 | 2026-04-07 | odds_drift 18% 权重恢复生效 |
| 1b | running_style 推导验证 | — | 2026-04-07 | `analyze.py` 第84-102行已有推导逻辑，无需改动 |
| 2 | 独赢/位置赔率比值冷门信号 | v1.5.1 | 2026-04-07 | 新增 `score_win_place_ratio()` |
| 3 | 批量预测控制台输出投注建议 | v1.5.0 | 2026-04-07 | 控制台显示 `预测前3：[1, 4, 10]  \|  推荐：独赢 #1` |

---

## 🟡 待处理（按优先级）

### #4 — `pace_index` 阈值验证

**类型**：Bug 确认  
**优先级**：中  
**当前状态**：`score_sectional()` 的阈值逻辑（pace_index < 1 = 快 = 高分）定义正确，但 HKJC 排位表 HTML 中是否真的提供了分段计时数据需要验证。

**验证方法**：
1. 用 Playwright 抓取一场历史赛事的排位表 HTML
2. 搜索 `sectional`、`分段`、`time` 相关字段
3. 若无数据 → `pace_index` 永远为默认值 1.0，配速评分永远为 50 分（8% 权重空转）

**可能行动**：
- 若 HKJC 无此数据：从赛果页（LocalResults）提取实际完成时间，反推 `pace_index` 作为代理指标
- 若确认无法获取：考虑从历史完成时间的分布推断（快于平均→高分，慢于平均→低分）

**工作量**：低（主要是验证和调研）

---

### #5 — 时间衰减曲线实证验证

**类型**：调参  
**优先级**：中  
**当前**：`scoring.py` 的 `_time_weight()` 使用固定衰减曲线（近30天×1.0，31-90天×0.8）。

**问题**：衰减曲线未经实证，不同场地（ST vs HV）或不同距离可能适用不同曲线。

**方案**：对历史数据集（.archive 中的预测存档 + 赛果）跑网格搜索，测试以下曲线：

```python
# 方案A（当前）
{0: 1.0, 30: 0.8, 90: 0.6, 180: 0.4}

# 方案B（更陡）
{0: 1.0, 14: 0.9, 30: 0.7, 60: 0.5, 180: 0.3}

# 方案C（更缓）
{0: 1.0, 60: 0.9, 120: 0.8, 180: 0.7}
```

**工作量**：中（需构建历史数据集 + 编写搜索脚本）

---

### #6 — 赛季级骑师/练马师统计

**类型**：新特征  
**优先级**：低  
**当前**：`score_jockey()` 和 `score_trainer()` 仅从"本马历史战绩"中提取骑师/练马师数据。

**优化**：HKJC 公开每赛季的骑师/练马师总胜率，可作为跨马通用信号：

```python
# HKJC URL
JOCKEY_SEASON_URL = "https://racing.hkjc.com/racing/information/Chinese/Jockey/..."
TRAINER_SEASON_URL = "https://racing.hkjc.com/racing/information/Chinese/Trainer/..."
```

**叠加逻辑**：在现有本马专有评分基础上，叠加"该骑师/练马师当前赛季的整体胜率"作为 bonus。

**工作量**：中（需要抓取 + 解析 + 评分融合）

---

### #7 — 缺赛/新马兜底评分

**类型**：边界处理  
**优先级**：低  
**当前**：新马或长期缺赛后复出的马，所有历史评分返回中性 50 分。

**优化**：用该马的"总体历史前3率"（不限场地/距离）作为降级兜底评分：

```python
def _overall_top3_rate(history: list) -> float:
    """全场不限条件的前3率"""
    if not history:
        return 0.0
    top3 = sum(1 for r in history if r.get("position", 99) <= 3)
    return top3 / len(history)

# 当 same_condition_score 和 same_venue_score 都接近默认值时，
# 用 overall_top3_rate 作为兜底加成
```

**工作量**：低

---

### #8 — 投注模块增强：价值金额建议

**类型**：功能增强  
**优先级**：低  
**当前**：`betting.py` 只推荐"买哪个"，没有建议"买多少钱"。

**方案**：加入简单凯利公式，根据价值指数决定下注比例：

```python
def kelly_fraction(value_index: float, odds: float) -> float:
    """
    凯利公式简化版：
    f* = (bp - q) / b
    其中 b = 赔率 - 1, p = 隐含胜率, q = 1 - p
    """
    if not value_index or value_index <= 0:
        return 0  # 不值得下注
    implied_prob = (1.0 / odds) * 0.92
    b = odds - 1
    if b <= 0:
        return 0
    kelly = (value_index * b - (1 - implied_prob)) / b
    return max(0, min(kelly, 0.2))  # 上限20%防止过度集中
```

**工作量**：低

---

### #9 — 精度追踪面板

**类型**：工具  
**优先级**：低  
**当前**：每次回测手动查看进化报告，无累积追踪。

**方案**：在 `.evolution/` 目录下维护 `metrics.json`：

```json
{
  "history": [
    {"date": "2026-04-02", "venue": "ST", "top1_rate": 0.111, "top3_rate": 0.296, "bet_rate": null},
    {"date": "2026-04-06", "venue": "ST", "top1_rate": 0.273, "top3_rate": 0.455, "bet_rate": null}
  ]
}
```

`compare_and_evolve()` 每次运行后追加记录，输出精度趋势摘要（不依赖外部库）。

**工作量**：中

---

### #10 — 赛果缓存"完赛状态"检查

**类型**：技术债  
**优先级**：低  
**当前**：赛果缓存 TTL=7天，但若赛事未结束时抓取（空结果 HTML），会污染后续解析。

**方案**：缓存赛果时，同时记录"完赛马数"。加载缓存时验证马数是否合理（≥10匹）：

```python
def _cache_set_race_result(url: str, html: str, parsed: dict):
    # 赛果缓存时记录马数
    horse_count = len(parsed.get("results", []))
    _cache_set(url, html, parsed={**parsed, "_horse_count": horse_count})

def _cache_get_with_validation(url: str, ttl: int):
    cached = _cache_get(url, ttl)
    if cached and cached.get("_horse_count", 0) < 10:
        return None  # 数据不完整，当作缓存未命中
    return cached
```

**工作量**：低

---

### #11 — Playwright 实例稳定性

**类型**：技术债  
**优先级**：低  
**当前**：`PlaywrightManager` 单例在长时间运行（如深夜自动化）后可能超时。

**方案**：加入健康检查：

```python
@classmethod
def is_healthy(cls) -> bool:
    """检查浏览器实例是否仍然可用"""
    if not cls._initialized or not cls._browser:
        return False
    try:
        # 简单 ping
        cls._browser.new_page().close()
        return True
    except Exception:
        return False
```

若不健康，自动重启浏览器实例。

**工作量**：低

---

## 📝 更新记录

| 日期 | 变更 | 操作人 |
|------|------|--------|
| 2026-04-07 | 初始创建，从 v1.5.1 优化分析中分离待处理项 | WorkBuddy |
