import json
from datamodel import OrderDepth, TradingState, Order
from typing import List

class Trader:

    def run(self, state: TradingState):
        result = {}
        
        for product in state.order_depths:
            # We are only focusing on Pepper Root for this combined strategy
            if product != "INTARIAN_PEPPER_ROOT":
                continue 

            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            # Get current position (defaults to 0)
            position = state.position.get(product, 0)
            
            if len(order_depth.sell_orders) != 0 and len(order_depth.buy_orders) != 0:
                best_ask = min(order_depth.sell_orders.keys())
                best_bid = max(order_depth.buy_orders.keys())

                # ---------------------------------------------------------
                # PHASE A: Accumulate & Market Make (Skewed Long)
                # ---------------------------------------------------------
                
                # We want to buy up to our absolute limit of +80
                max_buy_volume = 80 - position
                
                # We ONLY want to sell what we already own. We NEVER go short.
                max_sell_volume = -max(position, 5) 
                
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
                    
                # Because of our skew, this will only trigger if we have a >0 position
                if max_sell_volume < 0:
                    orders.append(Order(product, my_ask, max_sell_volume))

            result[product] = orders

        # Serialize state for the next timestamp (empty here as this specific strat is stateless)
        traderData = "" 
        conversions = 0

        return result, conversions, traderData