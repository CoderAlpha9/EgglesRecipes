import json
from datamodel import OrderDepth, TradingState, Order
from typing import List

class Trader:

    def run(self, state: TradingState):
        result = {}
        
        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            # 1. Get current position for the product (defaults to 0)
            position = state.position.get(product, 0)
            
            # Ensure there is liquidity on both sides of the book before calculating spread
            if len(order_depth.sell_orders) != 0 and len(order_depth.buy_orders) != 0:
                best_ask = min(order_depth.sell_orders.keys())
                best_bid = max(order_depth.buy_orders.keys())
                
                # ---------------------------------------------------------
                # STRATEGY 1: ASH_COATED_OSMIUM (Aggressive Market Making)
                # ---------------------------------------------------------
                if product == "ASH_COATED_OSMIUM":
                    # Calculate allowable volume to stay within the +/- 80 limit
                    max_buy_volume = 80 - position
                    max_sell_volume = -80 - position
                    
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
                        
                # ---------------------------------------------------------
                # STRATEGY 2: INTARIAN_PEPPER_ROOT (Accumulate & Liquidate)
                # ---------------------------------------------------------
                # if product == "INTARIAN_PEPPER_ROOT":
                #     # Define the timestamp where we stop buying and start liquidating
                #     liquidation_threshold = 99000
                    
                #     if state.timestamp < liquidation_threshold:
                #         # PHASE A: Accumulation
                #         # Buy as much long as possible up to the limit of 80
                #         max_buy_volume = 80 - position
                #         if max_buy_volume > 0:
                #             # Aggressively take the best ask to guarantee fills
                #             orders.append(Order(product, best_ask, max_buy_volume))
                #     else:
                #         # PHASE B: Liquidation
                #         # Sell off the entire long position to realize profit before day ends
                #         if position > 0:
                #             # Hit the best bid to guarantee execution
                #             orders.append(Order(product, best_bid, -position))

                if product == "INTARIAN_PEPPER_ROOT":
                    # PHASE A: Accumulation
                    # Buy as much long as possible up to the limit of 80
                    max_buy_volume = 80 - position
                    
                    # Sort the asks from lowest price to highest price to ensure we get the best deals first
                    sorted_asks = sorted(order_depth.sell_orders.items())
                    
                    for ask_price, ask_vol in sorted_asks:
                        if max_buy_volume <= 0:
                            break  # We hit our position limit, stop walking the book
                            
                        # Resting sell volumes are negative, so negate them to get the absolute available liquidity
                        available_vol = -ask_vol
                        
                        # Calculate how much we can actually take at this level
                        buy_qty = min(max_buy_volume, available_vol)
                        
                        if buy_qty > 0:
                            orders.append(Order(product, ask_price, buy_qty))
                            max_buy_volume -= buy_qty
                
                # if product == "INTARIAN_PEPPER_ROOT":
                #     # Calculate allowable volume to stay within the +/- 80 limit
                #     max_buy_volume = 80 - position
                #     max_sell_volume = -80 - position
                    
                #     # Pennying: Quote 1 tick inside the current spread
                #     my_bid = best_bid + 1
                #     my_ask = best_ask - 1
                    
                #     # Safety check: Fall back to joining the best quotes if the spread is too tight
                #     if my_bid >= my_ask:
                #         my_bid = best_bid
                #         my_ask = best_ask
                        
                #     # Place resting orders
                #     if max_buy_volume > 0:
                #         orders.append(Order(product, my_bid, max_buy_volume))
                        
                #     if max_sell_volume < 0:
                #         orders.append(Order(product, my_ask, max_sell_volume))

            result[product] = orders

        # Serialize state for the next timestamp (empty here as this strat is stateless)
        traderData = "" 
        conversions = 0

        return result, conversions, traderData