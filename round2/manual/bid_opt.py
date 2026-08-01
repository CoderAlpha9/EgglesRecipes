import matplotlib.pyplot as plt
import numpy as np
import scipy.stats as stats

BUDGET = 100

def research(x):
    return 200_000 * np.log(1 + x) / np.log(1 + 100)

def scale(y):
    return (y / 100) * 7

def expected_speed_multiplier(speed_bid, alpha, beta):
    # Maps a normalized bid to an expected rank multiplier using a Beta CDF
    x = speed_bid / 100.0
    percentile = stats.beta.cdf(x, alpha, beta)
    return 0.1 + (0.8 * percentile)

def analyze_profile(profile_name, alpha, beta):
    speed_bids = np.arange(0, 101, 1)
    best_pnls_for_speeds = []
    
    global_best_pnl = -np.inf
    global_best_speed = 0
    global_best_research = 0
    global_best_scale = 0

    # Test every single possible speed bid from 0 to 100
    for speed in speed_bids:
        C = BUDGET - speed
        
        # If speed eats the whole budget, PnL is just the lost budget fee
        if C <= 0:
            best_pnls_for_speeds.append(-50000 * (BUDGET / 100))
            continue
            
        # 1. Get the game-theory predicted multiplier for this specific speed bid
        speed_mul = expected_speed_multiplier(speed, alpha, beta)
        
        # 2. Find the optimal Research and Scale allocation for whatever budget is left (C)
        x = np.arange(0, C, 0.01)
        y1 = research(x)
        y2 = scale(C - x)
        ynet = y1 * y2 * speed_mul - 50000 * (BUDGET / 100)
        
        # 3. Extract the peak PnL for this specific speed bid
        best_idx = np.argmax(ynet)
        max_pnl = ynet[best_idx]
        best_pnls_for_speeds.append(max_pnl)
        
        # 4. Check if this is the highest PnL we've seen across ALL speed bids
        if max_pnl > global_best_pnl:
            global_best_pnl = max_pnl
            global_best_speed = speed
            global_best_research = x[best_idx]
            global_best_scale = C - global_best_research

    # Print the exact optimal values to the console
    print(f"--- Peak Allocation: {profile_name.upper()} Crowd ---")
    print(f"Max Expected PnL : {global_best_pnl:,.2f}")
    print(f"Speed (z)        : {global_best_speed}%")
    print(f"Research (x)     : {global_best_research:.2f}%")
    print(f"Scale (y)        : {global_best_scale:.2f}%")
    print(f"Expected Mult.   : {expected_speed_multiplier(global_best_speed, alpha, beta):.3f}x\n")
    
    # Plot the overarching PnL curve for this psychology profile
    plt.plot(speed_bids, best_pnls_for_speeds, label=f"{profile_name.capitalize()}")
    # Mark the exact absolute peak with a black dot
    plt.plot(global_best_speed, global_best_pnl, 'ko', markersize=5) 

# Dictionary of beta distribution parameters representing different psychologies
profiles = {
    "Random (Uniform)": (1, 1),
    "Anchored (Bell Curve)": (5, 5),
    "Conservative (Low Bids)": (2, 5),
    "Aggressive (Arms Race)": (5, 2),
    "Super Aggressive (Arms Race)": (100, 100)
}

plt.figure(figsize=(10, 6))

for name, (a, b) in profiles.items():
    analyze_profile(name, a, b)

plt.title("Expected PnL vs. Speed Investment by Psychology Profile")
plt.xlabel("Speed Investment % (z)")
plt.ylabel("Maximum Expected PnL")
plt.legend()
plt.grid(True, linestyle='--', alpha=0.5)
plt.show()