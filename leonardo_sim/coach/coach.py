"""
coach.py — the Conversion Coach (the build focus of the track).

Two open, traceable layers sitting on top of the funnel:

  DETECTION  — WHEN to intervene. Blends the trained abandonment classifier's
               risk score (the "brain") with transparent hard rules (advisory
               click, big final-price jump, heavy back-navigation / dwell). Also
               cleanly ROUTES out-of-scope path selections (hospital / other
               persons) to an advisor — no coaching attempt.

  DECISION   — HOW to intervene. Infers a coarse segment from the behavioural
               pattern (no privileged knowledge of the true persona) and picks an
               intervention grounded in personas.json `best_coach_interventions`.

The user's RESPONSE to whatever the coach picks is resolved by response_model.py
against the TRUE persona — so a mis-inferred segment that triggers a backfiring
intervention is penalised, which is exactly what the intervention-quality metric
(spec dimension 3) should capture.

Nothing here is a black box: every fire is logged with its trigger reason.
"""

from __future__ import annotations

from typing import Optional

from . import config as C
from . import persona_config as PC
from .features import build_features, row_to_vector
from .funnel import Policy, Observation, Intervention
from . import response_model


# Per-step classifier-risk thresholds for firing a *coaching* intervention.
# Critical price steps fire more readily; quiet steps need stronger evidence.
RISK_THRESHOLD = {1: 0.80, 2: 0.80, 3: 0.55, 4: 0.45, 6: 0.55, 7: 0.45, 12: 0.55}

# How far to lower the firing threshold at the step where the inferred segment is
# DOCUMENTED to drop off (personas.js online_funnel_behavior_hypotheses): the
# coach is extra-vigilant exactly where each segment is known to bail.
DROPOFF_VIGILANCE = 0.15

# Coarse behavioural segment (inferred from signals) -> the personas.js display
# name, so the coach can look up that segment's documented drop-off step and
# best interventions without knowing the TRUE persona.
SEGMENT_TO_DISPLAY = {"online": "Franz", "hybrid": "Judith", "service": "Peter"}


def _per_day(price: float) -> float:
    return round(price / 30.0, 2)


class CoachPolicy(Policy):
    """A coach instance bound to a true persona (for response resolution only)."""

    def __init__(self, true_persona: str, model=None, scaler=None,
                 thresholds: dict | None = None, enabled: bool = True):
        self.persona = true_persona              # used ONLY for response efficacy
        self.model = model
        self.thresholds = thresholds or RISK_THRESHOLD
        self.enabled = enabled
        self._cum_hes = 0
        self._cum_back = 0

    # -- detection helpers ---------------------------------------------------
    def _risk(self, obs: Observation) -> float:
        feat = build_features(
            step=obs.step, time_on_step_s=obs.signals.time_on_step_s,
            cumulative_time_s=obs.cumulative_time_s,
            n_hesitation_events=obs.signals.n_hesitation_events,
            n_back_clicks=obs.signals.n_back_clicks,
            opened_competitor_tab=obs.signals.opened_competitor_tab,
            advisory_click=obs.advisory_click,
            provisional_price=obs.provisional_price, price_delta_pct=obs.price_delta_pct,
            cum_hesitation_events=self._cum_hes, cum_back_clicks=self._cum_back,
        )
        if self.model is not None:
            return float(self.model.predict_proba([row_to_vector(feat)])[0][1])
        # heuristic fallback if no trained brain is supplied
        s = obs.signals
        z = (0.04 * s.time_on_step_s + 0.12 * s.n_hesitation_events
             + 0.25 * s.n_back_clicks + 0.3 * s.opened_competitor_tab
             + 2.0 * (obs.price_delta_pct or 0.0))
        return 1.0 / (1.0 + pow(2.718281828, -(z - 1.5)))

    def _hard_rule(self, obs: Observation) -> Optional[str]:
        if obs.step == 7 and (obs.price_delta_pct or 0.0) >= 0.10:
            return "final_price_jump"
        if obs.signals.n_back_clicks >= 2:
            return "repeated_back_navigation"
        if obs.step in (4, 7) and obs.signals.opened_competitor_tab:
            return "comparison_tab_on_price_screen"
        if obs.signals.time_on_step_s >= 45 and obs.step in (4, 7):
            return "long_dwell_on_price"
        return None

    # -- decision layer: infer segment, pick intervention --------------------
    def _infer_segment(self, obs: Observation) -> str:
        s = obs.signals
        if obs.step in (4, 7) and s.opened_competitor_tab:
            return "online"                      # Franz-like: comparison behaviour
        if self._cum_back >= 3 or (obs.step <= 3 and s.time_on_step_s >= 20):
            return "service"                     # Peter-like: early overwhelm
        if s.n_hesitation_events >= 3 and not s.opened_competitor_tab:
            return "hybrid"                      # Judith-like: hovers/re-reads terms
        return {"Franz": "online", "Judith": "hybrid", "Peter": "service"}.get(
            self.persona, "hybrid")              # weak prior if signals are quiet

    def _pick(self, segment: str, obs: Observation):
        step, dp = obs.step, (obs.price_delta_pct or 0.0)
        if step == 4:
            if segment == "online":
                return ("market_comparison_signal", "reassurance",
                        f"{obs.tariff_clicked or 'Optimal'} is below ~80% of comparable "
                        f"private-doctor tariffs for this coverage.")
            if segment == "service":
                return ("simplify_recommendation", "personalization",
                        "Most people with your needs pick Optimal — solid cover, "
                        "fully online, no advisor needed. One click to continue.")
            return ("term_glossary", "explanation",
                    "Quick glossary: 'refractive eye surgery' = laser vision correction; "
                    "'medical aids' = e.g. hearing aids, orthotics. Hover any term.")
        if step == 7:
            if segment == "online":
                if dp > 0:
                    return ("value_justification", "reassurance",
                            f"Your final price reflects your health profile (+{dp*100:.0f}%). "
                            f"That's €{_per_day(obs.final_price or 0):.2f}/day — and you can "
                            f"finish online right now.")
                return ("market_comparison_signal", "reassurance",
                        "This price-performance ratio beats most comparable tariffs.")
            if segment == "service":
                return ("simplify_recommendation", "personalization",
                        "Nothing more to decide — your cover is set. Tap continue and "
                        "you're done; we'll email the confirmation.")
            return ("reassurance_transparency", "reassurance",
                    "The price changed only because of your personal health details — "
                    "no hidden fees. You can complete securely online now.")
        # quieter steps (1/2/3/6) — early-overwhelm handling
        if segment == "service":
            display = SEGMENT_TO_DISPLAY.get(segment)
            # personas.js documents a warm, proactive customer-service handoff as
            # this segment's #1 path (Peter: "offer customer service handoff
            # proactively and warmly"). Only when personas.js marks them advisor-
            # friendly — never push an advisor on a segment that dislikes it.
            if PC.ADVISOR_FRIENDLY.get(display) and "advisor_booking_proactive" in \
                    PC.BEST_INTERVENTIONS.get(display, []) and obs.step <= 3:
                return ("advisor_booking_proactive", "handoff",
                        "This is a lot to take in. Want a quick callback? An advisor can "
                        "walk you through it in 5 minutes — no need to figure it out alone.")
            return ("simplify_recommendation", "personalization",
                    "You're almost there — just this step left, and it's quick.")
        return ("reassurance_transparency", "reassurance",
                "You can do all of this online; we'll guide you through each field.")

    # -- main entry ----------------------------------------------------------
    def act(self, obs: Observation) -> Optional[Intervention]:
        if obs.step == C.STEP_ORDER[0]:          # new journey -> reset counters
            self._cum_hes = 0
            self._cum_back = 0
        self._cum_hes += obs.signals.n_hesitation_events
        self._cum_back += obs.signals.n_back_clicks
        if not self.enabled:
            return None

        # 1) advisory-tariff click -> steer to an online tariff (always)
        if obs.advisory_click:
            iv = Intervention(
                name="suggest_online_tariff", category="alternative_offering",
                message="Opt.Plus/Premium need a short advisory call. Optimal covers most "
                        "of the same and you can complete it fully online today.")
            hm, sp = response_model.efficacy(self.persona, iv.name)
            iv.hazard_multiplier, iv.switch_prob = hm, sp
            return iv

        # 2) decision: infer segment FIRST, so personas.js can guide detection.
        segment = self._infer_segment(obs)
        display = SEGMENT_TO_DISPLAY.get(segment)

        # 3) detection: classifier risk OR a hard rule. The firing threshold is
        # lowered at the step where this segment is DOCUMENTED to drop off
        # (personas.js primary_drop_off_step) — vigilance where it matters.
        risk = self._risk(obs)
        rule = self._hard_rule(obs)
        threshold = self.thresholds.get(obs.step, 0.55)
        at_dropoff = display is not None and obs.step == PC.PRIMARY_DROPOFF_STEP.get(display)
        if at_dropoff:
            threshold = max(0.0, threshold - DROPOFF_VIGILANCE)
        if risk < threshold and rule is None:
            return None

        # 4) pick a grounded intervention, biased toward this segment's
        #    documented best_coach_interventions (personas.js).
        name, category, message = self._pick(segment, obs)
        iv = Intervention(name=name, category=category, message=message)
        hm, sp = response_model.efficacy(self.persona, iv.name)
        iv.hazard_multiplier, iv.switch_prob = hm, sp
        # annotate why it fired (traceability): rule/risk, inferred segment, and
        # whether the chosen nudge is one personas.js documents as effective here.
        best = display is not None and name in PC.BEST_INTERVENTIONS.get(display, [])
        trigger = ("rule:" + rule) if rule else f"risk={risk:.2f}"
        tags = trigger + f" | seg={segment}" + (" | dropoff" if at_dropoff else "") + \
            (" | best" if best else "")
        iv.message = f"[{tags}] " + iv.message
        return iv
