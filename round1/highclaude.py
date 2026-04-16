import json
from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict

"""
=============================================================================
IMC PROSPERITY ROUND 1 - OPTIMISED STRATEGY
=============================================================================

PRODUCT ANALYSIS SUMMARY
─────────────────────────────────────────────────────────────────────────────
INTARIAN_PEPPER_ROOT:
  • Price rises at an almost perfectly linear rate of +0.001/timestamp
    → +1000 per day (10000 timestamps/day × 0.001)
  • Intercepts: Day -2 = 10000, Day -1 = 11000, Day 0 = 12000
    (each day starts exactly where the previous ended)
  • Spread: typically 11–16 ticks wide
  • Best strategy: get to max long (+80) as fast as possible at open,
    hold all day. Profit ≈ 79k–80k per day × 3 days ≈ 238k total.

ASH_COATED_OSMIUM:
  • Mean-reverting around ~10000 (no directional drift)
  • Spread is almost always exactly 16 ticks (modal value), sometimes 18–19
  • EMA of mid price is very stable (std of deviation < 3.3)
  • Negative tick-by-tick autocorrelation (lag-1 = –0.49): after a move
    up, next tick tends to revert, and vice versa.
  • Strategy: use a long-span EMA as fair value, quote 1 tick on each
    side adjusted for inventory skew. Fill when market crosses quotes.
    Position skew pushes quotes away from inventory direction.
=============================================================================
"""

POSITION_LIMIT = 80


class Trader:

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}

        # ── Deserialise persistent state ──────────────────────────────────
        try:
            trader_state = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            trader_state = {}

        osm_ema = trader_state.get("osm_ema", None)   # EMA of osmium mid

        # ── Route per product ─────────────────────────────────────────────
        for product in state.order_depths:
            od: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            position = state.position.get(product, 0)

            if not od.sell_orders or not od.buy_orders:
                result[product] = orders
                continue

            best_ask = min(od.sell_orders.keys())
            best_bid = max(od.buy_orders.keys())
            mid = (best_ask + best_bid) / 2.0

            # ─────────────────────────────────────────────────────────────
            # STRATEGY A: INTARIAN_PEPPER_ROOT  – Trend Follower / Max Long
            # ─────────────────────────────────────────────────────────────
            #
            # The price rises +0.001 per timestamp (≈ +1000/day).
            # There is NO profitable short: we'd be fighting a 1-seashell/ts
            # headwind.  Being at maximum long (+80) the entire day earns
            # ~80 × 1000 = 80,000 seashells per day in unrealised appreciation.
            #
            # Execution:
            #   1. Sweep all three ask levels at once to reach +80 ASAP.
            #   2. Once at +80, do nothing (no churning, no market-making).
            #   3. Never voluntarily go short or even flat.
            # ─────────────────────────────────────────────────────────────
            if product == "INTARIAN_PEPPER_ROOT":
                remaining = POSITION_LIMIT - position   # how many more we can buy

                if remaining > 0:
                    # Sweep level 1, 2, 3 asks in one tick to fill faster
                    asks_sorted = sorted(od.sell_orders.keys())   # ascending
                    for ask_price in asks_sorted:
                        if remaining <= 0:
                            break
                        available = abs(od.sell_orders[ask_price])
                        fill = min(remaining, available)
                        orders.append(Order(product, ask_price, fill))
                        remaining -= fill

            # ─────────────────────────────────────────────────────────────
            # STRATEGY B: ASH_COATED_OSMIUM  – EMA-Anchored Market Maker
            # ─────────────────────────────────────────────────────────────
            #
            # Fair value = slow EMA of the mid price (span 500 ticks).
            # Spread is nearly always 16 ticks; we quote ±1 tick around
            # fair value (so we capture ~8 ticks per round trip vs the 16
            # tick spread).
            #
            # Inventory skew: if we are long, shift our quotes DOWN slightly
            # so we hit our sell faster and buy slower.  This prevents us
            # from getting stuck at max long/short.
            #
            #   adj_fair  = ema  −  (position / limit) × SKEW
            #   my_bid    = adj_fair − OFFSET
            #   my_ask    = adj_fair + OFFSET
            #
            # We fill passively when the market crosses our resting quotes:
            #   • If best_ask ≤ my_bid  → lift the ask (buy)
            #   • If best_bid ≥ my_ask  → hit the bid (sell)
            # ─────────────────────────────────────────────────────────────
            elif product == "ASH_COATED_OSMIUM":
                EMA_SPAN  = 500    # slow EMA keeps fair value stable
                OFFSET    = 1      # ticks each side of fair value for our quotes
                SKEW      = 2      # max inventory-skew in ticks

                # Update EMA
                alpha = 2.0 / (EMA_SPAN + 1)
                if osm_ema is None:
                    osm_ema = mid
                else:
                    osm_ema = alpha * mid + (1 - alpha) * osm_ema

                fair = osm_ema

                # Inventory skew: lean away from current position
                skew_ticks = (position / POSITION_LIMIT) * SKEW
                adj_fair   = fair - skew_ticks

                my_bid = round(adj_fair - OFFSET)
                my_ask = round(adj_fair + OFFSET)

                # Safety: ensure bid < ask
                if my_bid >= my_ask:
                    my_bid = round(fair) - 1
                    my_ask = round(fair) + 1

                # ── BUY side ──────────────────────────────────────────────
                # If the best ask in the book is at or below our bid, buy it.
                if best_ask <= my_bid and position < POSITION_LIMIT:
                    max_buy = POSITION_LIMIT - position
                    # Sweep all affordable ask levels
                    for ask_price in sorted(od.sell_orders.keys()):
                        if max_buy <= 0 or ask_price > my_bid:
                            break
                        vol = min(max_buy, abs(od.sell_orders[ask_price]))
                        orders.append(Order(product, ask_price, vol))
                        max_buy -= vol

                # ── SELL side ─────────────────────────────────────────────
                # If the best bid in the book is at or above our ask, sell it.
                if best_bid >= my_ask and position > -POSITION_LIMIT:
                    max_sell = position + POSITION_LIMIT
                    for bid_price in sorted(od.buy_orders.keys(), reverse=True):
                        if max_sell <= 0 or bid_price < my_ask:
                            break
                        vol = min(max_sell, abs(od.buy_orders[bid_price]))
                        orders.append(Order(product, bid_price, -vol))
                        max_sell -= vol

            result[product] = orders

        # ── Serialise state ───────────────────────────────────────────────
        new_state = {"osm_ema": osm_ema}
        trader_data = json.dumps(new_state)
        conversions = 0

        return result, conversions, trader_data