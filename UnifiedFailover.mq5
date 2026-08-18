//+------------------------------------------------------------------+
//|                     UnifiedFailover.mq5                          |
//|  Single watchdog EA for all three bots — SuperTrend, Ghost Grid, |
//|  CAB Watcher. Monitors one Python heartbeat file. If Python dies  |
//|  it applies an ATR-based airbag trailing stop to ALL open         |
//|  positions across all 9 magic numbers.                           |
//|                                                                  |
//|  REPLACES: CAB_Unified.mq5 (entry logic moved to cab_entry.py)  |
//|                                                                  |
//|  SETUP:                                                          |
//|    1. Attach to ANY chart (one instance only)                    |
//|    2. Set HeartbeatFile to match config.json heartbeat.path      |
//|    3. All 9 magic numbers are hardcoded below — update if yours  |
//|       differ from defaults                                       |
//|                                                                  |
//|  MAGIC NUMBERS COVERED:                                          |
//|    SuperTrend : 101234, 201567, 301890, 401213                   |
//|    Ghost Grid : 201, 202, 203, 204                               |
//|    CAB Watcher: 999555                                           |
//+------------------------------------------------------------------+
#property version   "1.00"
#property strict
#include <Trade\Trade.mqh>

//--- INPUTS
input string   HeartbeatFile      = "cab_heartbeat.txt"; // Heartbeat filename
input int      WarnThresholdSec   = 60;    // Warn in chart comment after N sec
input int      FailoverThresholdSec = 120; // Activate airbag after N sec
input double   AirbagATRMult      = 5.0;  // Airbag SL = ATR × this
input int      ATRPeriod          = 14;    // ATR period for airbag SL
input bool     LogToFile          = true;  // Write failover events to log file

//--- All magic numbers under unified runner protection
//    Update these if you change magic numbers in config.json
const long MAGIC_NUMBERS[] = {
    101234, 201567, 301890, 401213,   // SuperTrend (legacy pairs)
    402213, 403213, 404213, 405213,   // SuperTrend (expanded pairs block 1)
    406213, 407213, 408213,           // SuperTrend (expanded pairs block 2)
    201, 202, 204,                    // Ghost Grid legs
    999555                            // CAB Watcher
};

//--- Globals
CTrade  trade;
long    g_last_heartbeat_diff = 0;
bool    g_failover_active     = false;
bool    g_warned              = false;
string  g_log_file            = "unified_failover.log";

//--- fix-atrhandle: cached ATR indicator handles, one per symbol.
//    Previously _RunAirbag() called iATR()+CopyBuffer()+IndicatorRelease()
//    fresh EVERY 5-second cycle for EVERY managed position — i.e. repeatedly
//    creating and destroying indicator handles during exactly the scenario
//    (Python already crashed) where you want the least additional failure
//    surface. MQL5 has a per-terminal indicator handle limit; this avoids
//    hammering it during what could be an extended unattended failover.
string g_atr_symbols[];
int    g_atr_handles[];

//+------------------------------------------------------------------+
int OnInit() {
    EventSetTimer(5);   // check heartbeat every 5 seconds
    Comment("UnifiedFailover: ONLINE | Watching ", ArraySize(MAGIC_NUMBERS),
            " magic numbers");
    _Log("EA started — monitoring " + IntegerToString(ArraySize(MAGIC_NUMBERS))
         + " magic numbers");
    return INIT_SUCCEEDED;
}

void OnDeinit(const int reason) {
    EventKillTimer();
    // fix-atrhandle: release every cached handle on shutdown — without this
    // the cache defeats its own purpose by leaking handles across restarts.
    for(int i = 0; i < ArraySize(g_atr_handles); i++) {
        IndicatorRelease(g_atr_handles[i]);
    }
    ArrayResize(g_atr_symbols, 0);
    ArrayResize(g_atr_handles, 0);
    Comment("");
}

//+------------------------------------------------------------------+
void OnTimer() {
    _GuardNakedTrades();
    
    g_last_heartbeat_diff = _ReadHeartbeat();

    if(g_last_heartbeat_diff <= -999999) {
        // Heartbeat file missing entirely
        _SetComment("HEARTBEAT FILE MISSING — Python never started?");
        return;
    }

    if(g_last_heartbeat_diff <= WarnThresholdSec) {
        // All good — Python is alive
        if(g_failover_active) {
            _Log("Python reconnected after failover — airbag remains until SL hit");
        }
        g_failover_active = false;
        g_warned          = false;
        _SetComment("ONLINE | Last Python pulse: " +
                    IntegerToString((int)g_last_heartbeat_diff) + "s ago");
        return;
    }

    if(g_last_heartbeat_diff <= FailoverThresholdSec) {
        // Warning zone — Python is slow / stalling
        if(!g_warned) {
            _Log("WARNING: Python heartbeat " +
                 IntegerToString((int)g_last_heartbeat_diff) + "s ago — monitoring");
            g_warned = true;
        }
        _SetComment("WARNING: Python silent " +
                    IntegerToString((int)g_last_heartbeat_diff) +
                    "s | Failover in " +
                    IntegerToString((int)(FailoverThresholdSec - g_last_heartbeat_diff)) + "s");
        return;
    }

    // ── FAILOVER ACTIVE ───────────────────────────────────────────────────────
    if(!g_failover_active) {
        _Log("FAILOVER ACTIVATED — Python offline " +
             IntegerToString((int)g_last_heartbeat_diff) + "s | Applying airbag SL");
        g_failover_active = true;
    }

    _SetComment("FAILOVER ACTIVE | Python offline " +
                IntegerToString((int)g_last_heartbeat_diff) +
                "s | ATR airbag trailing ALL positions");

    _RunAirbag();
}

//+------------------------------------------------------------------+
//  AIRBAG — apply ATR-based trailing SL to all managed positions
//+------------------------------------------------------------------+
void _RunAirbag() {
    int total = PositionsTotal();
    for(int i = 0; i < total; i++) {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(!_IsManagedMagic(PositionGetInteger(POSITION_MAGIC))) continue;

        string sym   = PositionGetString(POSITION_SYMBOL);
        int    ptype = (int)PositionGetInteger(POSITION_TYPE);

        // fix-atrhandle: reuse a cached handle for this symbol instead of
        // creating a fresh one every cycle for every position.
        int atr_handle = _GetATRHandle(sym);
        if(atr_handle == INVALID_HANDLE) continue;

        double atr_buf[];
        if(CopyBuffer(atr_handle, 0, 0, 1, atr_buf) < 1) {
            continue;   // handle stays cached — a transient CopyBuffer miss
                        // doesn't mean the handle itself is bad
        }

        double atr      = atr_buf[0];
        double sl_dist  = atr * AirbagATRMult;
        double curr_sl  = PositionGetDouble(POSITION_SL);

        double new_sl;
        if(ptype == POSITION_TYPE_BUY) {
            double bid = SymbolInfoDouble(sym, SYMBOL_BID);
            new_sl = bid - sl_dist;
            // Only trail upward (never widen SL on a buy)
            if(curr_sl != 0 && new_sl <= curr_sl) continue;
        } else {
            double ask = SymbolInfoDouble(sym, SYMBOL_ASK);
            new_sl = ask + sl_dist;
            // Only trail downward (never widen SL on a sell)
            if(curr_sl != 0 && new_sl >= curr_sl) continue;
        }

        // Stops-level guard
        long   stops_level = SymbolInfoInteger(sym, SYMBOL_TRADE_STOPS_LEVEL);
        double point       = SymbolInfoDouble(sym, SYMBOL_POINT);
        double stops_dist  = stops_level * point;
        double curr_price  = (ptype == POSITION_TYPE_BUY)
                             ? SymbolInfoDouble(sym, SYMBOL_BID)
                             : SymbolInfoDouble(sym, SYMBOL_ASK);

        if(MathAbs(new_sl - curr_price) < stops_dist) continue;

        // Modify
        if(trade.PositionModify(ticket, new_sl, PositionGetDouble(POSITION_TP))) {
            _Log("AIRBAG SL | #" + IntegerToString((int)ticket) +
                 " " + sym +
                 " | new_sl=" + DoubleToString(new_sl, (int)SymbolInfoInteger(sym, SYMBOL_DIGITS)) +
                 " | atr=" + DoubleToString(atr, (int)SymbolInfoInteger(sym, SYMBOL_DIGITS)));
        }
    }
}

//+------------------------------------------------------------------+
//  HELPERS
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//  _GuardNakedTrades — continuously scan for sl==0.0 and close >15s
//+------------------------------------------------------------------+
void _GuardNakedTrades() {
    int total = PositionsTotal();
    for(int i = 0; i < total; i++) {
        ulong ticket = PositionGetTicket(i);
        if(ticket == 0) continue;
        if(!_IsManagedMagic(PositionGetInteger(POSITION_MAGIC))) continue;

        double curr_sl = PositionGetDouble(POSITION_SL);
        if(curr_sl == 0.0) {
            long open_time = PositionGetInteger(POSITION_TIME);
            long diff = (long)TimeCurrent() - open_time;
            if(diff > 15) {
                _Log("NAKED TRADE FAILSAFE | #" + IntegerToString((int)ticket) + " | open >15s with no SL! Force closing.");
                trade.PositionClose(ticket);
            }
        }
    }
}


// fix-atrhandle: look up a cached ATR handle for `sym`, creating and
// caching one on first use. Returns INVALID_HANDLE if creation fails.
int _GetATRHandle(string sym) {
    for(int i = 0; i < ArraySize(g_atr_symbols); i++) {
        if(g_atr_symbols[i] == sym) {
            return g_atr_handles[i];
        }
    }
    int handle = iATR(sym, PERIOD_H1, ATRPeriod);
    if(handle == INVALID_HANDLE) {
        _Log("ATR handle creation FAILED for " + sym);
        return INVALID_HANDLE;
    }
    int n = ArraySize(g_atr_symbols);
    ArrayResize(g_atr_symbols, n + 1);
    ArrayResize(g_atr_handles, n + 1);
    g_atr_symbols[n] = sym;
    g_atr_handles[n] = handle;
    _Log("ATR handle cached for " + sym);
    return handle;
}

bool _IsManagedMagic(long magic) {
    int n = ArraySize(MAGIC_NUMBERS);
    for(int i = 0; i < n; i++) {
        if(MAGIC_NUMBERS[i] == magic) return true;
    }
    return false;
}

long _ReadHeartbeat() {
    int handle = INVALID_HANDLE;
    for(int i=0; i<3; i++) {
        handle = FileOpen(HeartbeatFile, FILE_READ | FILE_TXT | FILE_COMMON | FILE_ANSI | FILE_SHARE_READ | FILE_SHARE_WRITE);
        if(handle != INVALID_HANDLE) break;
        Sleep(50); // wait 50ms and try again
    }
    if(handle == INVALID_HANDLE) return -999999;   // file missing
    
    string ts_str = "";
    while(!FileIsEnding(handle)) ts_str += FileReadString(handle);
    FileClose(handle);
    
    StringTrimLeft(ts_str);
    StringTrimRight(ts_str);
    
    long ts = (long)StringToInteger(ts_str);
    if(ts == 0) return -999999;
    
    long diff = (long)TimeGMT() - ts;
    // Handle local clock drift where Python time is slightly ahead of MT5 server time
    if(diff < 0) diff = 0; 
    
    return diff;
}

void _SetComment(string msg) {
    Comment("UnifiedFailover: " + msg);
}

void _Log(string msg) {
    if(!LogToFile) return;
    int handle = FileOpen(g_log_file,
                          FILE_WRITE | FILE_READ | FILE_SHARE_READ | FILE_TXT | FILE_ANSI,
                          ',', CP_UTF8);
    if(handle == INVALID_HANDLE) return;
    FileSeek(handle, 0, SEEK_END);
    FileWriteString(handle,
        TimeToString(TimeLocal(), TIME_DATE | TIME_SECONDS) + " | " + msg + "\n");
    FileClose(handle);
}

//+------------------------------------------------------------------+
void OnTick() {
    // Tick handler intentionally empty — all logic runs on timer
    // OnTimer fires every 5s regardless of tick activity
}
