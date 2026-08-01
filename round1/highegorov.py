"""
highest_stable.py — Egorov Regime Edition
==========================================

Original strategies:
    ASH_COATED_OSMIUM     — simple penny market-making (±1 tick inside spread)
    INTARIAN_PEPPER_ROOT  — sweep all asks aggressively up to position limit

What Egorov adds:
    We treat the rolling window of mid-price deviations as a finite measure
    space (each tick has weight 1/N).  Our EMA estimators converge pointwise
    to the true parameters, but Egorov's theorem guarantees that convergence
    is *uniform* only off an exceptional set E with μ(E) < ε.

    Empirical exceptional set:
        Ê  = { t : |dev_t| > δ · σ_t }
        ε̂  = |Ê| / N

    ε̂ ≤ ε  →  normal regime  — estimators reliable, tight quotes / sweep asks
    ε̂ >  ε  →  exceptional    — regime break, widen quotes / bid at discount

Changes vs. original:
    1. _update_ema_var()   – shared EMA + variance helper (replaces repeated logic)
    2. _egorov_regime()    – detects exceptional set from deviation history
    3. OSMIUM              – spread widens proportionally to ε̂ in exceptional regime;
                             maintains tight penny quoting in normal regime
    4. PEPPER              – in exceptional regime places a discount bid (EMA − σ)
                             instead of blindly sweeping all ask levels
    5. traderData          – added persistent state for EMA / Egorov window
"""

import json
import math
from datamodel import OrderDepth, TradingState, Order
from typing import List, Tuple


class Trader:

    POSITION_LIMITS = {
        "ASH_COATED_OSMIUM":    80,
        "INTARIAN_PEPPER_ROOT": 80,
    }

    # ── Egorov hyper-parameters ────────────────────────────────────────── #
    EGOROV_WINDOW  : int   = 20    # N  – rolling window size (finite measure space)
    EGOROV_EPSILON : float = 0.10  # ε  – max acceptable measure of exceptional set
    EGOROV_DELTA   : float = 2.5   # δ  – outlier threshold (multiples of σ)

    # ── EMA hyper-parameters ───────────────────────────────────────────── #
    BB_ALPHA  : float = 0.15   # Bollinger EMA speed (OSMIUM)
    PEP_ALPHA : float = 0.20   # Ask-price EMA speed (PEPPER)

    # ──────────────────────────────────────────────────────────────────── #
    #  Helpers                                                              #
    # ──────────────────────────────────────────────────────────────────── #

    def _update_ema_var(
        self,
        alpha: float,
        prev_ema: float,
        prev_var: float,
        value: float,
    ) -> Tuple[float, float, float]:
        """One-step EMA + variance.  Returns (new_ema, new_var, deviation)."""
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

        Returns
        -------
        in_exceptional : bool    True  → inside E (uniform convergence broken)
        epsilon_hat    : float   ε̂ = |Ê| / N
        """
        if std <= 0.0 or len(dev_history) < 5:
            return False, 0.0

        threshold   = self.EGOROV_DELTA * std
        bad_count   = sum(1 for d in dev_history if abs(d) > threshold)
        epsilon_hat = bad_count / len(dev_history)

        return epsilon_hat > self.EGOROV_EPSILON, epsilon_hat

    # ──────────────────────────────────────────────────────────────────── #
    #  Main entry point                                                     #
    # ──────────────────────────────────────────────────────────────────── #

    def run(self, state: TradingState):
        result     = {}
        conversions = 0

        # Persistent state
        trader_state: dict = {
            "OSM_EG":  {},   # OSMIUM  – {ema, var, devs}
            "PEP_EG":  {},   # PEPPER  – {ema, var, devs}
        }
        if state.traderData:
            try:
                loaded = json.loads(state.traderData)
                for k in trader_state:
                    trader_state[k] = loaded.get(k, trader_state[k])
            except Exception:
                pass

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order]     = []
            position = state.position.get(product, 0)

            if not order_depth.sell_orders or not order_depth.buy_orders:
                result[product] = orders
                continue

            best_ask = min(order_depth.sell_orders.keys())
            best_bid = max(order_depth.buy_orders.keys())
            mid_price = (best_bid + best_ask) / 2.0

            # ==============================================================
            # STRATEGY 1 – ASH_COATED_OSMIUM
            # Original: penny inside spread (best_bid+1 / best_ask-1)
            # Egorov:   spread multiplier widens when ε̂ > ε
            # ==============================================================
            if product == "ASH_COATED_OSMIUM":
                limit = self.POSITION_LIMITS[product]

                # ── EMA + Egorov regime ───────────────────────────────────
                eg = trader_state["OSM_EG"].get(
                    product, {"ema": mid_price, "var": 1.0, "devs": []}
                )
                new_ema, new_var, dev = self._update_ema_var(
                    self.BB_ALPHA, eg["ema"], eg["var"], mid_price
                )
                devs = (eg["devs"] + [dev])[-self.EGOROV_WINDOW:]
                trader_state["OSM_EG"][product] = {"ema": new_ema, "var": new_var, "devs": devs}

                std = math.sqrt(new_var) if new_var > 0 else 1.0
                in_exceptional, epsilon_hat = self._egorov_regime(devs, std)

                # ── Regime-gated spread multiplier ────────────────────────
                #   Normal      → stay 1 tick inside (original behaviour)
                #   Exceptional → spread widens with ε̂; don't penny a
                #                 market whose variance estimate is unreliable
                if in_exceptional:
                    # ε̂ ∈ (0.10, 1.0] → extra_ticks ∈ (0, ~4]
                    extra_ticks = int(math.ceil(epsilon_hat * 4.0))
                else:
                    extra_ticks = 0

                my_bid = best_bid + 1 - extra_ticks
                my_ask = best_ask - 1 + extra_ticks

                # Fallback: never cross the spread
                if my_bid >= my_ask:
                    my_bid = best_bid
                    my_ask = best_ask

                max_buy_volume  =  limit - position
                max_sell_volume = -limit - position

                if max_buy_volume  > 0: orders.append(Order(product, my_bid,  max_buy_volume))
                if max_sell_volume < 0: orders.append(Order(product, my_ask,  max_sell_volume))

            # ==============================================================
            # STRATEGY 2 – INTARIAN_PEPPER_ROOT
            # Original: sweep every ask level up to position limit
            # Egorov:   in exceptional regime, bid at EMA−σ (discount) instead
            # ==============================================================
            elif product == "INTARIAN_PEPPER_ROOT":
                limit = self.POSITION_LIMITS[product]

                # ── EMA + Egorov regime ───────────────────────────────────
                eg = trader_state["PEP_EG"].get(
                    product, {"ema": float(best_ask), "var": 1.0, "devs": []}
                )
                new_ema, new_var, dev = self._update_ema_var(
                    self.PEP_ALPHA, eg["ema"], eg["var"], float(best_ask)
                )
                devs = (eg["devs"] + [dev])[-self.EGOROV_WINDOW:]
                trader_state["PEP_EG"][product] = {"ema": new_ema, "var": new_var, "devs": devs}

                std = math.sqrt(new_var) if new_var > 0 else 1.0
                in_exceptional, _ = self._egorov_regime(devs, std)

                max_buy_volume = limit - position
                if max_buy_volume > 0:

                    if in_exceptional:
                        # ── Exceptional regime ────────────────────────────
                        # Uniform convergence broken → ask price is deviating
                        # structurally from its EMA.  Place a single passive
                        # bid at EMA − σ to accumulate at a discount rather
                        # than chasing a potentially inflated ask.
                        discount_price = int(math.floor(new_ema - std))
                        my_bid         = max(best_bid, min(discount_price, best_ask - 1))
                        orders.append(Order(product, my_bid, max_buy_volume))

                    else:
                        # ── Normal regime ─────────────────────────────────
                        # Estimators reliable → sweep all ask levels as before.
                        remaining = max_buy_volume
                        for ask_price in sorted(order_depth.sell_orders.keys()):
                            if remaining <= 0:
                                break
                            ask_vol  = -order_depth.sell_orders[ask_price]   # positive
                            fill_vol = min(remaining, ask_vol)
                            orders.append(Order(product, ask_price, fill_vol))
                            remaining -= fill_vol

            result[product] = orders

        traderData = json.dumps(trader_state)
        return result, conversions, traderData