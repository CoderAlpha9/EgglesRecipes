import numpy as np
import pandas as pd

# ==============================================================================
# 1. ENTER YOUR ORDERS HERE (Map exactly to your UI)
# ==============================================================================
my_orders = {
    'AC':        {'action': 'BUY', 'vol': 0},
    'AC_50_P':   {'action': 'BUY',  'vol': 0},
    'AC_50_C':   {'action': 'SELL',  'vol': 0},
    'AC_35_P':   {'action': 'SELL',  'vol': 0},
    'AC_40_P':   {'action': 'SELL',  'vol': 0},
    'AC_45_P':   {'action': 'BUY',  'vol': 0},
    'AC_60_C':   {'action': 'SELL',  'vol': 0},
    'AC_50_P_2': {'action': 'BUY',  'vol': 50},
    'AC_50_C_2': {'action': 'BUY',  'vol': 50},
    'AC_50_CO':  {'action': 'SELL',  'vol': 50},
    'AC_40_BP':  {'action': 'SELL',  'vol': 50},
    'AC_45_KO':  {'action': 'BUY', 'vol': 500}
}

# ==============================================================================
# 2. INTARIAN MARKET DATA & ENGINE PARAMETERS
# ==============================================================================
market_data = {
    'AC': {'bid': 49.975, 'ask': 50.025},
    'AC_50_P': {'bid': 12.00, 'ask': 12.05},
    'AC_50_C': {'bid': 12.00, 'ask': 12.05},
    'AC_35_P': {'bid': 4.33, 'ask': 4.35},
    'AC_40_P': {'bid': 6.50, 'ask': 6.55},
    'AC_45_P': {'bid': 9.05, 'ask': 9.10},
    'AC_60_C': {'bid': 8.80, 'ask': 8.85},
    'AC_50_P_2': {'bid': 9.70, 'ask': 9.75},
    'AC_50_C_2': {'bid': 9.70, 'ask': 9.75},
    'AC_50_CO': {'bid': 22.20, 'ask': 22.30},
    'AC_40_BP': {'bid': 5.00, 'ask': 5.10},
    'AC_45_KO': {'bid': 0.15, 'ask': 0.175}
}

S0 = 50.0
VOL = 2.51           
DRIFT = 0.0          
TRADING_DAYS_PER_YEAR = 252
STEPS_PER_DAY = 4
CONTRACT_MULTIPLIER = 3000

# Exact Time Grid based on the latest Wiki Update
dt = 1.0 / (TRADING_DAYS_PER_YEAR * STEPS_PER_DAY)
steps_14 = 10 * STEPS_PER_DAY  # 40 steps (2 weeks)
steps_21 = 15 * STEPS_PER_DAY  # 60 steps (3 weeks)

# ==============================================================================
# 3. THE BACKTESTER ENGINE
# ==============================================================================
def simulate_round_pnl(paths):
    """Calculates the PnL for exactly 1 batch of paths (e.g., 100 simulations)."""
    n_sims = paths.shape[0]
    S_14 = paths[:, steps_14]
    S_21 = paths[:, steps_21]
    
    payoffs = {}
    
    # 1. Underlying marked to expiry
    payoffs['AC'] = S_21
    
    # 2. Vanillas T+21
    payoffs['AC_50_P'] = np.maximum(50 - S_21, 0)
    payoffs['AC_50_C'] = np.maximum(S_21 - 50, 0)
    payoffs['AC_35_P'] = np.maximum(35 - S_21, 0)
    payoffs['AC_40_P'] = np.maximum(40 - S_21, 0)
    payoffs['AC_45_P'] = np.maximum(45 - S_21, 0)
    payoffs['AC_60_C'] = np.maximum(S_21 - 60, 0)
    
    # 3. Vanillas T+14
    payoffs['AC_50_P_2'] = np.maximum(50 - S_14, 0)
    payoffs['AC_50_C_2'] = np.maximum(S_14 - 50, 0)
    
    # 4. Chooser
    chosen_is_call = S_14 > 50
    payoff_as_call = np.maximum(S_21 - 50, 0)
    payoff_as_put = np.maximum(50 - S_21, 0)
    payoffs['AC_50_CO'] = np.where(chosen_is_call, payoff_as_call, payoff_as_put)
    
    # 5. Binary
    payoffs['AC_40_BP'] = np.where(S_21 < 40, 10.0, 0.0)
    
    # 6. Knock Out
    min_px = np.min(paths[:, :steps_21+1], axis=1)
    barrier_breached = min_px < 35.0
    ko_payoff = np.maximum(45 - S_21, 0)
    ko_payoff[barrier_breached] = 0.0
    payoffs['AC_45_KO'] = ko_payoff
    
    # Evaluate Portfolio
    total_pnl_per_sim = np.zeros(n_sims)
    
    for asset, order in my_orders.items():
        action = order['action']
        vol = order['vol']
        
        if action == 'PASS' or vol == 0:
            continue
            
        ask = market_data[asset]['ask']
        bid = market_data[asset]['bid']
        sim_payoff = payoffs[asset]
        
        if action == 'BUY':
            edge = sim_payoff - ask
        elif action == 'SELL':
            edge = bid - sim_payoff
            
        total_pnl_per_sim += edge * vol * CONTRACT_MULTIPLIER
        
    return total_pnl_per_sim

def run_stress_test(n_rounds=10_000, sims_per_round=100):
    print(f"Initializing Intarian Engine Simulator...")
    print(f"Running {n_rounds:,} separate rounds of {sims_per_round} simulations each.\n")
    
    drift_term = (DRIFT - 0.5 * VOL**2) * dt
    diffusion_term = VOL * np.sqrt(dt)
    
    round_scores = []
    
    # Generate chunks to avoid RAM explosions
    chunk_size = 1000
    for chunk in range(0, n_rounds, chunk_size):
        curr_chunk_size = min(chunk_size, n_rounds - chunk)
        total_sims = curr_chunk_size * sims_per_round
        
        Z = np.random.standard_normal((total_sims, steps_21))
        paths = np.zeros((total_sims, steps_21 + 1))
        paths[:, 0] = S0
        paths[:, 1:] = S0 * np.exp(np.cumsum(drift_term + diffusion_term * Z, axis=1))
        
        pnl_array = simulate_round_pnl(paths)
        
        # Calculate the Intarian Final Score (Average PnL over the 100 paths)
        # Reshape into (curr_chunk_size, 100) and take the mean across the 100
        pnl_reshaped = pnl_array.reshape(curr_chunk_size, sims_per_round)
        scores = np.mean(pnl_reshaped, axis=1)
        round_scores.extend(scores.tolist())
        
    round_scores = np.array(round_scores)
    
    mean_score = np.mean(round_scores)
    win_rate = np.mean(round_scores > 0) * 100
    worst_case = np.min(round_scores)
    best_case = np.max(round_scores)
    std_dev = np.std(round_scores)
    
    print("=====================================================")
    print("              BACKTEST ENGINE RESULTS                ")
    print("=====================================================")
    print(f"Expected Average Score:      {int(mean_score):,}")
    print(f"Win Rate (Probability > 0):  {win_rate:.2f}%")
    print(f"Score Volatility (Std Dev):  {int(std_dev):,}")
    print("-----------------------------------------------------")
    print(f"Worst Intarian Run (Min):    {int(worst_case):,}")
    print(f"Best Intarian Run (Max):     {int(best_case):,}")
    print("=====================================================")

if __name__ == "__main__":
    np.random.seed(42) # For reproducibility 
    run_stress_test(n_rounds=10_000, sims_per_round=100)