import re
from collections import defaultdict, deque
from datetime import datetime

raw = open('ReportHistory-474167713.html', 'rb').read()
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
        deals.append(dict(time=datetime.strptime(tds[0], '%Y.%m.%d %H:%M:%S'),
                          symbol=tds[2], typ=tds[3], d=tds[4], vol=num(tds[5]),
                          price=tds[6], order=tds[7],
                          comm=num(tds[9]), fee=num(tds[10]), swap=num(tds[11]),
                          profit=num(tds[12])))


def entry_bot(comment):
    c = comment.strip()
    if c.startswith('SNIPER_R'):
        return 'GHOST202'
    if c.startswith('SNIPER_GC'):
        return 'GHOST204'
    if c.startswith('cab_managed'):
        return 'CAB'
    if c.startswith('SuperTrend'):
        return 'ST'
    return 'UNKNOWN'


# single source of truth: one open-position list per symbol
open_pos = defaultdict(list)  # symbol -> list of dicts
trades = []
for d in deals:
    sym = d['symbol']
    pnl_full = d['profit'] + d['comm'] + d['fee'] + d['swap']
    if d['d'] == 'in':
        open_pos[sym].append(dict(vol=d['vol'], bot=entry_bot(orders.get(d['order'], '')),
                                  t0=d['time'], dirn=d['typ'], order=d['order']))
    elif d['d'] == 'out':
        exit_c = orders.get(d['order'], '').strip()
        # preference order for exit ownership
        if exit_c.startswith('STv2') or exit_c.startswith('SuperTrend'):
            pref = ['ST']
        elif 'CAB' in exit_c:
            pref = ['CAB']
        elif exit_c.startswith('SNIPER'):
            pref = ['GHOST202', 'GHOST204']
        else:
            pref = None  # SL/empty: FIFO over whoever is open
        need = d['vol']
        got = []
        if pref:
            for pb in pref:
                for p in open_pos[sym]:
                    if need <= 1e-9:
                        break
                    if p['bot'] == pb and p['vol'] > 1e-9:
                        take = min(need, p['vol'])
                        got.append((p, take))
                        p['vol'] -= take
                        need -= take
        for p in open_pos[sym]:  # FIFO fallback over remaining
            if need <= 1e-9:
                break
            if p['vol'] > 1e-9:
                take = min(need, p['vol'])
                got.append((p, take))
                p['vol'] -= take
                need -= take
        open_pos[sym] = [p for p in open_pos[sym] if p['vol'] > 1e-9]
        for (p, take) in got:
            trades.append(dict(bot=p['bot'], symbol=sym, dirn=p['dirn'], t0=p['t0'],
                               t1=d['time'], hold_h=(d['time'] - p['t0']).total_seconds() / 3600,
                               pnl=pnl_full * (take / d['vol']),
                               profit_only=d['profit'] * (take / d['vol']),
                               exit_c=exit_c))

W0, W1 = datetime(2026, 9, 1), datetime(2026, 9, 6)
w7 = [t for t in trades if W0 <= t['t1'] < W1]

print('=== W7 BY BOT (single-queue, exit-comment preference) ===')
print(f"{'bot':<10}{'n':>5}{'WR':>8}{'fullPnL':>10}{'profitOnly':>11}{'avg':>8}")
for bot in ['CAB', 'ST', 'GHOST202', 'GHOST204', 'UNKNOWN']:
    ts = [t for t in w7 if t['bot'] == bot]
    if not ts:
        continue
    n = len(ts)
    tot = sum(t['pnl'] for t in ts)
    pon = sum(t['profit_only'] for t in ts)
    wr = sum(1 for t in ts if t['pnl'] > 0) / n * 100
    print(f"{bot:<10}{n:>5}{wr:>7.1f}%{tot:>10.2f}{pon:>11.2f}{tot/n:>8.2f}")

print()
print('=== W7 GHOST202 (XAUUSDm only) profit-only vs full-cost ===')
g = [t for t in w7 if t['bot'] == 'GHOST202']
print(f"n={len(g)} full={sum(t['pnl'] for t in g):.2f} profitOnly={sum(t['profit_only'] for t in g):.2f}")
costs = sum((t['pnl'] - t['profit_only']) for t in g)
print(f"total Ghost costs W7 = {costs:.2f}")

print()
print('=== Ghost H4 split cross-check vs control (control: DOWN n=99 +27.18 / UP n=75 -53.67) ===')
# H4 comes from audit CSV; here just P&L totals for sign check

print()
print('=== CROSS-BOT EXIT INTERFERENCE CHECK (exit-comment names bot A but position attributed to bot B) ===')
for t in w7:
    ec = t['exit_c']
    named = None
    if ec.startswith('STv2') or ec.startswith('SuperTrend'):
        named = 'ST'
    elif 'CAB' in ec:
        named = 'CAB'
    elif ec.startswith('SNIPER'):
        named = 'GHOST'
    if named and t['bot'] not in (named, 'GHOST202', 'GHOST204') and not (named == 'GHOST' and t['bot'].startswith('GHOST')):
        print(f"{t['t1']:%m-%d %H:%M} pos={t['bot']:<9}{t['symbol']:<10}closed-by={named:<6}"
              f"pnl={t['pnl']:>8.2f} exitC={ec[:40]!r}")

print()
print('=== metals by bot (final) ===')
agg = defaultdict(lambda: [0, 0.0, 0])
for t in w7:
    if t['symbol'] in ('XAUUSDm', 'XAGUSDm'):
        a = agg[(t['bot'], t['symbol'])]
        a[0] += 1
        a[1] += t['pnl']
        a[2] += 1 if t['pnl'] > 0 else 0
for (bot, sym), a in sorted(agg.items()):
    print(f"{bot:<10}{sym:<12}n={a[0]:>3} WR={a[2]/a[0]*100:>5.1f}% pnl={a[1]:>9.2f}")

print()
print('=== W7 total sanity ===')
print(f"sum all bots full={sum(t['pnl'] for t in w7):.2f} (account realized was 30.09)")
