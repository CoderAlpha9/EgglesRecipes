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
    
    Z = np.random.standard_normal((total_sims, steps_21))
    base_payoffs = get_path_payoffs(S0, Z)
    
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
        
        buy_path_pnl = (base_payoffs[asset] - ask) * mult
        sell_path_pnl = (bid - base_payoffs[asset]) * mult
        
        buy_scores[asset] = np.mean(buy_path_pnl.reshape(n_rounds, sims_per_round), axis=1)
        sell_scores[asset] = np.mean(sell_path_pnl.reshape(n_rounds, sims_per_round), axis=1)
        
        p_base = base_g[asset].mean()
        p_up = up_g[asset].mean()
        p_down = down_g[asset].mean()
        
        greeks[asset] = {
            'delta': (p_up - p_down) / (2 * bump),
            'gamma': (p_up - 2 * p_base + p_down) / (bump**2)
        }
        
    return buy_scores, sell_scores, greeks, n_rounds

# ==============================================================================
# 3. PURE MINIMAX PORTFOLIO EVALUATOR
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
    best_case = np.max(total_scores)
    avg_pnl = np.mean(total_scores)
    
    # Lexicographical strict priority tuple: 
    # Python will ONLY consider index 1 if index 0 is exactly equal.
    fitness = (worst_case, -abs(net_delta), avg_pnl)
    
    return fitness, worst_case, best_case, avg_pnl, net_delta, net_gamma

# ==============================================================================
# 4. HEDGED HILL-CLIMBING OPTIMIZER
# ==============================================================================
def optimize_portfolio(buy_scores, sell_scores, greeks, n_rounds, max_iterations=3000):
    print("\n--- Generating Random Valid Starting Portfolio ---")
    np.random.seed() # Pure randomness
    
    init_portfolio = {}
    for asset in gui_order:
        max_v = market_data[asset]['vol']
        init_portfolio[asset] = np.random.randint(-max_v, max_v + 1)
        
    best_fit, init_w, init_b, init_a, init_d, init_g = eval_portfolio(init_portfolio, buy_scores, sell_scores, greeks, n_rounds)
    
    # Store initial metrics for output
    initial_metrics = {
        'portfolio': init_portfolio.copy(),
        'worst': init_w, 'best': init_b, 'avg': init_a, 
        'delta': init_d, 'gamma': init_g
    }
    
    print(f"Random Start  -> Max Loss (Floor): {int(init_w):,} | Avg: {int(init_a):,} | Delta: {init_d:.2f}")
    print("Initiating Pure Minimax Optimization...\n")
    
    portfolio = init_portfolio.copy()
    
    for i in range(max_iterations):
        improved = False
        neighbors = []
        
        # Search Neighborhood
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
                            # Respect limits
                            new_ac = max(-market_data['AC']['vol'], min(market_data['AC']['vol'], new_ac))
                            n2['AC'] = new_ac
                            neighbors.append(n2)
                            
        # Evaluate all generated neighbors
        best_n_fit = best_fit
        best_n = None
        best_n_metrics = None
        
        for n in neighbors:
            fit, w, b, a, d, g = eval_portfolio(n, buy_scores, sell_scores, greeks, n_rounds)
            # Tuple comparison handles the strict priority automatically
            if fit > best_n_fit:
                best_n_fit = fit
                best_n = n
                best_n_metrics = (w, b, a, d, g)
                
        # Step Forward if Improved
        if best_n is not None:
            portfolio = best_n
            best_fit = best_n_fit
            worst, best, avg, delta, gamma = best_n_metrics
            improved = True
            
            if i % 50 == 0:
                print(f"Iter {i:04d} | Max Loss (Floor): {int(worst):,} | Delta: {delta:.2f} | Avg: {int(avg):,}")
                
        if not improved:
            print(f"\n[!] Mathematical Peak Reached at iteration {i}.")
            break
            
    final_metrics = {
        'portfolio': portfolio,
        'worst': worst, 'best': best, 'avg': avg, 
        'delta': delta, 'gamma': gamma
    }
    
    return initial_metrics, final_metrics

if __name__ == "__main__":
    # Run Engine
    buy_scores, sell_scores, greeks, n_rounds = precompute_vectorized_engine(n_rounds=5000, sims_per_round=100)
    init_metrics, fin_metrics = optimize_portfolio(buy_scores, sell_scores, greeks, n_rounds)
    
    # ---------------------------------------------------------
    # OUTPUT FORMATTING
    # ---------------------------------------------------------
    print("\n=====================================================================================")
    print("                              PORTFOLIO EVOLUTION REPORT                             ")
    print("=====================================================================================")
    
    print("\n[ INITIAL RANDOM PORTFOLIO ]")
    init_df = []
    for asset in gui_order:
        vol = init_metrics['portfolio'][asset]
        action = "PASS" if vol == 0 else ("BUY" if vol > 0 else "SELL")
        init_df.append({"Asset": asset, "Action": action, "Volume": abs(vol)})
    print(pd.DataFrame(init_df).to_string(index=False))
    
    print("\n[ FINAL OPTIMIZED PORTFOLIO (Minimax Peak) ]")
    fin_df = []
    for asset in gui_order:
        vol = fin_metrics['portfolio'][asset]
        action = "PASS" if vol == 0 else ("BUY" if vol > 0 else "SELL")
        fin_df.append({"Asset": asset, "Action": action, "Volume": abs(vol)})
    print(pd.DataFrame(fin_df).to_string(index=False))

    print("\n=====================================================================================")
    print("                                PERFORMANCE METRICS                                  ")
    print("=====================================================================================")
    
    # Format comparison table
    compare_data = {
        "Metric": [
            "Max Loss (Worst Case Floor)", 
            "Max Profit (Best Case Ceiling)", 
            "Average Expected PnL", 
            "Net Portfolio Delta", 
            "Net Portfolio Gamma"
        ],
        "Random Start": [
            f"{int(init_metrics['worst']):,}",
            f"{int(init_metrics['best']):,}",
            f"{int(init_metrics['avg']):,}",
            f"{init_metrics['delta']:.4f}",
            f"{init_metrics['gamma']:.4f}"
        ],
        "Optimized Final": [
            f"{int(fin_metrics['worst']):,}",
            f"{int(fin_metrics['best']):,}",
            f"{int(fin_metrics['avg']):,}",
            f"{fin_metrics['delta']:.4f}",
            f"{fin_metrics['gamma']:.4f}"
        ]
    }
    
    df_compare = pd.DataFrame(compare_data)
    print(df_compare.to_string(index=False))
    print("=====================================================================================\n")