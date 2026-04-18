import random

def simulate_auction_engine(asset, test_price, test_volume):
    # 1. Define the raw, stale order book data exactly as it appears
    if asset == "FLAX":
        bids = {30: 30000, 29: 5000, 28: 12000, 27: 28000}
        asks = {28: 40000, 31: 20000, 32: 20000, 33: 30000}
        buyback_price = 30.0
        fees = 0.0
    elif asset == "MUSHROOM":
        bids = {20: 43000, 19: 17000, 18: 6000, 17: 5000, 16: 10000, 15: 5000, 14: 10000, 13: 7000}
        asks = {12: 20000, 13: 25000, 14: 35000, 15: 6000, 16: 5000, 18: 10000, 19: 12000} # Note: 0 volume at 17 is omitted
        buyback_price = 20.0
        fees = 0.10
    else:
        return 0, 0, 0

    # 2. Collect all unique price levels
    all_prices = set(bids.keys()).union(set(asks.keys()))
    all_prices.add(test_price)

    max_matched_volume = -1
    clearing_price = -1

    # 3. Determine the Clearing Price
    # Sorting in descending order ensures that if matched volumes tie, 
    # the algorithm naturally preserves the higher price (the tie-breaker rule)
    for p in sorted(list(all_prices), reverse=True):
        
        # Sum of bids willing to pay at least 'p'
        cum_bids = sum(vol for bp, vol in bids.items() if bp >= p)
        if test_price >= p:
            cum_bids += test_volume

        # Sum of asks willing to sell for 'p' or less
        cum_asks = sum(vol for ap, vol in asks.items() if ap <= p)

        # Exchange executes the maximum overlapping liquidity
        matched_volume = min(cum_bids, cum_asks)

        # Strictly greater (>) ensures tie-breakers favor the higher price 
        if matched_volume > max_matched_volume:
            max_matched_volume = matched_volume
            clearing_price = p

    # 4. Process Fills based on Price/Time Priority
    # If our bid is lower than the clearing price, we get nothing
    if test_price < clearing_price:
        return 0.0, clearing_price, 0
        
    total_asks_at_cp = sum(vol for ap, vol in asks.items() if ap <= clearing_price)
    
    # We are last in time priority. All bids in the book AT or ABOVE our price execute first.
    competing_bids_ahead = sum(vol for bp, vol in bids.items() if bp >= test_price)
    
    available_liquidity_for_us = max(0, total_asks_at_cp - competing_bids_ahead)
    our_fill = min(test_volume, available_liquidity_for_us)
    
    # 5. Calculate Final PnL
    pnl = our_fill * (buyback_price - clearing_price - fees)
    return pnl, clearing_price, our_fill


def run_monte_carlo(asset, max_limit, price_range, iterations):
    best_pnl = -1.0
    best_configurations = []

    for _ in range(iterations):
        # Randomly sample the parameter space without bias
        rand_price = random.choice(price_range)
        rand_volume = random.randint(0, max_limit)

        pnl, cp, fill = simulate_auction_engine(asset, rand_price, rand_volume)

        # Dynamically record the best results
        if pnl > best_pnl:
            best_pnl = pnl
            best_configurations = [(rand_price, rand_volume, cp, fill)]
        elif pnl == best_pnl and pnl > 0:
            config = (rand_price, rand_volume, cp, fill)
            if config not in best_configurations:
                best_configurations.append(config)

    print(f"=== {asset} MONTE CARLO RESULTS ({iterations:,} iterations) ===")
    print(f"Highest PnL Discovered: {best_pnl} XIRECs")
    print(f"Top Strategy Examples to achieve this:")
    for cfg in best_configurations[:3]:
        print(f" -> BUY {cfg[1]:>5} units @ {cfg[0]} (Forces CP to {cfg[2]}, gets filled for {cfg[3]})")
    print()
    return best_pnl


if __name__ == "__main__":
    # Ensure our random price ranges cover everything around the active order books
    flax_prices = list(range(27, 33))
    mushroom_prices = list(range(12, 20))

    p1 = run_monte_carlo("FLAX", 30000, flax_prices, iterations=500000)
    p2 = run_monte_carlo("MUSHROOM", 43000, mushroom_prices, iterations=500000)
    print("Net:", p1+p2)