# Horse Racing Expert Sources Reference

## Hong Kong Major Racing Media

### Official Channels
| Source | URL | Description |
|--------|-----|-------------|
| Hong Kong Jockey Club | racing.hkjc.com | Official data and tips |
| HKJC YouTube | youtube.com/@hkjc | Race highlights and analysis |
| **HKJC Tips Index** | racing.hkjc.com/racing/chinese/tipsindex/tips_index.asp | **Official daily tips index (6% weight)** |

#### HKJC Tips Index Description
- **Data Source**: Official HKJC website daily published tips index
- **Index Range**: Usually 80-120, 100 as baseline
  - > 100: Market favors (well-regarded)
  - < 100: Market dislikes (underestimated)
- **Weight Setting**: **6%** (higher than external expert predictions at 4%)
- **Scoring Rules**:
  - Index 100 → Score 50 (neutral)
  - Every 5 points deviation → Score ±10
  - No data → Default 50

> ⚠️ **v1.4.0 Update**: Tips index URL upgraded from standalone fetch in fetch.py to config.py constants, unified call in fetch.py. Weight adapts in newcomer/class_down scenarios (see `references/analysis_weights_en.md` scenario weights section).

### Racing Newspapers
| Source | URL | Description |
|--------|-----|-------------|
| Oriental Daily Racing | orientaldaily.on.cc | Hong Kong authoritative racing paper |
| The Sun Racing | the-sun.on.cc | Professional racing commentary |
| Apple Daily Racing | appledaily.com | News with racing tips |

### Online Platforms
| Source | URL | Description |
|--------|-----|-------------|
| Racing Commentary Sites | Various | Commentators' blogs |
| Racing Info Platforms | Various | Horse racing information platforms |
| Commentator Columns | Personal websites | Professional analysis |

## Search Keywords

### Pre-race Prediction Search
```
# General
"Sha Tin racing prediction"
"Happy Valley tonight tips"
"HKJC horse racing analysis"

# Specific race
"Sha Tin race 3 prediction"
"1400m horse racing analysis"
"Class 5 horse racing prediction"

# With date
"March 2026 Sha Tin racing"
"Ching Ming Festival Happy Valley"
```

### Commentator Search
```
"racing expert picks"
"expert horse racing analysis"
"trainer comments"
```

## Expert Prediction Evaluation Criteria

### Reliable Expert Characteristics
- Has long-term horse racing analysis experience
- Analysis is evidence-based with data support
- Objective views, not exaggerated
- High historical prediction accuracy

### Warning Signs
- Overly optimistic / only recommends favorites
- Simple recommendations without analysis reasons
- Frequently changes opinions
- Lacks professional background

## Expert Consensus Calculation

```python
def calculate_expert_consensus(horse_id, expert_recommendations):
    """
    horse_id: Horse identification number
    expert_recommendations: List of expert recommendations
    Returns: Consensus percentage (0-100)
    """
    total_experts = len(expert_recommendations)
    recommended_count = sum(1 for rec in expert_recommendations if horse_id in rec)
    
    return (recommended_count / total_experts) * 100
```

## Integrating Expert Predictions

1. **Collect**: Gather expert predictions from multiple sources
2. **Deduplicate**: Merge duplicate recommendations from same expert
3. **Statistics**: Calculate expert consensus for each horse
4. **Convert**: Convert consensus to score (0-100)
5. **Integrate**: Merge into final score with 6% weight

## Notes

- Expert predictions are for reference only, do not blindly follow
- Prioritize analysis backed by data
- Combine with your own analysis for judgment
- Odds are more reliable objective indicators
