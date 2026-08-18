import sys
original_order_send = None

def patch_mt5():
    global original_order_send
    import MetaTrader5 as mt5
    original_order_send = mt5.order_send
    
    def hooked_order_send(request):
        print(f"HOOKED ORDER_SEND: {request}")
        return original_order_send(request)
        
    mt5.order_send = hooked_order_send

# Let's just modify the mt5_gateway.py directly!
