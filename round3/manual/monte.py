import numpy as np
import matplotlib.pyplot as plt

# Discretized spaces
bids = np.arange(670, 921, 1)
reserves = np.arange(670, 921, 5)

# Pre-compute win probabilities
p_res = np.array([np.sum(reserves < b) / len(reserves) for b in bids])
prob_map = dict(zip(bids, p_res))

def calculate_pnl(b, mu):
    """Calculates exact PnL for a given bid and exact lobby mean."""
    if b == 920: return 0.0
    p_win = prob_map.get(b, 0)
    
    if b > mu:
        return (920 - b) * p_win
    else:
        return ((920 - mu)**3 / (920 - b)**2) * p_win

def simulate_lobby(n_opponents, my_bid, opp_mean, opp_std, num_simulations=10000):
    """
    Runs M Monte Carlo simulations of an N-player lobby to find the true Expected Value 
    and relative Win Rate of your bid.
    """
    my_pnls = np.zeros(num_simulations)
    my_ranks = np.zeros(num_simulations)
    
    for i in range(num_simulations):
        # 1. Generate finite opponent bids (rounded to integers, clipped to bounds)
        opp_bids = np.random.normal(opp_mean, opp_std, n_opponents)
        opp_bids = np.clip(np.round(opp_bids), 670, 920)
        
        # 2. Calculate the EXACT endogenous mean including your bid
        total_bids = np.append(opp_bids, my_bid)
        mu = np.mean(total_bids)
        
        # 3. Calculate PnLs for the entire lobby
        lobby_pnls = np.array([calculate_pnl(b, mu) for b in total_bids])
        
        # 4. Extract your performance
        my_pnl = lobby_pnls[-1]
        my_pnls[i] = my_pnl
        
        # Rank 1 is highest PnL. We use argsort to find our relative placement.
        # Negative sign for descending order.
        ranks = np.argsort(-lobby_pnls) 
        my_rank = np.where(ranks == n_opponents)[0][0] + 1 
        my_ranks[i] = my_rank

    avg_pnl = np.mean(my_pnls)
    avg_rank = np.mean(my_ranks)
    win_rate = np.mean(my_ranks == 1) # How often did you outright win the lobby?
    
    return avg_pnl, avg_rank, win_rate

def grid_search_optimal_play():
    N_OPPONENTS = 500  # Adjust based on your assumption of lobby size
    OPP_MEAN = 821    # Assume competitors are "Level 1" thinkers
    OPP_STD = 20       # Assume tight clustering
    
    print(f"Simulating N={N_OPPONENTS} Lobby (Opponents: Normal({OPP_MEAN}, {OPP_STD}))\n")
    
    results = []
    test_bids = range(790, 850, 2)
    
    for b in test_bids:
        ev, rank, wr = simulate_lobby(N_OPPONENTS, b, OPP_MEAN, OPP_STD, num_simulations=5000)
        results.append((b, ev, rank, wr))
        print(f"Bid: {b:3d} | EV: {ev:5.1f} | Avg Rank: {rank:4.1f} | 1st Place Win Rate: {wr*100:4.1f}%")

    # Find maximums
    best_ev_bid = max(results, key=lambda x: x[1])
    best_wr_bid = max(results, key=lambda x: x[3])
    
    print("\n--- STRATEGIC CONCLUSION ---")
    print(f"Max Expected Value Bid: {best_ev_bid[0]} (EV: {best_ev_bid[1]:.1f})")
    print(f"Max Win Rate Bid:       {best_wr_bid[0]} (Win Rate: {best_wr_bid[3]*100:.1f}%)")

grid_search_optimal_play()