# HKJC Website URL Reference

## Main Pages

### Race Information
- Race Results: `https://racing.hkjc.com/racing/information/Chinese/Racing/LocalResults.aspx`
- Fixture: `https://racing.hkjc.com/racing/information/Chinese/Racing/Fixture.aspx`
- Race Card: `https://racing.hkjc.com/racing/information/Chinese/Racing/RaceCard.aspx`

### Horse Information
- Horse Profile: `https://racing.hkjc.com/racing/information/Chinese/Horse/Horse.aspx?HorseId={horse_id}`
- Horse Search: `https://racing.hkjc.com/racing/information/Chinese/Horse/SearchHorse.aspx`

### Odds Information
- Odds Page: `https://racing.hkjc.com/racing/information/Chinese/Racing/Odds.aspx`
- Real-time Odds: `https://racing.hkjc.com/racing/information/Chinese/Racing/RealTimeOdds.aspx`

### Jockey/Trainer
- Jockey Profile: `https://racing.hkjc.com/racing/information/Chinese/Jockey/JockeyRecord.aspx?jockeyid={jockey_id}`
- Trainer Profile: `https://racing.hkjc.com/racing/information/Chinese/Trainer/TrainerRecord.aspx?trainerid={trainer_id}`

## URL Parameters

### Race Results Page Parameters
| Parameter | Description | Example Value |
|-----------|-------------|---------------|
| racedate | Race date | 2026/03/29 |
| Racecourse | Venue code | ST (Sha Tin), HV (Happy Valley) |
| RaceNo | Race number | 1, 2, 3... |

### Horse ID Format
- Format: `HK_{Year}_{Number}`
- Example: `HK_2024_K341`

## Venue Codes

| Code | Venue |
|------|-------|
| ST | Sha Tin |
| HV | Happy Valley |

## HKJC GraphQL API (v1.6.0)

### GraphQL Endpoint
- Base URL: `https://info.cld.hkjc.com/graphql/base/`
- Wrapped by the `hkjc-api` npm package and called through `scripts/hkjc_api_client.js`

### Bridge Command Examples

```bash
# Detect meetings for a date + venue
node scripts/hkjc_api_client.js meetings --date 2026-04-08 --venue HV

# Fetch one race card
node scripts/hkjc_api_client.js race --date 2026-04-08 --venue HV --race 3

# Fetch odds pools (WIN/PLA/QIN/QPL/TRI)
node scripts/hkjc_api_client.js odds --date 2026-04-08 --venue HV --race 3 --types WIN,PLA,QIN,QPL,TRI
```

### API Coverage

- ✅ Covered: race-day detection, core race-card fields, WIN/PLA/QIN/QPL/TRI odds pools, race result rank via `finalPosition`
- ⚠️ Partial: results keep rank only; finish time / margins still require page fallback
- ❌ Not covered: horse history, official tips index, running positions

## Data Scraping Notes

1. Prefer the API path first, but throttle requests: minimum 500ms interval, maximum 2 attempts per call
2. For page fallback, set correct User-Agent and Accept-Language headers
3. Pages may use JavaScript dynamic loading, some data requires waiting
4. Odds data changes in real-time, so fetch close to race time when needed
5. Respect the website's robots.txt and access frequency limits
