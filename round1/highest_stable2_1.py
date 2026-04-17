import json
import math
from datamodel import OrderDepth, TradingState, Order
from typing import List

class Trader:
    # Added missing dictionary referenced in the loop
    POSITION_LIMITS = {
        "ASH_COATED_OSMIUM": 80,
        "INTARIAN_PEPPER_ROOT": 80
    }

    def run(self, state: TradingState):
        result = {}
        conversions = 0
        
        trader_state = {
            "OSMIUM_STATE": {},
            "PEPPER_STATE": {}
        }
        
        if state.traderData:
            try:
                loaded_state = json.loads(state.traderData)
                trader_state.update(loaded_state)
            except Exception:
                pass

        for product in state.order_depths:
            if product not in self.POSITION_LIMITS:
                continue

            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            if len(order_depth.sell_orders) == 0 or len(order_depth.buy_orders) == 0:
                continue

            # Safely parse the order book
            sorted_bids = sorted(order_depth.buy_orders.items(), key=lambda x: x[0], reverse=True)
            sorted_asks = sorted(order_depth.sell_orders.items(), key=lambda x: x[0])
            
            best_bid, best_bid_vol = sorted_bids[0]
            best_ask, best_ask_vol = sorted_asks[0]
            best_ask_vol = -best_ask_vol 
            
            mid_price = (best_bid + best_ask) / 2.0
            current_pos = state.position.get(product, 0)
            limit = self.POSITION_LIMITS.get(product, 80)
                
            # ---------------------------------------------------------
            # STRATEGY 1: ASH_COATED_OSMIUM (EMA20 + Market Making)
            # ---------------------------------------------------------
            if product == "ASH_COATED_OSMIUM":
                
                # --- 1. EMA20 Fair Price Tracker ---
                alpha = 2 / (20 + 1)
                
                if "ema20" not in trader_state["OSMIUM_STATE"]:
                    trader_state["OSMIUM_STATE"]["ema20"] = mid_price
                    
                prev_ema = trader_state["OSMIUM_STATE"]["ema20"]
                ema20 = (alpha * mid_price) + ((1 - alpha) * prev_ema)
                trader_state["OSMIUM_STATE"]["ema20"] = ema20
                
                fair_price = ema20

                # --- 2. Inventory Neutralization (Taking Liquidity) ---
                # If we are long and the market is bidding higher than our fair price, sell to neutralize.
                if current_pos > 0 and best_bid > fair_price:
                    dump_vol = min(current_pos, best_bid_vol)
                    if dump_vol > 0:
                        orders.append(Order(product, best_bid, -dump_vol))
                        current_pos -= dump_vol  # Update position for the next phase
                        
                # If we are short and the market is asking lower than our fair price, buy to neutralize.
                elif current_pos < 0 and best_ask < fair_price:
                    cover_vol = min(abs(current_pos), best_ask_vol)
                    if cover_vol > 0:
                        orders.append(Order(product, best_ask, cover_vol))
                        current_pos += cover_vol # Update position for the next phase

                # --- 3. Constant Market Making (Pennying) ---
                # Recalculate available capacities based on updated position
                max_buy_volume = limit - current_pos
                max_sell_volume = -(limit + current_pos)
                
                # Quote 1 tick inside the current spread
                my_bid = best_bid + 1
                my_ask = best_ask - 1
                
                # Safety check: Fall back to joining the best quotes if the spread is too tight
                if my_bid >= my_ask:
                    my_bid = best_bid
                    my_ask = best_ask
                    
                # Place resting maker orders
                if max_buy_volume > 0:
                    orders.append(Order(product, my_bid, max_buy_volume))
                    
                if max_sell_volume < 0:
                    orders.append(Order(product, my_ask, max_sell_volume))
                    
            # ---------------------------------------------------------
            # STRATEGY 2: INTARIAN_PEPPER_ROOT (Unchanged)
            # ---------------------------------------------------------
            elif product == "INTARIAN_PEPPER_ROOT":
            
                if "prev_ask" not in trader_state["PEPPER_STATE"]:
                    trader_state["PEPPER_STATE"]["prev_ask"] = best_ask
                    
                prev_ask = trader_state["PEPPER_STATE"]["prev_ask"]
                trader_state["PEPPER_STATE"]["prev_ask"] = best_ask

                # PHASE A: Accumulation
                max_buy_volume = 80 - current_pos
                if max_buy_volume > 0:
                    
                    is_spike = best_ask > prev_ask
                    
                    if not is_spike:
                        orders.append(Order(product, best_ask, max_buy_volume))
                    else:
                        my_bid = best_bid + 1
                        if my_bid >= best_ask:
                            my_bid = best_bid
                            
                        orders.append(Order(product, my_bid, max_buy_volume))

            result[product] = orders

        traderData = json.dumps(trader_state)
        return result, conversions, traderData