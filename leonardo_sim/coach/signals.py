"""
signals.py — behavioural-signal model for the calibrated funnel.

Each step a user reaches has a latent *friction* f ∈ [0,1] (drawn in funnel.py).
The user leaves the step when f crosses the calibrated hazard threshold, and the
SAME f drives the observable behavioural signals — so high-friction users both
leave more AND emit stronger signals. That coupling is what makes the signals
genuinely predictive (the classifier learns f from its noisy proxies) and what
the coach reacts to at run time.

Signal magnitudes are grounded in the ranges observed in the LLM persona runs
(data_*.csv) and in the per-persona behavioural hypotheses in personas.json
(e.g. Peter: long dwell + back-navigation early; Franz: competitor tabs at
price screens; Judith: hesitation/hover on unfamiliar terms).
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass
class StepSignals:
    time_on_step_s: int
    n_hesitation_events: int
    n_back_clicks: int
    opened_competitor_tab: int


# Per (persona, step): signal ceilings reached as friction f → 1.
# (dwell_base_s, dwell_span_s, hesitation_max, backclick_max, competitor_prob_max)
# dwell ≈ dwell_base + f*dwell_span ; counts ≈ round(f*max) ; tab ~ Bernoulli(f*prob)
_P = {
    "Franz": {
        1:  (5, 6, 1, 0, 0.02),
        2:  (4, 4, 1, 0, 0.00),
        3:  (8, 8, 2, 1, 0.02),
        4:  (12, 70, 5, 2, 0.55),   # reads tariffs, opens competitor tab
        6:  (20, 30, 4, 1, 0.06),
        7:  (8, 40, 4, 2, 0.45),    # sticks on final price, compares
        12: (15, 25, 2, 1, 0.05),
    },
    "Judith": {
        1:  (6, 5, 1, 0, 0.00),
        2:  (5, 4, 1, 0, 0.00),
        3:  (9, 10, 2, 1, 0.00),
        4:  (12, 55, 8, 3, 0.10),   # hovers terms, re-reads, hesitates a lot
        6:  (25, 35, 6, 2, 0.02),
        7:  (10, 45, 6, 3, 0.05),
        12: (14, 22, 3, 1, 0.00),
    },
    "Peter": {
        1:  (7, 18, 4, 2, 0.00),    # overwhelmed *early*: long dwell + back-nav
        2:  (5, 8, 2, 1, 0.00),
        3:  (10, 22, 5, 3, 0.00),
        4:  (10, 40, 6, 4, 0.00),   # too many numbers, no "recommended for you"
        6:  (15, 30, 6, 3, 0.00),
        7:  (9, 30, 4, 2, 0.04),
        12: (10, 18, 3, 1, 0.00),
    },
}


def draw_signals(rng, persona: str, step: int, friction: float) -> StepSignals:
    base, span, hes_max, back_max, comp_max = _P[persona][step]
    # multiplicative noise so the signal↔friction link is strong but not perfect
    noise = rng.lognormal(mean=0.0, sigma=0.25)
    dwell = base + friction * span * noise
    hes = rng.binomial(hes_max, min(0.95, 0.15 + 0.8 * friction))
    back = rng.binomial(back_max, min(0.9, 0.05 + 0.7 * friction))
    comp = 1 if rng.random() < comp_max * (0.3 + 0.7 * friction) else 0
    return StepSignals(
        time_on_step_s=max(1, int(round(dwell))),
        n_hesitation_events=int(hes),
        n_back_clicks=int(back),
        opened_competitor_tab=int(comp),
    )
