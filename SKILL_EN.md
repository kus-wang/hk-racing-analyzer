---
name: hk-racing-analyzer-en
description: Hong Kong Horse Racing Analysis and Prediction Tool. Provides quantitative analysis based on historical performance, odds trends, sectional timing data, and official tips index, delivering top-3 probability distribution and betting recommendations. Trigger keywords: analyze Sha Tin/Happy Valley race X, horse racing prediction, horse analysis, HKJC racing, today's racing analysis, compare horse X and Y, today's results. Use cases: Users want to analyze a race, predict outcomes, compare horses, view race results.
---

# Hong Kong Horse Racing Analyzer (HK Racing Analyzer)

Data-driven horse racing prediction tool combining historical data analysis with AI-assisted judgment.

## Core Features

1. **Race Data Analysis** — Scrape HKJC race data and analyze all participating horses
2. **Prediction Analysis** — Provide top-3 probability distribution based on multi-dimensional scoring
3. **Betting Recommendations** — Offer concise win / quinella / dark-horse suggestions
4. **Daily Automation** — Auto-detect race days, batch-predict all races, post-race backtest, self-evolution suggestions

## Analysis Dimensions

### Primary Dimensions

| Dimension | Data Source | Analysis Points |
|-----------|-------------|-----------------|
| **History — Same Condition** | HKJC Horse Profile | Last 5 races at same distance + same venue (time-decayed) |
| **History — Same Venue** | HKJC Horse Profile | Last 5 races at same venue (any distance, time-decayed) |
| **Class Fit** | Race Entry | Rating vs. class ceiling/floor |
| **Odds Value** | HKJC Odds Page | Absolute final odds |
| **Odds Drift** | HKJC Odds Page | Opening → final odds movement (shortening = strong signal) |
| **Sectional / Pace Index** | HKJC Results | Running style derived from historical position calls |

### Secondary Dimensions

| Dimension | Data Source | Analysis Points |
|-----------|-------------|-----------------|
| **HKJC Tips Index** | HKJC Official Tips Index Page | Official daily tips (>100 hot, <100 cold) |
| Jockey | Horse history (dynamic) | Win/top-3 rate of this jockey on this horse |
| Trainer | Horse history (dynamic) | Win/top-3 rate of this trainer with this horse |
| Barrier | Historical stats | Barrier win rate at same distance (ST/HV) |
| Track Preference | Horse Profile | Turf/Dirt, Good/Fast performance (included in same-condition history) |
| Weight/Body Weight | Race Data | Weight carried changes, body weight trends (planned) |

> Jockey/Trainer weights are dynamically computed by `weights.py` based on venue/distance/class — no fixed values needed. See `references/analysis_weights.md` for the scoring rubric.

### External Reference (Optional)

Use `web_search` to search expert tips as supplementary reference.

Search: `"Sha Tin racing race X prediction"` / `"Happy Valley tonight tips"`

> Expert predictions are reference only; prefer data-backed analysis over pure opinion.

---

## Workflow

### Step 1: Parse User Request

Extract from user input:
- Race date (default: today)
- Venue (Sha Tin `ST` / Happy Valley `HV`)
- Race number
- Intent (prediction / comparison / results query)

**Natural Language Date Support**:

| User Input | Parsed As |
|------------|-----------|
| "today" | Current date |
| "tomorrow" | Current date + 1 day |
| "tomorrow afternoon/evening" | Current date + 1 day |
| "next Monday" etc. | Specified weekday this week |
| "2026/04/05" | Exact date |
| "April 5th" | Specified month/day, current year |

**Venue Chinese → Code Mapping**:

| User Input | Parsed As |
|------------|-----------|
| 沙田 / ST / Sha Tin | ST |
| 跑马地 / HV / Happy Valley / tonight | HV |

**Intent Recognition**:

| Keywords | Recognized As |
|----------|---------------|
| "analyze", "predict", "recommend" | Race prediction |
| "compare", "vs", "which is better", "X and Y" | Horse comparison |
| "results", "who won", "finished" | Race results query |

**Full Parsing Examples**:
- "Analyze Sha Tin race 3 today" → date=today, venue=ST, race=3, intent=prediction
- "Analyze Happy Valley race 5 tonight" → date=today, venue=HV, race=5, intent=prediction
- "Compare horse 3 and 7" → date=today, intent=comparison, horses=[3, 7]
- "Who won race 2 at Sha Tin today" → date=today, venue=ST, race=2, intent=results

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
| Tips index | 30 min | Updated before each race |
| Generic fallback | 1 hour | — |

### Step 3: Data Analysis

Run `scripts/analyze_race.py`:

```bash
python scripts/analyze_race.py --date YYYY/MM/DD --venue ST/HV --race N
```

The script automatically:
1. Fetches race card and horse list
2. Parallel-fetches each horse's historical performance (~8 threads)
3. Gets odds data
4. Calculates multi-dimensional scores → Softmax probability → top-3 prediction

Optional: use `web_search` for expert tips (see "External Reference" above).

### Step 4: Generate Prediction Report

Output format:

```markdown
## 🏇 [Date] [Venue] Race X Analysis Report

### Race Information
- Race Name / Distance / Class / Track Condition / Prize Money

### 📊 Top-3 Probability Prediction

| Rank | No. | Horse Name | Win Prob. | Key Reason |
|:----:|:---:|------------|-----------|------------|
| 🥇   | X   | XXX        | XX%       | ...        |
| 🥈   | X   | XXX        | XX%       | ...        |
| 🥉   | X   | XXX        | XX%       | ...        |

### 🎯 Betting Style Profile

Auto-generated by `classify_betting_style()` in `output.py`:

| Style | Meaning | Recommended Strategy |
|-------|---------|---------------------|
| **🛡️ Conservative** | Top1 or top-2 clearly dominant | Win/Place preferred, control cost |
| **⚡ Aggressive** | Open field, no clear favorite | Dark horse hunting, PQ/Trio |
| **🔀 Undecided** | Multiple horses with similar strength | PQ all three pairs, spread risk |

### 📋 Full Field Scoring
(Each dimension scored 0-100, for reference)

| No. | Horse | Score | Hist.Cond | Hist.Venue | Class | Odds | Drift | Pace | Tips | Jockey | Trainer | Barrier | Expert |
|:---:|:------|:-----:|:---------:|:----------:|:-----:|:----:|:-----:|:----:|:----:|:------:|:-------:|:------:|:------:|
| X   | XXX   | XX    | XX        | XX         | XX    | XX   | XX    | XX   | XX   | XX     | XX      | XX     | XX     |

### 🔍 Dark Horse Watch
(Horses that are NOT favorites but meet the following criteria)
- ✅ Top-3 record in same condition (distance + venue)
- ✅ Odds not drifting (market not overly pessimistic)
- ✅ High class fit (rating close to class ceiling)
- ✅ Barrier preference matches

### 💡 Betting Recommendations
(See betting recommendation logic below)

### ⚠️ Risk Warning
- Data is for reference only, not investment advice
- Race results are subject to many uncontrollable factors
- Please participate responsibly
```

#### Betting Recommendation Logic (AI autonomous judgment)

**1. Win**
- Condition: Top1 probability clearly dominant (35%+), **or** odds <= 4x
- Reason: Favorite has significantly higher win probability
- Risk: Low odds on favorites mean limited returns

**2. Place**
- Condition: Any of Top3 has probability >= 20%
- Reason: Lower threshold than Win; any top-3 finish wins
- Best for: Clear favorite but uncertain about exact finishing position

**3. Quinella**
- Condition: Top1 + Top2 probability sum >= 55%, both horses competitive
- Reason: Both top horses have high confidence and comparable strength
- Recommended combo: Horse #1 + Horse #2

**4. Place Quinella (PQ)**
- Condition: Top3 probabilities are scattered, hard to rank
- Reason: Hard to rank top 3 confidently; PQ cheaper than Trio
- Recommended combos: 1+2 / 1+3 / 2+3 (all three pairs)

**5. Trio**
- Condition: All Top3 have probability >= 10% each, sum >= 45%
- Reason: High confidence across top 3, broad coverage
- Recommended combo: #1 + #2 + #3

> AI should judge flexibly based on actual probability distribution. The script only outputs probability data; betting judgment is performed autonomously by AI.

#### Betting Output Format

```markdown
### 💡 Betting Recommendations

**🏆 Best Pick**: [bet type] — [horse combo]
> Reason: [brief explanation]

**Other Options**:
- **Win**: No.X [horse name] (prob XX%) — [reason]
- **Place**: No.X (prob XX%) — [reason]
- **Quinella**: No.X + No.X (sum XX%) — [reason]
- **Place Quinella (PQ)**: No.X+No.X / No.X+No.X / No.X+No.X — [reason]
- **Trio**: No.X + No.X + No.X — [reason]
```

---

### Supplementary: Horse Comparison Feature

When the user requests a comparison between two (or more) horses:

**Step 1**: Identify comparison request, extract horse number(s)

Recognize phrases like "compare 3 and 7", "which is better, X or Y", "any value in horse 3 vs 7".

**Step 2**: Fetch both horses' scoring data for this race

Run `analyze_race.py` to get full-field scores, extract the relevant horses' dimensional sub-scores.

**Step 3**: Dimension-by-dimension comparison

| Dimension | What to Compare |
|-----------|----------------|
| Overall Score | Total score ranking |
| Historical Performance | Same-condition / same-venue win rate |
| Odds Trend | Market signal (shortening vs drifting) |
| Pace Match | Running style vs. track condition fit |
| Jockey / Trainer | Combined strength |

**Step 4**: Output comparison report

```markdown
## [Venue] Race X — Horse Comparison: #X vs #X

### One-Line Verdict
[Quick judgment based on score gap]

### Dimension Comparison
| Dimension | #X [Horse Name] | #X [Horse Name] | Advantage |
|:---------|:--------------:|:--------------:|:---------:|
| Overall Score | XX | XX | #X |
| Same-Condition History | XX | XX | #X |
| Odds Trend | XX | XX | #X |
| ... | ... | ... | ... |

### Detailed Analysis by Dimension
[Brief explanation of gap causes per dimension]

### Overall Recommendation
[Bet direction advice combining probability data]
```

---

### Supplementary: Today's Race Results Query

When the user queries results of a race that has already finished:

**Data Source**: Call `fetch_race_results()` to fetch HKJC results page, then `parse_race_results()` to parse structured data.

```python
from fetch import fetch_race_results
from parse import parse_race_results

html = fetch_race_results("2026/04/01", "ST")
races = parse_race_results(html)
# races = [{"race_no": 1, "results": [{"pos": 1, "no": "12", "name": "爆熱", ...}]}, ...]
```

**Logic**:
- Results available after ~23:00 on race day
- Extract: race number, position, horse no. + name, finish time, win odds

**Results Output Format**:

```markdown
## [Date] [Venue] Race Results

| Race | 1st | 2nd | 3rd | Time |
|:----:|:---:|:---:|:---:|:----:|
| 1 | No.X [Horse] | No.X [Horse] | No.X [Horse] | HH:MM |
| 2 | ... | ... | ... | ... |
```

If the race has not yet concluded, inform the user of the estimated results publication time.

---

## Daily Automation System

| Task | Schedule | Action |
|------|----------|--------|
| Race Day Prediction | **Daily 14:30** | Detect tomorrow's race day → batch-predict all races → notify summary |
| Backtest + Evolution | **Daily 23:30** | Fetch today's results → compare predictions → send full evolution report |

### Self-Evolution Workflow

```
[14:30 daily]  Detect race day → batch predict all races → save to .archive/
                   ↓ (same day 23:30)
[23:30 daily]  Fetch actual results → compare predictions
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

# Scenario mode: newcomer / class_down / class_up / normal
python scripts/analyze_race.py --venue ST --race 3 --scenario newcomer

# Force refresh — bypass cache (~30 min before post)
python scripts/analyze_race.py --venue ST --race 3 --force-refresh

# Clear cache for this race then re-analyze
python scripts/analyze_race.py --venue ST --race 3 --clear-cache

# Show cache statistics
python scripts/analyze_race.py --cache-stats

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

| File | Responsibility |
|:-----|:---------------|
| `main.py` | CLI parsing, main workflow orchestration, parallel history fetching |
| `analyze.py` | Single horse multi-dimensional scoring |
| `scoring.py` | All scoring functions (history/odds/pace/jockey/tips) |
| `fetch.py` | HTTP requests, Playwright dynamic loading, horse history / tips / race results |
| `parse.py` | Race card, horse history & race results HTML parsing |
| `cache.py` | Disk cache read/write, TTL expiry, stats cleanup |
| `output.py` | Markdown report formatting, auto betting-style classification |
| `config.py` | URL constants, cache TTL, default weights |
| `weights.py` | Scenario/venue/distance-adaptive dynamic weight calculation |
| `probability.py` | Softmax normalized probability calculation |
| `analyze_race.py` | **Entry compatibility layer** (directly calls main.py, CLI usage unchanged) |

#### Automation Scripts

- `daily_scheduler.py` - Daily automation: race day detection, batch prediction, post-race backtest, evolution report generation
- `apply_evolution.py` - Evolution applicator: safely applies user-confirmed suggestions to code (with backup/rollback)
- `dump_race.py` - Debug utility: dumps raw cached race data to stdout

### references/
- `hkjc_urls.md` — HKJC URL reference (including jockey/trainer profile pages)
- `analysis_weights.md` — Dimension weight config (with jockey/trainer dynamic scoring rubric and scenario-adaptive rules)
- `expert_sources.md` — Expert prediction reference sources

### Auto-generated Directories (appear after first run)
- `.archive/` — Prediction archives + backtest reports
- `.evolution/` — Evolution suggestion reports + applied history
- `.backups/` — `analyze_race.py` backups (auto-created before each `apply_evolution` run)
- `.cache/` — HTTP response cache (auto-managed, keyed by URL hash)
