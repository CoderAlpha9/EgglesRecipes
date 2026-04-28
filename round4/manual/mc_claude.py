import numpy as np
import time

np.random.seed(42)

# ---------- Environment ----------
S0           = 50.0
r            = 0.0
sigma        = 2.51                       # 251% annualized vol
trading_days = 252
steps_per_day= 4
dt           = 1.0 / (trading_days * steps_per_day)   # 1 / 1008

T1_steps     = 40                         # 2 weeks
T2_steps     = 60                         # 3 weeks

N            = 500_000                    # paths (well above 100k minimum)

# ---------- Path generation (vectorized + antithetic) ----------
t0 = time.time()
half = N // 2
Z_half = np.random.standard_normal((half, T2_steps)).astype(np.float64)
Z      = np.concatenate([Z_half, -Z_half], axis=0)   # antithetic pairs

mu_dt         = (r - 0.5 * sigma**2) * dt
sigma_sqrt_dt = sigma * np.sqrt(dt)

log_inc       = mu_dt + sigma_sqrt_dt * Z
log_S         = np.log(S0) + np.cumsum(log_inc, axis=1)
# Prepend t=0 column
log_S         = np.concatenate([np.full((N, 1), np.log(S0)), log_S], axis=1)
S             = np.exp(log_S)                        # shape (N, 61)

S_T1   = S[:, T1_steps]
S_T2   = S[:, T2_steps]
S_min  = S.min(axis=1)                               # path minimum incl. t=0

# ---------- Payoff functions (r = 0  =>  no discounting) ----------
def stats(payoff):
    fv = payoff.mean()
    se = payoff.std(ddof=1) / np.sqrt(N)
    return fv, se

results = []

# 1. Vanilla Put K=50, 3w
results.append(("AC_50_P",   *stats(np.maximum(50 - S_T2, 0)),   12.00, 12.05))
# 2. Vanilla Call K=50, 3w
results.append(("AC_50_C",   *stats(np.maximum(S_T2 - 50, 0)),   12.00, 12.05))
# 3. Put K=35, 3w
results.append(("AC_35_P",   *stats(np.maximum(35 - S_T2, 0)),    4.33,  4.35))
# 4. Put K=40, 3w
results.append(("AC_40_P",   *stats(np.maximum(40 - S_T2, 0)),    6.50,  6.55))
# 5. Put K=45, 3w
results.append(("AC_45_P",   *stats(np.maximum(45 - S_T2, 0)),    9.05,  9.10))
# 6. Call K=60, 3w
results.append(("AC_60_C",   *stats(np.maximum(S_T2 - 60, 0)),    8.80,  8.85))
# 7. Vanilla Put K=50, 2w
results.append(("AC_50_P_2", *stats(np.maximum(50 - S_T1, 0)),    9.70,  9.75))
# 8. Vanilla Call K=50, 2w
results.append(("AC_50_C_2", *stats(np.maximum(S_T1 - 50, 0)),    9.70,  9.75))

# 9. Chooser - at step 40 becomes whichever has max ITM value
#    S_T1 > 50  -> call ITM > put ITM  -> becomes call
#    S_T1 < 50  -> put  ITM > call ITM -> becomes put
chosen_call   = S_T1 > 50.0
chooser_payoff= np.where(chosen_call,
                         np.maximum(S_T2 - 50, 0),
                         np.maximum(50 - S_T2, 0))
results.append(("AC_50_CO",  *stats(chooser_payoff),             22.20, 22.30))

# 10. Binary Put K=40 -> pays 10 if S_T2 < 40
results.append(("AC_40_BP",  *stats(10.0 * (S_T2 < 40.0)),        5.00,  5.10))

# 11. Down-and-Out Put K=45, Barrier=35
barrier_hit  = (S_min < 35.0)            # "below 35 at ANY discrete step"
ko_payoff    = np.maximum(45 - S_T2, 0) * (~barrier_hit)
results.append(("AC_45_KO",  *stats(ko_payoff),                   0.15, 0.175))

elapsed = time.time() - t0

# ---------- Output ----------
print(f"Paths: {N:,}   |   Steps: {T2_steps}   |   Sim time: {elapsed:.2f}s")
print()
print(f"{'Contract':<10} {'FairValue':>10} {'StdErr':>9} {'Bid':>8} {'Ask':>8} "
      f"{'Edge':>10} {'Decision':<8} {'MaxVol':>7}")
print("-" * 84)

# capture for diagnostic prints
table = []
for name, fv, se, bid, ask in results:
    if fv > ask:
        decision = "BUY"
        edge     = fv - ask
    elif fv < bid:
        decision = "SELL"
        edge     = bid - fv
    else:
        decision = "NONE"
        edge     = 0.0
    vol = 500 if name == "AC_45_KO" else 50
    max_vol = vol if decision != "NONE" else 0
    table.append((name, fv, se, bid, ask, edge, decision, max_vol))
    print(f"{name:<10} {fv:>10.4f} {se:>9.4f} {bid:>8.4f} {ask:>8.4f} "
          f"{edge:>10.4f} {decision:<8} {max_vol:>7d}")

# ---------- Diagnostics for exotics ----------
print()
print("DIAGNOSTICS (high-vol regime sanity checks)")
print("-" * 60)
sigma_sqrtT2 = sigma * np.sqrt(T2_steps * dt)
sigma_sqrtT1 = sigma * np.sqrt(T1_steps * dt)
print(f"sigma*sqrt(T2) = {sigma_sqrtT2:.4f}   sigma*sqrt(T1) = {sigma_sqrtT1:.4f}")
print(f"E[S_T2]  = {S_T2.mean():.4f}    (martingale check, should be ~50)")
print(f"P(barrier 35 hit before T2)        = {barrier_hit.mean():.4%}")
print(f"P(S_T2 < 45 AND barrier NOT hit)   = {((S_T2 < 45) & ~barrier_hit).mean():.4%}")
print(f"P(S_T2 < 40)                       = {(S_T2 < 40).mean():.4%}")
print(f"E[max(K-S_T2,0)| barrier not hit]  conditioned mean payoff = "
      f"{ko_payoff[~barrier_hit].mean() if (~barrier_hit).any() else 0:.4f}")
print(f"Vanilla 45-Put MC                  = "
      f"{np.maximum(45 - S_T2, 0).mean():.4f}")
print(f"Knocked-out value lost (Vanilla45P - KO) = "
      f"{np.maximum(45 - S_T2, 0).mean() - ko_payoff.mean():.4f}")