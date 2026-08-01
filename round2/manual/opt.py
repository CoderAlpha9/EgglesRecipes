import matplotlib.pyplot as plt
import numpy as np

BUDGET = 100 #max pnl if budget is 100, dont tweak

#need to identify reln between these 2:
SPEED = 11
SPEED_MUL = 0.11

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
    print(f"Maximum Net PnL : {max_pnl:,.2f}")
    print(f"Research (x)    : {best_x:.2f}%")
    print(f"Scale (y)       : {best_y:.2f}%")

    # Plot the curve
    plt.plot(x, ynet, label=f"C={C} Curve")
    
    # Plot a red dot exactly at the peak so you can visualize it
    plt.plot(best_x, max_pnl, 'ro', label=f"Peak (x={best_x:.2f}, y={best_y:.2f})")

crunch(BUDGET - SPEED)

plt.legend()
plt.title(f"Profit Optimization (Speed Multiplier: {SPEED_MUL}x)")
plt.xlabel("Research % (x)")
plt.ylabel("Net PnL")
plt.grid(True, linestyle='--', alpha=0.5)
plt.show()