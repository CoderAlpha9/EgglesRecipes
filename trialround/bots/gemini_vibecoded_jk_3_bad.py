import json
import math
from datamodel import OrderDepth, UserId, TradingState, Order, Trade
from typing import List, Dict

class Trader:
    POSITION_LIMITS = {
        "EMERALDS": 80,
        "TOMATOES": 80
    }

    def compute_vwap(self, market_trades: List[Trade], fallback_price: float) -> float:
        """Calculates Volume Weighted Average Price from recent trades."""
        if not market_trades:
            return fallback_price
        total_vol = 0
        total_val = 0
        for trade in market_trades:
            total_vol += trade.quantity
            total_val += trade.price * trade.quantity
        return total_val / total_vol if total_vol > 0 else fallback_price

    def compute_obi(self, order_depth: OrderDepth) -> float:
        """Calculates Order Book Imbalance. Returns [-1.0 to 1.0]. Positive means buy pressure."""
        bid_vol = sum(order_depth.buy_orders.values())
        # Sell volumes are negative in the datamodel, so we negate to get absolute volume
        ask_vol = sum(-vol for vol in order_depth.sell_orders.values())
        total_vol = bid_vol + ask_vol
        if total_vol == 0:
            return 0.0
        return (bid_vol - ask_vol) / total_vol

    def compute_rsi(self, history: List[float], periods: int = 14) -> float:
        """Calculates Relative Strength Index."""
        if len(history) < periods + 1:
            return 50.0 # Neutral if not enough data
            
        gains = 0.0
        losses = 0.0
        for i in range(1, len(history)):
            change = history[i] - history[i-1]
            if change > 0:
                gains += change
            else:
                losses -= change
                
        avg_gain = gains / periods
        avg_loss = losses / periods
        
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def run(self, state: TradingState):
        result = {}
        conversions = 0
        
        # --- Restore State ---
        trader_state = {
            "TOM_HIST": [],
            "TOM_EMA_9": None,
            "TOM_EMA_21": None
        }
        if state.traderData:
            try:
                trader_state = json.loads(state.traderData)
            except Exception:
                pass

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            current_pos = state.position.get(product, 0)
            limit = self.POSITION_LIMITS.get(product, 80)
            market_trades = state.market_trades.get(product, [])
            
            if len(order_depth.sell_orders) == 0 or len(order_depth.buy_orders) == 0:
                continue

            best_ask = min(order_depth.sell_orders.keys())
            best_bid = max(order_depth.buy_orders.keys())
            mid_price = (best_bid + best_ask) / 2.0
            
            obi = self.compute_obi(order_depth)
            vwap = self.compute_vwap(market_trades, mid_price)

            # ==========================================
            # STRATEGY 1: EMERALDS (Micro-Structure Mean Reversion)
            # ==========================================
            if product == "EMERALDS":
                fair_value = 10000.0
                
                # If OBI is extremely high, market wants to buy. We shift our fair value slightly up.
                adjusted_fair = fair_value + (obi * 1.5)
                
                # 1. Aggressive Market Taking
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

                # 2. Passive Market Making with Inventory Skew & OBI adjustment
                # The more we hold, the more we skew our prices to offload
                inventory_skew = (current_pos / limit) * 3.0 
                
                my_bid = int(round(adjusted_fair - 1.5 - inventory_skew))
                my_ask = int(round(adjusted_fair + 1.5 - inventory_skew))
                
                # Prevent crossing our own spread
                if my_bid >= my_ask:
                    my_bid = my_ask - 1

                # Ladder orders
                if current_pos < limit:
                    qty = limit - current_pos
                    orders.append(Order(product, my_bid, qty))
                if current_pos > -limit:
                    qty = -limit - current_pos
                    orders.append(Order(product, my_ask, qty))

            # ==========================================
            # STRATEGY 2: TOMATOES (MACD + RSI + VWAP Trend)
            # ==========================================
            elif product == "TOMATOES":
                # Update history
                history = trader_state["TOM_HIST"]
                history.append(mid_price)
                if len(history) > 15:
                    history.pop(0)
                trader_state["TOM_HIST"] = history
                
                # Calculate EMAs
                ema_9 = trader_state["TOM_EMA_9"]
                ema_21 = trader_state["TOM_EMA_21"]
                
                multiplier_9 = 2.0 / (9 + 1)
                multiplier_21 = 2.0 / (21 + 1)
                
                if ema_9 is None:
                    ema_9 = mid_price
                    ema_21 = mid_price
                else:
                    ema_9 = (mid_price - ema_9) * multiplier_9 + ema_9
                    ema_21 = (mid_price - ema_21) * multiplier_21 + ema_21
                
                trader_state["TOM_EMA_9"] = ema_9
                trader_state["TOM_EMA_21"] = ema_21
                
                macd_diff = ema_9 - ema_21
                rsi = self.compute_rsi(history)
                
                # Dynamic Fair Value Blending
                # We anchor to VWAP, adjust by MACD momentum, and OBI pressure
                momentum_signal = macd_diff * 0.5
                order_book_signal = obi * 2.0
                fair_value = vwap + momentum_signal + order_book_signal
                
                inventory_skew = (current_pos / limit) * 4.0
                
                my_bid = int(round(fair_value - 2.0 - inventory_skew))
                my_ask = int(round(fair_value + 2.0 - inventory_skew))
                
                if my_bid >= my_ask:
                    my_bid = my_ask - 1

                # --- Momentum Taking ---
                # If RSI is oversold (< 30) and momentum is shifting up, aggressively take cheap asks
                if rsi < 30 and macd_diff > -0.5 and best_ask < fair_value:
                    vol = min(-order_depth.sell_orders.get(best_ask, 0), limit - current_pos)
                    if vol > 0:
                        orders.append(Order(product, best_ask, vol))
                        current_pos += vol
                        
                # If RSI is overbought (> 70) and momentum shifting down, aggressively sell to bids
                elif rsi > 70 and macd_diff < 0.5 and best_bid > fair_value:
                    vol = max(-order_depth.buy_orders.get(best_bid, 0), -limit - current_pos)
                    if vol < 0:
                        orders.append(Order(product, best_bid, vol))
                        current_pos += vol

                # --- Liquidity Provision ---
                if current_pos < limit:
                    orders.append(Order(product, my_bid, limit - current_pos))
                if current_pos > -limit:
                    orders.append(Order(product, my_ask, -limit - current_pos))

            result[product] = orders

        # --- Save State ---
        traderData = json.dumps(trader_state)
        
        return result, conversions, traderData