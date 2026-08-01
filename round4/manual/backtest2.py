import numpy as np
import pandas as pd

# ==============================================================================
# 1. ENTER YOUR ORDERS HERE (Map exactly to your UI)
# ==============================================================================
# my_orders = {
#     'AC':        {'action': 'BUY', 'vol': 0},
#     'AC_50_P':   {'action': 'BUY',  'vol': 0},
#     'AC_50_C':   {'action': 'BUY',  'vol': 0},
#     'AC_35_P':   {'action': 'SELL',  'vol': 0},
#     'AC_40_P':   {'action': 'SELL',  'vol': 0},
#     'AC_45_P':   {'action': 'BUY',  'vol': 0},
#     'AC_60_C':   {'action': 'SELL',  'vol': 0},
#     'AC_50_P_2': {'action': 'BUY',  'vol': 0},
#     'AC_50_C_2': {'action': 'BUY',  'vol': 0},
#     'AC_50_CO':  {'action': 'SELL',  'vol': 0},
#     'AC_40_BP':  {'action': 'SELL',  'vol': 0},
#     'AC_45_KO':  {'action': 'BUY', 'vol': 0}
# }

my_orders = {
    'AC':        {'action': 'SELL', 'vol': 18},
    'AC_50_P':   {'action': 'BUY',  'vol': 50},
    'AC_50_C':   {'action': 'BUY',  'vol': 30},
    'AC_35_P':   {'action': 'SELL',  'vol': 0},
    'AC_40_P':   {'action': 'SELL',  'vol': 0},
    'AC_45_P':   {'action': 'BUY',  'vol': 0},
    'AC_60_C':   {'action': 'BUY',  'vol': 20},
    'AC_50_P_2': {'action': 'BUY',  'vol': 50},
    'AC_50_C_2': {'action': 'BUY',  'vol': 50},
    'AC_50_CO':  {'action': 'SELL',  'vol': 50},
    'AC_40_BP':  {'action': 'SELL',  'vol': 50},
    'AC_45_KO':  {'action': 'BUY', 'vol': 500}
}

# my_orders = {
#     'AC':        {'action': 'SELL', 'vol': 0},
#     'AC_50_P':   {'action': 'BUY',  'vol': 0},
#     'AC_50_C':   {'action': 'BUY',  'vol': 0},
#     'AC_35_P':   {'action': 'SELL',  'vol': 0},
#     'AC_40_P':   {'action': 'SELL',  'vol': 0},
#     'AC_45_P':   {'action': 'BUY',  'vol': 0},
#     'AC_60_C':   {'action': 'SELL',  'vol': 0},
#     'AC_50_P_2': {'action': 'BUY',  'vol': 50},
#     'AC_50_C_2': {'action': 'BUY',  'vol': 50},
#     'AC_50_CO':  {'action': 'SELL',  'vol': 50},
#     'AC_40_BP':  {'action': 'SELL',  'vol': 50},
#     'AC_45_KO':  {'action': 'BUY', 'vol': 500}
# }

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

dt = 1.0 / (TRADING_DAYS_PER_YEAR * STEPS_PER_DAY)
steps_14 = 10 * STEPS_PER_DAY  # 40 steps (2 weeks)
steps_21 = 15 * STEPS_PER_DAY  # 60 steps (3 weeks)
drift_term = (DRIFT - 0.5 * VOL**2) * dt
diffusion_term = VOL * np.sqrt(dt)

# ==============================================================================
# 3. CORE SIMULATION MATH
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
    payoff_as_call = np.maximum(S_21 - 50, 0)
    payoff_as_put = np.maximum(50 - S_21, 0)
    payoffs['AC_50_CO'] = np.where(chosen_is_call, payoff_as_call, payoff_as_put)
    payoffs['AC_40_BP'] = np.where(S_21 < 40, 10.0, 0.0)
    
    min_px = np.min(paths[:, :steps_21+1], axis=1)
    barrier_breached = min_px < 35.0
    ko_payoff = np.maximum(45 - S_21, 0)
    ko_payoff[barrier_breached] = 0.0
    payoffs['AC_45_KO'] = ko_payoff
    
    return payoffs

# ==============================================================================
# 4. GREEKS & PORTFOLIO ANALYSIS
# ==============================================================================
def analyze_portfolio():
    print("Calculating Theoretical Greeks (500,000 paths)...")
    np.random.seed(42)
    Z = np.random.standard_normal((1000_000, steps_21))
    
    bump = 0.01
    base = get_path_payoffs(S0, Z)
    up = get_path_payoffs(S0 + bump, Z)
    down = get_path_payoffs(S0 - bump, Z)
    
    total_theo_ev = 0
    total_delta = 0
    total_gamma = 0
    
    for asset, order in my_orders.items():
        action = order['action']
        vol = order['vol']
        if action == 'PASS' or vol == 0:
            continue
            
        ask = market_data[asset]['ask']
        bid = market_data[asset]['bid']
        
        p_base = base[asset].mean()
        p_up = up[asset].mean()
        p_down = down[asset].mean()
        
        delta = (p_up - p_down) / (2 * bump)
        gamma = (p_up - 2 * p_base + p_down) / (bump**2)
        
        if action == 'BUY':
            edge = (p_base - ask) * CONTRACT_MULTIPLIER * vol
            pos_delta = delta * vol
            pos_gamma = gamma * vol
        else: # SELL
            edge = (bid - p_base) * CONTRACT_MULTIPLIER * vol
            pos_delta = -delta * vol
            pos_gamma = -gamma * vol
            
        total_theo_ev += edge
        total_delta += pos_delta
        total_gamma += pos_gamma
        
    return total_theo_ev, total_delta, total_gamma

# ==============================================================================
# 5. STRESS TEST ENGINE
# ==============================================================================
def run_stress_test(n_rounds=10_000, sims_per_round=100):
    print(f"Running {n_rounds:,} separate Intarian Rounds (100 paths each)...\n")
    round_scores = []
    chunk_size = 1000
    
    for chunk in range(0, n_rounds, chunk_size):
        curr_chunk_size = min(chunk_size, n_rounds - chunk)
        total_sims = curr_chunk_size * sims_per_round
        
        Z = np.random.standard_normal((total_sims, steps_21))
        payoffs = get_path_payoffs(S0, Z)
        
        total_pnl_per_sim = np.zeros(total_sims)
        
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

# ==============================================================================
# 6. QUANTITATIVE CRITIQUE ENGINE
# ==============================================================================
def generate_quant_critique(theo_ev, delta, gamma, stats):
    # print("=====================================================")
    # print("              QUANTITATIVE STRATEGY CRITIQUE         ")
    # print("=====================================================")
    
    # # Delta Critique
    # print("1. DIRECTIONAL RISK (DELTA)")
    # if abs(delta) < 2.0:
    #     print(f"   [PASS] Superb Delta neutrality (Net Delta: {delta:.2f}). Strategy is successfully insulated against underlying price movements.")
    # elif abs(delta) < 15.0:
    #     print(f"   [WARN] Slight directional tilt (Net Delta: {delta:.2f}). You are exposed to a mild sequence risk if the market trends against this delta.")
    # else:
    #     direction = "LONG" if delta > 0 else "SHORT"
    #     print(f"   [FAIL] HEAVILY {direction} DELTA (Net Delta: {delta:.2f}). You are essentially making a massive directional bet on the Aether Crystal. Adjust underlying 'AC' volumes to hedge this.")
    # print("")

    # # Gamma Critique
    # print("2. VOLATILITY RISK (GAMMA)")
    # if gamma > 5.0:
    #     print(f"   [PASS] Excellent Long Gamma profile (Net Gamma: {gamma:.2f}). Violent 251% volatility swings will naturally push your delta into profitable territory.")
    # elif gamma > -5.0:
    #     print(f"   [WARN] Flat Gamma profile (Net Gamma: {gamma:.2f}). You are relying entirely on the theoretical mispricing edge rather than structural volatility mechanics.")
    # else:
    #     print(f"   [FAIL] SEVERE SHORT GAMMA (Net Gamma: {gamma:.2f}). Selling too much optionality in a 251% vol environment is a death trap. A massive market swing will accelerate your losses exponentially.")
    # print("")

    # # Survival / Backtest Critique
    # print("3. SURVIVABILITY & EXPECTATIONS")
    # if stats['win_rate'] >= 90:
    #     print(f"   [PASS] Bulletproof Edge. Win Rate: {stats['win_rate']:.2f}%. Over 100 paths, this strategy is mathematically dominant.")
    # elif stats['win_rate'] >= 75:
    #     print(f"   [WARN] Solid Edge, but vulnerable to variance. Win Rate: {stats['win_rate']:.2f}%. You will likely win, but bad sequence luck could hit you.")
    # else:
    #     print(f"   [FAIL] Coin Flip. Win Rate: {stats['win_rate']:.2f}%. The theoretical edge is being swallowed by the variance of only running 100 simulations. Do not submit this.")
    
    # print("")
    # if stats['worst'] < -1_000_000:
    #     print(f"   [CRITICAL] CATASTROPHIC TAIL RISK DETECTED. Worst case Intarian Run is {int(stats['worst']):,}. A single bad batch of 100 paths will blow up your account.")
    # else:
    #     print(f"   [PASS] Risk is contained. Worst case observed was {int(stats['worst']):,}.")
    print("=====================================================")

if __name__ == "__main__":
    theo_ev, delta, gamma = analyze_portfolio()
    stats = run_stress_test(n_rounds=10_000, sims_per_round=100)
    
    print("=====================================================")
    print("              PORTFOLIO THEORETICAL METRICS          ")
    print("=====================================================")
    print(f"Theoretical Expected PnL:    {int(theo_ev):,}")
    print(f"Net Portfolio Delta:         {delta:.4f}")
    print(f"Net Portfolio Gamma:         {gamma:.4f}")
    print("=====================================================")
    print("              BACKTEST ENGINE RESULTS                ")
    print("=====================================================")
    print(f"Expected Average Score:      {int(stats['mean']):,}")
    print(f"Win Rate (Probability > 0):  {stats['win_rate']:.2f}%")
    print(f"Score Volatility (Std Dev):  {int(stats['std_dev']):,}")
    print("-----------------------------------------------------")
    print(f"Worst Intarian Run (Min):    {int(stats['worst']):,}")
    print(f"Best Intarian Run (Max):     {int(stats['best']):,}")
    print("")
    
    generate_quant_critique(theo_ev, delta, gamma, stats)