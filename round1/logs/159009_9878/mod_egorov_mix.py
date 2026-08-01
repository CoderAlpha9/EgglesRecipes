"""
Trading strategy with Egorov Regime Detection
==============================================
Egorov's theorem (measure theory):
    If f_n → f pointwise on a finite measure space (Ω, μ), then for every ε > 0
    there exists a measurable set E with μ(E) < ε such that f_n → f *uniformly*
    on the complement Ω \\ E.

Application:
    Treat our rolling window of price deviations as a finite measure space
    (uniform measure, each tick carries weight 1/N).  Our EMA estimators converge
    pointwise to the "true" parameters, but Egorov guarantees that convergence is
    uniform EVERYWHERE except on a set E whose measure we can bound.

    We estimate E empirically:
        Ê = { t : |dev_t| > δ · σ_t }         (outlier timesteps)
        ε̂ = |Ê| / N                             (empirical exceptional measure)

    When ε̂ > EGOROV_EPSILON  →  we are *inside* the exceptional set E.
        • Estimators are unreliable (convergence not uniform here).
        • Widen spreads, trust OU mean-reversion more, reduce taker aggression.

    When ε̂ ≤ EGOROV_EPSILON  →  we are on Ω \\ E (normal regime).
        • Uniform convergence holds; trust Bollinger / micro-price signals fully.
        • Tighter spreads, normal taker edge, exploit Bollinger extremes aggressively.

Key changes vs. original:
    1.  _update_ema_var()   – DRY helper for EMA + variance update.
    2.  _egorov_regime()    – Egorov exceptional-set detector.
    3.  OSMIUM strategy     – spread multiplier, OU weight, and taker edge all
                              gate on Egorov regime.
    4.  PEPPER strategy     – uses EMA + σ discount-bid in exceptional regime
                              instead of the simple spike/no-spike binary.
"""

import json
import math
from datamodel import OrderDepth, TradingState, Order
from typing import List, Tuple


class Trader:
    # ------------------------------------------------------------------ #
    #  Position limits                                                     #
    # ------------------------------------------------------------------ #
    POSITION_LIMITS = {
        "ASH_COATED_OSMIUM":    80,
        "INTARIAN_PEPPER_ROOT": 80,
    }

    # ------------------------------------------------------------------ #
    #  Egorov hyper-parameters                                            #
    # ------------------------------------------------------------------ #
    EGOROV_WINDOW  : int   = 20    # N  – size of finite measure space (rolling window)
    EGOROV_EPSILON : float = 0.10  # ε  – max acceptable measure of exceptional set
    EGOROV_DELTA   : float = 2.5   # δ  – outlier threshold in units of σ

    # ------------------------------------------------------------------ #
    #  EMA hyper-parameters                                               #
    # ------------------------------------------------------------------ #
    OU_ALPHA   : float = 0.05   # slow mean for OU estimator
    BB_ALPHA   : float = 0.15   # faster EMA for Bollinger bands
    PEP_ALPHA  : float = 0.20   # ask-price EMA for Pepper Root

    # ------------------------------------------------------------------ #
    #  Helpers                                                            #
    # ------------------------------------------------------------------ #

    def _update_ema_var(
        self,
        alpha: float,
        prev_ema: float,
        prev_var: float,
        value: float,
    ) -> Tuple[float, float, float]:
        """
        One-step exponential moving average + variance update.

        Returns
        -------
        new_ema : float
        new_var : float
        dev     : float   (value - prev_ema, i.e. the deviation *before* update)
        """
        dev     = value - prev_ema
        new_ema = alpha * value + (1.0 - alpha) * prev_ema
        new_var = alpha * (dev ** 2) + (1.0 - alpha) * prev_var
        return new_ema, new_var, dev

    def _egorov_regime(
        self,
        dev_history: List[float],
        std: float,
    ) -> Tuple[bool, float]:
        """
        Egorov exceptional-set detector.

        Parameters
        ----------
        dev_history : list of recent deviations (the finite measure space)
        std         : current rolling standard deviation

        Returns
        -------
        in_exceptional : bool    True  → inside E (regime break, estimators unreliable)
                                 False → on Ω\\E (normal, uniform convergence holds)
        epsilon_hat    : float   empirical measure of E, ε̂ = |Ê|/N
        """
        if std <= 0.0 or len(dev_history) < 5:
            return False, 0.0

        threshold   = self.EGOROV_DELTA * std
        bad_count   = sum(1 for d in dev_history if abs(d) > threshold)
        epsilon_hat = bad_count / len(dev_history)

        return epsilon_hat > self.EGOROV_EPSILON, epsilon_hat

    # ------------------------------------------------------------------ #
    #  Main entry point                                                   #
    # ------------------------------------------------------------------ #

    def run(self, state: TradingState):
        result     = {}
        conversions = 0

        # Persistent state skeleton
        trader_state: dict = {
            "OFI_STATE":    {},
            "OU_STATE":     {},
            "BB_STATE":     {},
            "PEPPER_STATE": {},
            "EG_STATE":     {},   # Egorov deviation histories keyed by product
        }
        if state.traderData:
            try:
                loaded = json.loads(state.traderData)
                for k in trader_state:            # keep schema consistent
                    trader_state[k] = loaded.get(k, trader_state[k])
            except Exception:
                pass

        for product in state.order_depths:
            if product not in self.POSITION_LIMITS:
                continue

            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order]     = []

            if not order_depth.sell_orders or not order_depth.buy_orders:
                continue

            sorted_bids = sorted(order_depth.buy_orders.items(),  key=lambda x: x[0], reverse=True)
            sorted_asks = sorted(order_depth.sell_orders.items(), key=lambda x: x[0])

            best_bid, best_bid_vol = sorted_bids[0]
            best_ask, best_ask_vol = sorted_asks[0]
            best_ask_vol = -best_ask_vol            # convention: positive volume

            mid_price   = (best_bid + best_ask) / 2.0
            current_pos = state.position.get(product, 0)
            limit       = self.POSITION_LIMITS[product]
            buy_cap     = limit - current_pos
            sell_cap    = limit + current_pos

            # ==============================================================
            # STRATEGY 1 – ASH_COATED_OSMIUM
            # ==============================================================
            if product == "ASH_COATED_OSMIUM":

                # ── 1. Ornstein-Uhlenbeck mean estimator ──────────────────
                ou_state = trader_state["OU_STATE"].get(
                    product, {"mu": mid_price, "var": 1.0}
                )
                if ou_state["mu"] == 0:
                    ou_state["mu"] = mid_price

                new_mu, new_ou_var, _ = self._update_ema_var(
                    self.OU_ALPHA, ou_state["mu"], ou_state["var"], mid_price
                )
                trader_state["OU_STATE"][product] = {"mu": new_mu, "var": new_ou_var}

                # ── 2. Order-flow imbalance & micro-price ─────────────────
                prev_ofi = trader_state["OFI_STATE"].get(
                    product, {"b_p": best_bid, "b_v": 0, "a_p": best_ask, "a_v": 0}
                )

                def ofi_delta(new_p, new_v, old_p, old_v):
                    if new_p > old_p:   return  new_v
                    if new_p == old_p:  return  new_v - old_v
                    return -old_v

                tick_ofi = (
                    ofi_delta(best_bid, best_bid_vol, prev_ofi["b_p"], prev_ofi["b_v"])
                  - ofi_delta(best_ask, best_ask_vol, prev_ofi["a_p"], prev_ofi["a_v"])
                )
                trader_state["OFI_STATE"][product] = {
                    "b_p": best_bid,  "b_v": best_bid_vol,
                    "a_p": best_ask,  "a_v": best_ask_vol,
                }

                total_bid_vol  = sum(order_depth.buy_orders.values())
                total_ask_vol  = sum(-v for v in order_depth.sell_orders.values())
                total_book_vol = total_bid_vol + total_ask_vol
                micro_price = (
                    (best_bid * total_ask_vol + best_ask * total_bid_vol) / total_book_vol
                    if total_book_vol > 0 else mid_price
                )

                # ── 3. Bollinger EMA ──────────────────────────────────────
                bb_state = trader_state["BB_STATE"].get(
                    product, {"ema": mid_price, "var": 1.0}
                )
                if bb_state["ema"] == 0:
                    bb_state["ema"] = mid_price

                new_ema, new_var_bb, dev_bb = self._update_ema_var(
                    self.BB_ALPHA, bb_state["ema"], bb_state["var"], mid_price
                )
                trader_state["BB_STATE"][product] = {"ema": new_ema, "var": new_var_bb}
                bb_std = math.sqrt(new_var_bb) if new_var_bb > 0 else 1.0

                # ── 4. Egorov regime detection ────────────────────────────
                eg_state   = trader_state["EG_STATE"].get(product, {"devs": []})
                dev_history = eg_state["devs"]
                dev_history.append(dev_bb)
                dev_history = dev_history[-self.EGOROV_WINDOW:]          # keep window fixed
                trader_state["EG_STATE"][product] = {"devs": dev_history}

                in_exceptional, epsilon_hat = self._egorov_regime(dev_history, bb_std)

                # ── 5. Regime-gated parameters ────────────────────────────
                #
                #  Egorov guarantee:  on Ω\E our estimators converge uniformly
                #  → trust signals fully, tight spreads.
                #
                #  Inside E          our estimators are unreliable
                #  → inflate spreads proportionally to ε̂, increase OU weight,
                #    reduce taker aggression.
                #
                if in_exceptional:
                    # Spread widens linearly with empirical measure of exceptional set.
                    # ε̂ ∈ (0.10, 1.0]  →  spread_mult ∈ (1.30, 3.70]
                    spread_mult      = 1.0 + epsilon_hat * 2.7
                    extra_taker_edge = 1.5          # much harder to justify taking
                    ou_weight        = 0.60         # trust long-run mean more
                    bb_exploit       = 0.5          # cautious Bollinger exploitation
                else:
                    spread_mult      = 1.0
                    extra_taker_edge = 0.0
                    ou_weight        = 0.25
                    bb_exploit       = 1.5          # full Bollinger exploitation

                # Egorov-scaled Bollinger bands
                bb_upper = new_ema + 2.0 * bb_std * spread_mult
                bb_lower = new_ema - 2.0 * bb_std * spread_mult

                # ── 6. Fair price ─────────────────────────────────────────
                ou_drift   = ou_weight * (new_mu - mid_price)
                fair_price = micro_price + ou_drift - (tick_ofi / 8.0)

                # ── 7. Dynamic spreads & stagnation guard ─────────────────
                stagnation_penalty = 0.0
                base_taker_edge    = 0.4 + extra_taker_edge
                if bb_std < 1.0:
                    base_taker_edge    = max(0.2, base_taker_edge)
                    stagnation_penalty = 1.0 * spread_mult

                pos_ratio  = current_pos / limit
                pos_skew   = (abs(pos_ratio) ** 2) * math.copysign(1.0, pos_ratio)

                buy_edge_required  = base_taker_edge + pos_skew * 10.0
                sell_edge_required = base_taker_edge - pos_skew * 10.0

                # Bollinger extreme exploitation — scaled by regime
                if mid_price <= bb_lower:
                    buy_edge_required  -= bb_exploit
                if mid_price >= bb_upper:
                    sell_edge_required -= bb_exploit

                # ── 8. Taker sweeper ──────────────────────────────────────
                for ask_p, ask_v in sorted_asks:
                    if ask_p < fair_price - buy_edge_required:
                        buy_qty = min(-ask_v, buy_cap)
                        if buy_qty > 0:
                            orders.append(Order(product, ask_p, buy_qty))
                            buy_cap     -= buy_qty
                            current_pos += buy_qty

                for bid_p, bid_v in sorted_bids:
                    if bid_p > fair_price + sell_edge_required:
                        sell_qty = min(bid_v, sell_cap)
                        if sell_qty > 0:
                            orders.append(Order(product, bid_p, -sell_qty))
                            sell_cap    -= sell_qty
                            current_pos -= sell_qty

                # ── 9. Maker quoting ──────────────────────────────────────
                skew            = pos_skew * 5.0
                half_spread     = 1.5 * spread_mult
                ideal_bid       = fair_price - half_spread - skew - stagnation_penalty
                ideal_ask       = fair_price + half_spread - skew + stagnation_penalty

                my_bid = int(math.floor(min(best_bid + 1, ideal_bid)))
                my_ask = int(math.ceil( max(best_ask - 1, ideal_ask)))

                if my_bid >= my_ask:
                    my_bid = my_ask - 1
                my_bid = min(my_bid, best_ask - 1)
                my_ask = max(my_ask, best_bid + 1)

                if buy_cap  > 0: orders.append(Order(product, my_bid,  buy_cap))
                if sell_cap > 0: orders.append(Order(product, my_ask, -sell_cap))

            # ==============================================================
            # STRATEGY 2 – INTARIAN_PEPPER_ROOT
            # Egorov-enhanced accumulation: track ask-price regime to time entries
            # ==============================================================
            elif product == "INTARIAN_PEPPER_ROOT":

                pep = trader_state["PEPPER_STATE"]
                if "ask_ema" not in pep:
                    pep.update({
                        "prev_ask": best_ask,
                        "ask_ema":  float(best_ask),
                        "ask_var":  1.0,
                        "ask_devs": [],
                    })

                prev_ask = pep["prev_ask"]

                # EMA of ask price
                new_ask_ema, new_ask_var, ask_dev = self._update_ema_var(
                    self.PEP_ALPHA, pep["ask_ema"], pep["ask_var"], float(best_ask)
                )
                ask_std  = math.sqrt(new_ask_var) if new_ask_var > 0 else 1.0
                ask_devs = pep["ask_devs"]
                ask_devs.append(ask_dev)
                ask_devs = ask_devs[-self.EGOROV_WINDOW:]

                # Egorov check on ask-price stream
                in_exceptional_pep, _ = self._egorov_regime(ask_devs, ask_std)

                # Persist
                pep["prev_ask"]  = best_ask
                pep["ask_ema"]   = new_ask_ema
                pep["ask_var"]   = new_ask_var
                pep["ask_devs"]  = ask_devs
                trader_state["PEPPER_STATE"] = pep

                max_buy = limit - current_pos
                if max_buy > 0:

                    if in_exceptional_pep:
                        # ── Exceptional regime ────────────────────────────
                        # Uniform convergence broken → price is structurally
                        # departing from its EMA trajectory.  Use Egorov bound
                        # to place a discount bid at  EMA - σ  (one std below
                        # rolling fair value) rather than chasing the ask.
                        discount_level = int(math.floor(new_ask_ema - ask_std))
                        my_bid         = max(best_bid, min(discount_level, best_ask - 2))
                        orders.append(Order(product, my_bid, max_buy))

                    elif best_ask <= prev_ask:
                        # ── Normal regime, price stable / falling ─────────
                        # Estimators reliable → safely lift the ask.
                        orders.append(Order(product, best_ask, max_buy))

                    else:
                        # ── Normal regime, short-term spike ───────────────
                        # Passively queue one tick above best bid.
                        my_bid = best_bid + 1
                        if my_bid >= best_ask:
                            my_bid = best_bid
                        orders.append(Order(product, my_bid, max_buy))

            result[product] = orders

        traderData = json.dumps(trader_state)
        return result, conversions, traderData