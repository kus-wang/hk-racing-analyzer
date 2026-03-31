---
name: hk-racing-analyzer-en
description: Hong Kong Horse Racing Analysis and Prediction Tool. Provides quantitative analysis based on historical performance, odds trends, and sectional timing data, delivering top-3 probability distribution and betting recommendations. Trigger keywords: analyze Sha Tin/Happy Valley race X, horse racing prediction, horse analysis, HKJC racing, today's racing analysis. Use cases: Users want to analyze a specific horse race, predict race outcomes, or view horse historical performance.
---

# Hong Kong Horse Racing Analyzer (HK Racing Analyzer)

Data-driven horse racing prediction tool combining historical data analysis with AI-assisted judgment.

## Core Features

1. **Race Data Analysis** - Scrape HKJC race data and analyze participating horses
2. **Prediction Analysis** - Provide top-3 probability distribution based on multi-dimensional data
3. **Betting Recommendations** - Offer concise betting advice

## Analysis Dimensions

### Primary Analysis Dimensions (Higher Weight)

| Dimension | Data Source | Analysis Points |
|-----------|-------------|-----------------|
| **Horse Historical Performance** | HKJC Horse Profile | Last 5/10 races, same track performance, same distance performance |
| **Odds Trends** | HKJC Odds Page | Opening odds vs. final odds, odds movement trends |
| **Sectional Timing/Pace** | HKJC Race Results | Early speed, late sprint, sectional times |

### Secondary Analysis Dimensions (Lower Weight)

| Dimension | Data Source | Analysis Points |
|-----------|-------------|-----------------|
| Jockey Win Rate | HKJC Jockey Profile | Season win rate, this jockey's record with this horse |
| Trainer Win Rate | HKJC Trainer Profile | Season win rate, stable overall performance |
| Barrier Analysis | Historical Stats | Win rate by barrier at same distance |
| Track Preference | Horse Profile | Turf/Dirt, Good/Fast track performance |
| Weight/Body Weight | Race Data | Weight changes, body weight trends |

### External Reference Dimension (Supplementary)

| Dimension | Data Source | Analysis Points |
|-----------|-------------|-----------------|
| **Expert Predictions** | Web Search | Professional racing commentators and experts' opinions |

#### How to Obtain Expert Predictions

Use `web_search` tool to search for expert predictions:

```
Search Keywords:
- "Sha Tin racing race X prediction"
- "Happy Valley tonight racing tips"
- "HKJC horse racing analysis"
- "racing expert picks"
```

Reference Expert Sources:
- Hong Kong Jockey Club official tips
- Oriental Daily Racing, The Sun Racing and other professional media
- Well-known racing commentators' blogs/columns

Expert Prediction Integration Method:
1. Search for predictions from multiple experts
2. Extract hot picks recommended by each expert
3. Calculate expert consensus (how many experts recommend the same horse)
4. Use as supplementary reference with 5-10% weight

Notes:
- Expert predictions are for reference only, do not blindly follow
- Focus on expert analysis backed by data
- Be wary of overly optimistic/pessimistic extreme views

## Workflow

### Step 1: Parse User Request

Extract from user input:
- Race date (default: today)
- Venue (Sha Tin/Happy Valley)
- Race number

Examples:
- "Analyze Sha Tin race 3 today" → Date=today, Venue=Sha Tin, Race=3
- "Analyze Happy Valley race 5 tonight" → Date=today, Venue=Happy Valley, Race=5

### Step 2: Obtain Race Data (with Caching)

The script has built-in disk caching to **avoid redundant fetches for the same race**, saving network requests and wait time.

Cache storage location:
```
<skill_dir>/.cache/<url_hash>.json
```

Cache TTL by data type:

| Data Type | TTL | Notes |
|-----------|-----|-------|
| Historical race results (finished) | 7 days | Results never change |
| Today's race card (pre-race) | 30 min | May change due to scratcher/jockey switch |
| Horse historical records | 24 hours | Updated after each race |
| Odds data | 5 min | Real-time changes near post time |
| Other generic pages | 1 hour | Fallback TTL |

Use `web_fetch` tool to access HKJC pages (the script handles caching automatically):

```
Race Information Page:
https://racing.hkjc.com/racing/information/Chinese/Racing/LocalResults.aspx

Horse Profile Page:
https://racing.hkjc.com/racing/information/Chinese/Horse/Horse.aspx?HorseId=HK_XXXX_XXXX

Odds Page:
https://racing.hkjc.com/racing/information/Chinese/Racing/Odds.aspx
```

#### A. Local Data Analysis
Run `scripts/analyze_race.py` script for analysis:

```bash
# First-time analysis (builds cache automatically)
python scripts/analyze_race.py --date YYYY/MM/DD --venue ST/HV --race N

# Force refresh all data (use near post time for latest odds)
python scripts/analyze_race.py --venue ST --race 3 --force-refresh

# Clear cache for this race then re-analyze
python scripts/analyze_race.py --venue ST --race 3 --clear-cache

# Show cache statistics only
python scripts/analyze_race.py --cache-stats
```

The script will:
1. Check disk cache first; fetch from network only on cache miss or expiry
2. Scrape participating horse information
3. Obtain each horse's historical performance
4. Get odds data
5. Calculate comprehensive scores

#### B. Expert Prediction Acquisition (Optional)
Use `web_search` to search for expert predictions:

```bash
# Search examples
web_search "Sha Tin racing race 3 prediction March 2026"
web_search "Happy Valley tonight racing tips recommendations"
```

Extract information:
- Hot picks recommended by experts
- Key reasons in expert analysis
- Expert consensus statistics

#### C. Comprehensive Prediction
Integrate local data analysis with expert predictions:

```
Final Score = Local Analysis Score × 94% + Expert Consensus Score × 6%
```

Expert Consensus Score Calculation:
- Count number of experts recommending this horse
- Divide by total number of experts = Consensus percentage
- Convert to 0-100 score

Use `web_fetch` tool to access HKJC pages:

```
Race Information Page:
https://racing.hkjc.com/racing/information/Chinese/Racing/LocalResults.aspx

Horse Profile Page:
https://racing.hkjc.com/racing/information/Chinese/Horse/Horse.aspx?HorseId=HK_XXXX_XXXX

Odds Page:
https://racing.hkjc.com/racing/information/Chinese/Racing/Odds.aspx
```

### Step 3: Data Analysis

Run `scripts/analyze_race.py` script for analysis:

```bash
python scripts/analyze_race.py --date YYYY/MM/DD --venue ST/HV --race N
```

The script will:
1. Scrape participating horse information
2. Obtain each horse's historical performance
3. Get odds data
4. Calculate comprehensive scores

### Step 4: Generate Prediction Report

Output Format:

```markdown
## 🏇 [Date] [Venue] Race X Analysis Report

### Race Basic Information
- Race Name
- Distance/Class/Track Condition
- Prize Money

### 📊 Top-3 Probability Prediction

| Rank | Horse No. | Horse Name | Win Probability | Analysis Reason |
|------|-----------|------------|-----------------|-----------------|
| 1 | X | XXX | XX% | ... |
| 2 | X | XXX | XX% | ... |
| 3 | X | XXX | XX% | ... |

### 🎯 Expert Prediction Reference

| Horse | Expert Consensus | Representative Views |
|-------|------------------|----------------------|
| XXX | X/X (XX%) | ... |
| XXX | X/X (XX%) | ... |

### 💡 Betting Recommendations

**Win Recommended**: No.X XXX
- Reason: ...

**Quinella Recommended**: X, X
- Reason: ...

**Dark Horse Watch**: No.X
- Reason: ...

### ⚠️ Risk Warning
- ...
```

## Quick Start

When user requests analysis:

```bash
# Analyze Sha Tin race 3 today
python scripts/analyze_race.py --venue ST --race 3

# Analyze specific date Happy Valley race 5
python scripts/analyze_race.py --date 2026/03/30 --venue HV --race 5
```

## Notes

1. **Data Timeliness** - Odds data changes in real-time, analysis results are for reference only
2. **History Doesn't Guarantee Future** - Past performance is for reference only, does not guarantee future results
3. **Risk Warning** - Horse racing betting involves risks, please participate rationally
4. **Data Source** - All data comes from Hong Kong Jockey Club official website (HKJC)

## Resources

### scripts/
- `analyze_race.py` - Main analysis script, scrapes data and generates predictions
- `fetch_horse_history.py` - Obtain horse historical performance
- `fetch_odds.py` - Obtain odds data

### references/
- `hkjc_urls.md` - HKJC website URL reference
- `analysis_weights.md` - Dimension weight configuration
- `expert_sources.md` - Expert sources and evaluation criteria
