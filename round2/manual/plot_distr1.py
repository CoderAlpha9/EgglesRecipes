import matplotlib.pyplot as plt
import numpy as np

def research(x):
    return 200_000 * np.log(1 + x) / np.log(1 + 100)

def scale(x):
    return (x/100) * 7

# C is cost left after speed investment
# thus speed = (100-C)/100
def crunch(C, budget):
    if C <= 0:
        return # Skip to prevent empty plotting errors

    x = np.arange(0, C, 1)
    y1 = list(map(research, x))
    y2 = list(map(scale, C-x))
    ynet = [y1[i] * y2[i] * ((budget-C)/100) - (budget/100)*50000 for i in range(len(y1))]

    # Normalize C and budget to 0.0 - 1.0 for RGB coloring
    red_val = C / 100.0
    green_val = 0.0 # Kept at 0 for a pure red/blue/purple spectrum
    blue_val = budget / 100.0
    
    # Apply the custom color tuple
    plt.plot(x, ynet, color=(red_val, green_val, blue_val))

# Make the figure a bit larger to see the lines clearly
plt.figure(figsize=(10, 6))

for budget in range(10, 101, 10):
    for C in range(10, budget + 1, 10):
        crunch(C, budget)

# Added labels and grid for readability
plt.title("PnL Optimization (Color Map: Red = High 'C', Blue = High 'Budget')")
plt.xlabel("Research Allocation")
plt.ylabel("Net PnL")
plt.grid(True, linestyle='--', alpha=0.5)

plt.show()