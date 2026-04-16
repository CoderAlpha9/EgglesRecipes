import json
import math
from datamodel import OrderDepth, TradingState, Order
from typing import List

class Trader:
    
    def run(self, state: TradingState):
        result = {}
        
        # 1. State Tracker for Osmium MACD
        try:
            trader_state = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            trader_state = {}

        if "OSMIUM" not in trader_state:
            trader_state["OSMIUM"] = {
                "ema_fast": 0.0,
                "ema_slow": 0.0,
                "ticks": 0
            }

        # MACD Parameters
        alpha_fast = 0.1
        alpha_slow = 0.02
        macd_normalization_factor = 2.0 # Adjusts how sensitive the volume skew is to MACD

        for product in state.order_depths:
            if product == "ASH_COATED_OSMIUM":
                order_depth: OrderDepth = state.order_depths[product]
                orders: List[Order] = []
                
                if len(order_depth.sell_orders) == 0 or len(order_depth.buy_orders) == 0:
                    continue

                best_bid = max(order_depth.buy_orders.keys())
                best_ask = min(order_depth.sell_orders.keys())
                tick_mid = (best_bid + best_ask) / 2.0
                
                # --- UPDATE MACD ---
                ts = trader_state["OSMIUM"]
                if ts["ticks"] == 0:
                    ts["ema_fast"] = tick_mid
                    ts["ema_slow"] = tick_mid
                else:
                    ts["ema_fast"] = (alpha_fast * tick_mid) + ((1 - alpha_fast) * ts["ema_fast"])
                    ts["ema_slow"] = (alpha_slow * tick_mid) + ((1 - alpha_slow) * ts["ema_slow"])
                
                ts["ticks"] += 1
                
                macd_raw = ts["ema_fast"] - ts["ema_slow"]
                
                # Normalize MACD to a signal between -1.0 and 1.0
                trend_signal = max(-1.0, min(1.0, macd_raw / macd_normalization_factor))

                # --- SUPPORT / RESISTANCE OVERRIDES ---
                # If we hit the known bounds, ignore the MACD and prepare for the reversal
                if best_ask >= 10020:
                    trend_signal = -1.0  # Force maximum selling behavior
                elif best_bid <= 9980:
                    trend_signal = 1.0   # Force maximum buying behavior

                # --- ASYMMETRIC VOLUME MULTIPLIERS ---
                buy_multiplier = 1.0
                sell_multiplier = 1.0
                
                if trend_signal > 0:
                    # Uptrend: Choke sell volume to avoid getting run over
                    sell_multiplier = max(0.0, 1.0 - trend_signal)
                elif trend_signal < 0:
                    # Downtrend: Choke buy volume
                    buy_multiplier = max(0.0, 1.0 + trend_signal)

                # --- INVENTORY MANAGEMENT & LIMITS ---
                position = state.position.get(product, 0)
                max_buy_volume = 80 - position
                max_sell_volume = -80 - position
                
                # Inventory Skew (shifts prices to naturally offload extreme positions)
                pos_ratio = position / 80.0
                price_skew = int(round(pos_ratio * 1.5)) # Shifts quotes down if long, up if short
                
                # --- PENNYING EXECUTION ---
                # Quote 1 tick inside the spread, adjusted by our inventory skew
                my_bid = best_bid + 1 - price_skew
                my_ask = best_ask - 1 - price_skew
                
                # Safety checks
                if my_bid >= my_ask:
                    my_bid = best_bid
                    my_ask = best_ask
                
                # Prevent crossing the actual market due to extreme inventory skew
                my_bid = min(my_bid, best_ask - 1)
                my_ask = max(my_ask, best_bid + 1)

                # --- APPLY VOLUME SKEW AND PLACE ORDERS ---
                quoted_buy_vol = int(max_buy_volume * buy_multiplier)
                quoted_sell_vol = int(max_sell_volume * sell_multiplier)

                if quoted_buy_vol > 0:
                    orders.append(Order(product, my_bid, quoted_buy_vol))
                    
                if quoted_sell_vol < 0:
                    orders.append(Order(product, my_ask, quoted_sell_vol))

                result[product] = orders

        # Serialize state
        traderData = json.dumps(trader_state)
        conversions = 0
        return result, conversions, traderData