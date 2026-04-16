import json
from datamodel import OrderDepth, TradingState, Order
from typing import List

class Trader:
    
    def run(self, state: TradingState):
        result = {}
        
        # 1. Load our saved state to track the EMA (Mean)
        try:
            trader_state = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            trader_state = {}

        if "TOMATOES" not in trader_state:
            trader_state["TOMATOES"] = {
                "ema_mid": 0.0,
                "ticks": 0
            }

        # EMA smoothing factor
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

            available_bid_vol = order_depth.buy_orders[best_bid]
            available_ask_vol = -order_depth.sell_orders[best_ask]
            
            # 3. Update our Tracking Mean (EMA)
            ts = trader_state["TOMATOES"]
            if ts["ticks"] == 0:
                ts["ema_mid"] = tick_mid
            else:
                ts["ema_mid"] = (alpha * tick_mid) + ((1 - alpha) * ts["ema_mid"])
                
            ts["ticks"] += 1
            mean_price = ts["ema_mid"]

            # 4. Strictly calculate allowable limits
            position = state.position.get(product, 0)
            max_buy_volume = 80 - position
            max_sell_volume = -80 - position
            
            # 5. PHASE A: The Mean-Reversion Exit (Dumping Inventory)
            # If we are holding Longs and a Bid spikes up to/past our mean, we sell to exit
            if position > 0 and best_bid >= mean_price - 1:
                # Limit the dump volume to what is actually available at the best bid
                dump_vol = max(max_sell_volume, -min(position, available_bid_vol)) 
                if dump_vol < 0:
                    orders.append(Order(product, best_bid, dump_vol))
                    max_sell_volume -= dump_vol
            
            # If we are holding Shorts and an Ask troughs down to/past our mean, we buy to cover
            if position < 0 and best_ask <= mean_price + 1:
                # Limit the cover volume to what is actually available at the best ask (ask volumes are negative)
                cover_vol = min(max_buy_volume, min(-position, available_ask_vol)) 
                if cover_vol > 0:
                    orders.append(Order(product, best_ask, cover_vol))
                    max_buy_volume -= cover_vol

            # 6. PHASE B: Aggressive "Pennying" (Market Making inside the spread)
            # We want to be the best buyer and the best seller, pocketing the difference.
            
            my_bid = best_bid + 1
            my_ask = best_ask - 1
            
            # Safety check: If the spread is extremely tight (1 tick), our aggressive quotes 
            # might cross each other. If so, we fall back to joining the existing best prices.
            if my_bid >= my_ask:
                my_bid = best_bid
                my_ask = best_ask

            # Place resting orders with our remaining allowable volume
            if max_buy_volume > 0:
                orders.append(Order(product, my_bid, max_buy_volume))
                
            if max_sell_volume < 0:
                orders.append(Order(product, my_ask, max_sell_volume))

            result[product] = orders

        # Serialize state for the next timestamp
        traderData = json.dumps(trader_state)
        conversions = 0
        return result, conversions, traderData