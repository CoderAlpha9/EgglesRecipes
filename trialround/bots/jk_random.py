from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import json

class Trader:
    LIMITS = {"EMERALDS": 80, "TOMATOES": 80}

    def bid(self):
        return 15
    
    def run(self, state: TradingState):
        trading_state = {"EMERALDS_EMA": 0, "TOMATOES_EMA": 0, "epochs": 0}
        if state.traderData:
            try:
                trading_state = json.loads(state.traderData)
            except:
                pass
            
        result = {}

        for product in state.order_depths:
            orders: List[Order] = []
            curr_order_depth = state.order_depths[product]
            posn = state.position.get(product, 0)

            acceptable_price = -1
            if trading_state["epochs"] > 200:
                acceptable_price = trading_state[product+"_EMA"]
            sp, sv, bp, bv = [], [], [], []

            if len(curr_order_depth.sell_orders) > 0:
                q = posn
                for price, vol in curr_order_depth.sell_orders.items():
                    sp.append(price)
                    sv.append(vol)
                    if acceptable_price!=-1 and (price < acceptable_price) and (abs(q-vol) < self.LIMITS[product]-10):
                        orders.append(Order(product, price, -vol))
                        q -= vol

            if len(curr_order_depth.buy_orders) > 0:
                q = posn
                for price, vol in curr_order_depth.buy_orders.items():
                    bp.append(price)
                    bv.append(vol)
                    if acceptable_price!=-1 and (price > acceptable_price) and (abs(q-vol) < self.LIMITS[product]-10):
                        orders.append(Order(product, price, -vol))
                        q -= vol

            print([bp, bv, sp, sv])

            bn = sum([bp[i]*bv[i] for i in range(len(bp))])
            sn = sum([sp[i]*-sv[i] for i in range(len(sp))])
            vwap = (bn + sn) / (sum(bv) - sum(sv))
            trading_state[product+"_EMA"] = vwap * 0.1 + trading_state[product+"_EMA"] * 0.9
                    
            result[product] = orders
        
        trading_state["epochs"] += 1
    
        traderData = json.dumps(trading_state)
        conversions = 0
        return result, conversions, traderData