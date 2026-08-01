import numpy as np
import pandas as pd

def build_delta_neutral_book(n_sims=1_000_000):
    # ==============================================================================
    # 1. ENVIRONMENT & MARKET DATA
    # ==============================================================================
    S0 = 50.0
    r = 0.0
    vol = 2.51
    days_per_year = 252
    steps_per_day = 4
    
    dt = 1.0 / (days_per_year * steps_per_day)
    steps_14 = 40  
    steps_21 = 60  
    
    drift = (r - 0.5 * vol**2) * dt
    diffusion = vol * np.sqrt(dt)
    
    market_data = {
        'AC_50_P':   {'bid': 12.00, 'ask': 12.05, 'max_vol': 50},
        'AC_50_C':   {'bid': 12.00, 'ask': 12.05, 'max_vol': 50},
        'AC_35_P':   {'bid': 4.33,  'ask': 4.35,  'max_vol': 50},
        'AC_40_P':   {'bid': 6.50,  'ask': 6.55,  'max_vol': 50},
        'AC_45_P':   {'bid': 9.05,  'ask': 9.10,  'max_vol': 50},
        'AC_60_C':   {'bid': 8.80,  'ask': 8.85,  'max_vol': 50},
        'AC_50_P_2': {'bid': 9.70,  'ask': 9.75,  'max_vol': 50},
        'AC_50_C_2': {'bid': 9.70,  'ask': 9.75,  'max_vol': 50},
        'AC_50_CO':  {'bid': 22.20, 'ask': 22.30, 'max_vol': 50},
        'AC_40_BP':  {'bid': 5.00,  'ask': 5.10,  'max_vol': 50},
        'AC_45_KO':  {'bid': 0.15,  'ask': 0.175, 'max_vol': 500}
    }

    # ==============================================================================
    # 2. PATH GENERATION & PAYOFF CALCULATION
    # ==============================================================================
    np.random.seed(42) # Common Random Numbers for stable Greeks
    Z = np.random.standard_normal((n_sims, steps_21))
    
    def calculate_payoffs(start_price):
        paths = np.zeros((n_sims, steps_21 + 1))
        paths[:, 0] = start_price
        paths[:, 1:] = start_price * np.exp(np.cumsum(drift + diffusion * Z, axis=1))
        
        S_14 = paths[:, steps_14]
        S_21 = paths[:, steps_21]
        
        payoffs = {}
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
        
        min_prices = np.min(paths[:, :steps_21+1], axis=1)
        ko_payoff = np.maximum(45 - S_21, 0)
        ko_payoff[min_prices < 35.0] = 0.0
        payoffs['AC_45_KO'] = ko_payoff
        
        return payoffs

    # ==============================================================================
    # 3. BUMP AND REVALUE (GREEKS EXTRACTION)
    # ==============================================================================
    print("Simulating paths and extracting Greeks...")
    bump = 0.01
    base_payoffs = calculate_payoffs(S0)
    up_payoffs   = calculate_payoffs(S0 + bump)
    down_payoffs = calculate_payoffs(S0 - bump)
    
    # ==============================================================================
    # 4. ALPHA EXTRACTION & POSITION SIZING
    # ==============================================================================
    portfolio = []
    net_option_delta = 0.0
    total_theo_edge = 0.0
    
    for contract, market in market_data.items():
        base_val = base_payoffs[contract].mean()
        up_val   = up_payoffs[contract].mean()
        down_val = down_payoffs[contract].mean()
        
        unit_delta = (up_val - down_val) / (2 * bump)
        
        bid = market['bid']
        ask = market['ask']
        max_vol = market['max_vol']
        
        vol_executed = 0
        action = "NONE"
        edge_per_unit = 0.0
        
        if base_val > ask:
            action = "BUY"
            vol_executed = max_vol
            edge_per_unit = base_val - ask
            pos_delta = unit_delta * vol_executed
        elif base_val < bid:
            action = "SELL"
            vol_executed = -max_vol
            edge_per_unit = bid - base_val
            pos_delta = unit_delta * vol_executed
        else:
            pos_delta = 0.0
            
        if vol_executed != 0:
            net_option_delta += pos_delta
            total_theo_edge += edge_per_unit * abs(vol_executed)
            
        portfolio.append({
            "Contract": contract,
            "Fair Value": round(base_val, 4),
            "Unit Delta": round(unit_delta, 4),
            "Action": action,
            "Volume": abs(vol_executed),
            "Pos Delta": round(pos_delta, 2),
        })

    # ==============================================================================
    # 5. THE DELTA OFFSET (HEDGING)
    # ==============================================================================
    # The underlying AC has a fixed unit delta of 1.0. We take the inverse of the net options delta.
    ac_hedge_volume = -int(round(net_option_delta))
    ac_action = "BUY" if ac_hedge_volume > 0 else ("SELL" if ac_hedge_volume < 0 else "NONE")
    
    # Prepend the underlying hedge to the order book
    portfolio.insert(0, {
        "Contract": "AC (Underlying)",
        "Fair Value": 50.00,
        "Unit Delta": 1.0000,
        "Action": ac_action,
        "Volume": abs(ac_hedge_volume),
        "Pos Delta": float(ac_hedge_volume)
    })
    
    final_net_delta = net_option_delta + ac_hedge_volume
    
    df = pd.DataFrame(portfolio)
    return df, total_theo_edge, final_net_delta

if __name__ == "__main__":
    df_book, expected_edge, final_delta = build_delta_neutral_book(n_sims=1_000_000)
    
    print("\n===============================================================================")
    print("                       DELTA-NEUTRAL ORDER BOOK                                ")
    print("===============================================================================")
    print(df_book.to_string(index=False))
    print("===============================================================================")
    print(f"Total Theoretical Edge (Alpha):  {expected_edge:,.2f} Intarian Credits (per 1x multiplier)")
    print(f"Final Portfolio Net Delta:       {final_delta:,.2f} (Perfectly Hedged)")
    print("===============================================================================\n")