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


def bot_of(comment):
    c = comment.strip()
    if c.startswith('SNIPER_R'):
        return 'GHOST202'
    if c.startswith('SNIPER_GC'):
        return 'GHOST204'
    if c.startswith('cab_managed'):
        return 'CAB'
    if c.startswith('SuperTrend'):
        return 'ST'
    return 'OTHER/SL'


orders = {}
for tr in tr_re.findall(orders_html):
    tds = [clean(t) for t in td_re.findall(tr)]
    if len(tds) >= 11 and tds[1].isdigit():
        orders[tds[1]] = tds[10]

deals = []
for tr in tr_re.findall(deals_html):
    tds = [clean(t) for t in td_re.findall(tr)]
    if len(tds) >= 14 and len(tds[1]) >= 9 and tds[1].isdigit():
        t = datetime.strptime(tds[0], '%Y.%m.%d %H:%M:%S')
        def num(s):
            return float(s.replace(' ', '') or 0)
        deals.append(dict(time=t, symbol=tds[2], typ=tds[3], d=tds[4],
                          vol=num(tds[5]), order=tds[7],
                          comm=num(tds[9]), fee=num(tds[10]),
                          swap=num(tds[11]), profit=num(tds[12])))
print('deals parsed:', len(deals),
      '| in:', sum(1 for d in deals if d['d'] == 'in'),
      '| out:', sum(1 for d in deals if d['d'] == 'out'))

open_q = defaultdict(deque)
trades = []
for d in deals:
    key = d['symbol']
    if d['d'] == 'in':
        bot = bot_of(orders.get(d['order'], ''))
        open_q[key].append(dict(vol=d['vol'], bot=bot, t0=d['time'], dirn=d['typ']))
    elif d['d'] == 'out':
        need = d['vol']
        pnl = d['profit'] + d['comm'] + d['fee'] + d['swap']
        t1 = d['time']
        while need > 1e-9 and open_q[key]:
            head = open_q[key][0]
            take = min(need, head['vol'])
            trades.append(dict(bot=head['bot'], symbol=key, dirn=head['dirn'],
                               t0=head['t0'], t1=t1,
                               hold_h=(t1 - head['t0']).total_seconds() / 3600,
                               pnl=pnl * (take / d['vol'])))
            head['vol'] -= take
            need -= take
            if head['vol'] <= 1e-9:
                open_q[key].popleft()
        if need > 1e-9:
            trades.append(dict(bot='UNMATCHED', symbol=key, dirn='?', t0=None,
                               t1=t1, hold_h=None, pnl=pnl * (need / d['vol'])))

still_open = {k: round(sum(h['vol'] for h in q), 2) for k, q in open_q.items() if q}
print('still-open volumes by symbol:', still_open)

W0, W1 = datetime(2026, 9, 1), datetime(2026, 9, 6)
w7 = [t for t in trades if t['t1'] and W0 <= t['t1'] < W1]

print()
print('=== W7 CLOSED TRADES BY BOT (pnl = profit+comm+fee+swap) ===')
hdr = f"{'bot':<10}{'n':>5}{'WR':>8}{'totalPnL':>11}{'avg':>8}{'avgW':>9}{'avgL':>9}{'PF':>7}{'medHold_h':>11}"
print(hdr)
for bot in sorted(set(t['bot'] for t in w7)):
    ts = [t for t in w7 if t['bot'] == bot]
    if not ts:
        continue
    n = len(ts)
    wins = [t for t in ts if t['pnl'] > 0]
    losses = [t for t in ts if t['pnl'] <= 0]
    tot = sum(t['pnl'] for t in ts)
    gp = sum(t['pnl'] for t in wins)
    gl = -sum(t['pnl'] for t in losses)
    holds = sorted(t['hold_h'] for t in ts if t['hold_h'] is not None)
    med = holds[len(holds) // 2] if holds else -1
    avgw = sum(t['pnl'] for t in wins) / len(wins) if wins else 0.0
    avgl = sum(t['pnl'] for t in losses) / len(losses) if losses else 0.0
    pf = gp / gl if gl > 0 else float('inf')
    print(f"{bot:<10}{n:>5}{len(wins)/n*100:>7.1f}%{tot:>11.2f}{tot/n:>8.2f}"
          f"{avgw:>9.2f}{avgl:>9.2f}{pf:>7.2f}{med:>11.2f}")

print()
print('=== W7 BY BOT x SYMBOL (sorted by abs pnl) ===')
agg = defaultdict(lambda: [0, 0.0, 0])
for t in w7:
    a = agg[(t['bot'], t['symbol'])]
    a[0] += 1
    a[1] += t['pnl']
    a[2] += 1 if t['pnl'] > 0 else 0
for (bot, sym), a in sorted(agg.items(), key=lambda kv: -abs(kv[1][1])):
    print(f"{bot:<10}{sym:<12}n={a[0]:>3}  WR={a[2]/a[0]*100:>5.1f}%  pnl={a[1]:>9.2f}  avg={a[1]/a[0]:>7.2f}")

print()
print('=== OUTLIER CONCENTRATION (W7) ===')
for bot in ['CAB', 'ST', 'GHOST202']:
    ts = sorted([t for t in w7 if t['bot'] == bot], key=lambda t: -t['pnl'])
    if not ts:
        continue
    tot = sum(t['pnl'] for t in ts)
    gp = sum(t['pnl'] for t in ts if t['pnl'] > 0)
    top1 = ts[0]['pnl']
    top2 = top1 + ts[1]['pnl'] if len(ts) > 1 else top1
    top3 = top2 + ts[2]['pnl'] if len(ts) > 2 else top2
    print(f"{bot}: total={tot:.2f} GP={gp:.2f} | top1={top1:.2f} ({(top1/gp*100 if gp>0 else 0):.0f}% of GP)"
          f" top3={top3:.2f} ({(top3/gp*100 if gp>0 else 0):.0f}%) | net excl top-2 winners = {tot-top2:.2f}")

print()
print('=== W7 DAILY NET P&L BY BOT ===')
days = sorted(set(t['t1'].date() for t in w7))
print('day       ' + ''.join(f'{b:>10}' for b in ['CAB', 'ST', 'GHOST202', 'GHOST204']))
for day in days:
    row = [sum(t['pnl'] for t in w7 if t['bot'] == b and t['t1'].date() == day)
           for b in ['CAB', 'ST', 'GHOST202', 'GHOST204']]
    print(str(day) + ''.join(f'{v:>10.2f}' for v in row))

print()
print('=== CAB W7 EXCLUDING XAUUSDm+XAGUSDm ===')
cab_ex = [t for t in w7 if t['bot'] == 'CAB' and t['symbol'] not in ('XAUUSDm', 'XAGUSDm')]
n = len(cab_ex)
tot = sum(t['pnl'] for t in cab_ex)
print(f"n={n} WR={sum(1 for t in cab_ex if t['pnl']>0)/n*100:.1f}% pnl={tot:.2f} avg={tot/n:.2f}")

print()
print('=== EXPORT-WINDOW BY BOT (inception context; export starts Aug 7) ===')
for bot in ['CAB', 'ST', 'GHOST202', 'GHOST204']:
    ts = [t for t in trades if t['bot'] == bot]
    if ts:
        print(f"{bot:<10} n={len(ts):>4} pnl={sum(t['pnl'] for t in ts):>9.2f}")

print()
print('=== WILSON 95% CI (WR) ===')


def wilson(k, n):
    if n == 0:
        return (0, 0)
    p = k / n
    z = 1.96
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    return ((c - h) * 100, (c + h) * 100)


for label, k, n in [('W7 H4=DOWN (WR52.5%)', 53, 101),
                    ('W7 H4=UP (WR37.3%)', 28, 75),
                    ('W6 H4=DOWN (WR35.0%)', 87, 248),
                    ('W6 H4=UP (WR47.2%)', 55, 117)]:
    lo, hi = wilson(k, n)
    print(f"{label}: n={n} CI=[{lo:.1f}%, {hi:.1f}%]")

print()
print('=== GHOST202 W7: P&L distribution shape ===')
ts = sorted([t['pnl'] for t in w7 if t['bot'] == 'GHOST202'])
n = len(ts)
print(f"n={n} min={ts[0]:.2f} p10={ts[n//10]:.2f} median={ts[n//2]:.2f} "
      f"p90={ts[9*n//10]:.2f} max={ts[-1]:.2f}")
print(f"sum top-5 wins={sum(ts[-5:]):.2f} | sum bottom-5 losses={sum(ts[:5]):.2f}")
