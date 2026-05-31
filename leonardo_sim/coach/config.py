"""
config.py — single source of truth for the UNIQA Conversion-Coach simulation.

Everything the calibrated funnel, the classifier, the coach and the evaluator
need is declared here so the numbers are auditable in one place (spec §10:
"reproducibility and clarity of evaluation").

The funnel is a probabilistic state machine (spec Demo Option 4) whose per-step
abandonment hazards are CALIBRATED so the no-coach baseline reproduces UNIQA's
real funnel:

    initial-price drop  (step 4) ≈ 66 %
    final-price  drop   (step 7) ≈ 78 %
    overall online conversion    ≈ 5.6 %

Behavioural signals (dwell, hesitation, back-clicks, competitor tab) are drawn
from a latent per-step "friction" so they are genuinely predictive of the
abandonment label — that is what gives the classifier ("the coach's brain")
something real to learn, and what the coach observes at run time.
"""

from __future__ import annotations

# The authoritative segmentation/funnel facts live in personas.js and are loaded
# by coach.persona_config. We import the numeric baselines from there so there is
# a single source of truth; the calibrated per-step hazards below stay local
# because they are tuning parameters, not survey facts.
from . import persona_config as PC

# --------------------------------------------------------------------------- #
# Product / funnel facts (Track spec + uniqa-funnel-doc)                       #
# --------------------------------------------------------------------------- #

TARIFF_PRICES = {"Start": 38.74, "Optimal": 68.14, "Opt.Plus": 96.66, "Premium": 140.16}
ONLINE_TARIFFS = ("Start", "Optimal")          # the only conversion targets
ADVISORY_TARIFFS = ("Opt.Plus", "Premium")     # clicking these => advisor route (clean exit)

# In-scope private-doctor / "myself only" path. Step 5 (hospital add-ons) is
# out of scope and never reached on this path.
STEP_ORDER = [1, 2, 3, 4, 6, 7, 12]
STEP_NAMES = {
    1: "coverage_selection",
    2: "for_whom",
    3: "personal_data",
    4: "tariff_initial_price",
    6: "health_questions",
    7: "final_price",
    12: "closing",
}
# The two graded drop-off steps and their real conditional drop targets,
# and the overall online-conversion baseline — all sourced from personas.js.
CRITICAL_STEPS = dict(PC.CRITICAL_STEPS)              # {4: 0.66, 7: 0.78}
TARGET_OVERALL_CONVERSION = PC.TARGET_OVERALL_CONVERSION   # 0.056

# Segment mix of online-funnel traffic (personas.js shared_context).
PERSONA_MIX = dict(PC.PERSONA_MIX)                    # {"Franz":0.50,"Judith":0.30,"Peter":0.20}
# Segment labels match the simulator's CSV `segment` column (singular spelling).
SEGMENTS = {
    "Franz": "segment_2_online_affine",
    "Judith": "segment_1_rising_hybrid",
    "Peter": "segment_3_service_affine",
}

# --------------------------------------------------------------------------- #
# Calibrated baseline hazards   P(leave at step | reached step), no coach.     #
# "leave" = abandon OR self-route to advisor at that step.                     #
# Shapes encode the archetypes (verified against the targets by               #
# `python -m coach.funnel --calibrate`):                                       #
#   Franz  — blasts early steps, primary drop at FINAL price (step 7)          #
#   Judith — primary drop at INITIAL price (step 4); also wobbles at final     #
#   Peter  — overwhelmed EARLY (steps 1/3) and at the price wall               #
# --------------------------------------------------------------------------- #

BASE_HAZARD = {
    "Franz":  {1: 0.02, 2: 0.02, 3: 0.03, 4: 0.45, 6: 0.05, 7: 0.78, 12: 0.06},
    "Judith": {1: 0.03, 2: 0.04, 3: 0.03, 4: 0.77, 6: 0.05, 7: 0.60, 12: 0.08},
    "Peter":  {1: 0.09, 2: 0.05, 3: 0.10, 4: 0.79, 6: 0.08, 7: 0.64, 12: 0.10},
}

# Share of a step's "leave" events that are advisor routes (vs silent abandon).
# Out-of-scope selections (hospital / other-persons / Opt.Plus / Premium) always
# route; this captures the *remaining* "I'll just call them" routing intent.
ROUTE_FRACTION = {
    "Franz":  {1: 0.3, 2: 0.3, 3: 0.0, 4: 0.4, 6: 0.0, 7: 0.1, 12: 0.0},
    "Judith": {1: 0.5, 2: 0.6, 3: 0.1, 4: 0.6, 6: 0.1, 7: 0.4, 12: 0.2},
    "Peter":  {1: 0.6, 2: 0.6, 3: 0.4, 4: 0.7, 6: 0.4, 7: 0.5, 12: 0.3},
}

# Probability a persona actively selects an OUT-OF-SCOPE option (forces a clean
# advisor route regardless of hazard): hospital/both at step 1, "other" at
# step 2, Opt.Plus/Premium at step 4.
OOS_SELECT = {
    "Franz":  {1: 0.04, 2: 0.03, 4: 0.12},
    "Judith": {1: 0.07, 2: 0.08, 4: 0.24},
    "Peter":  {1: 0.12, 2: 0.07, 4: 0.18},
}

# Final-price risk surcharge applied at step 7 (provisional → final price).
# (surcharge_fraction, weight). A bigger jump raises step-7 friction.
SURCHARGE_SCENARIOS = [(0.00, 0.20), (0.04, 0.34), (0.10, 0.26), (0.18, 0.14), (0.30, 0.06)]

# How strongly an unexpected final-price jump adds to step-7 hazard, per persona
# (Franz & Judith are explicitly price-gap sensitive; Peter less so — he's
# already overwhelmed by then). Added hazard = SURCHARGE_SENSITIVITY * surcharge.
SURCHARGE_SENSITIVITY = {"Franz": 0.6, "Judith": 0.5, "Peter": 0.3}

# Which tariff each persona gravitates to online (used for price reframing copy).
PREFERRED_ONLINE_TARIFF = {"Franz": "Optimal", "Judith": "Optimal", "Peter": "Start"}
