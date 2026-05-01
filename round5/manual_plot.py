import numpy as np
import matplotlib.pyplot as plt

# Define your portfolio and stress test scenarios here.
# 'p_actual': The percentage you have invested based on your screenshot (-ve for Sell, +ve for Buy)
# 'x_scenario': The assumed percentage price change of the asset (-ve if price drops, +ve if price rises)
portfolio = {
    "Obsidian cutlery": {"p_actual": -10, "x_scenario": -20},
    "Pyroflex cells": {"p_actual": -6, "x_scenario": -10},
    "Thermalite core": {"p_actual": 10, "x_scenario": 15},
    "Lava cake": {"p_actual": -24, "x_scenario": -48},
    "Magma ink": {"p_actual": 1, "x_scenario": 0},
    "Scoria paste": {"p_actual": 3, "x_scenario": 0},
    "Ashes of the Phoenix": {"p_actual": -5, "x_scenario": 5},
    "Volcanic incense": {"p_actual": 1, "x_scenario": -5},
    "Sulfur reactor": {"p_actual": 11, "x_scenario": 10}
}

def calculate_pnl(p, x):
    """
    Calculates Net PnL based on the derived Ignith exchange mathematical formula.
    Net PnL = Gross Profit - Fee
    Net PnL = 100 * p * x - 100 * p^2
    """
    return 100 * p * x - 100 * (p ** 2)

# Set up the 2x5 plot grid
fig, axes = plt.subplots(2, 5, figsize=(22, 10))
fig.suptitle("Ignith Exchange Portfolio Stress Test: PnL vs. Position Size (p%)", fontsize=18, fontweight='bold')
axes = axes.flatten()

# Range of p for the x-axis of our plots (-30% to +30%)
p_range = np.linspace(-30, 30, 200)

# Generate plots for the 9 assets
for i, (asset, data) in enumerate(portfolio.items()):
    ax = axes[i]
    p_actual = data["p_actual"]
    x_val = data["x_scenario"]
    
    # Calculate PnL curve for the continuous range
    pnl_curve = calculate_pnl(p_range, x_val)
    
    # Calculate exact PnL for the specific portfolio point
    pnl_actual = calculate_pnl(p_actual, x_val)
    
    # Plot the PnL parabola
    ax.plot(p_range, pnl_curve, label=f"PnL Curve (if asset changes {x_val}%)", color='#1f77b4', linewidth=2)
    
    # Highlight your actual position
    ax.scatter([p_actual], [pnl_actual], color='#d62728', s=120, zorder=5, label=f"Your Pos: {p_actual}%\nPnL: {pnl_actual:,.0f}")
    ax.axvline(x=p_actual, color='#d62728', linestyle='--', alpha=0.5)
    
    # Axis formatting and zero-lines
    ax.axhline(0, color='black', linewidth=1)
    ax.axvline(0, color='black', linewidth=1)
    ax.set_title(asset, fontweight='bold')
    ax.set_xlabel("Position (p%)")
    ax.set_ylabel("Net PnL")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower center", fontsize='small')

# Add a 10th plot for the Total Aggregate PnL of the stress test
ax_total = axes[9]
total_pnl_actual = sum(calculate_pnl(d["p_actual"], d["x_scenario"]) for d in portfolio.values())

ax_total.text(0.5, 0.65, "Total Expected PnL\n(Sum of Scenarios):", ha='center', va='center', fontsize=16, fontweight='bold')
ax_total.text(0.5, 0.45, f"{total_pnl_actual:,.2f}", ha='center', va='center', fontsize=24, color='green' if total_pnl_actual > 0 else 'red', weight='bold')

ax_total.axis('off')

plt.tight_layout()
plt.subplots_adjust(top=0.90)
plt.show()