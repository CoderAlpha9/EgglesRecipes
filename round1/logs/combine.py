import json
import math
from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict

"""
=============================================================================
IMC PROSPERITY ROUND 1 — COMBINED OPTIMISED STRATEGY
=============================================================================

SYNTHESIS OF ALL FOUR APPROACHES:

ASH_COATED_OSMIUM (Mean-Reversion Market Maker):
  ┌─ Fair value: micro-price + OU drift − OFI adjustment (from 159009)
  │    Better than raw EMA mid — accounts for order-book imbalance and
  │    mean-reversion drift simultaneously.
  ├─ Bollinger Bands (from 159009): detect extremes to reduce edge on
  │    the reverting side and catch outsized moves.
  ├─ Tiered deviation quoting (from 179936/178838):
  │    Near fair  →  penny inside on both sides
  │    Moderate   →  extra penny on reverting side
  │    Strong     →  2/3 volume at -2 ticks, 1/3 at -1 tick (reverting)
  ├─ Position-skew on quotes (from 159009): nonlinear skew prevents
  │    getting pinned at position limits.
  ├─ End-of-day flattening (from 179936/178838): actually wired up
  │    (was defined but never called in those files).
  └─ One-sided book handling (from 179936/178838): post estimated
       quotes when one side of the book is empty.

INTARIAN_PEPPER_ROOT (Trend Follower / Max Long):
  ┌─ Sweep all ask levels aggressively to reach +80 ASAP (178838 style).
  │    Price rises ~+0.001/tick so every tick at sub-max position is lost
  │    profit. No price cap needed — we always want to be long.
  └─ Never go short; never market-make; just accumulate and hold.

KEY IMPROVEMENTS OVER EACH INDIVIDUAL FILE:
  • highclaude:  EMA-only fair value replaced by richer micro-price + OU
  • 179936/838:  _flatten_position now actually called at LIQUIDATION_TS
  • 159009:      tiered multi-level quoting added for better fill rates
                 on the reverting side; pepper no longer hesitates on spikes
=============================================================================
"""

POSITION_LIMIT = 80
LIQUIDATION_TS = 97_000     # Begin flattening ~3k ticks before day end


class Trader:

    # ─────────────────────────────────────────────────────────────────────
    # OSMIUM CONSTANTS
    # ─────────────────────────────────────────────────────────────────────
    OSMIUM_MEAN     = 10_000
    HALF_SPREAD_EST = 8        # Fallback half-spread for one-sided books

    # Fair value weights
    OU_ALPHA        = 0.05     # OU rolling EMA (slow, tracks long drift)
    BB_ALPHA        = 0.15     # Bollinger EMA (faster, tracks recent moves)
    OFI_SCALE       = 8.0      # Divisor for OFI adjustment to fair value

    # Quoting offsets
    BASE_HALF_SPREAD = 1.5     # Base half-spread around fair value
    STAGNATION_HALF  = 2.5     # Half-spread when BB std is very low
    POS_SKEW_MAX     = 5.0     # Max ticks of position skew on quotes
    TAKER_EDGE       = 0.4     # Min edge to cross the spread as taker
    BB_EXTREME_BONUS = 1.5     # Extra edge reduction at BB extremes

    # Tiered deviation thresholds (for extra aggression on reverting side)
    SKEW_THRESH        = 2     # Ticks deviation to trigger moderate skew
    STRONG_SKEW_THRESH = 4     # Ticks deviation for aggressive multi-level

    # ─────────────────────────────────────────────────────────────────────

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}

        trader_state: dict = {}
        if state.traderData:
            try:
                trader_state = json.loads(state.traderData)
            except Exception:
                trader_state = {}

        for product in state.order_depths:
            od: OrderDepth = state.order_depths[product]
            position = state.position.get(product, 0)

            if product == "ASH_COATED_OSMIUM":
                result[product] = self._trade_osmium(
                    product, od, position, state.timestamp, trader_state
                )
            elif product == "INTARIAN_PEPPER_ROOT":
                result[product] = self._trade_pepper(product, od, position)
            else:
                result[product] = []

        trader_data = json.dumps(trader_state)
        return result, 0, trader_data

    # ═════════════════════════════════════════════════════════════════════
    # OSMIUM: Micro-Price + OU + Bollinger + Tiered Quoting
    # ═════════════════════════════════════════════════════════════════════
    def _trade_osmium(self, product, od: OrderDepth, position, timestamp, ts):
        orders: List[Order] = []

        best_bid = max(od.buy_orders.keys())  if od.buy_orders  else None
        best_ask = min(od.sell_orders.keys()) if od.sell_orders else None

        # ── Mid / micro-price ─────────────────────────────────────────────
        if best_bid is not None and best_ask is not None:
            mid = (best_bid + best_ask) / 2.0
            total_bid_vol = sum(od.buy_orders.values())
            total_ask_vol = sum(-v for v in od.sell_orders.values())
            total_vol = total_bid_vol + total_ask_vol
            micro_price = (
                (best_bid * total_ask_vol + best_ask * total_bid_vol) / total_vol
                if total_vol > 0 else mid
            )
        elif best_bid is not None:
            mid = micro_price = float(best_bid)
        elif best_ask is not None:
            mid = micro_price = float(best_ask)
        else:
            return orders

        # ── OU estimator (rolling EMA of deviation from long-run mean) ────
        ou = ts.get("osm_ou", {"mu": mid, "var": 1.0})
        if ou["mu"] == 0:
            ou["mu"] = mid
        new_mu  = ou["mu"] + self.OU_ALPHA * (mid - ou["mu"])
        dev_ou  = mid - ou["mu"]
        new_var = ou["var"] + self.OU_ALPHA * (dev_ou ** 2 - ou["var"])
        ts["osm_ou"] = {"mu": new_mu, "var": new_var}
        ou_drift = 0.25 * (new_mu - mid)          # mean-reversion pull

        # ── Bollinger EMA + std ───────────────────────────────────────────
        bb = ts.get("osm_bb", {"ema": mid, "var": 1.0})
        if bb["ema"] == 0:
            bb["ema"] = mid
        new_bb_ema = self.BB_ALPHA * mid + (1 - self.BB_ALPHA) * bb["ema"]
        dev_bb     = mid - new_bb_ema
        new_bb_var = self.BB_ALPHA * dev_bb ** 2 + (1 - self.BB_ALPHA) * bb["var"]
        ts["osm_bb"] = {"ema": new_bb_ema, "var": new_bb_var}
        bb_std   = math.sqrt(new_bb_var) if new_bb_var > 0 else 1.0
        bb_upper = new_bb_ema + 2.0 * bb_std
        bb_lower = new_bb_ema - 2.0 * bb_std

        # ── OFI signal ────────────────────────────────────────────────────
        tick_ofi = 0.0
        if best_bid is not None and best_ask is not None:
            prev = ts.get("osm_ofi", {"b_p": best_bid, "b_v": 0, "a_p": best_ask, "a_v": 0})
            bid_vol = abs(od.buy_orders.get(best_bid, 0))
            ask_vol = abs(od.sell_orders.get(best_ask, 0))
            ofi_bid = (bid_vol if best_bid > prev["b_p"] else
                       (bid_vol - prev["b_v"] if best_bid == prev["b_p"] else -prev["b_v"]))
            ofi_ask = (ask_vol if best_ask < prev["a_p"] else
                       (ask_vol - prev["a_v"] if best_ask == prev["a_p"] else -prev["a_v"]))
            tick_ofi = ofi_bid - ofi_ask
            ts["osm_ofi"] = {"b_p": best_bid, "b_v": bid_vol, "a_p": best_ask, "a_v": ask_vol}

        # ── Fair value ────────────────────────────────────────────────────
        fair_price = micro_price + ou_drift - (tick_ofi / self.OFI_SCALE)

        # ── Deviation of mid from fair (used for tiered quoting) ──────────
        deviation = mid - fair_price

        # ── Position skew (nonlinear, from 159009) ────────────────────────
        pos_ratio = position / POSITION_LIMIT
        pos_skew  = (abs(pos_ratio) ** 2) * math.copysign(1, pos_ratio)  # [-1, +1]

        # ── Dynamic spread ────────────────────────────────────────────────
        stagnation_penalty = 0.0
        half_spread = self.BASE_HALF_SPREAD
        if bb_std < 1.0:
            half_spread = self.STAGNATION_HALF
            stagnation_penalty = 1.0

        buy_edge  = self.TAKER_EDGE + pos_skew  * 10.0
        sell_edge = self.TAKER_EDGE - pos_skew  * 10.0

        # Bollinger extreme: reduce edge on reverting side
        if mid <= bb_lower:
            buy_edge  -= self.BB_EXTREME_BONUS
        if mid >= bb_upper:
            sell_edge -= self.BB_EXTREME_BONUS

        max_buy  = POSITION_LIMIT - position
        max_sell = POSITION_LIMIT + position

        # ══════════════════════════════════════════════════════════════════
        # END-OF-DAY FLATTENING  (actually wired up, unlike 179936/178838)
        # ══════════════════════════════════════════════════════════════════
        if timestamp >= LIQUIDATION_TS:
            return self._flatten_position(
                product, od, position, best_bid, best_ask, max_buy, max_sell
            )

        # ══════════════════════════════════════════════════════════════════
        # TAKER SWEEP  (cross spread when mispriced vs fair value)
        # ══════════════════════════════════════════════════════════════════
        cur_buy  = max_buy
        cur_sell = max_sell
        cur_pos  = position

        if best_bid is not None and best_ask is not None:
            for ask_p in sorted(od.sell_orders.keys()):
                if cur_buy <= 0:
                    break
                if ask_p < fair_price - buy_edge:
                    qty = min(-od.sell_orders[ask_p], cur_buy)
                    if qty > 0:
                        orders.append(Order(product, ask_p, qty))
                        cur_buy -= qty
                        cur_pos += qty

            for bid_p in sorted(od.buy_orders.keys(), reverse=True):
                if cur_sell <= 0:
                    break
                if bid_p > fair_price + sell_edge:
                    qty = min(od.buy_orders[bid_p], cur_sell)
                    if qty > 0:
                        orders.append(Order(product, bid_p, -qty))
                        cur_sell -= qty
                        cur_pos -= qty

        # ══════════════════════════════════════════════════════════════════
        # MAKER QUOTES — TWO-SIDED BOOK
        # ══════════════════════════════════════════════════════════════════
        if best_bid is not None and best_ask is not None:
            skew_ticks = pos_skew * self.POS_SKEW_MAX

            # Base maker quotes (with position skew applied)
            ideal_bid = fair_price - half_spread - skew_ticks - stagnation_penalty
            ideal_ask = fair_price + half_spread - skew_ticks + stagnation_penalty

            # Clamp to penny inside the book
            my_bid = int(math.floor(min(best_bid + 1, ideal_bid)))
            my_ask = int(math.ceil(max(best_ask - 1, ideal_ask)))
            if my_bid >= my_ask:
                my_bid = my_ask - 1
            my_bid = min(my_bid, best_ask - 1)
            my_ask = max(my_ask, best_bid + 1)

            # ── Tiered deviation logic (extra aggression on reverting side)
            if deviation >= self.STRONG_SKEW_THRESH:
                # Far above fair → aggressive multi-level sell
                sp1 = best_ask - 2
                sp2 = best_ask - 1
                bp  = best_bid              # defensive buy
                if sp1 <= bp:
                    sp1 = bp + 1
                if sp2 <= bp:
                    sp2 = sp1

                s_total = cur_sell
                s_at_1  = s_total * 2 // 3
                s_at_2  = s_total - s_at_1
                if s_at_1 > 0:
                    orders.append(Order(product, sp1, -s_at_1))
                if s_at_2 > 0:
                    orders.append(Order(product, sp2 if sp2 != sp1 else sp1, -s_at_2))
                if cur_buy > 0:
                    orders.append(Order(product, bp, cur_buy))

            elif deviation <= -self.STRONG_SKEW_THRESH:
                # Far below fair → aggressive multi-level buy
                bp1 = best_bid + 2
                bp2 = best_bid + 1
                sp  = best_ask
                if bp1 >= sp:
                    bp1 = sp - 1
                if bp2 >= sp:
                    bp2 = bp1

                b_total = cur_buy
                b_at_1  = b_total * 2 // 3
                b_at_2  = b_total - b_at_1
                if b_at_1 > 0:
                    orders.append(Order(product, bp1, b_at_1))
                if b_at_2 > 0:
                    orders.append(Order(product, bp2 if bp2 != bp1 else bp1, b_at_2))
                if cur_sell > 0:
                    orders.append(Order(product, sp, -cur_sell))

            elif deviation >= self.SKEW_THRESH:
                # Moderate above fair → extra penny on sell only
                mq_ask = max(best_ask - 2, my_bid + 1)
                if cur_sell > 0:
                    orders.append(Order(product, mq_ask, -cur_sell))
                if cur_buy > 0:
                    orders.append(Order(product, best_bid, cur_buy))

            elif deviation <= -self.SKEW_THRESH:
                # Moderate below fair → extra penny on buy only
                mq_bid = min(best_bid + 2, my_ask - 1)
                if cur_buy > 0:
                    orders.append(Order(product, mq_bid, cur_buy))
                if cur_sell > 0:
                    orders.append(Order(product, best_ask, -cur_sell))

            else:
                # Near fair → standard skewed penny quotes
                if cur_buy > 0:
                    orders.append(Order(product, my_bid, cur_buy))
                if cur_sell > 0:
                    orders.append(Order(product, my_ask, -cur_sell))

        # ══════════════════════════════════════════════════════════════════
        # ONE-SIDED BOOK: Post on the missing side
        # ══════════════════════════════════════════════════════════════════
        elif best_bid is not None and best_ask is None:
            est_ask = int(best_bid + self.HALF_SPREAD_EST * 2)
            if cur_sell > 0:
                orders.append(Order(product, est_ask, -cur_sell))
            if cur_buy > 0:
                orders.append(Order(product, best_bid + 1, cur_buy))

        elif best_ask is not None and best_bid is None:
            est_bid = int(best_ask - self.HALF_SPREAD_EST * 2)
            if cur_buy > 0:
                orders.append(Order(product, est_bid, cur_buy))
            if cur_sell > 0:
                orders.append(Order(product, best_ask - 1, -cur_sell))

        return orders

    def _flatten_position(self, product, od, position, best_bid, best_ask, max_buy, max_sell):
        """Aggressively flatten near end of day to realise P&L."""
        orders: List[Order] = []

        if position > 0:
            if best_bid is not None:
                remaining = position
                for bid_p in sorted(od.buy_orders.keys(), reverse=True):
                    if remaining <= 0:
                        break
                    qty = min(remaining, abs(od.buy_orders[bid_p]))
                    orders.append(Order(product, bid_p, -qty))
                    remaining -= qty
                if remaining > 0:
                    sp = (best_bid + 1) if best_ask is None else (best_ask - 2)
                    orders.append(Order(product, sp, -remaining))
            elif best_ask is not None:
                orders.append(Order(product, best_ask - 2, -position))

        elif position < 0:
            if best_ask is not None:
                remaining = abs(position)
                for ask_p in sorted(od.sell_orders.keys()):
                    if remaining <= 0:
                        break
                    qty = min(remaining, abs(od.sell_orders[ask_p]))
                    orders.append(Order(product, ask_p, qty))
                    remaining -= qty
                if remaining > 0:
                    bp = (best_ask - 1) if best_bid is None else (best_bid + 2)
                    orders.append(Order(product, bp, remaining))
            elif best_bid is not None:
                orders.append(Order(product, best_bid + 2, abs(position)))

        else:
            # Already flat: tiny passive quotes to capture any last spread
            if best_bid is not None and best_ask is not None:
                my_bid = best_bid + 1
                my_ask = best_ask - 1
                if my_bid >= my_ask:
                    my_bid, my_ask = best_bid, best_ask
                if max_buy > 0:
                    orders.append(Order(product, my_bid, min(max_buy, 10)))
                if max_sell > 0:
                    orders.append(Order(product, my_ask, -min(max_sell, 10)))

        return orders

    # ═════════════════════════════════════════════════════════════════════
    # PEPPER ROOT: Sweep to Max Long Immediately, Hold All Day
    # ═════════════════════════════════════════════════════════════════════
    def _trade_pepper(self, product, od: OrderDepth, position):
        """
        Price rises +0.001/tick (~+1000/day). Being at +80 the entire day
        earns ~80k seashells. Always buy — never hesitate on spikes, never
        sell, never market-make. Sweep every ask level until position limit.
        """
        orders: List[Order] = []
        remaining = POSITION_LIMIT - position
        if remaining <= 0 or not od.sell_orders:
            return orders

        for ask_price in sorted(od.sell_orders.keys()):
            if remaining <= 0:
                break
            qty = min(remaining, abs(od.sell_orders[ask_price]))
            if qty > 0:
                orders.append(Order(product, ask_price, qty))
                remaining -= qty

        return orders