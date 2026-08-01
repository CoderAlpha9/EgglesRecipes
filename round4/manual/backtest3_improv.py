import numpy as np
import pandas as pd
import os
import time

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

LEDGER_FILE = "intarian_ledger.csv"

# ==============================================================================
# 2. CORE SIMULATION MATH & VECTORIZED PRECOMPUTATION
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
    start_time = time.time()
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
        
    print(f"Pre-computation complete in {time.time() - start_time:.2f} seconds.\n")
    return buy_scores, sell_scores, greeks, n_rounds

# ==============================================================================
# 3. HIGH-VOLUME EVALUATOR
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
    
    # Priority Tuple: 
    # 1. Maximize Floor (Minimize Max Loss)
    # 2. Maximize Gamma
    # 3. Maximize Average PnL
    fitness = (worst_case, net_gamma, avg_pnl)
    return fitness, worst_case, best_case, avg_pnl, net_delta, net_gamma

# ==============================================================================
# 4. SINGLE BATCH CYCLICAL OPTIMIZER
# ==============================================================================
def optimize_single_batch(buy_scores, sell_scores, greeks, n_rounds, max_iterations=500):
    init_portfolio = {}
    
    # Phase A: Randomize Options & Delta Neutralize via AC
    while True:
        for asset in gui_order:
            if asset != 'AC':
                max_v = market_data[asset]['vol']
                init_portfolio[asset] = np.random.randint(-max_v, max_v + 1)
        
        net_opt_delta = sum(init_portfolio[a] * greeks[a]['delta'] for a in gui_order if a != 'AC')
        ac_hedge = -int(round(net_opt_delta / greeks['AC']['delta']))
        
        if abs(ac_hedge) <= market_data['AC']['vol']:
            init_portfolio['AC'] = ac_hedge
            break
            
    best_fit, w, b, a, d, g = eval_portfolio(init_portfolio, buy_scores, sell_scores, greeks, n_rounds)
    portfolio = init_portfolio.copy()
    
    # Phase B: Cycle through Minimax optimizations while locking Delta
    for i in range(max_iterations):
        improved = False
        best_n_fit = best_fit
        best_n = None
        best_n_metrics = None
        
        for asset in gui_order:
            if asset == 'AC': 
                continue # AC is handled mechanically
                
            max_v = market_data[asset]['vol']
            for d_vol in [-1, 1]:
                if abs(portfolio[asset] + d_vol) <= max_v:
                    n1 = portfolio.copy()
                    n1[asset] += d_vol
                    
                    # Instantly Delta-Hedge the proposed move
                    delta_shift = d_vol * greeks[asset]['delta']
                    ac_hedge_needed = -int(round(delta_shift / greeks['AC']['delta']))
                    new_ac = n1['AC'] + ac_hedge_needed
                    
                    if abs(new_ac) <= market_data['AC']['vol']:
                        n1['AC'] = new_ac
                        fit, w, b, a, d, g = eval_portfolio(n1, buy_scores, sell_scores, greeks, n_rounds)
                        
                        if fit > best_n_fit:
                            best_n_fit = fit
                            best_n = n1
                            best_n_metrics = (w, b, a, d, g)
                            
        if best_n is not None:
            portfolio = best_n
            best_fit = best_n_fit
            w, b, a, d, g = best_n_metrics
            improved = True
                
        if not improved:
            break # Flatlined
            
    return best_fit, {
        'portfolio': portfolio,
        'worst': w, 'best': b, 'avg': a, 
        'delta': d, 'gamma': g
    }

# ==============================================================================
# 5. 100-BATCH GLOBAL SEARCH
# ==============================================================================
def run_global_optimization(n_restarts=100):
    buy_scores, sell_scores, greeks, n_rounds = precompute_vectorized_engine(n_rounds=5000, sims_per_round=100)
    
    print(f"Initiating {n_restarts} Independent Optimization Batches...")
    global_best_fit = (-float('inf'), -float('inf'), -float('inf'))
    global_best_metrics = None
    
    for run in range(1, n_restarts + 1):
        fit, metrics = optimize_single_batch(buy_scores, sell_scores, greeks, n_rounds, max_iterations=500)
        
        if fit > global_best_fit:
            global_best_fit = fit
            global_best_metrics = metrics
            print(f"[*] Batch {run:03d} | NEW GLOBAL BEST! Max Loss: {int(metrics['worst']):,} | Avg: {int(metrics['avg']):,} | Delta: {metrics['delta']:.2f}")
            
    return global_best_metrics, greeks

# ==============================================================================
# 6. HISTORICAL LEDGER TRACKING & COMPARISON
# ==============================================================================
def manage_ledger(current_metrics):
    curr_row = current_metrics['portfolio'].copy()
    curr_row['Max_Loss'] = current_metrics['worst']
    curr_row['Max_Profit'] = current_metrics['best']
    curr_row['Avg_PnL'] = current_metrics['avg']
    curr_row['Net_Delta'] = current_metrics['delta']
    curr_row['Net_Gamma'] = current_metrics['gamma']
    
    df_curr = pd.DataFrame([curr_row])
    historical_best = None
    
    if os.path.exists(LEDGER_FILE):
        try:
            df_hist = pd.read_csv(LEDGER_FILE)
            if not df_hist.empty:
                best_idx = df_hist['Max_Loss'].idxmax()
                historical_best = df_hist.loc[best_idx].to_dict()
        except Exception as e:
            print(f"Could not read ledger: {e}")
            
    print("\n=====================================================================================")
    print("                      HISTORICAL LEDGER COMPARISON                                   ")
    print("=====================================================================================")
    
    if historical_best:
        compare_data = {
            "Metric": ["Max Loss (Floor)", "Max Profit (Ceiling)", "Average PnL", "Net Delta", "Net Gamma"],
            "Historical Best Run": [
                f"{int(historical_best['Max_Loss']):,}",
                f"{int(historical_best['Max_Profit']):,}",
                f"{int(historical_best['Avg_PnL']):,}",
                f"{historical_best['Net_Delta']:.4f}",
                f"{historical_best['Net_Gamma']:.4f}"
            ],
            "Global Best (This Batch)": [
                f"{int(current_metrics['worst']):,}",
                f"{int(current_metrics['best']):,}",
                f"{int(current_metrics['avg']):,}",
                f"{current_metrics['delta']:.4f}",
                f"{current_metrics['gamma']:.4f}"
            ]
        }
        status = []
        for curr, hist in zip([current_metrics['worst'], current_metrics['best'], current_metrics['avg']], 
                              [historical_best['Max_Loss'], historical_best['Max_Profit'], historical_best['Avg_PnL']]):
            if curr > hist: status.append("BEAT")
            elif curr < hist: status.append("LOWER")
            else: status.append("TIE")
        status.extend(["N/A", "N/A"]) 
        compare_data["Status"] = status
        
        print(pd.DataFrame(compare_data).to_string(index=False))
        
        if current_metrics['worst'] > historical_best['Max_Loss']:
            print("\n>>> NEW ALL-TIME BEST RECORD ESTABLISHED (Max Loss Floor Improved) <<<")
    else:
        print("No historical ledger found. This run establishes the baseline record.")
        
    df_curr.to_csv(LEDGER_FILE, mode='a', header=not os.path.exists(LEDGER_FILE), index=False)
    print("=====================================================================================\n")

if __name__ == "__main__":
    np.random.seed()
    
    # 1. Execute the 100-batch global search
    global_best, out_greeks = run_global_optimization(n_restarts=100)
    
    # 2. Output Orders for GUI Execution
    print("\n=====================================================================================")
    print("                      GLOBAL BEST PORTFOLIO ACROSS 100 RUNS                          ")
    print("=====================================================================================")
    
    fin_df = []
    for asset in gui_order:
        vol = global_best['portfolio'][asset]
        action = "PASS" if vol == 0 else ("BUY" if vol > 0 else "SELL")
        fin_df.append({
            "Asset": asset, 
            "Action": action, 
            "Volume": abs(vol), 
            "Position Delta": round(vol * out_greeks[asset]['delta'], 2) if vol != 0 else 0.0
        })
    print(pd.DataFrame(fin_df).to_string(index=False))
    
    # 3. Manage historical tracking
    manage_ledger(global_best)