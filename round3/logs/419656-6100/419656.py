from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List, Tuple, Optional
import json
import math


class Trader:
    """
    IMC Prosperity 4 Round 3 robust trader.

    Design goals:
    - HYDROGEL_PACK: keep the proven anchored mean-reversion edge, but avoid
      Avellaneda-style always-on quoting.
    - VELVETFRUIT_EXTRACT: do NOT symmetric market-make. Trade only anchored
      mean-reversion with cost-aware profit-taking.
    - VEV options: do not blindly short all vouchers. Use dynamic cross-section
      fair value + average-cost exits. This makes options opportunistic instead
      of a PnL drag.
    """

    HYDRO = "HYDROGEL_PACK"
    VELVET = "VELVETFRUIT_EXTRACT"

    STRIKES = {
        "VEV_4000": 4000,
        "VEV_4500": 4500,
        "VEV_5000": 5000,
        "VEV_5100": 5100,
        "VEV_5200": 5200,
        "VEV_5300": 5300,
        "VEV_5400": 5400,
        "VEV_5500": 5500,
        "VEV_6000": 6000,
        "VEV_6500": 6500,
    }

    LIMIT = {
        HYDRO: 200,
        VELVET: 200,
        "VEV_4000": 300,
        "VEV_4500": 300,
        "VEV_5000": 300,
        "VEV_5100": 300,
        "VEV_5200": 300,
        "VEV_5300": 300,
        "VEV_5400": 300,
        "VEV_5500": 300,
        "VEV_6000": 300,
        "VEV_6500": 300,
    }

    # --- product-level risk caps, intentionally below/around hard limits ---
    HYDRO_CAP = 200
    VELVET_CAP = 80
    OPTION_CAP = 90
    OPTION_TOTAL_ABS_CAP = 260

    # Stable anchors from the supplied history. These are not exact-fit levels;
    # EMA and inventory skew still adapt them intraday.
    HYDRO_ANCHOR = 9991.0
    VELVET_ANCHOR = 5250.0

    # Middle strikes only. 4000/4500 are nearly pure parity; 6000/6500 are floors.
    ACTIVE_OPTIONS = ["VEV_5100", "VEV_5200", "VEV_5300", "VEV_5400"]

    # Conservative strike-specific baseline vols. Used only as a fallback / sanity
    # model; the main option fair uses dynamic cross-sectional calibration.
    BASE_VOL = {
        "VEV_5000": 0.242,
        "VEV_5100": 0.237,
        "VEV_5200": 0.243,
        "VEV_5300": 0.248,
        "VEV_5400": 0.230,
        "VEV_5500": 0.252,
    }

    def run(self, state: TradingState):
        data = self._load_state(getattr(state, "traderData", ""))

        # Update average cost before making new decisions.
        for product in [self.HYDRO, self.VELVET] + list(self.STRIKES.keys()):
            self._update_cost(product, state, data)

        result: Dict[str, List[Order]] = {}
        planned_pos = dict(getattr(state, "position", {}) or {})

        # 1) Main edge: anchored mean reversion in Hydrogel.
        self._trade_hydro(state, data, result, planned_pos)

        # 2) Secondary edge: Velvet mean reversion. No always-on MM.
        self._trade_velvet(state, data, result, planned_pos)

        # 3) Options: first manage/close inventory, then only take large relative edges.
        self._trade_options(state, data, result, planned_pos)

        # Remember last quoted prices for fallback cost tracking.
        trader_data = json.dumps(data, separators=(",", ":"))
        return result, 0, trader_data

    # ------------------------------------------------------------------
    # State and cost tracking
    # ------------------------------------------------------------------

    def _load_state(self, trader_data: str) -> Dict:
        if not trader_data:
            return {"ema": {}, "avg": {}, "last_pos": {}, "last_bid": {}, "last_ask": {}}
        try:
            data = json.loads(trader_data)
            if not isinstance(data, dict):
                raise ValueError
        except Exception:
            data = {}
        data.setdefault("ema", {})
        data.setdefault("avg", {})
        data.setdefault("last_pos", {})
        data.setdefault("last_bid", {})
        data.setdefault("last_ask", {})
        return data

    def _get_avg(self, data: Dict, product: str) -> float:
        try:
            return float(data.get("avg", {}).get(product, 0.0))
        except Exception:
            return 0.0

    def _set_avg(self, data: Dict, product: str, value: float) -> None:
        data.setdefault("avg", {})[product] = float(value)

    def _apply_fill_to_cost(self, product: str, side: str, price: float, qty: int, data: Dict) -> None:
        if qty <= 0:
            return
        old_pos = int(data.get("last_pos", {}).get(product, 0))
        avg = self._get_avg(data, product)

        if side == "BUY":
            if old_pos >= 0:
                new_pos = old_pos + qty
                avg = (avg * old_pos + price * qty) / new_pos if new_pos > 0 else 0.0
            else:
                # Buying closes short first. If it flips long, new long cost is fill price.
                new_pos = old_pos + qty
                if new_pos > 0:
                    avg = price
                elif new_pos == 0:
                    avg = 0.0
        else:  # SELL
            if old_pos <= 0:
                new_abs = -old_pos + qty
                avg = (avg * (-old_pos) + price * qty) / new_abs if new_abs > 0 else 0.0
                new_pos = old_pos - qty
            else:
                # Selling closes long first. If it flips short, new short cost is fill price.
                new_pos = old_pos - qty
                if new_pos < 0:
                    avg = price
                elif new_pos == 0:
                    avg = 0.0

        self._set_avg(data, product, avg)
        data.setdefault("last_pos", {})[product] = int(new_pos)

    def _update_cost(self, product: str, state: TradingState, data: Dict) -> None:
        """Update average entry cost from own_trades, with a fallback from position delta."""
        current_pos = int((getattr(state, "position", {}) or {}).get(product, 0))
        last_pos = int(data.get("last_pos", {}).get(product, current_pos))

        used_own_trades = False
        own_trades = (getattr(state, "own_trades", {}) or {}).get(product, [])
        for tr in own_trades:
            price = float(getattr(tr, "price", 0.0))
            qty = int(getattr(tr, "quantity", 0))
            buyer = str(getattr(tr, "buyer", ""))
            seller = str(getattr(tr, "seller", ""))
            if qty <= 0 or price <= 0:
                continue
            if buyer == "SUBMISSION":
                self._apply_fill_to_cost(product, "BUY", price, qty, data)
                used_own_trades = True
            elif seller == "SUBMISSION":
                self._apply_fill_to_cost(product, "SELL", price, qty, data)
                used_own_trades = True

        if not used_own_trades and current_pos != last_pos:
            # Fallback when own_trades are unavailable in a local runner.
            dq = current_pos - last_pos
            if dq > 0:
                px = data.get("last_bid", {}).get(product, None)
                if px is not None:
                    self._apply_fill_to_cost(product, "BUY", float(px), abs(dq), data)
            else:
                px = data.get("last_ask", {}).get(product, None)
                if px is not None:
                    self._apply_fill_to_cost(product, "SELL", float(px), abs(dq), data)

        # Ensure stored position equals the exchange-reported position.
        data.setdefault("last_pos", {})[product] = current_pos
        if current_pos == 0:
            self._set_avg(data, product, 0.0)

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    def _book(self, depth: Optional[OrderDepth]):
        if depth is None or not depth.buy_orders or not depth.sell_orders:
            return None
        bid = max(depth.buy_orders.keys())
        ask = min(depth.sell_orders.keys())
        bid_vol = abs(int(depth.buy_orders[bid]))
        ask_vol = abs(int(depth.sell_orders[ask]))
        if bid_vol <= 0 or ask_vol <= 0:
            return None
        mid = 0.5 * (bid + ask)
        micro = (bid * ask_vol + ask * bid_vol) / (bid_vol + ask_vol)
        return int(bid), bid_vol, int(ask), ask_vol, float(mid), float(micro)

    def _ema(self, data: Dict, key: str, value: float, alpha: float) -> float:
        prev = data.setdefault("ema", {}).get(key, None)
        if prev is None:
            ema = float(value)
        else:
            ema = alpha * float(value) + (1.0 - alpha) * float(prev)
        data["ema"][key] = ema
        return ema

    def _add_buy(self, product: str, price: int, qty: int,
                 result: Dict[str, List[Order]], planned_pos: Dict[str, int], data: Dict) -> int:
        if qty <= 0:
            return 0
        limit = self.LIMIT[product]
        cur = int(planned_pos.get(product, 0))
        qty = min(int(qty), limit - cur)
        if qty <= 0:
            return 0
        result.setdefault(product, []).append(Order(product, int(price), int(qty)))
        planned_pos[product] = cur + qty
        data.setdefault("last_bid", {})[product] = int(price)
        return qty

    def _add_sell(self, product: str, price: int, qty: int,
                  result: Dict[str, List[Order]], planned_pos: Dict[str, int], data: Dict) -> int:
        if qty <= 0:
            return 0
        limit = self.LIMIT[product]
        cur = int(planned_pos.get(product, 0))
        qty = min(int(qty), limit + cur)
        if qty <= 0:
            return 0
        result.setdefault(product, []).append(Order(product, int(price), -int(qty)))
        planned_pos[product] = cur - qty
        data.setdefault("last_ask", {})[product] = int(price)
        return qty

    def _edge_clip(self, edge: float, small: int, normal: int, large: int) -> int:
        if edge > 22.0:
            return large
        if edge > 14.0:
            return normal
        return small

    # ------------------------------------------------------------------
    # HYDROGEL_PACK
    # ------------------------------------------------------------------

    def _trade_hydro(self, state: TradingState, data: Dict,
                     result: Dict[str, List[Order]], planned_pos: Dict[str, int]) -> None:
        product = self.HYDRO
        b = self._book((getattr(state, "order_depths", {}) or {}).get(product))
        if b is None:
            return
        bid, bid_vol, ask, ask_vol, mid, micro = b
        spread = ask - bid

        # This is deliberately close to the profitable first submission's Hydro logic:
        # slow EMA + stable anchor + inventory skew. The main improvement is using
        # the full allowed cap only when the edge is large enough.
        ema = self._ema(data, "hydro_slow", mid, 0.010)
        fair = 0.60 * ema + 0.40 * self.HYDRO_ANCHOR

        pos = int(planned_pos.get(product, 0))
        cap = self.HYDRO_CAP

        # Inventory skew: when already long, require cheaper asks; when short,
        # require richer bids. This prevents blind maxing during trends.
        fair_adj = fair - 6.5 * (pos / cap)

        threshold = max(9.5, 0.55 * spread)
        if getattr(state, "timestamp", 0) >= 90000:
            # Slightly reduce fresh late risk, but do not force liquidation at bad prices.
            threshold += 1.5

        buy_edge = fair_adj - ask
        sell_edge = bid - fair_adj

        if pos < cap and buy_edge > threshold:
            clip = self._edge_clip(buy_edge, small=12, normal=20, large=26)
            qty = min(ask_vol, clip, cap - pos)
            self._add_buy(product, ask, qty, result, planned_pos, data)

        pos = int(planned_pos.get(product, 0))
        if pos > -cap and sell_edge > threshold:
            clip = self._edge_clip(sell_edge, small=12, normal=20, large=26)
            qty = min(bid_vol, clip, cap + pos)
            self._add_sell(product, bid, qty, result, planned_pos, data)

    # ------------------------------------------------------------------
    # VELVETFRUIT_EXTRACT
    # ------------------------------------------------------------------

    def _velvet_synthetic_fair(self, state: TradingState) -> Optional[float]:
        vals = []
        depths = getattr(state, "order_depths", {}) or {}
        # Deep ITM vouchers behave almost like S - K, so C + K is an underlying estimate.
        for product, weight in (("VEV_4000", 1.0), ("VEV_4500", 1.0)):
            b = self._book(depths.get(product))
            if b is not None:
                _, _, _, _, mid, _ = b
                vals.append((mid + self.STRIKES[product], weight))
        if not vals:
            return None
        total_w = sum(w for _, w in vals)
        return sum(v * w for v, w in vals) / total_w

    def _trade_velvet(self, state: TradingState, data: Dict,
                      result: Dict[str, List[Order]], planned_pos: Dict[str, int]) -> None:
        product = self.VELVET
        b = self._book((getattr(state, "order_depths", {}) or {}).get(product))
        if b is None:
            return
        bid, bid_vol, ask, ask_vol, mid, micro = b
        spread = ask - bid

        slow = self._ema(data, "velvet_slow", micro, 0.020)
        fast = self._ema(data, "velvet_fast", micro, 0.080)
        synth = self._velvet_synthetic_fair(state)

        # Velvet is much tighter than Hydro and can trend intraday. Use an anchor,
        # but mix it with EMA and parity-implied fair to avoid stale one-way bets.
        if synth is None:
            fair = 0.52 * slow + 0.48 * self.VELVET_ANCHOR
        else:
            fair = 0.44 * slow + 0.38 * self.VELVET_ANCHOR + 0.18 * synth

        trend = max(-12.0, min(12.0, fast - slow))
        fair += 0.05 * trend

        pos = int(planned_pos.get(product, 0))
        cap = self.VELVET_CAP
        fair_adj = fair - 4.0 * (pos / cap)
        threshold = max(6.0, 1.05 * spread)

        avg = self._get_avg(data, product)

        # Take profit first. This is the main protection against the losing
        # buy-high/sell-low behavior seen in the uploaded A-S run.
        if pos > 0 and avg > 0 and bid >= avg + 3:
            qty = min(bid_vol, 10, pos)
            self._add_sell(product, bid, qty, result, planned_pos, data)
            pos = int(planned_pos.get(product, 0))
        elif pos < 0 and avg > 0 and ask <= avg - 3:
            qty = min(ask_vol, 10, -pos)
            self._add_buy(product, ask, qty, result, planned_pos, data)
            pos = int(planned_pos.get(product, 0))

        # Fresh entries: only when deviation from anchored fair is large enough
        # to pay the full spread. No symmetric always-on market making.
        buy_edge = fair_adj - ask
        sell_edge = bid - fair_adj

        if pos < cap and buy_edge > threshold:
            qty = min(ask_vol, 10, cap - pos)
            self._add_buy(product, ask, qty, result, planned_pos, data)
        elif pos > -cap and sell_edge > threshold:
            qty = min(bid_vol, 10, cap + pos)
            self._add_sell(product, bid, qty, result, planned_pos, data)

    # ------------------------------------------------------------------
    # OPTIONS
    # ------------------------------------------------------------------

    def _norm_cdf(self, x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def _bs_call(self, s: float, k: float, t: float, sigma: float) -> float:
        intrinsic = max(s - k, 0.0)
        if t <= 0 or sigma <= 1e-9:
            return intrinsic
        vol_t = sigma * math.sqrt(t)
        if vol_t <= 1e-9:
            return intrinsic
        d1 = (math.log(s / k) + 0.5 * sigma * sigma * t) / vol_t
        d2 = d1 - vol_t
        return s * self._norm_cdf(d1) - k * self._norm_cdf(d2)

    def _option_mid_map(self, state: TradingState) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for product in self.ACTIVE_OPTIONS:
            b = self._book((getattr(state, "order_depths", {}) or {}).get(product))
            if b is not None:
                out[product] = b[4]
        return out

    def _effective_option_t(self, state: TradingState) -> float:
        # In official Round 3 the remaining life is near 5 days, while public day-2
        # replay behaves closer to 6. We do not hard fit timestamps; calibration of
        # sigma absorbs this small difference. Keep T conservative and positive.
        ts = float(getattr(state, "timestamp", 0) or 0)
        t_days = max(3.0, 5.8 - ts / 100000.0)
        return t_days / 365.0

    def _fit_sigma(self, s: float, mids: Dict[str, float], t: float) -> float:
        # One-parameter fit prevents overfitting while aligning to the current option regime.
        best_sigma = 0.25
        best_err = 10 ** 18
        for i in range(61):
            sigma = 0.15 + i * 0.005
            err = 0.0
            n = 0
            for product, mid in mids.items():
                k = self.STRIKES[product]
                # Avoid letting tiny far OTM price dominate the fit.
                w = 1.0 if mid >= 10 else 0.5
                pred = self._bs_call(s, k, t, sigma)
                err += w * (pred - mid) * (pred - mid)
                n += 1
            if n > 0 and err < best_err:
                best_err = err
                best_sigma = sigma
        return best_sigma

    def _total_abs_option_pos(self, planned_pos: Dict[str, int]) -> int:
        return sum(abs(int(planned_pos.get(p, 0))) for p in self.ACTIVE_OPTIONS)

    def _trade_options(self, state: TradingState, data: Dict,
                       result: Dict[str, List[Order]], planned_pos: Dict[str, int]) -> None:
        depths = getattr(state, "order_depths", {}) or {}
        ub = self._book(depths.get(self.VELVET))
        if ub is None:
            return
        _, _, _, _, s_mid, s_micro = ub
        s = 0.75 * s_mid + 0.25 * s_micro

        t = self._effective_option_t(state)
        mids = self._option_mid_map(state)
        if len(mids) < 3:
            return
        sigma = self._fit_sigma(s, mids, t)

        # First: close profitable option inventory. This is the missing risk control
        # from the first submission: shorts were profitable mid-run but were held to loss.
        for product in self.ACTIVE_OPTIONS:
            b = self._book(depths.get(product))
            if b is None:
                continue
            bid, bid_vol, ask, ask_vol, mid, _ = b
            pos = int(planned_pos.get(product, 0))
            avg = self._get_avg(data, product)
            if pos == 0 or avg <= 0:
                continue

            # Use larger required profit for wider/more expensive options.
            min_profit = 1.0
            if mid > 80:
                min_profit = 1.5
            if mid > 150:
                min_profit = 2.0

            if pos > 0 and bid >= avg + min_profit:
                qty = min(pos, bid_vol, 12)
                self._add_sell(product, bid, qty, result, planned_pos, data)
            elif pos < 0 and ask <= avg - min_profit:
                qty = min(-pos, ask_vol, 12)
                self._add_buy(product, ask, qty, result, planned_pos, data)

        # Second: new entries only before the late-risk zone and only if one strike
        # is far away from the calibrated cross-section.
        if getattr(state, "timestamp", 0) >= 72000:
            return

        candidates = []
        total_abs = self._total_abs_option_pos(planned_pos)
        if total_abs >= self.OPTION_TOTAL_ABS_CAP:
            return

        for product in self.ACTIVE_OPTIONS:
            b = self._book(depths.get(product))
            if b is None:
                continue
            bid, bid_vol, ask, ask_vol, mid, _ = b
            spread = ask - bid
            k = self.STRIKES[product]

            dyn_fair = self._bs_call(s, k, t, sigma)
            base_sigma = self.BASE_VOL.get(product, sigma)
            base_fair = self._bs_call(s, k, t, base_sigma)
            # Use mostly dynamic fair; baseline is only a weak prior.
            fair = 0.75 * dyn_fair + 0.25 * base_fair

            pos = int(planned_pos.get(product, 0))
            fair_adj = fair - 0.8 * (pos / self.OPTION_CAP)

            # Must beat spread comfortably. This avoids selling 5200/5300 too cheaply.
            threshold = max(3.5, 1.25 * spread + 1.2)
            buy_edge = fair_adj - ask
            sell_edge = bid - fair_adj

            if buy_edge > threshold and pos < self.OPTION_CAP:
                candidates.append((buy_edge, "BUY", product, ask, ask_vol))
            if sell_edge > threshold and pos > -self.OPTION_CAP:
                candidates.append((sell_edge, "SELL", product, bid, bid_vol))

        candidates.sort(reverse=True, key=lambda x: x[0])

        for edge, side, product, price, avail in candidates[:1]:
            pos = int(planned_pos.get(product, 0))
            remaining_total = self.OPTION_TOTAL_ABS_CAP - self._total_abs_option_pos(planned_pos)
            if remaining_total <= 0:
                break
            clip = 4 if edge < 5.0 else 6
            if side == "BUY":
                qty = min(avail, clip, self.OPTION_CAP - pos, remaining_total)
                self._add_buy(product, price, qty, result, planned_pos, data)
            else:
                qty = min(avail, clip, self.OPTION_CAP + pos, remaining_total)
                self._add_sell(product, price, qty, result, planned_pos, data)