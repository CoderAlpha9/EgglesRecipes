"""
Ignith Portfolio Optimizer — Round 5 Manual
PnL_i = x_i * r_i * B - x_i^2 * B   (signed x: long>0, short<0)
Closed-form unconstrained optimum: x_i* = mu_i / 2
Constraint: sum |x_i| <= 1  (rescale if binding)
"""
import numpy as np
from scipy.optimize import minimize

np.random.seed(7)
BUDGET = 1_000_000

# --- Sentiment-derived priors (mu = anchor return, sigma = uncertainty within range) ---
# News is FRESH (between trading days, market hasn't seen it).
# Crowded obvious trades will be amplified by aggregate submissions (range mechanic).
products = [
    # name,                mu,    sigma,  rationale
    ('thermalite_core',   +0.15, 0.06),  # 1.42M -> 3.89M users (+174%); concrete forward data
    ('lava_cake',         -0.18, 0.06),  # actual lava found, sales halt, lawsuits, vendor returns
    ('pyroflex_cells',    -0.15, 0.05),  # 50% PCTC abolished tomorrow -> levy doubles
    ('sulfur_reactor',    +0.14, 0.04),  # Index 118 inclusion -> mechanical fund rebalancing
    ('obsidian_cutlery',  -0.13, 0.05),  # production halted, contamination, evacuation
    ('ashes_phoenix',     -0.05, 0.05),  # PR damage, partially defused by "birds immortal"
    ('volcanic_incense',   0.00, 0.07),  # ambiguous: rally vs FOMO exhaustion -> skip
    ('scoria_paste',      +0.05, 0.04),  # influencer pump, very crowded -> small edge
    ('magma_ink',         +0.04, 0.04),  # one-off hot drop, mild positive carry
]
names  = [p[0] for p in products]
mus    = np.array([p[1] for p in products])
sigmas = np.array([p[2] for p in products])
n      = len(products)

# === STEP 1: closed-form analytic optimum ===
x_cf = mus / 2.0
used = np.sum(np.abs(x_cf))
if used > 1.0:
    x_cf = x_cf / used   # rescale to fit budget
print(f"Analytic budget usage: {np.sum(np.abs(x_cf))*100:.2f}%  (constraint binding: {used>1.0})")

# === STEP 2: numerical optimizer (sanity check, with full sum|x|<=1 constraint) ===
def neg_E_pnl(x):
    return -np.sum(x*mus - x**2)
cons = ({'type': 'ineq', 'fun': lambda x: 1.0 - np.sum(np.abs(x))})
bnds = [(-1, 1)] * n
res = minimize(neg_E_pnl, x0=np.zeros(n), method='SLSQP', bounds=bnds, constraints=cons)
x_num = res.x
diff  = np.max(np.abs(x_num - x_cf))
print(f"Numerical vs analytic max diff: {diff:.2e}  -> closed-form is optimal\n")

x_opt = x_cf  # use analytic

# === STEP 3: Monte Carlo over realized return uncertainty ===
# Game-theory bias: crowded directional trades pulled to far edge of range
crowd_bias = np.array([0.3, 0.5, 0.5, 0.4, 0.4, 0.2, 0.0, 0.5, 0.3])  # fraction of sigma
mu_realized = mus + np.sign(mus) * crowd_bias * sigmas

N = 200_000
shocks  = np.random.randn(N, n)
returns = mu_realized + sigmas * shocks
pnl_mat = x_opt * returns * BUDGET - (x_opt**2) * BUDGET
total   = pnl_mat.sum(axis=1)

# === STEP 4: report ===
print("="*88)
print(f"{'PRODUCT':<20} {'SIGNAL':<6} {'ALLOC%':>8} {'INVEST $':>12} {'FEE $':>10} {'E[PnL] $':>12}")
print("="*88)
for i, nm in enumerate(names):
    sig = "BUY" if x_opt[i] > 1e-6 else ("SELL" if x_opt[i] < -1e-6 else "SKIP")
    inv = abs(x_opt[i]) * BUDGET
    fee = (x_opt[i]**2) * BUDGET
    epn = pnl_mat[:, i].mean()
    print(f"{nm:<20} {sig:<6} {abs(x_opt[i])*100:>7.2f}% {inv:>12,.0f} {fee:>10,.0f} {epn:>12,.0f}")
print("="*88)
print(f"{'TOTAL':<20} {'':<6} {np.sum(np.abs(x_opt))*100:>7.2f}% "
      f"{np.sum(np.abs(x_opt))*BUDGET:>12,.0f} {np.sum(x_opt**2)*BUDGET:>10,.0f} {total.mean():>12,.0f}")

print("\n--- Monte Carlo (200k sims) ---")
print(f"  E[PnL]      : ${total.mean():>12,.0f}   ({total.mean()/BUDGET*100:.2f}% of budget)")
print(f"  Std         : ${total.std():>12,.0f}")
print(f"  Sharpe-ish  : {total.mean()/total.std():.3f}")
print(f"  P(PnL > 0)  : {(total>0).mean()*100:.2f}%")
print(f"  P(PnL>+25k) : {(total>25_000).mean()*100:.2f}%")
print(f"  5% VaR      : ${np.percentile(total, 5):>12,.0f}")
print(f"  Median      : ${np.percentile(total,50):>12,.0f}")
print(f"  95th pct    : ${np.percentile(total,95):>12,.0f}")

# === STEP 5: robustness — what if my mus are off by ±30%? ===
print("\n--- Robustness: shock all mus by +/-30% ---")
for shift in [-0.3, -0.15, 0.0, 0.15, 0.3]:
    mu_p = mus * (1 + shift)
    pnl_p = (x_opt * mu_p - x_opt**2) * BUDGET
    print(f"  mu *= {1+shift:.2f}  ->  E[PnL] = ${pnl_p.sum():>10,.0f}")

# === STEP 6: per-product break-even returns ===
print("\n--- Break-even return required (return that yields PnL=0 for that product) ---")
print("    PnL_i = 0  =>  r_i = x_i  (i.e., realized return must equal allocation fraction)")
for i, nm in enumerate(names):
    if abs(x_opt[i]) > 1e-6:
        be = x_opt[i] * 100  # percent
        print(f"  {nm:<20} need realized r {'>' if x_opt[i]>0 else '<'} {be:+.2f}%   "
              f"(my anchor: {mus[i]*100:+.2f}%, margin: {abs(mus[i]*100 - be):.2f}pp)")