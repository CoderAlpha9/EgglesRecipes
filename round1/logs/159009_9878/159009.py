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
        
        trader_state = {
            "OFI_STATE": {},  
            "OU_STATE": {},
            "BB_STATE": {},
            "PEPPER_STATE": {}
        }
        
        if state.traderData:
            try:
                trader_state = json.loads(state.traderData)
            except Exception:
                pass

        for product in state.order_depths:
            # We only process Osmium and Pepper Root
            if product not in self.POSITION_LIMITS:
                continue

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

            current_pos = state.position.get(product, 0)
            limit = self.POSITION_LIMITS.get(product, 80)
            buy_cap = limit - current_pos
            sell_cap = limit + current_pos

            # ==========================================
            # STRATEGY 1: ASH_COATED_OSMIUM (Exact Tomatoes Strategy)
            # ==========================================
            if product == "ASH_COATED_OSMIUM":
                
                # ------------------------------------------
                # 1. ORNSTEIN-UHLENBECK ESTIMATOR (Rolling EMA)
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
                # 2. MICROSTRUCTURE: O.F.I. & MICRO-PRICE
                # ------------------------------------------
                prev_state = trader_state["OFI_STATE"].get(product, {"b_p": best_bid, "b_v": 0, "a_p": best_ask, "a_v": 0})
                
                ofi_bid = best_bid_vol if best_bid > prev_state["b_p"] else (best_bid_vol - prev_state["b_v"] if best_bid == prev_state["b_p"] else -prev_state["b_v"])
                ofi_ask = best_ask_vol if best_ask < prev_state["a_p"] else (best_ask_vol - prev_state["a_v"] if best_ask == prev_state["a_p"] else -prev_state["a_v"])
                tick_ofi = ofi_bid - ofi_ask
                trader_state["OFI_STATE"][product] = {"b_p": best_bid, "b_v": best_bid_vol, "a_p": best_ask, "a_v": best_ask_vol}

                total_bid_vol = sum(order_depth.buy_orders.values())
                total_ask_vol = sum(-v for v in order_depth.sell_orders.values())
                total_book_vol = total_bid_vol + total_ask_vol
                
                micro_price = (best_bid * total_ask_vol + best_ask * total_bid_vol) / total_book_vol if total_book_vol > 0 else mid_price

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

                # --- DYNAMIC NON-OVERFIT FAIR PRICE ---
                fair_price = micro_price + ou_drift - (tick_ofi / 8.0)

                # --- DYNAMIC SPREADS & STAGNATION GUARD ---
                stagnation_penalty = 0.0
                base_taker_edge = 0.4
                if bb_std < 1.0: 
                    base_taker_edge = 0.2
                    stagnation_penalty = 1.0

                pos_ratio = current_pos / limit
                pos_skew = (abs(pos_ratio) ** 2) * math.copysign(1, pos_ratio)
                
                buy_edge_required = base_taker_edge + pos_skew * 10.0
                sell_edge_required = base_taker_edge - pos_skew * 10.0

                # --- BROWNIAN EXTREME EXPLOITATION ---
                if mid_price <= bb_lower:
                    buy_edge_required -= 1.5 
                if mid_price >= bb_upper:
                    sell_edge_required -= 1.5 

                # --- TAKER SWEEPER ---
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

                # --- MAKER QUOTING ---
                skew = pos_skew * 5.0
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

        traderData = json.dumps(trader_state)
        return result, conversions, traderData