import json
import math
from datamodel import OrderDepth, UserId, TradingState, Order, Trade
from typing import List, Dict


class Trader:
    POSITION_LIMITS = {
        "EMERALDS": 80,
        "TOMATOES": 80,
    }

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _slope(self, prices: List[float]) -> float:
        """OLS slope of recent prices (positive = up-trend)."""
        n = len(prices)
        if n < 2:
            return 0.0
        x_mean = (n - 1) / 2.0
        y_mean = sum(prices) / n
        num = sum((i - x_mean) * (prices[i] - y_mean) for i in range(n))
        den = sum((i - x_mean) ** 2 for i in range(n))
        return num / den if den else 0.0

    def _std(self, prices: List[float]) -> float:
        if len(prices) < 2:
            return 0.0
        mean = sum(prices) / len(prices)
        return math.sqrt(sum((x - mean) ** 2 for x in prices) / len(prices))

    def _rolling_zscore(self, prices: List[float], window: int = 30) -> float:
        """Z-score of the latest price vs the rolling window."""
        hist = prices[-window:] if len(prices) >= window else prices
        if len(hist) < 5:
            return 0.0
        mean = sum(hist) / len(hist)
        std = self._std(hist)
        return (prices[-1] - mean) / std if std > 0.1 else 0.0

    # ── Main ───────────────────────────────────────────────────────────────────

    def run(self, state: TradingState):
        result = {}
        conversions = 0

        # Restore persisted state
        trader_state: dict = {}
        if state.traderData:
            try:
                trader_state = json.loads(state.traderData)
            except Exception:
                pass

        for product, order_depth in state.order_depths.items():
            if not order_depth.sell_orders or not order_depth.buy_orders:
                continue

            orders: List[Order] = []
            pos = state.position.get(product, 0)
            limit = self.POSITION_LIMITS.get(product, 80)

            best_ask = min(order_depth.sell_orders)
            best_bid = max(order_depth.buy_orders)
            mid = (best_bid + best_ask) / 2.0

            # ══════════════════════════════════════════════════════════════════
            # EMERALDS  –  peg to 10000, undercut the book to maximise fill rate
            # ══════════════════════════════════════════════════════════════════
            # Data insight: market always sits 9992 bid / 10008 ask (spread=16).
            # Quoting 9999/10001 undercuts every resting order and captures all
            # incoming flow for a clean 2-tick edge per side.
            if product == "EMERALDS":
                FV = 10000

                # --- Inventory-skewed quotes ---
                # Light skew: if long, lower both quotes slightly to encourage
                # selling; if short, raise them.
                skew = round((pos / limit) * 1)   # ±1 tick max skew

                my_bid = FV - 1 - skew   # default 9999
                my_ask = FV + 1 - skew   # default 10001

                # Never cross fair value (would be giving money away)
                my_bid = min(my_bid, FV - 1)
                my_ask = max(my_ask, FV + 1)

                # Post both sides proportional to remaining room
                buy_room  = limit - pos
                sell_room = limit + pos

                if buy_room > 0:
                    orders.append(Order(product, my_bid, buy_room))
                if sell_room > 0:
                    orders.append(Order(product, my_ask, -sell_room))

            # ══════════════════════════════════════════════════════════════════
            # TOMATOES  –  trend + mean-reversion hybrid
            # ══════════════════════════════════════════════════════════════════
            # Data insights:
            #   • Mid drifted −49 on day −1, +6.5 on day −2  → meaningful trends
            #   • Lag-1 autocorrelation = −0.42  → strong mean-reversion at
            #     the tick level, but multi-bar trends exist
            #   • std ≈ 20 → use 30-bar rolling z-score for signal
            elif product == "TOMATOES":
                key = "TOM_HIST"
                hist: List[float] = trader_state.get(key, [])
                hist.append(mid)
                if len(hist) > 50:
                    hist = hist[-50:]
                trader_state[key] = hist

                SLOPE_WINDOW  = 10   # bars for short-term slope
                MR_WINDOW     = 30   # bars for z-score baseline
                ENTRY_SIZE    = 15   # lots per signal
                TREND_THR     = 1.2  # slope threshold to enter trend trade
                MR_Z_ENTRY    = 1.5  # z-score threshold for mean-reversion entry
                MR_Z_EXIT     = 0.3  # z-score threshold to close MR position
                DUMP_THRESH   = 60   # inventory level that triggers panic unwind

                slope = self._slope(hist[-SLOPE_WINDOW:]) if len(hist) >= SLOPE_WINDOW else 0.0
                z     = self._rolling_zscore(hist, MR_WINDOW)
                std   = self._std(hist[-MR_WINDOW:])

                # ---- Kill-switches / panic unwind ----
                market_trades = state.market_trades.get(product, [])
                sell_pressure = sum(t.quantity for t in market_trades if t.price <= best_bid) > 15
                is_crashing   = slope < -1.0 or (slope < -0.5 and sell_pressure)
                is_rocketing  = slope > 1.0

                if pos > DUMP_THRESH and is_crashing:
                    # Dump everything at best bid immediately
                    orders.append(Order(product, best_bid, -pos - limit))
                    pos = -limit
                elif pos < -DUMP_THRESH and is_rocketing:
                    orders.append(Order(product, best_ask, limit - pos))
                    pos = limit

                # ---- Trend following ----
                if slope > TREND_THR and pos < limit and not is_crashing:
                    qty = min(ENTRY_SIZE, limit - pos)
                    orders.append(Order(product, best_ask, qty))
                    pos += qty

                elif slope < -TREND_THR and pos > -limit and not is_rocketing:
                    qty = min(ENTRY_SIZE, limit + pos)
                    orders.append(Order(product, best_bid, -qty))
                    pos -= qty

                # ---- Mean reversion ----
                # (Only enter MR if we're not already riding a trend the same
                #  way; prevents doubling into a runaway move.)
                elif z < -MR_Z_ENTRY and pos < limit:
                    qty = min(ENTRY_SIZE, limit - pos)
                    orders.append(Order(product, best_ask, qty))
                    pos += qty

                elif z > MR_Z_ENTRY and pos > -limit:
                    qty = min(ENTRY_SIZE, limit + pos)
                    orders.append(Order(product, best_bid, -qty))
                    pos -= qty

                # ---- Mean-reversion exit ----
                if abs(z) < MR_Z_EXIT:
                    if pos > 0:
                        orders.append(Order(product, best_bid, -pos))
                        pos = 0
                    elif pos < 0:
                        orders.append(Order(product, best_ask, -pos))
                        pos = 0

                # ---- Passive market making on the remainder ----
                # Provide liquidity around a volatility-adjusted mid.
                # Widen the spread when vol is high to avoid adverse selection.
                vol_adj  = max(1, min(int(std / 5), 4))   # 1–4 ticks extra half-spread
                skew     = round((pos / limit) * 4)       # inventory skew ±4 ticks

                mm_bid = int(round(mid - vol_adj - skew))
                mm_ask = int(round(mid + vol_adj - skew))
                if mm_bid >= mm_ask:
                    mm_bid = mm_ask - 1

                buy_room  = limit - pos
                sell_room = limit + pos

                # Only post passive quotes if not crashing/rocketing
                if buy_room > 0 and not is_crashing:
                    orders.append(Order(product, mm_bid, buy_room))
                if sell_room > 0 and not is_rocketing:
                    orders.append(Order(product, mm_ask, -sell_room))

            result[product] = orders

        traderData = json.dumps(trader_state)
        return result, conversions, traderData