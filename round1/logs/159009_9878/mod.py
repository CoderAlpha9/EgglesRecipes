import json
import math
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
        
        # Initialize cleanly separated state dictionaries
        trader_state = {
            "OSMIUM_MACD": {},
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
            buy_cap = limit - current_pos
            sell_cap = limit + current_pos

            # ==========================================
            # STRATEGY 1: ASH_COATED_OSMIUM (Triangular Wave Engine)
            # ==========================================
            if product == "ASH_COATED_OSMIUM":
                
                # --- 1. MACD MOMENTUM TRACKER ---
                if "ema_fast" not in trader_state["OSMIUM_MACD"]:
                    trader_state["OSMIUM_MACD"] = {"ema_fast": mid_price, "ema_slow": mid_price}
                
                ts = trader_state["OSMIUM_MACD"]
                ts["ema_fast"] = (0.1 * mid_price) + (0.9 * ts["ema_fast"])
                ts["ema_slow"] = (0.02 * mid_price) + (0.98 * ts["ema_slow"])
                
                macd_raw = ts["ema_fast"] - ts["ema_slow"]
                trend_signal = max(-1.0, min(1.0, macd_raw / 2.0))

                # --- 2. DOUBLE-BARREL S/R OVERRIDES ---
                # We do not just wait for passive fills at the extremes; we take the liquidity instantly
                if best_ask >= 10020:
                    trend_signal = -1.0  # Force maximum selling behavior
                    
                    # Aggressive Take: Dump existing longs instantly into the bids
                    if current_pos > 0 and best_bid >= 10018:
                        dump_vol = min(current_pos, order_depth.buy_orders[best_bid])
                        if dump_vol > 0:
                            orders.append(Order(product, best_bid, -dump_vol))
                            current_pos -= dump_vol
                            buy_cap += dump_vol
                            sell_cap -= dump_vol # Reduce remaining capacity for the passive maker

                elif best_bid <= 9980:
                    trend_signal = 1.0   # Force maximum buying behavior
                    
                    # Aggressive Take: Cover existing shorts instantly into the asks
                    if current_pos < 0 and best_ask <= 9982:
                        cover_vol = min(abs(current_pos), -order_depth.sell_orders[best_ask])
                        if cover_vol > 0:
                            orders.append(Order(product, best_ask, cover_vol))
                            current_pos += cover_vol
                            buy_cap -= cover_vol
                            sell_cap += cover_vol # Reduce remaining capacity for the passive maker

                # --- 3. ZERO-EDGE UNWINDING (Capacity Management) ---
                # If inventory is dangerously skewed, dump at the current top-of-book 
                # to free up capacity for the inevitable reversal.
                is_unwinding_long = (current_pos >= 60 and best_ask < 10020)
                is_unwinding_short = (current_pos <= -60 and best_bid > 9980)

                # --- 4. ASYMMETRIC VOLUME MULTIPLIERS ---
                buy_multiplier = 1.0
                sell_multiplier = 1.0
                
                if trend_signal > 0:
                    sell_multiplier = max(0.0, 1.0 - trend_signal)
                elif trend_signal < 0:
                    buy_multiplier = max(0.0, 1.0 + trend_signal)

                # --- 5. EXECUTION: PENNYING & UNWINDING ---
                pos_ratio = current_pos / limit
                price_skew = int(round(pos_ratio * 1.5))
                
                my_bid = best_bid + 1 - price_skew
                my_ask = best_ask - 1 - price_skew
                
                # Apply Zero-Edge Unwinding overrides
                if is_unwinding_long:
                    my_ask = best_ask  # Join best ask to guarantee offload
                if is_unwinding_short:
                    my_bid = best_bid  # Join best bid to guarantee offload
                
                # Safety checks to prevent crossing our own spread
                if my_bid >= my_ask:
                    my_bid = best_bid
                    my_ask = best_ask
                    
                my_bid = min(my_bid, best_ask - 1)
                my_ask = max(my_ask, best_bid + 1)
                
                quoted_buy_vol = int(buy_cap * buy_multiplier)
                quoted_sell_vol = int(sell_cap * sell_multiplier)
                
                if quoted_buy_vol > 0:
                    orders.append(Order(product, my_bid, quoted_buy_vol))
                if quoted_sell_vol > 0:
                    orders.append(Order(product, my_ask, -quoted_sell_vol))

            # ==========================================
            # STRATEGY 2: INTARIAN_PEPPER_ROOT (Smart Accumulation)
            # ==========================================
            elif product == "INTARIAN_PEPPER_ROOT":
                
                if "prev_ask" not in trader_state["PEPPER_STATE"]:
                    trader_state["PEPPER_STATE"]["prev_ask"] = best_ask
                    
                prev_ask = trader_state["PEPPER_STATE"]["prev_ask"]
                trader_state["PEPPER_STATE"]["prev_ask"] = best_ask

                # PHASE A: Accumulation
                max_buy_volume = 80 - current_pos
                if max_buy_volume > 0:
                    
                    # Detect if the price suddenly spiked up
                    is_spike = best_ask > prev_ask
                    
                    if not is_spike:
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

        # Serialize state mapping safely back to the engine
        traderData = json.dumps(trader_state)
        return result, conversions, traderData