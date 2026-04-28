from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict
import math

class Trader:
    
    def bid(self):
        return 840 

    def norm_cdf(self, x: float) -> float:
        """Standard Normal Cumulative Distribution Function"""
        return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

    def bs_call_and_delta(self, S: float, K: float, T: float, r: float, sigma: float):
        """Calculates theoretical Black-Scholes Call Price and Delta"""
        T = max(T, 1e-6) 
        if T <= 1e-5:
            return max(0.0, S - K), (1.0 if S > K else 0.0)
        
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        
        price = S * self.norm_cdf(d1) - K * math.exp(-r * T) * self.norm_cdf(d2)
        delta = self.norm_cdf(d1)
        
        return price, delta

    def run(self, state: TradingState):
        result = {}
        conversions = 0
        traderData = state.traderData

        underlying = 'VELVETFRUIT_EXTRACT'
        if underlying not in state.order_depths:
            return result, conversions, traderData

        u_depth = state.order_depths[underlying]
        if not u_depth.buy_orders or not u_depth.sell_orders:
            return result, conversions, traderData
        
        # 1. Underlying Metrics
        best_u_bid = max(u_depth.buy_orders.keys())
        best_u_ask = min(u_depth.sell_orders.keys())
        S = (best_u_bid + best_u_ask) / 2.0 

        T_days = 5.0 - (state.timestamp / 1000000.0)
        T_years = max(T_days / 252.0, 1e-6) 
        r = 0.0
        sigma = 0.252
        
        STRIKES = [4000, 4500, 5000, 5100, 5200, 5300, 5400, 5500, 6000, 6500]
        OPT_LIMIT = 300
        U_LIMIT = 200
        
        # Market Making Parameters
        BASE_EDGE = 2.0      # Our desired profit margin per trade
        MAX_SKEW = 2.5       # Max price adjustment based on inventory
        DELTA_SKEW = 1.0     # Max price adjustment based on portfolio delta
        
        # 2. Portfolio Delta Calculation
        current_option_delta = 0.0
        for strike in STRIKES:
            opt_symbol = f"VEV_{strike}"
            pos = state.position.get(opt_symbol, 0)
            if pos != 0:
                _, delta = self.bs_call_and_delta(S, strike, T_years, r, sigma)
                current_option_delta += pos * delta

        # Total directional risk
        current_underlying = state.position.get(underlying, 0)
        net_delta = current_option_delta + current_underlying

        # 3. Quote Generation (Market Making)
        for strike in STRIKES:
            opt_symbol = f"VEV_{strike}"
            if opt_symbol not in state.order_depths:
                continue
                
            result[opt_symbol] = []
            pos = state.position.get(opt_symbol, 0)
            
            theo_price, opt_delta = self.bs_call_and_delta(S, strike, T_years, r, sigma)
            
            # Inventory Skew: If we have too many longs, lower our quotes to sell them off.
            inventory_skew = (pos / OPT_LIMIT) * MAX_SKEW
            
            # Delta Skew: If we are dangerously long delta, lower quotes on calls to avoid buying more.
            # We normalize net_delta against our safety limit of 150.
            directional_skew = (net_delta / 150.0) * DELTA_SKEW
            
            # Combine skews. Note: Both skews push quotes DOWN when long, and UP when short.
            total_skew = inventory_skew + directional_skew
            
            # Calculate our resting Bid and Ask
            my_bid = math.floor(theo_price - BASE_EDGE - total_skew)
            my_ask = math.ceil(theo_price + BASE_EDGE - total_skew)
            
            # Edge case handling for deep OTM options (price cannot go below 0)
            my_bid = max(0, my_bid)
            my_ask = max(1, my_ask) # Ensure ask is always at least 1
            if my_bid >= my_ask:
                my_bid = my_ask - 1

            # Order Sizing
            qty_to_buy = OPT_LIMIT - pos
            qty_to_sell = -OPT_LIMIT - pos
            
            # Submit Quotes
            if qty_to_buy > 0:
                result[opt_symbol].append(Order(opt_symbol, my_bid, qty_to_buy))
            if qty_to_sell < 0:
                result[opt_symbol].append(Order(opt_symbol, my_ask, qty_to_sell))

        # 4. Lazy Delta Hedging (Risk Management)
        result[underlying] = []
        HEDGE_THRESHOLD = 20.0 
        
        if abs(net_delta) > HEDGE_THRESHOLD:
            qty_to_trade = -round(net_delta)
            
            if qty_to_trade > 0:
                max_buy = U_LIMIT - current_underlying
                qty = min(qty_to_trade, max_buy)
                if qty > 0:
                    # Hedge immediately by crossing the spread
                    result[underlying].append(Order(underlying, best_u_ask, qty))
            elif qty_to_trade < 0:
                max_sell = U_LIMIT + current_underlying
                qty = min(-qty_to_trade, max_sell)
                if qty > 0:
                    # Hedge immediately by crossing the spread
                    result[underlying].append(Order(underlying, best_u_bid, -qty))

        # Cleanup
        result = {k: v for k, v in result.items() if len(v) > 0}

        return result, conversions, traderData