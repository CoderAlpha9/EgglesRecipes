import json
import math
import statistics
from datamodel import OrderDepth, TradingState, Order
from typing import List, Tuple

class RegimeClassifier:
    # --- Tuned for 100ms High-Frequency Micro-Price Data ---
    LONG_WINDOW = 200       # 10 seconds of macro-trend history
    SHORT_WINDOW = 10       # 2 seconds of micro-chop history
    SLOPE_MOM_WINDOW = 15   # 1 second of slope momentum lookback

    # --- Trained TREND thresholds (85th Percentile) ---
    R2_TREND_THRESH = 0.70
    SLOPE_TREND_THRESH = 0.078

    # --- Trained MR thresholds (30th Percentile) ---
    ACF_MR_THRESH = -0.48
    ER_MR_THRESH = 0.06

    def classify(self, micro_hist: List[float], slope_hist: List[float]) -> Tuple[str, int, float, float]:
        if len(micro_hist) < self.LONG_WINDOW:
            return "NEUTRAL", 0, 0.0, 0.0

        macro_chunk = micro_hist[-self.LONG_WINDOW:]
        slope, r2 = self._linreg_slope_r2(macro_chunk)

        slope_hist.append(slope)
        slope_building = True

        if len(slope_hist) >= self.SLOPE_MOM_WINDOW:
            old_slope = slope_hist[-self.SLOPE_MOM_WINDOW]
            if slope > 0:
                slope_building = slope >= old_slope * 0.80
            elif slope < 0:
                slope_building = slope <= old_slope * 0.80

        micro_chunk = micro_hist[-self.SHORT_WINDOW:]
        micro_rets = [micro_chunk[i] - micro_chunk[i - 1] for i in range(1, len(micro_chunk))]

        micro_net = abs(micro_chunk[-1] - micro_chunk[0])
        micro_path = sum(abs(r) for r in micro_rets)

        micro_er = micro_net / micro_path if micro_path > 0 else 0.0
        micro_acf = self._acf1(micro_rets)

        regime, direction = self._classify_regime(r2, slope, micro_acf, micro_er, slope_building)
        return regime, direction, slope, r2

    def _classify_regime(self, r2, slope, micro_acf, micro_er, slope_building):
        # A true structural breakout
        if r2 > self.R2_TREND_THRESH and abs(slope) > self.SLOPE_TREND_THRESH and slope_building:
            direction = -1 if slope < 0 else 1
            return "TREND", direction

        # A highly noisy, mean-reverting chop channel
        if micro_acf < self.ACF_MR_THRESH and micro_er < self.ER_MR_THRESH:
            return "MEAN_REVERSION", 0

        return "NEUTRAL", 0

    def _linreg_slope_r2(self, series):
        n = len(series)
        if n < 4: return 0.0, 0.0

        xm = (n - 1) / 2.0
        ym = statistics.mean(series)

        ssxy = sum((i - xm) * (series[i] - ym) for i in range(n))
        ssxx = sum((i - xm) ** 2 for i in range(n))
        ssy = sum((series[i] - ym) ** 2 for i in range(n))

        if ssxx < 1e-9 or ssy < 1e-9: return 0.0, 0.0

        slope = ssxy / ssxx
        r2 = (ssxy ** 2) / (ssxx * ssy)
        return slope, r2

    def _acf1(self, rets):
        if len(rets) < 4: return 0.0

        r0 = rets[:-1]
        r1 = rets[1:]

        m0 = statistics.mean(r0)
        m1 = statistics.mean(r1)

        num = sum((a - m0) * (b - m1) for a, b in zip(r0, r1))
        den0 = sum((x - m0) ** 2 for x in r0)
        den1 = sum((x - m1) ** 2 for x in r1)

        denom = math.sqrt(den0 * den1)
        if denom < 1e-9: return 0.0

        return num / denom


class Trader:
    POSITION_LIMITS = {
        "EMERALDS": 80,
        "TOMATOES": 80
    }

    # ==========================================
    # --- MODEL WEIGHTS & SCALARS (STATIC CV) ---
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

    def __init__(self):
        self.regime_classifier = RegimeClassifier()

    def run(self, state: TradingState):
        result = {}
        conversions = 0
        
        trader_state = {
            "EMERALDS_FEAT": {"spread":[], "imb":[], "mdiv":[], "vol":[]},
            "TOMATOES_FEAT": {"spread":[], "imb":[], "mdiv":[], "vol":[], "micro_hist":[], "slope_hist":[]},
            "OFI_STATE": {},  
            "OU_STATE": {},
            "BB_STATE": {} 
        }
        
        if state.traderData:
            try:
                trader_state = json.loads(state.traderData)
            except Exception:
                pass
                
        window_len = 10 

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
            # 0. ORNSTEIN-UHLENBECK ESTIMATOR
            # ------------------------------------------
            ou_alpha = 0.05 
            ou_state = trader_state["OU_STATE"].get(product, {"mu": mid_price, "var": 1.0})
            if ou_state["mu"] == 0: ou_state["mu"] = mid_price
            
            new_mu = ou_state["mu"] + ou_alpha * (mid_price - ou_state["mu"])
            dev = mid_price - ou_state["mu"]
            new_var = ou_state["var"] + ou_alpha * ((dev ** 2) - ou_state["var"])
            
            trader_state["OU_STATE"][product] = {"mu": new_mu, "var": new_var}
            ou_drift = 0.25 * (new_mu - mid_price)

            # ------------------------------------------
            # 1. MICROSTRUCTURE: O.F.I. 
            # ------------------------------------------
            prev_state = trader_state["OFI_STATE"].get(product, {"b_p": best_bid, "b_v": 0, "a_p": best_ask, "a_v": 0})
            
            ofi_bid = best_bid_vol if best_bid > prev_state["b_p"] else (best_bid_vol - prev_state["b_v"] if best_bid == prev_state["b_p"] else -prev_state["b_v"])
            ofi_ask = best_ask_vol if best_ask < prev_state["a_p"] else (best_ask_vol - prev_state["a_v"] if best_ask == prev_state["a_p"] else -prev_state["a_v"])
            tick_ofi = ofi_bid - ofi_ask
            trader_state["OFI_STATE"][product] = {"b_p": best_bid, "b_v": best_bid_vol, "a_p": best_ask, "a_v": best_ask_vol}

            # ------------------------------------------
            # 2. BASE FEATURES & Z-SCORES
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
            feats["mdiv"].append(tick_mdiv); feats["vol"].append(0) # Deprecated volume tracking
            
            # --- UPGRADE: Tracking Micro-Price for Smooth Regime Classification ---
            if "micro_hist" in feats:
                feats["micro_hist"].append(micro_price)
                if len(feats["micro_hist"]) > self.regime_classifier.LONG_WINDOW: 
                    feats["micro_hist"].pop(0)
            
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
            # EXECUTION: TOMATOES (Regime + 63890 Baseline)
            # ==========================================
            if product == "TOMATOES":
                
                # --- ZERO-LAG EMA BOLLINGER ---
                alpha_ema = 0.15 
                bb_state = trader_state["BB_STATE"].get(product, {"ema": mid_price, "var": 1.0})
                if bb_state["ema"] == 0: bb_state["ema"] = mid_price
                
                new_ema = (alpha_ema * mid_price) + ((1 - alpha_ema) * bb_state["ema"])
                dev_bb = mid_price - new_ema
                new_var_bb = (alpha_ema * (dev_bb ** 2)) + ((1 - alpha_ema) * bb_state["var"])
                
                trader_state["BB_STATE"][product] = {"ema": new_ema, "var": new_var_bb}
                bb_std = math.sqrt(new_var_bb) if new_var_bb > 0 else 1.0
                bb_upper = new_ema + (2.0 * bb_std)
                bb_lower = new_ema - (2.0 * bb_std)

                # --- 🎯 MICRO-PRICE REGIME DETECTION 🎯 ---
                regime, direction = "NEUTRAL", 0
                if len(feats["micro_hist"]) >= self.regime_classifier.LONG_WINDOW:
                    regime, direction, slope, r2 = self.regime_classifier.classify(feats["micro_hist"], feats["slope_hist"])
                    if len(feats["slope_hist"]) > self.regime_classifier.SLOPE_MOM_WINDOW + 2:
                        feats["slope_hist"].pop(0)

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
                
                fair_price = mid_price + alpha + ou_drift

                # --- REGIME-SCALED EDGES ---
                stagnation_penalty = 0.0
                base_taker_edge = 0.4 # Default 2.8K baseline

                if regime == "TREND":
                    # Wide edge to protect from adverse selection during breakouts
                    base_taker_edge = 0.5 
                elif regime == "MEAN_REVERSION":
                    # Aggressive edge to farm the micro-chop
                    base_taker_edge = 0.3 
                elif bb_std < 1.0: 
                    # The 111k-150k Stagnation Desert Failsafe
                    base_taker_edge = 0.2
                    stagnation_penalty = 1.0

                # --- UPGRADE: SYMMETRIC CUBIC SKEW ---
                # Pos_skew naturally preserves its sign (e.g., -0.5^3 = -0.125).
                # This guarantees the bot trades out of Short positions just as aggressively as Long positions.
                pos_skew = (current_pos / limit) ** 3
                buy_edge_required = base_taker_edge + pos_skew * 6.0
                sell_edge_required = base_taker_edge - pos_skew * 6.0

                # --- TREND FILTERED REVERSION (FIXED) ---
                # We only catch the bottom if we are NOT in a confirmed downtrend
                if mid_price <= bb_lower:
                    if not (regime == "TREND" and direction == -1):
                        buy_edge_required -= 1.5 
                
                # We only short the top if we are NOT in a confirmed uptrend
                if mid_price >= bb_upper:
                    if not (regime == "TREND" and direction == 1):
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

                # --- PROVEN MAKER QUOTING ---
                skew = (current_pos / limit) * 4.0
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
            # EXECUTION: EMERALDS (Untouched 2.8K Baseline)
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

                pos_ratio = current_pos / limit
                buy_edge_required = 1.5 + (pos_ratio * 3.0)
                sell_edge_required = 1.5 - (pos_ratio * 3.0)

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
                
                skew = pos_ratio * 4.0
                ideal_bid = fair_price - 2.0 - skew
                ideal_ask = fair_price + 2.0 - skew
                
                my_bid = int(math.floor(min(best_bid + 1, ideal_bid)))
                my_ask = int(math.ceil(max(best_ask - 1, ideal_ask)))

                if my_bid >= my_ask: my_bid = my_ask - 1
                my_bid = min(my_bid, best_ask - 1)
                my_ask = max(my_ask, best_bid + 1)

                if buy_cap > 0: orders.append(Order(product, my_bid, buy_cap))
                if sell_cap > 0: orders.append(Order(product, my_ask, -sell_cap))

            result[product] = orders

        traderData = json.dumps(trader_state)
        return result, conversions, traderData