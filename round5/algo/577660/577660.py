from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List, Optional, Tuple
import json


class Trader:
    POSITION_LIMIT = 10

    CHOCOLATE = "OXYGEN_SHAKE_CHOCOLATE"
    EVENING = "OXYGEN_SHAKE_EVENING_BREATH"
    GARLIC = "OXYGEN_SHAKE_GARLIC"
    MINT = "OXYGEN_SHAKE_MINT"
    MORNING = "OXYGEN_SHAKE_MORNING_BREATH"

    TRADED = [CHOCOLATE, EVENING, GARLIC, MINT, MORNING]

    VOL_ALPHA = 0.03
    SPREAD_ALPHA = 0.05
    FAST_ALPHA = 0.06
    SLOW_ALPHA = 0.012

    PARAMS = {
        GARLIC: {
            "mode": "fixed_long",
            "cover_vol_mult": 18.0,
            "cover_spread_mult": 12.0,
            "cover_pct": 0.012,
            "reentry_frac": 0.55,
            "spread_gate_mult": 5.5,
            "spread_floor": 80.0,
        },
        CHOCOLATE: {
            "mode": "detect_direction",
            "min_count": 1000,
            "det_vol_mult": 20.0,
            "det_spread_mult": 20.0,
            "det_pct": 0.018,
            "ema_gap_frac": 0.18,
            "min_conf_ratio": 0.80,
            "confirm_ticks": 3,
            "cover_vol_mult": 16.0,
            "cover_spread_mult": 16.0,
            "cover_pct": 0.014,
            "reentry_frac": 0.55,
            "spread_gate_mult": 5.5,
            "spread_floor": 90.0,
        },
        EVENING: {
            "mode": "paired_strong_direction",
            "pair": MORNING,
            "min_count": 1500,
            "det_vol_mult": 28.0,
            "det_spread_mult": 28.0,
            "det_pct": 0.030,
            "ema_gap_frac": 0.20,
            "min_conf_ratio": 1.60,
            "confirm_ticks": 4,
            "pair_move_frac": 0.45,
            "pair_gap_frac": 0.05,
            "cover_vol_mult": 20.0,
            "cover_spread_mult": 20.0,
            "cover_pct": 0.050,
            "reentry_frac": 0.55,
            "spread_gate_mult": 6.0,
            "spread_floor": 100.0,
        },
        MORNING: {
            "mode": "paired_strong_direction",
            "pair": EVENING,
            "min_count": 1500,
            "det_vol_mult": 28.0,
            "det_spread_mult": 28.0,
            "det_pct": 0.030,
            "ema_gap_frac": 0.20,
            "min_conf_ratio": 1.60,
            "confirm_ticks": 4,
            "pair_move_frac": 0.45,
            "pair_gap_frac": 0.05,
            "cover_vol_mult": 20.0,
            "cover_spread_mult": 20.0,
            "cover_pct": 0.050,
            "reentry_frac": 0.55,
            "spread_gate_mult": 6.0,
            "spread_floor": 100.0,
        },
        MINT: {
            "mode": "neutral_grid",
            "grid_vol_mult": 36.0,
            "grid_spread_mult": 26.0,
            "grid_pct": 0.018,
            "exit_frac": 0.90,
            "stop_mult": 3.50,
            "ref_alpha": 0.001,
            "cool_ticks": 250,
            "spread_gate_mult": 5.0,
            "spread_floor": 90.0,
        },
    }

    def best_bid_ask(self, order_depth: OrderDepth) -> Tuple[Optional[int], Optional[int]]:
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        return best_bid, best_ask

    def mid_price(self, order_depth: OrderDepth) -> Optional[float]:
        best_bid, best_ask = self.best_bid_ask(order_depth)
        if best_bid is not None and best_ask is not None:
            return (best_bid + best_ask) / 2.0
        if best_bid is not None:
            return float(best_bid)
        if best_ask is not None:
            return float(best_ask)
        return None

    def spread(self, order_depth: OrderDepth) -> Optional[int]:
        best_bid, best_ask = self.best_bid_ask(order_depth)
        if best_bid is None or best_ask is None:
            return None
        return best_ask - best_bid

    def fresh_data(self) -> Dict:
        return {
            "init_mid": {},
            "last_mid": {},
            "ema_fast": {},
            "ema_slow": {},
            "vol_ema": {},
            "spread_ema": {},
            "count": {},

            "raw_dir": {},
            "raw_dir_count": {},
            "confirmed_dir": {},

            "active_dir": {},
            "entry_anchor": {},
            "exit_anchor": {},

            "neutral_ref": {},
            "neutral_entry": {},
            "neutral_entry_dir": {},
            "neutral_cooldown": {},
        }

    def load_data(self, trader_data: str, timestamp: int) -> Dict:
        if timestamp == 0:
            return self.fresh_data()

        if not trader_data:
            return self.fresh_data()

        try:
            data = json.loads(trader_data)
        except Exception:
            return self.fresh_data()

        defaults = self.fresh_data()
        for key, value in defaults.items():
            data.setdefault(key, value)
        return data

    def update_indicators(self, data: Dict, product: str, mid: float, spread: Optional[int]) -> None:
        sp = float(spread if spread is not None else 0.0)

        if product not in data["init_mid"]:
            data["init_mid"][product] = mid
            data["last_mid"][product] = mid
            data["ema_fast"][product] = mid
            data["ema_slow"][product] = mid
            data["vol_ema"][product] = 0.0
            data["spread_ema"][product] = max(sp, 1.0)
            data["count"][product] = 1
            data["raw_dir"][product] = 0
            data["raw_dir_count"][product] = 0
            data["confirmed_dir"][product] = 0
            return

        last_mid = float(data["last_mid"].get(product, mid))
        abs_step = abs(mid - last_mid)

        old_vol = float(data["vol_ema"].get(product, 0.0))
        old_spread = float(data["spread_ema"].get(product, max(sp, 1.0)))
        old_fast = float(data["ema_fast"].get(product, mid))
        old_slow = float(data["ema_slow"].get(product, mid))

        data["vol_ema"][product] = self.VOL_ALPHA * abs_step + (1.0 - self.VOL_ALPHA) * old_vol
        data["spread_ema"][product] = self.SPREAD_ALPHA * max(sp, 1.0) + (1.0 - self.SPREAD_ALPHA) * old_spread
        data["ema_fast"][product] = self.FAST_ALPHA * mid + (1.0 - self.FAST_ALPHA) * old_fast
        data["ema_slow"][product] = self.SLOW_ALPHA * mid + (1.0 - self.SLOW_ALPHA) * old_slow
        data["last_mid"][product] = mid
        data["count"][product] = int(data["count"].get(product, 0)) + 1

    def detection_threshold(self, data: Dict, product: str, mid: float) -> float:
        p = self.PARAMS[product]
        vol = max(float(data["vol_ema"].get(product, 1.0)), 1.0)
        sp = max(float(data["spread_ema"].get(product, 1.0)), 1.0)

        return max(
            p["det_vol_mult"] * vol,
            p["det_spread_mult"] * sp,
            p["det_pct"] * mid,
        )

    def cover_threshold(self, data: Dict, product: str, mid: float) -> float:
        p = self.PARAMS[product]
        vol = max(float(data["vol_ema"].get(product, 1.0)), 1.0)
        sp = max(float(data["spread_ema"].get(product, 1.0)), 1.0)

        return max(
            p["cover_vol_mult"] * vol,
            p["cover_spread_mult"] * sp,
            p["cover_pct"] * mid,
        )

    def mint_grid_threshold(self, data: Dict, mid: float) -> float:
        p = self.PARAMS[self.MINT]
        vol = max(float(data["vol_ema"].get(self.MINT, 1.0)), 1.0)
        sp = max(float(data["spread_ema"].get(self.MINT, 1.0)), 1.0)

        return max(
            p["grid_vol_mult"] * vol,
            p["grid_spread_mult"] * sp,
            p["grid_pct"] * mid,
        )

    def spread_allowed(self, data: Dict, product: str) -> float:
        p = self.PARAMS[product]
        sp = max(float(data["spread_ema"].get(product, 1.0)), 1.0)
        return max(float(p["spread_floor"]), float(p["spread_gate_mult"]) * sp)

    def reset_directional_grid(self, data: Dict, product: str, direction: int) -> None:
        data["active_dir"][product] = direction
        data["entry_anchor"][product] = None
        data["exit_anchor"][product] = None

    def pair_confirms(self, data: Dict, product: str, direction: int, pair: str, pair_mid: float) -> bool:
        p = self.PARAMS[product]

        if pair not in data["init_mid"]:
            return False

        pair_move = pair_mid - float(data["init_mid"].get(pair, pair_mid))
        pair_gap = float(data["ema_fast"].get(pair, pair_mid)) - float(data["ema_slow"].get(pair, pair_mid))
        pair_threshold = self.detection_threshold(data, pair, pair_mid)

        move_ok = direction * pair_move <= -float(p["pair_move_frac"]) * pair_threshold
        gap_ok = direction * pair_gap <= -float(p["pair_gap_frac"]) * pair_threshold

        return move_ok and gap_ok

    def detect_direction(self, data: Dict, product: str, mids: Dict[str, float]) -> int:
        if product == self.GARLIC:
            if int(data["confirmed_dir"].get(product, 0)) != 1:
                data["confirmed_dir"][product] = 1
                self.reset_directional_grid(data, product, 1)
            return 1

        confirmed = int(data["confirmed_dir"].get(product, 0))
        if confirmed != 0:
            return confirmed

        if product not in mids:
            return 0

        p = self.PARAMS[product]
        count = int(data["count"].get(product, 0))
        if count < int(p["min_count"]):
            return 0

        mid = mids[product]
        init_mid = float(data["init_mid"].get(product, mid))
        move = mid - init_mid
        threshold = self.detection_threshold(data, product, mid)

        ema_fast = float(data["ema_fast"].get(product, mid))
        ema_slow = float(data["ema_slow"].get(product, mid))
        ema_gap = ema_fast - ema_slow

        candidate = 0
        if abs(move) >= float(p["min_conf_ratio"]) * threshold:
            if move > 0 and ema_gap > float(p["ema_gap_frac"]) * threshold:
                candidate = 1
            elif move < 0 and ema_gap < -float(p["ema_gap_frac"]) * threshold:
                candidate = -1

        if candidate != 0 and p["mode"] == "paired_strong_direction":
            pair = p["pair"]
            if pair not in mids or not self.pair_confirms(data, product, candidate, pair, mids[pair]):
                candidate = 0

        if candidate == 0:
            data["raw_dir"][product] = 0
            data["raw_dir_count"][product] = 0
            return 0

        previous_raw = int(data["raw_dir"].get(product, 0))
        if candidate == previous_raw:
            data["raw_dir_count"][product] = int(data["raw_dir_count"].get(product, 0)) + 1
        else:
            data["raw_dir"][product] = candidate
            data["raw_dir_count"][product] = 1

        if int(data["raw_dir_count"].get(product, 0)) >= int(p["confirm_ticks"]):
            data["confirmed_dir"][product] = candidate
            self.reset_directional_grid(data, product, candidate)
            return candidate

        return 0

    def directional_grid_target(
        self,
        data: Dict,
        product: str,
        order_depth: OrderDepth,
        current_position: int,
        direction: int,
    ) -> int:
        best_bid, best_ask = self.best_bid_ask(order_depth)
        mid = self.mid_price(order_depth)

        if direction == 0 or mid is None or (best_bid is None and best_ask is None):
            return 0

        if int(data["active_dir"].get(product, 0)) != direction:
            self.reset_directional_grid(data, product, direction)

        cover = self.cover_threshold(data, product, mid)
        reentry = float(self.PARAMS[product]["reentry_frac"]) * cover

        entry_anchor = data["entry_anchor"].get(product)
        exit_anchor = data["exit_anchor"].get(product)

        if direction < 0:
            if current_position > 0:
                return 0

            if current_position < 0:
                if entry_anchor is None:
                    entry_anchor = float(best_bid if best_bid is not None else mid)
                    data["entry_anchor"][product] = entry_anchor

                if best_bid is not None and best_bid >= float(entry_anchor) + cover:
                    data["entry_anchor"][product] = None
                    data["exit_anchor"][product] = float(best_ask if best_ask is not None else best_bid)
                    return 0

                return -self.POSITION_LIMIT

            if exit_anchor is None:
                data["entry_anchor"][product] = float(best_bid if best_bid is not None else mid)
                return -self.POSITION_LIMIT

            if best_bid is not None and best_bid >= float(exit_anchor) + reentry:
                data["entry_anchor"][product] = float(best_bid)
                data["exit_anchor"][product] = None
                return -self.POSITION_LIMIT

            return 0

        if direction > 0:
            if current_position < 0:
                return 0

            if current_position > 0:
                if entry_anchor is None:
                    entry_anchor = float(best_ask if best_ask is not None else mid)
                    data["entry_anchor"][product] = entry_anchor

                if best_ask is not None and best_ask <= float(entry_anchor) - cover:
                    data["entry_anchor"][product] = None
                    data["exit_anchor"][product] = float(best_bid if best_bid is not None else best_ask)
                    return 0

                return self.POSITION_LIMIT

            if exit_anchor is None:
                data["entry_anchor"][product] = float(best_ask if best_ask is not None else mid)
                return self.POSITION_LIMIT

            if best_ask is not None and best_ask <= float(exit_anchor) - reentry:
                data["entry_anchor"][product] = float(best_ask)
                data["exit_anchor"][product] = None
                return self.POSITION_LIMIT

            return 0

        return 0

    def neutral_grid_target(self, data: Dict, order_depth: OrderDepth, current_position: int) -> int:
        product = self.MINT
        p = self.PARAMS[product]

        best_bid, best_ask = self.best_bid_ask(order_depth)
        mid = self.mid_price(order_depth)

        if mid is None or (best_bid is None and best_ask is None):
            return 0

        if product not in data["neutral_ref"] or data["neutral_ref"].get(product) is None:
            data["neutral_ref"][product] = mid
            data["neutral_entry"][product] = None
            data["neutral_entry_dir"][product] = 0
            data["neutral_cooldown"][product] = 0

        ref = float(data["neutral_ref"].get(product, mid))
        threshold = self.mint_grid_threshold(data, mid)
        exit_threshold = float(p["exit_frac"]) * threshold
        stop_threshold = float(p["stop_mult"]) * threshold

        if current_position == 0:
            cooldown = int(data["neutral_cooldown"].get(product, 0))
            if cooldown > 0:
                data["neutral_cooldown"][product] = cooldown - 1
                data["neutral_ref"][product] = float(p["ref_alpha"]) * mid + (1.0 - float(p["ref_alpha"])) * ref
                if abs(mid - ref) > 0.5 * threshold:
                    return 0

            if best_ask is not None and best_ask <= ref - threshold:
                data["neutral_entry"][product] = float(best_ask)
                data["neutral_entry_dir"][product] = 1
                return self.POSITION_LIMIT

            if best_bid is not None and best_bid >= ref + threshold:
                data["neutral_entry"][product] = float(best_bid)
                data["neutral_entry_dir"][product] = -1
                return -self.POSITION_LIMIT

            data["neutral_ref"][product] = float(p["ref_alpha"]) * mid + (1.0 - float(p["ref_alpha"])) * ref
            return 0

        if current_position > 0:
            entry = data["neutral_entry"].get(product)
            if entry is None:
                entry = float(best_ask if best_ask is not None else mid)
                data["neutral_entry"][product] = entry

            if best_bid is not None and best_bid >= float(entry) + exit_threshold:
                data["neutral_ref"][product] = float(best_bid)
                data["neutral_entry"][product] = None
                data["neutral_entry_dir"][product] = 0
                return 0

            if best_ask is not None and best_ask <= float(entry) - stop_threshold:
                data["neutral_ref"][product] = mid
                data["neutral_entry"][product] = None
                data["neutral_entry_dir"][product] = 0
                data["neutral_cooldown"][product] = int(p["cool_ticks"])
                return 0

            return self.POSITION_LIMIT

        if current_position < 0:
            entry = data["neutral_entry"].get(product)
            if entry is None:
                entry = float(best_bid if best_bid is not None else mid)
                data["neutral_entry"][product] = entry

            if best_ask is not None and best_ask <= float(entry) - exit_threshold:
                data["neutral_ref"][product] = float(best_ask)
                data["neutral_entry"][product] = None
                data["neutral_entry_dir"][product] = 0
                return 0

            if best_bid is not None and best_bid >= float(entry) + stop_threshold:
                data["neutral_ref"][product] = mid
                data["neutral_entry"][product] = None
                data["neutral_entry_dir"][product] = 0
                data["neutral_cooldown"][product] = int(p["cool_ticks"])
                return 0

            return -self.POSITION_LIMIT

        return 0

    def orders_to_target(
        self,
        product: str,
        order_depth: OrderDepth,
        current_position: int,
        target_position: int,
        max_spread: float,
    ) -> List[Order]:
        orders: List[Order] = []

        target_position = max(-self.POSITION_LIMIT, min(self.POSITION_LIMIT, target_position))
        delta = target_position - current_position

        if delta == 0:
            return orders

        sp = self.spread(order_depth)
        reducing_risk = abs(target_position) < abs(current_position)

        if sp is not None and float(sp) > max_spread and not reducing_risk:
            return orders

        if delta > 0:
            need = delta

            for ask, ask_volume in sorted(order_depth.sell_orders.items()):
                if need <= 0:
                    break

                available = -ask_volume
                if available <= 0:
                    continue

                qty = min(need, available)
                orders.append(Order(product, ask, qty))
                need -= qty

            if need > 0:
                best_bid, best_ask = self.best_bid_ask(order_depth)
                if best_bid is not None and best_ask is not None:
                    price = min(best_bid + 1, best_ask - 1)
                    if price > best_bid:
                        orders.append(Order(product, price, need))
                elif best_bid is not None:
                    orders.append(Order(product, best_bid + 1, need))

        elif delta < 0:
            need = -delta

            for bid, bid_volume in sorted(order_depth.buy_orders.items(), reverse=True):
                if need <= 0:
                    break

                available = bid_volume
                if available <= 0:
                    continue

                qty = min(need, available)
                orders.append(Order(product, bid, -qty))
                need -= qty

            if need > 0:
                best_bid, best_ask = self.best_bid_ask(order_depth)
                if best_bid is not None and best_ask is not None:
                    price = max(best_ask - 1, best_bid + 1)
                    if price < best_ask:
                        orders.append(Order(product, price, -need))
                elif best_ask is not None:
                    orders.append(Order(product, best_ask - 1, -need))

        return orders

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}

        data = self.load_data(state.traderData, state.timestamp)

        for product in state.order_depths:
            result[product] = []

        mids: Dict[str, float] = {}
        spreads: Dict[str, Optional[int]] = {}

        for product in self.TRADED:
            if product not in state.order_depths:
                continue

            order_depth = state.order_depths[product]
            mid = self.mid_price(order_depth)
            if mid is None:
                continue

            spread = self.spread(order_depth)
            mids[product] = mid
            spreads[product] = spread
            self.update_indicators(data, product, mid, spread)

        for product in self.TRADED:
            if product not in state.order_depths or product not in mids:
                continue

            current_position = state.position.get(product, 0)
            order_depth = state.order_depths[product]

            if product == self.MINT:
                target = self.neutral_grid_target(data, order_depth, current_position)
            else:
                direction = self.detect_direction(data, product, mids)
                target = self.directional_grid_target(
                    data=data,
                    product=product,
                    order_depth=order_depth,
                    current_position=current_position,
                    direction=direction,
                )

            result[product] = self.orders_to_target(
                product=product,
                order_depth=order_depth,
                current_position=current_position,
                target_position=target,
                max_spread=self.spread_allowed(data, product),
            )

        traderData = json.dumps(data, separators=(",", ":"))
        conversions = 0
        return result, conversions, traderData