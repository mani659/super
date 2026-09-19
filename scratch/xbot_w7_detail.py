import re
from collections import defaultdict
from datetime import datetime

W0, W1 = datetime(2026, 9, 1), datetime(2026, 9, 6)

def parse_mt5_html(path):
    raw = open(path, 'rb').read()
    txt = raw.decode('utf-16', errors='ignore')
    oi, di = txt.find('Orders</b>'), txt.find('Deals</b>')
    orders_html, deals_html = txt[oi:di], txt[di:]
    tr_re = re.compile(r'<tr[^>]*>(.*?)</tr>', re.S)
    td_re = re.compile(r'<td[^>]*>(.*?)</td>', re.S)
    def clean(s):
        return re.sub(r'<[^>]+>', '', s).replace('&nbsp;', ' ').strip()
    def num(s):
        return float(s.replace(' ', '') or 0)
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
                              vol=num(tds[5]), price=tds[6], order=tds[7],
                              comm=num(tds[9]), fee=num(tds[10]), swap=num(tds[11]),
                              profit=num(tds[12]), comment=orders.get(tds[7], '')))
    return orders, deals

def cab_strategy(comment):
    c = comment.strip()
    if c.startswith('INV_'): return 'INVERSION'
    if c.startswith('CONT_'): return 'CONTINUATION'
    if c.startswith('GRID_'): return 'GRID'
    return 'OTHER'

print("=== cab/ (262924445) W7 trade-by-trade ===")
orders, deals = parse_mt5_html('cab/ReportHistory-262924445.html')
open_pos = defaultdict(list)
trades = []
for d in deals:
    sym = d['symbol']
    pnl_full = d['profit'] + d['comm'] + d['fee'] + d['swap']
    if d['d'] == 'in':
        open_pos[sym].append(dict(vol=d['vol'], strat=cab_strategy(orders.get(d['order'], '')),
                                  t0=d['time'], dirn=d['typ'], price=d['price'],
                                  ecomment=orders.get(d['order'], '')[:24]))
    elif d['d'] == 'out':
        exit_c = orders.get(d['order'], '').strip()
        need = d['vol']
        got = []
        for p in open_pos[sym]:
            if need <= 1e-9: break
            if p['vol'] > 1e-9:
                take = min(need, p['vol'])
                got.append((p, take)); p['vol'] -= take; need -= take
        open_pos[sym] = [p for p in open_pos[sym] if p['vol'] > 1e-9]
        for (p, take) in got:
            trades.append(dict(strat=p['strat'], symbol=sym, dirn=p['dirn'], t0=p['t0'],
                               t1=d['time'], vol=take, pin=p['price'], px=d['price'],
                               pnl=pnl_full * (take / d['vol']), exit_c=exit_c,
                               ecomment=p['ecomment']))
w7c = [t for t in trades if W0 <= t['t1'] < W1]
for t in sorted(w7c, key=lambda t: t['t1']):
    print(f"{t['t0']:%m-%d %H:%M} -> {t['t1']:%m-%d %H:%M} {t['strat']:<13}{t['symbol']:<10}"
          f"{t['dirn']:<5}vol={t['vol']:<6}{t['pin']} -> {t['px']}  pnl=${t['pnl']:>9.2f}  "
          f"exit={t['exit_c'][:20] or 'BROKER_SL_TP':<20} entryC={t['ecomment']!r}")
print(f"\nTOTAL n={len(w7c)} pnl=${sum(t['pnl'] for t in w7c):.2f}")
print(f"entries BEFORE W7 (decisions not made last week): {sum(1 for t in w7c if t['t0'] < W0)}")

print("\n=== cab_multi_pair xlsx probe ===")
try:
    import pandas as pd
    xl = pd.ExcelFile('cab_multi_pair/ReportHistory-260714012.xlsx')
    df = xl.parse('Sheet1', header=None)
    print("shape:", df.shape)
    # find row that looks like header (contains 'Time' or 'Deal')
    hdr_row = None
    for i in range(min(5, len(df))):
        rowvals = [str(v) for v in df.iloc[i].tolist() if str(v) != 'nan']
        if any('ime' in v for v in rowvals) or 'Deal' in rowvals:
            hdr_row = i
            print(f"header at row {i}: {rowvals[:16]}")
            break
    if hdr_row is not None:
        df2 = pd.read_excel('cab_multi_pair/ReportHistory-260714012.xlsx', header=hdr_row)
        print("cols:", list(df2.columns)[:16])
        print(df2.head(3).to_string())
except Exception as e:
    print("xlsx probe error:", e)