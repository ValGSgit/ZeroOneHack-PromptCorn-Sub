"""
response_model.py — how each persona RESPONDS to an intervention.

These efficacies are *documented synthetic assumptions* (the Track spec explicitly
endorses this: §6 "use synthetic assumptions; document them"). They are derived
directly from the per-persona `best_coach_interventions` hypotheses in
personas.json and the persona briefings:

  Franz  (Online Affine)   — data/price reframing & market comparison work;
                             pushing an advisor BACKFIRES (he closes the tab).
  Judith (Rising Hybrid)   — term explanations, price transparency and
                             reassurance keep her online; respects being helped.
  Peter  (Service Affine)  — a single clear RECOMMENDATION / simplification works;
                             piling on MORE information BACKFIRES (paralysis);
                             brand "we're here for you" copy falls flat (NPS −6).

`hazard_multiplier`  : multiplies the step's leave-hazard (<1 helps, >1 backfires).
`switch_prob`        : P(an advisory-tariff clicker switches to an online tariff).

A NEUTRAL default (≈1.0) is returned for persona/intervention pairs that are not
a good fit — so a mis-targeted coach gets no uplift, which is what penalises poor
intervention quality in the evaluation (spec dimension 3).
"""

from __future__ import annotations

# persona -> intervention_name -> (hazard_multiplier, switch_prob)
EFFICACY = {
    "Franz": {
        "psychological_price_reframe": (0.60, 0.0),
        "market_comparison_signal":    (0.50, 0.0),
        "value_justification":         (0.55, 0.0),
        "suggest_cheaper_tariff":      (0.60, 0.0),
        "save_progress_resume_later":  (0.80, 0.0),
        "suggest_online_tariff":       (0.70, 0.70),   # Opt.Plus/Premium -> Optimal
        "term_glossary":               (0.92, 0.0),
        "advisor_booking_proactive":   (1.25, 0.0),    # BACKFIRE — hates advisor push
        "simplify_recommendation":     (0.90, 0.0),
    },
    "Judith": {
        "term_glossary":               (0.60, 0.0),
        "market_comparison_signal":    (0.65, 0.0),
        "psychological_price_reframe": (0.70, 0.0),
        "value_justification":         (0.55, 0.0),
        "reassurance_transparency":    (0.58, 0.0),
        "suggest_online_tariff":       (0.72, 0.50),
        "suggest_cheaper_tariff":      (0.68, 0.0),
        "save_progress_resume_later":  (0.78, 0.0),
        "simplify_recommendation":     (0.75, 0.0),
        "advisor_booking_proactive":   (0.95, 0.0),    # tolerated, but routes out
    },
    "Peter": {
        "simplify_recommendation":     (0.58, 0.0),
        "psychological_price_reframe": (0.75, 0.0),
        "reassurance_transparency":    (0.82, 0.0),
        "suggest_online_tariff":       (0.70, 0.50),   # Opt.Plus -> Start
        "value_justification":         (0.85, 0.0),
        "save_progress_resume_later":  (0.85, 0.0),
        "term_glossary":               (0.88, 0.0),
        "market_comparison_signal":    (1.15, 0.0),    # BACKFIRE — more info = paralysis
        "trust_badge":                 (0.95, 0.0),    # brand words fall flat (NPS −6)
        "advisor_booking_proactive":   (0.80, 0.0),    # genuinely welcome, but routes out
    },
}

NEUTRAL = (1.0, 0.0)


def efficacy(persona: str, intervention_name: str) -> tuple[float, float]:
    return EFFICACY.get(persona, {}).get(intervention_name, NEUTRAL)
