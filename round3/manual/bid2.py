import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm

# Define the discrete space
bids = np.arange(670, 921, 1)
reserves = np.arange(670, 921, 5)

def prob_win_reserve(b):
    """Probability of beating the discrete uniform reserve."""
    return np.sum(reserves < b) / len(reserves)

# Pre-compute reserve probabilities
p_res = np.array([prob_win_reserve(b) for b in bids])

def get_ev_profile(mu_dist):
    """
    Calculates EV across all bids for a given probability distribution of mu.
    """
    ev_profile = np.zeros(len(bids))
    
    for i, b in enumerate(bids):
        # Strict edge case handling: Zero margin means zero profit.
        if b == 920:
            ev_profile[i] = 0
            continue
            
        expected_pnl = 0
        for j, mu in enumerate(bids):
            p_mu = mu_dist[j]
            if p_mu == 0:
                continue
                
            if b > mu:
                # Dominant Regime
                pnl = (920 - b) * p_res[i]
            else:
                # Penalized Regime (safe from divide-by-zero since b < 920 here)
                pnl = ((920 - mu)**3 / (920 - b)**2) * p_res[i]
                
            expected_pnl += pnl * p_mu
            
        ev_profile[i] = expected_pnl
        
    # Find true peak
    best_idx = np.argmax(ev_profile)
    return ev_profile, bids[best_idx], ev_profile[best_idx]

def build_gmm_distribution(components):
    """
    Builds a composite probability distribution (GMM) from specified cohorts.
    components: list of dicts defining cohort behavior and weight in the meta.
    """
    combined_pdf = np.zeros(len(bids))
    
    for comp in components:
        if comp['type'] == 'normal':
            pdf = norm.pdf(bids, loc=comp['loc'], scale=comp['scale'])
        elif comp['type'] == 'uniform':
            pdf = np.ones(len(bids))
        else:
            raise ValueError("Unsupported distribution type")
            
        # Normalize component so it sums to 1
        pdf /= np.sum(pdf)
        # Add to the mixture based on weight
        combined_pdf += pdf * comp['weight']
        
    # Final normalization to ensure the mixture sums perfectly to 1
    combined_pdf /= np.sum(combined_pdf)
    return combined_pdf

def run_meta_simulation():
    # ---------------------------------------------------------
    # DEFINE YOUR MARKET GMM HERE
    # Tune the weights to represent the expected participant pool
    # ---------------------------------------------------------
    market_composition = [
        # 15% of players don't know what they are doing (Uniform)
        {'type': 'uniform', 'weight': 0.01},
        {'type': 'normal', 'weight': 0.03, 'loc': 795, 'scale': 2},

        {'type': 'normal', 'weight': 0.05, 'loc': 801, 'scale': 5},
        
        # 45% of players are basic quants anchoring to pure EV (Normal at 801)
        {'type': 'normal', 'weight': 0.03, 'loc': 806, 'scale': 5},
        
        # 30% of players are paranoid and step up (Normal at 825)
        {'type': 'normal', 'weight': 0.05, 'loc': 811, 'scale': 5},
        
        # 10% of players are Discord followers strictly bidding ~836
        {'type': 'normal', 'weight': 0.05, 'loc': 816, 'scale': 5},
        {'type': 'normal', 'weight': 0.05, 'loc': 821, 'scale': 5},
        {'type': 'normal', 'weight': 0.05, 'loc': 826, 'scale': 5},
        
        {'type': 'normal', 'weight': 0.05, 'loc': 831, 'scale': 5},
        {'type': 'normal', 'weight': 0.05, 'loc': 826, 'scale': 5},
        
        {'type': 'normal', 'weight': 0.1, 'loc': 831, 'scale': 5},
        
        {'type': 'normal', 'weight': 0.005, 'loc': 836, 'scale': 1},
        {'type': 'normal', 'weight': 0.005, 'loc': 837, 'scale': 2},
        
        {'type': 'normal', 'weight': 0.05, 'loc': 846, 'scale': 10},
        {'type': 'normal', 'weight': 0.04, 'loc': 856, 'scale': 10},
        {'type': 'normal', 'weight': 0.03, 'loc': 871, 'scale': 10},
        {'type': 'normal', 'weight': 0.03, 'loc': 891, 'scale': 20},
        {'type': 'normal', 'weight': 0.03, 'loc': 901, 'scale': 20},
        
        {'type': 'normal', 'weight': 0.02, 'loc': 911, 'scale': 20},
    ]
    
    # Generate the global distribution
    gmm_dist = build_gmm_distribution(market_composition)
    
    # Calculate EV
    ev_profile, best_bid, max_ev = get_ev_profile(gmm_dist)
    
    # Plotting
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10), sharex=True)
    
    # Plot 1: The GMM Distribution of avg_b2
    ax1.plot(bids, gmm_dist, color='purple', fillstyle='bottom')
    ax1.fill_between(bids, gmm_dist, alpha=0.3, color='purple')
    ax1.set_title("Modeled Competitor Distribution (GMM for avg_b2)")
    ax1.set_ylabel("Probability")
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: The Resulting EV Curve
    ax2.plot(bids, ev_profile, color='blue', linewidth=2)
    ax2.plot(best_bid, max_ev, 'ro', markersize=8, 
             label=f'Optimal Bid: {best_bid} (EV: {max_ev:.2f})')
    ax2.axvline(best_bid, color='red', linestyle='--', alpha=0.5)
    
    ax2.set_title("Your Expected Value Curve against GMM")
    ax2.set_xlabel("Your Bid 2")
    ax2.set_ylabel("Expected Profit")
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('bid2_gmm_optimization.png')
    
    print(f"Market Modeled. Optimal Bid: {best_bid}")

run_meta_simulation()