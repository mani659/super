import os

with open('v2/bots/supertrend_bot.py', 'a', encoding='utf-8') as f:
    f.write('''
    def _session_allowed(self) -> bool:
        if not self.config.session_gate_enabled:
            return True
        if self.config.symbol not in self.config.session_gate_pairs:
            return True
        hour = datetime.utcnow().hour
        # Assume session logic from V1 if any, or just return True for now
        return True

    def calculate_position_size(self, stop_loss_points: float) -> float:
        """V2.3 strict mathematical port for position sizing using shared utils."""
        sym_info = self.gateway.symbol_info(self.config.symbol)
        if not sym_info:
            return 0.01
            
        sl_price_dist = stop_loss_points * sym_info.point
        
        return calculate_dynamic_lot(
            gateway=self.gateway,
            symbol=self.config.symbol,
            risk_percent=self.config.risk_percent,
            sl_dist_price=sl_price_dist,
            max_lot_demo_cap=None
        )

    def execute_cycle(self, df: pd.DataFrame, current_dd: float, max_dd: float):
        if not self._session_allowed():
            return False

        signal_dir = self.generate_signal(df)
        if signal_dir is None:
            return False

        sym_info = self.gateway.symbol_info(self.config.symbol)
        tick = self.gateway.symbol_info_tick(self.config.symbol)
        if not sym_info or not tick:
            return False

        snapshot = self.kr.get_market_state(self.config.symbol, "M30")
        if not snapshot:
            return False

        supertrends, optimal_factor = self._get_supertrends_cached(df)
        current_st = supertrends[min(supertrends.keys(), key=lambda x: abs(x - optimal_factor))]
        st_line = float(current_st["output"].iloc[-1])
        
        if signal_dir == 1:
            order_type = mt5.ORDER_TYPE_BUY
            fill_price = tick.ask
            sl_points = abs(fill_price - st_line) / sym_info.point
        else:
            order_type = mt5.ORDER_TYPE_SELL
            fill_price = tick.bid
            sl_points = abs(fill_price - st_line) / sym_info.point

        volume = self.calculate_position_size(sl_points)
        sl_price = round(st_line, sym_info.digits)

        ts = TradeSignal(
            symbol=self.config.symbol,
            bot_name="SuperTrendBotV2",
            magic_number=self.config.magic_number,
            order_type=order_type,
            sl_price=sl_price
        )
        
        if self.router.route_signal(ts, current_dd, max_dd):
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.config.symbol,
                "volume": volume,
                "type": order_type,
                "price": fill_price,
                "sl": sl_price,
                "tp": 0.0,
                "deviation": 20,
                "magic": self.config.magic_number,
                "comment": "ST_V2",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            res = self.gateway.order_send(req)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"Executed ST_V2 {self.config.symbol} | Ticket {res.order}")
                # Build and register Trade Thesis
                thesis = TradeThesis(
                    ticket=res.order,
                    symbol=self.config.symbol,
                    direction=signal_dir,
                    bot_name="SuperTrendBotV2",
                    magic_number=self.config.magic_number,
                    timeframe="M30",
                    initial_sl=sl_price,
                    initial_tp=0.0,
                    entry_atr=snapshot.atr_raw,
                    regime_at_entry=snapshot.regime,
                    entry_conviction=snapshot.adx_raw,
                    layer_depth=0,
                    timestamp=time.time(),
                    market_snapshot=snapshot
                )
                self.kr.register_trade_thesis(thesis)
                return True
        return False
''')
