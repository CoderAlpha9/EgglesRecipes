import matplotlib.pyplot as plt
import numpy as np
import scipy.stats as stats

BUDGET = 100 # max pnl if budget is 100, dont tweak

# --- N-REGIME POPULATION MODEL ---
# Define regimes as tuples: (Weight, Mean_Speed, Standard_Deviation)
# Note: The sum of all weights must equal 1.0 (100% of the population)
REGIMES = [
    (0.06, 0, 1),    # 20% of people heavily clustered around 0
    (0.05, 1, 1),
    (0.03, 5, 2),
    (0.06, 10, 3),
    (0.09, 20, 5),
    (0.1, 30, 5),
    (0.20, 40, 7),   # 75% of people loosely clustered around 40
    (0.03, 45, 1),
    (0.13, 50, 3),
    (0.02, 55, 1),
    (0.1, 60, 4),
    (0.03, 70, 5),
    (0.04, 80, 5),
    (0.03, 90, 3),
    (0.02, 95, 3),
    (0.01, 99, 2)   # 5% of people heavily clustered at exactly 100
]

SPEED = 90

def get_speed_multiplier(my_speed, regimes):
    """Calculates expected multiplier based on N-regime opponent distribution."""
    percentile = 0.0
    for weight, mean, std in regimes:
        # CDF calculates the probability that an opponent in this regime bids <= my_speed
        percentile += weight * stats.norm.cdf(my_speed, loc=mean, scale=std)
    
    # Map the resulting percentile (0.0 to 1.0) to the multiplier (0.1 to 0.9)
    return 0.1 + (0.8 * percentile)

# Dynamically calculate the multiplier before running the crunch
SPEED_MUL = get_speed_multiplier(SPEED, REGIMES)

def research(x):
    return 200_000 * np.log(1 + x) / np.log(1 + 100)

def scale(y):
    return (y/100) * 7

# C is cost left after speed investment
def crunch(C):
    # Step by 0.01 instead of 1 for highly precise decimal allocations
    x = np.arange(0, C, 0.01)
    
    # Using NumPy vectorization instead of maps/loops for faster execution
    y1 = research(x)       # x is research invest
    y2 = scale(C - x)      # C-x is scale invest
    ynet = y1 * y2 * SPEED_MUL - 50000 * (BUDGET / 100)

    # 1. Find the index of the absolute highest PnL in the array
    best_idx = np.argmax(ynet)
    
    # 2. Extract the corresponding values using that index
    best_x = x[best_idx]
    best_y = C - best_x
    max_pnl = ynet[best_idx]

    # Print the exact optimal values to the console
    print("--- Optimal Allocation Found ---")
    print(f"Speed Invested  : {SPEED}%")
    print(f"Expected Mult.  : {SPEED_MUL:.4f}x")
    print(f"Maximum Net PnL : {max_pnl:,.2f}")
    print(f"Research (x)    : {best_x:.2f}%")
    print(f"Scale (y)       : {best_y:.2f}%")

    # Plot the curve
    plt.plot(x, ynet, label=f"C={C} Curve")
    
    # Plot a red dot exactly at the peak so you can visualize it
    plt.plot(best_x, max_pnl, 'ro', label=f"Peak (x={best_x:.2f}, y={best_y:.2f})")

crunch(BUDGET - SPEED)

plt.legend()
plt.title(f"Profit Optimization (Speed Multiplier: {SPEED_MUL:.3f}x)")
plt.xlabel("Research % (x)")
plt.ylabel("Net PnL")
plt.grid(True, linestyle='--', alpha=0.5)
plt.show()