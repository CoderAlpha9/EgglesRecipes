import json
import math
from datamodel import OrderDepth, UserId, TradingState, Order, Trade
from typing import List, Dict

class Trader:
    POSITION_LIMITS = {
        "EMERALDS": 80,
        "TOMATOES": 80
    }

    def calculate_linear_regression_slope(self, prices: List[float]) -> float:
        """Calculates the slope of the price trend. Positive = Upward, Negative = Downward."""
        if len(prices) < 2:
            return 0.0
        n = len(prices)
        x_mean = (n - 1) / 2.0
        y_mean = sum(prices) / n
        numerator = sum((i - x_mean) * (prices[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        return numerator / denominator if denominator != 0 else 0.0

    def calculate_std_dev(self, prices: List[float]) -> float:
        """Calculates the standard deviation (volatility) of the price history."""
        if len(prices) < 2:
            return 0.0
        mean = sum(prices) / len(prices)
        variance = sum((x - mean) ** 2 for x in prices) / len(prices)
        return math.sqrt(variance)

    def compute_obi(self, order_depth: OrderDepth) -> float:
        """Calculates Order Book Imbalance [-1.0 to 1.0]."""
        bid_vol = sum(order_depth.buy_orders.values())
        ask_vol = sum(-vol for vol in order_depth.sell_orders.values())
        total_vol = bid_vol + ask_vol
        return (bid_vol - ask_vol) / total_vol if total_vol > 0 else 0.0

    def run(self, state: TradingState):
        result = {}
        conversions = 0
        
        # --- State Management ---
        trader_state = {"TOMATOES_HISTORY": []}
        if state.traderData:
            try:
                trader_state = json.loads(state.traderData)
            except Exception:
                pass
                
        history_len = 20

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            if len(order_depth.sell_orders) == 0 or len(order_depth.buy_orders) == 0:
                continue

            current_pos = state.position.get(product, 0)
            limit = self.POSITION_LIMITS.get(product, 80)
            
            best_ask = min(order_depth.sell_orders.keys())
            best_bid = max(order_depth.buy_orders.keys())
            mid_price = (best_bid + best_ask) / 2.0

            # ==========================================
            # STRATEGY 1: EMERALDS (Strict Peg & Arb)
            # ==========================================
            if product == "EMERALDS":
                fair_value = 10000
                
                # 1. Arbitrage Sniping
                if best_ask < fair_value:
                    vol = min(-order_depth.sell_orders[best_ask], limit - current_pos)
                    if vol > 0:
                        orders.append(Order(product, best_ask, vol))
                        current_pos += vol
                        
                if best_bid > fair_value:
                    vol = max(-order_depth.buy_orders[best_bid], -limit - current_pos)
                    if vol < 0:
                        orders.append(Order(product, best_bid, vol))
                        current_pos += vol
                
                # 2. Strategic Market Making
                my_bid = 9998
                my_ask = 10002
                
                if current_pos > 40:
                    my_ask = 10000 
                    my_bid = 9996  
                elif current_pos < -40:
                    my_bid = 10000 
                    my_ask = 10004 

                if current_pos < limit:
                    orders.append(Order(product, my_bid, limit - current_pos))
                if current_pos > -limit:
                    orders.append(Order(product, my_ask, -limit - current_pos))

            # ==========================================
            # STRATEGY 2: TOMATOES (Slope + Volatility + OBI)
            # ==========================================
            elif product == "TOMATOES":
                hist = trader_state.get("TOMATOES_HISTORY", [])
                hist.append(mid_price)
                if len(hist) > history_len:
                    hist.pop(0)
                trader_state["TOMATOES_HISTORY"] = hist
                
                slope = self.calculate_linear_regression_slope(hist)
                std_dev = self.calculate_std_dev(hist)
                obi = self.compute_obi(order_depth)
                
                # --- Base Quoting ---
                my_bid = best_bid + 1
                my_ask = best_ask - 1
                
                # --- Adjustments ---
                # 1. Inventory Skew (Protect capital)
                skew = (current_pos / limit) * 3.0
                
                # 2. Volatility Widening (Protect against swings)
                # If std_dev is high (e.g., > 3), we widen our spread by that amount
                vol_spread = min(int(std_dev / 1.5), 4) # Cap widening to 4 ticks max
                
                # 3. OBI Micro-Shift (Front-run the pressure)
                obi_shift = obi * 2.0 
                
                # Apply all modifiers to our target quotes
                my_bid = int(round(my_bid - skew - vol_spread + obi_shift))
                my_ask = int(round(my_ask - skew + vol_spread + obi_shift))
                
                # Sanity check: never cross our own spread
                if my_bid >= my_ask:
                    my_bid = my_ask - 1

                # --- THE KILL SWITCHES ---
                # Added Trade Flow Toxicity check: if market_trades are largely at the bid, it's crashing.
                market_trades = state.market_trades.get(product, [])
                recent_sell_pressure = sum(t.quantity for t in market_trades if t.price <= best_bid) > 15

                is_crashing = slope < -0.8 or (slope < -0.4 and recent_sell_pressure)
                is_rocketing = slope > 0.8 
                
                # Extreme Inventory Danger (Stop-Loss Pivot)
                if current_pos > 60 and is_crashing:
                    dump_vol = -limit - current_pos
                    orders.append(Order(product, best_bid, dump_vol))
                    current_pos += dump_vol
                elif current_pos < -60 and is_rocketing:
                    cover_vol = limit - current_pos
                    orders.append(Order(product, best_ask, cover_vol))
                    current_pos += cover_vol

                # Normal Market Making
                if current_pos < limit and not is_crashing:
                    orders.append(Order(product, my_bid, limit - current_pos))
                if current_pos > -limit and not is_rocketing:
                    orders.append(Order(product, my_ask, -limit - current_pos))

            result[product] = orders

        traderData = json.dumps(trader_state)
        return result, conversions, traderData