import matplotlib.pyplot as plt
import numpy as np

def prob(bid):
    # Discrete reserve prices: 670, 675, 680 ... 920
    reserves = np.arange(670, 921, 5)
    # Trade executes only if bid is STRICTLY GREATER than the reserve price
    beaten_reserves = np.sum(reserves < bid)
    return beaten_reserves / len(reserves)

def func(bid):
    # Expected profit = Margin * Probability of trading
    return (920 - bid) * prob(bid)

def crunch():
    # Test all integer bids from 670 to 920
    x = np.arange(670, 921, 1)
    ynet = [func(b) for b in x]
    
    # Setup plot
    plt.figure(figsize=(10, 6))
    plt.plot(x, ynet, label='Expected Profit (EV)', color='blue')
    
    # Highlight the optimal integer bid
    max_ev = max(ynet)
    best_bid = x[ynet.index(max_ev)]
    
    plt.plot(best_bid, max_ev, 'ro', markersize=8, 
             label=f'Optimal Integer Bid: {best_bid}\n(EV: {max_ev:.2f})')
    plt.axvline(best_bid, color='red', linestyle='--', alpha=0.5)
    
    plt.title('Bid 1: Expected Profit vs. Bid Amount')
    plt.xlabel('Bid 1 Amount')
    plt.ylabel('Expected Profit (EV)')
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    # Save instead of show to view in this environment
    plt.savefig('bid1_ev.png')

crunch()