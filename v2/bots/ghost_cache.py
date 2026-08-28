"""
GhostCache — Virtual Grid Layer Tracker
========================================
Magic 204: Pure ghost cache exhaustion entry

WHAT QUESTION THIS ANSWERS (and how we know when we're done):
─────────────────────────────────────────────────────────────
  Q: Does waiting for the nth virtual exhaustion layer before firing a
     mean-reversion entry produce better outcomes than firing immediately
     at first retraction from probe (magic 202)?

  MEASURE: avg_R and win_rate per magic after 30+ fills each (same probes,
           different entry timing). Data decides — not theory.

  DECISION MATRIX (non-negotiable, checked after 2-week demo):
  ┌────────────────────────────────────────────┬────────────────────────────┐
  │ Outcome                                    │ Decision                   │
  ├────────────────────────────────────────────┼────────────────────────────┤
  │ 204 avg_R > 202 avg_R by >20%             │ Replace 202 with 204 in P4 │
  │ 204 ≈ 202 (within 20%)                    │ Keep both, tune by regime  │
  │ 204 avg_R < 202 avg_R                     │ Kill 204, keep 202          │
  │ 204 fires <10 times in 2 weeks            │ n too high → lower to n=2  │
  │ 204 fires >6 times per day                │ n too low → raise to n=4   │
  └────────────────────────────────────────────┴────────────────────────────┘

HOW 204 DIFFERS FROM 202:
─────────────────────────────────────────────────────────────
  202 fires at the FIRST retraction from probe extreme.
      → Aggressive, frequent, low conviction

  204 fires only AFTER:
      1. Price extends to nth virtual layer BEYOND probe extreme (exhaustion)
      2. THEN price retraces back through the (n-1)th layer (confirmation)
      → Patient, rare, high conviction

  They never compete for the same entry — 202 fires first, 204 fires later
  if the probe extends further. Both can be live simultaneously.

  Visual:
        ▲                         ← nth layer (exhaustion)
        │  ←──── invalidation zone (trend, not exhaustion)
        ▲                         ← nth layer (fire zone upper boundary)
        │
        ▲  [204 ENTRY HERE]       ← (n-1)th layer retrace triggers entry
        ▲                         ← (n-1)th layer
        │
        ▲  [202 ENTRY HERE]       ← 1st retraction from probe (existing)
        │
        ●  ← probe_extreme
        │
        ●  ← probe_origin

INTEGRATION INTO ghost_sniper_v5_1.py:
─────────────────────────────────────────────────────────────
  # After existing 201/202 trigger block, BEFORE armed = None reset:
  if armed is not None:
      if ghost_cache is None:
          ghost_cache = GhostCache(
              probe_direction=armed,
              probe_origin=break_level,     # price before probe
              probe_extreme=probe_extreme,
              atr_step=dynamic_step,
              n_layers=N_LAYERS_DEFAULT,
          )

      signal = ghost_cache.update(current_price, atr)
      if signal:
          send_order(
              mt5.ORDER_TYPE_SELL if signal['order_type'] == 'SELL' else mt5.ORDER_TYPE_BUY,
              signal['sl'], 0.0,
              MAGIC_GHOST_CACHE, 'SNIPER_GC',
              atr, armed, 'GHOST_CACHE', bs, gates,
          )
          log_event('GHOST_CACHE_FIRE', {
              **signal,
              'atr_at_fill':   round(atr, 5),
              'regime_at_fill': bs.get('regime', ''),
          })

  # Reset ghost_cache when probe resets (armed = None):
  if armed is None and ghost_cache is not None:
      ghost_cache = None

WATCHER PERSONALITY FOR 204 (in sniper_watcher_v3_1.py):
─────────────────────────────────────────────────────────────
  manage_204_ghost_cache() — grid-state aware exits ONLY:
    TP: combined P&L reaches +1R on first-layer risk → close all 204 legs
    Stop: combined P&L reaches -3R → close all 204 legs immediately
    No per-position reaper — that is the entire point being tested

  This is identical to the GridWatcher rebuild (gh-gw task) but as
  a personality function in the existing dispatch table.

LOGGING COLUMNS TO ADD TO AUDIT CSV:
─────────────────────────────────────────────────────────────
  virtual_layer_depth   - n at time of fire (tune n from this)
  probe_origin_dist     - total move from probe origin to nth layer
  cache_age_seconds     - how long cache was active before firing
  max_layer_reached     - deepest virtual layer touched (even if no fire)
"""

from dataclasses import dataclass, field
from typing import Optional
import time


# ─────────────────────────────────────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

# V1 Week 6 configuration: Lowered to 2 to increase fire rate after Week 5 zero fires
N_LAYERS_DEFAULT      = 2    # Start here. Tune from data after 30+ fills.
                             # n=2: fires more often, less exhaustion evidence
                             # n=3: balanced — start here
                             # n=4: fires rarely, very high conviction required

SL_ATR_BUFFER         = 0.5  # SL = nth_layer_price ± 0.5×ATR (Slab C Grace)
                             # Wide enough to survive the liquidity sweep that
                             # always happens at extreme levels on Gold.

CACHE_INVALIDATION_N  = 2    # If price reaches (n + 2) layers, this is a trend.
                             # Reset cache. Do not fire. Accept we missed it.

MAX_CACHE_AGE_SECONDS = 300  # 5 minutes max. After this, ATR step is stale
                             # and the virtual layer prices are wrong.

MAGIC_GHOST_CACHE     = 204  # New magic number — isolated from 201/202


# ─────────────────────────────────────────────────────────────────────────────
#  GHOST CACHE
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GhostCache:
    """
    Virtual grid layer tracker. Pure Python, zero MT5 dependency.
    Instantiate on ARMED. Call update() every loop tick.
    Returns entry signal dict when fire condition met, else None.

    One GhostCache instance per probe. Reset to None when probe resets.
    """

    probe_direction: str    # "UP_PROBE" | "DOWN_PROBE"
    probe_origin:    float  # price level at which probe was first detected
    probe_extreme:   float  # furthest point reached — updated dynamically
    atr_step:        float  # grid step size = 1.0 × ATR at time of arming
    n_layers:        int    = N_LAYERS_DEFAULT

    # Runtime state — do not set at construction
    max_layer_touched:  int   = field(default=0,     init=False)
    entry_fired:        bool  = field(default=False,  init=False)
    invalidated:        bool  = field(default=False,  init=False)
    created_at:         float = field(default_factory=time.time, init=False)
    _initial_extreme:   float = field(default=0.0,   init=False, repr=False)

    def __post_init__(self):
        # Lock the layer anchor at construction time.
        # probe_extreme updates dynamically as price extends (for SL and invalidation),
        # but virtual layer PRICES must be fixed — otherwise layers shift with price
        # and can never be "reached" in a stable way.
        self._initial_extreme = self.probe_extreme

    # ── Layer price helpers ───────────────────────────────────────────────────

    def _layer_price(self, index: int) -> float:
        """
        Price of the nth virtual layer. Anchored to _initial_extreme (FIXED).

        UP_PROBE:   layers extend ABOVE initial probe extreme (ascending)
                    Fire direction = SELL (mean reversion back down)

        DOWN_PROBE: layers extend BELOW initial probe extreme (descending)
                    Fire direction = BUY (mean reversion back up)

        WHY FIXED: if we anchored to dynamic probe_extreme, the layer prices
        would shift upward every time price made a new high, making layers
        permanently unreachable. The virtual grid is placed at the moment
        of arming and stays there.
        """
        if self.probe_direction == "UP_PROBE":
            return self._initial_extreme + (index * self.atr_step)
        else:
            return self._initial_extreme - (index * self.atr_step)

    @property
    def nth_layer_price(self) -> float:
        """The decisive exhaustion level. Fire condition: price touched this."""
        return self._layer_price(self.n_layers)

    @property
    def retrace_level(self) -> float:
        """
        Entry trigger: price must retrace THROUGH this level after touching nth.
        This is the (n-1)th layer — one step back toward the origin.
        """
        return self._layer_price(self.n_layers - 1)

    @property
    def invalidation_level(self) -> float:
        """Trend continuation threshold. If reached → cache is dead."""
        return self._layer_price(self.n_layers + CACHE_INVALIDATION_N)

    @property
    def sl_price(self) -> float:
        """
        SL for the real entry. Anchored at nth layer ± 0.5×ATR buffer.
        The nth layer is the furthest known point of the probe — SL must sit
        beyond it or it will be hit immediately on any residual momentum.
        """
        buffer = self.atr_step * SL_ATR_BUFFER
        if self.probe_direction == "UP_PROBE":
            return self.nth_layer_price + buffer   # SELL entry → SL above
        else:
            return self.nth_layer_price - buffer   # BUY entry  → SL below

    # ── Core update ───────────────────────────────────────────────────────────

    def update(self, current_price: float, current_atr: float) -> Optional[dict]:
        """
        Call every loop tick. Returns entry signal dict or None.

        The signal dict contains everything needed by send_order() and
        the audit CSV logging columns.
        """
        if self.entry_fired or self.invalidated:
            return None

        # Stale cache guard — ATR step becomes wrong over time
        if time.time() - self.created_at > MAX_CACHE_AGE_SECONDS:
            self.invalidated = True
            return None

        # Update probe extreme as price continues
        if self.probe_direction == "UP_PROBE":
            self.probe_extreme = max(self.probe_extreme, current_price)
        else:
            self.probe_extreme = min(self.probe_extreme, current_price)

        # Invalidation check — price has extended too far, this is a trend
        if self._price_reached(current_price, self.invalidation_level):
            self.invalidated = True
            return None

        # Track deepest virtual layer touched
        for i in range(1, self.n_layers + 1):
            if self._price_reached(current_price, self._layer_price(i)):
                self.max_layer_touched = max(self.max_layer_touched, i)

        # Fire condition: nth layer touched AND price has retracted through (n-1)th
        if (self.max_layer_touched >= self.n_layers
                and self._price_retracted(current_price, self.retrace_level)):
            self.entry_fired = True
            return {
                'order_type':          'SELL' if self.probe_direction == 'UP_PROBE' else 'BUY',
                'sl':                   self.sl_price,
                'tp':                   0.0,  # Fluid TP — watcher owns all exits
                'virtual_layer_depth':  self.max_layer_touched,
                'probe_origin_dist':    abs(self.nth_layer_price - self.probe_origin),
                'cache_age_seconds':    round(time.time() - self.created_at, 1),
            }

        return None

    def _price_reached(self, current: float, target: float) -> bool:
        if self.probe_direction == "UP_PROBE":
            return current >= target
        return current <= target

    def _price_retracted(self, current: float, level: float) -> bool:
        """Price has come BACK through the level (opposite direction to probe)."""
        if self.probe_direction == "UP_PROBE":
            return current < level   # was going up, now fell below (n-1)th
        return current > level       # was going down, now rose above (n-1)th

    # ── Logging ───────────────────────────────────────────────────────────────

    def status(self) -> dict:
        """Call every cycle for debug logging regardless of fire state."""
        return {
            'direction':          self.probe_direction,
            'probe_extreme':      round(self.probe_extreme, 3),
            'nth_layer':          round(self.nth_layer_price, 3),
            'retrace_level':      round(self.retrace_level, 3),
            'invalidation':       round(self.invalidation_level, 3),
            'sl':                 round(self.sl_price, 3),
            'max_layer_touched':  self.max_layer_touched,
            'fired':              self.entry_fired,
            'invalidated':        self.invalidated,
            'age_s':              round(time.time() - self.created_at, 1),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  UNIT TESTS  — run before wiring to MT5
# ─────────────────────────────────────────────────────────────────────────────

def run_unit_tests() -> bool:
    """
    10 scenarios. ALL must pass. Do not wire into Hunter until green.
    """
    print("=" * 55)
    print("GhostCache unit tests — run before wiring to MT5")
    print("=" * 55)
    passed = 0

    # T1: UP_PROBE — nth layer price is correct
    c = GhostCache("UP_PROBE", 2000.0, 2010.0, 2.0, n_layers=3)
    assert abs(c.nth_layer_price - 2016.0) < 0.001, f"T1 FAIL nth={c.nth_layer_price}"
    print("T1 PASS  UP_PROBE nth layer price = 2016.0")
    passed += 1

    # T2: DOWN_PROBE — nth layer price is correct
    c = GhostCache("DOWN_PROBE", 2000.0, 1990.0, 2.0, n_layers=3)
    assert abs(c.nth_layer_price - 1984.0) < 0.001, f"T2 FAIL nth={c.nth_layer_price}"
    print("T2 PASS  DOWN_PROBE nth layer price = 1984.0")
    passed += 1

    # T3: No fire before nth layer is touched
    c = GhostCache("UP_PROBE", 2000.0, 2010.0, 2.0, n_layers=3)
    result = c.update(2014.0, 2.0)  # only 2nd layer (2014.0) reached
    assert result is None,          f"T3 FAIL fired too early: {result}"
    assert c.max_layer_touched == 2, f"T3 FAIL layer count: {c.max_layer_touched}"
    print("T3 PASS  No signal before nth layer touched")
    passed += 1

    # T4: nth layer touched but no retrace yet → no signal
    c = GhostCache("UP_PROBE", 2000.0, 2010.0, 2.0, n_layers=3)
    c.update(2016.5, 2.0)          # touches nth (2016.0)
    result = c.update(2015.5, 2.0) # above retrace_level (2014.0) → no fire
    assert result is None,          f"T4 FAIL fired before retrace: {result}"
    print("T4 PASS  nth touched, above retrace level — no signal yet")
    passed += 1

    # T5: UP_PROBE full fire sequence
    c = GhostCache("UP_PROBE", 2000.0, 2010.0, 2.0, n_layers=3)
    c.update(2016.5, 2.0)           # nth layer touched
    r = c.update(2013.5, 2.0)       # retraced below (n-1)th = 2014.0
    assert r is not None,            f"T5 FAIL no signal"
    assert r['order_type'] == 'SELL',f"T5 FAIL direction {r['order_type']}"
    assert r['virtual_layer_depth'] == 3
    print(f"T5 PASS  UP_PROBE SELL fired | SL={r['sl']:.3f}")
    passed += 1

    # T6: DOWN_PROBE full fire sequence
    c = GhostCache("DOWN_PROBE", 2000.0, 1990.0, 2.0, n_layers=3)
    c.update(1983.5, 2.0)           # nth layer touched (1984.0)
    r = c.update(1986.5, 2.0)       # retrace above (n-1)th = 1986.0
    assert r is not None,            f"T6 FAIL no signal"
    assert r['order_type'] == 'BUY', f"T6 FAIL direction {r['order_type']}"
    print(f"T6 PASS  DOWN_PROBE BUY fired | SL={r['sl']:.3f}")
    passed += 1

    # T7: Invalidation — trend extension kills cache
    c = GhostCache("UP_PROBE", 2000.0, 2010.0, 2.0, n_layers=3)
    c.update(2016.5, 2.0)           # nth layer
    c.update(2020.5, 2.0)           # (n+2)th = 2010 + 5×2 = 2020 → invalidate
    r = c.update(2013.0, 2.0)       # retrace attempt after invalidation
    assert r is None,                f"T7 FAIL fired after invalidation"
    assert c.invalidated,            "T7 FAIL not marked invalidated"
    print("T7 PASS  Cache invalidated on trend extension")
    passed += 1

    # T8: No double fire
    c = GhostCache("UP_PROBE", 2000.0, 2010.0, 2.0, n_layers=3)
    c.update(2016.5, 2.0)
    r1 = c.update(2013.5, 2.0)
    r2 = c.update(2013.0, 2.0)
    assert r1 is not None,           "T8 FAIL first fire missed"
    assert r2 is None,               "T8 FAIL double fire"
    print("T8 PASS  No double fire after entry")
    passed += 1

    # T9: SL geometry — UP_PROBE SL sits ABOVE nth layer
    c = GhostCache("UP_PROBE", 2000.0, 2010.0, 2.0, n_layers=3)
    expected = 2016.0 + (0.5 * 2.0)  # nth_layer + 0.5×atr_step = 2017.0
    assert abs(c.sl_price - expected) < 0.001, f"T9 FAIL sl={c.sl_price} expected={expected}"
    print(f"T9 PASS  UP_PROBE SL above nth layer = {c.sl_price:.3f}")
    passed += 1

    # T10: SL geometry — DOWN_PROBE SL sits BELOW nth layer
    c = GhostCache("DOWN_PROBE", 2000.0, 1990.0, 2.0, n_layers=3)
    expected = 1984.0 - (0.5 * 2.0)  # nth_layer - 0.5×atr_step = 1983.0
    assert abs(c.sl_price - expected) < 0.001, f"T10 FAIL sl={c.sl_price} expected={expected}"
    print(f"T10 PASS DOWN_PROBE SL below nth layer = {c.sl_price:.3f}")
    passed += 1

    print("=" * 55)
    print(f"Results: {passed}/10 tests passed")
    if passed == 10:
        print("ALL GREEN — safe to wire into Hunter")
    else:
        print("FAILURES — fix before wiring to Hunter")
    print("=" * 55)
    return passed == 10


if __name__ == "__main__":
    run_unit_tests()
