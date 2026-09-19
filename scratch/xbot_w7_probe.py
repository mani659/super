import re
from datetime import datetime

def parse_mt5_html(path):
    raw = open(path, 'rb').read()
    txt = raw.decode('utf-16', errors='ignore')
    oi, di = txt.find('Orders</b>'), txt.find('Deals</b>')
    if oi == -1 or di == -1:
        return None, None, None
    orders_html, deals_html = txt[oi:di], txt[di:]
    tr_re = re.compile(r'<tr[^>]*>(.*?)</tr>', re.S)
    td_re = re.compile(r'<td[^>]*>(.*?)</td>', re.S)
    def clean(s):
        return re.sub(r'<[^>]+>', '', s).replace('&nbsp;', ' ').strip()
    orders = {}
    for tr in tr_re.findall(orders_html):
        tds = [clean(t) for t in td_re.findall(tr)]
        if len(tds) >= 11 and tds[1].isdigit():
            orders[tds[1]] = tds[10]
    deals = []
    for tr in tr_re.findall(deals_html):
        tds = [clean(t) for t in td_re.findall(tr)]
        if len(tds) >= 14 and len(tds[1]) >= 9 and tds[1].isdigit():
            try:
                t = datetime.strptime(tds[0], '%Y.%m.%d %H:%M:%S')
            except Exception:
                continue
            deals.append(dict(time=t, symbol=tds[2], typ=tds[3], d=tds[4],
                              order=tds[7], comment=orders.get(tds[7], '')))
    return orders, deals, txt

for path in ['ReportHistory-474167713.html', 'cab/ReportHistory-262924445.html']:
    orders, deals, _ = parse_mt5_html(path)
    print(f"=== {path} ===")
    if deals is None:
        print("  parse failed"); continue
    print(f"  deals={len(deals)} first={deals[0]['time']} last={deals[-1]['time']}")
    from collections import Counter
    w7 = [d for d in deals if datetime(2026,9,1) <= d['time'] < datetime(2026,9,6)]
    print(f"  W7 deals (Sep1-5): {len(w7)}  in={sum(1 for d in w7 if d['d']=='in')} out={sum(1 for d in w7 if d['d']=='out')}")
    if w7:
        c = Counter(d['comment'][:24] for d in w7 if d['d']=='out')
        print("  W7 out-comments:", dict(c.most_common(12)))

print()
print("=== cab/cab_watcher_production.log W7 activity ===")
import io
log = open('cab/cab_watcher_production.log', encoding='utf-8', errors='ignore').read()
dates = Counter()
for m in re.finditer(r'(\d{4}-\d{2}-\d{2}) \d{2}:\d{2}:\d{2}', log):
    dates[m.group(1)] += 1
for d in sorted(dates):
    if d >= '2026-08-30':
        print(f"  {d}: {dates[d]} lines")

print()
print("=== cab_multi_pair/cab_performance_ledger.csv ===")
led = open('cab_multi_pair/cab_performance_ledger.csv', encoding='utf-8', errors='ignore').read()
lines = led.splitlines()
print("  rows:", len(lines))
print("  header:", lines[0][:200])
print("  first:", lines[1][:200] if len(lines) > 1 else '')
print("  last :", lines[-1][:200])

print()
print("=== cab_multi_pair xlsx ===")
try:
    import pandas as pd
    xl = pd.ExcelFile('cab_multi_pair/ReportHistory-260714012.xlsx')
    print("  sheets:", xl.sheet_names)
    for s in xl.sheet_names[:3]:
        df = xl.parse(s, nrows=5)
        print(f"  -- {s}: cols={list(df.columns)[:8]}")
except Exception as e:
    print("  xlsx error:", e)