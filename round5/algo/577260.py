from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List, Dict, Optional, Tuple, Any
import json
import math

class _PebblesStrategy:
    POSITION_LIMIT = 10
    XS = 'PEBBLES_XS'
    S = 'PEBBLES_S'
    M = 'PEBBLES_M'
    L = 'PEBBLES_L'
    XL = 'PEBBLES_XL'
    TRADED = {XS, S, M, L, XL}
    ALL_PEBBLES = [XS, S, M, L, XL]
    SHORT_COVER_BUFFER = {XS: 200.0, S: 200.0}
    SHORT_REENTRY_BUFFER = {XS: 100.0, S: 100.0}
    M_GRID_THRESHOLD = 300.0
    L_GRID_THRESHOLD = 100.0
    XL_COVER_BUFFER = 100.0
    XL_REENTRY_BUFFER = 100.0
    XL_LONG_XSS_TRIGGER = 450.0
    XL_LONG_REST_MIN = 250.0
    XL_LONG_REST_STRONG = 900.0
    XL_LONG_ML_MAX = 100.0
    XL_SHORT_ML_TRIGGER = 800.0
    XL_SHORT_REST_MIN = 300.0
    XL_SHORT_REST_STRONG = 1000.0
    XL_SHORT_ML_MIN = 700.0
    XL_CONFIRM_COUNT = 2

    def bid(self):
        return 15

    def best_bid_ask(self, order_depth: OrderDepth) -> Tuple[Optional[int], Optional[int]]:
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        return (best_bid, best_ask)

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
        return {'init_mid': {}, 'last_mid': {}, 'short_anchor': {}, 'cover_anchor': {}, 'grid_ref': {}, 'grid_entry': {}, 'grid_dir': {}, 'xl_raw_signal': 0, 'xl_signal_count': 0, 'xl_confirmed_signal': 0, 'xl_buffer_dir': 0, 'xl_entry_anchor': None, 'xl_exit_anchor': None, 'xl_paused_dir': 0, 'pebble_sum_ref': None}

    def load_data(self, trader_data: str, timestamp: int) -> Dict:
        if timestamp == 0:
            return self.fresh_data()
        if not trader_data:
            return self.fresh_data()
        try:
            data = json.loads(trader_data)
        except Exception:
            return self.fresh_data()
        data.setdefault('init_mid', {})
        data.setdefault('last_mid', {})
        data.setdefault('short_anchor', {})
        data.setdefault('cover_anchor', {})
        data.setdefault('grid_ref', {})
        data.setdefault('grid_entry', {})
        data.setdefault('grid_dir', {})
        data.setdefault('xl_raw_signal', 0)
        data.setdefault('xl_signal_count', 0)
        data.setdefault('xl_confirmed_signal', 0)
        data.setdefault('xl_buffer_dir', 0)
        data.setdefault('xl_entry_anchor', None)
        data.setdefault('xl_exit_anchor', None)
        data.setdefault('xl_paused_dir', 0)
        data.setdefault('pebble_sum_ref', None)
        return data

    def update_state(self, data: Dict, mids: Dict[str, float]) -> None:
        for product in self.ALL_PEBBLES:
            if product not in mids:
                continue
            mid = mids[product]
            if product not in data['init_mid']:
                data['init_mid'][product] = mid
            data['last_mid'][product] = mid

    def buffered_short_target(self, product: str, order_depth: OrderDepth, current_position: int, data: Dict) -> int:
        best_bid, best_ask = self.best_bid_ask(order_depth)
        if best_bid is None and best_ask is None:
            return current_position
        cover_buffer = self.SHORT_COVER_BUFFER[product]
        reentry_buffer = self.SHORT_REENTRY_BUFFER[product]
        short_anchor = data['short_anchor'].get(product)
        cover_anchor = data['cover_anchor'].get(product)
        if current_position < 0:
            if short_anchor is None:
                if best_bid is not None:
                    short_anchor = float(best_bid)
                else:
                    mid = self.mid_price(order_depth)
                    short_anchor = float(mid) if mid is not None else 0.0
                data['short_anchor'][product] = short_anchor
            if best_bid is not None and best_bid >= short_anchor + cover_buffer:
                if best_ask is not None:
                    data['cover_anchor'][product] = float(best_ask)
                else:
                    data['cover_anchor'][product] = float(best_bid)
                return 0
            return -self.POSITION_LIMIT
        else:
            if current_position > 0:
                return 0
            if cover_anchor is None:
                if best_bid is not None:
                    data['short_anchor'][product] = float(best_bid)
                else:
                    mid = self.mid_price(order_depth)
                    data['short_anchor'][product] = float(mid) if mid is not None else 0.0
                return -self.POSITION_LIMIT
            if best_bid is not None and best_bid >= cover_anchor + reentry_buffer:
                data['short_anchor'][product] = float(best_bid)
                return -self.POSITION_LIMIT
            return 0

    def reset_grid_position_state(self, data: Dict, product: str) -> None:
        data['grid_entry'][product] = None
        data['grid_dir'][product] = 0

    def long_only_grid_target(self, product: str, order_depth: OrderDepth, current_position: int, data: Dict, threshold: float) -> int:
        best_bid, best_ask = self.best_bid_ask(order_depth)
        mid = self.mid_price(order_depth)
        if best_bid is None and best_ask is None and (mid is None):
            return current_position
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

    def symmetric_grid_target(self, product: str, order_depth: OrderDepth, current_position: int, data: Dict, threshold: float) -> int:
        best_bid, best_ask = self.best_bid_ask(order_depth)
        mid = self.mid_price(order_depth)
        if best_bid is None and best_ask is None and (mid is None):
            return current_position
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

    def pebble_identity_ok(self, data: Dict, mids: Dict[str, float]) -> bool:
        if not all((p in mids for p in self.ALL_PEBBLES)):
            return False
        pebble_sum = sum((mids[p] for p in self.ALL_PEBBLES))
        if data.get('pebble_sum_ref') is None:
            data['pebble_sum_ref'] = pebble_sum
            return True
        return abs(pebble_sum - data['pebble_sum_ref']) <= 250

    def compute_xl_signal(self, data: Dict, mids: Dict[str, float]) -> int:
        required = [self.XS, self.S, self.M, self.L, self.XL]
        if not all((p in mids for p in required)):
            return 0
        init = data['init_mid']
        if not all((p in init for p in required)):
            return 0
        xs_s_now = mids[self.XS] + mids[self.S]
        xs_s_init = init[self.XS] + init[self.S]
        xs_s_move = xs_s_now - xs_s_init
        ml_now = mids[self.M] + mids[self.L]
        ml_init = init[self.M] + init[self.L]
        ml_move = ml_now - ml_init
        rest4_move = xs_s_move + ml_move
        short_signal = ml_move > self.XL_SHORT_ML_TRIGGER and rest4_move > self.XL_SHORT_REST_MIN or (rest4_move > self.XL_SHORT_REST_STRONG and ml_move > self.XL_SHORT_ML_MIN)
        long_signal = xs_s_move < -self.XL_LONG_XSS_TRIGGER and ml_move < self.XL_LONG_ML_MAX and (rest4_move < -self.XL_LONG_REST_MIN) or (rest4_move < -self.XL_LONG_REST_STRONG and ml_move < self.XL_LONG_ML_MAX)
        if short_signal:
            return -1
        if long_signal:
            return +1
        return 0

    def confirmed_xl_signal(self, data: Dict, raw_signal: int) -> int:
        if raw_signal == 0:
            return data.get('xl_confirmed_signal', 0)
        prev_raw = data.get('xl_raw_signal', 0)
        if raw_signal == prev_raw:
            data['xl_signal_count'] = data.get('xl_signal_count', 0) + 1
        else:
            data['xl_signal_count'] = 1
            data['xl_raw_signal'] = raw_signal
        if data['xl_signal_count'] >= self.XL_CONFIRM_COUNT:
            data['xl_confirmed_signal'] = raw_signal
        return data.get('xl_confirmed_signal', 0)

    def reset_xl_buffer(self, data: Dict, direction: int) -> None:
        data['xl_buffer_dir'] = direction
        data['xl_entry_anchor'] = None
        data['xl_exit_anchor'] = None
        data['xl_paused_dir'] = 0

    def buffered_xl_target(self, order_depth: OrderDepth, current_position: int, desired_signal: int, desired_abs_position: int, data: Dict) -> int:
        best_bid, best_ask = self.best_bid_ask(order_depth)
        if best_bid is None and best_ask is None:
            return current_position
        if desired_signal == 0 or desired_abs_position <= 0:
            self.reset_xl_buffer(data, 0)
            return 0
        desired_abs_position = max(0, min(self.POSITION_LIMIT, desired_abs_position))
        if data.get('xl_buffer_dir', 0) != desired_signal:
            self.reset_xl_buffer(data, desired_signal)
        entry_anchor = data.get('xl_entry_anchor')
        exit_anchor = data.get('xl_exit_anchor')
        paused_dir = data.get('xl_paused_dir', 0)
        mid = self.mid_price(order_depth)
        if desired_signal > 0:
            if current_position > 0:
                if entry_anchor is None:
                    if best_ask is not None:
                        entry_anchor = float(best_ask)
                    elif mid is not None:
                        entry_anchor = float(mid)
                    else:
                        entry_anchor = 0.0
                    data['xl_entry_anchor'] = entry_anchor
                if best_ask is not None and best_ask <= entry_anchor - self.XL_COVER_BUFFER:
                    if best_bid is not None:
                        data['xl_exit_anchor'] = float(best_bid)
                    else:
                        data['xl_exit_anchor'] = float(best_ask)
                    data['xl_entry_anchor'] = None
                    data['xl_paused_dir'] = +1
                    return 0
                return desired_abs_position
            else:
                if paused_dir != +1 or exit_anchor is None:
                    if best_ask is not None:
                        data['xl_entry_anchor'] = float(best_ask)
                    elif mid is not None:
                        data['xl_entry_anchor'] = float(mid)
                    else:
                        data['xl_entry_anchor'] = 0.0
                    data['xl_exit_anchor'] = None
                    data['xl_paused_dir'] = 0
                    return desired_abs_position
                if best_ask is not None and best_ask <= exit_anchor - self.XL_REENTRY_BUFFER:
                    data['xl_entry_anchor'] = float(best_ask)
                    data['xl_exit_anchor'] = None
                    data['xl_paused_dir'] = 0
                    return desired_abs_position
                return 0
        elif current_position < 0:
            if entry_anchor is None:
                if best_bid is not None:
                    entry_anchor = float(best_bid)
                elif mid is not None:
                    entry_anchor = float(mid)
                else:
                    entry_anchor = 0.0
                data['xl_entry_anchor'] = entry_anchor
            if best_bid is not None and best_bid >= entry_anchor + self.XL_COVER_BUFFER:
                if best_ask is not None:
                    data['xl_exit_anchor'] = float(best_ask)
                else:
                    data['xl_exit_anchor'] = float(best_bid)
                data['xl_entry_anchor'] = None
                data['xl_paused_dir'] = -1
                return 0
            return -desired_abs_position
        else:
            if paused_dir != -1 or exit_anchor is None:
                if best_bid is not None:
                    data['xl_entry_anchor'] = float(best_bid)
                elif mid is not None:
                    data['xl_entry_anchor'] = float(mid)
                else:
                    data['xl_entry_anchor'] = 0.0
                data['xl_exit_anchor'] = None
                data['xl_paused_dir'] = 0
                return -desired_abs_position
            if best_bid is not None and best_bid >= exit_anchor + self.XL_REENTRY_BUFFER:
                data['xl_entry_anchor'] = float(best_bid)
                data['xl_exit_anchor'] = None
                data['xl_paused_dir'] = 0
                return -desired_abs_position
            return 0

    def orders_to_target(self, product: str, order_depth: OrderDepth, current_position: int, target_position: int, max_spread: int) -> List[Order]:
        orders: List[Order] = []
        target_position = max(-self.POSITION_LIMIT, min(self.POSITION_LIMIT, target_position))
        delta = target_position - current_position
        if delta == 0:
            return orders
        sp = self.spread(order_depth)
        reducing_risk = abs(target_position) < abs(current_position)
        if sp is not None and sp > max_spread and (not reducing_risk):
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

    def run_with_data(self, state: TradingState, trader_data: str):
        result: Dict[str, List[Order]] = {}
        data = self.load_data(trader_data, state.timestamp)
        mids: Dict[str, float] = {}
        for product, order_depth in state.order_depths.items():
            mid = self.mid_price(order_depth)
            if mid is not None:
                mids[product] = mid
        self.update_state(data, mids)
        identity_ok = self.pebble_identity_ok(data, mids)
        for product in state.order_depths:
            result[product] = []
        for product in [self.XS, self.S]:
            if product not in state.order_depths:
                continue
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
            if raw_xl_signal != 0 and xl_signal != 0 and (raw_xl_signal != xl_signal):
                desired_signal = 0
                desired_abs_position = 0
            elif xl_signal != 0:
                desired_signal = xl_signal
                desired_abs_position = 10
            elif raw_xl_signal != 0:
                desired_signal = raw_xl_signal
                desired_abs_position = 5
            else:
                desired_signal = 0
                desired_abs_position = 0
            current_position = state.position.get(self.XL, 0)
            xl_target = self.buffered_xl_target(order_depth=state.order_depths[self.XL], current_position=current_position, desired_signal=desired_signal, desired_abs_position=desired_abs_position, data=data)
            result[self.XL] = self.orders_to_target(product=self.XL, order_depth=state.order_depths[self.XL], current_position=current_position, target_position=xl_target, max_spread=100)
        elif self.XL in state.order_depths:
            self.reset_xl_buffer(data, 0)
            current_position = state.position.get(self.XL, 0)
            result[self.XL] = self.orders_to_target(product=self.XL, order_depth=state.order_depths[self.XL], current_position=current_position, target_position=0, max_spread=100)
        traderData = json.dumps(data, separators=(',', ':'))
        conversions = 0
        return (result, conversions, traderData)

class _SnackpackStrategy:
    POSITION_LIMIT = 10
    CHOCOLATE = 'SNACKPACK_CHOCOLATE'
    VANILLA = 'SNACKPACK_VANILLA'
    PISTACHIO = 'SNACKPACK_PISTACHIO'
    STRAWBERRY = 'SNACKPACK_STRAWBERRY'
    RASPBERRY = 'SNACKPACK_RASPBERRY'
    TRADED = {CHOCOLATE, VANILLA, PISTACHIO, STRAWBERRY, RASPBERRY}
    SYMMETRIC_GRID_LAYERS = {CHOCOLATE: [(125.0, 2), (150.0, 8)], VANILLA: [(125.0, 2), (150.0, 8)], RASPBERRY: [(75.0, 8), (100.0, 2)], PISTACHIO: [(75.0, 5), (150.0, 5)], STRAWBERRY: [(300.0, 4), (400.0, 6)]}

    def bid(self):
        return 15

    def best_bid_ask(self, order_depth: OrderDepth) -> Tuple[Optional[int], Optional[int]]:
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        return (best_bid, best_ask)

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

    def usable_price(self, order_depth: OrderDepth) -> Optional[float]:
        mid = self.mid_price(order_depth)
        if mid is not None:
            return mid
        best_bid, best_ask = self.best_bid_ask(order_depth)
        if best_bid is not None:
            return float(best_bid)
        if best_ask is not None:
            return float(best_ask)
        return None

    def fresh_data(self) -> Dict:
        return {'layer_ref': {}, 'layer_entry': {}, 'layer_dir': {}, 'last_mid': {}}

    def load_data(self, trader_data: str, timestamp: int) -> Dict:
        if timestamp == 0:
            return self.fresh_data()
        if not trader_data:
            return self.fresh_data()
        try:
            data = json.loads(trader_data)
        except Exception:
            return self.fresh_data()
        data.setdefault('layer_ref', {})
        data.setdefault('layer_entry', {})
        data.setdefault('layer_dir', {})
        data.setdefault('last_mid', {})
        return data

    def layer_key(self, product: str, layer_idx: int) -> str:
        return product + '#' + str(layer_idx)

    def init_layer_if_needed(self, data: Dict, key: str, initial_price: float) -> None:
        if key not in data['layer_ref'] or data['layer_ref'].get(key) is None:
            data['layer_ref'][key] = float(initial_price)
            data['layer_entry'][key] = None
            data['layer_dir'][key] = 0

    def reset_layer_position_state(self, data: Dict, key: str) -> None:
        data['layer_entry'][key] = None
        data['layer_dir'][key] = 0

    def update_last_mid(self, data: Dict, product: str, mid: Optional[float]) -> None:
        if mid is not None:
            data['last_mid'][product] = mid

    def layered_symmetric_grid_target(self, product: str, order_depth: OrderDepth, data: Dict) -> int:
        best_bid, best_ask = self.best_bid_ask(order_depth)
        usable = self.usable_price(order_depth)
        if usable is None:
            return 0
        target = 0
        layers = self.SYMMETRIC_GRID_LAYERS[product]
        for idx, (threshold, qty) in enumerate(layers):
            key = self.layer_key(product, idx)
            self.init_layer_if_needed(data, key, usable)
            ref = float(data['layer_ref'][key])
            entry = data['layer_entry'].get(key)
            layer_dir = int(data['layer_dir'].get(key, 0))
            if layer_dir > 0:
                if entry is None:
                    entry = usable
                    data['layer_entry'][key] = float(entry)
                if best_bid is not None and best_bid >= float(entry) + threshold:
                    data['layer_ref'][key] = float(best_bid)
                    self.reset_layer_position_state(data, key)
                    layer_dir = 0
                else:
                    target += qty
                    continue
            elif layer_dir < 0:
                if entry is None:
                    entry = usable
                    data['layer_entry'][key] = float(entry)
                if best_ask is not None and best_ask <= float(entry) - threshold:
                    data['layer_ref'][key] = float(best_ask)
                    self.reset_layer_position_state(data, key)
                    layer_dir = 0
                else:
                    target -= qty
                    continue
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

    def orders_to_target(self, product: str, order_depth: OrderDepth, current_position: int, target_position: int, max_spread: int) -> List[Order]:
        orders: List[Order] = []
        target_position = max(-self.POSITION_LIMIT, min(self.POSITION_LIMIT, target_position))
        delta = target_position - current_position
        if delta == 0:
            return orders
        sp = self.spread(order_depth)
        reducing_risk = abs(target_position) < abs(current_position)
        if sp is not None and sp > max_spread and (not reducing_risk):
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

    def run_with_data(self, state: TradingState, trader_data: str):
        result: Dict[str, List[Order]] = {}
        data = self.load_data(trader_data, state.timestamp)
        for product in state.order_depths:
            result[product] = []
        for product in self.TRADED:
            if product not in state.order_depths:
                continue
            order_depth = state.order_depths[product]
            current_position = state.position.get(product, 0)
            mid = self.mid_price(order_depth)
            self.update_last_mid(data, product, mid)
            target_position = self.layered_symmetric_grid_target(product=product, order_depth=order_depth, data=data)
            result[product] = self.orders_to_target(product=product, order_depth=order_depth, current_position=current_position, target_position=target_position, max_spread=80)
        traderData = json.dumps(data, separators=(',', ':'))
        conversions = 0
        return (result, conversions, traderData)

class _SleepPodStrategy:
    LIMIT = 10
    SUEDE = 'SLEEP_POD_SUEDE'
    LAMB = 'SLEEP_POD_LAMB_WOOL'
    POLY = 'SLEEP_POD_POLYESTER'
    NYLON = 'SLEEP_POD_NYLON'
    COTTON = 'SLEEP_POD_COTTON'
    PRODUCTS = [SUEDE, LAMB, POLY, NYLON, COTTON]
    BASE_PRODUCT = SUEDE
    FAST_ALPHA = 2.0 / (16.0 + 1.0)
    SLOW_ALPHA = 2.0 / (100.0 + 1.0)
    ANCHOR_ALPHA = 2.0 / (250.0 + 1.0)
    VOL_ALPHA = 2.0 / (60.0 + 1.0)
    MIN_OBS_FOR_ADAPTIVE = 450
    OPEN_MOVE_SPREAD_MULT = 5.0
    OPEN_MOVE_VOL_MULT = 6.0
    CONFIRM_COUNT = 3
    ADAPTIVE_SIZE = 10

    def run_with_data(self, state: TradingState, trader_data: str):
        result: Dict[str, List[Order]] = {}
        data = self._load_state(trader_data)
        if 'pods' not in data:
            data['pods'] = {}
        for product in self.PRODUCTS:
            if product not in data['pods']:
                data['pods'][product] = self._new_memory()
        mids, spreads = self._read_market(state)
        for product in self.PRODUCTS:
            if product in mids:
                self._update_memory(memory=data['pods'][product], mid=mids[product], spread=spreads[product])
        targets = {p: 0 for p in self.PRODUCTS}
        if self.SUEDE in mids:
            targets[self.SUEDE] = self.LIMIT
        for product in [self.LAMB, self.POLY, self.NYLON, self.COTTON]:
            if product not in mids:
                continue
            target = self._adaptive_target(memory=data['pods'][product], mid=mids[product], spread=spreads[product])
            targets[product] = target
        for product in self.PRODUCTS:
            if product not in state.order_depths:
                continue
            position = state.position.get(product, 0)
            target = max(-self.LIMIT, min(self.LIMIT, int(targets.get(product, 0))))
            orders = self._move_to_target(product=product, order_depth=state.order_depths[product], position=position, target=target)
            if orders:
                result[product] = orders
        return (result, 0, self._dump_state(data))

    def _adaptive_target(self, memory: Dict[str, Any], mid: float, spread: float) -> int:
        if memory['obs'] < self.MIN_OBS_FOR_ADAPTIVE:
            return memory.get('target', 0)
        open_mid = memory['open']
        fast = memory['fast']
        slow = memory['slow']
        anchor = memory['anchor']
        vol = max(1.0, memory['vol'])
        open_move = mid - open_mid
        fast_slow = fast - slow
        anchor_move = mid - anchor
        required_move = max(self.OPEN_MOVE_SPREAD_MULT * spread, self.OPEN_MOVE_VOL_MULT * vol)
        long_signal = open_move > required_move and fast_slow > 0 and (anchor_move > -0.25 * required_move)
        short_signal = open_move < -required_move and fast_slow < 0 and (anchor_move < 0.25 * required_move)
        if long_signal:
            memory['long_count'] += 1
            memory['short_count'] = 0
        elif short_signal:
            memory['short_count'] += 1
            memory['long_count'] = 0
        else:
            memory['long_count'] = max(0, memory['long_count'] - 1)
            memory['short_count'] = max(0, memory['short_count'] - 1)
        target = memory.get('target', 0)
        if memory['long_count'] >= self.CONFIRM_COUNT:
            target = self.ADAPTIVE_SIZE
        elif memory['short_count'] >= self.CONFIRM_COUNT:
            target = -self.ADAPTIVE_SIZE
        memory['target'] = target
        return target

    def _update_memory(self, memory: Dict[str, Any], mid: float, spread: float) -> None:
        memory['obs'] += 1
        if memory['open'] is None:
            memory['open'] = mid
            memory['prev'] = mid
            memory['fast'] = mid
            memory['slow'] = mid
            memory['anchor'] = mid
            memory['vol'] = max(1.0, 0.35 * spread)
            return
        prev = memory['prev']
        diff = mid - prev
        memory['prev'] = mid
        memory['fast'] = self.FAST_ALPHA * mid + (1.0 - self.FAST_ALPHA) * memory['fast']
        memory['slow'] = self.SLOW_ALPHA * mid + (1.0 - self.SLOW_ALPHA) * memory['slow']
        memory['anchor'] = self.ANCHOR_ALPHA * mid + (1.0 - self.ANCHOR_ALPHA) * memory['anchor']
        memory['vol'] = self.VOL_ALPHA * abs(diff) + (1.0 - self.VOL_ALPHA) * memory['vol']

    def _read_market(self, state: TradingState):
        mids: Dict[str, float] = {}
        spreads: Dict[str, float] = {}
        for product in self.PRODUCTS:
            od = state.order_depths.get(product)
            if od is None or not od.buy_orders or (not od.sell_orders):
                continue
            best_bid = max(od.buy_orders.keys())
            best_ask = min(od.sell_orders.keys())
            mids[product] = (best_bid + best_ask) / 2.0
            spreads[product] = max(1.0, best_ask - best_bid)
        return (mids, spreads)

    def _move_to_target(self, product: str, order_depth: OrderDepth, position: int, target: int) -> List[Order]:
        orders: List[Order] = []
        if position == target:
            return orders
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return orders
        delta = target - position
        if delta > 0:
            self._buy(product, order_depth, orders, delta)
        elif delta < 0:
            self._sell(product, order_depth, orders, -delta)
        return orders

    def _buy(self, product: str, order_depth: OrderDepth, orders: List[Order], quantity: int) -> None:
        remaining = quantity
        for ask in sorted(order_depth.sell_orders.keys()):
            if remaining <= 0:
                break
            available = -order_depth.sell_orders[ask]
            if available <= 0:
                continue
            take = min(remaining, available)
            orders.append(Order(product, ask, take))
            remaining -= take

    def _sell(self, product: str, order_depth: OrderDepth, orders: List[Order], quantity: int) -> None:
        remaining = quantity
        for bid in sorted(order_depth.buy_orders.keys(), reverse=True):
            if remaining <= 0:
                break
            available = order_depth.buy_orders[bid]
            if available <= 0:
                continue
            take = min(remaining, available)
            orders.append(Order(product, bid, -take))
            remaining -= take

    def _new_memory(self) -> Dict[str, Any]:
        return {'obs': 0, 'open': None, 'prev': None, 'fast': None, 'slow': None, 'anchor': None, 'vol': 1.0, 'long_count': 0, 'short_count': 0, 'target': 0}

    def _load_state(self, trader_data: str) -> Dict[str, Any]:
        if not trader_data:
            return {}
        try:
            data = json.loads(trader_data)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def _dump_state(self, data: Dict[str, Any]) -> str:
        try:
            return json.dumps(data, separators=(',', ':'))
        except Exception:
            return '{}'

class _GalaxyStrategy:
    LIMIT = 10
    BLACK = 'GALAXY_SOUNDS_BLACK_HOLES'
    RINGS = 'GALAXY_SOUNDS_PLANETARY_RINGS'
    GALAXY_PRODUCTS = ['GALAXY_SOUNDS_DARK_MATTER', 'GALAXY_SOUNDS_BLACK_HOLES', 'GALAXY_SOUNDS_PLANETARY_RINGS', 'GALAXY_SOUNDS_SOLAR_WINDS', 'GALAXY_SOUNDS_SOLAR_FLAMES']
    FAST_ALPHA = 2.0 / (18.0 + 1.0)
    SLOW_ALPHA = 2.0 / (120.0 + 1.0)
    ANCHOR_ALPHA = 2.0 / (600.0 + 1.0)
    VOL_ALPHA = 2.0 / (90.0 + 1.0)
    PROBE_SIZE = 3
    SAFE_SIZE = 5
    FULL_SIZE = 10

    def run_with_data(self, state: TradingState, trader_data: str):
        result: Dict[str, List[Order]] = {}
        data = self._load_state(trader_data)
        if 'pair' not in data:
            data['pair'] = self._new_pair_memory()
        mids: Dict[str, float] = {}
        spreads: Dict[str, float] = {}
        for product in self.GALAXY_PRODUCTS:
            od = state.order_depths.get(product)
            if od is None or not od.buy_orders or (not od.sell_orders):
                continue
            best_bid = max(od.buy_orders.keys())
            best_ask = min(od.sell_orders.keys())
            mids[product] = (best_bid + best_ask) / 2.0
            spreads[product] = max(1.0, best_ask - best_bid)
        targets = {p: 0 for p in self.GALAXY_PRODUCTS}
        if self.BLACK in mids and self.RINGS in mids:
            pair_size = self._adaptive_pair_size(memory=data['pair'], timestamp=state.timestamp, black_mid=mids[self.BLACK], rings_mid=mids[self.RINGS], black_spread=spreads[self.BLACK], rings_spread=spreads[self.RINGS])
            targets[self.BLACK] = pair_size
            targets[self.RINGS] = -pair_size
        for product in self.GALAXY_PRODUCTS:
            if product not in state.order_depths:
                continue
            position = state.position.get(product, 0)
            target = max(-self.LIMIT, min(self.LIMIT, targets.get(product, 0)))
            orders = self._move_to_target(product=product, order_depth=state.order_depths[product], position=position, target=target)
            if orders:
                result[product] = orders
        return (result, 0, self._dump_state(data))

    def _adaptive_pair_size(self, memory: Dict[str, Any], timestamp: int, black_mid: float, rings_mid: float, black_spread: float, rings_spread: float) -> int:
        rel = black_mid - rings_mid
        pair_cost = black_spread + rings_spread
        memory['obs'] += 1
        memory['last_timestamp'] = timestamp
        if memory['rel_fast'] is None:
            memory['rel_fast'] = rel
            memory['rel_slow'] = rel
            memory['rel_anchor'] = rel
            memory['rel_last'] = rel
            memory['rel_vol'] = 1.0
            memory['pair_size'] = self.PROBE_SIZE
            memory['entry_rel'] = rel
            return self.PROBE_SIZE
        prev_rel = memory['rel_last']
        d_rel = rel - prev_rel
        memory['rel_last'] = rel
        memory['rel_fast'] = self.FAST_ALPHA * rel + (1.0 - self.FAST_ALPHA) * memory['rel_fast']
        memory['rel_slow'] = self.SLOW_ALPHA * rel + (1.0 - self.SLOW_ALPHA) * memory['rel_slow']
        memory['rel_anchor'] = self.ANCHOR_ALPHA * rel + (1.0 - self.ANCHOR_ALPHA) * memory['rel_anchor']
        memory['rel_vol'] = self.VOL_ALPHA * abs(d_rel) + (1.0 - self.VOL_ALPHA) * memory['rel_vol']
        noise = max(1.0, memory['rel_vol'], 0.3 * pair_cost)
        rel_fast = memory['rel_fast']
        rel_slow = memory['rel_slow']
        rel_anchor = memory['rel_anchor']
        health = 0
        if rel_fast > rel_slow + 0.2 * noise:
            health += 1
        elif rel_fast < rel_slow - 0.2 * noise:
            health -= 1
        if rel > rel_anchor + 0.25 * noise:
            health += 1
        elif rel < rel_anchor - 0.25 * noise:
            health -= 1
        memory['rel_history'].append(rel)
        if len(memory['rel_history']) > 80:
            memory['rel_history'] = memory['rel_history'][-80:]
        recent_momentum = 0.0
        if len(memory['rel_history']) >= 20:
            recent_momentum = memory['rel_history'][-1] - memory['rel_history'][-20]
            if recent_momentum > 1.5 * noise:
                health += 1
            elif recent_momentum < -1.5 * noise:
                health -= 1
        entry_rel = memory.get('entry_rel')
        if entry_rel is not None:
            adverse = entry_rel - rel
            if adverse > max(4.0 * noise, 1.5 * pair_cost):
                health -= 2
        if health >= 2:
            memory['good_count'] += 1
            memory['bad_count'] = max(0, memory['bad_count'] - 1)
        elif health <= -2:
            memory['bad_count'] += 1
            memory['good_count'] = max(0, memory['good_count'] - 1)
        else:
            memory['good_count'] = max(0, memory['good_count'] - 1)
            memory['bad_count'] = max(0, memory['bad_count'] - 1)
        current_size = int(memory.get('pair_size', 0))
        if memory['bad_count'] >= 8:
            new_size = 0
        elif memory['bad_count'] >= 4:
            new_size = self.PROBE_SIZE
        elif memory['good_count'] >= 5:
            new_size = self.FULL_SIZE
        elif memory['good_count'] >= 2:
            new_size = max(current_size, self.SAFE_SIZE)
        elif current_size == 0:
            if health > 0:
                new_size = self.PROBE_SIZE
            else:
                new_size = 0
        else:
            new_size = current_size
        if current_size == 0 and health <= 0:
            new_size = 0
        if current_size == 0 and new_size > 0:
            memory['entry_rel'] = rel
        if new_size == 0:
            memory['entry_rel'] = None
        if abs(new_size - current_size) < 2 and new_size != 0:
            new_size = current_size
        memory['pair_size'] = int(max(0, min(self.LIMIT, new_size)))
        return memory['pair_size']

    def _move_to_target(self, product: str, order_depth: OrderDepth, position: int, target: int) -> List[Order]:
        orders: List[Order] = []
        if position == target:
            return orders
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return orders
        delta = target - position
        if delta > 0:
            self._take_asks(product, order_depth, orders, delta)
        elif delta < 0:
            self._hit_bids(product, order_depth, orders, -delta)
        return orders

    def _take_asks(self, product: str, order_depth: OrderDepth, orders: List[Order], quantity: int) -> None:
        remaining = quantity
        for ask in sorted(order_depth.sell_orders.keys()):
            if remaining <= 0:
                break
            available = -order_depth.sell_orders[ask]
            if available <= 0:
                continue
            take = min(remaining, available)
            orders.append(Order(product, ask, take))
            remaining -= take

    def _hit_bids(self, product: str, order_depth: OrderDepth, orders: List[Order], quantity: int) -> None:
        remaining = quantity
        for bid in sorted(order_depth.buy_orders.keys(), reverse=True):
            if remaining <= 0:
                break
            available = order_depth.buy_orders[bid]
            if available <= 0:
                continue
            take = min(remaining, available)
            orders.append(Order(product, bid, -take))
            remaining -= take

    def _new_pair_memory(self) -> Dict[str, Any]:
        return {'obs': 0, 'last_timestamp': None, 'rel_fast': None, 'rel_slow': None, 'rel_anchor': None, 'rel_last': None, 'rel_vol': 1.0, 'rel_history': [], 'entry_rel': None, 'good_count': 0, 'bad_count': 0, 'pair_size': 0}

    def _load_state(self, trader_data: str) -> Dict[str, Any]:
        if not trader_data:
            return {}
        try:
            data = json.loads(trader_data)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def _dump_state(self, data: Dict[str, Any]) -> str:
        try:
            return json.dumps(data, separators=(',', ':'))
        except Exception:
            return '{}'

class _RobotStrategy:
    POSITION_LIMIT = 10
    ROBOT_DISHES = 'ROBOT_DISHES'
    ROBOT_MOPPING = 'ROBOT_MOPPING'
    ROBOT_LAUNDRY = 'ROBOT_LAUNDRY'
    ROBOT_IRONING = 'ROBOT_IRONING'
    TRADED = {ROBOT_DISHES, ROBOT_MOPPING, ROBOT_LAUNDRY, ROBOT_IRONING}
    DISHES_GRID_THRESHOLD = 80.0
    EARLY_DETECT_END = 5000
    EARLY_HIT_THRESHOLD = 50.0
    EARLY_FALLBACK_THRESHOLD = 20.0
    MOPPING_INVALIDATE_THRESHOLD = 300.0
    MOPPING_COVER_BUFFER = 300.0
    MOPPING_REENTRY_BUFFER = 100.0
    LAUNDRY_COVER_BUFFER = 350.0
    LAUNDRY_REENTRY_BUFFER = 150.0
    IRONING_CONFIRM_THRESHOLD = 300.0
    IRONING_COVER_BUFFER = 200.0
    IRONING_REENTRY_BUFFER = 125.0
    MAX_SPREAD_TO_OPEN = 25

    def bid(self):
        return 15

    def fresh_data(self) -> Dict:
        return {'init_mid': {}, 'last_mid': {}, 'mode': {}, 'grid_ref': {}, 'grid_entry': {}, 'grid_dir': {}, 'trend_active_dir': {}, 'entry_anchor': {}, 'exit_anchor': {}, 'paused_dir': {}}

    def load_data(self, trader_data: str, timestamp: int) -> Dict:
        if timestamp == 0:
            return self.fresh_data()
        if not trader_data:
            return self.fresh_data()
        try:
            data = json.loads(trader_data)
        except Exception:
            return self.fresh_data()
        data.setdefault('init_mid', {})
        data.setdefault('last_mid', {})
        data.setdefault('mode', {})
        data.setdefault('grid_ref', {})
        data.setdefault('grid_entry', {})
        data.setdefault('grid_dir', {})
        data.setdefault('trend_active_dir', {})
        data.setdefault('entry_anchor', {})
        data.setdefault('exit_anchor', {})
        data.setdefault('paused_dir', {})
        return data

    def save_data(self, data: Dict) -> str:
        return json.dumps(data, separators=(',', ':'))

    def update_mid_state(self, data: Dict, product: str, mid: float) -> None:
        if product not in data['init_mid']:
            data['init_mid'][product] = mid
        data['last_mid'][product] = mid

    def best_bid_ask(self, od: OrderDepth) -> Tuple[Optional[int], Optional[int]]:
        best_bid = max(od.buy_orders.keys()) if od.buy_orders else None
        best_ask = min(od.sell_orders.keys()) if od.sell_orders else None
        return (best_bid, best_ask)

    def mid_price(self, od: OrderDepth) -> Optional[float]:
        best_bid, best_ask = self.best_bid_ask(od)
        if best_bid is not None and best_ask is not None:
            return (best_bid + best_ask) / 2.0
        if best_bid is not None:
            return float(best_bid)
        if best_ask is not None:
            return float(best_ask)
        return None

    def spread(self, od: OrderDepth) -> Optional[int]:
        best_bid, best_ask = self.best_bid_ask(od)
        if best_bid is None or best_ask is None:
            return None
        return best_ask - best_bid

    def update_mopping_laundry_mode(self, data: Dict, product: str, mid: float, timestamp: int) -> str:
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
        if mode == 'OFF':
            return mode
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

    def update_ironing_mode(self, data: Dict, product: str, mid: float) -> str:
        mode = data['mode'].get(product, 'WAIT')
        if mode in ('LONG', 'SHORT', 'OFF'):
            return mode
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

    def reset_grid_position_state(self, data: Dict, product: str) -> None:
        data['grid_entry'][product] = None
        data['grid_dir'][product] = 0

    def symmetric_grid_target(self, product: str, order_depth: OrderDepth, current_position: int, data: Dict, threshold: float) -> int:
        best_bid, best_ask = self.best_bid_ask(order_depth)
        mid = self.mid_price(order_depth)
        if best_bid is None and best_ask is None and (mid is None):
            return current_position
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

    def reset_trend_state(self, data: Dict, product: str) -> None:
        data['trend_active_dir'][product] = 0
        data['entry_anchor'][product] = None
        data['exit_anchor'][product] = None
        data['paused_dir'][product] = 0

    def buffered_trend_target(self, data: Dict, product: str, od: OrderDepth, current_position: int, desired_dir: int, cover_buffer: float, reentry_buffer: float) -> int:
        best_bid, best_ask = self.best_bid_ask(od)
        mid = self.mid_price(od)
        if best_bid is None and best_ask is None and (mid is None):
            return current_position
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
            if current_position < 0:
                return 0
            if current_position > 0:
                if entry_anchor is None:
                    entry_anchor = float(best_ask if best_ask is not None else mid)
                    data['entry_anchor'][product] = entry_anchor
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
            if current_position > 0:
                return 0
            if current_position < 0:
                if entry_anchor is None:
                    entry_anchor = float(best_bid if best_bid is not None else mid)
                    data['entry_anchor'][product] = entry_anchor
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

    def target_for_product(self, data: Dict, product: str, od: OrderDepth, current_position: int, timestamp: int) -> int:
        mid = self.mid_price(od)
        if mid is None:
            return current_position
        if product == self.ROBOT_DISHES:
            return self.symmetric_grid_target(product=product, order_depth=od, current_position=current_position, data=data, threshold=self.DISHES_GRID_THRESHOLD)
        if product == self.ROBOT_MOPPING:
            mode = self.update_mopping_laundry_mode(data, product, mid, timestamp)
            if mode == 'LONG':
                return self.buffered_trend_target(data=data, product=product, od=od, current_position=current_position, desired_dir=1, cover_buffer=self.MOPPING_COVER_BUFFER, reentry_buffer=self.MOPPING_REENTRY_BUFFER)
            if mode == 'SHORT':
                return self.buffered_trend_target(data=data, product=product, od=od, current_position=current_position, desired_dir=-1, cover_buffer=self.MOPPING_COVER_BUFFER, reentry_buffer=self.MOPPING_REENTRY_BUFFER)
            return 0
        if product == self.ROBOT_LAUNDRY:
            mode = self.update_mopping_laundry_mode(data, product, mid, timestamp)
            if mode == 'LONG':
                return self.buffered_trend_target(data=data, product=product, od=od, current_position=current_position, desired_dir=1, cover_buffer=self.LAUNDRY_COVER_BUFFER, reentry_buffer=self.LAUNDRY_REENTRY_BUFFER)
            if mode == 'SHORT':
                return self.buffered_trend_target(data=data, product=product, od=od, current_position=current_position, desired_dir=-1, cover_buffer=self.LAUNDRY_COVER_BUFFER, reentry_buffer=self.LAUNDRY_REENTRY_BUFFER)
            return 0
        if product == self.ROBOT_IRONING:
            mode = self.update_ironing_mode(data, product, mid)
            if mode == 'LONG':
                return self.buffered_trend_target(data=data, product=product, od=od, current_position=current_position, desired_dir=1, cover_buffer=self.IRONING_COVER_BUFFER, reentry_buffer=self.IRONING_REENTRY_BUFFER)
            if mode == 'SHORT':
                return self.buffered_trend_target(data=data, product=product, od=od, current_position=current_position, desired_dir=-1, cover_buffer=self.IRONING_COVER_BUFFER, reentry_buffer=self.IRONING_REENTRY_BUFFER)
            return 0
        return 0

    def orders_to_target(self, product: str, od: OrderDepth, current_position: int, target_position: int) -> List[Order]:
        orders: List[Order] = []
        target_position = max(-self.POSITION_LIMIT, min(self.POSITION_LIMIT, target_position))
        delta = target_position - current_position
        if delta == 0:
            return orders
        sp = self.spread(od)
        reducing_risk = abs(target_position) < abs(current_position)
        if sp is not None and sp > self.MAX_SPREAD_TO_OPEN and (not reducing_risk):
            return orders
        if delta > 0:
            need = min(delta, self.POSITION_LIMIT - current_position)
            for ask, ask_volume in sorted(od.sell_orders.items()):
                if need <= 0:
                    break
                available = -ask_volume
                if available <= 0:
                    continue
                qty = min(need, available)
                orders.append(Order(product, ask, qty))
                need -= qty
            if need > 0:
                best_bid, best_ask = self.best_bid_ask(od)
                if best_bid is not None and best_ask is not None:
                    price = min(best_bid + 1, best_ask - 1)
                    if price > best_bid:
                        orders.append(Order(product, price, need))
                elif best_bid is not None:
                    orders.append(Order(product, best_bid + 1, need))
                elif best_ask is not None:
                    orders.append(Order(product, best_ask, need))
        elif delta < 0:
            need = min(-delta, self.POSITION_LIMIT + current_position)
            for bid, bid_volume in sorted(od.buy_orders.items(), reverse=True):
                if need <= 0:
                    break
                available = bid_volume
                if available <= 0:
                    continue
                qty = min(need, available)
                orders.append(Order(product, bid, -qty))
                need -= qty
            if need > 0:
                best_bid, best_ask = self.best_bid_ask(od)
                if best_bid is not None and best_ask is not None:
                    price = max(best_ask - 1, best_bid + 1)
                    if price < best_ask:
                        orders.append(Order(product, price, -need))
                elif best_ask is not None:
                    orders.append(Order(product, best_ask - 1, -need))
                elif best_bid is not None:
                    orders.append(Order(product, best_bid, -need))
        return orders

    def run_with_data(self, state: TradingState, trader_data: str):
        result: Dict[str, List[Order]] = {}
        data = self.load_data(trader_data, state.timestamp)
        for product in state.order_depths:
            result[product] = []
        for product, od in state.order_depths.items():
            if product not in self.TRADED:
                continue
            mid = self.mid_price(od)
            if mid is None:
                continue
            self.update_mid_state(data, product, mid)
            current_position = state.position.get(product, 0)
            target_position = self.target_for_product(data=data, product=product, od=od, current_position=current_position, timestamp=state.timestamp)
            result[product] = self.orders_to_target(product=product, od=od, current_position=current_position, target_position=target_position)
        traderData = self.save_data(data)
        conversions = 0
        return (result, conversions, traderData)

class _MicrochipStrategy:
    POSITION_LIMIT = 10
    OVAL = 'MICROCHIP_OVAL'
    SQUARE = 'MICROCHIP_SQUARE'
    CIRCLE = 'MICROCHIP_CIRCLE'
    RECTANGLE = 'MICROCHIP_RECTANGLE'
    TRIANGLE = 'MICROCHIP_TRIANGLE'
    TRADED = {OVAL, SQUARE, CIRCLE}
    ALL_MICROCHIPS = {OVAL, SQUARE, CIRCLE, RECTANGLE, TRIANGLE}
    VOL_ALPHA = 0.03
    SPREAD_ALPHA = 0.05
    FAST_ALPHA = 0.06
    SLOW_ALPHA = 0.012
    PARAMS = {OVAL: {'mode': 'always_short', 'cover_vol_mult': 18.0, 'cover_spread_mult': 20.0, 'cover_pct': 0.025, 'reentry_frac': 0.55, 'max_spread': 90}, SQUARE: {'mode': 'detect_direction', 'min_count': 1000, 'det_vol_mult': 25.0, 'det_spread_mult': 25.0, 'det_pct': 0.018, 'ema_gap_frac': 0.2, 'confirm_ticks': 3, 'min_conf_ratio': 1.0, 'cover_vol_mult': 16.0, 'cover_spread_mult': 18.0, 'cover_pct': 0.015, 'reentry_frac': 0.55, 'max_spread': 140}, CIRCLE: {'mode': 'detect_direction', 'min_count': 4000, 'det_vol_mult': 45.0, 'det_spread_mult': 40.0, 'det_pct': 0.04, 'ema_gap_frac': 0.2, 'confirm_ticks': 5, 'min_conf_ratio': 1.7, 'cover_vol_mult': 38.0, 'cover_spread_mult': 35.0, 'cover_pct': 0.035, 'reentry_frac': 0.55, 'extended_wait_mult': 2.8, 'max_spread': 120}}

    def best_bid_ask(self, order_depth: OrderDepth) -> Tuple[Optional[int], Optional[int]]:
        best_bid = max(order_depth.buy_orders.keys()) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders.keys()) if order_depth.sell_orders else None
        return (best_bid, best_ask)

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
        return {'init_mid': {}, 'last_mid': {}, 'ema_fast': {}, 'ema_slow': {}, 'vol_ema': {}, 'spread_ema': {}, 'count': {}, 'raw_dir': {}, 'raw_dir_count': {}, 'confirmed_dir': {}, 'active_dir': {}, 'entry_anchor': {}, 'exit_anchor': {}, 'wait_entry_dir': {}, 'wait_entry_ref': {}}

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
        if product not in data['init_mid']:
            data['init_mid'][product] = mid
            data['last_mid'][product] = mid
            data['ema_fast'][product] = mid
            data['ema_slow'][product] = mid
            data['vol_ema'][product] = 0.0
            data['spread_ema'][product] = max(sp, 1.0)
            data['count'][product] = 1
            data['raw_dir'][product] = 0
            data['raw_dir_count'][product] = 0
            data['confirmed_dir'][product] = 0
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

    def cover_threshold(self, data: Dict, product: str, mid: float) -> float:
        p = self.PARAMS[product]
        vol = max(float(data['vol_ema'].get(product, 1.0)), 1.0)
        sp = max(float(data['spread_ema'].get(product, 1.0)), 1.0)
        return max(p['cover_vol_mult'] * vol, p['cover_spread_mult'] * sp, p['cover_pct'] * mid)

    def detection_threshold(self, data: Dict, product: str, mid: float) -> float:
        p = self.PARAMS[product]
        vol = max(float(data['vol_ema'].get(product, 1.0)), 1.0)
        sp = max(float(data['spread_ema'].get(product, 1.0)), 1.0)
        return max(p['det_vol_mult'] * vol, p['det_spread_mult'] * sp, p['det_pct'] * mid)

    def reset_directional_grid(self, data: Dict, product: str, direction: int) -> None:
        data['active_dir'][product] = direction
        data['entry_anchor'][product] = None
        data['exit_anchor'][product] = None
        data['wait_entry_dir'][product] = 0
        data['wait_entry_ref'][product] = None

    def detect_direction(self, data: Dict, product: str, mid: float) -> int:
        if product == self.OVAL:
            if int(data['confirmed_dir'].get(product, 0)) != -1:
                data['confirmed_dir'][product] = -1
                self.reset_directional_grid(data, product, -1)
            return -1
        confirmed = int(data['confirmed_dir'].get(product, 0))
        if confirmed != 0:
            return confirmed
        p = self.PARAMS[product]
        count = int(data['count'].get(product, 0))
        if count < int(p['min_count']):
            return 0
        init_mid = float(data['init_mid'].get(product, mid))
        move = mid - init_mid
        threshold = self.detection_threshold(data, product, mid)
        ema_fast = float(data['ema_fast'].get(product, mid))
        ema_slow = float(data['ema_slow'].get(product, mid))
        ema_gap = ema_fast - ema_slow
        candidate = 0
        if abs(move) >= p['min_conf_ratio'] * threshold:
            if move > 0 and ema_gap > p['ema_gap_frac'] * threshold:
                candidate = 1
            elif move < 0 and ema_gap < -p['ema_gap_frac'] * threshold:
                candidate = -1
        if candidate == 0:
            data['raw_dir'][product] = 0
            data['raw_dir_count'][product] = 0
            return 0
        previous_raw = int(data['raw_dir'].get(product, 0))
        if candidate == previous_raw:
            data['raw_dir_count'][product] = int(data['raw_dir_count'].get(product, 0)) + 1
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

    def directional_grid_target(self, data: Dict, product: str, order_depth: OrderDepth, current_position: int, direction: int) -> int:
        best_bid, best_ask = self.best_bid_ask(order_depth)
        mid = self.mid_price(order_depth)
        if direction == 0 or mid is None or (best_bid is None and best_ask is None):
            return 0
        if int(data['active_dir'].get(product, 0)) != direction:
            self.reset_directional_grid(data, product, direction)
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
            if current_position > 0:
                return 0
            if current_position < 0:
                if entry_anchor is None:
                    entry_anchor = float(best_bid if best_bid is not None else mid)
                    data['entry_anchor'][product] = entry_anchor
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
            if current_position < 0:
                return 0
            if current_position > 0:
                if entry_anchor is None:
                    entry_anchor = float(best_ask if best_ask is not None else mid)
                    data['entry_anchor'][product] = entry_anchor
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

    def orders_to_target(self, product: str, order_depth: OrderDepth, current_position: int, target_position: int, max_spread: int) -> List[Order]:
        orders: List[Order] = []
        target_position = max(-self.POSITION_LIMIT, min(self.POSITION_LIMIT, target_position))
        delta = target_position - current_position
        if delta == 0:
            return orders
        sp = self.spread(order_depth)
        reducing_risk = abs(target_position) < abs(current_position)
        if sp is not None and sp > max_spread and (not reducing_risk):
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

    def run_with_data(self, state: TradingState, trader_data: str):
        result: Dict[str, List[Order]] = {}
        data = self.load_data(trader_data, state.timestamp)
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
            mids[product] = mid
            spreads[product] = self.spread(order_depth)
            self.update_indicators(data, product, mid, spreads[product])
        for product in self.TRADED:
            if product not in state.order_depths or product not in mids:
                continue
            current_position = state.position.get(product, 0)
            direction = self.detect_direction(data, product, mids[product])
            target = self.directional_grid_target(data=data, product=product, order_depth=state.order_depths[product], current_position=current_position, direction=direction)
            max_spread = int(self.PARAMS[product]['max_spread'])
            result[product] = self.orders_to_target(product=product, order_depth=state.order_depths[product], current_position=current_position, target_position=target, max_spread=max_spread)
        traderData = json.dumps(data, separators=(',', ':'))
        conversions = 0
        return (result, conversions, traderData)

class Trader:
    POSITION_LIMIT = 10
    OPEN_TARGETS: Dict[str, int] = {'PEBBLES_XL': +10, 'UV_VISOR_AMBER': -10, 'PANEL_4X4': +10, 'PANEL_1X2': -10, 'PEBBLES_M': -10, 'TRANSLATOR_GRAPHITE_MIST': +10, 'GALAXY_SOUNDS_SOLAR_FLAMES': +10, 'MICROCHIP_RECTANGLE': -10, 'PANEL_2X2': -10, 'GALAXY_SOUNDS_DARK_MATTER': -10, 'SLEEP_POD_SUEDE': +10, 'MICROCHIP_OVAL': -10, 'TRANSLATOR_VOID_BLUE': +10, 'UV_VISOR_ORANGE': +10, 'GALAXY_SOUNDS_BLACK_HOLES': -10, 'ROBOT_IRONING': +10, 'OXYGEN_SHAKE_GARLIC': -10, 'GALAXY_SOUNDS_SOLAR_WINDS': -10, 'OXYGEN_SHAKE_EVENING_BREATH': +10, 'SNACKPACK_STRAWBERRY': +10, 'SNACKPACK_RASPBERRY': -10, 'MICROCHIP_SQUARE': -10, 'OXYGEN_SHAKE_CHOCOLATE': -5}
    MID_TARGETS: Dict[str, int] = {'GALAXY_SOUNDS_PLANETARY_RINGS': -10, 'PEBBLES_XL': +10, 'GALAXY_SOUNDS_SOLAR_FLAMES': +10, 'PANEL_4X4': +10, 'GALAXY_SOUNDS_BLACK_HOLES': +10, 'MICROCHIP_RECTANGLE': -10, 'PANEL_1X2': -10, 'TRANSLATOR_GRAPHITE_MIST': +10, 'ROBOT_DISHES': -10, 'TRANSLATOR_ECLIPSE_CHARCOAL': +10, 'PEBBLES_M': -10, 'UV_VISOR_AMBER': -10, 'PANEL_2X2': -10, 'GALAXY_SOUNDS_DARK_MATTER': -10, 'MICROCHIP_OVAL': -10, 'TRANSLATOR_VOID_BLUE': +10, 'UV_VISOR_ORANGE': +10, 'SLEEP_POD_SUEDE': +10}
    GATE_20K: Dict[str, Tuple[int, float]] = {'PANEL_2X4': (-1, 100.0)}
    GATE_50K: Dict[str, Tuple[int, float]] = {'PANEL_1X4': (-1, 80.0), 'TRANSLATOR_SPACE_GRAY': (-1, 100.0), 'SLEEP_POD_COTTON': (+1, 100.0), 'PEBBLES_S': (-1, 100.0), 'UV_VISOR_RED': (+1, 100.0), 'TRANSLATOR_ASTRO_BLACK': (+1, 150.0)}
    LATE_TARGETS: Dict[str, int] = {'MICROCHIP_OVAL': -10, 'PEBBLES_XS': -10, 'OXYGEN_SHAKE_GARLIC': +10, 'GALAXY_SOUNDS_BLACK_HOLES': +10, 'UV_VISOR_AMBER': -10, 'PANEL_2X4': +10, 'PEBBLES_S': -10, 'UV_VISOR_RED': +10, 'SNACKPACK_PISTACHIO': -7, 'SNACKPACK_STRAWBERRY': +7, 'SLEEP_POD_LAMB_WOOL': +5, 'SNACKPACK_CHOCOLATE': -4}
    T_GATE_20 = 20000
    T_GATE_50 = 50000
    T_LATE = 100000
    PEBBLES = ['PEBBLES_XS', 'PEBBLES_S', 'PEBBLES_M', 'PEBBLES_L', 'PEBBLES_XL']
    SNACK_PAIR_1 = ('SNACKPACK_CHOCOLATE', 'SNACKPACK_VANILLA')
    SNACK_PAIR_2 = ('SNACKPACK_PISTACHIO', 'SNACKPACK_RASPBERRY')
    MR_PRODUCTS = {'ROBOT_IRONING', 'ROBOT_DISHES', 'OXYGEN_SHAKE_EVENING_BREATH', 'OXYGEN_SHAKE_CHOCOLATE'}
    PEBBLES_OVERRIDE_PRODUCTS = set(_PebblesStrategy.TRADED)
    SNACKPACK_OVERRIDE_PRODUCTS = set(_SnackpackStrategy.TRADED)
    SLEEP_POD_OVERRIDE_PRODUCTS = set(_SleepPodStrategy.PRODUCTS)
    GALAXY_OVERRIDE_PRODUCTS = set(_GalaxyStrategy.GALAXY_PRODUCTS)
    ROBOT_OVERRIDE_PRODUCTS = set(_RobotStrategy.TRADED)
    MICROCHIP_OVERRIDE_PRODUCTS = set(_MicrochipStrategy.ALL_MICROCHIPS)
    OVERRIDE_PRODUCTS = PEBBLES_OVERRIDE_PRODUCTS | SNACKPACK_OVERRIDE_PRODUCTS | SLEEP_POD_OVERRIDE_PRODUCTS | GALAXY_OVERRIDE_PRODUCTS | ROBOT_OVERRIDE_PRODUCTS | MICROCHIP_OVERRIDE_PRODUCTS

    def bid(self):
        return 15

    def load_data(self, trader_data: str) -> Dict:
        if not trader_data:
            return {'init_mid': {}, 'gate20': {}, 'gate50': {}, 'pair_mean': {}, 'pair_var': {}, 'pair_count': {}, 'last_mid': {}, 'abs_ewma': {}, '__substates': {}}
        try:
            data = json.loads(trader_data)
        except Exception:
            data = {'init_mid': {}, 'gate20': {}, 'gate50': {}, 'pair_mean': {}, 'pair_var': {}, 'pair_count': {}, 'last_mid': {}, 'abs_ewma': {}, '__substates': {}}
        data.setdefault('init_mid', {})
        data.setdefault('gate20', {})
        data.setdefault('gate50', {})
        data.setdefault('pair_mean', {})
        data.setdefault('pair_var', {})
        data.setdefault('pair_count', {})
        data.setdefault('last_mid', {})
        data.setdefault('abs_ewma', {})
        data.setdefault('__substates', {})
        return data

    def save_data(self, data: Dict) -> str:
        return json.dumps(data, separators=(',', ':'))

    def best_bid(self, order_depth: OrderDepth) -> Optional[int]:
        if not order_depth.buy_orders:
            return None
        return max(order_depth.buy_orders.keys())

    def best_ask(self, order_depth: OrderDepth) -> Optional[int]:
        if not order_depth.sell_orders:
            return None
        return min(order_depth.sell_orders.keys())

    def mid_price(self, order_depth: OrderDepth) -> Optional[float]:
        bid = self.best_bid(order_depth)
        ask = self.best_ask(order_depth)
        if bid is not None and ask is not None:
            return (bid + ask) / 2.0
        if bid is not None:
            return float(bid)
        if ask is not None:
            return float(ask)
        return None

    def spread(self, order_depth: OrderDepth) -> Optional[int]:
        bid = self.best_bid(order_depth)
        ask = self.best_ask(order_depth)
        if bid is None or ask is None:
            return None
        return ask - bid

    def store_init_mid(self, data: Dict, product: str, mid: float) -> None:
        if product not in data['init_mid']:
            data['init_mid'][product] = mid

    def update_micro_stats(self, data: Dict, product: str, mid: float) -> None:
        last = data['last_mid'].get(product)
        if last is None:
            data['last_mid'][product] = mid
            data['abs_ewma'][product] = 1.0
            return
        delta = mid - last
        prev_abs = data['abs_ewma'].get(product, abs(delta))
        data['abs_ewma'][product] = 0.95 * prev_abs + 0.05 * abs(delta)
        data['last_mid'][product] = mid

    def update_pair_stat(self, data: Dict, key: str, value: float) -> None:
        count = int(data['pair_count'].get(key, 0))
        mean = float(data['pair_mean'].get(key, value))
        var = float(data['pair_var'].get(key, 10000.0))
        alpha = 0.003
        if count == 0:
            mean = value
            var = 10000.0
        else:
            diff = value - mean
            mean = (1.0 - alpha) * mean + alpha * value
            var = (1.0 - alpha) * var + alpha * diff * diff
        data['pair_count'][key] = count + 1
        data['pair_mean'][key] = mean
        data['pair_var'][key] = max(var, 1.0)

    def eval_gate_once(self, data: Dict, gate_store: str, product: str, mid: float, gate_config: Dict[str, Tuple[int, float]]) -> None:
        if product not in gate_config:
            return
        if product in data[gate_store]:
            return
        init = data['init_mid'].get(product)
        if init is None:
            data[gate_store][product] = 0
            return
        direction, threshold = gate_config[product]
        favorable_move = direction * (mid - init)
        if favorable_move >= threshold:
            data[gate_store][product] = direction
        else:
            data[gate_store][product] = 0

    def pebble_arb_targets(self, mids: Dict[str, float], order_depths: Dict[str, OrderDepth], base_targets: Dict[str, int]) -> Dict[str, int]:
        out: Dict[str, int] = {}
        if not all((p in mids and p in order_depths for p in self.PEBBLES)):
            return out
        total = sum((mids[p] for p in self.PEBBLES))
        residual = total - 50000.0
        if abs(residual) < 12.0:
            return out
        best_product = None
        best_direction = 0
        best_edge = 0.0
        for p in self.PEBBLES:
            od = order_depths[p]
            bid = self.best_bid(od)
            ask = self.best_ask(od)
            sp = self.spread(od)
            if bid is None or ask is None or sp is None:
                continue
            fv = 50000.0 - sum((mids[q] for q in self.PEBBLES if q != p))
            tau = 0.5 * sp + 1.0
            buy_edge = fv - ask - tau
            sell_edge = bid - fv - tau
            if buy_edge > best_edge:
                best_edge = buy_edge
                best_product = p
                best_direction = +1
            if sell_edge > best_edge:
                best_edge = sell_edge
                best_product = p
                best_direction = -1
        if best_product is None or best_edge <= 0:
            return out
        base = base_targets.get(best_product, 0)
        if base != 0 and (base > 0) != (best_direction > 0):
            return out
        if base == 0:
            out[best_product] = 6 * best_direction
        else:
            out[best_product] = base
        return out

    def snack_pair_targets(self, data: Dict, mids: Dict[str, float], base_targets: Dict[str, int]) -> Dict[str, int]:
        out: Dict[str, int] = {}
        pairs = {'CV': self.SNACK_PAIR_1, 'PR': self.SNACK_PAIR_2}
        for key, pair in pairs.items():
            a, b = pair
            if a not in mids or b not in mids:
                continue
            s = mids[a] + mids[b]
            count = int(data['pair_count'].get(key, 0))
            mean = float(data['pair_mean'].get(key, s))
            var = float(data['pair_var'].get(key, 10000.0))
            sd = math.sqrt(max(var, 1.0))
            self.update_pair_stat(data, key, s)
            if count < 200:
                continue
            z = (s - mean) / sd
            if abs(z) < 2.2:
                continue
            direction = -1 if z > 0 else +1
            size = 3
            if abs(z) > 3.0:
                size = 5
            for p in pair:
                if base_targets.get(p, 0) != 0:
                    continue
                out[p] = direction * size
        return out

    def base_target_for_product(self, data: Dict, product: str, mid: Optional[float], timestamp: int) -> int:
        if timestamp >= self.T_LATE:
            return self.LATE_TARGETS.get(product, 0)
        if product in self.GATE_20K:
            if mid is not None and timestamp >= self.T_GATE_20:
                self.eval_gate_once(data, 'gate20', product, mid, self.GATE_20K)
            direction = data['gate20'].get(product)
            if direction is None:
                return 0
            return int(direction) * self.POSITION_LIMIT
        if product in self.GATE_50K:
            if timestamp < self.T_GATE_50:
                return 0
            if mid is not None:
                self.eval_gate_once(data, 'gate50', product, mid, self.GATE_50K)
            direction = data['gate50'].get(product)
            if direction is None:
                return 0
            return int(direction) * self.POSITION_LIMIT
        if timestamp < self.T_GATE_50:
            return self.OPEN_TARGETS.get(product, 0)
        return self.MID_TARGETS.get(product, 0)

    def send_to_target(self, product: str, order_depth: OrderDepth, current_pos: int, target_pos: int) -> List[Order]:
        orders: List[Order] = []
        target_pos = max(-self.POSITION_LIMIT, min(self.POSITION_LIMIT, target_pos))
        delta = target_pos - current_pos
        if delta == 0:
            return orders
        sp = self.spread(order_depth)
        reducing_risk = abs(target_pos) < abs(current_pos)
        if sp is not None and sp > 150 and (not reducing_risk):
            return orders
        if delta > 0:
            qty_needed = delta
            for ask, ask_volume in sorted(order_depth.sell_orders.items()):
                if qty_needed <= 0:
                    break
                available = -ask_volume
                if available <= 0:
                    continue
                qty = min(qty_needed, available)
                orders.append(Order(product, ask, qty))
                qty_needed -= qty
            if qty_needed > 0:
                bid = self.best_bid(order_depth)
                ask = self.best_ask(order_depth)
                if bid is not None and ask is not None and (bid + 1 < ask):
                    orders.append(Order(product, bid + 1, qty_needed))
                elif bid is not None:
                    orders.append(Order(product, bid, qty_needed))
        elif delta < 0:
            qty_needed = -delta
            for bid, bid_volume in sorted(order_depth.buy_orders.items(), reverse=True):
                if qty_needed <= 0:
                    break
                available = bid_volume
                if available <= 0:
                    continue
                qty = min(qty_needed, available)
                orders.append(Order(product, bid, -qty))
                qty_needed -= qty
            if qty_needed > 0:
                bid = self.best_bid(order_depth)
                ask = self.best_ask(order_depth)
                if bid is not None and ask is not None and (bid + 1 < ask):
                    orders.append(Order(product, ask - 1, -qty_needed))
                elif ask is not None:
                    orders.append(Order(product, ask, -qty_needed))
        return orders

    def passive_mean_reversion_orders(self, product: str, order_depth: OrderDepth, current_pos: int, base_target: int, data: Dict) -> List[Order]:
        orders: List[Order] = []
        if product not in self.MR_PRODUCTS:
            return orders
        if base_target != 0:
            return orders
        if abs(current_pos) >= 6:
            return orders
        bid = self.best_bid(order_depth)
        ask = self.best_ask(order_depth)
        if bid is None or ask is None:
            return orders
        mid = (bid + ask) / 2.0
        last = data['last_mid'].get(product)
        if last is None:
            return orders
        delta = mid - last
        avg_abs = float(data['abs_ewma'].get(product, 1.0))
        threshold = max(3.0, 2.5 * avg_abs)
        if delta > threshold and current_pos > -6:
            price = ask - 1
            if price > bid:
                qty = min(2, self.POSITION_LIMIT + current_pos)
                if qty > 0:
                    orders.append(Order(product, price, -qty))
        elif delta < -threshold and current_pos < 6:
            price = bid + 1
            if price < ask:
                qty = min(2, self.POSITION_LIMIT - current_pos)
                if qty > 0:
                    orders.append(Order(product, price, qty))
        return orders

    def override_strategy_orders(self, state: TradingState, data: Dict) -> Dict[str, List[Order]]:
        override_orders: Dict[str, List[Order]] = {product: [] for product in state.order_depths if product in self.OVERRIDE_PRODUCTS}
        substates = data.setdefault('__substates', {})
        strategies = [('pebbles', _PebblesStrategy(), self.PEBBLES_OVERRIDE_PRODUCTS), ('snackpack', _SnackpackStrategy(), self.SNACKPACK_OVERRIDE_PRODUCTS), ('sleep_pods', _SleepPodStrategy(), self.SLEEP_POD_OVERRIDE_PRODUCTS), ('galaxy', _GalaxyStrategy(), self.GALAXY_OVERRIDE_PRODUCTS), ('robot', _RobotStrategy(), self.ROBOT_OVERRIDE_PRODUCTS), ('microchip', _MicrochipStrategy(), self.MICROCHIP_OVERRIDE_PRODUCTS)]
        for key, strategy, traded_products in strategies:
            trader_data = substates.get(key, '')
            orders, _conversions, new_trader_data = strategy.run_with_data(state=state, trader_data=trader_data)
            substates[key] = new_trader_data
            for product in traded_products:
                if product in state.order_depths:
                    override_orders[product] = orders.get(product, [])
        return override_orders

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}
        data = self.load_data(state.traderData)
        override_orders = self.override_strategy_orders(state, data)
        mids: Dict[str, float] = {}
        base_targets: Dict[str, int] = {}
        for product, order_depth in state.order_depths.items():
            mid = self.mid_price(order_depth)
            if mid is not None:
                mids[product] = mid
                self.store_init_mid(data, product, mid)
            base_targets[product] = self.base_target_for_product(data=data, product=product, mid=mid, timestamp=state.timestamp)
        pebble_targets = self.pebble_arb_targets(mids=mids, order_depths=state.order_depths, base_targets=base_targets)
        snack_targets = self.snack_pair_targets(data=data, mids=mids, base_targets=base_targets)
        for product, order_depth in state.order_depths.items():
            mid = mids.get(product)
            if mid is not None:
                self.update_micro_stats(data, product, mid)
            if product in override_orders:
                result[product] = override_orders.get(product, [])
                continue
            target_pos = base_targets.get(product, 0)
            if product in pebble_targets:
                target_pos = pebble_targets[product]
            if target_pos == 0 and product in snack_targets:
                target_pos = snack_targets[product]
            current_pos = state.position.get(product, 0)
            orders = self.send_to_target(product=product, order_depth=order_depth, current_pos=current_pos, target_pos=target_pos)
            if target_pos == 0:
                orders.extend(self.passive_mean_reversion_orders(product=product, order_depth=order_depth, current_pos=current_pos, base_target=target_pos, data=data))
            result[product] = orders
        traderData = self.save_data(data)
        conversions = 0
        return (result, conversions, traderData)