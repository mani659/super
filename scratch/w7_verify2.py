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
    return 'OTHER'


def exit_owner(comment):
    """Bot named by the CLOSING order comment, else None."""
    c = comment.strip()
    if c.startswith('STv2') or c.startswith('SuperTrend'):
        return 'ST'
    if 'CAB' in c or c.startswith('cab_managed'):
        return 'CAB'
    if c.startswith('SNIPER'):
        return 'GHOST'
    return None


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

# per (symbol, bot) entry queues + per-symbol fallback queue
q_bot = defaultdict(deque)   # (symbol, bot) -> entries
q_all = defaultdict(deque)   # symbol -> entries (fallback)
trades = []


def pop_match(symbol, want_bot, need):
    """Take `need` volume from the (symbol,want_bot) queue if possible; else from symbol queue."""
    q = q_bot[(symbol, want_bot)] if want_bot else q_all[symbol]
    taken = []
    rem = need
    while rem > 1e-9 and q:
        head = q[0]
        take = min(rem, head['vol'])
        taken.append((head, take))
        head['vol'] -= take
        rem -= take
        if head['vol'] <= 1e-9:
            q.popleft()
    return taken, rem


for d in deals:
    sym = d['symbol']
    if d['d'] == 'in':
        bot = entry_bot(orders.get(d['order'], ''))
        e = dict(vol=d['vol'], bot=bot, t0=d['time'], dirn=d['typ'], price=d['price'])
        q_bot[(sym, bot)].append(e)
        q_all[sym].append(e)
    elif d['d'] == 'out':
        pnl_full = d['profit'] + d['comm'] + d['fee'] + d['swap']
        owner = exit_owner(orders.get(d['order'], ''))
        want = {'ST': 'ST', 'CAB': 'CAB', 'GHOST': 'GHOST202'}.get(owner)
        got, rem = pop_match(sym, want, d['vol'])
        if rem > 1e-9:  # named bot had no open vol -> fall back to any
            got2, rem = pop_match(sym, None, rem)
            got += got2
        for (head, take) in got:
            trades.append(dict(bot=head['bot'], symbol=sym, dirn=head['dirn'],
                               t0=head['t0'], t1=d['time'],
                               hold_h=(d['time'] - head['t0']).total_seconds() / 3600,
                               pnl=pnl_full * (take / d['vol']),
                               pnl_net_cost=pnl_full * (take / d['vol']),
                               profit_only=d['profit'] * (take / d['vol']),
                               exit_c=orders.get(d['order'], ''),
                               exit_price=d['price']))
        if rem > 1e-9:
            trades.append(dict(bot='UNMATCHED', symbol=sym, dirn='?', t0=None,
                               t1=d['time'], hold_h=None, pnl=pnl_full * (rem / d['vol']),
                               pnl_net_cost=pnl_full * (rem / d['vol']),
                               profit_only=d['profit'] * (rem / d['vol']),
                               exit_c=orders.get(d['order'], ''), exit_price=d['price']))

W0, W1 = datetime(2026, 9, 1), datetime(2026, 9, 6)
w7 = [t for t in trades if t['t1'] and W0 <= t['t1'] < W1]

print('=== W7 BY BOT (attribution via exit-order comment, FIFO fallback) ===')
print(f"{'bot':<10}{'n':>5}{'WR':>8}{'fullPnL':>10}{'profitOnly':>11}{'avg':>8}{'PF':>7}")
for bot in ['CAB', 'ST', 'GHOST202', 'GHOST204', 'OTHER', 'UNMATCHED']:
    ts = [t for t in w7 if t['bot'] == bot]
    if not ts:
        continue
    n = len(ts)
    tot = sum(t['pnl'] for t in ts)
    pon = sum(t['profit_only'] for t in ts)
    gp = sum(t['pnl'] for t in ts if t['pnl'] > 0)
    gl = -sum(t['pnl'] for t in ts if t['pnl'] <= 0)
    wr = sum(1 for t in ts if t['pnl'] > 0) / n * 100
    print(f"{bot:<10}{n:>5}{wr:>7.1f}%{tot:>10.2f}{pon:>11.2f}{tot/n:>8.2f}{(gp/gl if gl>0 else float('inf')):>7.2f}")

print()
print('=== W7 BY BOT x SYMBOL (metals focus) ===')
agg = defaultdict(lambda: [0, 0.0, 0])
for t in w7:
    a = agg[(t['bot'], t['symbol'])]
    a[0] += 1
    a[1] += t['pnl']
    a[2] += 1 if t['pnl'] > 0 else 0
for (bot, sym), a in sorted(agg.items(), key=lambda kv: -abs(kv[1][1]))[:12]:
    print(f"{bot:<10}{sym:<12}n={a[0]:>3}  WR={a[2]/a[0]*100:>5.1f}%  pnl={a[1]:>9.2f}  avg={a[1]/a[0]:>7.2f}")

print()
print('=== TOP 12 W7 TRADES BY ABS P&L (who really owns them) ===')
for t in sorted(w7, key=lambda t: -abs(t['pnl']))[:12]:
    print(f"{t['t1']:%m-%d %H:%M} {t['bot']:<9}{t['symbol']:<10}{t['dirn']:<5}"
          f"pnl={t['pnl']:>8.2f} hold={t['hold_h'] if t['hold_h'] is not None else -1:>6.1f}h"
          f" exitC={t['exit_c'][:38]!r}")

print()
print('=== ST + CAB XAGUSDm trade-by-trade (the disputed symbol) ===')
for t in sorted([t for t in w7 if t['symbol'] == 'XAGUSDm'], key=lambda t: t['t1']):
    print(f"{t['t1']:%m-%d %H:%M} {t['bot']:<9}{t['dirn']:<5}pnl={t['pnl']:>8.2f} "
          f"hold={t['hold_h'] if t['hold_h'] is not None else -1:>6.1f}h exitC={t['exit_c'][:40]!r}")

print()
print('=== W7 DAILY NET (full cost) BY BOT ===')
days = sorted(set(t['t1'].date() for t in w7))
print('day       ' + ''.join(f'{b:>10}' for b in ['CAB', 'ST', 'GHOST202', 'GHOST204']))
for day in days:
    row = [sum(t['pnl'] for t in w7 if t['bot'] == b and t['t1'].date() == day)
           for b in ['CAB', 'ST', 'GHOST202', 'GHOST204']]
    print(str(day) + ''.join(f'{v:>10.2f}' for v in row))

print()
print('=== CAB W7 direction split (full cost) ===')
for dirn in ['sell', 'buy']:
    ts = [t for t in w7 if t['bot'] == 'CAB' and t['dirn'] == dirn]
    if ts:
        print(f"CAB {dirn:<5} n={len(ts):>3} WR={sum(1 for t in ts if t['pnl']>0)/len(ts)*100:>5.1f}% "
              f"pnl={sum(t['pnl'] for t in ts):>9.2f}")

print()
print('=== OUTLIER CONCENTRATION (revised attribution) ===')
for bot in ['CAB', 'ST', 'GHOST202']:
    ts = sorted([t for t in w7 if t['bot'] == bot], key=lambda t: -t['pnl'])
    if not ts:
        continue
    tot = sum(t['pnl'] for t in ts)
    gp = sum(t['pnl'] for t in ts if t['pnl'] > 0)
    top2 = sum(t['pnl'] for t in ts[:2])
    print(f"{bot}: total={tot:.2f} GP={gp:.2f} top1={ts[0]['pnl']:.2f} "
          f"({(ts[0]['pnl']/gp*100 if gp>0 else 0):.0f}% of GP) | net excl top-2 = {tot-top2:.2f}")

print()
print('=== GHOST202 distribution (revised) ===')
ts = sorted(t['pnl'] for t in w7 if t['bot'] == 'GHOST202')
n = len(ts)
print(f"n={n} min={ts[0]:.2f} p10={ts[n//10]:.2f} med={ts[n//2]:.2f} p90={ts[9*n//10]:.2f} max={ts[-1]:.2f}")
