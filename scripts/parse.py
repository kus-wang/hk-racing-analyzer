#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HKJC 赛马分析工具 - HTML 解析模块

提供排位表解析和马匹历史战绩解析功能。
"""

import re
from config import VENUE_MAP, CONDITION_MAP


# ==============================================================================
# 工具函数
# ==============================================================================

def _clean_text(html_fragment: str) -> str:
    """去除 HTML 标签，返回纯文本（合并空白）。"""
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html_fragment)).strip()


def g(items: list, idx: int, default="") -> str:
    """安全获取列表元素，带默认值。"""
    return items[idx] if idx < len(items) else default


# ==============================================================================
# 马匹历史战绩解析
# ==============================================================================

def parse_horse_history(html: str) -> dict:
    """
    解析 HKJC Horse.aspx 页面，返回马匹历史战绩及基本信息。

    返回结构：
    {
        "current_rating": int,          # 最後評分
        "history": [
            {
                "date":      "2023/04/30",
                "venue":     "ST",       # ST / HV
                "distance":  1200,       # 米
                "condition": "good",     # fast/good_to_firm/good/yielding/soft
                "race_class": "4",       # 班次
                "barrier":   8,          # 档位
                "rating":    52,         # 当场评分
                "position":  14,         # 名次（DNF/DQ 等 → 99）
                "odds":      182.0,      # 独赢赔率
                "running_positions": [13, 13, 14],  # 沿途走位
                "finish_time": "1:11.42",
                "jockey":    "骑师名",
                "trainer":   "练马师名",
            },
            ...
        ]
    }
    """
    result = {"current_rating": 40, "history": []}

    # ── 最後評分 ────────────────────────────────────────────────
    # 两种页面结构：旧格式用 "最後評分" / 新格式用 class 内嵌
    rating_m = re.search(
        r'最後評分[^<]*</td>\s*<td[^>]*>\s*(\d+)',
        html
    )
    if not rating_m:
        # 尝试兜底：找 "最後評分" 附近的第一个数字
        idx_r = html.find('最後評分')
        if idx_r > 0:
            num_m = re.search(r'>\s*(\d+)\s*<', html[idx_r:idx_r + 300])
            if num_m:
                result["current_rating"] = int(num_m.group(1))
    else:
        result["current_rating"] = int(rating_m.group(1))

    # ── 往绩表：找 class=bigborder 的 table ──────────────────────
    # 表头关键字：'場次'
    table_start = html.find('class=bigborder')
    if table_start == -1:
        table_start = html.find('class="bigborder"')
    if table_start == -1:
        return result

    # 找到该 table 的结束
    table_open = html.rfind('<table', 0, table_start + 20)
    table_end = html.find('</table>', table_open)
    if table_end == -1:
        return result
    table_html = html[table_open: table_end + len('</table>')]

    # ── 逐 <tr> 解析 ────────────────────────────────────────────
    tr_pattern = re.compile(r'<tr\b[^>]*>(.*?)</tr>', re.DOTALL | re.IGNORECASE)
    td_pattern = re.compile(r'<td\b[^>]*>(.*?)</td>', re.DOTALL | re.IGNORECASE)

    for tr_m in tr_pattern.finditer(table_html):
        tr_html = tr_m.group(1)
        tds_raw = [m.group(1) for m in td_pattern.finditer(tr_html)]
        if len(tds_raw) < 12:
            continue  # 跳过表头行 / 马季分隔行

        tds = [_clean_text(td) for td in tds_raw]

        # 列顺序：[0]场次 [1]名次 [2]日期 [3]马场 [4]途程 [5]场地状况
        #         [6]班次 [7]档位 [8]评分 [9]练马师 [10]骑师
        #         [11]头马距离 [12]赔率 [13]负磅 [14]走位 [15]时间 [16]体重

        # 日期：支持 DD/MM/YYYY 和 DD/MM/YY 两种格式
        raw_date = g(tds, 2)
        date_m = re.match(r'(\d{1,2})/(\d{2})/(\d{2,4})', raw_date)
        if not date_m:
            continue
        day, month, year = date_m.group(1), date_m.group(2), date_m.group(3)
        if len(year) == 2:
            year = ("20" + year) if int(year) <= 50 else ("19" + year)
        race_date = f"{year}/{month}/{day.zfill(2)}"

        # 场地
        venue_raw = g(tds, 3).lower()
        venue = "ST"
        for k, v in VENUE_MAP.items():
            if k.lower() in venue_raw:
                venue = v
                break

        # 途程
        try:
            distance = int(re.sub(r'[^\d]', '', g(tds, 4)))
        except (ValueError, IndexError):
            distance = 0

        # 场地状况
        cond_raw = g(tds, 5)
        condition = CONDITION_MAP.get(cond_raw, "good")

        # 班次
        race_class = g(tds, 6)

        # 档位
        try:
            barrier = int(re.sub(r'[^\d]', '', g(tds, 7)).strip() or "0")
        except ValueError:
            barrier = 0

        # 评分
        try:
            rating = int(re.sub(r'[^\d]', '', g(tds, 8)).strip() or "0")
        except ValueError:
            rating = 0

        # 名次
        pos_raw = g(tds, 1)
        try:
            position = int(re.sub(r'[^\d]', '', pos_raw).strip() or "99")
        except ValueError:
            position = 99  # DNF / DQ

        # 赔率
        try:
            odds = float(re.sub(r'[^\d.]', '', g(tds, 12)).strip() or "0") or None
        except ValueError:
            odds = None

        # 走位（如 "13 13 14" 或 "8 9 7 1"）
        run_pos_raw = g(tds, 14)
        run_positions = []
        if run_pos_raw:
            parts = re.findall(r'\d+', run_pos_raw)
            run_positions = [int(p) for p in parts]

        # 骑师 / 练马师
        jockey = g(tds, 10)
        trainer = g(tds, 9)

        # 完成时间
        finish_time = g(tds, 15)

        result["history"].append({
            "date": race_date,
            "venue": venue,
            "distance": distance,
            "condition": condition,
            "race_class": race_class,
            "barrier": barrier,
            "rating": rating,
            "position": position,
            "odds": odds,
            "running_positions": run_positions,
            "finish_time": finish_time,
            "jockey": jockey,
            "trainer": trainer,
        })

    return result


# ==============================================================================
# 排位表解析
# ==============================================================================

def parse_race_entries(html, race_no=None):
    """
    从 HKJC 排位表 (RaceCard) 页面 HTML 解析参赛马匹信息。

    页面结构（Playwright 动态渲染后）：
    - 正选马：<tr class="...f_tac...f_fs13...">，TD 数 24-25 列
      [0]马号  [1]历史走位  [2]马名(链接)  [3]烙号  [4]负磅
      [5]骑师  [6]档位  [7]练马师  [8-9]评分变化  [10]当前评分
      ... 其余数据
    - 后备马：结构不同（TD 数较少），但也需解析

    关键修复（2026-04-02）：
    1. 使用 Playwright 获取动态渲染的 HTML
    2. TR 匹配使用更宽松的模式：同时包含 f_tac 和 f_fs13 class
    3. 解析所有马（包含后备马），通过 is_reserve 字段区分
    """
    horses = []
    seen_ids = set()

    # 匹配包含 f_tac 和 f_fs13 的 TR（正选马 + 后备马）
    tr_pattern = re.compile(
        r'<tr[^>]*class="[^"]*f_tac[^"]*f_fs13[^"]*"[^>]*>(.*?)</tr>',
        re.DOTALL | re.IGNORECASE
    )
    td_pattern = re.compile(r'<td[^>]*>(.*?)</td>', re.DOTALL | re.IGNORECASE)

    for tr_m in tr_pattern.finditer(html):
        tr_content = tr_m.group(1)

        # 检查是否有 horseid（排除无 horseid 的标题行等）
        if 'horseid=' not in tr_content.lower():
            continue

        # 解析所有 td
        tds = td_pattern.findall(tr_content)
        td_count = len(tds)

        # 判断是否后备马：后备马通常 td_count < 12 或包含特定标记
        is_reserve = td_count < 12

        # 提取数据
        def clean_td(td_html):
            """清理 TD 内容，去除 HTML 标签"""
            clean = re.sub(r'<[^>]+>', '', td_html).strip()
            return clean.replace('&nbsp;', '').strip()

        clean_tds = [clean_td(td) for td in tds]

        def get_td(idx, default=""):
            return clean_tds[idx] if idx < len(clean_tds) else default

        # 提取 horseid 和马名
        # 格式：href="/...horse?horseid=XXX" onclick="...">马名</a>
        horse_m = re.search(r'href="[^"]*horseid=([A-Za-z0-9_]+)[^>]*>([^<]+)</a>', tr_content)
        if not horse_m:
            continue
        horse_id = horse_m.group(1).strip()
        if horse_id in seen_ids:
            continue
        seen_ids.add(horse_id)
        horse_name = horse_m.group(2).strip()

        # 提取骑师（可能有体重调整如 "(-7)"）
        jockey_m = re.search(r'jockeyid=([A-Za-z0-9_]+)', tr_content)
        jockey = jockey_m.group(1).strip() if jockey_m else ""
        # 从 TD 内容中获取骑师名称
        jockey_name = get_td(5, "").split('(')[0].strip()

        # 提取练马师
        trainer_m = re.search(r'trainerid=([A-Za-z0-9_]+)', tr_content)
        trainer = trainer_m.group(1).strip() if trainer_m else ""
        # 从 TD 内容中获取练马师名称
        trainer_name = get_td(7, "").strip()

        # 解析各字段
        # TD[0] = 马号
        try:
            horse_no = int(get_td(0, "0").strip())
        except (ValueError, IndexError):
            continue  # 跳过无效行

        # TD[4] = 负磅
        try:
            weight_str = get_td(4, "0").replace(",", "")
            weight = float(re.sub(r'[^\d.]', '', weight_str)) if weight_str else 0
        except (ValueError, IndexError):
            weight = 0

        # TD[6] = 档位（后备马通常没有档位）
        try:
            barrier_str = get_td(6, "0").strip()
            barrier = int(re.sub(r'[^\d]', '', barrier_str)) if barrier_str and re.sub(r'[^\d]', '', barrier_str) else 0
        except (ValueError, IndexError):
            barrier = 0

        # TD[10] 或 TD[9] = 当前评分
        try:
            rating_str = get_td(10, get_td(9, "40"))
            current_rating = int(re.sub(r'[^\d]', '', rating_str)) if rating_str else 40
        except (ValueError, IndexError):
            current_rating = 40

        horses.append({
            "id": horse_id,
            "name": horse_name,
            "no": horse_no,
            "barrier": barrier,
            "jockey": jockey_name,
            "jockey_code": jockey,
            "trainer": trainer_name,
            "trainer_code": trainer,
            "weight": weight,
            "current_rating": current_rating,
            "is_reserve": is_reserve,  # 标记是否为后备马
            "final_odds": None,
            "opening_odds": None,
            "tips_index": None,  # HKJC 官方贴士指数原始值
            "history": [],
            "history_same_condition_score": 40,
            "history_same_venue_score": 40,
            "class_fit_score": 50,
            "odds_value_score": 50,
            "odds_drift_score": 50,
            "sectional_score": 50,
            "jockey_score": 50,
            "trainer_score": 50,
            "barrier_score": 50,
            "tips_index_score": 50,  # HKJC 官方贴士指数评分
            "expert_score": 50,
            "total_score": 0,
            "probability": 0,
            "confidence": "⭐ 低",
            "longshot_alert": False,
        })

    return horses


def parse_race_results(html: str) -> list:
    """
    从 HKJC LocalResults.aspx 页面 HTML 解析全场赛果。

    返回结构（按场次分组）：
    [
        {
            "race_no": 1,
            "distance": 1200,
            "condition": "好地",
            "results": [
                {
                    "pos":      1,
                    "no":       "12",
                    "name":     "爆熱",
                    "jockey":   "艾兆禮",
                    "trainer":  "告東尼",
                    "weight":   118,
                    "barrier":  7,
                    "distance": "-",
                    "finish_time": "1:08.88",
                    "odds":     3.7,
                },
                ...
            ]
        },
        ...
    ]

    若解析失败，返回空列表 []。
    """
    if not html or len(html) < 500:
        return []

    races = []

    # ── 找所有赛果表格（class="f_tac table_bd draggable"）──
    # 每张表对应一个场次，<thead> 中含 "名次" / "馬號"
    table_pattern = re.compile(
        r'<table[^>]*class="[^"]*f_tac[^"]*table_bd[^"]*"[^>]*>(.*?)</table>',
        re.DOTALL | re.IGNORECASE
    )

    for tbl_m in table_pattern.finditer(html):
        tbl_html = tbl_m.group(0)
        # 检查是否为赛果表（表头含"名次"）
        if '名次' not in tbl_html or '馬號' not in tbl_html:
            continue

        # 提取场次号（查找 "第 X 场" 附近的文字）
        race_no = 0
        race_m = re.search(r'第\s*([1-9]|1[0-9])\s*場', tbl_html)
        if race_m:
            race_no = int(race_m.group(1))
        if not race_no:
            race_no = len(races) + 1

        # 提取距离（表头附近 "1200米"）
        distance = 0
        dist_m = re.search(r'(\d+)\s*米', tbl_html)
        if dist_m:
            distance = int(dist_m.group(1))

        # 提取场地状况（表头附近 "好地" 等）
        condition = ""
        for cond in ["好地", "快地", "黏地", "濕慢地", "全天候"]:
            if cond in tbl_html:
                condition = cond
                break

        # ── 逐 <tr> 解析马匹成绩 ──
        tr_pattern = re.compile(r'<tr[^>]*>(.*?)</tr>', re.DOTALL)
        td_pattern = re.compile(r'<td[^>]*>(.*?)</td>', re.DOTALL)

        results = []
        seen_nos = set()

        for tr_m in tr_pattern.finditer(tbl_html):
            tr_html = tr_m.group(1)
            tds_raw = td_pattern.findall(tr_html)
            if len(tds_raw) < 3:
                continue

            # 清理：去除所有子标签，只保留文本
            tds = [
                re.sub(r'<[^>]+>', ' ', td).strip().replace('\n', ' ').replace('\r', '')
                for td in tds_raw
            ]
            tds = [re.sub(r'\s+', ' ', t).strip() for t in tds]

            # 列0：名次（可能含相机链接文字，取末尾数字）
            pos_text = tds[0] if len(tds) > 0 else ""
            pos_m = re.search(r'(\d+)\s*$', pos_text)
            if not pos_m:
                continue

            # 列1：马号（纯数字 1-14）
            no_text = tds[1] if len(tds) > 1 else ""
            no_m = re.match(r'^\s*(\d{1,2})\s*$', no_text)
            if not no_m:
                continue
            no = no_m.group(1).strip()
            if no in seen_nos:
                continue
            seen_nos.add(no)

            # 列2：马名（可能含 "(G368)" 后缀）
            name_text = tds[2] if len(tds) > 2 else ""
            name_m = re.match(r'^(.+?)\s*(?:&nbsp;)?\s*\([A-Z]\d+\)', name_text)
            name = name_m.group(1).strip() if name_m else name_text.strip()

            # 列3：骑师
            jockey = tds[3].strip() if len(tds) > 3 else ""

            # 列4：练马师
            trainer = tds[4].strip() if len(tds) > 4 else ""

            # 列5：实际负磅
            weight = 0
            wt_m = re.search(r'\d+', tds[5]) if len(tds) > 5 else None
            if wt_m:
                weight = int(wt_m.group(0))

            # 列7：档位
            barrier = 0
            br_m = re.search(r'\d+', tds[7]) if len(tds) > 7 else None
            if br_m:
                barrier = int(br_m.group(0))

            # 列8：头马距离
            distance_txt = tds[8].strip() if len(tds) > 8 else "-"

            # 列10：完成时间
            finish_time = tds[10].strip() if len(tds) > 10 else ""

            # 列11：独赢赔率
            odds = None
            od_m = re.search(r'[\d.]+', tds[11]) if len(tds) > 11 else None
            if od_m:
                try:
                    odds = float(od_m.group(0))
                except ValueError:
                    odds = None

            try:
                pos = int(pos_m.group(1))
                if 1 <= pos <= 20 and name:
                    results.append({
                        "pos": pos,
                        "no": no,
                        "name": name,
                        "jockey": jockey,
                        "trainer": trainer,
                        "weight": weight,
                        "barrier": barrier,
                        "distance": distance_txt,
                        "finish_time": finish_time,
                        "odds": odds,
                    })
            except (ValueError, IndexError):
                continue

        if results:
            races.append({
                "race_no": race_no,
                "distance": distance,
                "condition": condition,
                "results": results,
            })

    # 按场次号排序
    races.sort(key=lambda x: x["race_no"])
    return races


def validate_race_entries(horses, race_no=None):
    """
    验证解析结果的完整性，提前发现页面结构变更。

    检查项：
    1. 正选马数量是否正常（通常 10-12 匹）
    2. 必需字段是否完整（id/name/no/current_rating）
    3. 马号/评分是否有异常值

    返回：(is_valid, warnings) 元组
    """
    warnings = []
    is_valid = True

    if not horses:
        warnings.append("未解析出任何马匹，可能页面结构已变更")
        return False, warnings

    # 分离正选和后备马
    regular_horses = [h for h in horses if not h.get("is_reserve", False)]

    # 检查正选马数量
    if len(regular_horses) < 10:
        warnings.append(f"正选马数量异常少（{len(regular_horses)} 匹），页面结构可能已变更")
        is_valid = False

    # 检查必需字段
    required_fields = ["id", "name", "no", "current_rating"]
    missing_fields_horses = []

    for horse in horses:
        missing = [f for f in required_fields if not horse.get(f)]
        if missing:
            missing_fields_horses.append(f"#{horse.get('no', '?')}: {', '.join(missing)}")

    if missing_fields_horses:
        warnings.append(f"部分马匹缺少必需字段: {missing_fields_horses[:3]}")
        is_valid = False

    # 检查马号连续性
    horse_numbers = sorted([h.get("no", 0) for h in horses if h.get("no", 0) > 0])
    if horse_numbers:
        expected = list(range(horse_numbers[0], horse_numbers[0] + len(horse_numbers)))
        if horse_numbers != expected:
            warnings.append(f"马号可能不连续: {horse_numbers}")

    # 检查评分范围
    ratings = [h.get("current_rating", 0) for h in horses if h.get("current_rating", 0) > 0]
    if ratings:
        min_r, max_r = min(ratings), max(ratings)
        if max_r - min_r > 80:
            warnings.append(f"评分跨度异常大（{min_r}-{max_r}），可能解析有误")
            is_valid = False

    return is_valid, warnings
