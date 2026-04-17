import json
import math
from datamodel import OrderDepth, TradingState, Order
from typing import List


class Trader:
    POSITION_LIMITS = {
        "ASH_COATED_OSMIUM": 80,
        "INTARIAN_PEPPER_ROOT": 80
    }

    ACO_VOL_WINDOW = 20
    EMA_ALPHA = 0.08

    def run(self, state: TradingState):
        result = {}
        conversions = 0

        trader_state = {
            "PEPPER_PREV_ASK": None,
            "OSMIUM_SLOW_EMA": None,
            "ACO_MID_HISTORY": [],
            "ASH_COATED_OSMIUM_BID_EMA": None,
            "ASH_COATED_OSMIUM_ASK_EMA": None,
            "INTARIAN_PEPPER_ROOT_BID_EMA": None,
            "INTARIAN_PEPPER_ROOT_ASK_EMA": None,
        }

        if state.traderData:
            try:
                trader_state = json.loads(state.traderData)
            except Exception:
                pass

        for product in state.order_depths:

            if product not in self.POSITION_LIMITS:
                continue

            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []

            bid_ema_key = f"{product}_BID_EMA"
            ask_ema_key = f"{product}_ASK_EMA"

            bid_ema = trader_state.get(bid_ema_key)
            ask_ema = trader_state.get(ask_ema_key)

            best_bid = None
            best_ask = None

            # ---------------- UPDATE EMA IF LIVE DATA EXISTS ----------------

            if order_depth.buy_orders:
                best_bid = max(order_depth.buy_orders.keys())

                if bid_ema is None:
                    bid_ema = best_bid
                else:
                    bid_ema = (
                        self.EMA_ALPHA * best_bid
                        + (1 - self.EMA_ALPHA) * bid_ema
                    )

            if order_depth.sell_orders:
                best_ask = min(order_depth.sell_orders.keys())

                if ask_ema is None:
                    ask_ema = best_ask
                else:
                    ask_ema = (
                        self.EMA_ALPHA * best_ask
                        + (1 - self.EMA_ALPHA) * ask_ema
                    )

            trader_state[bid_ema_key] = bid_ema
            trader_state[ask_ema_key] = ask_ema

            # ---------------- SYNTHETIC FALLBACK QUOTES ----------------

            if best_bid is None and bid_ema is not None:
                best_bid = int(round(bid_ema)) +  1

            if best_ask is None and ask_ema is not None:
                best_ask = int(round(ask_ema)) - 1

            # still no anchor available → skip safely
            if best_bid is None or best_ask is None:
                continue

            mid_price = (best_bid + best_ask) / 2.0

            current_pos = state.position.get(product, 0)
            limit = self.POSITION_LIMITS[product]

            buy_vol = limit - current_pos
            sell_vol = -limit - current_pos

            # =====================================================
            # STRATEGY 1: ASH_COATED_OSMIUM
            # =====================================================

            if product == "ASH_COATED_OSMIUM":

                osmium_ema = trader_state.get("OSMIUM_SLOW_EMA")

                if osmium_ema is None:
                    osmium_ema = mid_price
                else:
                    osmium_ema = 0.002 * mid_price + 0.998 * osmium_ema

                trader_state["OSMIUM_SLOW_EMA"] = osmium_ema

                fair_value = int(round(osmium_ema))

                history = trader_state.get("ACO_MID_HISTORY", [])
                history.append(mid_price)

                if len(history) > self.ACO_VOL_WINDOW:
                    history = history[-self.ACO_VOL_WINDOW:]

                trader_state["ACO_MID_HISTORY"] = history

                if len(history) == self.ACO_VOL_WINDOW:

                    mean = sum(history) / self.ACO_VOL_WINDOW

                    variance = sum(
                        (x - mean) ** 2 for x in history
                    ) / self.ACO_VOL_WINDOW

                    roll_vol = math.sqrt(variance)

                    spread_offset = int(1 + roll_vol)

                else:
                    spread_offset = 1

                # ---------- DEPTH SWEEP (SAFE IF DEPTH EXISTS) ----------

                if order_depth.sell_orders:

                    for ask_price, ask_vol in sorted(order_depth.sell_orders.items()):

                        ask_vol = -ask_vol

                        if ask_price < fair_value and buy_vol > 0:

                            take_vol = min(buy_vol, ask_vol)

                            orders.append(
                                Order(product, ask_price, take_vol)
                            )

                            buy_vol -= take_vol
                            current_pos += take_vol

                        else:
                            break

                if order_depth.buy_orders:

                    for bid_price, bid_vol in sorted(
                        order_depth.buy_orders.items(),
                        reverse=True,
                    ):

                        if bid_price > fair_value and sell_vol < 0:

                            take_vol = max(sell_vol, -bid_vol)

                            orders.append(
                                Order(product, bid_price, take_vol)
                            )

                            sell_vol -= take_vol
                            current_pos += take_vol

                        else:
                            break

                # ---------- PASSIVE LADDER QUOTING ----------

                if buy_vol > 0:

                    base_bid = best_bid + 1

                    if base_bid >= best_ask:
                        base_bid = best_bid

                    cap = (
                        fair_value
                        if current_pos < 0
                        else fair_value - spread_offset
                    )

                    base_bid = min(base_bid, cap)

                    chunk1 = int(buy_vol / 3)
                    chunk2 = int(buy_vol / 3)
                    chunk3 = buy_vol - chunk1 - chunk2

                    if chunk1 > 0:
                        orders.append(Order(product, base_bid, chunk1))

                    if chunk2 > 0:
                        orders.append(
                            Order(product, base_bid - spread_offset, chunk2)
                        )

                    if chunk3 > 0:
                        orders.append(
                            Order(product, base_bid - 2 * spread_offset, chunk3)
                        )

                if sell_vol < 0:

                    base_ask = best_ask - 1

                    if base_ask <= best_bid:
                        base_ask = best_ask

                    floor = (
                        fair_value
                        if current_pos > 0
                        else fair_value + spread_offset
                    )

                    base_ask = max(base_ask, floor)

                    chunk1 = int(sell_vol / 3)
                    chunk2 = int(sell_vol / 3)
                    chunk3 = sell_vol - chunk1 - chunk2

                    if chunk1 < 0:
                        orders.append(Order(product, base_ask, chunk1))

                    if chunk2 < 0:
                        orders.append(
                            Order(product, base_ask + spread_offset, chunk2)
                        )

                    if chunk3 < 0:
                        orders.append(
                            Order(product, base_ask + 2 * spread_offset, chunk3)
                        )

            # =====================================================
            # STRATEGY 2: INTARIAN_PEPPER_ROOT
            # =====================================================

            elif product == "INTARIAN_PEPPER_ROOT":

                prev_ask = trader_state.get("PEPPER_PREV_ASK")

                if prev_ask is None:
                    prev_ask = best_ask

                trader_state["PEPPER_PREV_ASK"] = best_ask

                if buy_vol > 0:

                    is_spike = best_ask > prev_ask

                    if not is_spike:

                        orders.append(
                            Order(product, best_ask, buy_vol)
                        )

                    else:

                        my_bid = best_bid + 1

                        if my_bid >= best_ask:
                            my_bid = best_bid

                        orders.append(
                            Order(product, my_bid, buy_vol)
                        )

                if current_pos > 0:

                    orders.append(
                        Order(product, best_ask + 4, -current_pos)
                    )

            result[product] = orders

        return result, conversions, json.dumps(trader_state)