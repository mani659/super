import re
from collections import defaultdict, deque
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

def session_of(dt):
    h = dt.hour
    if 0 <= h < 7: return 'ASIAN'
    if 7 <= h < 12: return 'LONDON'
    if 12 <= h < 17: return 'LONDON_NY'
    if 17 <= h < 22: return 'NY'
    return 'LATE_NY'

def tab(rows, title):
    print(f"\n=== {title} ===")
    print(f"{'bucket':<18}{'n':>5}{'WR':>8}{'P&L $':>10}{'avg':>9}")
    for k, v in sorted(rows.items(), key=lambda x: -x[1][2]):
        n, tot, wins = v
        if n == 0: continue
        print(f"{k:<18}{n:>5}{wins/n*100:>7.1f}%{tot:>10.2f}{tot/n:>9.2f}")

# ============ 1. cab_super (V1, acct 474167713) — CAB subset via w7_verify3 attribution ============
print("#" * 70)
print("# CAB_SUPER (V1 unified runner, acct 474167713)")
print("#" * 70)
orders, deals = parse_mt5_html('ReportHistory-474167713.html')
def entry_bot(comment):
    c = comment.strip()
    if c.startswith('SNIPER_R'): return 'GHOST202'
    if c.startswith('SNIPER_GC'): return 'GHOST204'
    if c.startswith('cab_managed'): return 'CAB'
    if c.startswith('SuperTrend'): return 'ST'
    return 'UNKNOWN'
open_pos = defaultdict(list)
trades = []
for d in deals:
    sym = d['symbol']
    pnl_full = d['profit'] + d['comm'] + d['fee'] + d['swap']
    if d['d'] == 'in':
        open_pos[sym].append(dict(vol=d['vol'], bot=entry_bot(orders.get(d['order'], '')),
                                  t0=d['time'], dirn=d['typ']))
    elif d['d'] == 'out':
        exit_c = orders.get(d['order'], '').strip()
        # preference order for exit ownership (verified in W7 session)
        if exit_c.startswith('STv2') or exit_c.startswith('SuperTrend'):
            pref = ['ST']
        elif 'CAB' in exit_c:
            pref = ['CAB']
        elif exit_c.startswith('SNIPER'):
            pref = ['GHOST202', 'GHOST204']
        else:
            pref = None
        need = d['vol']
        got = []
        if pref:
            for pb in pref:
                for p in open_pos[sym]:
                    if need <= 1e-9: break
                    if p['bot'] == pb and p['vol'] > 1e-9:
                        take = min(need, p['vol'])
                        got.append((p, take)); p['vol'] -= take; need -= take
        for p in open_pos[sym]:
            if need <= 1e-9: break
            if p['vol'] > 1e-9:
                take = min(need, p['vol'])
                got.append((p, take)); p['vol'] -= take; need -= take
        open_pos[sym] = [p for p in open_pos[sym] if p['vol'] > 1e-9]
        for (p, take) in got:
            trades.append(dict(bot=p['bot'], symbol=sym, dirn=p['dirn'], t0=p['t0'],
                               t1=d['time'], pnl=pnl_full * (take / d['vol'])))
w7 = [t for t in trades if W0 <= t['t1'] < W1 and t['bot'] == 'CAB']
print(f"CAB W7: n={len(w7)} WR={sum(1 for t in w7 if t['pnl']>0)/len(w7)*100:.1f}% "
      f"P&L=${sum(t['pnl'] for t in w7):.2f} avg=${sum(t['pnl'] for t in w7)/len(w7):.2f}")
by_sym = defaultdict(lambda: [0, 0.0, 0])
for t in w7:
    a = by_sym[t['symbol']]; a[0] += 1; a[1] += t['pnl']; a[2] += 1 if t['pnl'] > 0 else 0
tab(by_sym, "CAB_SUPER per-symbol")
by_dir = defaultdict(lambda: [0, 0.0, 0])
for t in w7:
    a = by_dir[t['dirn']]; a[0] += 1; a[1] += t['pnl']; a[2] += 1 if t['pnl'] > 0 else 0
tab(by_dir, "CAB_SUPER per-direction")
by_sess = defaultdict(lambda: [0, 0.0, 0])
for t in w7:
    a = by_sess[session_of(t['t1'])]; a[0] += 1; a[1] += t['pnl']; a[2] += 1 if t['pnl'] > 0 else 0
tab(by_sess, "CAB_SUPER per-close-session")

# ============ 2. cab/ standalone modular (acct 262924445) ============
print("\n" + "#" * 70)
print("# CAB (standalone modular, acct 262924445)")
print("#" * 70)
orders, deals = parse_mt5_html('cab/ReportHistory-262924445.html')
def cab_strategy(comment):
    c = comment.strip()
    if c.startswith('INV_'): return 'INVERSION'
    if c.startswith('CONT_'): return 'CONTINUATION'
    if c.startswith('GRID_'): return 'GRID'
    return 'OTHER'
open_pos = defaultdict(list)
trades = []
for d in deals:
    sym = d['symbol']
    pnl_full = d['profit'] + d['comm'] + d['fee'] + d['swap']
    if d['d'] == 'in':
        open_pos[sym].append(dict(vol=d['vol'], strat=cab_strategy(orders.get(d['order'], '')),
                                  t0=d['time'], dirn=d['typ']))
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
                               t1=d['time'], pnl=pnl_full * (take / d['vol']), exit_c=exit_c))
w7c = [t for t in trades if W0 <= t['t1'] < W1]
print(f"CAB W7: n={len(w7c)} WR={sum(1 for t in w7c if t['pnl']>0)/len(w7c)*100:.1f}% "
      f"P&L=${sum(t['pnl'] for t in w7c):.2f} avg=${sum(t['pnl'] for t in w7c)/len(w7c):.2f}")
by_strat = defaultdict(lambda: [0, 0.0, 0])
for t in w7c:
    a = by_strat[t['strat']]; a[0] += 1; a[1] += t['pnl']; a[2] += 1 if t['pnl'] > 0 else 0
tab(by_strat, "CAB per-strategy")
by_sym = defaultdict(lambda: [0, 0.0, 0])
for t in w7c:
    a = by_sym[t['symbol']]; a[0] += 1; a[1] += t['pnl']; a[2] += 1 if t['pnl'] > 0 else 0
tab(by_sym, "CAB per-symbol")
by_exit = defaultdict(lambda: [0, 0.0, 0])
for t in w7c:
    k = t['exit_c'] if t['exit_c'] else 'BROKER_SL_TP'
    a = by_exit[k]; a[0] += 1; a[1] += t['pnl']; a[2] += 1 if t['pnl'] > 0 else 0
tab(by_exit, "CAB per-exit-reason")
by_sess = defaultdict(lambda: [0, 0.0, 0])
for t in w7c:
    a = by_sess[session_of(t['t1'])]; a[0] += 1; a[1] += t['pnl']; a[2] += 1 if t['pnl'] > 0 else 0
tab(by_sess, "CAB per-close-session")

# ============ 3. cab_multi_pair (acct 260714012) — ledger CSV ============
print("\n" + "#" * 70)
print("# CAB_MULTI_PAIR (acct 260714012) — from performance ledger")
print("#" * 70)
import csv
led = []
with open('cab_multi_pair/cab_performance_ledger.csv', encoding='utf-8', errors='ignore') as f:
    for row in csv.DictReader(f):
        try:
            ct = datetime.strptime(row['CloseTime'], '%Y-%m-%d %H:%M:%S')
        except Exception:
            continue
        if W0 <= ct < W1:
            led.append(dict(row, ct=ct))
print(f"CAB_MULTI_PAIR W7 closed: n={len(led)}")
by_exit = defaultdict(lambda: [0, 0.0, 0])
by_sym = defaultdict(lambda: [0, 0.0, 0])
by_sess = defaultdict(lambda: [0, 0.0, 0])
for r in led:
    rv = float(r['Realized_R'])
    for d, a in ((by_exit, by_exit[r['ExitReason']]),
                 (by_sym, by_sym[r['Symbol']]),
                 (by_sess, by_sess[session_of(r['ct'])])):
        a[0] += 1; a[1] += rv; a[2] += 1 if rv > 0 else 0
for d, title in ((by_exit, "CAB_MULTI_PAIR per-exit (R)"), (by_sym, "CAB_MULTI_PAIR per-symbol (R)"),
                 (by_sess, "CAB_MULTI_PAIR per-close-session (R)")):
    print(f"\n=== {title} ===")
    print(f"{'bucket':<18}{'n':>5}{'WR':>8}{'sumR':>9}{'avgR':>8}")
    for k, v in sorted(d.items(), key=lambda x: -x[1][1]):
        n, tot, wins = v
        if n == 0: continue
        print(f"{k:<18}{n:>5}{wins/n*100:>7.1f}%{tot:>9.2f}{tot/n:>8.2f}")
vols = [float(r['Volume']) for r in led]
print(f"\nvolume min={min(vols)} max={max(vols)} avg={sum(vols)/len(vols):.2f}")
for r in sorted(led, key=lambda x: float(x['Realized_R'])):
    print(f"  {r['ct']:%m-%d %H:%M} {r['Symbol']:<10}{r['Direction']:<5} vol={float(r['Volume']):.2f} "
          f"R={float(r['Realized_R']):>7.2f} {r['ExitReason']:<18} sess={r.get('Intel_Session','')}")