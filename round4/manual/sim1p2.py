import numpy as np
import pandas as pd

# --- 1. Simulation & Pricing Engine ---
def calculate_option_payoffs(S0, Z, drift_term, diffusion_term, steps_14, steps_21):
    """Helper function to calculate payoffs for a given starting price and shock array."""
    n_sims = Z.shape[0]
    
    # Generate Paths
    paths = np.zeros((n_sims, steps_21 + 1))
    paths[:, 0] = S0
    paths[:, 1:] = S0 * np.exp(np.cumsum(drift_term + diffusion_term * Z, axis=1))
    
    S_14 = paths[:, steps_14] 
    S_21 = paths[:, steps_21] 
    
    prices = {}
    
    # 0. Underlying
    prices['AC'] = S_21.mean()
    
    # 1. Vanilla Options (T+21)
    prices['AC_50_P'] = np.maximum(50 - S_21, 0).mean()
    prices['AC_50_C'] = np.maximum(S_21 - 50, 0).mean()
    prices['AC_35_P'] = np.maximum(35 - S_21, 0).mean()
    prices['AC_40_P'] = np.maximum(40 - S_21, 0).mean()
    prices['AC_45_P'] = np.maximum(45 - S_21, 0).mean()
    prices['AC_60_C'] = np.maximum(S_21 - 60, 0).mean()
    
    # 2. Vanilla Options (T+14)
    prices['AC_50_P_2'] = np.maximum(50 - S_14, 0).mean()
    prices['AC_50_C_2'] = np.maximum(S_14 - 50, 0).mean()
    
    # 3. Chooser Option (AC_50_CO)
    chosen_is_call = S_14 > 50
    payoff_as_call = np.maximum(S_21 - 50, 0)
    payoff_as_put = np.maximum(50 - S_21, 0)
    prices['AC_50_CO'] = np.where(chosen_is_call, payoff_as_call, payoff_as_put).mean()
    
    # 4. Binary Put (AC_40_BP)
    prices['AC_40_BP'] = np.where(S_21 < 40, 10.0, 0.0).mean()
    
    # 5. Knock-Out Put (AC_45_KO)
    min_prices_to_21 = np.min(paths[:, :steps_21+1], axis=1)
    barrier_breached = min_prices_to_21 < 35.0
    payoff_ko = np.maximum(45 - S_21, 0)
    payoff_ko[barrier_breached] = 0.0
    prices['AC_45_KO'] = payoff_ko.mean()
    
    return prices

def run_hedged_simulations(n_sims=500_000):
    print(f"Running {n_sims:,} bumped simulations for accurate Greeks...")
    
    # Environment
    S0_base = 50.0
    bump = 0.01          # 1 cent bump for Greeks
    VOL = 2.51           
    DRIFT = 0.0          
    DAYS_PER_YEAR = 252
    STEPS_PER_DAY = 4
    
    dt = 1.0 / (DAYS_PER_YEAR * STEPS_PER_DAY)
    steps_14 = 14 * STEPS_PER_DAY 
    steps_21 = 21 * STEPS_PER_DAY 
    
    drift_term = (DRIFT - 0.5 * VOL**2) * dt
    diffusion_term = VOL * np.sqrt(dt)
    
    # Generate ONE set of random shocks to use for all three simulations
    np.random.seed(42)
    Z = np.random.standard_normal((n_sims, steps_21))
    
    # Bump and Revalue
    base_prices = calculate_option_payoffs(S0_base, Z, drift_term, diffusion_term, steps_14, steps_21)
    up_prices = calculate_option_payoffs(S0_base + bump, Z, drift_term, diffusion_term, steps_14, steps_21)
    down_prices = calculate_option_payoffs(S0_base - bump, Z, drift_term, diffusion_term, steps_14, steps_21)
    
    greeks = {}
    for asset in base_prices.keys():
        p_base = base_prices[asset]
        p_up = up_prices[asset]
        p_down = down_prices[asset]
        
        # Central Difference approximations
        delta = (p_up - p_down) / (2 * bump)
        gamma = (p_up - 2 * p_base + p_down) / (bump ** 2)
        
        greeks[asset] = {
            'Theo': p_base,
            'Delta': delta,
            'Gamma': gamma
        }
        
    return greeks

# --- 2. Market Data ---
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

gui_order = [
    'AC', 'AC_50_P', 'AC_50_C', 'AC_35_P', 'AC_40_P', 'AC_45_P', 
    'AC_60_C', 'AC_50_P_2', 'AC_50_C_2', 'AC_50_CO', 'AC_40_BP', 'AC_45_KO'
]
# --- 3. The Evolutionary Optimizer (Gamma-Aware) ---
def optimize_portfolio(analytics, contract_multiplier=3000):
    print("Initializing Risk-Aware Package Optimizer (Delta/Gamma Constrained)...\n")
    
    assets = list(market_data.keys())
    portfolio = {asset: 0 for asset in assets}
    
    # Pre-calculate unit economics
    unit_ev = {}
    for asset in assets:
        theo = analytics[asset]['Theo']
        bid = market_data[asset]['bid']
        ask = market_data[asset]['ask']
        
        mult = 1 if asset == 'AC' else contract_multiplier
        unit_ev[asset] = {
            'buy': (theo - ask) * mult,
            'sell': (bid - theo) * mult
        }
        
    ac_delta = analytics['AC']['Delta']
    
    # Risk Parameters
    GAMMA_PENALTY_MULTIPLIER = 500000  # Massive penalty for being Short Volatility
    
    max_iterations = 5000
    for _ in range(max_iterations):
        best_move = None
        best_fitness = -float('inf')
        
        # Current Risk State
        current_gamma = sum(portfolio[a] * analytics[a]['Gamma'] for a in assets)
        
        for asset in assets:
            if asset == 'AC':
                continue # AC is our pure Delta hedge
                
            max_v = market_data[asset]['vol']
            asset_delta = analytics[asset]['Delta']
            asset_gamma = analytics[asset]['Gamma']
            
            # --- Evaluate BUYING 1 unit ---
            if portfolio[asset] < max_v:
                hedge_needed = -asset_delta / ac_delta
                ac_edge = unit_ev['AC']['buy'] if hedge_needed > 0 else unit_ev['AC']['sell']
                net_ev = unit_ev[asset]['buy'] + (abs(hedge_needed) * ac_edge)
                
                # Check Gamma Risk
                new_gamma = current_gamma + asset_gamma
                gamma_penalty = abs(new_gamma) * GAMMA_PENALTY_MULTIPLIER if new_gamma < 0 else 0
                
                fitness = net_ev - gamma_penalty
                
                if fitness > best_fitness:
                    best_fitness = fitness
                    best_move = (asset, 1)
                    
            # --- Evaluate SELLING 1 unit ---
            if portfolio[asset] > -max_v:
                hedge_needed = asset_delta / ac_delta
                ac_edge = unit_ev['AC']['buy'] if hedge_needed > 0 else unit_ev['AC']['sell']
                net_ev = unit_ev[asset]['sell'] + (abs(hedge_needed) * ac_edge)
                
                # Check Gamma Risk (Selling usually decreases Gamma)
                new_gamma = current_gamma - asset_gamma
                gamma_penalty = abs(new_gamma) * GAMMA_PENALTY_MULTIPLIER if new_gamma < 0 else 0
                
                fitness = net_ev - gamma_penalty
                
                if fitness > best_fitness:
                    best_fitness = fitness
                    best_move = (asset, -1)
                    
        # Termination: If no package increases fitness > 0, optimization is complete.
        if best_fitness <= 0.001:
            break
            
        # Execute Move
        asset_to_move, direction = best_move
        portfolio[asset_to_move] += direction

    # Final Delta Neutralization
    net_delta = sum(portfolio[a] * analytics[a]['Delta'] for a in assets if a != 'AC')
    ac_hedge = -int(round(net_delta / ac_delta))
    ac_max = market_data['AC']['vol']
    portfolio['AC'] = max(-ac_max, min(ac_max, ac_hedge))
    
    return portfolio
if __name__ == "__main__":
    # 1. Run Simulations
    analytics = run_hedged_simulations(n_sims=1000_000)
    
    # 2. Optimize
    final_portfolio = optimize_portfolio(analytics, contract_multiplier=3000)
    
    # 3. Format Output for GUI Execution
    print("--- GUI Execution Orders (Top to Bottom) ---")
    total_ev = 0
    total_delta = 0
    total_gamma = 0
    
    results = []
    for asset in gui_order:
        vol = final_portfolio[asset]
        action = "PASS"
        if vol > 0:
            action = "BUY"
        elif vol < 0:
            action = "SELL"
            
        # Calculate final stats
        theo = analytics[asset]['Theo']
        delta = analytics[asset]['Delta']
        gamma = analytics[asset]['Gamma']
        
        mult = 1 if asset == 'AC' else 3000
        edge = 0
        if vol > 0:
            edge = theo - market_data[asset]['ask']
        elif vol < 0:
            edge = market_data[asset]['bid'] - theo
            
        pnl = edge * abs(vol) * mult
        total_ev += pnl
        total_delta += vol * delta
        total_gamma += vol * gamma
        
        results.append({
            "Asset": asset,
            "Action": action,
            "Volume": abs(vol) if vol != 0 else 0,
            "Net Delta": round(vol * delta, 2) if vol != 0 else 0.00
        })
        
    df = pd.DataFrame(results)
    print(df.to_string(index=False))
    
    print("-" * 46)
    print(f"Total Expected PnL:  {int(total_ev):,}")
    print(f"Net Portfolio Delta: {total_delta:.4f} (Directionally Neutral)")
    print(f"Net Portfolio Gamma: {total_gamma:.4f} (Volatility Advantage)")