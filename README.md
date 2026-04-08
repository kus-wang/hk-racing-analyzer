# 🏇 HK Racing Analyzer

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Node.js](https://img.shields.io/badge/Node.js-18+-orange.svg)](https://nodejs.org)

> Data-driven horse racing prediction tool for HKJC races — delivering top-3 probability distribution and betting recommendations.
> 
> 香港赛马数据驱动预测工具，基于历史战绩、赔率走势、配速分段等多维数据，提供前3名概率预测与投注建议。

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Multi-dimensional Analysis** | 10 weighted dimensions: odds composite (22%), odds drift (18%), same-distance history (13%), same-venue history (17%), sectional pace (8%), jockey (4%), trainer (3%), barrier (4%), class fit (7%), tips index (4%) |
| **HKJC API-First Architecture** | GraphQL API priority with automatic page-scraping fallback for real-time race data |
| **Smart Betting Recommendations** | Auto-detects race type and recommends optimal bet type (WIN/PLACE/Q/TRIO) |
| **Self-Evolution Engine** | Compares predictions with actual results, generates weight optimization suggestions |
| **Intelligent Caching** | Layered TTL caching with Zlib compression, API JSON prioritized, 80-90% space reduction |
| **Reserve Horses Support** | Automatic substitution tracking when declared runners withdraw |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Playwright (for dynamic page scraping)

### Installation

```bash
# Clone the repository
git clone https://github.com/kus-wang/hk-racing-analyzer.git
cd hk-racing-analyzer

# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies
npm install

# Install Playwright browser
playwright install chromium
```

### Usage

```bash
# Analyze today's Sha Tin Race 3
python scripts/analyze_race.py --venue ST --race 3

# Analyze Happy Valley Race 5 on a specific date
python scripts/analyze_race.py --date 2026/03/30 --venue HV --race 5

# Force refresh all caches
python scripts/analyze_race.py --venue ST --race 3 --force-refresh

# View cache statistics
python scripts/analyze_race.py --cache-stats
```

---

## 📊 Sample Output

```
## 🏇 2026-03-29 Sha Tin Race 3

### Top-3 Probability Prediction

| Rank | # | Horse | Probability | Score |
|------|---|-------|-------------|-------|
| 1 | 8 | Romantic Warrior | 32% | 87 |
| 2 | 3 | Golden Bolt | 21% | 78 |
| 3 | 5 | Flying Dragon | 16% | 71 |

### Betting Recommendations
- **WIN**: #8 Romantic Warrior
- **QUINELLA**: 8, 3
- **Dark Horse**: #5 (odds 18, form improving)
```

---

## 🏗️ Architecture

### Dual-Channel Data Strategy

```
┌─────────────────┐     ┌─────────────────┐
│   HKJC API      │────▶│  GraphQL Bridge │
│  (Primary)      │     │  (api_client)   │
└─────────────────┘     └────────┬────────┘
                                 │
                    ┌────────────┴────────────┐
                    │    Structured Cache     │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │     Analysis Engine     │
                    └────────────┬────────────┘
                                 │
┌─────────────────┐     ┌────────┴────────┐
│  Page Scraping  │────▶│  HTML Parser    │
│   (Fallback)    │     │  (Playwright)   │
└─────────────────┘     └─────────────────┘
```

### Project Structure

```
hk-racing-analyzer/
├── scripts/
│   ├── main.py                 # CLI entry point
│   ├── analyze_race.py         # Main analysis script
│   ├── api_client.py           # Python API bridge
│   ├── hkjc_api_client.js      # Node.js GraphQL bridge
│   ├── fetch.py                # Data fetching (API-first)
│   ├── parse.py                # HTML parsing
│   ├── analyze.py              # Scoring logic
│   ├── scoring.py              # Dimension scoring functions
│   ├── probability.py          # Softmax normalization
│   ├── betting.py              # Betting recommendations
│   ├── output.py               # Report formatting
│   ├── cache.py                # Disk caching
│   ├── config.py               # Configuration
│   ├── weights.py              # Dynamic weight calculation
│   ├── daily_scheduler.py      # Automation scheduler
│   ├── race_day.py             # Race day detection
│   ├── race_results.py         # Results fetching
│   └── evolution_report.py     # Backtesting & evolution
├── references/                 # Documentation & references
├── .archive/                   # Prediction archives
├── .evolution/                 # Evolution reports
└── .cache/                     # Data cache
```

---

## ⚙️ Automation

| Task | Schedule | Function |
|------|----------|----------|
| Race Day Prediction | Daily 14:30 | Detect race day → batch predict → archive |
| Backtest & Evolution | Daily 23:30 | Fetch results → compare predictions → generate evolution suggestions |

### Evolution Workflow

```
[14:30] Detect race day → Batch predict → .archive/
              ↓
[23:30] Fetch actual results → Compare → .evolution/ (suggestions)
              ↓
[Manual] Review and apply: python scripts/apply_evolution.py --apply N
```

---

## 📖 Documentation

- [SKILL.md](SKILL.md) — 中文 Skill 文档 / Chinese documentation
- [SKILL_EN.md](SKILL_EN.md) — English documentation
- [RELEASE_NOTES.md](RELEASE_NOTES.md) — Full changelog
- [references/](references/) — HKJC URLs, weight configs, workflow docs

---

## 🛠️ Configuration

Edit `scripts/config.py` to customize:

- Weight distribution across dimensions
- Cache TTL by data type
- Output format (JSON / markdown)
- Automation schedule

---

## 📝 Changelog

| Version | Date | Highlights |
|---------|------|------------|
| [v1.6.0](RELEASE_NOTES.md#v160--2026-04-08) | 2026-04-08 | HKJC API-first architecture with automatic page fallback |
| [v1.5.2](RELEASE_NOTES.md#v152--2026-04-07) | 2026-04-07 | Refactored scheduler into 5 modules, 64% code reduction |
| [v1.5.0](RELEASE_NOTES.md#v150--2026-04-07) | 2026-04-07 | Smart betting recommendation module |
| [v1.4.0](RELEASE_NOTES.md#v140--2026-03-31) | 2026-03-31 | Modular refactor, daily automation, self-evolution engine |

See [RELEASE_NOTES.md](RELEASE_NOTES.md) for complete history.

---

## ⚠️ Disclaimer

- This tool is for **entertainment and educational purposes only**, not betting advice
- Racing results depend on many uncertain factors; **past performance does not guarantee future outcomes**
- Please **bet responsibly and within your means**
- All data sourced from the [Hong Kong Jockey Club](https://racing.hkjc.com) official website

---

## 📜 License

[MIT](LICENSE) © kus-wang

---

<p align="center">
  Built with ❤️ for HKJC racing enthusiasts
</p>
