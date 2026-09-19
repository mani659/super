import csv
from collections import defaultdict
from datetime import datetime

W0, W1 = datetime(2026, 9, 1), datetime(2026, 9, 6)

CONTRACT = {'XAUUSDm': 100, 'XAGUSDm': 5000, 'BTCUSDm': 1, 'ETHUSDm': 1,
            'USOILm': 1000, 'USTECm': 10, 'EURUSDm': 100000, 'GBPUSDm': 100000,
            'USDJPYm': 100000, 'EURGBPm': 100000, 'AUDNZDm': 100000}
# to-USD conversion for non-USD quoted crosses (approximate mid-week rates)
FX2USD = {'USDJPYm': lambda exit_p: 1.0 / exit_p, 'EURGBPm': lambda exit_p: 1.35,
          'AUDNZDm': lambda exit_p: 0.68}

rows = []
with open('cab_multi_pair/cab_performance_ledger.csv', encoding='utf-8', errors='ignore') as f:
    for r in csv.DictReader(f):
        try:
            ct = datetime.strptime(r['CloseTime'], '%Y-%m-%d %H:%M:%S')
        except Exception:
            continue
        if W0 <= ct < W1:
            rows.append(r)

total = 0.0
by_sym = defaultdict(lambda: [0, 0.0, 0])
for r in rows:
    sym = r['Symbol']
    op, ep = float(r['OpenPrice']), float(r['ExitPrice'])
    vol = float(r['Volume'])
    sign = 1 if r['Direction'] == 'BUY' else -1
    raw = (ep - op) * sign * vol * CONTRACT.get(sym, 0)
    if sym in FX2USD:
        usd = raw * FX2USD[sym](ep)
    else:
        usd = raw
    total += usd
    a = by_sym[sym]; a[0] += 1; a[1] += usd; a[2] += 1 if float(r['Realized_R']) > 0 else 0

print(f"cab_multi_pair W7 est USD: n={len(rows)} total=${total:.2f} "
      f"WR={sum(1 for r in rows if float(r['Realized_R'])>0)/len(rows)*100:.1f}% "
      f"avg=${total/len(rows):.2f}")
print(f"\n{'symbol':<10}{'n':>4}{'WR':>7}{'estUSD':>10}{'avg':>9}")
for k, v in sorted(by_sym.items(), key=lambda x: -abs(x[1][1])):
    n, tot, wins = v
    print(f"{k:<10}{n:>4}{wins/n*100:>6.1f}%{tot:>10.2f}{tot/n:>9.2f}")

# dollar per exit reason
by_exit = defaultdict(lambda: [0, 0.0, 0])
for r in rows:
    sym = r['Symbol']
    op, ep = float(r['OpenPrice']), float(r['ExitPrice'])
    vol = float(r['Volume'])
    sign = 1 if r['Direction'] == 'BUY' else -1
    raw = (ep - op) * sign * vol * CONTRACT.get(sym, 0)
    usd = raw * FX2USD[sym](ep) if sym in FX2USD else raw
    a = by_exit[r['ExitReason']]; a[0] += 1; a[1] += usd; a[2] += 1 if float(r['Realized_R']) > 0 else 0
print(f"\n{'exit':<20}{'n':>4}{'WR':>7}{'estUSD':>10}{'avg':>9}")
for k, v in sorted(by_exit.items(), key=lambda x: -abs(x[1][1])):
    n, tot, wins = v
    print(f"{k:<20}{n:>4}{wins/n*100:>6.1f}%{tot:>10.2f}{tot/n:>9.2f}")