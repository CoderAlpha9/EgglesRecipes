import json
import math
from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict, Tuple

class Trader:
    POSITION_LIMITS = {
        "EMERALDS": 80,
        "TOMATOES": 80
    }

    # ==========================================
    # --- MODEL WEIGHTS & SCALARS (CONSTANTS) ---
    # ==========================================
    T_INTERCEPT = -0.0037
    T_W_AVG_SPREAD = 0.0129
    T_W_AVG_IMBALANCE = 0.1183      
    T_W_MICRO_DIVERGENCE = 0.1232   
    T_W_VOLUME = -0.1741            

    T_AVG_SPREAD_MEAN = 13.0223;        T_AVG_SPREAD_STD = 0.1732
    T_AVG_IMBALANCE_MEAN = -0.0003;     T_AVG_IMBALANCE_STD = 0.0087
    T_MICRO_DIVERGENCE_MEAN = -0.0044;  T_MICRO_DIVERGENCE_STD = 0.0323
    T_VOLUME_MEAN = 14.3535;            T_VOLUME_STD = 7.0586

    E_INTERCEPT = -0.0299
    E_W_AVG_SPREAD = 0.1359
    E_W_AVG_IMBALANCE = 0.1327
    E_W_MICRO_DIVERGENCE = 0.1327
    E_W_VOLUME = -0.0342

    E_AVG_SPREAD_MEAN = 15.7418;        E_AVG_SPREAD_STD = 0.1477
    E_AVG_IMBALANCE_MEAN = -0.0001;     E_AVG_IMBALANCE_STD = 0.0046
    E_MICRO_DIVERGENCE_MEAN = -0.0005;  E_MICRO_DIVERGENCE_STD = 0.0184
    E_VOLUME_MEAN = 11.0556;            E_VOLUME_STD = 8.4472

    def run(self, state: TradingState):
        result = {}
        conversions = 0
        
        # --- State Management ---
        # UPGRADE: BB_STATE added for Zero-Lag EMA Bollinger Tracking
        trader_state = {
            "EMERALDS_FEAT": {"spread":[], "imb":[], "mdiv":[], "vol":[]},
            "TOMATOES_FEAT": {"spread":[], "imb":[], "mdiv":[], "vol":[]},
            "OFI_STATE": {},  
            "VPIN_STATE": {},
            "OU_STATE": {},
            "BB_STATE": {} 
        }
        
        if state.traderData:
            try:
                trader_state = json.loads(state.traderData)
            except Exception:
                pass
                
        window_len = 10 
        vpin_window_len = 15 

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            if len(order_depth.sell_orders) == 0 or len(order_depth.buy_orders) == 0:
                continue

            sorted_bids = sorted(order_depth.buy_orders.items(), key=lambda x: x[0], reverse=True)
            sorted_asks = sorted(order_depth.sell_orders.items(), key=lambda x: x[0])
            
            best_bid, best_bid_vol = sorted_bids[0]
            best_ask, best_ask_vol = sorted_asks[0]
            best_ask_vol = -best_ask_vol 
            
            mid_price = (best_bid + best_ask) / 2.0

            # ------------------------------------------
            # 0. ORNSTEIN-UHLENBECK ESTIMATOR (Untouched)
            # ------------------------------------------
            ou_alpha = 0.05 
            ou_state = trader_state["OU_STATE"].get(product, {"mu": mid_price, "var": 1.0})
            if ou_state["mu"] == 0: ou_state["mu"] = mid_price
            
            new_mu = ou_state["mu"] + ou_alpha * (mid_price - ou_state["mu"])
            dev = mid_price - ou_state["mu"]
            new_var = ou_state["var"] + ou_alpha * ((dev ** 2) - ou_state["var"])
            
            trader_state["OU_STATE"][product] = {"mu": new_mu, "var": new_var}
            ou_sigma = math.sqrt(new_var) if new_var > 0 else 1.0
            ou_theta = 0.25 
            ou_drift = ou_theta * (new_mu - mid_price)

            # ------------------------------------------
            # 1. MICROSTRUCTURE: O.F.I. 
            # ------------------------------------------
            prev_state = trader_state["OFI_STATE"].get(product, {"b_p": best_bid, "b_v": 0, "a_p": best_ask, "a_v": 0})
            
            ofi_bid = 0
            if best_bid > prev_state["b_p"]: ofi_bid = best_bid_vol
            elif best_bid == prev_state["b_p"]: ofi_bid = best_bid_vol - prev_state["b_v"]
            else: ofi_bid = -prev_state["b_v"]
                
            ofi_ask = 0
            if best_ask < prev_state["a_p"]: ofi_ask = best_ask_vol
            elif best_ask == prev_state["a_p"]: ofi_ask = best_ask_vol - prev_state["a_v"]
            else: ofi_ask = -prev_state["a_v"]
                
            tick_ofi = ofi_bid - ofi_ask
            trader_state["OFI_STATE"][product] = {"b_p": best_bid, "b_v": best_bid_vol, "a_p": best_ask, "a_v": best_ask_vol}

            # ------------------------------------------
            # 2. MICROSTRUCTURE: VPIN 
            # ------------------------------------------
            market_trades = state.market_trades.get(product,[])
            tick_buy_vol = sum(t.quantity for t in market_trades if t.price >= best_ask)
            tick_sell_vol = sum(t.quantity for t in market_trades if t.price <= best_bid)
            tick_vol = sum(t.quantity for t in market_trades) 
            
            vpin_hist = trader_state["VPIN_STATE"].get(product,[])
            vpin_hist.append({"b": tick_buy_vol, "s": tick_sell_vol})
            if len(vpin_hist) > vpin_window_len: vpin_hist.pop(0)
            trader_state["VPIN_STATE"][product] = vpin_hist
            
            tot_rolling_buy = sum(x["b"] for x in vpin_hist)
            tot_rolling_sell = sum(x["s"] for x in vpin_hist)
            tot_rolling_vol = tot_rolling_buy + tot_rolling_sell
            vpin = abs(tot_rolling_buy - tot_rolling_sell) / tot_rolling_vol if tot_rolling_vol > 0 else 0.0

            # ------------------------------------------
            # 3. BASE FEATURES & Z-SCORES
            # ------------------------------------------
            total_bid_vol = sum(order_depth.buy_orders.values())
            total_ask_vol = sum(-v for v in order_depth.sell_orders.values())
            total_book_vol = total_bid_vol + total_ask_vol
            
            tick_spread = best_ask - best_bid
            tick_imb = (total_bid_vol - total_ask_vol) / total_book_vol if total_book_vol > 0 else 0.0
            micro_price = (best_bid * total_ask_vol + best_ask * total_bid_vol) / total_book_vol if total_book_vol > 0 else mid_price
            tick_mdiv = micro_price - mid_price
            
            feat_key = f"{product}_FEAT"
            feats = trader_state[feat_key]
            
            feats["spread"].append(tick_spread); feats["imb"].append(tick_imb)
            feats["mdiv"].append(tick_mdiv); feats["vol"].append(tick_vol)
            
            for k in ["spread", "imb", "mdiv", "vol"]:
                if len(feats[k]) > window_len: feats[k].pop(0)
                    
            avg_spread = sum(feats["spread"]) / len(feats["spread"])
            avg_imb = sum(feats["imb"]) / len(feats["imb"])
            avg_mdiv = sum(feats["mdiv"]) / len(feats["mdiv"])
            avg_vol = sum(feats["vol"]) / len(feats["vol"])

            current_pos = state.position.get(product, 0)
            limit = self.POSITION_LIMITS.get(product, 80)
            buy_cap = limit - current_pos
            sell_cap = limit + current_pos
            is_warmed_up = len(feats["spread"]) >= window_len

            # ==========================================
            # EXECUTION: TOMATOES (EMA Bollinger Engine)
            # ==========================================
            if product == "TOMATOES":
                
                # --- FIX 1: ZERO-LAG EMA BOLLINGER ---
                # Replaces the 15-tick static array. Recovers from volatility spikes instantly.
                alpha_ema = 0.15 # Fast recovery factor
                bb_state = trader_state["BB_STATE"].get(product, {"ema": mid_price, "var": 1.0})
                
                if bb_state["ema"] == 0: bb_state["ema"] = mid_price
                
                new_ema = (alpha_ema * mid_price) + ((1 - alpha_ema) * bb_state["ema"])
                dev_bb = mid_price - new_ema
                new_var_bb = (alpha_ema * (dev_bb ** 2)) + ((1 - alpha_ema) * bb_state["var"])
                
                trader_state["BB_STATE"][product] = {"ema": new_ema, "var": new_var_bb}
                
                bb_std = math.sqrt(new_var_bb) if new_var_bb > 0 else 1.0
                bb_upper = new_ema + (2.0 * bb_std)
                bb_lower = new_ema - (2.0 * bb_std)

                if is_warmed_up:
                    z_spread = (avg_spread - self.T_AVG_SPREAD_MEAN) / self.T_AVG_SPREAD_STD
                    z_imb = (avg_imb - self.T_AVG_IMBALANCE_MEAN) / self.T_AVG_IMBALANCE_STD
                    z_mdiv = (avg_mdiv - self.T_MICRO_DIVERGENCE_MEAN) / self.T_MICRO_DIVERGENCE_STD
                    z_vol = (avg_vol - self.T_VOLUME_MEAN) / self.T_VOLUME_STD
                    
                    base_alpha = (self.T_INTERCEPT + 
                                  self.T_W_AVG_SPREAD * z_spread + 
                                  self.T_W_AVG_IMBALANCE * z_imb + 
                                  self.T_W_MICRO_DIVERGENCE * z_mdiv + 
                                  self.T_W_VOLUME * z_vol)
                    
                    ofi_fade = (tick_ofi / 8.0) * 0.75 
                    alpha = max(-5.0, min(5.0, base_alpha - ofi_fade))
                else:
                    alpha = 0.0 
                
                # OU drift retained exactly as your baseline requested
                fair_price = mid_price + alpha + ou_drift

                # STAGNATION FREQUENCY REDUCTION
                stagnation_penalty = 1.0 if bb_std < 1.2 else 0.0 

                # --- FIX 2: ASYMPTOTIC EDGE SKEW ---
                # Forces high-frequency trading at the start by lowering base edge to 0.4.
                # Uses a cubic multiplier (pos_ratio^3) to exponentially increase edge only when heavily loaded.
                pos_ratio = current_pos / limit
                buy_edge_required = 0.4 + (pos_ratio ** 3 if pos_ratio > 0 else pos_ratio) * 6.0
                sell_edge_required = 0.4 - (pos_ratio ** 3 if pos_ratio < 0 else pos_ratio) * 6.0

                # MOMENTUM REVERSION & LIQUIDITY EXPLOITATION 
                if mid_price <= bb_lower:
                    buy_edge_required -= 1.5 
                
                if mid_price >= bb_upper:
                    sell_edge_required -= 1.5 

                for ask_p, ask_v in sorted_asks:
                    if ask_p < fair_price - buy_edge_required:
                        buy_qty = min(-ask_v, buy_cap)
                        if buy_qty > 0:
                            orders.append(Order(product, ask_p, buy_qty))
                            buy_cap -= buy_qty; current_pos += buy_qty
                            
                for bid_p, bid_v in sorted_bids:
                    if bid_p > fair_price + sell_edge_required:
                        sell_qty = min(bid_v, sell_cap)
                        if sell_qty > 0:
                            orders.append(Order(product, bid_p, -sell_qty))
                            sell_cap -= sell_qty; current_pos -= sell_qty

                # PROVEN MAKER QUOTING
                skew = pos_ratio * 4.0
                
                ideal_bid = fair_price - 1.5 - skew - stagnation_penalty
                ideal_ask = fair_price + 1.5 - skew + stagnation_penalty
                
                my_bid = int(math.floor(min(best_bid + 1, ideal_bid)))
                my_ask = int(math.ceil(max(best_ask - 1, ideal_ask)))

                if my_bid >= my_ask: my_bid = my_ask - 1
                my_bid = min(my_bid, best_ask - 1)
                my_ask = max(my_ask, best_bid + 1)

                if buy_cap > 0: orders.append(Order(product, my_bid, buy_cap))
                if sell_cap > 0: orders.append(Order(product, my_ask, -sell_cap))

            # ==========================================
            # EXECUTION: EMERALDS (Untouched 10000 Peg)
            # ==========================================
            elif product == "EMERALDS":
                if is_warmed_up:
                    z_spread = (avg_spread - self.E_AVG_SPREAD_MEAN) / self.E_AVG_SPREAD_STD
                    z_imb = (avg_imb - self.E_AVG_IMBALANCE_MEAN) / self.E_AVG_IMBALANCE_STD
                    z_mdiv = (avg_mdiv - self.E_MICRO_DIVERGENCE_MEAN) / self.E_MICRO_DIVERGENCE_STD
                    z_vol = (avg_vol - self.E_VOLUME_MEAN) / self.E_VOLUME_STD
                    
                    alpha = (self.E_INTERCEPT + 
                             self.E_W_AVG_SPREAD * z_spread + 
                             self.E_W_AVG_IMBALANCE * z_imb + 
                             self.E_W_MICRO_DIVERGENCE * z_mdiv + 
                             self.E_W_VOLUME * z_vol)
                    
                    alpha = max(-2.0, min(2.0, alpha))
                else:
                    alpha = 0.0 
                
                fair_price = 10000 + (alpha * 0.5)

                buy_edge_required = (current_pos / limit) * 1.5
                sell_edge_required = -(current_pos / limit) * 1.5

                for ask_p, ask_v in sorted_asks:
                    if ask_p <= 9999 or ask_p < fair_price - buy_edge_required: 
                        buy_qty = min(-ask_v, buy_cap)
                        if buy_qty > 0:
                            orders.append(Order(product, ask_p, buy_qty))
                            buy_cap -= buy_qty; current_pos += buy_qty
                            
                for bid_p, bid_v in sorted_bids:
                    if bid_p >= 10001 or bid_p > fair_price + sell_edge_required:
                        sell_qty = min(bid_v, sell_cap)
                        if sell_qty > 0:
                            orders.append(Order(product, bid_p, -sell_qty))
                            sell_cap -= sell_qty; current_pos -= sell_qty
                
                skew = (current_pos / limit) * 4.0
                ideal_bid = fair_price - 2.0 - skew
                ideal_ask = fair_price + 2.0 - skew
                
                my_bid = int(math.floor(min(best_bid + 1, ideal_bid)))
                my_ask = int(math.ceil(max(best_ask - 1, ideal_ask)))

                if my_bid >= my_ask: my_bid = my_ask - 1

                if vpin > 0.20:
                    if tot_rolling_sell > tot_rolling_buy:
                        my_bid -= 3 
                    elif tot_rolling_buy > tot_rolling_sell:
                        my_ask += 3

                my_bid = min(my_bid, best_ask - 1)
                my_ask = max(my_ask, best_bid + 1)

                if buy_cap > 0: orders.append(Order(product, my_bid, buy_cap))
                if sell_cap > 0: orders.append(Order(product, my_ask, -sell_cap))

            result[product] = orders

        traderData = json.dumps(trader_state)
        return result, conversions, traderData