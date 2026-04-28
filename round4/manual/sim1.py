import numpy as np
import pandas as pd

def run_aether_crystal_simulations(n_sims=1_000_000):
    # --- Environment Parameters ---
    S0 = 50.0
    VOL = 2.51           # 251% annualized volatility
    DRIFT = 0.0          # Risk-neutral
    DAYS_PER_YEAR = 252
    STEPS_PER_DAY = 4
    
    dt = 1.0 / (DAYS_PER_YEAR * STEPS_PER_DAY)
    
    steps_14 = 14 * STEPS_PER_DAY # 56 steps
    steps_21 = 21 * STEPS_PER_DAY # 84 steps
    
    # --- GBM Path Generation ---
    drift_term = (DRIFT - 0.5 * VOL**2) * dt
    diffusion_term = VOL * np.sqrt(dt)
    
    Z = np.random.standard_normal((n_sims, steps_21))
    
    paths = np.zeros((n_sims, steps_21 + 1))
    paths[:, 0] = S0
    paths[:, 1:] = S0 * np.exp(np.cumsum(drift_term + diffusion_term * Z, axis=1))
    
    S_14 = paths[:, steps_14] 
    S_21 = paths[:, steps_21] 
    
    # --- Option & Underlying Pricing Logic ---
    prices = {}
    
    # 0. The Underlying
    # The expected value of the underlying under zero drift is exactly S0 (50.0)
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
    payoff_chooser = np.where(chosen_is_call, payoff_as_call, payoff_as_put)
    prices['AC_50_CO'] = payoff_chooser.mean()
    
    # 4. Binary Put (AC_40_BP)
    prices['AC_40_BP'] = np.where(S_21 < 40, 10.0, 0.0).mean()
    
    # 5. Knock-Out Put (AC_45_KO)
    min_prices_to_21 = np.min(paths[:, :steps_21+1], axis=1)
    barrier_breached = min_prices_to_21 < 35.0
    
    payoff_ko = np.maximum(45 - S_21, 0)
    payoff_ko[barrier_breached] = 0.0
    prices['AC_45_KO'] = payoff_ko.mean()
    
    return prices

# --- Market Data with Volumes ---
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

if __name__ == "__main__":
    np.random.seed(42)
    CONTRACT_MULTIPLIER = 3000
    
    theoretical_prices = run_aether_crystal_simulations(n_sims=1_000_000)
    
    results = []
    for asset, theo_price in theoretical_prices.items():
        bid = market_data[asset]['bid']
        ask = market_data[asset]['ask']
        max_vol = market_data[asset]['vol']
        
        action = "PASS"
        edge = 0.0
        exp_pnl_max_size = 0.0
        
        if theo_price > ask:
            action = "BUY"
            edge = theo_price - ask
            exp_pnl_max_size = edge * max_vol * CONTRACT_MULTIPLIER
        elif theo_price < bid:
            action = "SELL"
            edge = bid - theo_price
            exp_pnl_max_size = edge * max_vol * CONTRACT_MULTIPLIER
            
        results.append({
            "Asset": asset,
            "Theo": round(theo_price, 3),
            "Action": action,
            "Edge": round(edge, 3),
            "Max Vol": max_vol,
            "Exp PnL (Max Size)": int(exp_pnl_max_size)
        })
        
    df = pd.DataFrame(results).sort_values(by="Exp PnL (Max Size)", ascending=False)
    print(df.to_string(index=False))