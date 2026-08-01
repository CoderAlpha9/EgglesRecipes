import json
from datamodel import OrderDepth, TradingState, Order
from typing import List

class Trader:
    POSITION_LIMITS = {
        "ASH_COATED_OSMIUM": 80,
        "INTARIAN_PEPPER_ROOT": 80
    }

    def run(self, state: TradingState):

        result = {}
        conversions = 0
        
        trader_state = {
            "OFI_STATE": {},  
            "OU_STATE": {},
            "BB_STATE": {},
            "PEPPER_STATE": {}
        }
        
        if state.traderData:
            try:
                trader_state = json.loads(state.traderData)
            except Exception:
                pass

        for product in state.order_depths:
            # We only process Osmium and Pepper Root
            if product not in self.POSITION_LIMITS:
                continue

            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            if len(order_depth.sell_orders) == 0 or len(order_depth.buy_orders) == 0:
                continue

            sorted_bids = sorted(order_depth.buy_orders.items(), key=lambda x: x[0], reverse=True)
            sorted_asks = sorted(order_depth.sell_orders.items(), key=lambda x: x[0])
            
            best_bid, best_bid_vol = sorted_bids[0]
            best_ask, best_ask_vol = sorted_asks[0]
            best_ask_vol = -best_ask_vol 
            
            mid_price = (best_bid + best_ask) / 2.0

            current_pos = state.position.get(product, 0)
            limit = self.POSITION_LIMITS.get(product, 80)
            buy_cap = limit - current_pos
            sell_cap = limit + current_pos
                
            # ---------------------------------------------------------
            # STRATEGY 1: ASH_COATED_OSMIUM (Aggressive Market Making)
            # ---------------------------------------------------------
            if product == "ASH_COATED_OSMIUM":
                # Calculate allowable volume to stay within the +/- 80 limit
                max_buy_volume = 80 - current_pos
                max_sell_volume = -80 - current_pos
                
                # Pennying: Quote 1 tick inside the current spread
                my_bid = best_bid + 1
                my_ask = best_ask - 1
                
                # Safety check: Fall back to joining the best quotes if the spread is too tight
                if my_bid >= my_ask:
                    my_bid = best_bid
                    my_ask = best_ask
                    
                # Place resting orders
                if max_buy_volume > 0:
                    orders.append(Order(product, my_bid, max_buy_volume))
                    
                if max_sell_volume < 0:
                    orders.append(Order(product, my_ask, max_sell_volume))
                    
            elif product == "INTARIAN_PEPPER_ROOT":
            
                if "prev_ask" not in trader_state["PEPPER_STATE"]:
                    trader_state["PEPPER_STATE"]["prev_ask"] = best_ask
                    
                prev_ask = trader_state["PEPPER_STATE"]["prev_ask"]
                trader_state["PEPPER_STATE"]["prev_ask"] = best_ask

                # PHASE A: Accumulation
                max_buy_volume = 80 - current_pos
                if max_buy_volume > 0:
                    if not best_ask <= prev_ask:
                        # Price is stable or dropping -> safely take the ask
                        orders.append(Order(product, best_ask, max_buy_volume))
                    else:
                        # Price spiked (e.g. to 12010). Wait for it to drop. 
                        # Place a passive bid to accumulate cheaply (e.g. at 12006/12007)
                        my_bid = best_bid + 1
                        if my_bid >= best_ask:
                            my_bid = best_bid
                            
                        orders.append(Order(product, my_bid, max_buy_volume))

            result[product] = orders

        traderData = json.dumps(trader_state)
        conversions = 0

        return result, conversions, traderData