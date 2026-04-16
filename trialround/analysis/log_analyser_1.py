import json
import pandas as pd
import matplotlib.pyplot as plt
import io

def analyze_prosperity_logs(log_file_path):
    print(f"Loading logs from {log_file_path}...")
    
    with open(log_file_path, 'r') as f:
        log_data = json.load(f)

    final_profit = log_data.get('profit', 0)
    print(f"--- RUN SUMMARY ---")
    print(f"Final Profit: {final_profit:.2f} XIRECS\n")

    # Extract the activities CSV from the JSON
    csv_content = log_data['activitiesLog']
    df = pd.read_csv(io.StringIO(csv_content), sep=';')

    # Pivot the data to get PnL and Mid Prices per product over time
    pnl_df = df.pivot(index='timestamp', columns='product', values='profit_and_loss').fillna(method='ffill')
    price_df = df.pivot(index='timestamp', columns='product', values='mid_price').fillna(method='ffill')
    
    # Calculate Total PnL
    pnl_df['Total_PnL'] = pnl_df.sum(axis=1)

    # --- Plot 1: The PnL Curve ---
    plt.figure(figsize=(14, 7))
    plt.plot(pnl_df.index, pnl_df['Total_PnL'], label='Total PnL', color='forestgreen', linewidth=2.5)
    
    colors = {'EMERALDS': 'teal', 'TOMATOES': 'tomato'}
    for product in [p for p in pnl_df.columns if p != 'Total_PnL']:
        plt.plot(pnl_df.index, pnl_df[product], label=f'{product} PnL', color=colors.get(product, 'gray'), alpha=0.7, linestyle='--')

    plt.title(f'Profit & Loss Over Time (Final: {final_profit:.2f})', fontsize=16, fontweight='bold')
    plt.xlabel('Simulation Timestamp', fontsize=12)
    plt.ylabel('Cumulative Profit (XIRECS)', fontsize=12)
    plt.legend(loc='upper left')
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.tight_layout()
    plt.savefig('run_pnl_analysis.png', dpi=150)
    print("Saved -> run_pnl_analysis.png")

    # --- Plot 2: Price Tracking (Did the bot survive the crashes?) ---
    plt.figure(figsize=(14, 7))
    for product in price_df.columns:
        # Normalize prices to percentage change for easy comparison on the same axis
        normalized_price = (price_df[product] / price_df[product].iloc[0] - 1) * 100
        plt.plot(price_df.index, normalized_price, label=f'{product} Price % Change', color=colors.get(product, 'gray'), linewidth=2)

    plt.title('Market Price Action During Run (% Change)', fontsize=16, fontweight='bold')
    plt.xlabel('Simulation Timestamp', fontsize=12)
    plt.ylabel('Price % Change from Start', fontsize=12)
    plt.legend(loc='upper left')
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.tight_layout()
    plt.savefig('run_price_action.png', dpi=150)
    print("Saved -> run_price_action.png")

if __name__ == "__main__":
    # Replace with the name of your log file
    analyze_prosperity_logs('25192.json')