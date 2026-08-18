import MetaTrader5 as mt5
from datetime import datetime

def main():
    if not mt5.initialize():
        print(f"initialize() failed, error code = {mt5.last_error()}")
        return

    account_info = mt5.account_info()
    if account_info!=None:
        print(f"equity={account_info.equity} balance={account_info.balance}")
    else:
        print("Failed to get account info")

    # For Task 2, getting history Aug 11 to Aug 15 2026
    # Let's get it as dataframe and save to csv/html
    date_from = datetime(2026, 8, 11)
    date_to = datetime(2026, 8, 16) # up to end of 15th
    history_deals = mt5.history_deals_get(date_from, date_to)
    
    if history_deals != None and len(history_deals) > 0:
        import pandas as pd
        df = pd.DataFrame(list(history_deals), columns=history_deals[0]._asdict().keys())
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.to_html("week4_history.html")
        print("Exported week4_history.html")
    else:
        print("No history deals found or failed to get history")
        
    mt5.shutdown()

if __name__ == '__main__':
    main()
