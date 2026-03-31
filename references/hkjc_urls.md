# HKJC 网站 URL 参考

## 主要页面

### 赛事信息
- 赛果页面: `https://racing.hkjc.com/racing/information/Chinese/Racing/LocalResults.aspx`
- 日程页面: `https://racing.hkjc.com/racing/information/Chinese/Racing/Fixture.aspx`
- 出马表: `https://racing.hkjc.com/racing/information/Chinese/Racing/LocalRaceEntry.aspx`

### 马匹信息
- 马匹档案: `https://racing.hkjc.com/racing/information/Chinese/Horse/Horse.aspx?HorseId={horse_id}`
- 马匹搜索: `https://racing.hkjc.com/racing/information/Chinese/Horse/SearchHorse.aspx`

### 赔率信息
- 赔率页面: `https://racing.hkjc.com/racing/information/Chinese/Racing/Odds.aspx`
- 即时赔率: `https://racing.hkjc.com/racing/information/Chinese/Racing/RealTimeOdds.aspx`

### 骑师/练马师
- 骑师档案: `https://racing.hkjc.com/racing/information/Chinese/Jockey/JockeyRecord.aspx?jockeyid={jockey_id}`
- 练马师档案: `https://racing.hkjc.com/racing/information/Chinese/Trainer/TrainerRecord.aspx?trainerid={trainer_id}`

## URL 参数

### 赛果页面参数
| 参数 | 说明 | 示例值 |
|------|------|--------|
| racedate | 赛事日期 | 2026/03/29 |
| Racecourse | 场地代码 | ST(沙田), HV(跑马地) |
| RaceNo | 场次号 | 1, 2, 3... |

### 马匹ID格式
- 格式: `HK_{年份}_{编号}`
- 示例: `HK_2024_K341`

## 场地代码

| 代码 | 场地 |
|------|------|
| ST | 沙田 Sha Tin |
| HV | 跑马地 Happy Valley |

## 数据抓取注意事项

1. 需要设置正确的 User-Agent 和 Accept-Language
2. 页面可能使用 JavaScript 动态加载，部分数据需要等待
3. 赔率数据实时变化，建议在临场前抓取
4. 尊重网站的 robots.txt 和访问频率限制
