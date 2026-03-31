import json, glob, re, sys, os
sys.stdout.reconfigure(encoding='utf-8')

# 相对于脚本文件定位缓存目录，避免硬编码绝对路径
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
cache_dir = os.path.join(os.path.dirname(_SCRIPT_DIR), '.cache')
files = glob.glob(cache_dir + '/*.json')
with open(files[0], encoding='utf-8') as f:
    entry = json.load(f)
content = entry['content']

header_idx = content.find('馬號')
tbody_start = content.find('f_fs12 fontFam', header_idx)
tbody_tag_start = content.rfind('<tbody', 0, tbody_start + 20)
tbody_end = content.find('</tbody>', tbody_tag_start)
tbody_html = content[tbody_tag_start: tbody_end + len('</tbody>')]

tr_pattern = re.compile(r'<tr[^>]*>(.*?)</tr>', re.DOTALL)
td_pattern = re.compile(r'<td[^>]*>(.*?)</td>', re.DOTALL)

rows = []
for tr_m in tr_pattern.finditer(tbody_html):
    tr_content = tr_m.group(1)
    if 'horseid=' not in tr_content:
        continue
    horse_link = re.search(r'horseid=([A-Za-z0-9_]+)[^>]+>([^<]+)</a>', tr_content)
    if not horse_link:
        continue
    name = re.sub(r'&nbsp;.*', '', horse_link.group(2)).strip()
    hid  = horse_link.group(1).strip()

    jockey_m  = re.search(r'jockeyid=[^"]+[^>]+>([^<]+)</a>', tr_content)
    trainer_m = re.search(r'trainerid=[^"]+[^>]+>([^<]+)</a>', tr_content)
    jockey  = jockey_m.group(1).strip()  if jockey_m  else ''
    trainer = trainer_m.group(1).strip() if trainer_m else ''

    tds_raw = [td_m.group(1) for td_m in td_pattern.finditer(tr_content)]
    tds = [re.sub(r'<[^>]+>', ' ', td).strip() for td in tds_raw]
    def g(i): return tds[i] if i < len(tds) else ''

    rows.append({
        'rank':     g(0),
        'no':       g(1),
        'name':     name,
        'horseid':  hid,
        'jockey':   jockey,
        'trainer':  trainer,
        'weight':   g(6),
        'barrier':  g(7),
        'gap':      g(8),
        'sectional':g(9),
        'time':     g(10),
        'odds':     g(11),
    })

print(json.dumps(rows, ensure_ascii=False, indent=2))
