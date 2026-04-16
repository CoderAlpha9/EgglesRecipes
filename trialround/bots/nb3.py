import json
from datamodel import OrderDepth, TradingState, Order
from typing import List

class Trader:
    
    def run(self, state: TradingState):
        result = {}
        
        # 1. Load our saved state to track the EMA and its derivative
        try:
            trader_state = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            trader_state = {}

        if "TOMATOES" not in trader_state:
            trader_state["TOMATOES"] = {
                "ema_mid": 0.0,
                "prev_ema": 0.0,
                "smoothed_velocity": 0.0,
                "ticks": 0
            }

        # Smoothing factors
        alpha_ema = 0.1 
        alpha_vel = 0.1 # Smoothing for the derivative
        max_expected_velocity = 0.005 # Threshold for max trend strength

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

            # 3. Update Tracking Mean & Momentum
            ts = trader_state["TOMATOES"]
            if ts["ticks"] == 0:
                ts["ema_mid"] = tick_mid
                ts["prev_ema"] = tick_mid
                ts["smoothed_velocity"] = 0.0
            else:
                ts["prev_ema"] = ts["ema_mid"]
                ts["ema_mid"] = (alpha_ema * tick_mid) + ((1 - alpha_ema) * ts["ema_mid"])
                
                # Calculate Derivative (Velocity)
                raw_velocity = ts["ema_mid"] - ts["prev_ema"]
                ts["smoothed_velocity"] = (alpha_vel * raw_velocity) + ((1 - alpha_vel) * ts["smoothed_velocity"])

            ts["ticks"] += 1
            mean_price = ts["ema_mid"]
            velocity = ts["smoothed_velocity"]

            # 4. Asymmetric Volume Skew Calculation
            # Normalize velocity into a skew factor clamped between -1.0 and 1.0
            skew_factor = max(-1.0, min(1.0, velocity / max_expected_velocity))
            
            buy_multiplier = 1.0
            sell_multiplier = 1.0
            
            if skew_factor > 0:
                # Uptrend (+ve derivative): Choke sell volume to avoid getting run over
                sell_multiplier = 1.0 - skew_factor
                buy_multiplier = 1.0 + skew_factor
            elif skew_factor < 0:
                # Downtrend (-ve derivative): Choke buy volume to avoid catching a falling knife
                sell_multiplier = 1.0 - skew_factor
                buy_multiplier = 1.0 + skew_factor # skew_factor is negative, so this correctly reduces from 1.0

            # 5. Calculate absolute allowable limits
            position = state.position.get(product, 0)
            max_buy_volume = 80 - position
            max_sell_volume = -80 - position
            
            # 6. PHASE A: The Mean-Reversion Exit (UNTOUCHED)
            # We do NOT apply multipliers here. Exiting risk uses full available limits.
            available_bid_vol = order_depth.buy_orders[best_bid]
            available_ask_vol = -order_depth.sell_orders[best_ask]

            if position > 0 and best_bid >= mean_price - 1:
                dump_vol = max(max_sell_volume, -min(position, available_bid_vol)) 
                if dump_vol < 0:
                    orders.append(Order(product, best_bid, dump_vol))
                    max_sell_volume -= dump_vol
            
            if position < 0 and best_ask <= mean_price + 1:
                cover_vol = min(max_buy_volume, min(-position, available_ask_vol)) 
                if cover_vol > 0:
                    orders.append(Order(product, best_ask, cover_vol))
                    max_buy_volume -= cover_vol

            # 7. PHASE B: Aggressive "Pennying" with ADVERSE SELECTION PROTECTION
            my_bid = best_bid + 1
            my_ask = best_ask - 1
            
            if my_bid >= my_ask:
                my_bid = best_bid
                my_ask = best_ask

            # Apply momentum multipliers to the REMAINING allowable volume
            quoted_buy_vol = int(max_buy_volume * buy_multiplier // 2)
            quoted_sell_vol = int(max_sell_volume * sell_multiplier // 2)

            if quoted_buy_vol > 0:
                orders.append(Order(product, my_bid, quoted_buy_vol))
                
            if quoted_sell_vol < 0:
                orders.append(Order(product, my_ask, quoted_sell_vol))

            result[product] = orders

        # Serialize state for the next timestamp
        traderData = json.dumps(trader_state)
        conversions = 0
        return result, conversions, traderData