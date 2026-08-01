from datamodel import OrderDepth, TradingState, Order
from typing import List
import jsonpickle

PRODUCT = "ASH_COATED_OSMIUM"
PEPPER = "INTARIAN_PEPPER_ROOT"

POSITION_LIMIT = 80
MAX_QUOTE_SIZE = 35

EMA_ALPHA = 0.25

class _State:
    def __init__(self):
        self.ema_mid = None
        self.ema_bid = None
        self.ema_ask = None

        self.pepper_prev_ask = None

class Trader:
    
    def get_vwap(self, orders_dict: dict) -> float:
        """
        Calculates the Volume-Weighted Average Price (VWAP) across all available levels.
        """
        if not orders_dict:
            return None
            
        total_vol = sum(abs(v) for v in orders_dict.values())
        total_val = sum(p * abs(v) for p, v in orders_dict.items())
        
        return total_val / total_vol if total_vol > 0 else None

    def run(self, state: TradingState):

        result = {}
        conversions = 0

        try:
            s = jsonpickle.decode(state.traderData) if state.traderData else _State()
            if not isinstance(s, _State):
                s = _State()
        except:
            s = _State()

        if PRODUCT in state.order_depths:
            result[PRODUCT] = self._run_osmium(state, s)

        if PEPPER in state.order_depths:
            result[PEPPER] = self._run_pepper(state, s)

        traderData = jsonpickle.encode(s)
        return result, conversions, traderData

    # ─────────────────────────────────────────
    # OSMIUM (FINAL + ONE-SIDED FIX)
    # ─────────────────────────────────────────

    def _run_osmium(self, state: TradingState, s: _State) -> List[Order]:

        orders = []

        od = state.order_depths[PRODUCT]
        position = state.position.get(PRODUCT, 0)

        # ───────── EMA UPDATE ─────────

        best_bid = self.get_vwap(od.buy_orders)
        if best_bid is not None:
            if s.ema_bid is None:
                s.ema_bid = best_bid
            else:
                s.ema_bid = EMA_ALPHA * best_bid + (1 - EMA_ALPHA) * s.ema_bid

        best_ask = self.get_vwap(od.sell_orders)
        if best_ask is not None:
            if s.ema_ask is None:
                s.ema_ask = best_ask
            else:
                s.ema_ask = EMA_ALPHA * best_ask + (1 - EMA_ALPHA) * s.ema_ask

        buy_cap = POSITION_LIMIT - position
        sell_cap = POSITION_LIMIT + position

        # ───────── ONE-SIDED BOOK HANDLING ─────────

        # No BUY side → place BUY using EMA bid
        if best_bid is None:
            if s.ema_bid is not None and buy_cap > 0:
                price = int(round(s.ema_bid))
                size = min(MAX_QUOTE_SIZE, buy_cap)
                orders.append(Order(PRODUCT, price, size))
            return orders

        # No SELL side → place SELL using EMA ask
        if best_ask is None:
            if s.ema_ask is not None and sell_cap > 0:
                price = int(round(s.ema_ask))
                size = min(MAX_QUOTE_SIZE, sell_cap)
                orders.append(Order(PRODUCT, price, -size))
            return orders
            
        # ───────── NORMAL MARKET ─────────

        # Now utilizing precise float volume-weighted mid-price
        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

        # EMA mid
        if s.ema_mid is None:
            s.ema_mid = mid
        else:
            s.ema_mid = EMA_ALPHA * mid + (1 - EMA_ALPHA) * s.ema_mid

        fair = s.ema_mid
        dev = mid - fair

        # ───────── CORE EXECUTION ─────────
        # Always quote inside spread - Needs explicit rounding for submission

        bid_price = int(round(best_bid)) + 1
        ask_price = int(round(best_ask)) - 1

        if bid_price >= ask_price:
            bid_price = int(round(best_bid))
            ask_price = int(round(best_ask))

        # Inventory skew (size-based, not price-based)
        inv_ratio = position / POSITION_LIMIT

        bid_size = int(MAX_QUOTE_SIZE * (1 - max(0, inv_ratio)))
        ask_size = int(MAX_QUOTE_SIZE * (1 + min(0, inv_ratio)))

        bid_size = max(0, min(bid_size, buy_cap))
        ask_size = max(0, min(ask_size, sell_cap))

        # ───────── SELECTIVE AGGRESSION ─────────

        dir_buy = 0
        dir_sell = 0

        if dev < -3:
            dir_buy = min(20, buy_cap)

        elif dev > 3:
            dir_sell = min(20, sell_cap)

        # Avoid bad quotes in extremes
        if dev > 5:
            bid_size = 0

        if dev < -5:
            ask_size = 0

        # ───────── PLACE ORDERS ─────────

        if bid_size > 0:
            orders.append(Order(PRODUCT, bid_price, bid_size))

        if ask_size > 0:
            orders.append(Order(PRODUCT, ask_price, -ask_size))

        if dir_buy > 0:
            orders.append(Order(PRODUCT, int(round(best_ask)), dir_buy))

        if dir_sell > 0:
            orders.append(Order(PRODUCT, int(round(best_bid)), -dir_sell))

        return orders

    # ─────────────────────────────────────────
    # PEPPER 
    # ─────────────────────────────────────────

    def _run_pepper(self, state: TradingState, s: _State) -> List[Order]:

        orders = []

        od = state.order_depths[PEPPER]
        position = state.position.get(PEPPER, 0)

        if not od.buy_orders or not od.sell_orders:
            return orders

        best_bid = self.get_vwap(od.buy_orders)
        best_ask = self.get_vwap(od.sell_orders)

        buy_vol = POSITION_LIMIT - position

        prev_ask = s.pepper_prev_ask if s.pepper_prev_ask is not None else best_ask
        s.pepper_prev_ask = best_ask

        if buy_vol > 0:
            if best_ask <= prev_ask:
                orders.append(Order(PEPPER, int(round(best_ask)), buy_vol))
            else:
                orders.append(Order(PEPPER, int(round(best_bid)) + 1, buy_vol))

        if position > 0:
            orders.append(Order(PEPPER, int(round(best_ask)) + 4, -position))

        return orders