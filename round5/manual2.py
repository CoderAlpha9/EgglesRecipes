import cvxpy as cp
import numpy as np

# Grounded estimates based on Prosperity 3 actuals (Extreme shocks)
round4_sentiments = {
    "Obsidian cutlery": -0.60,      # Structural contamination / halted production
    "Pyroflex cells": -0.30,        # Tax levy doubles tomorrow
    "Thermalite core": 0.35,        # Massive sustained earnings/usage beat
    "Lava cake": -0.60,             # Product recall / lethal / legal liability
    "Magma ink": 0.00,              # Priced in (event was yesterday)
    "Scoria paste": 0.00,           # Psychic lore / noise
    "Ashes of the Phoenix": 0.05,   # Fading the retail panic (birds are immortal)
    "Volcanic incense": -0.20,      # Pump and dump collapse
    "Sulfur reactor": 0.40          # Guaranteed structural index inflows
}

n = len(round4_sentiments)
goods = list(round4_sentiments.keys())

# Convert decimal predictions to raw percentage integers for the PnL formula
values = np.array(list(round4_sentiments.values())) * 100

# FIX: Removed 'integer=True'. This allows the default OSQP/CLARABEL solvers to run.
pi = cp.Variable(n)

# Ignith Exchange Math:
fee = 100 * cp.sum_squares(pi)
pnl = 100 * (values @ pi)

objective = cp.Maximize(pnl - fee)
constraints = [cp.norm(pi, 1) <= 100] 

problem = cp.Problem(objective=objective, constraints=constraints)

# Will automatically use the default solver now
problem.solve()

calculated_fee = fee.value
expected_gross = pnl.value

print(f"Expected Net PnL: {problem.value:,.2f} seashells")
print(f"Total Fee Paid:   {calculated_fee:,.2f} seashells")
print("-" * 55)
print(f"{'Resource':<25} {'Position':<10} {'Exact %':<10} {'Rounded %'}")
print("-" * 55)

total_rounded_allocation = 0
for i, good in enumerate(goods):
    allocation = pi.value[i]
    if allocation is not None and abs(allocation) > 0.1: # Filter out near-zeros
        position_type = "Buy" if allocation > 0 else "Sell"
        rounded_val = round(abs(allocation))
        
        print(f"{good:<25} {position_type:<10} {abs(allocation):<10.2f} {rounded_val}%")
        total_rounded_allocation += rounded_val

print("-" * 55)
print(f"{'Total Budget Used':<25} {'':<10} {'':<10} {total_rounded_allocation}%")