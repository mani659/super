import re
from collections import defaultdict, deque, Counter
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
                          profit=num(tds[12]), balance=tds[13]))

print('deal direction values:', Counter(d['d'] for d in deals))
print()
print('--- in/out deals (reversals) ---')
for d in deals:
    if d['d'] == 'in/out':
        print(f"{d['time']:%m-%d %H:%M:%S} {d['symbol']:<10}{d['typ']:<5} vol={d['vol']} "
              f"pnl={d['profit'] + d['comm'] + d['fee'] + d['swap']:.2f} order={d['order']} "
              f"c={orders.get(d['order'], '')[:30]!r}")
print()
print('--- W7 XAGUSDm deals 09-03 19:55 .. 09-03 20:10 ---')
W0, W1 = datetime(2026, 9, 1), datetime(2026, 9, 6)
for d in deals:
    if d['symbol'] == 'XAGUSDm' and datetime(2026, 9, 3, 19, 55) <= d['time'] <= datetime(2026, 9, 3, 20, 10):
        print(f"{d['time']:%m-%d %H:%M:%S} {d['typ']:<5}{d['d']:<7} vol={d['vol']} price={d['price']} "
              f"pnl={d['profit']:.2f} bal={d['balance']} order={d['order']} c={orders.get(d['order'], '')[:30]!r}")
print()
print('--- zero-profit out deals in W7 (count + samples) ---')
zp = [d for d in deals if d['d'] in ('out', 'in/out') and W0 <= d['time'] < W1
      and abs(d['profit'] + d['comm'] + d['fee'] + d['swap']) < 0.005]
print('count:', len(zp))
for d in zp[:10]:
    print(f"{d['time']:%m-%d %H:%M} {d['symbol']:<10}{d['typ']:<5}{d['d']:<7} vol={d['vol']} order={d['order']} c={orders.get(d['order'], '')[:30]!r}")
print()
print('--- ACCOUNT-LEVEL W7 REALIZED (all closing deals, no attribution) ---')
w7close = [d for d in deals if d['d'] in ('out', 'in/out') and W0 <= d['time'] < W1]
tot = sum(d['profit'] + d['comm'] + d['fee'] + d['swap'] for d in w7close)
print(f"n closing deals={len(w7close)}  total pnl(comm/fee/swap incl)={tot:.2f}")
w7in = [d for d in deals if d['d'] in ('in', 'in/out') and W0 <= d['time'] < W1]
print(f"n opening deals={len(w7in)} (their profit should be ~0): {sum(d['profit'] for d in w7in):.2f}")
print()
print('--- DECISIVE EXIT-COMMENT SUMS (W7, no queue needed) ---')


def num_or(s):
    return d  # placeholder


groups = {'STv2-exit': 0, 'CAB-exit': 0, 'SNIPER-exit': 0, 'sl/tp-exit': 0, 'empty-exit': 0}
groupn = Counter()
for d in w7close:
    c = orders.get(d['order'], '').strip()
    pnl = d['profit'] + d['comm'] + d['fee'] + d['swap']
    if c.startswith('STv2') or c.startswith('SuperTrend'):
        g = 'STv2-exit'
    elif 'CAB' in c:
        g = 'CAB-exit'
    elif c.startswith('SNIPER'):
        g = 'SNIPER-exit'
    elif c.startswith('[sl') or c.startswith('[tp'):
        g = 'sl/tp-exit'
    else:
        g = 'empty-exit'
    groups[g] += pnl
    groupn[g] += 1
for g in groups:
    print(f"{g:<13} n={groupn[g]:>4}  pnl={groups[g]:>9.2f}")
