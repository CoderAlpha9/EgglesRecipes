import json
import math
from datamodel import OrderDepth, TradingState, Order
from typing import List


class Trader:
    POSITION_LIMITS = {
        "ASH_COATED_OSMIUM": 80,
        "INTARIAN_PEPPER_ROOT": 80,
    }

    # ── Osmium market-making params ───────────────────────────────────────────
    FAIR_ALPHA = 0.12        # Medium EMA speed for real-time fair value
    LONG_ALPHA = 0.003       # Slow EMA for long-term mean-reversion anchor
    VOL_WINDOW = 30          # Rolling window (ticks) for volatility estimate
    INV_SKEW   = 1.5         # Inventory-skew strength (× vol per unit of inv_ratio)
    REVERT_STR = 0.25        # Fraction to pull fair value toward long-term mean

    # ── Pepper trend-tracking params ──────────────────────────────────────────
    TREND_ALPHA = 0.08       # EMA smoothing for price-change trend signal

    # ─────────────────────────────────────────────────────────────────────────
    def bid(self) -> int:
        """
        Market Access Fee (MAF) bid.

        Round 2 rules:
          • The top 50 % of bidders pay their bid and receive 25 % more
            order-book quotes to trade against.
          • This is a one-time cost, subtracted from round 2 PnL.
          • The auction is blind; you just need to beat the median bidder.

        Sizing logic:
          • Extra access ≈ 20-30 % more market volume for osmium MM.
          • If expected R2 osmium PnL is ~100-150 K XIRECs, extra 25 %
            flow ≈ 25-40 K upside – well worth a few thousand XIRECs.
          • We bid 4 000 to sit comfortably in the top 50 % without
            being the sucker who paid 20 000 when 4 000 would have won.
        """
        return 4_000

    # ─────────────────────────────────────────────────────────────────────────
    def run(self, state: TradingState):
        result      = {}
        conversions = 0

        # ── Persistent state (survives across ticks via traderData) ──────────
        ts: dict = {
            "OSMIUM_FAIR": None,    # Short-to-medium EMA of weighted-mid
            "OSMIUM_LONG": None,    # Very slow EMA (mean-reversion anchor)
            "OSMIUM_VOLS": [],      # History of mid-prices for rolling vol
            "PEPPER_PREV_ASK":  None
        }
        if state.traderData:
            try:
                ts.update(json.loads(state.traderData))
            except Exception:
                pass

        for product in state.order_depths:
            if product not in self.POSITION_LIMITS:
                continue

            od: OrderDepth     = state.order_depths[product]
            orders: List[Order] = []

            cur_pos = state.position.get(product, 0)
            limit   = self.POSITION_LIMITS[product]
            buy_cap = limit - cur_pos       # remaining long headroom (≥ 0)
            sell_cap = -limit - cur_pos     # remaining short headroom (≤ 0)

            # Need at least one side to operate
            if not od.buy_orders or not od.sell_orders:
                result[product] = orders
                continue

            best_bid = max(od.buy_orders.keys())
            best_ask = min(od.sell_orders.keys())
            mid      = (best_bid + best_ask) / 2.0

            # ═══════════════════════════════════════════════════════════════
            # STRATEGY 1: ASH_COATED_OSMIUM
            # Model  : Mean-reverting random walk (some volatility, no trend)
            # Approach: Inventory-skewed market making (Avellaneda-Stoikov)
            #           + aggressive taking of clearly mis-priced orders
            #           + slow-EMA mean-reversion bias on quotes
            # ═══════════════════════════════════════════════════════════════
            if product == "ASH_COATED_OSMIUM":

                # ── 1. Volume-weighted mid (imbalance-adjusted fair value) ──
                # More volume on the bid side → price gravitates toward ask;
                # more on ask side → price gravitates toward bid.
                bvol  = sum(od.buy_orders.values())         # total bid qty
                avol  = -sum(od.sell_orders.values())       # total ask qty
                total = bvol + avol
                wmid  = (avol * best_bid + bvol * best_ask) / total if total > 0 else mid

                # ── 2. Update short & long EMAs ───────────────────────────
                fair   = ts["OSMIUM_FAIR"]
                long_m = ts["OSMIUM_LONG"]

                fair   = (self.FAIR_ALPHA * wmid + (1 - self.FAIR_ALPHA) * fair
                          if fair is not None else wmid)
                long_m = (self.LONG_ALPHA * wmid + (1 - self.LONG_ALPHA) * long_m
                          if long_m is not None else wmid)

                ts["OSMIUM_FAIR"] = fair
                ts["OSMIUM_LONG"] = long_m

                # ── 3. Rolling volatility (std-dev of mid over last N ticks) ─
                vols: list = ts["OSMIUM_VOLS"]
                vols.append(mid)
                if len(vols) > self.VOL_WINDOW:
                    vols = vols[-self.VOL_WINDOW:]
                ts["OSMIUM_VOLS"] = vols

                if len(vols) >= 5:
                    mv  = sum(vols) / len(vols)
                    vol = math.sqrt(sum((x - mv) ** 2 for x in vols) / len(vols))
                else:
                    vol = 1.5   # conservative default until warm-up
                vol = max(vol, 0.5)

                # ── 4. Adjusted fair value with mean-reversion pull ────────
                # When fair_ema is above long_ema (elevated), pull it down;
                # when below (depressed), pull it up.
                adj_fair = fair - self.REVERT_STR * (fair - long_m)
                fair_int = int(round(adj_fair))

                # ── 5. Inventory-skewed reservation price ─────────────────
                # inv_ratio ∈ [-1, +1]: +1 = max long, -1 = max short
                inv_ratio = cur_pos / limit
                # skew > 0 when long  → lowers reservation → encourages selling
                # skew < 0 when short → raises reservation → encourages buying
                skew       = int(round(self.INV_SKEW * vol * inv_ratio))
                reservation = fair_int - skew

                # ── 6. Dynamic half-spread based on volatility ─────────────
                half_spread = max(1, int(round(vol * 0.4)))

                # ── 7. Compute quote prices ────────────────────────────────
                q_bid = reservation - half_spread
                q_ask = reservation + half_spread
                if q_ask <= q_bid:
                    q_ask = q_bid + 1

                # ── 8. AGGRESSIVE TAKING ───────────────────────────────────
                # Buy any ask below (fair – inventory premium)
                # Sell any bid above (fair – inventory premium)
                # → inventory-aware: when already long, require a bigger
                #   discount before buying more; vice-versa when short.
                take_buy_thr  = fair_int - max(0, skew // 2)
                take_sell_thr = fair_int - min(0, skew // 2)

                if od.sell_orders and buy_cap > 0:
                    for ask_p in sorted(od.sell_orders.keys()):
                        if ask_p < take_buy_thr and buy_cap > 0:
                            ask_v    = -od.sell_orders[ask_p]
                            vol_take = min(buy_cap, ask_v)
                            orders.append(Order(product, ask_p, vol_take))
                            buy_cap -= vol_take
                            cur_pos += vol_take
                        else:
                            break

                if od.buy_orders and sell_cap < 0:
                    for bid_p in sorted(od.buy_orders.keys(), reverse=True):
                        if bid_p > take_sell_thr and sell_cap < 0:
                            bid_v    = od.buy_orders[bid_p]
                            vol_take = max(sell_cap, -bid_v)
                            orders.append(Order(product, bid_p, vol_take))
                            sell_cap -= vol_take
                            cur_pos  += vol_take
                        else:
                            break

                # Refresh capacity after aggressive taking
                buy_cap  = limit - cur_pos
                sell_cap = -limit - cur_pos

                # ── 9. PASSIVE QUOTING (3-level ladder) ───────────────────
                # Clamp to inside current best spread to lead the queue.
                eff_bid = min(q_bid, best_bid + 1)
                eff_ask = max(q_ask, best_ask - 1)

                # Safety: never let our quotes cross the opposite side
                if eff_bid >= best_ask:
                    eff_bid = best_ask - 1
                if eff_ask <= best_bid:
                    eff_ask = best_bid + 1

                if buy_cap > 0:
                    b1 = buy_cap // 3
                    b2 = buy_cap // 3
                    b3 = buy_cap - b1 - b2
                    if b1 > 0:
                        orders.append(Order(product, eff_bid, b1))
                    if b2 > 0:
                        orders.append(Order(product, eff_bid - half_spread, b2))
                    if b3 > 0:
                        orders.append(Order(product, eff_bid - 2 * half_spread, b3))

                if sell_cap < 0:
                    s1 = sell_cap // 3
                    s2 = sell_cap // 3
                    s3 = sell_cap - s1 - s2
                    if s1 < 0:
                        orders.append(Order(product, eff_ask, s1))
                    if s2 < 0:
                        orders.append(Order(product, eff_ask + half_spread, s2))
                    if s3 < 0:
                        orders.append(Order(product, eff_ask + 2 * half_spread, s3))
                        
            elif product == "INTARIAN_PEPPER_ROOT":

                prev_ask = ts.get("PEPPER_PREV_ASK")

                if prev_ask is None:
                    prev_ask = best_ask

                ts["PEPPER_PREV_ASK"] = best_ask

                if buy_cap > 0:

                    is_spike = best_ask > prev_ask

                    if not is_spike:

                        orders.append(
                            Order(product, best_ask, buy_cap)
                        )

                    else:

                        my_bid = best_bid + 1

                        if my_bid >= best_ask:
                            my_bid = best_bid

                        orders.append(
                            Order(product, my_bid, buy_cap)
                        )

                if cur_pos > 0:

                    orders.append(
                        Order(product, best_ask + 4, -cur_pos)
                    )

            result[product] = orders

        return result, conversions, json.dumps(ts)