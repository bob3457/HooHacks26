"""
Monte Carlo simulation engine — vectorized, 10,000 draws from the residual
distribution captured during walk-forward cross-validation.
"""

import numpy as np


def run_monte_carlo(
    forecast: dict,
    metadata: dict,
    n_simulations: int = 10_000,
    random_seed: int = 42,
) -> dict:
    """
    forecast : dict with keys 'current', 't1', 't2', 't3'
    metadata : model_metadata.json dict (must contain residual_mean/std per horizon)

    For each simulated path: add a draw from N(residual_mean, residual_std)
    to the point forecast, clip to physically plausible range ($100–$2000/mt).

    Returns percentile bands + probability metrics + full t2 distribution
    (sampled to 1000 values for JSON serialisation).
    """
    rng = np.random.default_rng(random_seed)

    # Vectorised draws — all 10,000 at once
    e1 = rng.normal(metadata["residual_mean_t1"], metadata["residual_std_t1"], n_simulations)
    e2 = rng.normal(metadata["residual_mean_t2"], metadata["residual_std_t2"], n_simulations)
    e3 = rng.normal(metadata["residual_mean_t3"], metadata["residual_std_t3"], n_simulations)

    sim_t1 = np.clip(forecast["t1"] + e1, 100, 2000)
    sim_t2 = np.clip(forecast["t2"] + e2, 100, 2000)
    sim_t3 = np.clip(forecast["t3"] + e3, 100, 2000)

    current = forecast["current"]

    return {
        "n_simulations": n_simulations,
        # T+1 (30 day)
        "p10_t1": float(np.percentile(sim_t1, 10)),
        "p25_t1": float(np.percentile(sim_t1, 25)),
        "p50_t1": float(np.percentile(sim_t1, 50)),
        "p75_t1": float(np.percentile(sim_t1, 75)),
        "p90_t1": float(np.percentile(sim_t1, 90)),
        # T+2 (60 day)
        "p10_t2": float(np.percentile(sim_t2, 10)),
        "p25_t2": float(np.percentile(sim_t2, 25)),
        "p50_t2": float(np.percentile(sim_t2, 50)),
        "p75_t2": float(np.percentile(sim_t2, 75)),
        "p90_t2": float(np.percentile(sim_t2, 90)),
        # T+3 (90 day)
        "p10_t3": float(np.percentile(sim_t3, 10)),
        "p50_t3": float(np.percentile(sim_t3, 50)),
        "p90_t3": float(np.percentile(sim_t3, 90)),
        # Probability metrics
        "prob_rising_t2":         float(np.mean(sim_t2 > current)),
        "prob_10pct_increase_t2": float(np.mean(sim_t2 > current * 1.10)),
        "prob_20pct_increase_t2": float(np.mean(sim_t2 > current * 1.20)),
        # Full t2 distribution — every 10th value = 1000 points for histogram
        "sim_t2_distribution": sim_t2[::10].tolist(),
    }
