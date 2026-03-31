---
name: hk-racing-analyzer-en
description: Hong Kong Horse Racing Analysis and Prediction Tool. Provides quantitative analysis based on historical performance, odds trends, and sectional timing data, delivering top-3 probability distribution and betting recommendations. Trigger keywords: analyze Sha Tin/Happy Valley race X, horse racing prediction, horse analysis, HKJC racing, today's racing analysis. Use cases: Users want to analyze a specific horse race, predict race outcomes, or view horse historical performance.
---

# Hong Kong Horse Racing Analyzer (HK Racing Analyzer)

Data-driven horse racing prediction tool combining historical data analysis with AI-assisted judgment.

## Core Features

1. **Race Data Analysis** — Scrape HKJC race data and analyze all participating horses
2. **Prediction Analysis** — Provide top-3 probability distribution based on multi-dimensional scoring
3. **Betting Recommendations** — Offer concise win / quinella / dark-horse suggestions
4. **Daily Automation** — Auto-detect race days, batch-predict all races, post-race backtest, self-evolution suggestions

## Analysis Dimensions

### Primary Dimensions (Higher Weight)

| Dimension | Data Source | Analysis Points | Weight |
|-----------|-------------|-----------------|--------|
| **History — Same Condition** | HKJC Horse Profile | Last 5 races at same distance + same venue | **18%** |
| **History — Same Venue** | HKJC Horse Profile | Last 5 races at same venue (any distance) | **13%** |
| **Class Fit** | Race Entry | Rating vs. class ceiling/floor | **8%** |
| **Odds Value** | HKJC Odds Page | Absolute final odds | **15%** |
| **Odds Drift** | HKJC Odds Page | Opening → final odds movement (shortening = strong signal) | **13%** |
| **Sectional / Pace Index** | HKJC Results | Running style derived from historical position calls | **15%** |

### Secondary Dimensions (Lower Weight — Supporting Signals)

| Dimension | Data Source | Analysis Points | Weight |
|-----------|-------------|-----------------|--------|
| Jockey | Horse history (dynamic) | Win/top-3 rate of this jockey on this horse | **5%** |
| Trainer | Horse history (dynamic) | Win/top-3 rate of this trainer with this horse | **4%** |
| Barrier | Historical stats | Barrier win rate at same distance (ST/HV) | **5%** |
| Track Preference | Horse Profile | Turf/Dirt, Good/Fast performance (included in same-condition history) | — |
| Weight/Body Weight | Race Data | Weight carried changes, body weight trends (planned) | — |

> **Note on Jockey/Trainer scoring**: No longer a fixed value of 50. Dynamically computed from the horse's own race history. See `references/analysis_weights.md` for the full scoring rubric.

### External Reference (Supplementary)

| Dimension | Data Source | Analysis Points | Weight |
|-----------|-------------|-----------------|--------|
| **Expert Predictions** | Web Search | Professional racing commentators' consensus | **4%** |

#### How to Obtain Expert Predictions

Use the `web_search` tool:

```
Search Keywords:
- "Sha Tin racing race X prediction"
- "Happy Valley tonight racing tips"
- "HKJC horse racing analysis"
- "racing expert picks"
```

Expert Prediction Integration:
1. Search multiple expert sources
2. Extract hot picks from each expert
3. Calculate consensus ratio (experts recommending this horse ÷ total experts)
4. Apply as supplementary signal at ~4% weight

Notes:
- Expert predictions are reference only; never follow blindly
- Prefer data-backed expert analysis over pure opinion
- Discount extreme optimism/pessimism

---

## Workflow

### Step 1: Parse User Request

Extract from user input:
- Race date (default: today)
- Venue (Sha Tin `ST` / Happy Valley `HV`)
- Race number

Examples:
- "Analyze Sha Tin race 3 today" → date=today, venue=ST, race=3
- "Analyze Happy Valley race 5 tonight" → date=today, venue=HV, race=5

### Step 2: Fetch Race Data (with Caching)

Built-in disk cache avoids redundant network requests.

Cache location:
```
<skill_dir>/.cache/<url_hash>.json
```

| Data Type | TTL | Notes |
|-----------|-----|-------|
| Historical race results (finished) | 7 days | Immutable after race ends |
| Today's race card (pre-race) | 30 min | May change for scratchers/jockey switches |
| Horse historical records | 24 hours | Updated once per race day |
| Odds data | 5 min | Real-time near post time |
| Generic fallback | 1 hour | — |

### Step 3: Data Analysis

#### A. Local Data Analysis

```bash
# Analyze Sha Tin race 3 today (auto-caches on first run)
python scripts/analyze_race.py --venue ST --race 3

# Analyze specific date, Happy Valley race 5
python scripts/analyze_race.py --date 2026/03/30 --venue HV --race 5

# Force refresh — bypass cache (use ~30 min before post)
python scripts/analyze_race.py --venue ST --race 3 --force-refresh

# Clear cache for this race then re-analyze
python scripts/analyze_race.py --venue ST --race 3 --clear-cache

# Show cache statistics
python scripts/analyze_race.py --cache-stats

# Scenario mode: newcomer / class_down / class_up / normal
python scripts/analyze_race.py --venue ST --race 3 --scenario class_down
```

The script will:
1. Check disk cache first; fetch from network only on cache miss / expiry
2. Scrape race card (horse list, draw, weight, jockey, trainer)
3. Fetch each horse's historical performance
4. Get odds data
5. Calculate multi-dimensional scores → Softmax probability → top-3 prediction

#### B. Expert Prediction (Optional)

```bash
web_search "Sha Tin racing race 3 prediction March 2026"
web_search "Happy Valley tonight racing tips"
```

#### C. Final Score Formula

```
Final Score = Local Analysis Score × 96% + Expert Consensus Score × 4%
```

### Step 4: Generate Prediction Report

Output format:

```markdown
## 🏇 [Date] [Venue] Race X Analysis Report

### Race Information
- Race Name / Distance / Class / Track Condition / Prize Money

### 📊 Top-3 Probability Prediction

| Rank | No. | Horse Name | Win Prob. | Key Reason |
|------|-----|------------|-----------|------------|
| 1    | X   | XXX        | XX%       | ...        |
| 2    | X   | XXX        | XX%       | ...        |
| 3    | X   | XXX        | XX%       | ...        |

### 📋 Full Field Scoring

| No. | Horse | Score | History | Odds | Pace | Jockey | Trainer | Barrier | Data ★ |
|-----|-------|-------|---------|------|------|--------|---------|---------|--------|

### 🎯 Expert Prediction Reference

| Horse | Consensus | Representative View |
|-------|-----------|---------------------|

### 💡 Betting Recommendations

**Win**: No.X XXX  
**Quinella**: X–X  
**Dark Horse ⚡**: No.X (odds >15, past top-3 in same condition, odds shortening)

### ⚠️ Risk Warning
```

---

## Daily Automation System

| Task | Schedule | Action |
|------|----------|--------|
| Race Day Prediction | **Daily 14:30** | Detect tomorrow's race day → batch-predict all races → notify summary |
| Backtest + Evolution | **Daily 09:00** | Fetch yesterday's results → compare predictions → send full evolution report |

### Self-Evolution Workflow

```
[14:30 daily]  Detect race day → batch predict all races → save to .archive/
                   ↓ (next morning 09:00)
[09:00 daily]  Fetch actual results → compare predictions
               Calculate accuracy (win rate / top-3 rate)
               Identify systematic bias (over/under-estimated horses)
               Generate structured evolution suggestions
                   ↓ (sent to user for review)
[Manual]       python apply_evolution.py --list
               python apply_evolution.py --report .evolution/xxx.md --apply N
                   ↓ (on apply)
[Auto-backup]  .backups/analyze_race_YYYYMMDD_HHMMSS.py
               To rollback: python apply_evolution.py --rollback
```

**Key principle**: Evolution suggestions are always reviewed by the user first. The Skill is never modified automatically.

---

## Quick Start

```bash
# Single race analysis
python scripts/analyze_race.py --venue ST --race 3

# Check if tomorrow is a race day + run predictions
python scripts/daily_scheduler.py --mode predict

# Run backtest on yesterday's results
python scripts/daily_scheduler.py --mode backtest

# List all pending evolution reports
python scripts/apply_evolution.py --list

# Apply suggestion #2 from a report
python scripts/apply_evolution.py --report .evolution/evolution_2026-03-31_ST.md --apply 2

# View applied history
python scripts/apply_evolution.py --history

# Rollback last applied change
python scripts/apply_evolution.py --rollback
```

### Cache Usage Guide

| Scenario | Recommended Action |
|----------|--------------------|
| First analysis of a race | Run normally — cache auto-builds |
| Repeat analysis within 1 hour | Run normally — cache hit, instant result |
| ~30 min before post time | `--force-refresh` for latest odds |
| Analyzing historical races (backtest) | Run normally — race results cached 7 days |

---

## Notes

1. **Data Timeliness** — Odds change in real-time; analysis is for reference only
2. **Past ≠ Future** — Historical performance is indicative, not predictive
3. **Risk Warning** — Horse racing betting involves financial risk; participate responsibly
4. **Data Source** — All data sourced from HKJC official website (racing.hkjc.com)

---

## Resources

### scripts/
- `analyze_race.py` — Main analysis script: data fetch, history parsing, multi-dimensional scoring, report output
- `daily_scheduler.py` — Daily automation: race day detection, batch prediction, post-race backtest, evolution report generation
- `apply_evolution.py` — Evolution applicator: safely applies user-confirmed suggestions to `analyze_race.py` (with backup/rollback)
- `dump_race.py` — Debug utility: dumps raw cached race data to stdout

### references/
- `hkjc_urls.md` — HKJC URL reference (including jockey/trainer profile pages)
- `analysis_weights.md` — Dimension weight config (with jockey/trainer dynamic scoring rubric and scenario-adaptive rules)
- `expert_sources.md` — Expert prediction reference sources

### Auto-generated Directories (appear after first run)
- `.archive/` — Prediction archives (`YYYY-MM-DD_VENUE_prediction.json`) + backtest reports (`_backtest.json`)
- `.evolution/` — Evolution suggestion reports (`evolution_YYYY-MM-DD_VENUE.md`) + applied history (`applied_history.json`)
- `.backups/` — `analyze_race.py` backups (auto-created before each `apply_evolution` run)
- `.cache/` — HTTP response cache (auto-managed, keyed by URL hash)
