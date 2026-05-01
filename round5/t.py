import numpy as np
import pandas as pd

def find_profit_threshold():
    # Sweep price changes (x) from 0.0% to 5.0% in small increments
    x_values = np.linspace(0.0, 5.0, 21)
    results = []

    for x in x_values:
        # 1. Calculate optimal continuous position (p = x / 2)
        p_continuous = x / 2
        
        # 2. Round to nearest integer since the exchange requires whole percentages
        p_integer = round(p_continuous)
        
        # 3. Calculate Net PnL for the integer position: 100*p*x - 100*p^2
        net_pnl = 100 * p_integer * x - 100 * (p_integer ** 2)
        
        results.append({
            "Price Move (x)": f"{x:.2f}%",
            "Optimal Pos (p)": f"{p_integer}%",
            "Net PnL": round(net_pnl, 2)
        })

    # Display as a clean matrix
    df = pd.DataFrame(results)
    print("IGNITH EXCHANGE: MINIMUM PROFITABILITY THRESHOLD")
    print("-" * 50)
    print(df.to_string(index=False))

if __name__ == "__main__":
    find_profit_threshold()