# Analysis Dimension Weight Configuration

## Module Architecture (v1.4.0 Refactored)

> Original `analyze_race.py` (~600 lines) split into 11 independent modules for clear responsibilities, easy maintenance and testing.

| Module | Lines | Responsibility |
|:-------|:-----:|:--------------|
| `main.py` | ~200 | CLI parsing, main flow orchestration |
| `analyze.py` | ~140 | Multi-dimension composite scoring for single horses |
| `scoring.py` | ~530 | All scoring functions (history/odds/pace/jockey/tips, incl. v1.4.13 win/place ratio) |
| `fetch.py` | ~340 | HTTP requests, Playwright dynamic loading, horse history/tip ratings |
| `parse.py` | ~330 | Race card, horse race history HTML parsing |
| `cache.py` | ~150 | Disk cache read/write, TTL expiry, statistics cleanup |
| `output.py` | ~110 | Markdown report formatting |
| `config.py` | ~80 | URL constants, cache TTL, weight defaults, venue/condition mappings |
| `weights.py` | ~70 | Dynamic weight calculation by scenario/venue/distance |
| `probability.py` | ~40 | Softmax normalization probability calculation |
| `analyze_race.py` | ~27 | **Entry compatibility layer** (delegates to main.py, CLI usage unchanged) |

---

## Current Weight Settings

> Historical performance split into three sub-dimensions, odds split into absolute value and drift, total still 100%.

### Base Weights (Default Scenario)

> Last updated: 2026-04-05 (v1.4.11 odds weight optimization)

| Dimension | Sub-dimension | Weight | Change | Notes |
|-----------|---------------|--------|--------|-------|
| **Historical Performance** | Same distance + venue, last 5 races | **13%** | ↓ -3% | Reduced history weight, supplemented by odds consensus |
| | Same venue (any distance), last 5 races | **15%** | ↓ -3% | Same as above |
| | Class fit (rating vs race class match) | **7%** | ↓ -1% | Secondary factor |
| **Odds** | Final odds composite score | **22%** | **↑ +7%** | 20-tier win odds + place bonus + implied probability fusion (v1.4.11) |
| | Odds drift (opening → final change magnitude) | **18%** | **↑ +3%** | Reflects capital flow, market signals valued more |
| **Pace/Sectionals** | Pace index (late sprint ability) | **8%** | ↓ -2% | ⚠️ Temporarily reduced (no empirical data yet), restore to 10% when data is connected |
| **Jockey** | — | **4%** | ↓ -1% | Dynamic calculation based on win/top3 rate of jockey × this horse in historical records |
| **Trainer** | — | **3%** | ↓ -1% | Dynamic calculation based on win/top3 rate of trainer × this horse in historical records |
| **Barrier** | — | **4%** | ↓ -1% | Same-distance barrier win rate statistics |
| **HKJC Tip Index** | — | **6%** | — | Official daily tip index (unchanged) |
| **External Expert Picks** | — | **0%** | **↓ -4%** | Unstable data source, removed |
| **Odds System Total** | | **40%** | **↑ +10%** | Odds formally became the dominant prediction signal |
| **Weight Bonus** | — | **Bonus** | +5~+11 | v1.6.3: Lightweight horses bonus, HV short races extra bonus |
| **TJ Combo Bonus** | — | **Bonus** | +6~+10 | v1.6.3: Top jockey+trainer combo whitelist bonus |
| **Total** | | **100%** | | |

> ⚠️ **v1.4.11 Odds Scoring Fusion**: Odds composite score = `win odds tier(20 tiers)×0.4 + implied probability×0.6`, cap=0.50 compresses extreme gaps. 1.8x super favorite → model prediction ~80.6% (implied ~51% + stacked positive signals → reasonable high confidence). Softmax T=4.0, PROB_CAP=0.88.

> ⚠️ **Weight Notes**: Jockey/trainer weights changed from fixed 50 to dynamic scoring based on this horse's historical records (see scoring criteria below).

---

## Scenario-Adaptive Weight Adjustment

### Happy Valley (HV) Races
- Barrier weight increases: 5% → 8% (tight turns, inner barrier advantage)
- Corresponding reduction: same-venue history 10% → 7%

### Sha Tin (ST) Long Distance (1800m+)
- Pace weight increases: 15% → 20% (long distance pace strategy more important)
- Corresponding reduction: final odds absolute value 15% → 10%

### Dirt Races
- Adds "dirt suitability" sub-dimension, weight 10%
- From "same distance + venue" history 15% → 5%, specifically looking at dirt performance
- Same-venue history 10% → 0% (fully replaced by dirt-related dimensions)

### First-Time Starters (Newcomers)
- Same distance + venue history weight set to 0% (no reference)
- Adds "morning trackwork state/rating" dimension as replacement, weight 15%
- Class fit increases: 8% → 15%
- Tip index increases: 6% → 8% (newcomers rely more on official tips)

### Class-Down Horses
- Class fit increases: 8% → 15%
- Odds drift increases: 13% → 18% (market reacts more sensitively to class-down horses)
- Tip index decreases: 6% → 4%
- Corresponding reduction: external expert picks 4% → 0%

### Class-Up Horses
- History weight reduced: same distance + venue 15% → 8% (different high-class competition)
- Odds drift increases: 13% → 18%
- Tip index decreases: 6% → 4%
- Corresponding reduction: external expert picks 4% → 0%

---

## Scoring Criteria

### Historical Performance Scoring (Sub-dimension: Same Distance + Venue, Last 5 Races) (0-100)

| Condition | Score Range | Notes |
|-----------|-------------|-------|
| Won last 3 races (same conditions) | 90-100 | Highest credibility |
| 2+ wins in last 5 races (same conditions) | 70-89 | |
| 1 win in last 5 races (same conditions) | 50-69 | |
| No wins but top-3 in last 5 races (same conditions) | 30-49 | |
| No top-3 in last 5 races (same conditions) | 10-29 | |
| No same-condition race record | 40 (neutral default) | No penalty, no reward |

> ⚠️ "Same conditions" definition: same venue (ST/HV) + same distance (±200m tolerance)

---

### Historical Performance Scoring (Sub-dimension: Class Fit) (0-100)

| Condition | Score Range | Description |
|-----------|-------------|-------------|
| Rating exceeds class ceiling by 5+ points | 75-90 | Clear class drop, has advantage |
| Rating matches class range | 50-70 | Normal competition |
| Rating below class floor by 3+ points | 20-45 | Class rise, struggling |
| First time in this class | 50 (neutral default) | |

---

### Odds Scoring (Sub-dimension: Final Odds Absolute Value) (0-100)

| Condition | Score Range |
|-----------|-------------|
| Super favorite (odds < 3.0) | 80-100 |
| Favorite (odds 3.0-5.0) | 60-79 |
| Mid-range (odds 5.0-10.0) | 40-59 |
| Long shot (odds 10.0-20.0) | 20-39 |
| Heavy long shot (odds > 20.0) | 0-19 |

---

### Odds Scoring (Sub-dimension: Odds Drift Change Magnitude) (0-100)

| Condition | Score Range | Description |
|-----------|-------------|-------------|
| Odds shortened > 50% (e.g. 10→4) | 80-100 | Heavy capital inflow, strong signal |
| Odds shortened 20-50% | 60-79 | Clearly favored |
| Odds change within ±20% | 40-60 | Market stable, no clear signal |
| Odds lengthened 20-50% | 20-39 | Capital outflow, bearish |
| Odds lengthened > 50% | 0-19 | Strong bearish signal |

> If no opening odds data is available, this sub-dimension uses neutral default score of 50.

---

### Odds Scoring (New Sub-dimension: Win/Place Ratio) (0-100)

> **v1.4.13 New**: `score_win_place_ratio()`, a cold-shot signal independent of odds_value scoring.

| Ratio Range (Win Odds ÷ Place Odds) | Score | Market Interpretation |
|-------------------------------------|-------|----------------------|
| < 2.0 | 78 | Win≈Place, market extremely bullish on win |
| 2.0 - 2.5 | 68 | Strongly bullish on win |
| 2.5 - 4.0 | 50 | Normal market pricing |
| 4.0 - 5.5 | 38 | High ratio, market thinks "can place but hard to win" |
| > 5.5 | 25 | Very high, market thinks almost impossible to win (true weak horse) |

**Application**: This signal is used in `betting.py`'s longshot recommendations, filtering out "fake cold shots" (horses with high win odds but also low place odds — not truly high-value win targets).

---

### Pace Scoring (Based on Historical Split Times) (0-100)

**Pace Index Calculation**:
```
Pace Index = Historical avg last 300m time / Standard last 300m time for this distance
Pace Index < 1.0 → Strong late sprint ability (high score)
Pace Index > 1.0 → Weak late sprint ability (low score)
```

**Surface Condition Match Adjustment**:

| Running Style | Surface Condition | Score Range | Description |
|--------------|-------------------|-------------|-------------|
| Front-runner | Fast/Firm to Good | 70-85 | Front-runners have significant advantage on fast tracks |
| Closer | Slow/Good | 70-85 | Closers have more room on slow tracks |
| Front-runner | Good/Slow | 40-60 | Unfavorable surface |
| Closer | Fast | 40-60 | Unfavorable surface |
| All-purpose | Any | 50-70 | Moderate surface impact |
| No historical split data | — | 50 (neutral default) | |

---

## Probability Calculation Formula (Optimized)

### Core Improvement: Softmax Normalization + Probability Cap

```python
import numpy as np

def calculate_probability(scores, temperature=4.0):
    """
    Use Softmax normalization to calculate probability,
    avoiding extreme bias from linear normalization.

    Parameters:
        scores: List of composite scores for each horse
        temperature: Temperature parameter. Higher = more even probability distribution
                    Current: 4.0 (v1.4.11, ↑ from 2.0 in v1.4.3)

    Returns:
        List of win probabilities for each horse (sums to 100%)
    """
    scores = np.array(scores, dtype=float)

    # Softmax normalization
    exp_scores = np.exp(scores / temperature)
    probabilities = exp_scores / exp_scores.sum()

    # Cap: single horse probability not exceeding 88%
    # (PROB_CAP = 0.88 in v1.4.11)
    probabilities = np.clip(probabilities, 0, 0.88)

    # Re-normalize
    probabilities = probabilities / probabilities.sum()

    return (probabilities * 100).round(1).tolist()
```

### Composite Score Calculation (With Scenario Weights)

```python
def get_weights(venue, distance, track_type, race_scenario):
    """
    Return appropriate weight dictionary based on venue, distance,
    track type and race scenario.

    race_scenario options:
        "normal"      - Normal race (default)
        "newcomer"    - First-time starter
        "class_down"  - Class drop
        "class_up"    - Class rise
    """
    # Default weights (latest version, v1.4.11)
    weights = {
        "history_same_condition": 0.13,   # Same distance + venue history
        "history_same_venue":     0.15,   # Same venue (any distance) history
        "class_fit":              0.07,   # Class fit
        "odds_value":             0.22,   # Final odds absolute value
        "odds_drift":             0.18,   # Odds drift
        "sectional":              0.08,   # Pace/sectional index
        "jockey":                 0.04,   # Jockey (dynamic scoring)
        "trainer":                0.03,   # Trainer (dynamic scoring)
        "barrier":                0.04,   # Barrier
        "expert":                 0.00,   # Expert picks (removed in v1.4.11)
        "tips":                   0.06,   # HKJC tip index
    }

    # Scenario adjustments
    if race_scenario == "newcomer":
        weights["history_same_condition"] = 0.00
        weights["history_same_venue"]     = 0.00
        weights["class_fit"]              = 0.15
        weights["tips"]                   = 0.08
        # Returned weight distributed to jockey and trainer
        weights["jockey"]   = 0.15
        weights["trainer"]  = 0.13
        weights["odds_value"] = 0.20
        weights["odds_drift"] = 0.14

    elif race_scenario == "class_down":
        weights["class_fit"]  = 0.15
        weights["odds_drift"] = 0.18
        weights["expert"]     = 0.00
        weights["tips"]       = 0.04
        weights["history_same_condition"] = 0.10
        weights["history_same_venue"]     = 0.07

    elif race_scenario == "class_up":
        weights["history_same_condition"] = 0.08
        weights["odds_drift"] = 0.18
        weights["expert"]     = 0.00
        weights["tips"]       = 0.04
        weights["history_same_condition"] = 0.08
        weights["history_same_venue"]     = 0.09

    # Venue adjustments
    if venue == "HV":
        weights["barrier"]            += 0.03
        weights["history_same_venue"] -= 0.03

    # Distance adjustments
    if distance >= 1800:
        weights["sectional"]  += 0.05
        weights["odds_value"] -= 0.05

    # Dirt adjustments
    if track_type == "dirt":
        weights["history_same_condition"] = 0.05  # Specifically look at dirt performance
        weights["history_same_venue"]     = 0.00
        weights["class_fit"]             += 0.05

    return weights
```

### Venue Factors (Retained as auxiliary adjustment)

| Venue | Factor |
|-------|--------|
| Sha Tin Turf | 1.0 |
| Happy Valley Turf | 1.0 |
| Sha Tin Dirt | 0.95 |

### Distance Factors (Retained)

| Distance | Factor |
|----------|--------|
| Sprint (1000m-1200m) | 1.0 |
| Mile (1400m-1600m) | 1.0 |
| Middle (1800m-2000m) | 0.98 |
| Long (2200m+) | 0.95 |

---

## Data Sufficiency & Confidence Level

Each horse is tagged with "data sufficiency" when generating predictions, indicating the reliability of the score.

| Data Sufficiency | Condition | Description |
|------------------|-----------|-------------|
| ⭐⭐⭐ High | Same-condition starts ≥ 3, odds drift data complete | Score highly reliable |
| ⭐⭐ Medium | Same-condition starts 1-2, or odds drift missing | Score has some reference value |
| ⭐ Low | No same-condition history, or first-time starter | Score mainly relies on odds and jockey/trainer |

---

## Long Shot Watch Filter Logic

Horses meeting **all** of the following conditions are tagged as "Long Shot Watch":

1. Final odds > 15
2. Has same-condition (same distance + venue) **top-3** record in history
3. Odds drift is **not lengthening** (opening-to-final difference < 20%)
4. Class fit score ≥ 50

> Long Shot Watch does not mean recommended bet. It only indicates upset potential — combine with other factors to judge.

---

### Jockey Scoring (Dynamic Calculation) (0-100)

Jockey scoring no longer uses fixed values but dynamically calculates from this horse's **historical performance**:

**Priority Logic (this jockey rode this horse ≥ 2 races)**:

| Win/Top-3 Rate | Score | Description |
|----------------|-------|-------------|
| Win rate ≥ 40% | 88 | Most trusted jockey for this horse |
| Win rate 20-40% | 75 | Good combination |
| Top-3 rate ≥ 50% | 65 | Consistent performance |
| Top-3 rate 30-50% | 55 | Average |
| Top-3 rate 10-30% | 42 | Below average |
| Top-3 rate < 10% | 28 | Poor combination |

**Fallback Logic (jockey rode this horse < 2 races)**: Compare with field-wide jockey average top-3 rate:

| Relative to Baseline | Score |
|---------------------|-------|
| Top-3 rate ≥ 2× baseline | 70 |
| Top-3 rate ≥ 1.3× baseline | 60 |
| Top-3 rate within 0.7-1.3× baseline | 50 |
| Top-3 rate < 0.7× baseline | 38 |
| First time riding this horse | 46 (neutral low) |
| No historical data | 50 (neutral) |

---

### Trainer Scoring (Dynamic Calculation) (0-100)

Trainer is long-term bound to the horse. Scoring logic similar to jockey, but requires ≥ 3 races of sample:

**Priority Logic (this trainer handled this horse ≥ 3 races)**:

| Win/Top-3 Rate | Score |
|----------------|-------|
| Win rate ≥ 35% | 85 |
| Win rate 15-35% | 70 |
| Top-3 rate ≥ 50% | 62 |
| Top-3 rate 30-50% | 52 |
| Top-3 rate 10-30% | 40 |
| Top-3 rate < 10% | 28 |

**Fallback Logic (< 3 races sample)**:

| Condition | Score |
|-----------|-------|
| New trainer (recent change) | 42 (high uncertainty) |
| Old trainer but few races, has top-3 | 55 |
| Old trainer but few races, no top-3 | 48 |

---

### Lightweight Horse Scoring (v1.6.3 New)

**Weight Bonus**: Lower weight means lighter load for the horse, especially advantageous on Happy Valley short-distance races and tracks with many turns.

Inspired by the other skill: weight < 120 lbs receives bonus points.

| Condition | Bonus | Description |
|-----------|-------|-------------|
| Weight < 115 lbs | +8 | Ultra-lightweight, significant advantage |
| Weight < 120 lbs | +5 | Lightweight, obvious advantage |
| Weight < 125 lbs | +3 | Slightly lightweight |
| Weight > 135 lbs | -5 | Heavy weight burden |
| Weight > 130 lbs | -2 | Slightly heavy |
| HV Happy Valley ≤ 1200m | +3 | Extra bonus (more turns, lightweight advantage amplified) |
| HV Happy Valley ≤ 1650m | +1 | Slight bonus |

> This bonus is a direct bonus item, not affected by weights. It is added directly to the total score.

---

### Top TJ Combo Scoring (v1.6.3 New)

**TJ Combo Bonus**: Top jockey + trainer combinations have better synergy.

Inspired by the other skill: Maintain a top TJ combo whitelist. When matched, give extra bonus points.

**Default Top Combo Whitelist**:

| Jockey | Trainer | Bonus |
|--------|---------|-------|
| Z Purton | J Size | +10 |
| V R Richards | J Size | +9 |
| Z Purton | C Fownes | +8 |
| K H Yeung | P F Yiu | +7 |
| H T Mo | K W Lui | +7 |
| C L Chau | K W Lui | +6 |
| A Badenoch | C S Shum | +6 |
| J J M Cavieres | D J Whyte | +6 |
| M Chadwick | A S Cruz | +6 |

> Matching method: Prefix matching of jockey_name and trainer_name (case-insensitive).

---

## Revision History

| Date | Version | Changes |
|------|---------|---------|
| 2026-04-09 | **v1.6.3** | New lightweight horse bonus (score_weight_bonus); New top TJ combo bonus (score_tj_combo_bonus) |
| 2026-04-07 | **v1.5.1** | odds_drift end-to-end fix: opening_odds_snapshot backfill now effective; new `score_win_place_ratio()` win/place ratio cold-shot signal; longshot recommendations enhanced with fake-cold-shot filter |
| 2026-04-05 | **v1.4.11 Odds weight optimization**: odds_value 15%→22%, odds_drift 18%→18%, Softmax T=4.0, PROB_CAP=0.88, added 20-tier fine-grained odds scoring, implied probability fusion, place odds bonus |
| 2026-04-02 | **v1.4.3 Evolution suggestions applied**: ①Softmax temperature 1.5→2.0; ②history_same_condition 18%→16%; ③odds_drift 13%→15%; ④sectional 15%→10% (temporary); ⑤history_same_venue 13%→18%; ⑥score_history time decay added (last 30d×1.0, 31-90d×0.8, 91-180d×0.6, >180d×0.4) |
| 2026-04-01 | **v1.4.0 Modular refactoring**: analyze_race.py (~600 lines) split into 11 independent modules (main/analyze/scoring/fetch/parse/cache/output/config/weights/probability), entry compatibility layer keeps CLI unchanged |
| 2026-03-30 | Jockey/trainer scoring dynamic: weights reduced from 8%/7% to 5%/4% (secondary factors), while changing fixed 50 score to dynamic statistical scoring based on historical performance; freed up 6% to supplement history dimensions (same-condition +3%→18%, same-venue +3%→13%); added jockey/trainer scoring criteria documentation |
| 2026-03-30 | Initial weight optimization: historical performance split into 3 sub-dimensions; odds split into absolute value + drift; pace changed to quantitative index based on split times; probability calculation changed to Softmax + cap; added scenario-adaptive weights, data sufficiency tags, long shot filter logic |
