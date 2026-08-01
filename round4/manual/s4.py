import numpy as np
import pandas as pd

# --- 1. Exact Exchange Time Mechanics ---
TRADING_DAYS_PER_YEAR = 252
STEPS_PER_DAY = 4
VOL = 2.51           
DRIFT = 0.0          

# 2 Weeks = 10 Trading Days = 40 steps
steps_14 = 10 * STEPS_PER_DAY 
# 3 Weeks = 15 Trading Days = 60 steps
steps_21 = 15 * STEPS_PER_DAY 

dt = 1.0 / (TRADING_DAYS_PER_YEAR * STEPS_PER_DAY)
drift_term = (DRIFT - 0.5 * VOL**2) * dt
diffusion_term = VOL * np.sqrt(dt)

# --- 2. Simulation & Pricing Engine ---
def calculate_option_payoffs(S0, Z):
    n_sims = Z.shape[0]
    
    paths = np.zeros((n_sims, steps_21 + 1))
    paths[:, 0] = S0
    paths[:, 1:] = S0 * np.exp(np.cumsum(drift_term + diffusion_term * Z, axis=1))
    
    S_14 = paths[:, steps_14] 
    S_21 = paths[:, steps_21] 
    
    prices = {}
    prices['AC'] = S_21.mean()
    prices['AC_50_P'] = np.maximum(50 - S_21, 0).mean()
    prices['AC_50_C'] = np.maximum(S_21 - 50, 0).mean()
    prices['AC_35_P'] = np.maximum(35 - S_21, 0).mean()
    prices['AC_40_P'] = np.maximum(40 - S_21, 0).mean()
    prices['AC_45_P'] = np.maximum(45 - S_21, 0).mean()
    prices['AC_60_C'] = np.maximum(S_21 - 60, 0).mean()
    prices['AC_50_P_2'] = np.maximum(50 - S_14, 0).mean()
    prices['AC_50_C_2'] = np.maximum(S_14 - 50, 0).mean()
    
    chosen_is_call = S_14 > 50
    payoff_as_call = np.maximum(S_21 - 50, 0)
    payoff_as_put = np.maximum(50 - S_21, 0)
    prices['AC_50_CO'] = np.where(chosen_is_call, payoff_as_call, payoff_as_put).mean()
    prices['AC_40_BP'] = np.where(S_21 < 40, 10.0, 0.0).mean()
    
    min_prices_to_21 = np.min(paths[:, :steps_21+1], axis=1)
    barrier_breached = min_prices_to_21 < 35.0
    payoff_ko = np.maximum(45 - S_21, 0)
    payoff_ko[barrier_breached] = 0.0
    prices['AC_45_KO'] = payoff_ko.mean()
    
    return prices

def run_hedged_simulations(n_sims=1000_000):
    print(f"Running {n_sims:,} bumped simulations on exact 40/60 step grid...")
    S0_base = 50.0
    bump = 0.01          
    
    np.random.seed(42)
    Z = np.random.standard_normal((n_sims, steps_21))
    
    base_prices = calculate_option_payoffs(S0_base, Z)
    up_prices = calculate_option_payoffs(S0_base + bump, Z)
    down_prices = calculate_option_payoffs(S0_base - bump, Z)
    
    greeks = {}
    for asset in base_prices.keys():
        greeks[asset] = {
            'Theo': base_prices[asset],
            'Delta': (up_prices[asset] - down_prices[asset]) / (2 * bump),
            'Gamma': (up_prices[asset] - 2 * base_prices[asset] + down_prices[asset]) / (bump ** 2)
        }
    return greeks

# --- 3. Market Data ---
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

# --- 4. The Global Optimizer ---
def optimize_portfolio(analytics):
    print("Initializing Deterministic Global Optimizer...\n")
    assets = list(market_data.keys())
    portfolio = {asset: 0 for asset in assets}
    
    # 1. Sweep the Free Money (Vanillas & Chooser)
    core_assets = ['AC_50_P', 'AC_50_C', 'AC_35_P', 'AC_40_P', 'AC_45_P', 
                   'AC_60_C', 'AC_50_P_2', 'AC_50_C_2', 'AC_50_CO']
                   
    for asset in core_assets:
        theo = analytics[asset]['Theo']
        ask = market_data[asset]['ask']
        bid = market_data[asset]['bid']
        max_v = market_data[asset]['vol']
        
        if theo > ask:
            portfolio[asset] = max_v
        elif theo < bid:
            portfolio[asset] = -max_v

    # 2. Assess Risk Capital (Banked Gamma)
    current_gamma = sum(portfolio[a] * analytics[a]['Gamma'] for a in core_assets)
    
    # 3. Optimize Binary Put (High EV, Negative Gamma)
    bp_asset = 'AC_40_BP'
    bp_theo = analytics[bp_asset]['Theo']
    bp_ask = market_data[bp_asset]['ask']
    bp_gamma = analytics[bp_asset]['Gamma']
    
    if bp_theo > bp_ask:
        if bp_gamma < 0:
            max_affordable = int(abs(current_gamma / bp_gamma))
            portfolio[bp_asset] = min(market_data[bp_asset]['vol'], max_affordable)
        else:
            portfolio[bp_asset] = market_data[bp_asset]['vol']
            
    # 4. Quarantine the Knock-Out Put
    portfolio['AC_45_KO'] = 0
    
    # 5. Perfect Delta Hedge with Underlying
    net_delta = sum(portfolio[a] * analytics[a]['Delta'] for a in assets if a != 'AC')
    ac_delta = analytics['AC']['Delta']
    ac_hedge = -int(round(net_delta / ac_delta))
    
    ac_max = market_data['AC']['vol']
    portfolio['AC'] = max(-ac_max, min(ac_max, ac_hedge))
    
    return portfolio

if __name__ == "__main__":
    analytics = run_hedged_simulations(n_sims=500_000)
    final_portfolio = optimize_portfolio(analytics)
    
    print("--- Final GUI Execution Orders (Top to Bottom) ---")
    total_ev = 0
    total_delta = 0
    total_gamma = 0
    
    results = []
    CONTRACT_MULTIPLIER = 3000 # Now applies universally to all products
    
    for asset in gui_order:
        vol = final_portfolio[asset]
        action = "PASS" if vol == 0 else ("BUY" if vol > 0 else "SELL")
            
        theo = analytics[asset]['Theo']
        delta = analytics[asset]['Delta']
        gamma = analytics[asset]['Gamma']
        
        edge = 0
        if vol > 0:
            edge = theo - market_data[asset]['ask']
        elif vol < 0:
            edge = market_data[asset]['bid'] - theo
            
        pnl = edge * abs(vol) * CONTRACT_MULTIPLIER
        total_ev += pnl
        total_delta += vol * delta
        total_gamma += vol * gamma
        
        results.append({
            "Asset": asset,
            "Action": action,
            "Volume": abs(vol),
            "Net Delta": round(vol * delta, 2) if vol != 0 else 0.00
        })
        
    df = pd.DataFrame(results)
    print(df.to_string(index=False))
    
    print("-" * 46)
    print(f"Total Expected PnL:  {int(total_ev):,}")
    print(f"Net Portfolio Delta: {total_delta:.4f} (Directionally Neutral)")
    print(f"Net Portfolio Gamma: {total_gamma:.4f} (Volatility Advantage)")