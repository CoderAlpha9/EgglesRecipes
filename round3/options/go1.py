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
        
        best_u_bid = max(u_depth.buy_orders.keys())
        best_u_ask = min(u_depth.sell_orders.keys())
        S = (best_u_bid + best_u_ask) / 2.0 

        # Time metric: 1M timestamps = 1 day
        T_days = 5.0 - (state.timestamp / 1000000.0)
        T_years = max(T_days / 252.0, 1e-6) 
        
        r = 0.0
        sigma = 0.252
        
        # We process all strikes, but the algorithm will naturally filter 
        # deep ITM/OTM because they rarely breach the expanded EDGE.
        STRIKES = [4000, 4500, 5000, 5100, 5200, 5300, 5400, 5500, 6000, 6500]
        
        current_option_delta = 0.0
        for strike in STRIKES:
            opt_symbol = f"VEV_{strike}"
            pos = state.position.get(opt_symbol, 0)
            if pos != 0:
                _, delta = self.bs_call_and_delta(S, strike, T_years, r, sigma)
                current_option_delta += pos * delta

        anticipated_delta = current_option_delta
        
        # --- NEW RISK PARAMETERS ---
        DELTA_LIMIT = 180.0
        OPT_LIMIT = 300
        # Increased EDGE to 3.5. We demand a larger mispricing to cover our hedging bleed.
        EDGE = 3.5 
        # The Lazy Hedge Threshold. We allow up to 20 Delta of naked exposure.
        HEDGE_THRESHOLD = 20.0 

        # 3. Execute Options Arbitrage
        for strike in STRIKES:
            opt_symbol = f"VEV_{strike}"
            if opt_symbol not in state.order_depths:
                continue
            
            result[opt_symbol] = []
            depth = state.order_depths[opt_symbol]
            pos = state.position.get(opt_symbol, 0)
            
            theo_price, delta = self.bs_call_and_delta(S, strike, T_years, r, sigma)
            
            # Buy Underpriced Options
            if len(depth.sell_orders) > 0:
                best_ask = min(depth.sell_orders.keys())
                ask_vol = -depth.sell_orders[best_ask]
                
                if best_ask < theo_price - EDGE:
                    max_buy_pos = OPT_LIMIT - pos
                    
                    if delta > 0:
                        max_buy_delta = int((DELTA_LIMIT - anticipated_delta) / delta)
                    else:
                        max_buy_delta = max_buy_pos
                        
                    qty = max(0, min(max_buy_pos, max_buy_delta, ask_vol))
                    if qty > 0:
                        result[opt_symbol].append(Order(opt_symbol, best_ask, qty))
                        anticipated_delta += qty * delta
                        pos += qty

            # Sell Overpriced Options
            if len(depth.buy_orders) > 0:
                best_bid = max(depth.buy_orders.keys())
                bid_vol = depth.buy_orders[best_bid]
                
                if best_bid > theo_price + EDGE:
                    max_sell_pos = OPT_LIMIT + pos 
                    
                    if delta > 0:
                        max_sell_delta = int((anticipated_delta - (-DELTA_LIMIT)) / delta)
                    else:
                        max_sell_delta = max_sell_pos
                        
                    qty = max(0, min(max_sell_pos, max_sell_delta, bid_vol))
                    if qty > 0:
                        result[opt_symbol].append(Order(opt_symbol, best_bid, -qty))
                        anticipated_delta -= qty * delta
                        pos -= qty

        # 4. Execute "Lazy" Dynamic Delta Hedging
        result[underlying] = []
        current_underlying = state.position.get(underlying, 0)
        
        # Calculate our total net exposure (Options Delta + Underlying Shares)
        net_exposure = anticipated_delta + current_underlying
        
        U_LIMIT = 200
        
        # ONLY hedge if our exposure breaches the safe band
        if abs(net_exposure) > HEDGE_THRESHOLD:
            # Calculate exactly how many shares to trade to get back to perfect 0 Delta
            qty_to_trade = -round(net_exposure)
            
            if qty_to_trade > 0:
                max_buy = U_LIMIT - current_underlying
                qty = min(qty_to_trade, max_buy)
                if qty > 0:
                    result[underlying].append(Order(underlying, best_u_ask, qty))
            elif qty_to_trade < 0:
                max_sell = U_LIMIT + current_underlying
                qty = min(-qty_to_trade, max_sell)
                if qty > 0:
                    result[underlying].append(Order(underlying, best_u_bid, -qty))

        result = {k: v for k, v in result.items() if len(v) > 0}

        return result, conversions, traderData