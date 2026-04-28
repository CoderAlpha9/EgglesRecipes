import numpy as np
import pandas as pd

# ==============================================================================
# 1. INTARIAN MARKET DATA & ENGINE PARAMETERS
# ==============================================================================
market_data = {
    'AC': {'bid': 49.975, 'ask': 50.025, 'vol': 200},
    'AC_50_P': {'bid': 12.00, 'ask': 12.05, 'vol': 50},
    'AC_50_C': {'bid': 12.00, 'ask': 12.05, 'vol': 50},
    'AC_35_P': {'bid': 4.33, 'ask': 4.35, 'vol': 50},
    'AC_40_P': {'bid': 6.50, 'ask': 6.55, 'vol': 50},
    'AC_45_P': {'bid': 9.05, 'ask': 9.10, 'vol': 50},
    'AC_60_C': {'bid': 8.80, 'ask': 8.85, 'vol': 50},
    'AC_50_P_2': {'bid': 9.70, 'ask': 9.75, 'vol': 50},
    'AC_50_C_2': {'bid': 9.70, 'ask': 9.75, 'vol': 50},
    'AC_50_CO': {'bid': 22.20, 'ask': 22.30, 'vol': 50},
    'AC_40_BP': {'bid': 5.00, 'ask': 5.10, 'vol': 50},
    'AC_45_KO': {'bid': 0.15, 'ask': 0.175, 'vol': 500}
}

gui_order = list(market_data.keys())

S0 = 50.0
VOL = 2.51           
DRIFT = 0.0          
TRADING_DAYS_PER_YEAR = 252
STEPS_PER_DAY = 4
CONTRACT_MULTIPLIER = 3000

dt = 1.0 / (TRADING_DAYS_PER_YEAR * STEPS_PER_DAY)
steps_14 = 10 * STEPS_PER_DAY 
steps_21 = 15 * STEPS_PER_DAY 
drift_term = (DRIFT - 0.5 * VOL**2) * dt
diffusion_term = VOL * np.sqrt(dt)

# ==============================================================================
# 2. CORE SIMULATION & PRECOMPUTATION
# ==============================================================================
def get_path_payoffs(start_price, Z):
    n_sims = Z.shape[0]
    paths = np.zeros((n_sims, steps_21 + 1))
    paths[:, 0] = start_price
    paths[:, 1:] = start_price * np.exp(np.cumsum(drift_term + diffusion_term * Z, axis=1))
    
    S_14 = paths[:, steps_14]
    S_21 = paths[:, steps_21]
    
    payoffs = {}
    payoffs['AC'] = S_21
    payoffs['AC_50_P'] = np.maximum(50 - S_21, 0)
    payoffs['AC_50_C'] = np.maximum(S_21 - 50, 0)
    payoffs['AC_35_P'] = np.maximum(35 - S_21, 0)
    payoffs['AC_40_P'] = np.maximum(40 - S_21, 0)
    payoffs['AC_45_P'] = np.maximum(45 - S_21, 0)
    payoffs['AC_60_C'] = np.maximum(S_21 - 60, 0)
    payoffs['AC_50_P_2'] = np.maximum(50 - S_14, 0)
    payoffs['AC_50_C_2'] = np.maximum(S_14 - 50, 0)
    
    chosen_is_call = S_14 > 50
    payoffs['AC_50_CO'] = np.where(chosen_is_call, np.maximum(S_21 - 50, 0), np.maximum(50 - S_21, 0))
    payoffs['AC_40_BP'] = np.where(S_21 < 40, 10.0, 0.0)
    
    min_px = np.min(paths[:, :steps_21+1], axis=1)
    ko_payoff = np.maximum(45 - S_21, 0)
    ko_payoff[min_px < 35.0] = 0.0
    payoffs['AC_45_KO'] = ko_payoff
    
    return payoffs

def precompute_vectorized_engine(n_rounds=5000, sims_per_round=100):
    print(f"Pre-computing Vectorized Matrices for {n_rounds:,} Intarian Rounds...")
    np.random.seed(42)
    total_sims = n_rounds * sims_per_round
    
    # Generate Base Paths
    Z = np.random.standard_normal((total_sims, steps_21))
    base_payoffs = get_path_payoffs(S0, Z)
    
    # Generate Bumped Paths for Greeks (Smaller sample for speed, since Greeks are theoretical)
    Z_greeks = np.random.standard_normal((100_000, steps_21))
    bump = 0.01
    base_g = get_path_payoffs(S0, Z_greeks)
    up_g = get_path_payoffs(S0 + bump, Z_greeks)
    down_g = get_path_payoffs(S0 - bump, Z_greeks)
    
    buy_scores = {}
    sell_scores = {}
    greeks = {}
    
    for asset in gui_order:
        ask = market_data[asset]['ask']
        bid = market_data[asset]['bid']
        mult = 1 if asset == 'AC' else CONTRACT_MULTIPLIER
        
        # 1. Store the Exact PnL per Round (Array of 5000 elements)
        buy_path_pnl = (base_payoffs[asset] - ask) * mult
        sell_path_pnl = (bid - base_payoffs[asset]) * mult
        
        buy_scores[asset] = np.mean(buy_path_pnl.reshape(n_rounds, sims_per_round), axis=1)
        sell_scores[asset] = np.mean(sell_path_pnl.reshape(n_rounds, sims_per_round), axis=1)
        
        # 2. Extract Base Greeks
        p_base = base_g[asset].mean()
        p_up = up_g[asset].mean()
        p_down = down_g[asset].mean()
        
        greeks[asset] = {
            'delta': (p_up - p_down) / (2 * bump),
            'gamma': (p_up - 2 * p_base + p_down) / (bump**2)
        }
        
    return buy_scores, sell_scores, greeks, n_rounds

# ==============================================================================
# 3. VECTORIZED PORTFOLIO EVALUATOR
# ==============================================================================
def eval_portfolio(portfolio, buy_scores, sell_scores, greeks, n_rounds):
    total_scores = np.zeros(n_rounds)
    net_delta = 0
    net_gamma = 0
    
    for asset, vol in portfolio.items():
        if vol > 0:
            total_scores += vol * buy_scores[asset]
        elif vol < 0:
            total_scores += abs(vol) * sell_scores[asset]
            
        net_delta += vol * greeks[asset]['delta']
        net_gamma += vol * greeks[asset]['gamma']
        
    worst_case = np.min(total_scores)
    avg_pnl = np.mean(total_scores)
    
    # Hard Penalties for Risk Violations
    penalty_delta = abs(net_delta) * 5_000_000
    penalty_gamma = abs(min(0, net_gamma)) * 5_000_000
    
    # THE USER'S OBJECTIVE FUNCTION
    # Priority 1: Maximize Worst Case (Heavily Weighted). Priority 2: Maximize Avg PnL.
    fitness = (worst_case * 10.0) + avg_pnl - penalty_delta - penalty_gamma
    
    return fitness, worst_case, avg_pnl, net_delta, net_gamma

# ==============================================================================
# 4. HEDGED HILL-CLIMBING OPTIMIZER
# ==============================================================================
def optimize_portfolio(buy_scores, sell_scores, greeks, n_rounds, max_iterations=5000):
    print("\n--- Generating Random Valid Starting Portfolio ---")
    np.random.seed() # Pure randomness for start
    
    portfolio = {}
    for asset in gui_order:
        max_v = market_data[asset]['vol']
        portfolio[asset] = np.random.randint(-max_v, max_v + 1)
        
    best_fit, worst, avg, delta, gamma = eval_portfolio(portfolio, buy_scores, sell_scores, greeks, n_rounds)
    
    print(f"Start | Worst: {int(worst):,} | Avg: {int(avg):,} | Delta: {delta:.2f}")
    print("\nInitiating Hedged Incremental Search...\n")
    
    for i in range(max_iterations):
        improved = False
        neighbors = []
        
        # 1. Generate Neighborhood (Single Moves AND Paired Hedged Moves)
        for asset in gui_order:
            max_v = market_data[asset]['vol']
            
            for d_vol in [-1, 1]:
                if abs(portfolio[asset] + d_vol) <= max_v:
                    
                    # A. Pure Single Move
                    n1 = portfolio.copy()
                    n1[asset] += d_vol
                    neighbors.append(n1)
                    
                    # B. Hedged Move (Adjust Option + Instantly Offset with Underlying)
                    if asset != 'AC':
                        delta_shift = d_vol * greeks[asset]['delta']
                        ac_hedge_needed = -int(round(delta_shift / greeks['AC']['delta']))
                        
                        if ac_hedge_needed != 0:
                            n2 = n1.copy()
                            new_ac = n2['AC'] + ac_hedge_needed
                            # Respect Volume Limits
                            new_ac = max(-market_data['AC']['vol'], min(market_data['AC']['vol'], new_ac))
                            n2['AC'] = new_ac
                            neighbors.append(n2)
                            
        # 2. Evaluate all generated neighbors
        best_n_fit = best_fit
        best_n = None
        best_n_metrics = None
        
        for n in neighbors:
            fit, w, a, d, g = eval_portfolio(n, buy_scores, sell_scores, greeks, n_rounds)
            if fit > best_n_fit:
                best_n_fit = fit
                best_n = n
                best_n_metrics = (w, a, d, g)
                
        # 3. Step Forward if Improved
        if best_n is not None:
            portfolio = best_n
            best_fit = best_n_fit
            worst, avg, delta, gamma = best_n_metrics
            improved = True
            
            if i % 100 == 0:
                print(f"Iter {i:04d} | Fit: {int(best_fit):,} | Worst: {int(worst):,} | Avg: {int(avg):,} | Delta: {delta:.2f}")
                
        # 4. Convergence Condition
        if not improved:
            print(f"\n[!] Global Optimum reached at iteration {i}. No further improvements possible.")
            break
            
    return portfolio, worst, avg, delta, gamma

if __name__ == "__main__":
    # Run Engine
    buy_scores, sell_scores, greeks, n_rounds = precompute_vectorized_engine(n_rounds=5000, sims_per_round=100)
    final_portfolio, final_worst, final_avg, final_delta, final_gamma = optimize_portfolio(buy_scores, sell_scores, greeks, n_rounds)
    
    # Display Format
    print("\n=====================================================")
    print("              FINAL OPTIMIZED GUI ORDERS             ")
    print("=====================================================")
    
    results = []
    for asset in gui_order:
        vol = final_portfolio[asset]
        action = "PASS" if vol == 0 else ("BUY" if vol > 0 else "SELL")
        results.append({
            "Asset": asset,
            "Action": action,
            "Volume": abs(vol),
            "Net Delta": round(vol * greeks[asset]['delta'], 2)
        })
        
    df = pd.DataFrame(results)
    print(df.to_string(index=False))
    
    print("\n=====================================================")
    print("              PORTFOLIO RISK METRICS                 ")
    print("=====================================================")
    print(f"Worst Intarian Run (Min PnL): {int(final_worst):,}  <-- PRIORITY 1 MAXIMIZED")
    print(f"Expected Average Score (PnL): {int(final_avg):,}  <-- PRIORITY 2 MAXIMIZED")
    print(f"Net Portfolio Delta:          {final_delta:.4f}")
    print(f"Net Portfolio Gamma:          {final_gamma:.4f}")
    print("=====================================================")