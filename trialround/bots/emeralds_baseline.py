from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List

class Trader:
    
    def run(self, state: TradingState):
        """Only method required. It takes all buy and sell orders for all
        symbols as an input, and outputs a list of orders to be sent."""

        result = {}
        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            if product == "EMERALDS":
                # 1. Check our current inventory for EMERALDS (defaults to 0)
                position = state.position.get(product, 0)
                
                # 2. Calculate the maximum volume we can trade without hitting the +/- 20 limit.
                # Buy volume must be positive, sell volume must be negative.
                max_buy_volume = 80 - position
                max_sell_volume = -80 - position
                
                # 3. Find the current best bid and ask in the market safely
                best_bid = max(order_depth.buy_orders.keys()) if len(order_depth.buy_orders) > 0 else 0
                best_ask = min(order_depth.sell_orders.keys()) if len(order_depth.sell_orders) > 0 else 20000

                # -- SCENARIO A: Heavy Long (We have too many EMERALDS) --
                if position >= 78:
                    if best_bid == 10000:
                        # Outlier! Someone is buying at fair value. Dump our inventory to them.
                        # We use max() because sell volumes are negative numbers.
                        sell_vol = max(max_sell_volume, -order_depth.buy_orders[best_bid])
                        orders.append(Order(product, 10000, sell_vol))
                        print(f"Dumping Long at 10000, volume: {sell_vol}")
                    else:
                        # Stop buying. Only place our Ask at 10002.
                        orders.append(Order(product, 10007, int(2*max_sell_volume//2)))

                # -- SCENARIO B: Heavy Short (We owe too many EMERALDS) --
                elif position <= -78:
                    if best_ask == 10000:
                        # Outlier! Someone is selling at fair value. Buy from them to cover.
                        # We use min() because buy volumes are positive numbers.
                        buy_vol = min(max_buy_volume, -order_depth.sell_orders[best_ask])
                        orders.append(Order(product, 10000, buy_vol))
                        print(f"Covering Short at 10000, volume: {buy_vol}")
                    else:
                        # Stop selling. Only place our Bid at 9998.
                        orders.append(Order(product, 9993, int(2*max_buy_volume//2)))

                # -- SCENARIO C: Normal Inventory (Safe to Market Make) --
                else:
                    # Place standard orders on both sides to capture the spread
                    orders.append(Order(product, 9993, int(2*max_buy_volume//2)))
                    orders.append(Order(product, 10007, int(2*max_sell_volume//2)))

            result[product] = orders
    
        # No state needed for this strategy, conversions set to 0
        traderData = ""  
        conversions = 0
        return result, conversions, traderData