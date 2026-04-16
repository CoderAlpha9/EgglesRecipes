import json
import math
from datamodel import OrderDepth, UserId, TradingState, Order, Trade
from typing import List

class Trader:
    POSITION_LIMITS = {
        "EMERALDS": 80,
        "TOMATOES": 80
    }

    def compute_obi(self, order_depth: OrderDepth) -> float:
        """Calculates Order Book Imbalance. Returns [-1.0 to 1.0]."""
        bid_vol = sum(order_depth.buy_orders.values())
        ask_vol = sum(-vol for vol in order_depth.sell_orders.values())
        total_vol = bid_vol + ask_vol
        return (bid_vol - ask_vol) / total_vol if total_vol > 0 else 0.0

    def calculate_std_dev(self, prices: List[float]) -> float:
        """Calculates realized volatility."""
        if len(prices) < 2:
            return 0.0
        mean = sum(prices) / len(prices)
        variance = sum((x - mean) ** 2 for x in prices) / len(prices)
        return math.sqrt(variance)

    def run(self, state: TradingState):
        result = {}
        conversions = 0
        
        # --- Restore Persistent State ---
        trader_state = {
            "TOMATOES_HISTORY": [],
            "TOMATOES_EMA_9": None,
            "TOMATOES_EMA_21": None,
            "TOMATOES_VWAP_VOL": 0,
            "TOMATOES_VWAP_VAL": 0.0
        }
        
        if state.traderData:
            try:
                trader_state = json.loads(state.traderData)
            except Exception:
                pass

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            if len(order_depth.sell_orders) == 0 or len(order_depth.buy_orders) == 0:
                continue

            current_pos = state.position.get(product, 0)
            limit = self.POSITION_LIMITS.get(product, 80)
            market_trades = state.market_trades.get(product, [])
            
            best_ask = min(order_depth.sell_orders.keys())
            best_bid = max(order_depth.buy_orders.keys())
            mid_price = (best_bid + best_ask) / 2.0

            # ==========================================
            # STRATEGY 1: EMERALDS (Continuous Skew + OBI)
            # ==========================================
            if product == "EMERALDS":
                fair_value = 10000
                obi = self.compute_obi(order_depth)
                
                # 1. Immediate Arbitrage Sniping
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
                
                # 2. Continuous Inventory Skew & OBI Front-Running
                obi_shift_bid = 1 if obi < -0.6 else 0
                obi_shift_ask = 1 if obi > 0.6 else 0
                
                # Continuous smooth skew instead of step-function
                skew = (current_pos / limit) * 2.0
                
                my_bid = int(round(9998 - obi_shift_bid - skew))
                my_ask = int(round(10002 + obi_shift_ask - skew))
                
                # Ensure valid spread
                if my_bid >= my_ask:
                    my_bid = my_ask - 1

                # Place resting liquidity orders
                if current_pos < limit:
                    orders.append(Order(product, my_bid, limit - current_pos))
                if current_pos > -limit:
                    orders.append(Order(product, my_ask, -limit - current_pos))

            # ==========================================
            # STRATEGY 2: TOMATOES (Aggressive Volume Capture)
            # ==========================================
            elif product == "TOMATOES":
                # --- State Management & Metric Calculation ---
                hist = trader_state.get("TOMATOES_HISTORY", [])
                hist.append(mid_price)
                if len(hist) > 20:
                    hist.pop(0)
                trader_state["TOMATOES_HISTORY"] = hist
                
                std_dev = self.calculate_std_dev(hist)
                
                # Fast & Slow EMAs for MACD
                ema_9 = trader_state.get("TOMATOES_EMA_9")
                ema_21 = trader_state.get("TOMATOES_EMA_21")
                
                m_9 = 2.0 / 10.0
                m_21 = 2.0 / 22.0
                
                if ema_9 is None:
                    ema_9 = mid_price
                    ema_21 = mid_price
                else:
                    ema_9 = (mid_price - ema_9) * m_9 + ema_9
                    ema_21 = (mid_price - ema_21) * m_21 + ema_21
                
                trader_state["TOMATOES_EMA_9"] = ema_9
                trader_state["TOMATOES_EMA_21"] = ema_21
                macd = ema_9 - ema_21
                
                # VWAP Calculation (Rolling decay)
                vwap_vol = trader_state.get("TOMATOES_VWAP_VOL", 0) * 0.95
                vwap_val = trader_state.get("TOMATOES_VWAP_VAL", 0.0) * 0.95
                
                for t in market_trades:
                    vwap_vol += t.quantity
                    vwap_val += t.price * t.quantity
                    
                trader_state["TOMATOES_VWAP_VOL"] = vwap_vol
                trader_state["TOMATOES_VWAP_VAL"] = vwap_val
                
                fair_value = (vwap_val / vwap_vol) if vwap_vol > 0 else mid_price
                
                # --- Advanced Quoting Logic ---
                # 1. Volatility Widening
                vol_spread = min(int(std_dev / 2.0), 4)
                
                # 2. Aggressive Inventory Skewing (Reduced from 4.0 to 2.5 to capture more volume)
                skew = (current_pos / limit) * 2.5
                
                my_bid = int(round(fair_value - 1.5 - vol_spread - skew))
                my_ask = int(round(fair_value + 1.5 + vol_spread - skew))
                
                # 3. MACD Reversal Sniping
                is_cheap = best_ask < fair_value - 3
                is_momentum_up = macd > -0.5
                
                is_expensive = best_bid > fair_value + 3
                is_momentum_down = macd < 0.5
                
                if is_cheap and is_momentum_up and current_pos < limit:
                    vol = min(-order_depth.sell_orders.get(best_ask, 0), limit - current_pos)
                    if vol > 0:
                        orders.append(Order(product, best_ask, vol))
                        current_pos += vol
                        
                elif is_expensive and is_momentum_down and current_pos > -limit:
                    vol = max(-order_depth.buy_orders.get(best_bid, 0), -limit - current_pos)
                    if vol < 0:
                        orders.append(Order(product, best_bid, vol))
                        current_pos += vol
                
                # 4. Tighter Momentum Stop-Loss (The Kill Switch)
                # Adjusted to -1.0 to cut losses faster since we are taking more inventory
                if current_pos > 40 and macd < -1.0:
                    dump_vol = -limit - current_pos
                    orders.append(Order(product, best_bid, dump_vol))
                    current_pos += dump_vol
                elif current_pos < -40 and macd > 1.0:
                    cover_vol = limit - current_pos
                    orders.append(Order(product, best_ask, cover_vol))
                    current_pos += cover_vol
                    
                if my_bid >= my_ask:
                    my_bid = my_ask - 1

                # 5. Liquidity Provision 
                if std_dev < 8.0:
                    if current_pos < limit:
                        orders.append(Order(product, my_bid, limit - current_pos))
                    if current_pos > -limit:
                        orders.append(Order(product, my_ask, -limit - current_pos))

            result[product] = orders

        # --- Save Persistent State ---
        traderData = json.dumps(trader_state)
        
        return result, conversions, traderData