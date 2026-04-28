import matplotlib.pyplot as plt
import numpy as np
import scipy.stats as stats

BUDGET = 100 # max pnl if budget is 100, dont tweak

# --- N-REGIME POPULATION MODEL ---
# Weights must sum exactly to 1.0
REGIMES = [
    (0.05, 0, 1),    
    (0.05, 1, 1),
    (0.03, 5, 2),
    (0.06, 10, 3),
    (0.09, 20, 5),
    (0.10, 30, 5),
    (0.20, 40, 7),   
    (0.03, 45, 1),
    (0.13, 50, 3),
    (0.02, 55, 1),
    (0.10, 60, 4),
    (0.03, 70, 5),
    (0.04, 80, 5),
    (0.03, 90, 3),
    (0.02, 95, 3),
    (0.02, 99, 2)    # Bumped from 0.01 to 0.02 to ensure sum == 1.0
]

def get_speed_multiplier(my_speed, regimes):
    """Calculates expected multiplier based on N-regime opponent distribution."""
    percentile = 0.0
    for weight, mean, std in regimes:
        percentile += weight * stats.norm.cdf(my_speed, loc=mean, scale=std)
    
    return 0.1 + (0.8 * percentile)

def research(x):
    return 200_000 * np.log(1 + x) / np.log(1 + 100)

def scale(y):
    return (y / 100) * 7

def find_global_optimum():
    best_overall_pnl = -np.inf
    best_overall_allocation = None
    
    # Arrays to store data for plotting the global landscape
    speeds_tested = np.arange(0, 101, 1)
    max_pnls_for_speed = []
    expected_mults = []

    # Outer loop: Test every possible Speed bid from 0 to 100
    for speed in speeds_tested:
        speed_mul = get_speed_multiplier(speed, REGIMES)
        expected_mults.append(speed_mul)
        
        C = BUDGET - speed
        
        # If budget is exhausted, PnL is just the base negative cost
        if C <= 0:
            pnl = -50000 * (BUDGET / 100)
            max_pnls_for_speed.append(pnl)
            continue

        # Inner optimization: Find best Research/Scale split for the remaining budget C
        x = np.arange(0, C + 0.01, 0.01) 
        y1 = research(x)
        y2 = scale(C - x)
        
        ynet = y1 * y2 * speed_mul - 50000 * (BUDGET / 100)
        
        best_idx = np.argmax(ynet)
        best_x = x[best_idx]
        best_y = C - best_x
        max_pnl = ynet[best_idx]
        
        max_pnls_for_speed.append(max_pnl)
        
        # Check if this Speed bid beats the current global high score
        if max_pnl > best_overall_pnl:
            best_overall_pnl = max_pnl
            best_overall_allocation = {
                'speed': speed,
                'speed_mul': speed_mul,
                'research': best_x,
                'scale': best_y,
                'pnl': max_pnl
            }

    return best_overall_allocation, speeds_tested, max_pnls_for_speed, expected_mults

# Run the optimization across all possible speeds
best_alloc, speeds, pnls, mults = find_global_optimum()

# Print the exact optimal values to the console
print("=== GLOBAL OPTIMAL ALLOCATION ===")
print(f"Maximum Net PnL : {best_alloc['pnl']:,.2f} XIRECs")
print(f"Speed Invested  : {best_alloc['speed']}%")
print(f"Expected Mult.  : {best_alloc['speed_mul']:,.4f}x")
print(f"Research (x)    : {best_alloc['research']:.2f}%")
print(f"Scale (y)       : {best_alloc['scale']:.2f}%")
print("-" * 33)
print(f"Total Invested  : {best_alloc['speed'] + best_alloc['research'] + best_alloc['scale']:.2f}%")

# Plot the overarching landscape
fig, ax1 = plt.subplots(figsize=(10, 6))

color = 'tab:blue'
ax1.set_xlabel('Speed Investment (%)', fontweight='bold')
ax1.set_ylabel('Max Possible Net PnL', color=color, fontweight='bold')
ax1.plot(speeds, pnls, color=color, linewidth=2, label="Optimal Net PnL at Speed")
ax1.tick_params(axis='y', labelcolor=color)

# Plot a red dot exactly at the global peak
ax1.plot(best_alloc['speed'], best_alloc['pnl'], 'ro', markersize=8, 
         label=f"Global Peak (Speed={best_alloc['speed']}%)")

# Add a second y-axis to overlay the Speed Multiplier CDF curve
ax2 = ax1.twinx()
color = 'tab:green'
ax2.set_ylabel('Expected Speed Multiplier (x)', color=color, fontweight='bold')
ax2.plot(speeds, mults, color=color, linestyle='--', alpha=0.6, label="Multiplier Probability Curve")
ax2.tick_params(axis='y', labelcolor=color)

# Formatting
plt.title("IMC Prosperity 4 - Round 2 Optimization", fontsize=14, fontweight='bold')
fig.tight_layout()
ax1.grid(True, linestyle='--', alpha=0.5)

# Combine legends from both axes
lines_1, labels_1 = ax1.get_legend_handles_labels()
lines_2, labels_2 = ax2.get_legend_handles_labels()
ax1.legend(lines_1 + lines_2, labels_1 + labels_2, loc='upper left')

plt.show()