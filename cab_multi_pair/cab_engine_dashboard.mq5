//+------------------------------------------------------------------+
//|                                       CAB_Engine_Dashboard.mq5   |
//|  Role: Python Heartbeat Monitor & Visual Dashboard               |
//|  Usage: Attach to ONE chart only to monitor the Python engine.   |
//+------------------------------------------------------------------+
#property version   "18.60"
#property strict

input group "System Bridge"
input int      InpHeartbeatDeadSec  = 60;
input string   InpHeartbeatFile     = "cab_heartbeat.txt";

long g_last_diff = 0;
long g_time_offset = 0; 
bool g_is_calibrated = false;

int OnInit() {
    EventSetTimer(1);
    Print("--- CAB DASHBOARD INITIALIZED ---");
    return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) { 
    EventKillTimer(); 
    Comment(""); // Clears the chart text when removed
}

void OnTimer() { 
    CheckHeartbeat(); 
    bool isOnline = (g_last_diff < InpHeartbeatDeadSec && g_is_calibrated);
    UpdateDashboard(isOnline);
}

void CheckHeartbeat() {
    // FILE_SHARE_WRITE is maintained so Python is never blocked from writing
    int handle = FileOpen(InpHeartbeatFile, FILE_READ|FILE_TXT|FILE_COMMON|FILE_ANSI|FILE_SHARE_READ|FILE_SHARE_WRITE);
    if(handle != INVALID_HANDLE) {
        string ts_raw = "";
        while(!FileIsEnding(handle)) ts_raw += FileReadString(handle);
        FileClose(handle);
        
        StringTrimLeft(ts_raw);
        StringTrimRight(ts_raw);
        
        long heartbeatTS = (long)StringToInteger(ts_raw);
        if(heartbeatTS > 0) {
            long currentSystemTime = (long)TimeLocal();
            if(!g_is_calibrated) {
                g_time_offset = currentSystemTime - heartbeatTS;
                g_is_calibrated = true;
            }
            g_last_diff = MathAbs((currentSystemTime - heartbeatTS) - g_time_offset);
        }
    }
}

void UpdateDashboard(bool online) {
    string status = online ? "✅ PYTHON ENGINE ONLINE" : "❌ PYTHON ENGINE OFFLINE (Check .bat script!)";
    Comment("=================================\n",
            "       CAB MASTER v18.6\n",
            "=================================\n",
            "Status: ", status, "\n",
            "Last Pulse: ", g_last_diff, "s ago\n",
            "=================================");
}