# Analysis Dimension Weight Configuration

## Module Architecture (v1.4.0 Refactored)

> Original `analyze_race.py` (~600 lines) has been split into 11 independent modules for clear responsibilities, maintainability, and testability.

| Module | Lines | Responsibility |
|:-------|:-----:|:---------------|
| `main.py` | ~200 | CLI parsing, main workflow orchestration |
| `analyze.py` | ~140 | Single horse multi-dimensional scoring |
| `scoring.py` | ~470 | All scoring functions (history/odds/pace/jockey/expert) |
| `fetch.py` | ~340 | HTTP requests, Playwright dynamic loading, horse history/tips index |
| `parse.py` | ~330 | Race card & horse history HTML parsing |
| `cache.py` | ~150 | Disk cache read/write, TTL expiry, stats cleanup |
| `output.py` | ~110 | Markdown report formatting |
| `config.py` | ~80 | URL constants, cache TTL, default weights, venue/condition mapping |
| `weights.py` | ~70 | Scenario/venue/distance-adaptive dynamic weight calculation |
| `probability.py` | ~40 | Softmax normalized probability calculation |
| `analyze_race.py` | ~27 | **Entry compatibility layer** (directly calls main.py, CLI usage unchanged) |

---

## Current Weight Settings

> Historical performance is split into 3 sub-dimensions; Odds is split into absolute value and drift. Total remains 100%.

### Base Weights (Default Scenario)

| Dimension | Sub-dimension | Weight | Description |
|-----------|---------------|--------|-------------|
| **Historical Performance** | Same distance + same venue (last 5 races) | **15%** | Most precise reference: same condition results |
| | Same venue only (last 5 races, any distance) | **10%** | Venue adaptability reference |
| | Class fit (rating vs class range match) | **8%** | Impact of class rise/drop on competitiveness |
| **Odds** | Final odds (absolute value) | **15%** | Reflects current market expectation |
| | Odds drift (opening → final change magnitude) | **13%** | Reflects money flow; significant shortening = strong signal |
| **Sectional Timing/Pace** | Pace index (late sprint ability) | **15%** | Calculated from historical sectional times, not manual judgment |
| **Jockey** | — | **8%** | Win rate and record on this horse |
| **Trainer** | — | **7%** | Stable win rate and current form |
| **Barrier** | — | **5%** | Win rate by barrier at same distance |
| **Expert Predictions** | — | **4%** | Multi-expert consensus rate (reduced from 6% → 4%) |
| **Total** | | **100%** | |

---

## Scenario-Adaptive Weight Adjustments

### Happy Valley (HV) Races
- Barrier weight increase: 5% → 8% (tight turns make inside barriers more important)
- Offset by reducing: Same venue history 10% → 7%

### Sha Tin (ST) Long-distance Races (1800m+)
- Sectional timing weight increase: 15% → 20% (pace strategy more critical)
- Offset by reducing: Final odds absolute value 15% → 10%

### Dirt Track Races
- Add "dirt track preference" dimension, weight 10%
- Same distance + same venue history 15% → 5% (focus on dirt-specific records)
- Same venue history 10% → 0% (replaced by dirt-related dimensions)

### Newcomer (Debut Horse)
- Same distance + same venue history: 0% (no reference data)
- Class fit increased: 8% → 15%
- Replace with jockey weight 15% + trainer weight 13% (more important for debut)

### Class Drop
- Class fit increased: 8% → 15%
- Odds drift increased: 13% → 18%
- Expert predictions: 4% → 0%

### Class Rise
- Same distance + same venue history reduced: 15% → 8%
- Odds drift increased: 13% → 18%
- Expert predictions: 4% → 0%

---

## Scoring Standards

### Historical Performance Score — Sub-dimension: Same Condition (0-100)

| Condition | Score Range | Note |
|-----------|-------------|------|
| Won last 3 races (same condition) | 90-100 | Highest confidence |
| 2+ wins in last 5 races (same condition) | 70-89 | |
| 1 win in last 5 races (same condition) | 50-69 | |
| No wins but placed top 3 in last 5 (same condition) | 30-49 | |
| No top 3 in last 5 (same condition) | 10-29 | |
| No same-condition race records | 40 (neutral default) | No penalty, no bonus |

> ⚠️ "Same condition" definition: Same venue (ST/HV) + same distance (within ±200m)

---

### Historical Performance Score — Sub-dimension: Class Fit (0-100)

| Condition | Score Range | Description |
|-----------|-------------|-------------|
| Rating 5+ points above class ceiling | 75-90 | Clear class drop, strong advantage |
| Rating within class range | 50-70 | Normal competition |
| Rating 3+ points below class floor | 20-45 | Class rise, tough competition |
| First time in this class | 50 (neutral default) | |

---

### Odds Score — Sub-dimension: Final Odds Absolute Value (0-100)

| Condition | Score Range |
|-----------|-------------|
| Heavy favorite (odds < 3.0) | 80-100 |
| Favorite (odds 3.0-5.0) | 60-79 |
| Mid-range (odds 5.0-10.0) | 40-59 |
| Outsider (odds 10.0-20.0) | 20-39 |
| Long shot (odds > 20.0) | 0-19 |

---

### Odds Score — Sub-dimension: Odds Drift (0-100)

| Condition | Score Range | Description |
|-----------|-------------|-------------|
| Odds shortened > 50% (e.g. 10→4) | 80-100 | Heavy money in, strong signal |
| Odds shortened 20-50% | 60-79 | Notably favored |
| Odds change within ±20% | 40-60 | Stable market, no clear signal |
| Odds drifted 20-50% | 20-39 | Money out, bearish |
| Odds drifted > 50% | 0-19 | Strong negative signal |

> If no opening odds data is available, use neutral default score of 50.

---

### Sectional Timing Score (Based on Historical Data) (0-100)

**Pace Index Calculation:**
```
Pace Index = Horse's avg last-300m time / Standard last-300m time for that distance
Pace Index < 1.0 → Strong late sprint ability (higher score)
Pace Index > 1.0 → Weak late sprint ability (lower score)
```

**Track Condition Match Adjustment:**

| Running Style | Track Condition | Score Range | Note |
|---------------|-----------------|-------------|------|
| Front-runner | Fast/Good-to-Firm | 70-85 | Front-runners benefit on fast tracks |
| Closer | Good/Yielding | 70-85 | Closers have more room on slow tracks |
| Front-runner | Good/Yielding | 40-60 | Unfavorable condition |
| Closer | Fast | 40-60 | Unfavorable condition |
| Even-paced | Any | 50-70 | Moderate track sensitivity |
| No historical sectional data | — | 50 (neutral default) | |

---

## Probability Calculation Formula (Optimized)

### Core Improvement: Softmax Normalization + Probability Cap

```python
import numpy as np

def calculate_probability(scores, temperature=1.5):
    """
    Calculate win probability using Softmax normalization.
    Avoids extreme skew from linear normalization.
    
    Args:
        scores: List of composite scores for each horse
        temperature: Temperature parameter (higher = more evenly distributed)
                     Recommended range: 1.2–2.0
    
    Returns:
        List of win probabilities (sum = 100%)
    """
    scores = np.array(scores, dtype=float)
    
    # Softmax normalization
    exp_scores = np.exp(scores / temperature)
    probabilities = exp_scores / exp_scores.sum()
    
    # Cap: single horse probability should not exceed 50%
    probabilities = np.clip(probabilities, 0, 0.50)
    
    # Re-normalize
    probabilities = probabilities / probabilities.sum()
    
    return (probabilities * 100).round(1).tolist()
```

### Composite Score Calculation (with Scenario Weights)

```python
def get_weights(venue, distance, track_type, race_scenario):
    """
    Returns the appropriate weight dictionary based on venue, distance,
    track type, and race scenario.
    
    race_scenario options:
        "normal"      - Standard race (default)
        "newcomer"    - Debut horse
        "class_down"  - Class drop
        "class_up"    - Class rise
    """
    # Default weights
    weights = {
        "history_same_condition": 0.15,
        "history_same_venue":     0.10,
        "class_fit":              0.08,
        "odds_value":             0.15,
        "odds_drift":             0.13,
        "sectional":              0.15,
        "jockey":                 0.08,
        "trainer":                0.07,
        "barrier":                0.05,
        "expert":                 0.04,
    }
    
    # Scenario adjustments
    if race_scenario == "newcomer":
        weights["history_same_condition"] = 0.00
        weights["history_same_venue"]     = 0.00
        weights["class_fit"]              = 0.15
        weights["expert"]                 = 0.00
        weights["jockey"]                 = 0.15
        weights["trainer"]                = 0.13
    
    elif race_scenario == "class_down":
        weights["class_fit"]              = 0.15
        weights["odds_drift"]             = 0.18
        weights["expert"]                 = 0.00
        weights["history_same_condition"] = 0.10
        weights["history_same_venue"]     = 0.07
    
    elif race_scenario == "class_up":
        weights["history_same_condition"] = 0.08
        weights["history_same_venue"]     = 0.09
        weights["odds_drift"]             = 0.18
        weights["expert"]                 = 0.00
    
    # Venue adjustment
    if venue == "HV":
        weights["barrier"]            += 0.03
        weights["history_same_venue"] -= 0.03
    
    # Distance adjustment
    if distance >= 1800:
        weights["sectional"]  += 0.05
        weights["odds_value"] -= 0.05
    
    # Track type adjustment
    if track_type == "dirt":
        weights["history_same_condition"] = 0.05
        weights["history_same_venue"]     = 0.00
        weights["class_fit"]             += 0.05
    
    return weights
```

### Track Factor (Supplementary)

| Track | Factor |
|-------|--------|
| Sha Tin Turf | 1.0 |
| Happy Valley Turf | 1.0 |
| Sha Tin Dirt | 0.95 |

### Distance Factor (Supplementary)

| Distance | Factor |
|----------|--------|
| Sprint (1000m-1200m) | 1.0 |
| Mile (1400m-1600m) | 1.0 |
| Middle distance (1800m-2000m) | 0.98 |
| Long distance (2200m+) | 0.95 |

---

## Data Confidence Rating

Each horse's prediction includes a "data confidence" tag to indicate scoring reliability.

| Rating | Condition | Note |
|--------|-----------|------|
| ⭐⭐⭐ High | ≥3 same-condition races + complete odds drift data | High reliability |
| ⭐⭐ Medium | 1-2 same-condition races, or missing odds drift | Moderate reference value |
| ⭐ Low | No same-condition history, or debut horse | Score mainly based on odds and jockey/trainer |

---

## Longshot Alert Criteria

Flag a horse as "Longshot Alert" if ALL of the following are met:

1. Final odds > 15
2. Has at least one **top-3 finish** in same-condition race history
3. Odds drift is **not negative** (final odds within 20% of opening odds)
4. Class fit score ≥ 50

> Longshot Alert does not mean a recommendation — it signals potential for an upset. Use with other factors.

---

## Revision History

| Date | Changes |
|------|---------|
| 2026-04-01 | **v1.4.0 Modular Refactoring**: analyze_race.py (~600 lines) split into 11 independent modules (main/analyze/scoring/fetch/parse/cache/output/config/weights/probability), entry compatibility layer preserved with unchanged CLI |
| 2026-03-30 | Dynamic jockey/trainer scoring: weights reduced from 8%/7% to 5%/4% (secondary factors), fixed 50-score replaced with history-based dynamic statistics; released 6% added to historical performance (same-condition +3%→18%, same-venue +3%→13%); added jockey/trainer scoring criteria documentation |
| 2026-03-30 | Initial weight optimization: historical performance split into 3 sub-dimensions; odds split into absolute value + drift; sectional timing replaced with quantitative pace index from actual split times; probability calculation switched to Softmax + cap; added scenario-adaptive weights, data confidence rating, and longshot alert criteria |
