from datamodel import OrderDepth, TradingState, Order, UserId
import json, math

class _OxygenShakeStrategy:
    POSITION_LIMIT = 10
    CHOCOLATE, EVENING, GARLIC = "OXYGEN_SHAKE_CHOCOLATE", "OXYGEN_SHAKE_EVENING_BREATH", "OXYGEN_SHAKE_GARLIC"
    MINT, MORNING = "OXYGEN_SHAKE_MINT", "OXYGEN_SHAKE_MORNING_BREATH"
    TRADED = [CHOCOLATE, EVENING, GARLIC, MINT, MORNING]
    VOL_ALPHA, SPREAD_ALPHA, FAST_ALPHA, SLOW_ALPHA = 0.03, 0.05, 0.06, 0.012
    PARAMS = {
        GARLIC: {"mode": "fixed_long", "cover_vol_mult": 18.0, "cover_spread_mult": 12.0, "cover_pct": 0.012, "reentry_frac": 0.55, "spread_gate_mult": 5.5, "spread_floor": 80.0},
        CHOCOLATE: {"mode": "detect_direction", "min_count": 1000, "det_vol_mult": 20.0, "det_spread_mult": 20.0, "det_pct": 0.018, "ema_gap_frac": 0.18, "min_conf_ratio": 0.80, "confirm_ticks": 3, "cover_vol_mult": 16.0, "cover_spread_mult": 16.0, "cover_pct": 0.014, "reentry_frac": 0.55, "spread_gate_mult": 5.5, "spread_floor": 90.0},
        EVENING: {"mode": "paired_strong_direction", "pair": MORNING, "min_count": 1500, "det_vol_mult": 28.0, "det_spread_mult": 28.0, "det_pct": 0.030, "ema_gap_frac": 0.20, "min_conf_ratio": 1.60, "confirm_ticks": 4, "pair_move_frac": 0.45, "pair_gap_frac": 0.05, "cover_vol_mult": 20.0, "cover_spread_mult": 20.0, "cover_pct": 0.050, "reentry_frac": 0.55, "spread_gate_mult": 6.0, "spread_floor": 100.0},
        MORNING: {"mode": "paired_strong_direction", "pair": EVENING, "min_count": 1500, "det_vol_mult": 28.0, "det_spread_mult": 28.0, "det_pct": 0.030, "ema_gap_frac": 0.20, "min_conf_ratio": 1.60, "confirm_ticks": 4, "pair_move_frac": 0.45, "pair_gap_frac": 0.05, "cover_vol_mult": 20.0, "cover_spread_mult": 20.0, "cover_pct": 0.050, "reentry_frac": 0.55, "spread_gate_mult": 6.0, "spread_floor": 100.0},
        MINT: {"mode": "neutral_grid", "grid_vol_mult": 36.0, "grid_spread_mult": 26.0, "grid_pct": 0.018, "exit_frac": 0.90, "stop_mult": 3.50, "ref_alpha": 0.001, "cool_ticks": 250, "spread_gate_mult": 5.0, "spread_floor": 90.0},
    }
    def best_bid_ask(self, order_depth):
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        return best_bid, best_ask
    def mid_price(self, order_depth):
        best_bid, best_ask = self.best_bid_ask(order_depth)
        if best_bid is not None and best_ask is not None: return (best_bid + best_ask) / 2.0
        if best_bid is not None: return float(best_bid)
        if best_ask is not None: return float(best_ask)
        return None
    def spread(self, order_depth):
        best_bid, best_ask = self.best_bid_ask(order_depth)
        if best_bid is None or best_ask is None: return None
        return best_ask - best_bid
    def fresh_data(self):
        return {"init_mid": {}, "last_mid": {}, "ema_fast": {}, "ema_slow": {}, "vol_ema": {}, "spread_ema": {}, "count": {}, "raw_dir": {}, "raw_dir_count": {}, "confirmed_dir": {}, "active_dir": {}, "entry_anchor": {}, "exit_anchor": {}, "neutral_ref": {}, "neutral_entry": {}, "neutral_entry_dir": {}, "neutral_cooldown": {}}
    def load_data(self, trader_data, timestamp):
        if timestamp == 0 or not trader_data: return self.fresh_data()
        try: data = json.loads(trader_data)
        except Exception: return self.fresh_data()
        defaults = self.fresh_data()
        for key, value in defaults.items(): data.setdefault(key, value)
        return data
    def update_indicators(self, data, product, mid, spread):
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
    def detection_threshold(self, data, product, mid):
        p = self.PARAMS[product]
        vol = max(float(data["vol_ema"].get(product, 1.0)), 1.0)
        sp = max(float(data["spread_ema"].get(product, 1.0)), 1.0)
        return max(p["det_vol_mult"] * vol, p["det_spread_mult"] * sp, p["det_pct"] * mid)
    def cover_threshold(self, data, product, mid):
        p = self.PARAMS[product]
        vol = max(float(data["vol_ema"].get(product, 1.0)), 1.0)
        sp = max(float(data["spread_ema"].get(product, 1.0)), 1.0)
        return max(p["cover_vol_mult"] * vol, p["cover_spread_mult"] * sp, p["cover_pct"] * mid)
    def mint_grid_threshold(self, data, mid):
        p = self.PARAMS[self.MINT]
        vol = max(float(data["vol_ema"].get(self.MINT, 1.0)), 1.0)
        sp = max(float(data["spread_ema"].get(self.MINT, 1.0)), 1.0)
        return max(p["grid_vol_mult"] * vol, p["grid_spread_mult"] * sp, p["grid_pct"] * mid)
    def spread_allowed(self, data, product):
        p = self.PARAMS[product]
        sp = max(float(data["spread_ema"].get(product, 1.0)), 1.0)
        return max(float(p["spread_floor"]), float(p["spread_gate_mult"]) * sp)
    def reset_directional_grid(self, data, product, direction):
        data["active_dir"][product] = direction
        data["entry_anchor"][product] = None
        data["exit_anchor"][product] = None
    def pair_confirms(self, data, product, direction, pair, pair_mid):
        p = self.PARAMS[product]
        if pair not in data["init_mid"]: return False
        pair_move = pair_mid - float(data["init_mid"].get(pair, pair_mid))
        pair_gap = float(data["ema_fast"].get(pair, pair_mid)) - float(data["ema_slow"].get(pair, pair_mid))
        pair_threshold = self.detection_threshold(data, pair, pair_mid)
        move_ok = direction * pair_move <= -float(p["pair_move_frac"]) * pair_threshold
        gap_ok = direction * pair_gap <= -float(p["pair_gap_frac"]) * pair_threshold
        return move_ok and gap_ok
    def detect_direction(self, data, product, mids):
        if product == self.GARLIC:
            if int(data["confirmed_dir"].get(product, 0)) != 1:
                data["confirmed_dir"][product] = 1
                self.reset_directional_grid(data, product, 1)
            return 1
        confirmed = int(data["confirmed_dir"].get(product, 0))
        if confirmed != 0: return confirmed
        if product not in mids: return 0
        p = self.PARAMS[product]
        count = int(data["count"].get(product, 0))
        if count < int(p["min_count"]): return 0
        mid = mids[product]
        init_mid = float(data["init_mid"].get(product, mid))
        move = mid - init_mid
        threshold = self.detection_threshold(data, product, mid)
        ema_fast = float(data["ema_fast"].get(product, mid))
        ema_slow = float(data["ema_slow"].get(product, mid))
        ema_gap = ema_fast - ema_slow
        candidate = 0
        if abs(move) >= float(p["min_conf_ratio"]) * threshold:
            if move > 0 and ema_gap > float(p["ema_gap_frac"]) * threshold: candidate = 1
            elif move < 0 and ema_gap < -float(p["ema_gap_frac"]) * threshold: candidate = -1
        if candidate != 0 and p["mode"] == "paired_strong_direction":
            pair = p["pair"]
            if pair not in mids or not self.pair_confirms(data, product, candidate, pair, mids[pair]): candidate = 0
        if candidate == 0:
            data["raw_dir"][product] = 0
            data["raw_dir_count"][product] = 0
            return 0
        previous_raw = int(data["raw_dir"].get(product, 0))
        if candidate == previous_raw: data["raw_dir_count"][product] = int(data["raw_dir_count"].get(product, 0)) + 1
        else:
            data["raw_dir"][product] = candidate
            data["raw_dir_count"][product] = 1
        if int(data["raw_dir_count"].get(product, 0)) >= int(p["confirm_ticks"]):
            data["confirmed_dir"][product] = candidate
            self.reset_directional_grid(data, product, candidate)
            return candidate
        return 0
    def directional_grid_target(self, data, product, order_depth, current_position, direction):
        best_bid, best_ask = self.best_bid_ask(order_depth)
        mid = self.mid_price(order_depth)
        if direction == 0 or mid is None or (best_bid is None and best_ask is None): return 0
        if int(data["active_dir"].get(product, 0)) != direction: self.reset_directional_grid(data, product, direction)
        cover = self.cover_threshold(data, product, mid)
        reentry = float(self.PARAMS[product]["reentry_frac"]) * cover
        entry_anchor = data["entry_anchor"].get(product)
        exit_anchor = data["exit_anchor"].get(product)
        if direction < 0:
            if current_position > 0: return 0
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
            if current_position < 0: return 0
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
    def neutral_grid_target(self, data, order_depth, current_position):
        product = self.MINT
        p = self.PARAMS[product]
        best_bid, best_ask = self.best_bid_ask(order_depth)
        mid = self.mid_price(order_depth)
        if mid is None or (best_bid is None and best_ask is None): return 0
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
                if abs(mid - ref) > 0.5 * threshold: return 0
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
    def orders_to_target(self, product, order_depth, current_position, target_position, max_spread):
        orders = []
        target_position = max(-self.POSITION_LIMIT, min(self.POSITION_LIMIT, target_position))
        delta = target_position - current_position
        if delta == 0: return orders
        sp = self.spread(order_depth)
        reducing_risk = abs(target_position) < abs(current_position)
        if sp is not None and float(sp) > max_spread and not reducing_risk: return orders
        if delta > 0:
            need = delta
            for ask, ask_volume in sorted(order_depth.sell_orders.items()):
                if need <= 0: break
                available = -ask_volume
                if available <= 0: continue
                qty = min(need, available)
                orders.append(Order(product, ask, qty))
                need -= qty
            if need > 0:
                best_bid, best_ask = self.best_bid_ask(order_depth)
                if best_bid is not None and best_ask is not None:
                    price = min(best_bid + 1, best_ask - 1)
                    if price > best_bid: orders.append(Order(product, price, need))
                elif best_bid is not None: orders.append(Order(product, best_bid + 1, need))
        elif delta < 0:
            need = -delta
            for bid, bid_volume in sorted(order_depth.buy_orders.items(), reverse=True):
                if need <= 0: break
                available = bid_volume
                if available <= 0: continue
                qty = min(need, available)
                orders.append(Order(product, bid, -qty))
                need -= qty
            if need > 0:
                best_bid, best_ask = self.best_bid_ask(order_depth)
                if best_bid is not None and best_ask is not None:
                    price = max(best_ask - 1, best_bid + 1)
                    if price < best_ask: orders.append(Order(product, price, -need))
                elif best_ask is not None: orders.append(Order(product, best_ask - 1, -need))
        return orders
    def run_with_data(self, state, trader_data):
        result = {}
        data = self.load_data(trader_data, state.timestamp)
        for product in state.order_depths: result[product] = []
        mids, spreads = {}, {}
        for product in self.TRADED:
            if product not in state.order_depths: continue
            order_depth = state.order_depths[product]
            mid = self.mid_price(order_depth)
            if mid is None: continue
            spread = self.spread(order_depth)
            mids[product] = mid
            spreads[product] = spread
            self.update_indicators(data, product, mid, spread)
        for product in self.TRADED:
            if product not in state.order_depths or product not in mids: continue
            current_position = state.position.get(product, 0)
            order_depth = state.order_depths[product]
            if product == self.MINT: target = self.neutral_grid_target(data, order_depth, current_position)
            else:
                direction = self.detect_direction(data, product, mids)
                target = self.directional_grid_target(data=data, product=product, order_depth=order_depth, current_position=current_position, direction=direction)
            result[product] = self.orders_to_target(product=product, order_depth=order_depth, current_position=current_position, target_position=target, max_spread=self.spread_allowed(data, product))
        return result, 0, json.dumps(data, separators=(",", ":"))

class _PebblesStrategy:
    POSITION_LIMIT = 10
    XS, S, M, L, XL = 'PEBBLES_XS', 'PEBBLES_S', 'PEBBLES_M', 'PEBBLES_L', 'PEBBLES_XL'
    TRADED = {XS, S, M, L, XL}
    ALL_PEBBLES = [XS, S, M, L, XL]
    SHORT_COVER_BUFFER = {XS: 200.0, S: 200.0}
    SHORT_REENTRY_BUFFER = {XS: 100.0, S: 100.0}
    M_GRID_THRESHOLD = 300.0
    L_GRID_THRESHOLD = 100.0
    XL_COVER_BUFFER, XL_REENTRY_BUFFER = 100.0, 100.0
    XL_LONG_XSS_TRIGGER, XL_LONG_REST_MIN, XL_LONG_REST_STRONG, XL_LONG_ML_MAX = 450.0, 250.0, 900.0, 100.0
    XL_SHORT_ML_TRIGGER, XL_SHORT_REST_MIN, XL_SHORT_REST_STRONG, XL_SHORT_ML_MIN = 800.0, 300.0, 1000.0, 700.0
    XL_CONFIRM_COUNT = 2
    def bid(self): return 15
    def best_bid_ask(self, order_depth):
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        return (best_bid, best_ask)
    def mid_price(self, order_depth):
        best_bid, best_ask = self.best_bid_ask(order_depth)
        if best_bid is not None and best_ask is not None: return (best_bid + best_ask) / 2.0
        if best_bid is not None: return float(best_bid)
        if best_ask is not None: return float(best_ask)
        return None
    def spread(self, order_depth):
        best_bid, best_ask = self.best_bid_ask(order_depth)
        if best_bid is None or best_ask is None: return None
        return best_ask - best_bid
    def fresh_data(self):
        return {'init_mid': {}, 'last_mid': {}, 'short_anchor': {}, 'cover_anchor': {}, 'grid_ref': {}, 'grid_entry': {}, 'grid_dir': {}, 'xl_raw_signal': 0, 'xl_signal_count': 0, 'xl_confirmed_signal': 0, 'xl_buffer_dir': 0, 'xl_entry_anchor': None, 'xl_exit_anchor': None, 'xl_paused_dir': 0, 'pebble_sum_ref': None}
    def load_data(self, trader_data, timestamp):
        if timestamp == 0 or not trader_data: return self.fresh_data()
        try: data = json.loads(trader_data)
        except Exception: return self.fresh_data()
        for k in ['init_mid', 'last_mid', 'short_anchor', 'cover_anchor', 'grid_ref', 'grid_entry', 'grid_dir']: data.setdefault(k, {})
        data.setdefault('xl_raw_signal', 0); data.setdefault('xl_signal_count', 0); data.setdefault('xl_confirmed_signal', 0)
        data.setdefault('xl_buffer_dir', 0); data.setdefault('xl_entry_anchor', None); data.setdefault('xl_exit_anchor', None)
        data.setdefault('xl_paused_dir', 0); data.setdefault('pebble_sum_ref', None)
        return data
    def update_state(self, data, mids):
        for product in self.ALL_PEBBLES:
            if product not in mids: continue
            mid = mids[product]
            if product not in data['init_mid']: data['init_mid'][product] = mid
            data['last_mid'][product] = mid
    def buffered_short_target(self, product, order_depth, current_position, data):
        best_bid, best_ask = self.best_bid_ask(order_depth)
        if best_bid is None and best_ask is None: return current_position
        cover_buffer = self.SHORT_COVER_BUFFER[product]
        reentry_buffer = self.SHORT_REENTRY_BUFFER[product]
        short_anchor = data['short_anchor'].get(product)
        cover_anchor = data['cover_anchor'].get(product)
        if current_position < 0:
            if short_anchor is None:
                if best_bid is not None: short_anchor = float(best_bid)
                else:
                    mid = self.mid_price(order_depth)
                    short_anchor = float(mid) if mid is not None else 0.0
                data['short_anchor'][product] = short_anchor
            if best_bid is not None and best_bid >= short_anchor + cover_buffer:
                data['cover_anchor'][product] = float(best_ask) if best_ask is not None else float(best_bid)
                return 0
            return -self.POSITION_LIMIT
        else:
            if current_position > 0: return 0
            if cover_anchor is None:
                if best_bid is not None: data['short_anchor'][product] = float(best_bid)
                else:
                    mid = self.mid_price(order_depth)
                    data['short_anchor'][product] = float(mid) if mid is not None else 0.0
                return -self.POSITION_LIMIT
            if best_bid is not None and best_bid >= cover_anchor + reentry_buffer:
                data['short_anchor'][product] = float(best_bid)
                return -self.POSITION_LIMIT
            return 0
    def reset_grid_position_state(self, data, product):
        data['grid_entry'][product] = None
        data['grid_dir'][product] = 0
    def long_only_grid_target(self, product, order_depth, current_position, data, threshold):
        best_bid, best_ask = self.best_bid_ask(order_depth)
        mid = self.mid_price(order_depth)
        if best_bid is None and best_ask is None and (mid is None): return current_position
        if product not in data['grid_ref'] or data['grid_ref'].get(product) is None:
            data['grid_ref'][product] = float(mid if mid is not None else best_ask if best_ask is not None else best_bid)
            self.reset_grid_position_state(data, product)
        ref = float(data['grid_ref'][product])
        entry = data['grid_entry'].get(product)
        if current_position < 0:
            self.reset_grid_position_state(data, product)
            return 0
        if current_position > 0:
            if entry is None:
                entry = float(mid if mid is not None else best_ask if best_ask is not None else best_bid)
                data['grid_entry'][product] = entry
                data['grid_dir'][product] = 1
            if best_bid is not None and best_bid >= entry + threshold:
                data['grid_ref'][product] = float(best_bid)
                self.reset_grid_position_state(data, product)
                return 0
            return self.POSITION_LIMIT
        self.reset_grid_position_state(data, product)
        if best_ask is not None and best_ask <= ref - threshold:
            data['grid_entry'][product] = float(best_ask)
            data['grid_dir'][product] = 1
            return self.POSITION_LIMIT
        return 0
    def symmetric_grid_target(self, product, order_depth, current_position, data, threshold):
        best_bid, best_ask = self.best_bid_ask(order_depth)
        mid = self.mid_price(order_depth)
        if best_bid is None and best_ask is None and (mid is None): return current_position
        if product not in data['grid_ref'] or data['grid_ref'].get(product) is None:
            data['grid_ref'][product] = float(mid if mid is not None else best_ask if best_ask is not None else best_bid)
            self.reset_grid_position_state(data, product)
        ref = float(data['grid_ref'][product])
        entry = data['grid_entry'].get(product)
        if current_position > 0:
            if entry is None:
                entry = float(mid if mid is not None else best_ask if best_ask is not None else best_bid)
                data['grid_entry'][product] = entry
                data['grid_dir'][product] = 1
            if best_bid is not None and best_bid >= entry + threshold:
                data['grid_ref'][product] = float(best_bid)
                self.reset_grid_position_state(data, product)
                return 0
            return self.POSITION_LIMIT
        if current_position < 0:
            if entry is None:
                entry = float(mid if mid is not None else best_bid if best_bid is not None else best_ask)
                data['grid_entry'][product] = entry
                data['grid_dir'][product] = -1
            if best_ask is not None and best_ask <= entry - threshold:
                data['grid_ref'][product] = float(best_ask)
                self.reset_grid_position_state(data, product)
                return 0
            return -self.POSITION_LIMIT
        self.reset_grid_position_state(data, product)
        if best_ask is not None and best_ask <= ref - threshold:
            data['grid_entry'][product] = float(best_ask)
            data['grid_dir'][product] = 1
            return self.POSITION_LIMIT
        if best_bid is not None and best_bid >= ref + threshold:
            data['grid_entry'][product] = float(best_bid)
            data['grid_dir'][product] = -1
            return -self.POSITION_LIMIT
        return 0
    def pebble_identity_ok(self, data, mids):
        if not all((p in mids for p in self.ALL_PEBBLES)): return False
        pebble_sum = sum((mids[p] for p in self.ALL_PEBBLES))
        if data.get('pebble_sum_ref') is None:
            data['pebble_sum_ref'] = pebble_sum
            return True
        return abs(pebble_sum - data['pebble_sum_ref']) <= 250
    def compute_xl_signal(self, data, mids):
        required = [self.XS, self.S, self.M, self.L, self.XL]
        if not all((p in mids for p in required)): return 0
        init = data['init_mid']
        if not all((p in init for p in required)): return 0
        xs_s_move = (mids[self.XS] + mids[self.S]) - (init[self.XS] + init[self.S])
        ml_move = (mids[self.M] + mids[self.L]) - (init[self.M] + init[self.L])
        rest4_move = xs_s_move + ml_move
        short_signal = ml_move > self.XL_SHORT_ML_TRIGGER and rest4_move > self.XL_SHORT_REST_MIN or (rest4_move > self.XL_SHORT_REST_STRONG and ml_move > self.XL_SHORT_ML_MIN)
        long_signal = xs_s_move < -self.XL_LONG_XSS_TRIGGER and ml_move < self.XL_LONG_ML_MAX and (rest4_move < -self.XL_LONG_REST_MIN) or (rest4_move < -self.XL_LONG_REST_STRONG and ml_move < self.XL_LONG_ML_MAX)
        if short_signal: return -1
        if long_signal: return +1
        return 0
    def confirmed_xl_signal(self, data, raw_signal):
        if raw_signal == 0: return data.get('xl_confirmed_signal', 0)
        if raw_signal == data.get('xl_raw_signal', 0): data['xl_signal_count'] = data.get('xl_signal_count', 0) + 1
        else:
            data['xl_signal_count'] = 1
            data['xl_raw_signal'] = raw_signal
        if data['xl_signal_count'] >= self.XL_CONFIRM_COUNT: data['xl_confirmed_signal'] = raw_signal
        return data.get('xl_confirmed_signal', 0)
    def reset_xl_buffer(self, data, direction):
        data['xl_buffer_dir'] = direction
        data['xl_entry_anchor'] = None
        data['xl_exit_anchor'] = None
        data['xl_paused_dir'] = 0
    def buffered_xl_target(self, order_depth, current_position, desired_signal, desired_abs_position, data):
        best_bid, best_ask = self.best_bid_ask(order_depth)
        if best_bid is None and best_ask is None: return current_position
        if desired_signal == 0 or desired_abs_position <= 0:
            self.reset_xl_buffer(data, 0)
            return 0
        desired_abs_position = max(0, min(self.POSITION_LIMIT, desired_abs_position))
        if data.get('xl_buffer_dir', 0) != desired_signal: self.reset_xl_buffer(data, desired_signal)
        entry_anchor, exit_anchor, paused_dir = data.get('xl_entry_anchor'), data.get('xl_exit_anchor'), data.get('xl_paused_dir', 0)
        mid = self.mid_price(order_depth)
        if desired_signal > 0:
            if current_position > 0:
                if entry_anchor is None:
                    data['xl_entry_anchor'] = entry_anchor = float(best_ask if best_ask is not None else mid if mid is not None else 0.0)
                if best_ask is not None and best_ask <= entry_anchor - self.XL_COVER_BUFFER:
                    data['xl_exit_anchor'] = float(best_bid if best_bid is not None else best_ask)
                    data['xl_entry_anchor'] = None
                    data['xl_paused_dir'] = +1
                    return 0
                return desired_abs_position
            else:
                if paused_dir != +1 or exit_anchor is None:
                    data['xl_entry_anchor'] = float(best_ask if best_ask is not None else mid if mid is not None else 0.0)
                    data['xl_exit_anchor'], data['xl_paused_dir'] = None, 0
                    return desired_abs_position
                if best_ask is not None and best_ask <= exit_anchor - self.XL_REENTRY_BUFFER:
                    data['xl_entry_anchor'] = float(best_ask)
                    data['xl_exit_anchor'], data['xl_paused_dir'] = None, 0
                    return desired_abs_position
                return 0
        elif current_position < 0:
            if entry_anchor is None:
                data['xl_entry_anchor'] = entry_anchor = float(best_bid if best_bid is not None else mid if mid is not None else 0.0)
            if best_bid is not None and best_bid >= entry_anchor + self.XL_COVER_BUFFER:
                data['xl_exit_anchor'] = float(best_ask if best_ask is not None else best_bid)
                data['xl_entry_anchor'], data['xl_paused_dir'] = None, -1
                return 0
            return -desired_abs_position
        else:
            if paused_dir != -1 or exit_anchor is None:
                data['xl_entry_anchor'] = float(best_bid if best_bid is not None else mid if mid is not None else 0.0)
                data['xl_exit_anchor'], data['xl_paused_dir'] = None, 0
                return -desired_abs_position
            if best_bid is not None and best_bid >= exit_anchor + self.XL_REENTRY_BUFFER:
                data['xl_entry_anchor'] = float(best_bid)
                data['xl_exit_anchor'], data['xl_paused_dir'] = None, 0
                return -desired_abs_position
            return 0
    def orders_to_target(self, product, order_depth, current_position, target_position, max_spread):
        orders = []
        target_position = max(-self.POSITION_LIMIT, min(self.POSITION_LIMIT, target_position))
        delta = target_position - current_position
        if delta == 0: return orders
        sp = self.spread(order_depth)
        reducing_risk = abs(target_position) < abs(current_position)
        if sp is not None and sp > max_spread and (not reducing_risk): return orders
        if delta > 0:
            need = delta
            for ask, ask_volume in sorted(order_depth.sell_orders.items()):
                if need <= 0: break
                available = -ask_volume
                if available <= 0: continue
                qty = min(need, available)
                orders.append(Order(product, ask, qty))
                need -= qty
            if need > 0:
                best_bid, best_ask = self.best_bid_ask(order_depth)
                if best_bid is not None and best_ask is not None:
                    price = min(best_bid + 1, best_ask - 1)
                    if price > best_bid: orders.append(Order(product, price, need))
                elif best_bid is not None: orders.append(Order(product, best_bid + 1, need))
        elif delta < 0:
            need = -delta
            for bid, bid_volume in sorted(order_depth.buy_orders.items(), reverse=True):
                if need <= 0: break
                available = bid_volume
                if available <= 0: continue
                qty = min(need, available)
                orders.append(Order(product, bid, -qty))
                need -= qty
            if need > 0:
                best_bid, best_ask = self.best_bid_ask(order_depth)
                if best_bid is not None and best_ask is not None:
                    price = max(best_ask - 1, best_bid + 1)
                    if price < best_ask: orders.append(Order(product, price, -need))
                elif best_ask is not None: orders.append(Order(product, best_ask - 1, -need))
        return orders
    def run_with_data(self, state, trader_data):
        result = {}
        data = self.load_data(trader_data, state.timestamp)
        mids = {}
        for product, order_depth in state.order_depths.items():
            mid = self.mid_price(order_depth)
            if mid is not None: mids[product] = mid
        self.update_state(data, mids)
        identity_ok = self.pebble_identity_ok(data, mids)
        for product in state.order_depths: result[product] = []
        for product in [self.XS, self.S]:
            if product not in state.order_depths: continue
            current_position = state.position.get(product, 0)
            target = self.buffered_short_target(product=product, order_depth=state.order_depths[product], current_position=current_position, data=data)
            result[product] = self.orders_to_target(product=product, order_depth=state.order_depths[product], current_position=current_position, target_position=target, max_spread=80)
        if self.M in state.order_depths:
            current_position = state.position.get(self.M, 0)
            target = self.long_only_grid_target(product=self.M, order_depth=state.order_depths[self.M], current_position=current_position, data=data, threshold=self.M_GRID_THRESHOLD)
            result[self.M] = self.orders_to_target(product=self.M, order_depth=state.order_depths[self.M], current_position=current_position, target_position=target, max_spread=100)
        if self.L in state.order_depths:
            current_position = state.position.get(self.L, 0)
            target = self.symmetric_grid_target(product=self.L, order_depth=state.order_depths[self.L], current_position=current_position, data=data, threshold=self.L_GRID_THRESHOLD)
            result[self.L] = self.orders_to_target(product=self.L, order_depth=state.order_depths[self.L], current_position=current_position, target_position=target, max_spread=100)
        if self.XL in state.order_depths and identity_ok:
            raw_xl_signal = self.compute_xl_signal(data, mids)
            xl_signal = self.confirmed_xl_signal(data, raw_xl_signal)
            if raw_xl_signal != 0 and xl_signal != 0 and (raw_xl_signal != xl_signal): desired_signal, desired_abs_position = 0, 0
            elif xl_signal != 0: desired_signal, desired_abs_position = xl_signal, 10
            elif raw_xl_signal != 0: desired_signal, desired_abs_position = raw_xl_signal, 5
            else: desired_signal, desired_abs_position = 0, 0
            current_position = state.position.get(self.XL, 0)
            xl_target = self.buffered_xl_target(order_depth=state.order_depths[self.XL], current_position=current_position, desired_signal=desired_signal, desired_abs_position=desired_abs_position, data=data)
            result[self.XL] = self.orders_to_target(product=self.XL, order_depth=state.order_depths[self.XL], current_position=current_position, target_position=xl_target, max_spread=100)
        elif self.XL in state.order_depths:
            self.reset_xl_buffer(data, 0)
            current_position = state.position.get(self.XL, 0)
            result[self.XL] = self.orders_to_target(product=self.XL, order_depth=state.order_depths[self.XL], current_position=current_position, target_position=0, max_spread=100)
        return result, 0, json.dumps(data, separators=(',', ':'))

class _SnackpackStrategy:
    POSITION_LIMIT = 10
    CHOCOLATE, VANILLA, PISTACHIO, STRAWBERRY, RASPBERRY = 'SNACKPACK_CHOCOLATE', 'SNACKPACK_VANILLA', 'SNACKPACK_PISTACHIO', 'SNACKPACK_STRAWBERRY', 'SNACKPACK_RASPBERRY'
    TRADED = {CHOCOLATE, VANILLA, PISTACHIO, STRAWBERRY, RASPBERRY}
    SYMMETRIC_GRID_LAYERS = {CHOCOLATE: [(125.0, 2), (150.0, 8)], VANILLA: [(125.0, 2), (150.0, 8)], RASPBERRY: [(75.0, 8), (100.0, 2)], PISTACHIO: [(75.0, 5), (150.0, 5)], STRAWBERRY: [(300.0, 4), (400.0, 6)]}
    def bid(self): return 15
    def best_bid_ask(self, order_depth):
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        return (best_bid, best_ask)
    def mid_price(self, order_depth):
        best_bid, best_ask = self.best_bid_ask(order_depth)
        if best_bid is not None and best_ask is not None: return (best_bid + best_ask) / 2.0
        if best_bid is not None: return float(best_bid)
        if best_ask is not None: return float(best_ask)
        return None
    def spread(self, order_depth):
        best_bid, best_ask = self.best_bid_ask(order_depth)
        if best_bid is None or best_ask is None: return None
        return best_ask - best_bid
    def usable_price(self, order_depth):
        mid = self.mid_price(order_depth)
        if mid is not None: return mid
        best_bid, best_ask = self.best_bid_ask(order_depth)
        if best_bid is not None: return float(best_bid)
        if best_ask is not None: return float(best_ask)
        return None
    def fresh_data(self): return {'layer_ref': {}, 'layer_entry': {}, 'layer_dir': {}, 'last_mid': {}}
    def load_data(self, trader_data, timestamp):
        if timestamp == 0 or not trader_data: return self.fresh_data()
        try: data = json.loads(trader_data)
        except Exception: return self.fresh_data()
        for k in ['layer_ref', 'layer_entry', 'layer_dir', 'last_mid']: data.setdefault(k, {})
        return data
    def layer_key(self, product, layer_idx): return product + '#' + str(layer_idx)
    def init_layer_if_needed(self, data, key, initial_price):
        if key not in data['layer_ref'] or data['layer_ref'].get(key) is None:
            data['layer_ref'][key] = float(initial_price)
            data['layer_entry'][key] = None
            data['layer_dir'][key] = 0
    def reset_layer_position_state(self, data, key):
        data['layer_entry'][key] = None
        data['layer_dir'][key] = 0
    def update_last_mid(self, data, product, mid):
        if mid is not None: data['last_mid'][product] = mid
    def layered_symmetric_grid_target(self, product, order_depth, data):
        best_bid, best_ask = self.best_bid_ask(order_depth)
        usable = self.usable_price(order_depth)
        if usable is None: return 0
        target = 0
        layers = self.SYMMETRIC_GRID_LAYERS[product]
        for idx, (threshold, qty) in enumerate(layers):
            key = self.layer_key(product, idx)
            self.init_layer_if_needed(data, key, usable)
            ref = float(data['layer_ref'][key])
            entry = data['layer_entry'].get(key)
            layer_dir = int(data['layer_dir'].get(key, 0))
            if layer_dir > 0:
                if entry is None: data['layer_entry'][key] = entry = usable
                if best_bid is not None and best_bid >= float(entry) + threshold:
                    data['layer_ref'][key] = float(best_bid)
                    self.reset_layer_position_state(data, key)
                    layer_dir = 0
                else: target += qty; continue
            elif layer_dir < 0:
                if entry is None: data['layer_entry'][key] = entry = usable
                if best_ask is not None and best_ask <= float(entry) - threshold:
                    data['layer_ref'][key] = float(best_ask)
                    self.reset_layer_position_state(data, key)
                    layer_dir = 0
                else: target -= qty; continue
            if layer_dir == 0:
                if best_ask is not None and best_ask <= ref - threshold:
                    data['layer_entry'][key] = float(best_ask)
                    data['layer_dir'][key] = +1
                    target += qty
                elif best_bid is not None and best_bid >= ref + threshold:
                    data['layer_entry'][key] = float(best_bid)
                    data['layer_dir'][key] = -1
                    target -= qty
        return max(-self.POSITION_LIMIT, min(self.POSITION_LIMIT, target))
    def orders_to_target(self, product, order_depth, current_position, target_position, max_spread):
        orders = []
        target_position = max(-self.POSITION_LIMIT, min(self.POSITION_LIMIT, target_position))
        delta = target_position - current_position
        if delta == 0: return orders
        sp = self.spread(order_depth)
        reducing_risk = abs(target_position) < abs(current_position)
        if sp is not None and sp > max_spread and (not reducing_risk): return orders
        if delta > 0:
            need = delta
            for ask, ask_volume in sorted(order_depth.sell_orders.items()):
                if need <= 0: break
                available = -ask_volume
                if available <= 0: continue
                qty = min(need, available)
                orders.append(Order(product, ask, qty))
                need -= qty
            if need > 0:
                best_bid, best_ask = self.best_bid_ask(order_depth)
                if best_bid is not None and best_ask is not None:
                    price = min(best_bid + 1, best_ask - 1)
                    if price > best_bid: orders.append(Order(product, price, need))
                elif best_bid is not None: orders.append(Order(product, best_bid + 1, need))
        elif delta < 0:
            need = -delta
            for bid, bid_volume in sorted(order_depth.buy_orders.items(), reverse=True):
                if need <= 0: break
                available = bid_volume
                if available <= 0: continue
                qty = min(need, available)
                orders.append(Order(product, bid, -qty))
                need -= qty
            if need > 0:
                best_bid, best_ask = self.best_bid_ask(order_depth)
                if best_bid is not None and best_ask is not None:
                    price = max(best_ask - 1, best_bid + 1)
                    if price < best_ask: orders.append(Order(product, price, -need))
                elif best_ask is not None: orders.append(Order(product, best_ask - 1, -need))
        return orders
    def run_with_data(self, state, trader_data):
        result = {}
        data = self.load_data(trader_data, state.timestamp)
        for product in state.order_depths: result[product] = []
        for product in self.TRADED:
            if product not in state.order_depths: continue
            order_depth = state.order_depths[product]
            current_position = state.position.get(product, 0)
            mid = self.mid_price(order_depth)
            self.update_last_mid(data, product, mid)
            target_position = self.layered_symmetric_grid_target(product=product, order_depth=order_depth, data=data)
            result[product] = self.orders_to_target(product=product, order_depth=order_depth, current_position=current_position, target_position=target_position, max_spread=80)
        return result, 0, json.dumps(data, separators=(',', ':'))

class _SleepPodStrategy:
    LIMIT = 10
    SUEDE, LAMB, POLY, NYLON, COTTON = 'SLEEP_POD_SUEDE', 'SLEEP_POD_LAMB_WOOL', 'SLEEP_POD_POLYESTER', 'SLEEP_POD_NYLON', 'SLEEP_POD_COTTON'
    PRODUCTS = [SUEDE, LAMB, POLY, NYLON, COTTON]
    BASE_PRODUCT = SUEDE
    FAST_ALPHA, SLOW_ALPHA = 2.0 / 17.0, 2.0 / 101.0
    ANCHOR_ALPHA, VOL_ALPHA = 2.0 / 251.0, 2.0 / 61.0
    MIN_OBS_FOR_ADAPTIVE, OPEN_MOVE_SPREAD_MULT, OPEN_MOVE_VOL_MULT, CONFIRM_COUNT, ADAPTIVE_SIZE = 450, 5.0, 6.0, 3, 10
    def run_with_data(self, state, trader_data):
        result, data = {}, self._load_state(trader_data)
        if 'pods' not in data: data['pods'] = {}
        for product in self.PRODUCTS:
            if product not in data['pods']: data['pods'][product] = self._new_memory()
        mids, spreads = self._read_market(state)
        for product in self.PRODUCTS:
            if product in mids: self._update_memory(memory=data['pods'][product], mid=mids[product], spread=spreads[product])
        targets = {p: 0 for p in self.PRODUCTS}
        if self.SUEDE in mids: targets[self.SUEDE] = self.LIMIT
        for product in [self.LAMB, self.POLY, self.NYLON, self.COTTON]:
            if product not in mids: continue
            targets[product] = self._adaptive_target(memory=data['pods'][product], mid=mids[product], spread=spreads[product])
        for product in self.PRODUCTS:
            if product not in state.order_depths: continue
            position = state.position.get(product, 0)
            target = max(-self.LIMIT, min(self.LIMIT, int(targets.get(product, 0))))
            orders = self._move_to_target(product=product, order_depth=state.order_depths[product], position=position, target=target)
            if orders: result[product] = orders
        return result, 0, self._dump_state(data)
    def _adaptive_target(self, memory, mid, spread):
        if memory['obs'] < self.MIN_OBS_FOR_ADAPTIVE: return memory.get('target', 0)
        open_move = mid - memory['open']
        fast_slow = memory['fast'] - memory['slow']
        anchor_move = mid - memory['anchor']
        required_move = max(self.OPEN_MOVE_SPREAD_MULT * spread, self.OPEN_MOVE_VOL_MULT * max(1.0, memory['vol']))
        long_signal = open_move > required_move and fast_slow > 0 and (anchor_move > -0.25 * required_move)
        short_signal = open_move < -required_move and fast_slow < 0 and (anchor_move < 0.25 * required_move)
        if long_signal: memory['long_count'] += 1; memory['short_count'] = 0
        elif short_signal: memory['short_count'] += 1; memory['long_count'] = 0
        else: memory['long_count'] = max(0, memory['long_count'] - 1); memory['short_count'] = max(0, memory['short_count'] - 1)
        target = memory.get('target', 0)
        if memory['long_count'] >= self.CONFIRM_COUNT: target = self.ADAPTIVE_SIZE
        elif memory['short_count'] >= self.CONFIRM_COUNT: target = -self.ADAPTIVE_SIZE
        memory['target'] = target
        return target
    def _update_memory(self, memory, mid, spread):
        memory['obs'] += 1
        if memory['open'] is None:
            for k in ['open', 'prev', 'fast', 'slow', 'anchor']: memory[k] = mid
            memory['vol'] = max(1.0, 0.35 * spread)
            return
        diff = mid - memory['prev']
        memory['prev'] = mid
        memory['fast'] = self.FAST_ALPHA * mid + (1.0 - self.FAST_ALPHA) * memory['fast']
        memory['slow'] = self.SLOW_ALPHA * mid + (1.0 - self.SLOW_ALPHA) * memory['slow']
        memory['anchor'] = self.ANCHOR_ALPHA * mid + (1.0 - self.ANCHOR_ALPHA) * memory['anchor']
        memory['vol'] = self.VOL_ALPHA * abs(diff) + (1.0 - self.VOL_ALPHA) * memory['vol']
    def _read_market(self, state):
        mids, spreads = {}, {}
        for product in self.PRODUCTS:
            od = state.order_depths.get(product)
            if od is None or not od.buy_orders or not od.sell_orders: continue
            b, a = max(od.buy_orders.keys()), min(od.sell_orders.keys())
            mids[product] = (b + a) / 2.0
            spreads[product] = max(1.0, a - b)
        return mids, spreads
    def _move_to_target(self, product, order_depth, position, target):
        orders = []
        if position == target or not order_depth.buy_orders or not order_depth.sell_orders: return orders
        delta = target - position
        if delta > 0: self._buy(product, order_depth, orders, delta)
        elif delta < 0: self._sell(product, order_depth, orders, -delta)
        return orders
    def _buy(self, product, order_depth, orders, quantity):
        rem = quantity
        for ask in sorted(order_depth.sell_orders.keys()):
            if rem <= 0: break
            avail = -order_depth.sell_orders[ask]
            if avail <= 0: continue
            take = min(rem, avail)
            orders.append(Order(product, ask, take))
            rem -= take
    def _sell(self, product, order_depth, orders, quantity):
        rem = quantity
        for bid in sorted(order_depth.buy_orders.keys(), reverse=True):
            if rem <= 0: break
            avail = order_depth.buy_orders[bid]
            if avail <= 0: continue
            take = min(rem, avail)
            orders.append(Order(product, bid, -take))
            rem -= take
    def _new_memory(self): return {'obs': 0, 'open': None, 'prev': None, 'fast': None, 'slow': None, 'anchor': None, 'vol': 1.0, 'long_count': 0, 'short_count': 0, 'target': 0}
    def _load_state(self, trader_data):
        if not trader_data: return {}
        try:
            data = json.loads(trader_data)
            if isinstance(data, dict): return data
        except Exception: pass
        return {}
    def _dump_state(self, data):
        try: return json.dumps(data, separators=(',', ':'))
        except Exception: return '{}'

class _GalaxyStrategy:
    LIMIT = 10
    BLACK, RINGS = 'GALAXY_SOUNDS_BLACK_HOLES', 'GALAXY_SOUNDS_PLANETARY_RINGS'
    GALAXY_PRODUCTS = ['GALAXY_SOUNDS_DARK_MATTER', BLACK, RINGS, 'GALAXY_SOUNDS_SOLAR_WINDS', 'GALAXY_SOUNDS_SOLAR_FLAMES']
    FAST_ALPHA, SLOW_ALPHA = 2.0 / 19.0, 2.0 / 121.0
    ANCHOR_ALPHA, VOL_ALPHA = 2.0 / 601.0, 2.0 / 91.0
    PROBE_SIZE, SAFE_SIZE, FULL_SIZE = 3, 5, 10
    def run_with_data(self, state, trader_data):
        result, data = {}, self._load_state(trader_data)
        if 'pair' not in data: data['pair'] = self._new_pair_memory()
        mids, spreads = {}, {}
        for product in self.GALAXY_PRODUCTS:
            od = state.order_depths.get(product)
            if od is None or not od.buy_orders or not od.sell_orders: continue
            b, a = max(od.buy_orders.keys()), min(od.sell_orders.keys())
            mids[product], spreads[product] = (b + a) / 2.0, max(1.0, a - b)
        targets = {p: 0 for p in self.GALAXY_PRODUCTS}
        if self.BLACK in mids and self.RINGS in mids:
            pair_size = self._adaptive_pair_size(memory=data['pair'], timestamp=state.timestamp, black_mid=mids[self.BLACK], rings_mid=mids[self.RINGS], black_spread=spreads[self.BLACK], rings_spread=spreads[self.RINGS])
            targets[self.BLACK] = pair_size
            targets[self.RINGS] = -pair_size
        for product in self.GALAXY_PRODUCTS:
            if product not in state.order_depths: continue
            position = state.position.get(product, 0)
            target = max(-self.LIMIT, min(self.LIMIT, targets.get(product, 0)))
            orders = self._move_to_target(product=product, order_depth=state.order_depths[product], position=position, target=target)
            if orders: result[product] = orders
        return result, 0, self._dump_state(data)
    def _adaptive_pair_size(self, memory, timestamp, black_mid, rings_mid, black_spread, rings_spread):
        rel = black_mid - rings_mid
        pair_cost = black_spread + rings_spread
        memory['obs'] += 1
        memory['last_timestamp'] = timestamp
        if memory['rel_fast'] is None:
            for k in ['rel_fast', 'rel_slow', 'rel_anchor', 'rel_last', 'entry_rel']: memory[k] = rel
            memory['rel_vol'] = 1.0
            memory['pair_size'] = self.PROBE_SIZE
            return self.PROBE_SIZE
        d_rel = rel - memory['rel_last']
        memory['rel_last'] = rel
        memory['rel_fast'] = self.FAST_ALPHA * rel + (1.0 - self.FAST_ALPHA) * memory['rel_fast']
        memory['rel_slow'] = self.SLOW_ALPHA * rel + (1.0 - self.SLOW_ALPHA) * memory['rel_slow']
        memory['rel_anchor'] = self.ANCHOR_ALPHA * rel + (1.0 - self.ANCHOR_ALPHA) * memory['rel_anchor']
        memory['rel_vol'] = self.VOL_ALPHA * abs(d_rel) + (1.0 - self.VOL_ALPHA) * memory['rel_vol']
        noise = max(1.0, memory['rel_vol'], 0.3 * pair_cost)
        health = 0
        if memory['rel_fast'] > memory['rel_slow'] + 0.2 * noise: health += 1
        elif memory['rel_fast'] < memory['rel_slow'] - 0.2 * noise: health -= 1
        if rel > memory['rel_anchor'] + 0.25 * noise: health += 1
        elif rel < memory['rel_anchor'] - 0.25 * noise: health -= 1
        memory['rel_history'].append(rel)
        if len(memory['rel_history']) > 80: memory['rel_history'] = memory['rel_history'][-80:]
        if len(memory['rel_history']) >= 20:
            momentum = memory['rel_history'][-1] - memory['rel_history'][-20]
            if momentum > 1.5 * noise: health += 1
            elif momentum < -1.5 * noise: health -= 1
        if memory.get('entry_rel') is not None:
            if memory['entry_rel'] - rel > max(4.0 * noise, 1.5 * pair_cost): health -= 2
        if health >= 2: memory['good_count'] += 1; memory['bad_count'] = max(0, memory['bad_count'] - 1)
        elif health <= -2: memory['bad_count'] += 1; memory['good_count'] = max(0, memory['good_count'] - 1)
        else: memory['good_count'] = max(0, memory['good_count'] - 1); memory['bad_count'] = max(0, memory['bad_count'] - 1)
        cur = int(memory.get('pair_size', 0))
        if memory['bad_count'] >= 8: new_sz = 0
        elif memory['bad_count'] >= 4: new_sz = self.PROBE_SIZE
        elif memory['good_count'] >= 5: new_sz = self.FULL_SIZE
        elif memory['good_count'] >= 2: new_sz = max(cur, self.SAFE_SIZE)
        elif cur == 0: new_sz = self.PROBE_SIZE if health > 0 else 0
        else: new_sz = cur
        if cur == 0 and health <= 0: new_sz = 0
        if cur == 0 and new_sz > 0: memory['entry_rel'] = rel
        if new_sz == 0: memory['entry_rel'] = None
        if abs(new_sz - cur) < 2 and new_sz != 0: new_sz = cur
        memory['pair_size'] = int(max(0, min(self.LIMIT, new_sz)))
        return memory['pair_size']
    def _move_to_target(self, product, order_depth, position, target):
        orders = []
        if position == target or not order_depth.buy_orders or not order_depth.sell_orders: return orders
        delta = target - position
        if delta > 0: self._take_asks(product, order_depth, orders, delta)
        elif delta < 0: self._hit_bids(product, order_depth, orders, -delta)
        return orders
    def _take_asks(self, product, order_depth, orders, quantity):
        rem = quantity
        for ask in sorted(order_depth.sell_orders.keys()):
            if rem <= 0: break
            avail = -order_depth.sell_orders[ask]
            if avail <= 0: continue
            take = min(rem, avail)
            orders.append(Order(product, ask, take))
            rem -= take
    def _hit_bids(self, product, order_depth, orders, quantity):
        rem = quantity
        for bid in sorted(order_depth.buy_orders.keys(), reverse=True):
            if rem <= 0: break
            avail = order_depth.buy_orders[bid]
            if avail <= 0: continue
            take = min(rem, avail)
            orders.append(Order(product, bid, -take))
            rem -= take
    def _new_pair_memory(self): return {'obs': 0, 'last_timestamp': None, 'rel_fast': None, 'rel_slow': None, 'rel_anchor': None, 'rel_last': None, 'rel_vol': 1.0, 'rel_history': [], 'entry_rel': None, 'good_count': 0, 'bad_count': 0, 'pair_size': 0}
    def _load_state(self, trader_data):
        if not trader_data: return {}
        try:
            data = json.loads(trader_data)
            if isinstance(data, dict): return data
        except Exception: pass
        return {}
    def _dump_state(self, data):
        try: return json.dumps(data, separators=(',', ':'))
        except Exception: return '{}'

class _RobotStrategy:
    POSITION_LIMIT = 10
    ROBOT_DISHES, ROBOT_MOPPING, ROBOT_LAUNDRY, ROBOT_IRONING = 'ROBOT_DISHES', 'ROBOT_MOPPING', 'ROBOT_LAUNDRY', 'ROBOT_IRONING'
    TRADED = {ROBOT_DISHES, ROBOT_MOPPING, ROBOT_LAUNDRY, ROBOT_IRONING}
    DISHES_GRID_THRESHOLD = 80.0
    EARLY_DETECT_END = 5000
    EARLY_HIT_THRESHOLD, EARLY_FALLBACK_THRESHOLD = 50.0, 20.0
    MOPPING_INVALIDATE_THRESHOLD, MOPPING_COVER_BUFFER, MOPPING_REENTRY_BUFFER = 300.0, 300.0, 100.0
    LAUNDRY_COVER_BUFFER, LAUNDRY_REENTRY_BUFFER = 350.0, 150.0
    IRONING_CONFIRM_THRESHOLD, IRONING_COVER_BUFFER, IRONING_REENTRY_BUFFER = 300.0, 200.0, 125.0
    MAX_SPREAD_TO_OPEN = 25
    def bid(self): return 15
    def fresh_data(self): return {'init_mid': {}, 'last_mid': {}, 'mode': {}, 'grid_ref': {}, 'grid_entry': {}, 'grid_dir': {}, 'trend_active_dir': {}, 'entry_anchor': {}, 'exit_anchor': {}, 'paused_dir': {}}
    def load_data(self, trader_data, timestamp):
        if timestamp == 0 or not trader_data: return self.fresh_data()
        try: data = json.loads(trader_data)
        except Exception: return self.fresh_data()
        for k in ['init_mid', 'last_mid', 'mode', 'grid_ref', 'grid_entry', 'grid_dir', 'trend_active_dir', 'entry_anchor', 'exit_anchor', 'paused_dir']: data.setdefault(k, {})
        return data
    def save_data(self, data): return json.dumps(data, separators=(',', ':'))
    def update_mid_state(self, data, product, mid):
        if product not in data['init_mid']: data['init_mid'][product] = mid
        data['last_mid'][product] = mid
    def best_bid_ask(self, od):
        best_bid = max(od.buy_orders.keys()) if od.buy_orders else None
        best_ask = min(od.sell_orders.keys()) if od.sell_orders else None
        return (best_bid, best_ask)
    def mid_price(self, od):
        best_bid, best_ask = self.best_bid_ask(od)
        if best_bid is not None and best_ask is not None: return (best_bid + best_ask) / 2.0
        if best_bid is not None: return float(best_bid)
        if best_ask is not None: return float(best_ask)
        return None
    def spread(self, od):
        best_bid, best_ask = self.best_bid_ask(od)
        if best_bid is None or best_ask is None: return None
        return best_ask - best_bid
    def update_mopping_laundry_mode(self, data, product, mid, timestamp):
        mode = data['mode'].get(product, 'WAIT')
        open_mid = float(data['init_mid'][product])
        move = mid - open_mid
        if mode in ('LONG', 'SHORT'):
            if product == self.ROBOT_MOPPING:
                if mode == 'SHORT' and move >= self.MOPPING_INVALIDATE_THRESHOLD:
                    data['mode'][product] = 'LONG'
                    self.reset_trend_state(data, product)
                    return 'LONG'
                if mode == 'LONG' and move <= -self.MOPPING_INVALIDATE_THRESHOLD:
                    data['mode'][product] = 'SHORT'
                    self.reset_trend_state(data, product)
                    return 'SHORT'
            return mode
        if mode == 'OFF': return mode
        if timestamp <= self.EARLY_DETECT_END:
            if move >= self.EARLY_HIT_THRESHOLD:
                data['mode'][product] = 'LONG'
                self.reset_trend_state(data, product)
                return 'LONG'
            if move <= -self.EARLY_HIT_THRESHOLD:
                data['mode'][product] = 'SHORT'
                self.reset_trend_state(data, product)
                return 'SHORT'
            return 'WAIT'
        if move >= self.EARLY_FALLBACK_THRESHOLD:
            data['mode'][product] = 'LONG'
            self.reset_trend_state(data, product)
            return 'LONG'
        if move <= -self.EARLY_FALLBACK_THRESHOLD:
            data['mode'][product] = 'SHORT'
            self.reset_trend_state(data, product)
            return 'SHORT'
        data['mode'][product] = 'OFF'
        return 'OFF'
    def update_ironing_mode(self, data, product, mid):
        mode = data['mode'].get(product, 'WAIT')
        if mode in ('LONG', 'SHORT', 'OFF'): return mode
        open_mid = float(data['init_mid'][product])
        move = mid - open_mid
        if move >= self.IRONING_CONFIRM_THRESHOLD:
            data['mode'][product] = 'LONG'
            self.reset_trend_state(data, product)
            return 'LONG'
        if move <= -self.IRONING_CONFIRM_THRESHOLD:
            data['mode'][product] = 'SHORT'
            self.reset_trend_state(data, product)
            return 'SHORT'
        return 'WAIT'
    def reset_grid_position_state(self, data, product):
        data['grid_entry'][product] = None
        data['grid_dir'][product] = 0
    def symmetric_grid_target(self, product, order_depth, current_position, data, threshold):
        best_bid, best_ask = self.best_bid_ask(order_depth)
        mid = self.mid_price(order_depth)
        if best_bid is None and best_ask is None and (mid is None): return current_position
        if product not in data['grid_ref'] or data['grid_ref'].get(product) is None:
            data['grid_ref'][product] = float(mid if mid is not None else best_ask if best_ask is not None else best_bid)
            self.reset_grid_position_state(data, product)
        ref = float(data['grid_ref'][product])
        entry = data['grid_entry'].get(product)
        if current_position > 0:
            if entry is None:
                entry = float(mid if mid is not None else best_ask if best_ask is not None else best_bid)
                data['grid_entry'][product] = entry
                data['grid_dir'][product] = 1
            if best_bid is not None and best_bid >= float(entry) + threshold:
                data['grid_ref'][product] = float(best_bid)
                self.reset_grid_position_state(data, product)
                return 0
            return self.POSITION_LIMIT
        if current_position < 0:
            if entry is None:
                entry = float(mid if mid is not None else best_bid if best_bid is not None else best_ask)
                data['grid_entry'][product] = entry
                data['grid_dir'][product] = -1
            if best_ask is not None and best_ask <= float(entry) - threshold:
                data['grid_ref'][product] = float(best_ask)
                self.reset_grid_position_state(data, product)
                return 0
            return -self.POSITION_LIMIT
        self.reset_grid_position_state(data, product)
        if best_ask is not None and best_ask <= ref - threshold:
            data['grid_entry'][product] = float(best_ask)
            data['grid_dir'][product] = 1
            return self.POSITION_LIMIT
        if best_bid is not None and best_bid >= ref + threshold:
            data['grid_entry'][product] = float(best_bid)
            data['grid_dir'][product] = -1
            return -self.POSITION_LIMIT
        return 0
    def reset_trend_state(self, data, product):
        data['trend_active_dir'][product] = 0
        data['entry_anchor'][product] = None
        data['exit_anchor'][product] = None
        data['paused_dir'][product] = 0
    def buffered_trend_target(self, data, product, od, current_position, desired_dir, cover_buffer, reentry_buffer):
        best_bid, best_ask = self.best_bid_ask(od)
        mid = self.mid_price(od)
        if best_bid is None and best_ask is None and (mid is None): return current_position
        active_dir = int(data['trend_active_dir'].get(product, 0))
        if active_dir != desired_dir:
            self.reset_trend_state(data, product)
            data['trend_active_dir'][product] = desired_dir
        if desired_dir == 0:
            self.reset_trend_state(data, product)
            return 0
        entry_anchor = data['entry_anchor'].get(product)
        exit_anchor = data['exit_anchor'].get(product)
        paused_dir = int(data['paused_dir'].get(product, 0))
        if desired_dir > 0:
            if current_position < 0: return 0
            if current_position > 0:
                if entry_anchor is None:
                    data['entry_anchor'][product] = entry_anchor = float(best_ask if best_ask is not None else mid)
                if best_bid is not None and best_bid <= float(entry_anchor) - cover_buffer:
                    data['exit_anchor'][product] = float(best_bid)
                    data['entry_anchor'][product] = None
                    data['paused_dir'][product] = 1
                    return 0
                return self.POSITION_LIMIT
            if paused_dir != 1 or exit_anchor is None:
                data['entry_anchor'][product] = float(best_ask if best_ask is not None else mid)
                data['exit_anchor'][product] = None
                data['paused_dir'][product] = 0
                return self.POSITION_LIMIT
            if best_ask is not None and best_ask <= float(exit_anchor) - reentry_buffer:
                data['entry_anchor'][product] = float(best_ask)
                data['exit_anchor'][product] = None
                data['paused_dir'][product] = 0
                return self.POSITION_LIMIT
            return 0
        if desired_dir < 0:
            if current_position > 0: return 0
            if current_position < 0:
                if entry_anchor is None:
                    data['entry_anchor'][product] = entry_anchor = float(best_bid if best_bid is not None else mid)
                if best_bid is not None and best_bid >= float(entry_anchor) + cover_buffer:
                    data['exit_anchor'][product] = float(best_ask if best_ask is not None else best_bid)
                    data['entry_anchor'][product] = None
                    data['paused_dir'][product] = -1
                    return 0
                return -self.POSITION_LIMIT
            if paused_dir != -1 or exit_anchor is None:
                data['entry_anchor'][product] = float(best_bid if best_bid is not None else mid)
                data['exit_anchor'][product] = None
                data['paused_dir'][product] = 0
                return -self.POSITION_LIMIT
            if best_bid is not None and best_bid >= float(exit_anchor) + reentry_buffer:
                data['entry_anchor'][product] = float(best_bid)
                data['exit_anchor'][product] = None
                data['paused_dir'][product] = 0
                return -self.POSITION_LIMIT
            return 0
        return 0
    def target_for_product(self, data, product, od, current_position, timestamp):
        mid = self.mid_price(od)
        if mid is None: return current_position
        if product == self.ROBOT_DISHES: return self.symmetric_grid_target(product=product, order_depth=od, current_position=current_position, data=data, threshold=self.DISHES_GRID_THRESHOLD)
        if product == self.ROBOT_MOPPING:
            mode = self.update_mopping_laundry_mode(data, product, mid, timestamp)
            if mode == 'LONG': return self.buffered_trend_target(data=data, product=product, od=od, current_position=current_position, desired_dir=1, cover_buffer=self.MOPPING_COVER_BUFFER, reentry_buffer=self.MOPPING_REENTRY_BUFFER)
            if mode == 'SHORT': return self.buffered_trend_target(data=data, product=product, od=od, current_position=current_position, desired_dir=-1, cover_buffer=self.MOPPING_COVER_BUFFER, reentry_buffer=self.MOPPING_REENTRY_BUFFER)
            return 0
        if product == self.ROBOT_LAUNDRY:
            mode = self.update_mopping_laundry_mode(data, product, mid, timestamp)
            if mode == 'LONG': return self.buffered_trend_target(data=data, product=product, od=od, current_position=current_position, desired_dir=1, cover_buffer=self.LAUNDRY_COVER_BUFFER, reentry_buffer=self.LAUNDRY_REENTRY_BUFFER)
            if mode == 'SHORT': return self.buffered_trend_target(data=data, product=product, od=od, current_position=current_position, desired_dir=-1, cover_buffer=self.LAUNDRY_COVER_BUFFER, reentry_buffer=self.LAUNDRY_REENTRY_BUFFER)
            return 0
        if product == self.ROBOT_IRONING:
            mode = self.update_ironing_mode(data, product, mid)
            if mode == 'LONG': return self.buffered_trend_target(data=data, product=product, od=od, current_position=current_position, desired_dir=1, cover_buffer=self.IRONING_COVER_BUFFER, reentry_buffer=self.IRONING_REENTRY_BUFFER)
            if mode == 'SHORT': return self.buffered_trend_target(data=data, product=product, od=od, current_position=current_position, desired_dir=-1, cover_buffer=self.IRONING_COVER_BUFFER, reentry_buffer=self.IRONING_REENTRY_BUFFER)
            return 0
        return 0
    def orders_to_target(self, product, od, current_position, target_position):
        orders = []
        target_position = max(-self.POSITION_LIMIT, min(self.POSITION_LIMIT, target_position))
        delta = target_position - current_position
        if delta == 0: return orders
        sp = self.spread(od)
        reducing_risk = abs(target_position) < abs(current_position)
        if sp is not None and sp > self.MAX_SPREAD_TO_OPEN and (not reducing_risk): return orders
        if delta > 0:
            need = min(delta, self.POSITION_LIMIT - current_position)
            for ask, ask_volume in sorted(od.sell_orders.items()):
                if need <= 0: break
                available = -ask_volume
                if available <= 0: continue
                qty = min(need, available)
                orders.append(Order(product, ask, qty))
                need -= qty
            if need > 0:
                best_bid, best_ask = self.best_bid_ask(od)
                if best_bid is not None and best_ask is not None:
                    price = min(best_bid + 1, best_ask - 1)
                    if price > best_bid: orders.append(Order(product, price, need))
                elif best_bid is not None: orders.append(Order(product, best_bid + 1, need))
                elif best_ask is not None: orders.append(Order(product, best_ask, need))
        elif delta < 0:
            need = min(-delta, self.POSITION_LIMIT + current_position)
            for bid, bid_volume in sorted(od.buy_orders.items(), reverse=True):
                if need <= 0: break
                available = bid_volume
                if available <= 0: continue
                qty = min(need, available)
                orders.append(Order(product, bid, -qty))
                need -= qty
            if need > 0:
                best_bid, best_ask = self.best_bid_ask(od)
                if best_bid is not None and best_ask is not None:
                    price = max(best_ask - 1, best_bid + 1)
                    if price < best_ask: orders.append(Order(product, price, -need))
                elif best_ask is not None: orders.append(Order(product, best_ask - 1, -need))
                elif best_bid is not None: orders.append(Order(product, best_bid, -need))
        return orders
    def run_with_data(self, state, trader_data):
        result = {}
        data = self.load_data(trader_data, state.timestamp)
        for product in state.order_depths: result[product] = []
        for product, od in state.order_depths.items():
            if product not in self.TRADED: continue
            mid = self.mid_price(od)
            if mid is None: continue
            self.update_mid_state(data, product, mid)
            current_position = state.position.get(product, 0)
            target_position = self.target_for_product(data=data, product=product, od=od, current_position=current_position, timestamp=state.timestamp)
            result[product] = self.orders_to_target(product=product, od=od, current_position=current_position, target_position=target_position)
        return result, 0, self.save_data(data)

class _MicrochipStrategy:
    POSITION_LIMIT = 10
    OVAL, SQUARE, CIRCLE = 'MICROCHIP_OVAL', 'MICROCHIP_SQUARE', 'MICROCHIP_CIRCLE'
    RECTANGLE, TRIANGLE = 'MICROCHIP_RECTANGLE', 'MICROCHIP_TRIANGLE'
    TRADED = {OVAL, SQUARE, CIRCLE}
    ALL_MICROCHIPS = {OVAL, SQUARE, CIRCLE, RECTANGLE, TRIANGLE}
    VOL_ALPHA, SPREAD_ALPHA, FAST_ALPHA, SLOW_ALPHA = 0.03, 0.05, 0.06, 0.012
    PARAMS = {
        OVAL: {'mode': 'always_short', 'cover_vol_mult': 18.0, 'cover_spread_mult': 20.0, 'cover_pct': 0.025, 'reentry_frac': 0.55, 'max_spread': 90},
        SQUARE: {'mode': 'detect_direction', 'min_count': 1000, 'det_vol_mult': 25.0, 'det_spread_mult': 25.0, 'det_pct': 0.018, 'ema_gap_frac': 0.2, 'confirm_ticks': 3, 'min_conf_ratio': 1.0, 'cover_vol_mult': 16.0, 'cover_spread_mult': 18.0, 'cover_pct': 0.015, 'reentry_frac': 0.55, 'max_spread': 140},
        CIRCLE: {'mode': 'detect_direction', 'min_count': 4000, 'det_vol_mult': 45.0, 'det_spread_mult': 40.0, 'det_pct': 0.04, 'ema_gap_frac': 0.2, 'confirm_ticks': 5, 'min_conf_ratio': 1.7, 'cover_vol_mult': 38.0, 'cover_spread_mult': 35.0, 'cover_pct': 0.035, 'reentry_frac': 0.55, 'extended_wait_mult': 2.8, 'max_spread': 120}
    }
    def best_bid_ask(self, order_depth):
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        return (best_bid, best_ask)
    def mid_price(self, order_depth):
        best_bid, best_ask = self.best_bid_ask(order_depth)
        if best_bid is not None and best_ask is not None: return (best_bid + best_ask) / 2.0
        if best_bid is not None: return float(best_bid)
        if best_ask is not None: return float(best_ask)
        return None
    def spread(self, order_depth):
        best_bid, best_ask = self.best_bid_ask(order_depth)
        if best_bid is None or best_ask is None: return None
        return best_ask - best_bid
    def fresh_data(self):
        return {'init_mid': {}, 'last_mid': {}, 'ema_fast': {}, 'ema_slow': {}, 'vol_ema': {}, 'spread_ema': {}, 'count': {}, 'raw_dir': {}, 'raw_dir_count': {}, 'confirmed_dir': {}, 'active_dir': {}, 'entry_anchor': {}, 'exit_anchor': {}, 'wait_entry_dir': {}, 'wait_entry_ref': {}}
    def load_data(self, trader_data, timestamp):
        if timestamp == 0 or not trader_data: return self.fresh_data()
        try: data = json.loads(trader_data)
        except Exception: return self.fresh_data()
        defaults = self.fresh_data()
        for key, value in defaults.items(): data.setdefault(key, value)
        return data
    def update_indicators(self, data, product, mid, spread):
        sp = float(spread if spread is not None else 0.0)
        if product not in data['init_mid']:
            for k in ['init_mid', 'last_mid', 'ema_fast', 'ema_slow']: data[k][product] = mid
            data['vol_ema'][product] = 0.0
            data['spread_ema'][product] = max(sp, 1.0)
            data['count'][product] = 1
            for k in ['raw_dir', 'raw_dir_count', 'confirmed_dir']: data[k][product] = 0
            return
        last_mid = float(data['last_mid'].get(product, mid))
        abs_step = abs(mid - last_mid)
        old_vol = float(data['vol_ema'].get(product, 0.0))
        old_spread = float(data['spread_ema'].get(product, max(sp, 1.0)))
        old_fast = float(data['ema_fast'].get(product, mid))
        old_slow = float(data['ema_slow'].get(product, mid))
        data['vol_ema'][product] = self.VOL_ALPHA * abs_step + (1.0 - self.VOL_ALPHA) * old_vol
        data['spread_ema'][product] = self.SPREAD_ALPHA * max(sp, 1.0) + (1.0 - self.SPREAD_ALPHA) * old_spread
        data['ema_fast'][product] = self.FAST_ALPHA * mid + (1.0 - self.FAST_ALPHA) * old_fast
        data['ema_slow'][product] = self.SLOW_ALPHA * mid + (1.0 - self.SLOW_ALPHA) * old_slow
        data['last_mid'][product] = mid
        data['count'][product] = int(data['count'].get(product, 0)) + 1
    def cover_threshold(self, data, product, mid):
        p = self.PARAMS[product]
        vol = max(float(data['vol_ema'].get(product, 1.0)), 1.0)
        sp = max(float(data['spread_ema'].get(product, 1.0)), 1.0)
        return max(p['cover_vol_mult'] * vol, p['cover_spread_mult'] * sp, p['cover_pct'] * mid)
    def detection_threshold(self, data, product, mid):
        p = self.PARAMS[product]
        vol = max(float(data['vol_ema'].get(product, 1.0)), 1.0)
        sp = max(float(data['spread_ema'].get(product, 1.0)), 1.0)
        return max(p['det_vol_mult'] * vol, p['det_spread_mult'] * sp, p['det_pct'] * mid)
    def reset_directional_grid(self, data, product, direction):
        data['active_dir'][product] = direction
        data['entry_anchor'][product] = None
        data['exit_anchor'][product] = None
        data['wait_entry_dir'][product] = 0
        data['wait_entry_ref'][product] = None
    def detect_direction(self, data, product, mid):
        if product == self.OVAL:
            if int(data['confirmed_dir'].get(product, 0)) != -1:
                data['confirmed_dir'][product] = -1
                self.reset_directional_grid(data, product, -1)
            return -1
        confirmed = int(data['confirmed_dir'].get(product, 0))
        if confirmed != 0: return confirmed
        p = self.PARAMS[product]
        count = int(data['count'].get(product, 0))
        if count < int(p['min_count']): return 0
        init_mid = float(data['init_mid'].get(product, mid))
        move = mid - init_mid
        threshold = self.detection_threshold(data, product, mid)
        ema_fast = float(data['ema_fast'].get(product, mid))
        ema_slow = float(data['ema_slow'].get(product, mid))
        ema_gap = ema_fast - ema_slow
        candidate = 0
        if abs(move) >= p['min_conf_ratio'] * threshold:
            if move > 0 and ema_gap > p['ema_gap_frac'] * threshold: candidate = 1
            elif move < 0 and ema_gap < -p['ema_gap_frac'] * threshold: candidate = -1
        if candidate == 0:
            data['raw_dir'][product] = 0
            data['raw_dir_count'][product] = 0
            return 0
        previous_raw = int(data['raw_dir'].get(product, 0))
        if candidate == previous_raw: data['raw_dir_count'][product] = int(data['raw_dir_count'].get(product, 0)) + 1
        else:
            data['raw_dir'][product] = candidate
            data['raw_dir_count'][product] = 1
        if int(data['raw_dir_count'].get(product, 0)) >= int(p['confirm_ticks']):
            data['confirmed_dir'][product] = candidate
            self.reset_directional_grid(data, product, candidate)
            if product == self.CIRCLE:
                cover = self.cover_threshold(data, product, mid)
                if abs(move) > p['extended_wait_mult'] * cover:
                    data['wait_entry_dir'][product] = candidate
                    data['wait_entry_ref'][product] = mid
            return candidate
        return 0
    def directional_grid_target(self, data, product, order_depth, current_position, direction):
        best_bid, best_ask = self.best_bid_ask(order_depth)
        mid = self.mid_price(order_depth)
        if direction == 0 or mid is None or (best_bid is None and best_ask is None): return 0
        if int(data['active_dir'].get(product, 0)) != direction: self.reset_directional_grid(data, product, direction)
        cover = self.cover_threshold(data, product, mid)
        reentry = self.PARAMS[product]['reentry_frac'] * cover
        wait_dir = int(data['wait_entry_dir'].get(product, 0))
        wait_ref = data['wait_entry_ref'].get(product)
        if wait_dir == direction and wait_ref is not None and (current_position == 0):
            wait_ref = float(wait_ref)
            if direction < 0:
                if best_bid is not None and best_bid >= wait_ref + reentry:
                    data['wait_entry_dir'][product] = 0
                    data['wait_entry_ref'][product] = None
                    data['entry_anchor'][product] = float(best_bid)
                    return -self.POSITION_LIMIT
                return 0
            if direction > 0:
                if best_ask is not None and best_ask <= wait_ref - reentry:
                    data['wait_entry_dir'][product] = 0
                    data['wait_entry_ref'][product] = None
                    data['entry_anchor'][product] = float(best_ask)
                    return self.POSITION_LIMIT
                return 0
        entry_anchor = data['entry_anchor'].get(product)
        exit_anchor = data['exit_anchor'].get(product)
        if direction < 0:
            if current_position > 0: return 0
            if current_position < 0:
                if entry_anchor is None:
                    data['entry_anchor'][product] = entry_anchor = float(best_bid if best_bid is not None else mid)
                if best_bid is not None and best_bid >= float(entry_anchor) + cover:
                    data['entry_anchor'][product] = None
                    data['exit_anchor'][product] = float(best_ask if best_ask is not None else best_bid)
                    return 0
                return -self.POSITION_LIMIT
            if exit_anchor is None:
                data['entry_anchor'][product] = float(best_bid if best_bid is not None else mid)
                return -self.POSITION_LIMIT
            if best_bid is not None and best_bid >= float(exit_anchor) + reentry:
                data['entry_anchor'][product] = float(best_bid)
                data['exit_anchor'][product] = None
                return -self.POSITION_LIMIT
            return 0
        if direction > 0:
            if current_position < 0: return 0
            if current_position > 0:
                if entry_anchor is None:
                    data['entry_anchor'][product] = entry_anchor = float(best_ask if best_ask is not None else mid)
                if best_ask is not None and best_ask <= float(entry_anchor) - cover:
                    data['entry_anchor'][product] = None
                    data['exit_anchor'][product] = float(best_bid if best_bid is not None else best_ask)
                    return 0
                return self.POSITION_LIMIT
            if exit_anchor is None:
                data['entry_anchor'][product] = float(best_ask if best_ask is not None else mid)
                return self.POSITION_LIMIT
            if best_ask is not None and best_ask <= float(exit_anchor) - reentry:
                data['entry_anchor'][product] = float(best_ask)
                data['exit_anchor'][product] = None
                return self.POSITION_LIMIT
            return 0
        return 0
    def orders_to_target(self, product, order_depth, current_position, target_position, max_spread):
        orders = []
        target_position = max(-self.POSITION_LIMIT, min(self.POSITION_LIMIT, target_position))
        delta = target_position - current_position
        if delta == 0: return orders
        sp = self.spread(order_depth)
        reducing_risk = abs(target_position) < abs(current_position)
        if sp is not None and sp > max_spread and (not reducing_risk): return orders
        if delta > 0:
            need = delta
            for ask, ask_volume in sorted(order_depth.sell_orders.items()):
                if need <= 0: break
                available = -ask_volume
                if available <= 0: continue
                qty = min(need, available)
                orders.append(Order(product, ask, qty))
                need -= qty
            if need > 0:
                best_bid, best_ask = self.best_bid_ask(order_depth)
                if best_bid is not None and best_ask is not None:
                    price = min(best_bid + 1, best_ask - 1)
                    if price > best_bid: orders.append(Order(product, price, need))
                elif best_bid is not None: orders.append(Order(product, best_bid + 1, need))
        elif delta < 0:
            need = -delta
            for bid, bid_volume in sorted(order_depth.buy_orders.items(), reverse=True):
                if need <= 0: break
                available = bid_volume
                if available <= 0: continue
                qty = min(need, available)
                orders.append(Order(product, bid, -qty))
                need -= qty
            if need > 0:
                best_bid, best_ask = self.best_bid_ask(order_depth)
                if best_bid is not None and best_ask is not None:
                    price = max(best_ask - 1, best_bid + 1)
                    if price < best_ask: orders.append(Order(product, price, -need))
                elif best_ask is not None: orders.append(Order(product, best_ask - 1, -need))
        return orders
    def run_with_data(self, state, trader_data):
        result = {}
        data = self.load_data(trader_data, state.timestamp)
        for product in state.order_depths: result[product] = []
        mids, spreads = {}, {}
        for product in self.TRADED:
            if product not in state.order_depths: continue
            order_depth = state.order_depths[product]
            mid = self.mid_price(order_depth)
            if mid is None: continue
            mids[product] = mid
            spreads[product] = self.spread(order_depth)
            self.update_indicators(data, product, mid, spreads[product])
        for product in self.TRADED:
            if product not in state.order_depths or product not in mids: continue
            current_position = state.position.get(product, 0)
            direction = self.detect_direction(data, product, mids[product])
            target = self.directional_grid_target(data=data, product=product, order_depth=state.order_depths[product], current_position=current_position, direction=direction)
            max_spread = int(self.PARAMS[product]['max_spread'])
            result[product] = self.orders_to_target(product=product, order_depth=state.order_depths[product], current_position=current_position, target_position=target, max_spread=max_spread)
        return result, 0, json.dumps(data, separators=(',', ':'))

class Trader:
    POSITION_LIMIT = 10
    OPEN_TARGETS = {'PEBBLES_XL':10,'UV_VISOR_AMBER':-10,'PANEL_4X4':10,'PANEL_1X2':-10,'PEBBLES_M':-10,'TRANSLATOR_GRAPHITE_MIST':10,'GALAXY_SOUNDS_SOLAR_FLAMES':10,'MICROCHIP_RECTANGLE':-10,'PANEL_2X2':-10,'GALAXY_SOUNDS_DARK_MATTER':-10,'SLEEP_POD_SUEDE':10,'MICROCHIP_OVAL':-10,'TRANSLATOR_VOID_BLUE':10,'UV_VISOR_ORANGE':10,'GALAXY_SOUNDS_BLACK_HOLES':-10,'ROBOT_IRONING':10,'OXYGEN_SHAKE_GARLIC':-10,'GALAXY_SOUNDS_SOLAR_WINDS':-10,'OXYGEN_SHAKE_EVENING_BREATH':10,'SNACKPACK_STRAWBERRY':10,'SNACKPACK_RASPBERRY':-10,'MICROCHIP_SQUARE':-10,'OXYGEN_SHAKE_CHOCOLATE':-5}
    MID_TARGETS = {'GALAXY_SOUNDS_PLANETARY_RINGS':-10,'PEBBLES_XL':10,'GALAXY_SOUNDS_SOLAR_FLAMES':10,'PANEL_4X4':10,'GALAXY_SOUNDS_BLACK_HOLES':10,'MICROCHIP_RECTANGLE':-10,'PANEL_1X2':-10,'TRANSLATOR_GRAPHITE_MIST':10,'ROBOT_DISHES':-10,'TRANSLATOR_ECLIPSE_CHARCOAL':10,'PEBBLES_M':-10,'UV_VISOR_AMBER':-10,'PANEL_2X2':-10,'GALAXY_SOUNDS_DARK_MATTER':-10,'MICROCHIP_OVAL':-10,'TRANSLATOR_VOID_BLUE':10,'UV_VISOR_ORANGE':10,'SLEEP_POD_SUEDE':10}
    GATE_20K = {'PANEL_2X4': (-1, 100.0)}
    GATE_50K = {'PANEL_1X4': (-1, 80.0), 'TRANSLATOR_SPACE_GRAY': (-1, 100.0), 'SLEEP_POD_COTTON': (+1, 100.0), 'PEBBLES_S': (-1, 100.0), 'UV_VISOR_RED': (+1, 100.0), 'TRANSLATOR_ASTRO_BLACK': (+1, 150.0)}
    LATE_TARGETS = {'MICROCHIP_OVAL':-10,'PEBBLES_XS':-10,'OXYGEN_SHAKE_GARLIC':10,'GALAXY_SOUNDS_BLACK_HOLES':10,'UV_VISOR_AMBER':-10,'PANEL_2X4':10,'PEBBLES_S':-10,'UV_VISOR_RED':10,'SNACKPACK_PISTACHIO':-7,'SNACKPACK_STRAWBERRY':7,'SLEEP_POD_LAMB_WOOL':5,'SNACKPACK_CHOCOLATE':-4}
    T_GATE_20, T_GATE_50, T_LATE = 20000, 50000, 100000
    PEBBLES = ['PEBBLES_XS', 'PEBBLES_S', 'PEBBLES_M', 'PEBBLES_L', 'PEBBLES_XL']
    SNACK_PAIR_1, SNACK_PAIR_2 = ('SNACKPACK_CHOCOLATE', 'SNACKPACK_VANILLA'), ('SNACKPACK_PISTACHIO', 'SNACKPACK_RASPBERRY')
    MR_PRODUCTS = {'ROBOT_IRONING', 'ROBOT_DISHES', 'OXYGEN_SHAKE_EVENING_BREATH', 'OXYGEN_SHAKE_CHOCOLATE'}
    OVERRIDE_PRODUCTS = set(_OxygenShakeStrategy.TRADED) | set(_PebblesStrategy.TRADED) | set(_SnackpackStrategy.TRADED) | set(_SleepPodStrategy.PRODUCTS) | set(_GalaxyStrategy.GALAXY_PRODUCTS) | set(_RobotStrategy.TRADED) | set(_MicrochipStrategy.ALL_MICROCHIPS)
    def bid(self): return 15
    def load_data(self, trader_data):
        if not trader_data: return {'init_mid': {}, 'gate20': {}, 'gate50': {}, 'pair_mean': {}, 'pair_var': {}, 'pair_count': {}, 'last_mid': {}, 'abs_ewma': {}, '__substates': {}}
        try: data = json.loads(trader_data)
        except Exception: data = {'init_mid': {}, 'gate20': {}, 'gate50': {}, 'pair_mean': {}, 'pair_var': {}, 'pair_count': {}, 'last_mid': {}, 'abs_ewma': {}, '__substates': {}}
        for k in ['init_mid', 'gate20', 'gate50', 'pair_mean', 'pair_var', 'pair_count', 'last_mid', 'abs_ewma', '__substates']: data.setdefault(k, {})
        return data
    def save_data(self, data): return json.dumps(data, separators=(',', ':'))
    def best_bid(self, order_depth): return max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
    def best_ask(self, order_depth): return min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
    def mid_price(self, order_depth):
        bid, ask = self.best_bid(order_depth), self.best_ask(order_depth)
        if bid is not None and ask is not None: return (bid + ask) / 2.0
        if bid is not None: return float(bid)
        if ask is not None: return float(ask)
        return None
    def spread(self, order_depth):
        bid, ask = self.best_bid(order_depth), self.best_ask(order_depth)
        if bid is None or ask is None: return None
        return ask - bid
    def store_init_mid(self, data, product, mid):
        if product not in data['init_mid']: data['init_mid'][product] = mid
    def update_micro_stats(self, data, product, mid):
        last = data['last_mid'].get(product)
        if last is None:
            data['last_mid'][product], data['abs_ewma'][product] = mid, 1.0
            return
        delta = mid - last
        prev_abs = data['abs_ewma'].get(product, abs(delta))
        data['abs_ewma'][product] = 0.95 * prev_abs + 0.05 * abs(delta)
        data['last_mid'][product] = mid
    def update_pair_stat(self, data, key, value):
        count = int(data['pair_count'].get(key, 0))
        mean = float(data['pair_mean'].get(key, value))
        var = float(data['pair_var'].get(key, 10000.0))
        alpha = 0.003
        if count == 0: mean, var = value, 10000.0
        else:
            diff = value - mean
            mean = (1.0 - alpha) * mean + alpha * value
            var = (1.0 - alpha) * var + alpha * diff * diff
        data['pair_count'][key] = count + 1
        data['pair_mean'][key] = mean
        data['pair_var'][key] = max(var, 1.0)
    def eval_gate_once(self, data, gate_store, product, mid, gate_config):
        if product not in gate_config or product in data[gate_store]: return
        init = data['init_mid'].get(product)
        if init is None:
            data[gate_store][product] = 0
            return
        direction, threshold = gate_config[product]
        favorable_move = direction * (mid - init)
        data[gate_store][product] = direction if favorable_move >= threshold else 0
    def pebble_arb_targets(self, mids, order_depths, base_targets):
        out = {}
        if not all((p in mids and p in order_depths for p in self.PEBBLES)): return out
        total = sum((mids[p] for p in self.PEBBLES))
        if abs(total - 50000.0) < 12.0: return out
        best_product, best_direction, best_edge = None, 0, 0.0
        for p in self.PEBBLES:
            od = order_depths[p]
            bid, ask, sp = self.best_bid(od), self.best_ask(od), self.spread(od)
            if bid is None or ask is None or sp is None: continue
            fv = 50000.0 - sum((mids[q] for q in self.PEBBLES if q != p))
            tau = 0.5 * sp + 1.0
            buy_edge, sell_edge = fv - ask - tau, bid - fv - tau
            if buy_edge > best_edge: best_edge, best_product, best_direction = buy_edge, p, +1
            if sell_edge > best_edge: best_edge, best_product, best_direction = sell_edge, p, -1
        if best_product is None or best_edge <= 0: return out
        base = base_targets.get(best_product, 0)
        if base != 0 and (base > 0) != (best_direction > 0): return out
        out[best_product] = 6 * best_direction if base == 0 else base
        return out
    def snack_pair_targets(self, data, mids, base_targets):
        out = {}
        for key, pair in {'CV': self.SNACK_PAIR_1, 'PR': self.SNACK_PAIR_2}.items():
            if pair[0] not in mids or pair[1] not in mids: continue
            s = mids[pair[0]] + mids[pair[1]]
            count = int(data['pair_count'].get(key, 0))
            mean = float(data['pair_mean'].get(key, s))
            var = float(data['pair_var'].get(key, 10000.0))
            self.update_pair_stat(data, key, s)
            if count < 200: continue
            z = (s - mean) / math.sqrt(max(var, 1.0))
            if abs(z) < 2.2: continue
            direction = -1 if z > 0 else +1
            size = 5 if abs(z) > 3.0 else 3
            for p in pair:
                if base_targets.get(p, 0) == 0: out[p] = direction * size
        return out
    def base_target_for_product(self, data, product, mid, timestamp):
        if timestamp >= self.T_LATE: return self.LATE_TARGETS.get(product, 0)
        if product in self.GATE_20K:
            if mid is not None and timestamp >= self.T_GATE_20: self.eval_gate_once(data, 'gate20', product, mid, self.GATE_20K)
            direction = data['gate20'].get(product)
            return int(direction) * self.POSITION_LIMIT if direction is not None else 0
        if product in self.GATE_50K:
            if timestamp < self.T_GATE_50: return 0
            if mid is not None: self.eval_gate_once(data, 'gate50', product, mid, self.GATE_50K)
            direction = data['gate50'].get(product)
            return int(direction) * self.POSITION_LIMIT if direction is not None else 0
        if timestamp < self.T_GATE_50: return self.OPEN_TARGETS.get(product, 0)
        return self.MID_TARGETS.get(product, 0)
    def send_to_target(self, product, order_depth, current_pos, target_pos):
        orders = []
        target_pos = max(-self.POSITION_LIMIT, min(self.POSITION_LIMIT, target_pos))
        delta = target_pos - current_pos
        if delta == 0: return orders
        sp = self.spread(order_depth)
        if sp is not None and sp > 150 and not (abs(target_pos) < abs(current_pos)): return orders
        if delta > 0:
            qty_needed = delta
            for ask, ask_volume in sorted(order_depth.sell_orders.items()):
                if qty_needed <= 0: break
                if -ask_volume <= 0: continue
                qty = min(qty_needed, -ask_volume)
                orders.append(Order(product, ask, qty))
                qty_needed -= qty
            if qty_needed > 0:
                bid, ask = self.best_bid(order_depth), self.best_ask(order_depth)
                if bid is not None and ask is not None and (bid + 1 < ask): orders.append(Order(product, bid + 1, qty_needed))
                elif bid is not None: orders.append(Order(product, bid, qty_needed))
        elif delta < 0:
            qty_needed = -delta
            for bid, bid_volume in sorted(order_depth.buy_orders.items(), reverse=True):
                if qty_needed <= 0: break
                if bid_volume <= 0: continue
                qty = min(qty_needed, bid_volume)
                orders.append(Order(product, bid, -qty))
                qty_needed -= qty
            if qty_needed > 0:
                bid, ask = self.best_bid(order_depth), self.best_ask(order_depth)
                if bid is not None and ask is not None and (bid + 1 < ask): orders.append(Order(product, ask - 1, -qty_needed))
                elif ask is not None: orders.append(Order(product, ask, -qty_needed))
        return orders
    def passive_mean_reversion_orders(self, product, order_depth, current_pos, base_target, data):
        orders = []
        if product not in self.MR_PRODUCTS or base_target != 0 or abs(current_pos) >= 6: return orders
        bid, ask = self.best_bid(order_depth), self.best_ask(order_depth)
        if bid is None or ask is None: return orders
        mid = (bid + ask) / 2.0
        last = data['last_mid'].get(product)
        if last is None: return orders
        delta = mid - last
        threshold = max(3.0, 2.5 * float(data['abs_ewma'].get(product, 1.0)))
        if delta > threshold and current_pos > -6:
            if ask - 1 > bid:
                qty = min(2, self.POSITION_LIMIT + current_pos)
                if qty > 0: orders.append(Order(product, ask - 1, -qty))
        elif delta < -threshold and current_pos < 6:
            if bid + 1 < ask:
                qty = min(2, self.POSITION_LIMIT - current_pos)
                if qty > 0: orders.append(Order(product, bid + 1, qty))
        return orders
    def override_strategy_orders(self, state, data):
        override_orders = {product: [] for product in state.order_depths if product in self.OVERRIDE_PRODUCTS}
        substates = data.setdefault('__substates', {})
        strategies = [
            ('oxygen', _OxygenShakeStrategy(), set(_OxygenShakeStrategy.TRADED)),
            ('pebbles', _PebblesStrategy(), set(_PebblesStrategy.TRADED)), 
            ('snackpack', _SnackpackStrategy(), set(_SnackpackStrategy.TRADED)), 
            ('sleep_pods', _SleepPodStrategy(), set(_SleepPodStrategy.PRODUCTS)), 
            ('galaxy', _GalaxyStrategy(), set(_GalaxyStrategy.GALAXY_PRODUCTS)), 
            ('robot', _RobotStrategy(), set(_RobotStrategy.TRADED)), 
            ('microchip', _MicrochipStrategy(), set(_MicrochipStrategy.ALL_MICROCHIPS))
        ]
        for key, strategy, traded_products in strategies:
            orders, _, new_trader_data = strategy.run_with_data(state=state, trader_data=substates.get(key, ''))
            substates[key] = new_trader_data
            for product in traded_products:
                if product in state.order_depths: override_orders[product] = orders.get(product, [])
        return override_orders
    def run(self, state):
        result = {}
        data = self.load_data(state.traderData)
        override_orders = self.override_strategy_orders(state, data)
        mids, base_targets = {}, {}
        for product, order_depth in state.order_depths.items():
            mid = self.mid_price(order_depth)
            if mid is not None:
                mids[product] = mid
                self.store_init_mid(data, product, mid)
            base_targets[product] = self.base_target_for_product(data=data, product=product, mid=mid, timestamp=state.timestamp)
        pebble_targets = self.pebble_arb_targets(mids=mids, order_depths=state.order_depths, base_targets=base_targets)
        snack_targets = self.snack_pair_targets(data=data, mids=mids, base_targets=base_targets)
        for product, order_depth in state.order_depths.items():
            if mids.get(product) is not None: self.update_micro_stats(data, product, mids[product])
            if product in override_orders:
                result[product] = override_orders.get(product, [])
                continue
            target_pos = base_targets.get(product, 0)
            if product in pebble_targets: target_pos = pebble_targets[product]
            if target_pos == 0 and product in snack_targets: target_pos = snack_targets[product]
            current_pos = state.position.get(product, 0)
            orders = self.send_to_target(product=product, order_depth=order_depth, current_pos=current_pos, target_pos=target_pos)
            if target_pos == 0: orders.extend(self.passive_mean_reversion_orders(product=product, order_depth=order_depth, current_pos=current_pos, base_target=target_pos, data=data))
            result[product] = orders
        return result, 0, self.save_data(data)