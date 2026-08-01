import pandas as pd
import matplotlib.pyplot as plt

def analyze_prosperity_data():
    print("Loading data...")
    # Load the price data
    prices_d2 = pd.read_csv('dataset/prices_round_0_day_-2.csv', sep=';')
    prices_d1 = pd.read_csv('dataset/prices_round_0_day_-1.csv', sep=';')
    
    # Load the trades data
    trades_d2 = pd.read_csv('dataset/trades_round_0_day_-2.csv', sep=';')
    trades_d1 = pd.read_csv('dataset/trades_round_0_day_-1.csv', sep=';')

    # The trades files do not inherently contain the day, so we add it manually 
    # to differentiate when combining them into a single dataframe
    trades_d2['day'] = -2
    trades_d1['day'] = -1

    # Combine datasets
    prices = pd.concat([prices_d2, prices_d1], ignore_index=True)
    trades = pd.concat([trades_d2, trades_d1], ignore_index=True)

    # Create a continuous time column for seamless plotting
    # Assuming standard Prosperity days have 1,000,000 timestamps
    prices['continuous_time'] = prices['day'] * 1000000 + prices['timestamp']
    trades['continuous_time'] = trades['day'] * 1000000 + trades['timestamp']

    # Calculate Bid-Ask Spread for Level 1 depth
    prices['spread'] = prices['ask_price_1'] - prices['bid_price_1']

    # --- Print Summary Statistics ---
    print("\n--- Price & Spread Summary ---")
    summary = prices.groupby('product')[['mid_price', 'spread']].agg(['min', 'max', 'mean', 'std']).round(2)
    print(summary)
    
    print("\n--- Total Trade Volume Summary ---")
    volume = trades.groupby('symbol')['quantity'].sum()
    print(volume)

    # --- Plotting Mid-Price ---
    plt.figure(figsize=(12, 6))
    for product in prices['product'].unique():
        subset = prices[prices['product'] == product]
        plt.plot(subset['continuous_time'], subset['mid_price'], label=product, linewidth=1.5)
        
    plt.title('Mid Price of Products Across Day -2 and Day -1', fontsize=14)
    plt.xlabel('Continuous Time (Day * 1M + Timestamp)', fontsize=12)
    plt.ylabel('Mid Price', fontsize=12)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('prosperity_mid_prices.png')
    print("\nSaved 'prosperity_mid_prices.png'")

    # --- Plotting Bid-Ask Spread ---
    plt.figure(figsize=(12, 6))
    for product in prices['product'].unique():
        subset = prices[prices['product'] == product]
        plt.plot(subset['continuous_time'], subset['spread'], label=product, alpha=0.7)
        
    plt.title('Bid-Ask Spread Across Day -2 and Day -1', fontsize=14)
    plt.xlabel('Continuous Time (Day * 1M + Timestamp)', fontsize=12)
    plt.ylabel('Spread (Ask 1 - Bid 1)', fontsize=12)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('prosperity_spreads.png')
    print("Saved 'prosperity_spreads.png'")

if __name__ == "__main__":
    analyze_prosperity_data()