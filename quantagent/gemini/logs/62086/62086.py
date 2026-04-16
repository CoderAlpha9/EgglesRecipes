from datamodel import Order, TradingState
import json
import math
import statistics


class Trader:

    PRODUCT = "TOMATOES"

    POSITION_LIMIT = 80
    MAX_ORDER_SIZE = 10

    # regime detection windows
    REGIME_WINDOW = 30
    BOLL_WINDOW = 40
    FEATURE_WINDOW = 10

    # regime thresholds
    ACF_MR_THRESH = -0.10
    ER_MR_THRESH = 0.25
    ER_TREND_THRESH = 0.30
    SLOPE_THRESH = 0.05

    # MR signal thresholds
    BAND_WIDTH = 1.40
    VI_Z_THRESH = 0.85
    PRICE_Z_THRESH = 0.35
    OU_Z_THRESH = 0.45
    MIN_SPREAD = 2

    # OU estimator settings
    OU_ALPHA = 0.05
    OU_THETA = 0.25

    # TOMATOES feature alpha weights from your code
    T_INTERCEPT = -0.0037
    T_W_AVG_SPREAD = 0.0129
    T_W_AVG_IMBALANCE = 0.1183
    T_W_MICRO_DIVERGENCE = 0.1232
    T_W_VOLUME = -0.1741

    T_AVG_SPREAD_MEAN = 13.0223
    T_AVG_SPREAD_STD = 0.1732
    T_AVG_IMBALANCE_MEAN = -0.0003
    T_AVG_IMBALANCE_STD = 0.0087
    T_MICRO_DIVERGENCE_MEAN = -0.0044
    T_MICRO_DIVERGENCE_STD = 0.0323
    T_VOLUME_MEAN = 14.3535
    T_VOLUME_STD = 7.0586

    def run(self, state: TradingState):

        result = {}
        conversions = 0

        try:
            mem = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            mem = {}

        tom = mem.get(
            "TOMATOES_STATE",
            {
                "mid_hist": [],
                "vi_hist": [],
                "feat": {
                    "spread": [],
                    "imb": [],
                    "mdiv": [],
                    "vol": []
                },
                "ou": {
                    "mu": None,
                    "var": 1.0
                }
            }
        )

        if self.PRODUCT not in state.order_depths:
            return {}, conversions, json.dumps(mem)

        od = state.order_depths[self.PRODUCT]
        if not od.buy_orders or not od.sell_orders:
            return {}, conversions, json.dumps(mem)

        best_bid = max(od.buy_orders.keys())
        best_ask = min(od.sell_orders.keys())
        best_bid_vol = od.buy_orders[best_bid]
        best_ask_vol = abs(od.sell_orders[best_ask])

        mid = (best_bid + best_ask) / 2.0
        spread = best_ask - best_bid

        total_touch = best_bid_vol + best_ask_vol
        touch_vi = (best_bid_vol - best_ask_vol) / total_touch if total_touch > 0 else 0.0

        total_bid_vol = sum(od.buy_orders.values())
        total_ask_vol = sum(-v for v in od.sell_orders.values())
        total_book_vol = total_bid_vol + total_ask_vol

        micro_price = (
            (best_bid * total_ask_vol + best_ask * total_bid_vol) / total_book_vol
            if total_book_vol > 0 else mid
        )
        micro_divergence = micro_price - mid

        market_trades = state.market_trades.get(self.PRODUCT, [])
        tick_vol = sum(t.quantity for t in market_trades)

        mid_hist = tom["mid_hist"]
        vi_hist = tom["vi_hist"]
        feat = tom["feat"]

        mid_hist.append(mid)
        vi_hist.append(touch_vi)
        feat["spread"].append(spread)
        feat["imb"].append((total_bid_vol - total_ask_vol) / total_book_vol if total_book_vol > 0 else 0.0)
        feat["mdiv"].append(micro_divergence)
        feat["vol"].append(tick_vol)

        if len(mid_hist) > 120:
            mid_hist = mid_hist[-120:]
        if len(vi_hist) > 120:
            vi_hist = vi_hist[-120:]

        for k in feat:
            if len(feat[k]) > 120:
                feat[k] = feat[k][-120:]

        tom["mid_hist"] = mid_hist
        tom["vi_hist"] = vi_hist
        tom["feat"] = feat

        position = state.position.get(self.PRODUCT, 0)
        buy_cap = self.POSITION_LIMIT - position
        sell_cap = self.POSITION_LIMIT + position

        orders = []

        if len(mid_hist) < max(self.REGIME_WINDOW, self.BOLL_WINDOW, self.FEATURE_WINDOW):
            result[self.PRODUCT] = orders
            mem["TOMATOES_STATE"] = tom
            return result, conversions, json.dumps(mem)

        # -------------------------------------------------
        # Regime detection: ACF1 + ER + slope
        # -------------------------------------------------
        regime_chunk = mid_hist[-self.REGIME_WINDOW:]
        returns = [regime_chunk[i] - regime_chunk[i - 1] for i in range(1, len(regime_chunk))]

        net_move = abs(regime_chunk[-1] - regime_chunk[0])
        path = sum(abs(r) for r in returns)
        er = net_move / path if path > 0 else 0.0

        acf1 = self._acf1(returns)
        slope = (regime_chunk[-1] - regime_chunk[0]) / self.REGIME_WINDOW

        regime = self._classify_regime(acf1, er, slope)

        # -------------------------------------------------
        # Only trade mean reversion regime
        # -------------------------------------------------
        if regime == "MEAN_REVERSION" and spread >= self.MIN_SPREAD:

            # Bollinger bands
            boll_chunk = mid_hist[-self.BOLL_WINDOW:]
            mean_price = statistics.mean(boll_chunk)
            std_price = statistics.pstdev(boll_chunk)
            std_price = std_price if std_price > 1e-9 else 1.0

            upper_band = mean_price + self.BAND_WIDTH * std_price
            lower_band = mean_price - self.BAND_WIDTH * std_price

            price_z = (mid - mean_price) / std_price

            # Touch imbalance z-score
            vi_window = vi_hist[-self.BOLL_WINDOW:]
            vi_z = self._zscore(touch_vi, vi_window)

            # OU mean reversion layer
            ou_state = tom.get("ou", {"mu": None, "var": 1.0})
            if ou_state["mu"] is None:
                ou_state["mu"] = mid

            new_mu = ou_state["mu"] + self.OU_ALPHA * (mid - ou_state["mu"])
            dev = mid - ou_state["mu"]
            new_var = ou_state["var"] + self.OU_ALPHA * ((dev ** 2) - ou_state["var"])
            new_var = max(new_var, 1e-6)

            ou_sigma = math.sqrt(new_var)
            ou_drift = self.OU_THETA * (new_mu - mid)
            ou_z = (mid - new_mu) / ou_sigma if ou_sigma > 1e-9 else 0.0

            tom["ou"] = {"mu": new_mu, "var": new_var}

            # Feature alpha fair value layer from your code
            if len(feat["spread"]) >= self.FEATURE_WINDOW:
                avg_spread = sum(feat["spread"][-self.FEATURE_WINDOW:]) / self.FEATURE_WINDOW
                avg_imb = sum(feat["imb"][-self.FEATURE_WINDOW:]) / self.FEATURE_WINDOW
                avg_mdiv = sum(feat["mdiv"][-self.FEATURE_WINDOW:]) / self.FEATURE_WINDOW
                avg_vol = sum(feat["vol"][-self.FEATURE_WINDOW:]) / self.FEATURE_WINDOW

                z_spread = (avg_spread - self.T_AVG_SPREAD_MEAN) / self.T_AVG_SPREAD_STD
                z_imb = (avg_imb - self.T_AVG_IMBALANCE_MEAN) / self.T_AVG_IMBALANCE_STD
                z_mdiv = (avg_mdiv - self.T_MICRO_DIVERGENCE_MEAN) / self.T_MICRO_DIVERGENCE_STD
                z_vol = (avg_vol - self.T_VOLUME_MEAN) / self.T_VOLUME_STD

                base_alpha = (
                    self.T_INTERCEPT
                    + self.T_W_AVG_SPREAD * z_spread
                    + self.T_W_AVG_IMBALANCE * z_imb
                    + self.T_W_MICRO_DIVERGENCE * z_mdiv
                    + self.T_W_VOLUME * z_vol
                )
                base_alpha = max(-5.0, min(5.0, base_alpha))
            else:
                base_alpha = 0.0

            # Composite fair price
            fair_price = mid + base_alpha + ou_drift

            # Score each side using multiple mean-reversion signals
            long_score = 0.0
            short_score = 0.0

            # Bollinger stretch
            if mid < lower_band:
                long_score += 2.0
            if mid > upper_band:
                short_score += 2.0

            # Price stretch from local mean
            if price_z < -self.PRICE_Z_THRESH:
                long_score += 1.0
            if price_z > self.PRICE_Z_THRESH:
                short_score += 1.0

            # Touch imbalance reversal
            if vi_z < -self.VI_Z_THRESH:
                long_score += 1.0
            if vi_z > self.VI_Z_THRESH:
                short_score += 1.0

            # OU reversion
            if ou_z < -self.OU_Z_THRESH:
                long_score += 1.0
            if ou_z > self.OU_Z_THRESH:
                short_score += 1.0

            # Small microprice confirmation
            if micro_divergence < 0:
                long_score += 0.25
            elif micro_divergence > 0:
                short_score += 0.25

            # -------------------------------------------------
            # Aggressive mean-reversion execution
            # -------------------------------------------------
            if short_score > long_score and short_score >= 2.0:
                target_qty = min(
                    self.MAX_ORDER_SIZE + int(2 * short_score),
                    sell_cap
                )

                if target_qty > 0:
                    for bid_p, bid_v in sorted(od.buy_orders.items(), key=lambda x: x[0], reverse=True):
                        if bid_p >= fair_price - 0.25 or bid_p > upper_band:
                            qty = min(bid_v, target_qty)
                            if qty > 0:
                                orders.append(Order(self.PRODUCT, bid_p, -(-qty)))
                                target_qty -= qty
                                sell_cap -= qty
                                position -= qty
                            if target_qty <= 0:
                                break

                    if target_qty > 0:
                        orders.append(Order(self.PRODUCT, int(best_bid), -(-target_qty)))
                        sell_cap -= target_qty

            elif long_score > short_score and long_score >= 2.0:
                target_qty = min(
                    self.MAX_ORDER_SIZE + int(2 * long_score),
                    buy_cap
                )

                if target_qty > 0:
                    for ask_p, ask_v in sorted(od.sell_orders.items(), key=lambda x: x[0]):
                        ask_qty = abs(ask_v)
                        if ask_p <= fair_price + 0.25 or ask_p < lower_band:
                            qty = min(ask_qty, target_qty)
                            if qty > 0:
                                orders.append(Order(self.PRODUCT, ask_p, -qty))
                                target_qty -= qty
                                buy_cap -= qty
                                position += qty
                            if target_qty <= 0:
                                break

                    if target_qty > 0:
                        orders.append(Order(self.PRODUCT, int(best_ask), -target_qty))
                        buy_cap -= target_qty

            # -------------------------------------------------
            # Passive maker layer if no strong immediate signal
            # -------------------------------------------------
            else:
                skew = (position / self.POSITION_LIMIT) * 2.5

                desired_bid = fair_price - 1.2 - skew
                desired_ask = fair_price + 1.2 - skew

                my_bid = int(math.floor(min(best_bid + 1, desired_bid)))
                my_ask = int(math.ceil(max(best_ask - 1, desired_ask)))

                if my_bid >= my_ask:
                    my_bid = my_ask - 1

                if buy_cap > 0 and my_bid < best_ask:
                    quote_buy = min(3, buy_cap)
                    orders.append(Order(self.PRODUCT, my_bid, -quote_buy))
                    buy_cap -= quote_buy

                if sell_cap > 0 and my_ask > best_bid:
                    quote_sell = min(3, sell_cap)
                    orders.append(Order(self.PRODUCT, my_ask, -(-quote_sell)))
                    sell_cap -= quote_sell

        result[self.PRODUCT] = orders
        mem["TOMATOES_STATE"] = tom
        return result, conversions, json.dumps(mem)

    def _classify_regime(self, acf1, er, slope):
        if acf1 < self.ACF_MR_THRESH and er < self.ER_MR_THRESH:
            return "MEAN_REVERSION"
        if er > self.ER_TREND_THRESH and abs(slope) > self.SLOPE_THRESH:
            return "TREND"
        return "NEUTRAL"

    def _acf1(self, rets):
        if len(rets) < 4:
            return 0.0

        r0 = rets[:-1]
        r1 = rets[1:]

        m0 = statistics.mean(r0)
        m1 = statistics.mean(r1)

        num = sum((a - m0) * (b - m1) for a, b in zip(r0, r1))
        den0 = sum((x - m0) ** 2 for x in r0)
        den1 = sum((x - m1) ** 2 for x in r1)
        denom = math.sqrt(den0 * den1)

        return num / denom if denom > 1e-9 else 0.0

    def _zscore(self, x, hist):
        if len(hist) < 5:
            return 0.0

        mu = statistics.mean(hist)
        sd = statistics.pstdev(hist)
        return (x - mu) / sd if sd > 1e-9 else 0.0