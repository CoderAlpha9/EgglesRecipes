from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List

class Trader:
    # Defining position limits as a class variable 
    # (Adjust these if the specific round details mandate different limits)
    POSITION_LIMITS = {
        "EMERALDS": 80,
        "TOMATOES": 80
    }

    def run(self, state: TradingState):
        """
        Takes all buy and sell orders for all symbols as an input, 
        and outputs a list of orders to be sent.
        """
        result = {}
        conversions = 0
        traderData = state.traderData

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            # Fetch current position to ensure we do not breach limits
            current_position = state.position.get(product, 0)
            limit = self.POSITION_LIMITS.get(product, 0)

            # Ensure there is liquidity on both sides to calculate logic safely
            if len(order_depth.sell_orders) != 0 and len(order_depth.buy_orders) != 0:
                
                # Best prices currently available in the order book
                best_ask = min(order_depth.sell_orders.keys())
                best_bid = max(order_depth.buy_orders.keys())
                
                if product == "EMERALDS":
                    fair_value = 10000
                    
                    # 1. Market Taking: Execute immediately if prices cross our fair value
                    if best_ask < fair_value:
                        # order_depth.sell_orders[best_ask] is negative, so we negate it
                        buy_volume = min(-order_depth.sell_orders[best_ask], limit - current_position)
                        if buy_volume > 0:
                            orders.append(Order(product, best_ask, buy_volume))
                            current_position += buy_volume
                            
                    if best_bid > fair_value:
                        # order_depth.buy_orders[best_bid] is positive, we want a negative volume to sell
                        sell_volume = max(-order_depth.buy_orders[best_bid], -limit - current_position)
                        if sell_volume < 0:
                            orders.append(Order(product, best_bid, sell_volume))
                            current_position += sell_volume

                    # 2. Market Making: Place resting orders to capture the spread
                    if current_position < limit:
                        orders.append(Order(product, 9998, limit - current_position))
                    if current_position > -limit:
                        orders.append(Order(product, 10002, -limit - current_position))

                elif product == "TOMATOES":
                    # Simple mid-price market making for the trending asset
                    mid_price = (best_bid + best_ask) / 2
                    
                    # Calculate bid and ask prices slightly off the mid-price
                    my_bid = int(mid_price) - 1
                    my_ask = int(mid_price) + 1
                    
                    # Place orders filling up our remaining position limit capacity
                    if current_position < limit:
                        orders.append(Order(product, my_bid, limit - current_position))
                    if current_position > -limit:
                        orders.append(Order(product, my_ask, -limit - current_position))

            result[product] = orders

        return result, conversions, traderData