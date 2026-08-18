# V2 Complete Trade Analysis (Aug 2026)

This analysis accurately parses closed POSITIONS from the HTML report to calculate final net PnL and trades per bot.

## Overall V2 Performance
- **Total V2 Closed Trades**: 369
- **Net V2 PnL**: $-82.86

## PnL Breakdown by Bot Engine
### CAB_INV_V2
- **Total Trades**: 103
- **Net PnL**: $133.94

**By Symbol:**
- **XAUUSDm**: 10 trades | PnL: $56.69
- **BTCUSDm**: 13 trades | PnL: $-4.02
- **ETHUSDm**: 10 trades | PnL: $1.89
- **USTECm**: 6 trades | PnL: $49.25
- **USOILm**: 8 trades | PnL: $38.89
- **EURUSDm**: 11 trades | PnL: $-1.07
- **GBPUSDm**: 9 trades | PnL: $0.11
- **USDJPYm**: 10 trades | PnL: $-6.81
- **XAGUSDm**: 9 trades | PnL: $-1.70
- **EURGBPm**: 7 trades | PnL: $0.52
- **AUDNZDm**: 10 trades | PnL: $0.19

### G_REV_V2
- **Total Trades**: 241
- **Net PnL**: $-198.83

**By Symbol:**
- **XAUUSDm**: 241 trades | PnL: $-198.83

### G_SCL_V2
- **Total Trades**: 23
- **Net PnL**: $-14.81

**By Symbol:**
- **XAUUSDm**: 23 trades | PnL: $-14.81

### CAB_REV_CLOSE_V2
- **Total Trades**: 1
- **Net PnL**: $-0.19

**By Symbol:**
- **EURGBPm**: 1 trades | PnL: $-0.19

### G_CACHE_V2
- **Total Trades**: 1
- **Net PnL**: $-2.97

**By Symbol:**
- **XAUUSDm**: 1 trades | PnL: $-2.97

---

# V2 Next Week Plan (Parity Phase)

1. **Clean Data Collection Run**: Let both V1 and V2 run concurrently in their isolated terminals throughout the week.
2. **Knowledge Register Edge Validation**: Build a standalone analysis script to parse `v2_knowledge_state.json` (or the historical DB if we archive it). This will unlock deep analytics like TradeThesis entry conviction vs R-multiple returns without relying on MT5 HTML reports.
3. **V2 Configuration Extraction**: Separate V2's config (including Terminal Path, Login, Pass) into a dedicated `v2/config/config.json` file as requested, ensuring V2 doesn't rely on system defaults.
4. **Pyramiding/Scale-In Testing**: Observe Ghost 204 Grid behavior and CAB multi-layer execution in the V2 environment to ensure dynamic lot sizing matches V1 to the cent.
