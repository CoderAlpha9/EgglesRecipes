import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

def load_and_prep_data():
    """Loads and merges the historical trading data."""
    print("Loading data...")
    # Load prices
    p_d2 = pd.read_csv('dataset/prices_round_0_day_-2.csv', sep=';')
    p_d1 = pd.read_csv('dataset/prices_round_0_day_-1.csv', sep=';')
    
    # Load trades
    t_d2 = pd.read_csv('dataset/trades_round_0_day_-2.csv', sep=';')
    t_d1 = pd.read_csv('dataset/trades_round_0_day_-1.csv', sep=';')

    # Add day indicators
    p_d2['day'] = -2
    p_d1['day'] = -1
    t_d2['day'] = -2
    t_d1['day'] = -1

    prices = pd.concat([p_d2, p_d1], ignore_index=True)
    trades = pd.concat([t_d2, t_d1], ignore_index=True)

    # Create continuous time axis (assuming 1M timestamps per day)
    prices['continuous_time'] = (prices['day'] + 2) * 1000000 + prices['timestamp']
    trades['continuous_time'] = (trades['day'] + 2) * 1000000 + trades['timestamp']

    return prices, trades

def calculate_advanced_metrics(prices, trades):
    """Calculates comprehensive order book and time series metrics."""
    print("Calculating metrics...")
    df = prices.copy()
    
    # ---------------------------------------------------------
    # 1. BASIC ORDER BOOK METRICS
    # ---------------------------------------------------------
    df['spread'] = df['ask_price_1'] - df['bid_price_1']
    df['mid_price'] = (df['ask_price_1'] + df['bid_price_1']) / 2.0

    # ---------------------------------------------------------
    # 2. MICROSTRUCTURE METRICS
    # ---------------------------------------------------------
    # Total Level 1 Volume
    df['total_vol_l1'] = df['bid_volume_1'] + df['ask_volume_1']
    
    # Order Book Imbalance (OBI)
    # [-1 to 1] where +1 means heavy buy pressure, -1 means heavy sell pressure
    df['obi_l1'] = (df['bid_volume_1'] - df['ask_volume_1']) / df['total_vol_l1']
    
    # Micro-Price (Volume-Weighted Mid Price)
    # Shifts the fair value closer to the side with less volume (as it's more likely to get eaten)
    df['micro_price'] = (df['bid_price_1'] * df['ask_volume_1'] + df['ask_price_1'] * df['bid_volume_1']) / df['total_vol_l1']

    # ---------------------------------------------------------
    # 3. TIME SERIES & MACRO METRICS
    # ---------------------------------------------------------
    results = []
    for product in df['product'].unique():
        prod_df = df[df['product'] == product].copy().sort_values('continuous_time')
        
        # Returns and Volatility
        prod_df['returns'] = prod_df['mid_price'].pct_change()
        prod_df['rolling_volatility_20'] = prod_df['returns'].rolling(window=20).std() * np.sqrt(20) # 20-tick realized vol
        
        # Exponential Moving Averages (Trends)
        prod_df['ema_9'] = prod_df['mid_price'].ewm(span=9, adjust=False).mean()
        prod_df['ema_21'] = prod_df['mid_price'].ewm(span=21, adjust=False).mean()
        prod_df['macd'] = prod_df['ema_9'] - prod_df['ema_21']
        
        # VWAP (Volume Weighted Average Price) from Trades
        prod_trades = trades[trades['symbol'] == product].copy()
        
        if not prod_trades.empty:
            # Merge trade volume into the price dataframe at the nearest timestamp
            trade_agg = prod_trades.groupby('continuous_time').apply(
                lambda x: pd.Series({
                    'traded_volume': x['quantity'].sum(),
                    'traded_value': (x['price'] * x['quantity']).sum()
                })
            ).reset_index()
            
            prod_df = pd.merge(prod_df, trade_agg, on='continuous_time', how='left')
            prod_df['traded_volume'] = prod_df['traded_volume'].fillna(0)
            prod_df['traded_value'] = prod_df['traded_value'].fillna(0)
            
            # Cumulative VWAP calculation (Rolling 50 ticks to reflect recent flow)
            prod_df['rolling_vol'] = prod_df['traded_volume'].rolling(50, min_periods=1).sum()
            prod_df['rolling_val'] = prod_df['traded_value'].rolling(50, min_periods=1).sum()
            prod_df['vwap_50'] = np.where(prod_df['rolling_vol'] > 0, prod_df['rolling_val'] / prod_df['rolling_vol'], prod_df['mid_price'])
        else:
            prod_df['vwap_50'] = prod_df['mid_price']
            
        results.append(prod_df)
        
    final_df = pd.concat(results, ignore_index=True)
    return final_df

def plot_comprehensive_analysis(df, product, start_idx=10000, end_idx=11000):
    """Generates a multi-panel dashboard for a specific product subset."""
    print(f"Generating charts for {product}...")
    pdf = df[df['product'] == product].sort_values('continuous_time').reset_index(drop=True)
    
    # Zoom in to see the micro-movements clearly
    subset = pdf.iloc[start_idx:end_idx]
    
    fig, axes = plt.subplots(4, 1, figsize=(15, 12), sharex=True, gridspec_kw={'height_ratios': [3, 1, 1, 1]})
    
    # PANEL 1: Price Action (Mid Price, Micro Price, VWAP)
    axes[0].plot(subset['continuous_time'], subset['mid_price'], label='Mid Price', color='black', alpha=0.5, linewidth=1)
    axes[0].plot(subset['continuous_time'], subset['micro_price'], label='Micro Price (Vol wgt)', color='dodgerblue', linestyle='--')
    axes[0].plot(subset['continuous_time'], subset['vwap_50'], label='50-Tick VWAP', color='darkorange', linewidth=2)
    axes[0].set_title(f'{product} - Price Action & Fair Value Indicators', fontweight='bold')
    axes[0].legend(loc='upper left')
    axes[0].grid(True, alpha=0.3)
    
    # PANEL 2: Spread & Volatility
    ax2_vol = axes[1].twinx()
    axes[1].plot(subset['continuous_time'], subset['spread'], color='purple', label='Spread')
    ax2_vol.plot(subset['continuous_time'], subset['rolling_volatility_20'], color='red', alpha=0.4, label='Realized Volatility')
    axes[1].set_ylabel('Spread (ticks)')
    ax2_vol.set_ylabel('Volatility')
    axes[1].legend(loc='upper left')
    ax2_vol.legend(loc='upper right')
    axes[1].grid(True, alpha=0.3)
    
    # PANEL 3: Order Book Imbalance (OBI)
    axes[2].fill_between(subset['continuous_time'], subset['obi_l1'], 0, where=(subset['obi_l1'] >= 0), color='green', alpha=0.5, label='Buy Pressure')
    axes[2].fill_between(subset['continuous_time'], subset['obi_l1'], 0, where=(subset['obi_l1'] < 0), color='red', alpha=0.5, label='Sell Pressure')
    axes[2].axhline(0, color='black', linewidth=1)
    axes[2].set_ylabel('OBI (-1 to 1)')
    axes[2].legend(loc='upper left')
    axes[2].grid(True, alpha=0.3)
    
    # PANEL 4: Momentum (MACD)
    axes[3].bar(subset['continuous_time'], subset['macd'], width=100, color=np.where(subset['macd'] > 0, 'green', 'red'), label='MACD (9-21)')
    axes[3].axhline(0, color='black', linewidth=1)
    axes[3].set_ylabel('MACD')
    axes[3].set_xlabel('Continuous Time')
    axes[3].legend(loc='upper left')
    axes[3].grid(True, alpha=0.3)
    
    plt.tight_layout()
    filename = f"{product.lower()}_comprehensive_metrics.png"
    plt.savefig(filename, dpi=150)
    plt.close()
    print(f"Saved -> {filename}")

if __name__ == "__main__":
    prices, trades = load_and_prep_data()
    metrics_df = calculate_advanced_metrics(prices, trades)
    
    # Output descriptive statistics for strategy tuning
    print("\n--- Strategy Tuning Parameters ---")
    for prod in metrics_df['product'].unique():
        pdf = metrics_df[metrics_df['product'] == prod]
        print(f"\n{prod.upper()}:")
        print(f"  Average Spread: {pdf['spread'].mean():.2f}")
        print(f"  Max Spread:     {pdf['spread'].max():.2f}")
        print(f"  Base Volatility:{pdf['rolling_volatility_20'].mean():.6f}")
        print(f"  OBI Std Dev:    {pdf['obi_l1'].std():.2f} (Use this for dynamic quoting thresholds)")
        
    # Generate Plots (Adjust start/end indices to explore different timeframes)
    plot_comprehensive_analysis(metrics_df, "EMERALDS", start_idx=5000, end_idx=7000)
    plot_comprehensive_analysis(metrics_df, "TOMATOES", start_idx=5000, end_idx=7000)
    
    # You can also save the enriched dataset to CSV for further exploration
    # metrics_df.to_csv('enriched_market_data.csv', index=False)