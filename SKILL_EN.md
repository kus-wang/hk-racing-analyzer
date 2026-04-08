---
name: hk-racing-analyzer-en
description: Hong Kong Horse Racing Analysis and Prediction Tool. Provides quantitative analysis based on historical performance, odds trends, sectional timing data, and official tips index, using an HKJC API-first architecture with page-scraping fallback to deliver top-3 probability distribution and betting recommendations. Trigger keywords: analyze Sha Tin/Happy Valley race X, horse racing prediction, horse analysis, HKJC racing, today's racing analysis, compare horse X and Y, today's results. Use cases: Users want to analyze a race, predict outcomes, compare horses, view race results.

---

# Hong Kong Horse Racing Analyzer (HK Racing Analyzer)

Data-driven horse racing prediction tool combining historical data analysis with AI-assisted judgment.

## Core Features

1. **Race Data Analysis** — Use HKJC GraphQL API as the primary source and official page scraping as fallback to analyze all participating horses
2. **Prediction Analysis** — Provide top-3 probability distribution based on multi-dimensional scoring
3. **Betting Recommendations** — Offer concise win / quinella / dark-horse suggestions
4. **Daily Automation** — Auto-detect race days, batch-predict all races, post-race backtest, self-evolution suggestions


## Analysis Dimensions

### Primary Dimensions

| Dimension | Data Source | Analysis Points |
|-----------|-------------|-----------------|
| **History — Same Condition** | HKJC Horse Profile page | Last 5 races at same distance + same venue (time-decayed); not replaceable by API yet |
| **History — Same Venue** | HKJC Horse Profile page | Last 5 races at same venue (any distance, time-decayed) |
| **Class Fit** | HKJC API race card | Rating vs. class ceiling/floor |
| **Odds Value** | HKJC API + odds page fallback | 20-tier fine-grained score + place odds bonus + win/place ratio signal (v1.4.13) |
| **Odds Drift** | HKJC API + odds page fallback | Opening → final odds movement (shortening = strong signal) |
| **Sectional / Pace Index** | Results / history pages | API only exposes finalPosition; sectional pace and running positions still come from page parsing |


### Secondary Dimensions

| Dimension | Data Source | Analysis Points |
|-----------|-------------|-----------------|
| **HKJC Tips Index** | HKJC Official Tips Index Page | Official daily tips (>100 hot, <100 cold) |
| Jockey | Horse history (dynamic) | Win/top-3 rate of this jockey on this horse |
| Trainer | Horse history (dynamic) | Win/top-3 rate of this trainer with this horse |
| Barrier | Historical stats | Barrier win rate at same distance (HV: inside barrier advantage) |
| Track Preference | Horse Profile | Turf/Dirt, Good/Fast performance (in same-condition history) |

> Jockey/Trainer weights are dynamically computed by `weights.py` based on venue/distance/class. See `references/analysis_weights_en.md` for the full scoring rubric.

### External Reference (Optional)

Use `web_search` to search expert tips as supplementary reference. Search: `"Sha Tin racing race X prediction"` / `"Happy Valley tonight tips"`

> Expert predictions are reference only; prefer data-backed analysis over pure opinion.

## Workflow

### Step 1: Parse User Request

Extract from user input: race date (default: today), venue (`ST`/`HV`), race number, intent (prediction / comparison / results).

**Natural Language Date Support**: `today`/`tomorrow`/`next Monday`/`YYYY/MM/DD`/`April 5th`
**Venue Mapping**: `沙田`/`ST`/`Sha Tin` → ST; `跑马地`/`HV`/`Happy Valley`/`tonight` → HV
**Intent Recognition**: `"analyze"`/`"predict"` → prediction; `"compare"`/`"vs"`/`"X and Y"` → comparison; `"results"`/`"who won"` → results query

**Examples**:
- "Analyze Sha Tin race 3 today" → date=today, venue=ST, race=3, intent=prediction
- "Compare horse 3 and 7" → date=today, intent=comparison, horses=[3, 7]
- "Who won race 2 at Sha Tin today" → date=today, venue=ST, race=2, intent=results

### Step 2: Fetch Race Data (with Caching, API-first)

Built-in disk cache avoids redundant network requests. Location: `.cache/<url_hash>.json`

#### Data Path (v1.6.0)

1. Call `scripts/api_client.py` → `scripts/hkjc_api_client.js` → `hkjc-api` GraphQL endpoint first
2. Limit every API operation to **2 attempts max** (including the first call) with a **500ms** retry delay
3. Keep at least **500ms** between any two API requests to avoid excessive frequency
4. Fall back to the original page path (Playwright / HTTP) when API retries are exhausted
5. Cache API responses as structured JSON in `parsed` whenever possible to reduce HTML size and re-parsing cost

#### API Coverage

- ✅ Race card core fields: horse no, horse name, barrier, weight, rating, jockey, trainer, reserve marker
- ✅ Odds pools: WIN / PLA / QIN / QPL / TRI
- ✅ Race-day detection: venue + total race count
- ⚠️ Race results: keep `finalPosition` only; finish time / margins still require page fallback
- ❌ Still page-only: horse history, official tips index, running positions

| Data Type | TTL | Notes |
|-----------|-----|-------|
| Historical race results (finished) | 7 days | Immutable after race ends; API rank first, page fallback for details |
| Today's race card (pre-race) | 30 min | API JSON cached first; may still change for scratchers/jockey switches |
| Horse historical records | 24 hours | Still fetched from Horse.aspx |
| Odds data | 5 min | API odds pools first, near-real-time |
| Tips index | 30 min | Page-only, pre-race updates |


### Step 3: Data Analysis

Run `scripts/analyze_race.py`:

```bash
python scripts/analyze_race.py --date YYYY/MM/DD --venue ST/HV --race N
```

The script automatically: fetches race card / odds / race-day metadata through HKJC API first → fetches horse history in parallel → falls back to page scraping when API retries fail → calculates multi-dimensional scores → Softmax probability → top-3 prediction.


Optional: use `web_search` for expert tips (see "External Reference" above).

### Step 4: Generate Prediction Report

The script outputs a Markdown analysis report with top-3 probability, betting style, full-field dimensional scores, dark horse watch, and betting recommendations.

> Detailed report template, betting recommendation logic, horse comparison flow, and race results query are all in `references/workflow.md`.

## Quick Start

```bash
# Single race analysis (second run uses cache, instant)
python scripts/analyze_race.py --venue ST --race 3

# Analyze Happy Valley race 5 on specific date
python scripts/analyze_race.py --date 2026/03/30 --venue HV --race 5

# Force refresh odds (~30 min before post)
python scripts/analyze_race.py --venue ST --race 3 --force-refresh

# Show cache statistics
python scripts/analyze_race.py --cache-stats

# Check if tomorrow is race day + batch predict
python scripts/daily_scheduler.py --mode predict

# Backtest yesterday's results
python scripts/daily_scheduler.py --mode backtest
```

### Cache Usage Guide

| Scenario | Recommended Action |
|----------|--------------------|
| First analysis of a race | Run normally — cache auto-builds |
| Repeat analysis within 1 hour | Run normally — cache hit, instant result |
| ~30 min before post time | `--force-refresh` for latest odds |
| Analyzing historical races (backtest) | Run normally — results cached 7 days |

## Notes

1. **Data Timeliness** — Odds change in real-time; analysis is for reference only
2. **Past ≠ Future** — Historical performance is indicative, not predictive
3. **Risk Warning** — Horse racing betting involves financial risk; participate responsibly
4. **Data Source** — All data sourced from HKJC official website (racing.hkjc.com)

## Resources

### scripts/

| File | Responsibility |
|:-----|:---------------|
| `main.py` | CLI parsing, main workflow orchestration, parallel history fetching |
| `analyze.py` | Single horse multi-dimensional scoring |
| `scoring.py` | All scoring functions (history/odds/pace/jockey/tips) |
| `api_client.py` | Python-side API bridge: subprocess wrapper for the Node client, 500ms throttling/retry policy, structured cache writes |
| `hkjc_api_client.js` | Node-side HKJC GraphQL bridge: exposes `meetings`, `race`, and `odds` commands |
| `fetch.py` | API-first data fetcher: race card / odds via GraphQL first, Playwright/HTTP fallback; horse history / tips still page-based |
| `parse.py` | HTML parsing for the page-fallback path (race card, horse history, race results) |
| `cache.py` | Disk cache read/write, TTL expiry, stats cleanup (API JSON stored in `parsed`) |
| `output.py` | Markdown report formatting, auto betting-style classification |
| `config.py` | URL constants, API bridge config, cache TTL, default weights |
| `weights.py` | Scenario/venue/distance-adaptive dynamic weight calculation |
| `probability.py` | Softmax normalized probability calculation |
| `analyze_race.py` | **Entry compatibility layer** (directly calls main.py, CLI unchanged) |
| `daily_scheduler.py` | **Scheduler orchestrator** (~390 lines): batch prediction workflow + main entry |
| `scheduler_cache.py` | HTML-fallback cache management + page fetching (scheduler only) |
| `race_day.py` | Race day detection: HKJC API first, page fallback |
| `race_results.py` | Actual results fetch: API `finalPosition` first, HTML parsing fallback |

| `evolution_report.py` | Backtest accuracy calculation + evolution suggestion generation + Markdown report |
| `apply_evolution.py` | Evolution applicator (with backup/rollback) |
| `dump_race.py` | Debug utility: dumps raw cached race data |

### references/

- `hkjc_urls_en.md` — HKJC URL / GraphQL API reference

- `analysis_weights_en.md` — Dimension weight config (v1.4.11: 40% odds weight, 20-tier fine-grained scoring, Softmax T=4.0)
- `expert_sources.md` — Expert prediction reference sources
- `workflow.md` — **Detailed procedures handbook**: report template, betting logic, CLI usage, comparison/results query flows

### Auto-generated Directories

- `.archive/` — Prediction archives + backtest reports
- `.evolution/` — Evolution suggestion reports + applied history
- `.backups/` — `analyze_race.py` backups (auto-created before each `apply_evolution` run)
- `.cache/` — HTTP response cache (auto-managed)

## Daily Automation

| Task | Schedule | Action |
|------|----------|--------|
| Race Day Prediction | **Daily 14:30** | Detect tomorrow's race day → batch-predict all races |
| Backtest + Evolution | **Daily 23:30** | Fetch today's results → compare predictions → generate evolution report |

### Self-Evolution Workflow

```
[14:30 daily]  Detect race day → batch predict all races → save to .archive/
                   ↓ (same day 23:30)
[23:30 daily]  Fetch actual results → compare predictions → generate evolution report
                   ↓ (user reviews)
[Manual]       python apply_evolution.py --list
               python apply_evolution.py --report .evolution/xxx.md --apply N
                   ↓ (on apply)
[Auto-backup]  .backups/analyze_race_YYYYMMDD_HHMMSS.py
               To rollback: python apply_evolution.py --rollback
```

**Key principle**: Evolution suggestions are always reviewed by the user first. The Skill is never modified automatically.
