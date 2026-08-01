import pandas as pd
import matplotlib.pyplot as plt

def generate_advanced_plots():
    print("Loading datasets...")
    prices_d2 = pd.read_csv('dataset/prices_round_0_day_-2.csv', sep=';')
    prices_d1 = pd.read_csv('dataset/prices_round_0_day_-1.csv', sep=';')
    trades_d2 = pd.read_csv('dataset/trades_round_0_day_-2.csv', sep=';')
    trades_d1 = pd.read_csv('dataset/trades_round_0_day_-1.csv', sep=';')

    prices_d2['day'] = -2
    prices_d1['day'] = -1
    trades_d2['day'] = -2
    trades_d1['day'] = -1

    prices = pd.concat([prices_d2, prices_d1], ignore_index=True)
    trades = pd.concat([trades_d2, trades_d1], ignore_index=True)

    # Shift day to start from 0 for a cleaner continuous x-axis
    prices['continuous_time'] = (prices['day'] + 2) * 1000000 + prices['timestamp']
    trades['continuous_time'] = (trades['day'] + 2) * 1000000 + trades['timestamp']

    # Calculate spread
    prices['spread'] = prices['ask_price_1'] - prices['bid_price_1']
    
    # Get unique products to loop through
    products = prices['product'].unique()

    for product in products:
        print(f"Generating charts for {product}...")
        p_data = prices[prices['product'] == product].copy()
        t_data = trades[trades['symbol'] == product].copy()
        
        # Calculate moving averages to smooth the order book noise
        p_data['mid_price_ma'] = p_data['mid_price'].rolling(window=100).mean()
        p_data['spread_ma'] = p_data['spread'].rolling(window=100).mean()
        
        # Create a figure with 2 subplots (Top: Price/Trades, Bottom: Spread)
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={'height_ratios': [3, 1]})
        
        # --- Top Plot: Mid Price and Executed Trades ---
        ax1.plot(p_data['continuous_time'], p_data['mid_price'], label='Raw Mid Price', color='dodgerblue', alpha=0.4, linewidth=1)
        ax1.plot(p_data['continuous_time'], p_data['mid_price_ma'], label='100-Tick Moving Avg', color='navy', linewidth=2)
        
        # Scatter actual trades as red crosses
        ax1.scatter(t_data['continuous_time'], t_data['price'], color='crimson', marker='x', s=15, label='Executed Market Trades', zorder=5, alpha=0.8)
        
        ax1.set_title(f'{product} - Market Analysis (Price & Volume)', fontsize=16, fontweight='bold')
        ax1.set_ylabel('Price', fontsize=12)
        ax1.legend(loc='upper right')
        ax1.grid(True, linestyle='--', alpha=0.5)
        
        # --- Bottom Plot: Bid-Ask Spread ---
        ax2.plot(p_data['continuous_time'], p_data['spread'], color='gray', alpha=0.3, label='Raw Spread')
        ax2.plot(p_data['continuous_time'], p_data['spread_ma'], color='darkorange', label='100-Tick MA Spread', linewidth=2)
        
        ax2.set_ylabel('Spread', fontsize=12)
        ax2.set_xlabel('Continuous Time (Ticks)', fontsize=12)
        ax2.legend(loc='upper right')
        ax2.grid(True, linestyle='--', alpha=0.5)
        
        # Layout cleanup and save
        plt.tight_layout()
        filename = f'{product.lower()}_advanced_analysis.png'
        plt.savefig(filename, dpi=150)
        plt.close()
        print(f"Saved -> {filename}")

if __name__ == "__main__":
    generate_advanced_plots()