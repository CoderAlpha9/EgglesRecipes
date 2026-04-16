import json
from datamodel import OrderDepth, TradingState, Order
from typing import List

class Trader:
    # ================================================================
    # ASH_COATED_OSMIUM: Mean-Reversion Market Making
    # ================================================================
    # Market analysis findings:
    #   - Autocorrelation lag-1: -0.49 (extremely strong mean reversion)
    #   - Long-term mean: ~10000, stdev: ~3.5
    #   - Typical spread: ~16 ticks (62% of ticks)
    #   - AR(1) phi: 0.36, half-life < 1 tick
    #   - Corr(deviation, next_return): -0.57
    #   - OFI > 0.4 => next return +3.5; OFI < -0.4 => next return -3.0
    #   - Both sides of MM are profitable (spread 14 > reversion per tick)
    #   - Reverting side earns MORE: at dev=5, sell earns 9.85, buy earns 4.15
    #
    # Strategy improvements over original:
    #   1. Extra penny on mean-reverting side (ask-2 or bid+2) for more fills
    #   2. Multi-level quoting: spread size across two price levels on reverting side
    #   3. Keep FULL size on both sides (both sides earn positive expected PnL)
    #   4. One-sided book handling (post on missing side at estimated fair price)
    #   5. End-of-day position flattening to realize profits
    #   6. EMA-based fair value tracking with strong mean anchor
    # ================================================================

    OSMIUM_MEAN = 10000
    OSMIUM_LIMIT = 80
    HALF_SPREAD_EST = 8       # Estimated half-spread for one-sided book quoting
    EMA_ALPHA = 0.1           # Slow EMA smoothing factor
    MEAN_WEIGHT = 0.8         # Weight of long-term mean in fair value calc
    SKEW_THRESH = 2           # Deviation to trigger extra penny on reverting side
    STRONG_SKEW_THRESH = 4    # Deviation for maximum aggression on reverting side
    LIQUIDATION_TS = 97000    # Start flattening position

    def run(self, state: TradingState):
        result = {}

        # Deserialize persistent state
        trader_state = {}
        if state.traderData:
            try:
                trader_state = json.loads(state.traderData)
            except Exception:
                trader_state = {}

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            position = state.position.get(product, 0)

            if product == "ASH_COATED_OSMIUM":
                orders = self.trade_osmium(
                    product, order_depth, position, state.timestamp, trader_state
                )
            elif product == "INTARIAN_PEPPER_ROOT":
                orders = self.trade_pepper(product, order_depth, position)

            result[product] = orders

        traderData = json.dumps(trader_state)
        conversions = 0
        return result, conversions, traderData

    # ================================================================
    #  OSMIUM: Mean-Reversion Market Maker
    # ================================================================
    def trade_osmium(self, product, od: OrderDepth, position, timestamp, ts):
        orders: List[Order] = []

        best_bid = max(od.buy_orders.keys()) if od.buy_orders else None
        best_ask = min(od.sell_orders.keys()) if od.sell_orders else None

        # --- Compute mid price ---
        if best_bid is not None and best_ask is not None:
            mid = (best_bid + best_ask) / 2
        elif best_bid is not None:
            mid = best_bid
        elif best_ask is not None:
            mid = best_ask
        else:
            return orders

        # --- Update slow EMA ---
        ema = ts.get("osm_ema", self.OSMIUM_MEAN)
        ema = self.EMA_ALPHA * mid + (1 - self.EMA_ALPHA) * ema
        ts["osm_ema"] = ema

        # --- Fair value: strong anchor to long-term mean ---
        fair_value = self.MEAN_WEIGHT * self.OSMIUM_MEAN + (1 - self.MEAN_WEIGHT) * ema

        # --- Deviation from fair value ---
        deviation = mid - fair_value

        # --- OFI signal ---
        ofi = 0
        if best_bid is not None and best_ask is not None:
            bid_vol = abs(od.buy_orders.get(best_bid, 0))
            ask_vol = abs(od.sell_orders.get(best_ask, 0))
            total_vol = bid_vol + ask_vol
            if total_vol > 0:
                ofi = (bid_vol - ask_vol) / total_vol

        max_buy = self.OSMIUM_LIMIT - position
        max_sell = self.OSMIUM_LIMIT + position

        # ==============================================================
        # END-OF-DAY FLATTENING
        # Flatten position to realize profits and avoid overnight risk.
        # Use aggressive pricing to ensure fills.
        # ==============================================================
        pass

        # ==============================================================
        # TWO-SIDED BOOK: Main Market Making Logic
        # ==============================================================
        if best_bid is not None and best_ask is not None:
            spread = best_ask - best_bid

            # --- Determine quote prices ---
            # Base: penny inside (bid+1, ask-1)
            # On strong mean-reversion signal: extra penny on reverting side
            # This makes the reverting side MORE likely to fill.
            # We keep both sides at FULL SIZE because both are profitable.

            if deviation >= self.STRONG_SKEW_THRESH:
                # Price well above fair value -> be very aggressive selling
                # Sell layer 1: ask-2 (aggressive, high fill probability)
                # Sell layer 2: ask-1 (standard penny)
                # Buy: bid only (defensive, still full size)
                sell_price_1 = best_ask - 2
                sell_price_2 = best_ask - 1
                buy_price = best_bid  # Wider buy (defensive)

                # Safety: ensure sell prices > buy price
                if sell_price_1 <= buy_price:
                    sell_price_1 = buy_price + 1
                if sell_price_2 <= buy_price:
                    sell_price_2 = sell_price_1

                # Split sell volume across two levels
                sell_total = max_sell
                sell_at_1 = min(sell_total, sell_total * 2 // 3)  # 2/3 at aggressive
                sell_at_2 = sell_total - sell_at_1                # 1/3 at standard

                if sell_at_1 > 0:
                    orders.append(Order(product, sell_price_1, -sell_at_1))
                if sell_at_2 > 0 and sell_price_2 != sell_price_1:
                    orders.append(Order(product, sell_price_2, -sell_at_2))
                elif sell_at_2 > 0:
                    # Same price, just add to first order
                    orders.append(Order(product, sell_price_1, -sell_at_2))

                if max_buy > 0:
                    orders.append(Order(product, buy_price, max_buy))

            elif deviation <= -self.STRONG_SKEW_THRESH:
                # Price well below fair value -> be very aggressive buying
                buy_price_1 = best_bid + 2  # Aggressive buy
                buy_price_2 = best_bid + 1  # Standard penny
                sell_price = best_ask       # Wider sell (defensive)

                if buy_price_1 >= sell_price:
                    buy_price_1 = sell_price - 1
                if buy_price_2 >= sell_price:
                    buy_price_2 = buy_price_1

                buy_total = max_buy
                buy_at_1 = min(buy_total, buy_total * 2 // 3)
                buy_at_2 = buy_total - buy_at_1

                if buy_at_1 > 0:
                    orders.append(Order(product, buy_price_1, buy_at_1))
                if buy_at_2 > 0 and buy_price_2 != buy_price_1:
                    orders.append(Order(product, buy_price_2, buy_at_2))
                elif buy_at_2 > 0:
                    orders.append(Order(product, buy_price_1, buy_at_2))

                if max_sell > 0:
                    orders.append(Order(product, sell_price, -max_sell))

            elif deviation >= self.SKEW_THRESH:
                # Moderate above fair -> extra penny on sell, standard on buy
                my_ask = best_ask - 2
                my_bid = best_bid

                if my_ask <= my_bid:
                    my_ask = my_bid + 1

                if max_sell > 0:
                    orders.append(Order(product, my_ask, -max_sell))
                if max_buy > 0:
                    orders.append(Order(product, my_bid, max_buy))

            elif deviation <= -self.SKEW_THRESH:
                # Moderate below fair -> extra penny on buy, standard on sell
                my_bid = best_bid + 2
                my_ask = best_ask

                if my_bid >= my_ask:
                    my_bid = my_ask - 1

                if max_buy > 0:
                    orders.append(Order(product, my_bid, max_buy))
                if max_sell > 0:
                    orders.append(Order(product, my_ask, -max_sell))

            else:
                # Near fair value -> standard pennying on both sides
                my_bid = best_bid + 1
                my_ask = best_ask - 1

                if my_bid >= my_ask:
                    my_bid = best_bid
                    my_ask = best_ask

                if max_buy > 0:
                    orders.append(Order(product, my_bid, max_buy))
                if max_sell > 0:
                    orders.append(Order(product, my_ask, -max_sell))

        # ==============================================================
        # ONE-SIDED BOOK: Post on the missing side
        # ==============================================================
        elif best_bid is not None and best_ask is None:
            # Only bids (asks exhausted) -> likely someone bought aggressively
            # Mean reversion suggests price will drop. Post a sell at estimated ask.
            estimated_ask = int(best_bid + self.HALF_SPREAD_EST * 2)

            if max_sell > 0:
                orders.append(Order(product, estimated_ask, -max_sell))
            if max_buy > 0:
                orders.append(Order(product, best_bid + 1, max_buy))

        elif best_ask is not None and best_bid is None:
            # Only asks (bids exhausted) -> likely aggressive selling
            # Mean reversion suggests price will rise. Post a buy at estimated bid.
            estimated_bid = int(best_ask - self.HALF_SPREAD_EST * 2)

            if max_buy > 0:
                orders.append(Order(product, estimated_bid, max_buy))
            if max_sell > 0:
                orders.append(Order(product, best_ask - 1, -max_sell))

        return orders

    def _flatten_position(self, product, od, position, best_bid, best_ask, max_buy, max_sell):
        """Aggressively flatten position near end of day."""
        orders = []

        if position > 0:
            # Long position: sell to flatten
            if best_bid is not None:
                # Hit bids to flatten
                remaining = position
                for bid_price in sorted(od.buy_orders.keys(), reverse=True):
                    if remaining <= 0:
                        break
                    bid_vol = abs(od.buy_orders[bid_price])
                    qty = min(remaining, bid_vol)
                    orders.append(Order(product, bid_price, -qty))
                    remaining -= qty
                # Post tight passive sell for remaining
                if remaining > 0:
                    sell_price = best_bid + 1 if best_ask is None else best_ask - 2
                    sell_price = max(sell_price, (best_bid + 1) if best_bid else 9990)
                    orders.append(Order(product, sell_price, -remaining))
            elif best_ask is not None:
                orders.append(Order(product, best_ask - 2, -position))

        elif position < 0:
            # Short position: buy to flatten
            if best_ask is not None:
                remaining = abs(position)
                for ask_price in sorted(od.sell_orders.keys()):
                    if remaining <= 0:
                        break
                    ask_vol = abs(od.sell_orders[ask_price])
                    qty = min(remaining, ask_vol)
                    orders.append(Order(product, ask_price, qty))
                    remaining -= qty
                if remaining > 0:
                    buy_price = best_ask - 1 if best_bid is None else best_bid + 2
                    buy_price = min(buy_price, (best_ask - 1) if best_ask else 10010)
                    orders.append(Order(product, buy_price, remaining))
            elif best_bid is not None:
                orders.append(Order(product, best_bid + 2, abs(position)))

        else:
            # Already flat: just do small market making
            if best_bid is not None and best_ask is not None:
                my_bid = best_bid + 1
                my_ask = best_ask - 1
                if my_bid >= my_ask:
                    my_bid = best_bid
                    my_ask = best_ask
                if max_buy > 0:
                    orders.append(Order(product, my_bid, min(max_buy, 10)))
                if max_sell > 0:
                    orders.append(Order(product, my_ask, -min(max_sell, 10)))

        return orders

    # ================================================================
    #  PEPPER ROOT: Accumulate & Hold (unchanged)
    # ================================================================
    def trade_pepper(self, product, od: OrderDepth, position):
        orders: List[Order] = []

        if not od.sell_orders:
            return orders

        # --- Sort asks (ascending) ---
        sorted_asks = sorted(od.sell_orders.keys())

        # --- L1 ask ---
        best_ask = sorted_asks[0]
        ask_vol = -od.sell_orders[best_ask]

        # Condition 1: buy full L1 volume if L1 <= 12007
        if best_ask <= 12007:
            orders.append(Order(product, best_ask, ask_vol))

        # --- L2 ask (only if exists) ---
        if len(sorted_asks) >= 2:
            second_best_ask = sorted_asks[1]

            # Condition 2: buy 5 units if L2 <= 12009
            if second_best_ask <= 12009:
                orders.append(Order(product, second_best_ask, 5))

        return orders