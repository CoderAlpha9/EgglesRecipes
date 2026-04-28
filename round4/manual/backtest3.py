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
steps_14 = 10 * STEPS_PER_DAY  # 40 steps (2 weeks)
steps_21 = 15 * STEPS_PER_DAY  # 60 steps (3 weeks)
drift_term = (DRIFT - 0.5 * VOL**2) * dt
diffusion_term = VOL * np.sqrt(dt)

# ==============================================================================
# 2. CORE SIMULATION MATH (Pre-computation)
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

def precompute_unit_metrics():
    print("Pre-computing Unit Greeks & Expected Value (500,000 paths)...")
    np.random.seed(42)
    Z = np.random.standard_normal((500_000, steps_21))
    
    bump = 0.01
    base = get_path_payoffs(S0, Z)
    up = get_path_payoffs(S0 + bump, Z)
    down = get_path_payoffs(S0 - bump, Z)
    
    metrics = {}
    for asset in gui_order:
        ask = market_data[asset]['ask']
        bid = market_data[asset]['bid']
        mult = 1 if asset == 'AC' else CONTRACT_MULTIPLIER
        
        p_base = base[asset].mean()
        p_up = up[asset].mean()
        p_down = down[asset].mean()
        
        delta = (p_up - p_down) / (2 * bump)
        gamma = (p_up - 2 * p_base + p_down) / (bump**2)
        
        metrics[asset] = {
            'buy_ev': (p_base - ask) * mult,
            'sell_ev': (bid - p_base) * mult,
            'delta': delta,
            'gamma': gamma
        }
    return metrics

# ==============================================================================
# 3. ITERATIVE RANDOM START OPTIMIZER (Hill Climbing)
# ==============================================================================
def evaluate_portfolio(portfolio, metrics):
    """Scores a portfolio state. Heavily penalizes Net Delta and Negative Gamma."""
    total_ev = 0
    total_delta = 0
    total_gamma = 0
    
    for asset, vol in portfolio.items():
        if vol > 0:
            total_ev += metrics[asset]['buy_ev'] * vol
        elif vol < 0:
            total_ev += metrics[asset]['sell_ev'] * abs(vol)
            
        total_delta += vol * metrics[asset]['delta']
        total_gamma += vol * metrics[asset]['gamma']
        
    # Strict penalties to force algorithmic safety
    penalty_delta = 500000 * abs(total_delta)
    penalty_gamma = 500000 * abs(min(0, total_gamma)) 
    
    fitness = total_ev - penalty_delta - penalty_gamma
    return fitness, total_ev, total_delta, total_gamma

def iterative_hill_climber(metrics, max_iterations=5000):
    # 1. Generate a completely random valid starting portfolio
    np.random.seed() # Unseed for true randomness
    current_portfolio = {}
    for asset in gui_order:
        max_v = market_data[asset]['vol']
        current_portfolio[asset] = np.random.randint(-max_v, max_v + 1)
        
    current_fitness, current_ev, current_delta, current_gamma = evaluate_portfolio(current_portfolio, metrics)
    
    print("\n--- RANDOM STARTING POSITION ---")
    print(f"Initial EV: {int(current_ev):,}")
    print(f"Initial Delta: {current_delta:.2f}")
    print(f"Initial Gamma: {current_gamma:.2f}")
    print("Beginning incremental optimization (+-1 search)...\n")
    
    # 2. Hill Climbing Loop
    for i in range(max_iterations):
        best_neighbor = None
        best_neighbor_fitness = current_fitness
        best_ev = current_ev
        best_delta = current_delta
        best_gamma = current_gamma
        
        # Test adding +1 and -1 to every single asset
        for asset in gui_order:
            max_v = market_data[asset]['vol']
            
            # Try +1
            if current_portfolio[asset] < max_v:
                test_portfolio = current_portfolio.copy()
                test_portfolio[asset] += 1
                fit, ev, d, g = evaluate_portfolio(test_portfolio, metrics)
                
                if fit > best_neighbor_fitness:
                    best_neighbor_fitness = fit
                    best_neighbor = test_portfolio
                    best_ev, best_delta, best_gamma = ev, d, g
            
            # Try -1
            if current_portfolio[asset] > -max_v:
                test_portfolio = current_portfolio.copy()
                test_portfolio[asset] -= 1
                fit, ev, d, g = evaluate_portfolio(test_portfolio, metrics)
                
                if fit > best_neighbor_fitness:
                    best_neighbor_fitness = fit
                    best_neighbor = test_portfolio
                    best_ev, best_delta, best_gamma = ev, d, g
                    
        # If no incremental +-1 move improves the fitness, we have reached the optimal peak
        if best_neighbor is None or best_neighbor_fitness <= current_fitness + 0.001:
            print(f"Convergence reached at iteration {i}.")
            break
            
        # Move to the better portfolio state
        current_portfolio = best_neighbor
        current_fitness = best_neighbor_fitness
        current_ev, current_delta, current_gamma = best_ev, best_delta, best_gamma
        
        if i % 100 == 0:
            print(f"Iter {i:03d} | Net EV: {int(current_ev):,}\t| Delta: {current_delta:.2f}\t| Gamma: {current_gamma:.2f}")
            
    return current_portfolio, current_ev, current_delta, current_gamma

# ==============================================================================
# 4. FINAL STRESS TEST
# ==============================================================================
def run_stress_test(portfolio, n_rounds=10_000, sims_per_round=100):
    print(f"\nRunning {n_rounds:,} separate Intarian Rounds (100 paths each) to verify optimal state...\n")
    round_scores = []
    chunk_size = 1000
    
    for chunk in range(0, n_rounds, chunk_size):
        curr_chunk_size = min(chunk_size, n_rounds - chunk)
        total_sims = curr_chunk_size * sims_per_round
        
        Z = np.random.standard_normal((total_sims, steps_21))
        payoffs = get_path_payoffs(S0, Z)
        
        total_pnl_per_sim = np.zeros(total_sims)
        
        for asset, vol in portfolio.items():
            if vol == 0:
                continue
                
            ask = market_data[asset]['ask']
            bid = market_data[asset]['bid']
            sim_payoff = payoffs[asset]
            mult = 1 if asset == 'AC' else CONTRACT_MULTIPLIER
            
            if vol > 0:
                edge = sim_payoff - ask
            elif vol < 0:
                edge = bid - sim_payoff
                
            total_pnl_per_sim += edge * abs(vol) * mult
            
        pnl_reshaped = total_pnl_per_sim.reshape(curr_chunk_size, sims_per_round)
        scores = np.mean(pnl_reshaped, axis=1)
        round_scores.extend(scores.tolist())
        
    round_scores = np.array(round_scores)
    return {
        'mean': np.mean(round_scores),
        'win_rate': np.mean(round_scores > 0) * 100,
        'std_dev': np.std(round_scores),
        'worst': np.min(round_scores),
        'best': np.max(round_scores)
    }

if __name__ == "__main__":
    # 1. Prepare Engine
    unit_metrics = precompute_unit_metrics()
    
    # 2. Random Start + Iterative Optimization
    optimal_portfolio, theo_ev, net_delta, net_gamma = iterative_hill_climber(unit_metrics)
    
    # 3. Format Orders for GUI
    print("\n--- OPTIMAL GUI EXECUTION ORDERS ---")
    results = []
    for asset in gui_order:
        vol = optimal_portfolio[asset]
        action = "PASS" if vol == 0 else ("BUY" if vol > 0 else "SELL")
        results.append({
            "Asset": asset,
            "Action": action,
            "Volume": abs(vol)
        })
    df = pd.DataFrame(results)
    print(df.to_string(index=False))
    
    # 4. Stress Test the Peak
    stats = run_stress_test(optimal_portfolio)
    
    print("=====================================================")
    print("              PORTFOLIO THEORETICAL METRICS          ")
    print("=====================================================")
    print(f"Theoretical Expected PnL:    {int(theo_ev):,}")
    print(f"Net Portfolio Delta:         {net_delta:.4f}")
    print(f"Net Portfolio Gamma:         {net_gamma:.4f}")
    print("=====================================================")
    print("              BACKTEST ENGINE RESULTS                ")
    print("=====================================================")
    print(f"Expected Average Score:      {int(stats['mean']):,}")
    print(f"Win Rate (Probability > 0):  {stats['win_rate']:.2f}%")
    print(f"Score Volatility (Std Dev):  {int(stats['std_dev']):,}")
    print("-----------------------------------------------------")
    print(f"Worst Intarian Run (Min):    {int(stats['worst']):,}")
    print(f"Best Intarian Run (Max):     {int(stats['best']):,}")
    print("=====================================================")