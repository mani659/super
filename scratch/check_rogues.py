import MetaTrader5 as mt5
import os
import sys

# SuperTrend magic numbers from unified_runner.py
MAGIC_SUPERTREND = {101234, 201567, 301890, 401213, 402213, 403213, 404213, 405213, 406213, 407213, 408213}

TERMINALS = [
    r"C:\Program Files\MetaTrader 5 EXNESS - Copy\terminal64.exe",
    r"C:\Program Files\MetaTrader 5 EXNESS - Copy (2)\terminal64.exe"
]

def kill_rogue_trades():
    total_killed = 0
    
    for path in TERMINALS:
        print(f"\n==============================================")
        print(f"Scanning Terminal: {path}")
        
        if not mt5.initialize(path=path):
            print(f"[!] Failed to connect to MT5 at {path}. Code: {mt5.last_error()}")
            continue
            
        account_info = mt5.account_info()
        if not account_info:
            print(f"[!] No account logged in on this terminal.")
            mt5.shutdown()
            continue
            
        print(f"[*] Connected. Account: {account_info.login} | Balance: {account_info.balance}")
        
        positions = mt5.positions_get()
        if positions is None:
            print(f"[*] No open positions found.")
            mt5.shutdown()
            continue
            
        killed_on_this = 0
        for pos in positions:
            if pos.magic in MAGIC_SUPERTREND:
                print(f"[X] ROGUE FOUND: Ticket #{pos.ticket} | Symbol: {pos.symbol} | Magic: {pos.magic} | Volume: {pos.volume}")
                
                # Close the rogue trade
                order_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(pos.symbol).bid if order_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(pos.symbol).ask
                
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": pos.symbol,
                    "volume": pos.volume,
                    "type": order_type,
                    "position": pos.ticket,
                    "price": price,
                    "deviation": 20,
                    "magic": pos.magic,
                    "comment": "Rogue Hijack Close",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                
                result = mt5.order_send(request)
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    print(f"    -> SUCCESSFULLY CLOSED Ticket #{pos.ticket}")
                    killed_on_this += 1
                    total_killed += 1
                else:
                    err = result.comment if result else mt5.last_error()
                    print(f"    -> FAILED TO CLOSE Ticket #{pos.ticket}. Error: {err}")
            
        if killed_on_this == 0:
            print(f"[*] Terminal is clean. No SuperTrend magic numbers found.")
            
        mt5.shutdown()
        
    print(f"\n==============================================")
    print(f"Scan Complete. Total rogue trades killed: {total_killed}")

if __name__ == "__main__":
    kill_rogue_trades()
