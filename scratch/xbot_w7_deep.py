"""Cross-bot W7 deep dive: cab vs cab_multi_pair vs cab_super.
Unified dataset with session x symbol x direction x exit cross-tabs + statistics.
READ-ONLY analysis. No file changes.

NOTE on cab_super: plain FIFO attribution is KNOWN-UNRELIABLE for the multi-bot
account 474167713 (shared XAU/XAG across CAB/ST). The control session resolved
attribution via deal-level contract math: n=48, WR=27.1%, +$85.50. That verified
dataset is the source for cab_super numbers below (per-symbol figures from the
W7 control analysis). cab/ and cab_multi_pair are single-purpose accounts where
extraction is clean."""
import re, csv, math
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
    def clean(s): return re.sub(r'<[^>]+>', '', s).replace('&nbsp;', ' ').strip()
    def num(s): return float(s.replace(' ', '') or 0)
    orders = {}
    for tr in tr_re.findall(orders_html):
        tds = [clean(t) for t in td_re.findall(tr)]
        if len(tds) >= 11 and tds[1].isdigit():
            orders[tds[1]] = tds[10]
    deals = []
    for tr in tr_re.findall(deals_html):
        tds = [clean(t) for t in td_re.findall(tr)]
        if len(tds) >= 14 and len(tds[1]) >= 9 and tds[1].isdigit():
            try: t = datetime.strptime(tds[0], '%Y.%m.%d %H:%M:%S')
            except Exception: continue
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

def cab_strategy(c):
    c = c.strip()
    if c.startswith('INV_'): return 'INVERSION'
    if c.startswith('CONT_'): return 'CONTINUATION'
    if c.startswith('GRID_'): return 'GRID'
    return 'OTHER'

def extract_pairs(path, bot_fn):
    orders, deals = parse_mt5_html(path)
    open_pos = defaultdict(list)
    trades = []
    for d in deals:
        sym = d['symbol']; pnl_full = d['profit'] + d['comm'] + d['fee'] + d['swap']
        if d['d'] == 'in':
            open_pos[sym].append(dict(bot=bot_fn(orders.get(d['order'], '')),
                                      t0=d['time'], dirn=d['typ'], pin=d['price'],
                                      ecomment=orders.get(d['order'], '')[:30], vol=d['vol']))
        elif d['d'] == 'out':
            exit_c = orders.get(d['order'], '').strip()
            need = d['vol']; got = []
            for p in open_pos[sym]:
                if need <= 1e-9: break
                if p['vol'] > 1e-9:
                    take = min(need, p['vol']); got.append((p, take)); p['vol'] -= take; need -= take
            open_pos[sym] = [p for p in open_pos[sym] if p['vol'] > 1e-9]
            for (p, take) in got:
                trades.append(dict(bot=p['bot'], symbol=sym, dirn=p['dirn'], t0=p['t0'],
                                   t1=d['time'], vol=take, pin=p['pin'], px=d['price'],
                                   pnl=pnl_full * (take / d['vol']), exit_c=exit_c,
                                   ecomment=p['ecomment']))
    return [t for t in trades if W0 <= t['t1'] < W1]

def binom_p(wins, n, p0=0.5):
    if n == 0: return 1.0
    phat = wins / n
    if n * p0 < 5: return float('nan')
    z = (abs(phat - p0) - 0.5 / n) / math.sqrt(p0 * (1 - p0) / n)
    return 2 * (1 - 0.5 * (1 + math.erf(z / math.sqrt(2))))

def ttest_p(vals):
    n = len(vals)
    if n < 2: return float('nan')
    mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / (n - 1)
    if var == 0: return 1.0
    se = math.sqrt(var / n)
    t = mean / se
    return 2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2))))

def add(rows, k, val, wins):
    r = rows.setdefault(k, {'n': 0, 'wins': 0, 'sum': 0.0, 'vals': []})
    r['n'] += 1; r['wins'] += wins; r['sum'] += val; r['vals'].append(val)

def tab(rows, title, min_n=1):
    print(f"\n=== {title} ===")
    print(f"{'bucket':<24}{'n':>5}{'WR':>8}{'sum':>10}{'avg':>9}{'t-test p':>9}")
    for k, v in sorted(rows.items(), key=lambda kv: -kv[1]['sum']):
        if v['n'] < min_n: continue
        avg = v['sum'] / v['n']
        p_t = ttest_p(v['vals'])
        flag = ' **' if p_t < 0.05 else ''
        print(f"{k:<24}{v['n']:>5}{v['wins']/v['n']*100:>7.1f}%{v['sum']:>10.2f}{avg:>9.3f}{p_t:>9.3f}{flag}")

def cohorts(name, trades, pnl_fn, label_fn, min_n=4):
    agg = defaultdict(lambda: {'n':0,'wins':0,'sum':0.0,'vals':[]})
    for t in trades:
        v = pnl_fn(t)
        add(agg, label_fn(t), v, 1 if v > 0 else 0)
    print(f"\n-- {name} --")
    scored = []
    for k, r in agg.items():
        if r['n'] < min_n: continue
        p_t = ttest_p(r['vals'])
        scored.append((k, r['n'], r['wins']/r['n'], r['sum']/r['n'], r['sum'], p_t))
    scored.sort(key=lambda x: x[4])
    print("  WORST:")
    for k, n, wr, mean, s, p in scored[:4]:
        sig = ' **' if p < 0.05 else ''
        print(f"    {k:<28} n={n:<3} WR={wr*100:>5.1f}%  avg={mean:>8.3f}  sum={s:>8.2f}  p={p:.3f}{sig}")
    print("  BEST:")
    for k, n, wr, mean, s, p in reversed(scored[-4:]):
        sig = ' **' if p < 0.05 else ''
        print(f"    {k:<28} n={n:<3} WR={wr*100:>5.1f}%  avg={mean:>8.3f}  sum={s:>8.2f}  p={p:.3f}{sig}")

# ================= 1. CAB_SUPER — CONTROL-VERIFIED figures =================
print("=" * 78)
print("CAB_SUPER (V1 unified, acct 474167713) — CONTROL-VERIFIED W7")
print("(deal-level contract math from control session; plain FIFO is unreliable)")
print("=" * 78)
# Verified: n=48, WR=27.1%, +$85.50. Per-symbol verified figures:
print("""
VERIFIED AGGREGATES:
  n=48 | WR=27.1% | P&L=+$85.50 | avg=+$1.78/trade
  BUY:  n=24  WR=29.2%  P&L=-$44.93
  SELL: n=24  WR=25.0%  P&L=+$130.43 (outlier-dominated)
  XAUUSDm: +$79.39 (n=3, 66.7% WR)   <- the outlier engine
  XAGUSDm: +$34.10 (n=5, 20.0% WR)
  USTECm:  -$13.27 drag
  USOILm:  -$21.45 drag
  GBPUSDm: -$4.38 drag
""")
# No per-trade reconstruction — only verified aggregates are used for cab_super.
# (Fabricating per-trade rows would violate data-backed discipline.)
cab_s_verified = {
    'XAUUSDm': (3, 79.39, 2), 'XAGUSDm': (5, 34.10, 1),
    'USOILm': (6, -21.45, 1), 'USTECm': (4, -13.27, 1), 'GBPUSDm': (5, -4.38, 1),
}
cab_s = []  # empty — cab_super enters cross-bot matrix via verified buckets below

# ================= 2. CAB standalone modular =================
print("\n" + "=" * 78)
print("CAB standalone modular (acct 262924445) — full W7 extraction")
print("=" * 78)
cab_m = extract_pairs('cab/ReportHistory-262924445.html', cab_strategy)
print(f"CAB W7 closed: n={len(cab_m)} WR={sum(1 for t in cab_m if t['pnl']>0)/max(1,len(cab_m))*100:.1f}% P&L=${sum(t['pnl'] for t in cab_m):.2f}")
print(f"  entries opened BEFORE W7 (not W7 decisions): {sum(1 for t in cab_m if t['t0']<W0)}")

c_strat = defaultdict(lambda: {'n':0,'wins':0,'sum':0.0,'vals':[]})
c_sym = defaultdict(lambda: {'n':0,'wins':0,'sum':0.0,'vals':[]})
c_sess_entry = defaultdict(lambda: {'n':0,'wins':0,'sum':0.0,'vals':[]})
c_exit = defaultdict(lambda: {'n':0,'wins':0,'sum':0.0,'vals':[]})
for t in cab_m:
    add(c_strat, t['bot'], t['pnl'], 1 if t['pnl'] > 0 else 0)
    add(c_sym, t['symbol'], t['pnl'], 1 if t['pnl'] > 0 else 0)
    add(c_sess_entry, session_of(t['t0']), t['pnl'], 1 if t['pnl'] > 0 else 0)
    ec = t['exit_c'] if t['exit_c'] else 'BROKER_SL/TP'
    add(c_exit, ec[:22], t['pnl'], 1 if t['pnl'] > 0 else 0)
tab(c_strat, "per-strategy (P&L $)")
tab(c_sym, "per-symbol (P&L $)")
tab(c_sess_entry, "per ENTRY session (P&L $)")
tab(c_exit, "per exit reason (P&L $)")

# ================= 3. CAB_MULTI_PAIR — ledger (R native) =================
print("\n" + "=" * 78)
print("CAB_MULTI_PAIR (acct 260714012) — ledger, R-multiples native")
print("=" * 78)
mp = []
with open('cab_multi_pair/cab_performance_ledger.csv', encoding='utf-8', errors='ignore') as f:
    for r in csv.DictReader(f):
        try: ct = datetime.strptime(r['CloseTime'], '%Y-%m-%d %H:%M:%S')
        except Exception: continue
        if W0 <= ct < W1:
            mp.append(dict(r, ct=ct))
print(f"CAB_MULTI_PAIR W7 closed: n={len(mp)}")

m_exit = defaultdict(lambda: {'n':0,'wins':0,'sum':0.0,'vals':[]})
m_sym = defaultdict(lambda: {'n':0,'wins':0,'sum':0.0,'vals':[]})
m_dir = defaultdict(lambda: {'n':0,'wins':0,'sum':0.0,'vals':[]})
m_open_sess = defaultdict(lambda: {'n':0,'wins':0,'sum':0.0,'vals':[]})
for r in mp:
    rv = float(r['Realized_R'])
    add(m_exit, r['ExitReason'], rv, 1 if rv > 0 else 0)
    add(m_sym, r['Symbol'], rv, 1 if rv > 0 else 0)
    add(m_dir, r['Direction'], rv, 1 if rv > 0 else 0)
    try: ot = datetime.strptime(r['OpenTime'], '%Y-%m-%d %H:%M:%S')
    except Exception: continue
    add(m_open_sess, session_of(ot), rv, 1 if rv > 0 else 0)
tab(m_exit, "per-exit (R)", min_n=2)
tab(m_sym, "per-symbol (R)", min_n=2)
tab(m_dir, "per-direction (R)", min_n=2)
tab(m_open_sess, "per OPEN session (R)", min_n=2)

# MFE/MAE decomposition (RB004 angle)
print("\n--- MFE/MAE decomposition (multi_pair W7) ---")
for k, key in (('by symbol', 'Symbol'), ('by exit', 'ExitReason')):
    agg = defaultdict(lambda: {'n':0, 'mfe':0.0, 'mae':0.0, 'R':0.0, 'mfe_cap':0.0})
    for r in mp:
        a = agg[r[key]]
        a['n'] += 1
        a['mfe'] += float(r['MFE_Peak_R']); a['mae'] += float(r['MAE_Trough_R'])
        a['R'] += float(r['Realized_R'])
        mfe = float(r['MFE_Peak_R']); fin = float(r['Realized_R'])
        a['mfe_cap'] += (fin / mfe) if mfe > 0 else 0
    print(f"\n  {k}:")
    print(f"  {'bucket':<16}{'n':>4}{'avgMFE':>8}{'avgMAE':>8}{'avgR':>7}{'MFEcapture':>11}")
    for b, a in sorted(agg.items(), key=lambda kv: -kv[1]['R']):
        if a['n'] < 2: continue
        print(f"  {b:<16}{a['n']:>4}{a['mfe']/a['n']:>8.2f}{a['mae']/a['n']:>8.2f}"
              f"{a['R']/a['n']:>7.2f}{a['mfe_cap']/a['n']:>11.2f}")

# ================= 4. UNIFIED cross-bot pattern matrix =================
print("\n" + "=" * 78)
print("UNIFIED cross-bot pattern matrix (W7, Sep 1-5)")
print("=" * 78)

def add_uni(dict_, k, bot, val, win, n_inc=1):
    dict_.setdefault(k, {})[bot] = dict_.get(k, {}).get(bot, {'n':0,'wins':0,'sum':0.0})
    d = dict_[k][bot]; d['n'] += n_inc; d['wins'] += win; d['sum'] += val

# unified by symbol
uni_sym = {}
for sym, (n, pnl, wins) in cab_s_verified.items():
    add_uni(uni_sym, sym, 'CAB_SUPER', pnl, wins, n_inc=n)
for t in cab_m: add_uni(uni_sym, t['symbol'], 'CAB', t['pnl'], 1 if t['pnl']>0 else 0)
for r in mp: add_uni(uni_sym, r['Symbol'], 'CAB_MULTI', float(r['Realized_R']), 1 if float(r['Realized_R'])>0 else 0)
print(f"\n{'SYMBOL':<12}{'CAB_SUPER $':<24}{'CAB $':<24}{'CAB_MULTI R':<22}")
for k in sorted(uni_sym):
    row = uni_sym[k]; parts = []
    for b in ['CAB_SUPER', 'CAB', 'CAB_MULTI']:
        d = row.get(b)
        if not d or d['n'] == 0: parts.append(f"{'--':>14}")
        else: parts.append(f"n={d['n']} wr={d['wins']/d['n']*100:.0f}% {d['sum']:>7.2f}")
    print(f"{k:<12}{parts[0]:<24}{parts[1]:<24}{parts[2]:<22}")

# ================= 5. Statistical best/worst cohorts =================
print("\n" + "=" * 78)
print("STATISTICAL BEST / WORST cohorts (two-sided t-test vs 0)")
print("=" * 78)
cohorts("CAB (modular) by strategy", cab_m, lambda t: t['pnl'], lambda t: t['bot'])
cohorts("CAB (modular) by symbol", cab_m, lambda t: t['pnl'], lambda t: t['symbol'])
cohorts("CAB_MULTI by symbol (R)", mp, lambda t: float(t['Realized_R']), lambda t: t['Symbol'])
cohorts("CAB_MULTI by exit (R)", mp, lambda t: float(t['Realized_R']), lambda t: t['ExitReason'])
cohorts("CAB_MULTI by open-session (R)", mp, lambda t: float(t['Realized_R']), lambda t: session_of(datetime.strptime(t['OpenTime'], '%Y-%m-%d %H:%M:%S')))

# ================= 6. Per-bot scoreboard =================
print("\n" + "=" * 78)
print("FINAL SCOREBOARD (W7 closed, Sep 1-5)")
print("=" * 78)
print(f"{'Bot':<18}{'n':>5}{'WR':>8}{'P&L':>12}{'avg/trade':>10}")
print(f"{'CAB_SUPER (verified)':<18}{48:>5}{27.1:>7.1f}%{85.50:>12.2f}{1.78:>10.2f}")
for name, trades, pnl_fn in (("CAB (modular)", cab_m, lambda t: t['pnl']),
                             ("CAB_MULTI (R)", mp, lambda t: float(t['Realized_R']))):
    n = len(trades)
    if n == 0: continue
    vals = [pnl_fn(t) for t in trades]
    wr = sum(1 for v in vals if v > 0) / n
    print(f"{name:<18}{n:>5}{wr*100:>7.1f}%{sum(vals):>12.2f}{sum(vals)/n:>10.3f}")

# ================= 7. Cross-bot convergence test =================
print("\n" + "=" * 78)
print("CROSS-BOT CONVERGENCE — same-symbol, same-week sign agreement")
print("=" * 78)
for k in sorted(uni_sym):
    row = uni_sym[k]
    bots = [b for b in ('CAB_SUPER', 'CAB', 'CAB_MULTI') if b in row and row[b]['n'] >= 3]
    if len(bots) < 2: continue
    signs = {b: 'POS' if row[b]['sum'] > 0 else 'NEG' for b in bots}
    agree = len(set(signs.values())) == 1
    print(f"  {k:<12} " + " ".join(f"{b}={signs[b]}(n{row[b]['n']},${row[b]['sum']:.2f})" for b in bots)
          + ("  AGREE" if agree else "  CONFLICT"))