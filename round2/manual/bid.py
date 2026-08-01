import scipy.stats as stats

def expected_speed_multiplier(my_bid, psychology_profile="anchored"):
    """
    Models the expected Speed Multiplier based on opponent psychology.
    my_bid: your investment in speed (0 to 100)
    """
    # Define alpha and beta for different psychological profiles
    profiles = {
        "random": (1, 1),           # Flat distribution
        "anchored": (5, 5),         # Bell curve centered at 50
        "conservative": (2, 5),     # Skewed towards 20-30
        "aggressive": (5, 2),       # Skewed towards 70-80
        "extreme_anchored": (10, 10)# Tight cluster exactly at 50
    }
    
    alpha, beta = profiles.get(psychology_profile, (5, 5))
    
    # Normalize bid to 0.0 - 1.0 for the Beta function
    x = my_bid / 100.0
    
    # Calculate the percentile (the expected % of people you beat)
    percentile = stats.beta.cdf(x, alpha, beta)
    
    # Map the percentile to the 0.1 to 0.9 multiplier range
    multiplier = 0.1 + (0.8 * percentile)
    
    return multiplier

# Example Usage:
bid = 11
print(f"Random crowd expected multiplier: {expected_speed_multiplier(bid, 'random'):.3f}")
print(f"Anchored crowd expected multiplier: {expected_speed_multiplier(bid, 'anchored'):.3f}")
print(f"Extreme anchored crowd expected multiplier: {expected_speed_multiplier(bid, 'extreme_anchored'):.3f}")
print(f"Conservative crowd expected multiplier: {expected_speed_multiplier(bid, 'conservative'):.3f}")
print(f"Aggressive crowd expected multiplier: {expected_speed_multiplier(bid, 'aggressive'):.3f}")