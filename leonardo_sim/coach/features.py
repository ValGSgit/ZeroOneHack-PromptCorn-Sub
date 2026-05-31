"""
features.py — the single feature definition shared by the classifier (training)
and the coach (inference). Keeping one builder guarantees the "coach's brain"
sees identical features at train and run time (no train/serve skew).

Only signals observable AT the moment of the decision are used — no leakage from
the journey outcome or future steps.
"""

from __future__ import annotations

FEATURE_COLUMNS = [
    "step",
    "time_on_step_s",
    "cumulative_time_s",
    "n_hesitation_events",
    "n_back_clicks",
    "opened_competitor_tab",
    "advisory_click",
    "provisional_price",
    "price_delta_pct",
    "cum_hesitation_events",
    "cum_back_clicks",
    "is_price_step",
]


def build_features(step, time_on_step_s, cumulative_time_s, n_hesitation_events,
                   n_back_clicks, opened_competitor_tab, advisory_click,
                   provisional_price, price_delta_pct,
                   cum_hesitation_events, cum_back_clicks) -> dict:
    return {
        "step": int(step),
        "time_on_step_s": float(time_on_step_s),
        "cumulative_time_s": float(cumulative_time_s),
        "n_hesitation_events": float(n_hesitation_events),
        "n_back_clicks": float(n_back_clicks),
        "opened_competitor_tab": float(opened_competitor_tab),
        "advisory_click": float(1 if advisory_click else 0),
        "provisional_price": float(provisional_price or 0.0),
        "price_delta_pct": float(price_delta_pct or 0.0),
        "cum_hesitation_events": float(cum_hesitation_events),
        "cum_back_clicks": float(cum_back_clicks),
        "is_price_step": float(1 if int(step) in (4, 7) else 0),
    }


def row_to_vector(feat: dict) -> list:
    return [feat[c] for c in FEATURE_COLUMNS]
