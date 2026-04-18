import matplotlib.pyplot as plt
import numpy as np
import scipy.stats as stats

BUDGET = 100

def research(x):
    return 200_000 * np.log(1 + x) / np.log(1 + 100)

def scale(y):
    return (y / 100) * 7

def expected_speed_multiplier(speed_bid, alpha, beta):
    x = speed_bid / 100.0
    percentile = stats.beta.cdf(x, alpha, beta)
    return 0.1 + (0.8 * percentile)

def analyze_profile(profile_name, alpha, beta, color):
    speed_bids = np.arange(0, 101, 1)
    best_pnls_for_speeds = []
    
    global_best_pnl = -np.inf
    global_best_speed = 0
    global_best_research = 0
    global_best_scale = 0

    for speed in speed_bids:
        C = BUDGET - speed
        
        if C <= 0:
            best_pnls_for_speeds.append(-50000 * (BUDGET / 100))
            continue
            
        speed_mul = expected_speed_multiplier(speed, alpha, beta)
        
        x = np.arange(0, C, 0.01)
        y1 = research(x)
        y2 = scale(C - x)
        ynet = y1 * y2 * speed_mul - 50000 * (BUDGET / 100)
        
        best_idx = np.argmax(ynet)
        max_pnl = ynet[best_idx]
        best_pnls_for_speeds.append(max_pnl)
        
        if max_pnl > global_best_pnl:
            global_best_pnl = max_pnl
            global_best_speed = speed
            global_best_research = x[best_idx]
            global_best_scale = C - global_best_research

    # Plot the overarching PnL curve
    plt.plot(speed_bids, best_pnls_for_speeds, label=f"{profile_name}", color=color, linewidth=2)
    
    # Plot the peak marker
    plt.plot(global_best_speed, global_best_pnl, marker='o', color=color, markersize=8, markeredgecolor='black') 
    
    # --- VISUAL ANCHORS ---
    # Vertical drop line to x-axis
    plt.vlines(x=global_best_speed, ymin=0, ymax=global_best_pnl, color=color, linestyle=':', alpha=0.7)
    # Horizontal drop line to y-axis
    plt.hlines(y=global_best_pnl, xmin=0, xmax=global_best_speed, color=color, linestyle=':', alpha=0.7)
    
    # --- DATA ANNOTATION BOX ---
    bbox_props = dict(boxstyle="round,pad=0.4", fc="white", ec=color, lw=1.5, alpha=0.9)
    plt.annotate(
        f"Speed: {global_best_speed}%\nRes (x): {global_best_research:.1f}%\nScale (y): {global_best_scale:.1f}%\nPnL: {global_best_pnl:,.0f}",
        xy=(global_best_speed, global_best_pnl),
        xytext=(15, -45), # Offset the text box slightly to the right and down
        textcoords='offset points',
        bbox=bbox_props,
        fontsize=9,
        arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0.2", color=color, lw=1.5)
    )

# Dictionary of profiles with assigned colors for visual clarity
profiles = {
    "Random (Uniform)": ((1, 1), 'tab:blue'),
    "Anchored (Bell Curve)": ((5, 5), 'tab:orange'),
    "Conservative (Low Bids)": ((2, 5), 'tab:green'),
    "Aggressive (Arms Race)": ((5, 2), 'tab:red')
}

plt.figure(figsize=(12, 8))

for name, params in profiles.items():
    (a, b), color = params
    analyze_profile(name, a, b, color)

plt.title("Expected PnL vs. Speed Investment by Psychology Profile", fontsize=14, fontweight='bold', pad=15)
plt.xlabel("Speed Investment %", fontsize=12)
plt.ylabel("Maximum Expected Net PnL", fontsize=12)

# Set axes limits to start at 0 so the anchors ground properly
plt.xlim(left=0, right=100)
plt.ylim(bottom=0)

plt.legend(loc="lower center", fontsize=10)
plt.grid(True, linestyle='--', alpha=0.4)
plt.tight_layout()
plt.show()