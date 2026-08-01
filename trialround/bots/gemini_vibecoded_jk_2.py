import json
from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List

class Trader:
    # Updated position limits
    POSITION_LIMITS = {
        "EMERALDS": 80,
        "TOMATOES": 80
    }

    def run(self, state: TradingState):
        result = {}
        conversions = 0
        
        # 1. Deserialize traderData to retain state (Memory across ticks)
        trader_state = {}
        if state.traderData != "":
            try:
                trader_state = json.loads(state.traderData)
            except Exception as e:
                print(f"Error loading traderData: {e}")
                pass

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            
            current_position = state.position.get(product, 0)
            limit = self.POSITION_LIMITS.get(product, 80)
            
            # Ensure order book has depth before calculating
            if len(order_depth.sell_orders) != 0 and len(order_depth.buy_orders) != 0:
                best_ask = min(order_depth.sell_orders.keys())
                best_bid = max(order_depth.buy_orders.keys())
                mid_price = (best_bid + best_ask) / 2
                
                # ==========================================
                # STRATEGY 1: EMERALDS (MEAN REVERSION)
                # ==========================================
                if product == "EMERALDS":
                    fair_value = 10000
                    
                    # --- Market Taking (Arbitrage) ---
                    # Instantly snipe any mispriced resting orders
                    if best_ask < fair_value:
                        buy_vol = min(-order_depth.sell_orders[best_ask], limit - current_position)
                        if buy_vol > 0:
                            orders.append(Order(product, best_ask, buy_vol))
                            current_position += buy_vol
                    
                    if best_bid > fair_value:
                        sell_vol = max(-order_depth.buy_orders[best_bid], -limit - current_position)
                        if sell_vol < 0:
                            orders.append(Order(product, best_bid, sell_vol))
                            current_position += sell_vol
                            
                    # --- Market Making (Inventory Skewing) ---
                    # Skew pricing based on position to avoid limit breaches
                    # E.g., if pos is +80, skew is 2. We lower our bids and asks to offload.
                    skew = int((current_position / limit) * 2) 
                    
                    our_bid = fair_value - 2 - skew
                    our_ask = fair_value + 2 - skew
                    
                    if current_position < limit:
                        orders.append(Order(product, int(our_bid), limit - current_position))
                    if current_position > -limit:
                        orders.append(Order(product, int(our_ask), -limit - current_position))
                        
                # ==========================================
                # STRATEGY 2: TOMATOES (EMA TRENDING)
                # ==========================================
                elif product == "TOMATOES":
                    # --- State Tracking (EMA) ---
                    ema_key = "TOMATOES_EMA"
                    if ema_key in trader_state:
                        # Alpha = 0.2 (20% weight to new price, 80% to historical)
                        ema = trader_state[ema_key]
                        ema = 0.2 * mid_price + 0.8 * ema
                    else:
                        ema = mid_price
                        
                    # Save updated EMA back to state
                    trader_state[ema_key] = ema
                    fair_value = ema
                    
                    # --- Inventory Skewing for Volatile Assets ---
                    # We use a slightly wider skew for volatile assets
                    skew = int((current_position / limit) * 3)
                    
                    our_bid = int(fair_value) - 2 - skew
                    our_ask = int(fair_value) + 2 - skew
                    
                    # --- Market Taking (Momentum/Mean Reversion to EMA) ---
                    # If the market suddenly spikes far below our EMA, we buy it up
                    if best_ask < fair_value - 3:
                        vol = min(-order_depth.sell_orders[best_ask], limit - current_position)
                        if vol > 0:
                            orders.append(Order(product, best_ask, vol))
                            current_position += vol
                            
                    # If the market spikes far above our EMA, we short it
                    if best_bid > fair_value + 3:
                        vol = max(-order_depth.buy_orders[best_bid], -limit - current_position)
                        if vol < 0:
                            orders.append(Order(product, best_bid, vol))
                            current_position += vol
                    
                    # --- Market Making (Liquidity Provision) ---
                    if current_position < limit:
                        orders.append(Order(product, our_bid, limit - current_position))
                    if current_position > -limit:
                        orders.append(Order(product, our_ask, -limit - current_position))

            result[product] = orders

        # 2. Serialize state back to a string so the engine passes it to our next iteration
        traderData = json.dumps(trader_state)
        
        return result, conversions, traderData