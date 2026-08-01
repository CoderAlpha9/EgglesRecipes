import json
import math
from datamodel import OrderDepth, TradingState, Order
from typing import List

class Trader:

    def run(self, state: TradingState):
        result = {}
        conversions = 0
        
        # 1. State Management
        try:
            trader_state = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            trader_state = {}

        if "TOMATOES" not in trader_state:
            trader_state["TOMATOES"] = {
                "robust_mid": 0.0,
                "avg_spread": 0.0,
                "ema_bid": 0.0,  # Added: Independent Bid tracking
                "ema_ask": 0.0,  # Added: Independent Ask tracking
                "ticks": 0
            }

        # Strategy Hyperparameters
        alpha_mid = 0.1     
        alpha_spread = 0.05 
        anomaly_threshold = 0.15 
        alpha_asym = 0.15   # Added: Speed of the independent Bid/Ask EMAs

        for product in state.order_depths:
            if product != "TOMATOES":
                continue
                
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            if len(order_depth.sell_orders) == 0 or len(order_depth.buy_orders) == 0:
                continue

            # Extract top of book safely
            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            
            tick_mid = (best_bid + best_ask) / 2.0
            tick_spread = best_ask - best_bid
            
            ts = trader_state["TOMATOES"]
            
            # 2. Update Robust Tracking Metrics & Asymmetric EMAs
            if ts["ticks"] == 0:
                ts["robust_mid"] = tick_mid
                ts["avg_spread"] = tick_spread
                ts["ema_bid"] = best_bid  # Initialize
                ts["ema_ask"] = best_ask  # Initialize
            else:
                # Core trackers for Anomaly Sniping
                ts["robust_mid"] = (alpha_mid * tick_mid) + ((1 - alpha_mid) * ts["robust_mid"])
                ts["avg_spread"] = (alpha_spread * tick_spread) + ((1 - alpha_spread) * ts["avg_spread"])
                
                # Independent tracking for Passive Quoting
                ts["ema_bid"] = (alpha_asym * best_bid) + ((1 - alpha_asym) * ts["ema_bid"])
                ts["ema_ask"] = (alpha_asym * best_ask) + ((1 - alpha_asym) * ts["ema_ask"])
                
            ts["ticks"] += 1
            
            robust_mid = ts["robust_mid"]
            avg_spread = ts["avg_spread"]
            ema_bid = ts["ema_bid"]
            ema_ask = ts["ema_ask"]
            
            # Ensure minimum viable spread
            avg_spread = max(2.0, avg_spread)

            # 3. Position Limits
            current_pos = state.position.get(product, 0)
            buy_cap = 80 - current_pos
            sell_cap = -80 - current_pos 

            # -------------------------------------------------------------
            # 4. Phase A: Aggressive Anomaly Sniping (UNTOUCHED)
            # -------------------------------------------------------------
            buy_trigger_price = robust_mid + (avg_spread * anomaly_threshold)
            sell_trigger_price = robust_mid - (avg_spread * anomaly_threshold)

            # Check if current Ask has crashed into the trigger zone
            if best_ask <= buy_trigger_price and buy_cap > 0:
                buy_vol = min(buy_cap, -order_depth.sell_orders[best_ask])
                if buy_vol > 0:
                    orders.append(Order(product, best_ask, buy_vol))
                    buy_cap -= buy_vol
                    current_pos += buy_vol

            # Check if current Bid has spiked into the trigger zone
            if best_bid >= sell_trigger_price and sell_cap < 0:
                sell_vol = max(sell_cap, -order_depth.buy_orders[best_bid])
                if sell_vol < 0:
                    orders.append(Order(product, best_bid, sell_vol))
                    sell_cap -= sell_vol
                    current_pos -= sell_vol

            # -------------------------------------------------------------
            # 5. Phase B: Passive Mean-Reversion / Unloading (UPGRADED)
            # -------------------------------------------------------------
            
            # Mild inventory skew to prevent drifting into max limits
            skew = (current_pos / 80.0) * (avg_spread * 0.2)
            
            # NEW: Replaced robust_mid spread calculation with independent EMAs
            ideal_bid = int(round(ema_bid - skew))
            ideal_ask = int(round(ema_ask - skew))

            # SAFETY LIMIT: Ensure independent EMAs never cross our own spread
            if ideal_bid >= ideal_ask:
                ideal_bid = ideal_ask - 1

            # Do not place passive orders more aggressively than the current market
            my_bid = min(ideal_bid, best_ask - 1)
            my_ask = max(ideal_ask, best_bid + 1)

            # Submit passive resting orders
            if buy_cap > 0:
                orders.append(Order(product, my_bid, buy_cap))
            if sell_cap < 0:
                orders.append(Order(product, my_ask, sell_cap))

            result[product] = orders

        traderData = json.dumps(trader_state)
        return result, conversions, traderData