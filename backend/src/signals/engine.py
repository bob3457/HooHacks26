"""
Signal engine — combines forecast + Monte Carlo output into a plain-English
buy/wait recommendation that a farmer can act on.
"""

from datetime import date


def generate_signal(forecast: dict, mc: dict, ng_change_30d: float) -> dict:
    """
    forecast      : {current, t1, t2, t3, pct_change_t2, ng_current}
    mc            : MonteCarloResult dict
    ng_change_30d : fractional % change in Henry Hub over last 30 days

    Signal thresholds (per spec §8.6):
      BUY_NOW         : pct_change_t2 > 8%  AND prob_rising > 65%
      CONSIDER_BUYING : pct_change_t2 > 4%  OR  prob_rising > 55%
      WAIT            : pct_change_t2 < -4% AND prob_rising < 40%
      NEUTRAL         : default
    """
    pct_change  = forecast["pct_change_t2"]
    prob_rising = mc["prob_rising_t2"]
    current     = forecast["current"]

    if pct_change > 0.08 and prob_rising > 0.65:
        signal  = "BUY_NOW"
        urgency = "HIGH"
        rationale = (
            f"Urea prices are forecast to rise {pct_change*100:.0f}% over the next 60 days "
            f"with {prob_rising*100:.0f}% probability. Consider purchasing inputs soon."
        )
    elif pct_change > 0.04 or prob_rising > 0.55:
        signal  = "CONSIDER_BUYING"
        urgency = "MODERATE"
        rationale = (
            f"Prices lean upward ({pct_change*100:+.0f}% forecast at 60 days) "
            f"but uncertainty is moderate. Partial pre-purchase may make sense."
        )
    elif pct_change < -0.04 and prob_rising < 0.40:
        signal  = "WAIT"
        urgency = "LOW"
        rationale = (
            f"Prices are forecast to soften ({pct_change*100:.0f}% over 60 days). "
            f"Waiting may reduce your input costs."
        )
    else:
        signal  = "NEUTRAL"
        urgency = "LOW"
        rationale = (
            "No strong price signal. Urea prices expected to remain stable. "
            "Monitor weekly and act if nat gas moves more than 10% in either direction."
        )

    ng_dir     = "up" if ng_change_30d >= 0 else "down"
    key_driver = f"Nat gas {ng_dir} {abs(ng_change_30d)*100:.0f}% in 30 days"

    forecast_summary = (
        f"Urea forecast: ${mc['p50_t2']:.0f}/mt in 60 days "
        f"({pct_change*100:+.0f}%) — 80% range: ${mc['p10_t2']:.0f}–${mc['p90_t2']:.0f}"
    )

    # Best month to buy = month with lowest p50 forecast
    months_ahead = {
        "t1": mc["p50_t1"],
        "t2": mc["p50_t2"],
        "t3": mc["p50_t3"],
    }
    best_horizon = min(months_ahead, key=months_ahead.get)
    horizon_labels = {"t1": "Next month", "t2": "In 2 months", "t3": "In 3 months"}
    best_month = horizon_labels[best_horizon]
    best_price = round(months_ahead[best_horizon], 0)

    confidence = round(prob_rising if signal != "WAIT" else 1 - prob_rising, 2)

    return {
        "signal":           signal,
        "urgency":          urgency,
        "recommendation":   signal.replace("_", " ").title(),
        "rationale":        rationale,
        "key_driver":       key_driver,
        "forecast_summary": forecast_summary,
        "confidence":       confidence,
        "as_of_date":       date.today().isoformat(),
        # Price context used by frontend
        "currentPrice":     round(current, 1),
        "bestMonth":        best_month,
        "bestPrice":        best_price,
        "forecast_t1":      round(mc["p50_t1"], 1),
        "forecast_t2":      round(mc["p50_t2"], 1),
        "forecast_t3":      round(mc["p50_t3"], 1),
        "p10_t2":           round(mc["p10_t2"], 1),
        "p90_t2":           round(mc["p90_t2"], 1),
        "prob_rising":      round(prob_rising, 2),
        "ng_current":       round(forecast.get("ng_current", 0), 2),
        "ng_change_30d":    round(ng_change_30d, 4),
    }
