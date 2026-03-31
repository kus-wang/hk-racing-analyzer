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

## Data Scraping Notes

1. Need to set correct User-Agent and Accept-Language headers
2. Pages may use JavaScript dynamic loading, some data requires waiting
3. Odds data changes in real-time, recommend scraping before race time
4. Respect website's robots.txt and access frequency limits
