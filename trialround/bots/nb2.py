import json
import math
from datamodel import OrderDepth, TradingState, Order
from typing import List

class Trader:
    
    def run(self, state: TradingState):
        result = {}
        
        # 1. State Tracker (Upgraded to include avg_spread)
        try:
            trader_state = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            trader_state = {}

        if "TOMATOES" not in trader_state:
            trader_state["TOMATOES"] = {
                "ema_mid": 0.0,
                "avg_spread": 0.0, # NEW: Track spread width
                "ticks": 0
            }

        alpha = 0.1 

        for product in state.order_depths:
            if product != "TOMATOES":
                continue
                
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            if len(order_depth.sell_orders) == 0 or len(order_depth.buy_orders) == 0:
                continue

            # 2. Extract current market conditions
            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            tick_mid = (best_bid + best_ask) / 2.0
            tick_spread = best_ask - best_bid
            
            # 3. Update our Tracking Mean & Spread
            ts = trader_state["TOMATOES"]
            if ts["ticks"] == 0:
                ts["ema_mid"] = tick_mid
                ts["avg_spread"] = tick_spread
            else:
                ts["ema_mid"] = (alpha * tick_mid) + ((1 - alpha) * ts["ema_mid"])
                ts["avg_spread"] = (alpha * tick_spread) + ((1 - alpha) * ts["avg_spread"])
                
            ts["ticks"] += 1
            mean_price = ts["ema_mid"]
            avg_spread = ts["avg_spread"]

            # 4. Strictly calculate allowable limits
            position = state.position.get(product, 0)
            max_buy_volume = 80 - position
            max_sell_volume = -80 - position
            
            # 5. PHASE A: The Mean-Reversion Exit (Preserved with Volume Checks)
            if position > 0 and best_bid >= mean_price - 1:
                available_bid_vol = order_depth.buy_orders[best_bid]
                dump_vol = max(max_sell_volume, -min(position, available_bid_vol)) 
                if dump_vol < 0:
                    orders.append(Order(product, best_bid, dump_vol))
                    max_sell_volume -= dump_vol
            
            if position < 0 and best_ask <= mean_price + 1:
                available_ask_vol = -order_depth.sell_orders[best_ask]
                cover_vol = min(max_buy_volume, min(-position, available_ask_vol)) 
                if cover_vol > 0:
                    orders.append(Order(product, best_ask, cover_vol))
                    max_buy_volume -= cover_vol

            # ==============================================================
            # 6. PHASE B: Quadratic Spread Grid (UPGRADED)
            # ==============================================================
            
            if max_buy_volume > 0 or max_sell_volume < 0:
                # Calculate how many levels to quote (half the spread width, minimum 3 to see the curve)
                num_levels = max(3, int(round(avg_spread / 2.0)))
                
                # Pre-calculate quadratic weights (i^2)
                weights = [(i + 1)**2 for i in range(num_levels)]
                total_w = sum(weights)
                
                base_bid = int(math.floor(mean_price))
                base_ask = int(math.ceil(mean_price))
                
                bid_dict = {}
                ask_dict = {}
                
                # --- DISTRIBUTE BIDS (Quadratically scaling outward) ---
                if max_buy_volume > 0:
                    allocated_buy = 0
                    for i in range(num_levels):
                        # Ensure rounding errors don't leave remaining volume
                        if i == num_levels - 1:
                            v = max_buy_volume - allocated_buy 
                        else:
                            v = int(max_buy_volume * (weights[i] / total_w))
                            
                        allocated_buy += v
                        
                        if v > 0:
                            # Price logic: step further below the mean
                            p = base_bid - i
                            
                            # Safety boundary: never cross the existing ask
                            p = min(p, best_ask - 1)
                            
                            # Add to dict (combines volume if boundary squishes levels together)
                            bid_dict[p] = bid_dict.get(p, 0) + v

                    for p, v in bid_dict.items():
                        orders.append(Order(product, p, v))

                # --- DISTRIBUTE ASKS (Quadratically scaling outward) ---
                if max_sell_volume < 0:
                    total_sell_abs = abs(max_sell_volume)
                    allocated_sell = 0
                    for i in range(num_levels):
                        if i == num_levels - 1:
                            v = total_sell_abs - allocated_sell
                        else:
                            v = int(total_sell_abs * (weights[i] / total_w))
                            
                        allocated_sell += v
                        
                        if v > 0:
                            # Price logic: step further above the mean
                            p = base_ask + i
                            
                            # Safety boundary: never cross the existing bid
                            p = max(p, best_bid + 1)
                            
                            ask_dict[p] = ask_dict.get(p, 0) - v # Sells are negative

                    for p, v in ask_dict.items():
                        orders.append(Order(product, p, v))

            result[product] = orders

        # Serialize state for the next timestamp
        traderData = json.dumps(trader_state)
        conversions = 0
        return result, conversions, traderData