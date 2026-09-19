# config.py
MAGIC_INVERSION = 9995551
MAGIC_CONTINUATION = 9995552
MAGIC_GRID = 9995553

SYMBOLS = ['XAUUSDm', 'BTCUSDm', 'ETHUSDm', 'USTECm', 'USOILm', 'EURUSDm', 'GBPUSDm', 'USDJPYm', 'EURGBPm', 'AUDNZDm']
TERMINAL_PATH = r"C:\Program Files\MetaTrader 5 EXNESS - Copy (2)\terminal64.exe"

ATR_PERIOD = 14
ATR_MULT_SL = 2.5
REWARD_MULTIPLIER = 2.0
RISK_PERCENT = 0.01

ENABLE_CONTINUATION = False  # Post-gate 13 Sep 2026: Cont entries disabled; manage_* still runs

# ── REAPER bailout tuning (fix-reaper-scale) ─────────────────────────────────
# The REAPER closes a losing trade (-0.5R) when the last closed H1 bar shows a
# reversal body. That body was being compared against the M15 ATR — a unit
# mismatch (an H1 body is typically ~2x an M15 ATR) — which made the gate nearly
# unreachable: over W4-W8 this bot logged 2 REAPER_FLIP kills against 54
# HARD_STOP exits (Sep-12 audit), i.e. the bailout effectively never ran.
# The comparison is now against the H1 ATR, at this fraction of it.
REAPER_BODY_ATR_FRACTION = 0.5

# ── Hard loss caps (fix-loss-cap) ────────────────────────────────────────────
# See shared_utils.enforce_loss_caps(). Measured on FLOATING loss, checked once
# per cycle, per symbol and across the whole book.
SYMBOL_LOSS_CAP_PCT    = 0.02
PORTFOLIO_LOSS_CAP_PCT = 0.05