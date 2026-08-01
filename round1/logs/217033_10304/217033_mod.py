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
            "PEPPER_PREV_ASK": None,
            "OSMIUM_SLOW_EMA": None
        }
        
        if state.traderData:
            try:
                trader_state = json.loads(state.traderData)
            except Exception:
                pass

        for product in state.order_depths:
            if product not in self.POSITION_LIMITS:
                continue

            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            if not order_depth.sell_orders or not order_depth.buy_orders:
                continue

            best_bid = max(order_depth.buy_orders.keys())
            best_ask = min(order_depth.sell_orders.keys())
            mid_price = (best_bid + best_ask) / 2.0
            
            current_pos = state.position.get(product, 0)
            limit = self.POSITION_LIMITS[product]
            buy_vol = limit - current_pos
            sell_vol = -limit - current_pos

            # ---------------------------------------------------------
            # STRATEGY 1: ASH_COATED_OSMIUM (Laddered Arbitrage)
            # ---------------------------------------------------------
            if product == "ASH_COATED_OSMIUM":
                osmium_ema = trader_state.get("OSMIUM_SLOW_EMA")
                if osmium_ema is None:
                    osmium_ema = mid_price
                else:
                    osmium_ema = 0.002 * mid_price + 0.998 * osmium_ema
                
                trader_state["OSMIUM_SLOW_EMA"] = osmium_ema
                fair_value = int(round(osmium_ema))

                # 1. Depth Sweeping
                for ask_price, ask_vol in sorted(order_depth.sell_orders.items()):
                    ask_vol = -ask_vol 
                    if ask_price < fair_value and buy_vol > 0:
                        take_vol = min(buy_vol, ask_vol)
                        orders.append(Order(product, ask_price, take_vol))
                        buy_vol -= take_vol 
                        current_pos += take_vol 
                    else:
                        break

                for bid_price, bid_vol in sorted(order_depth.buy_orders.items(), reverse=True):
                    if bid_price > fair_value and sell_vol < 0:
                        take_vol = max(sell_vol, -bid_vol) 
                        orders.append(Order(product, bid_price, take_vol))
                        sell_vol -= take_vol
                        current_pos += take_vol 
                    else:
                        break

                # 2. Laddered Passive Quoting (Scaling into positions)
                if buy_vol > 0:
                    base_bid = best_bid + 1
                    if base_bid >= best_ask:
                        base_bid = best_bid
                        
                    cap = fair_value if current_pos < 0 else fair_value - 1
                    base_bid = min(base_bid, cap)
                    
                    # Split remaining volume into 3 cascading tiers
                    chunk1 = int(buy_vol / 4.0)
                    chunk2 = int(buy_vol / 4.0)
                    chunk3 = int(buy_vol / 4.0)
                    chunk4 = buy_vol - chunk1 - chunk2 - chunk3
                    
                    if chunk1 > 0: orders.append(Order(product, base_bid, chunk1))
                    if chunk2 > 0: orders.append(Order(product, base_bid - 1, chunk2))
                    if chunk3 > 0: orders.append(Order(product, base_bid - 2, chunk3))
                    if chunk3 > 0: orders.append(Order(product, base_bid - 3, chunk4))
                    
                if sell_vol < 0:
                    base_ask = best_ask - 1
                    if base_ask <= best_bid:
                        base_ask = best_ask
                        
                    floor = fair_value if current_pos > 0 else fair_value + 1
                    base_ask = max(base_ask, floor)
                    
                    # Split remaining volume into 3 cascading tiers
                    chunk1 = int(sell_vol / 4.0)
                    chunk2 = int(sell_vol / 4.0)
                    chunk3 = int(sell_vol / 4.0)
                    chunk4 = sell_vol - chunk1 - chunk2 - chunk3
                    
                    if chunk1 < 0: orders.append(Order(product, base_ask, chunk1))
                    if chunk2 < 0: orders.append(Order(product, base_ask + 1, chunk2))
                    if chunk3 < 0: orders.append(Order(product, base_ask + 2, chunk3))
                    if chunk3 < 0: orders.append(Order(product, base_ask + 3, chunk3))

            # ---------------------------------------------------------
            # STRATEGY 2: INTARIAN_PEPPER_ROOT (Momentum + Bracket Spikes)
            # ---------------------------------------------------------
            elif product == "INTARIAN_PEPPER_ROOT":
                prev_ask = trader_state.get("PEPPER_PREV_ASK")
                if prev_ask is None:
                    prev_ask = best_ask
                    
                trader_state["PEPPER_PREV_ASK"] = best_ask
                
                if buy_vol > 0:
                    is_spike = best_ask > prev_ask
                    
                    if not is_spike:
                        # Aggressive Accumulation when stable
                        orders.append(Order(product, best_ask, buy_vol))
                    else:
                        # Passive bid on localized spikes
                        my_bid = best_bid + 1
                        if my_bid >= best_ask:
                            my_bid = best_bid
                        orders.append(Order(product, my_bid, buy_vol))

            result[product] = orders

        return result, conversions, json.dumps(trader_state)