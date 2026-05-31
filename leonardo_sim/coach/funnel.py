"""
funnel.py — calibrated probabilistic journey simulator (spec Demo Option 4).

A persona walks the 7 in-scope steps. Each step carries a latent *friction*
f∈[0,1]; the user leaves when f crosses the calibrated hazard threshold. The
SAME f drives the behavioural signals (signals.py), so signals predict leaving.

Key design choice — COMMON RANDOM NUMBERS: a journey's randomness is drawn ONCE
into a `Plan`. The plan is then `resolve`d under different policies (no-coach
baseline vs. coach). Because friction, signals, surcharge and coin flips are
shared, the baseline and coach runs are perfectly paired — which is exactly what
fair before/after measurement and clean trigger precision/recall require
(spec §8: "fair baseline comparisons require identical persona seeds").

Run `python -m coach.funnel --calibrate` to verify the baseline reproduces the
real funnel (≈66 % / ≈78 % drop, ≈5.6 % conversion).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from . import config as C
from .signals import draw_signals, StepSignals


# --------------------------------------------------------------------------- #
# What the coach observes, and what it may do                                  #
# --------------------------------------------------------------------------- #

@dataclass
class Observation:
    persona_hint: Optional[str]      # None at run time unless segment is known
    step: int
    step_name: str
    signals: StepSignals
    cumulative_time_s: float
    tariff_clicked: Optional[str]    # incl. Opt.Plus/Premium ("advisory" click)
    advisory_click: bool             # clicked an advisory-only tariff at step 4
    provisional_price: Optional[float]
    final_price: Optional[float]
    price_delta_pct: Optional[float]


@dataclass
class Intervention:
    name: str
    category: str
    message: str
    hazard_multiplier: float = 1.0   # <1 reduces leave hazard, >1 = backfire
    switch_prob: float = 0.0         # P(advisory-click user switches to Optimal)


class Policy:
    """Baseline policy: never intervenes, never routes proactively."""
    def act(self, obs: Observation) -> Optional[Intervention]:
        return None


# --------------------------------------------------------------------------- #
# Pre-drawn randomness for one journey                                         #
# --------------------------------------------------------------------------- #

@dataclass
class Plan:
    persona: str
    friction: dict          # step -> f
    route_coin: dict        # step -> U(0,1)  (abandon vs advisor-route split)
    save_coin: dict         # step -> U(0,1)  (advisory-switch resolution)
    signals: dict           # step -> StepSignals
    oos1: bool              # selected hospital/both at step 1
    oos2: bool              # selected "other persons" at step 2
    oos4: bool              # clicked Opt.Plus/Premium at step 4
    tariff: str             # chosen online tariff (if not oos4)
    surcharge: float        # final-price risk surcharge fraction


def make_plan(rng: np.random.Generator, persona: str) -> Plan:
    fr = {s: float(rng.random()) for s in C.STEP_ORDER}
    rc = {s: float(rng.random()) for s in C.STEP_ORDER}
    sc = {s: float(rng.random()) for s in C.STEP_ORDER}
    sig = {s: draw_signals(rng, persona, s, fr[s]) for s in C.STEP_ORDER}
    oos = C.OOS_SELECT[persona]
    oos1 = rng.random() < oos.get(1, 0.0)
    oos2 = rng.random() < oos.get(2, 0.0)
    oos4 = rng.random() < oos.get(4, 0.0)
    tariff = C.PREFERRED_ONLINE_TARIFF[persona] if rng.random() < 0.7 else \
        rng.choice(C.ONLINE_TARIFFS)
    surch = float(rng.choice([s for s, _ in C.SURCHARGE_SCENARIOS],
                             p=[w for _, w in C.SURCHARGE_SCENARIOS]))
    return Plan(persona, fr, rc, sc, sig, oos1, oos2, oos4, str(tariff), surch)


# --------------------------------------------------------------------------- #
# Resolution under a policy                                                    #
# --------------------------------------------------------------------------- #

@dataclass
class StepRecord:
    step: int
    step_name: str
    signals: StepSignals
    cumulative_time_s: float
    tariff: Optional[str]
    advisory_click: bool
    provisional_price: Optional[float]
    final_price: Optional[float]
    price_delta_pct: Optional[float]
    left_here: bool                  # abandoned/routed at this step
    routed: bool                     # the leave was an advisor route
    forced_oos: bool = False         # leave forced by an out-of-scope selection
    counterfactual_leave: bool = False   # would-leave with NO coach (set by eval)
    intervention: Optional[Intervention] = None


@dataclass
class Result:
    persona: str
    outcome: str                     # converted | abandoned | advisor_routed
    final_step: int
    steps: list = field(default_factory=list)
    interventions: list = field(default_factory=list)


def _base_hazard(persona: str, step: int, surcharge: float) -> float:
    h = C.BASE_HAZARD[persona][step]
    if step == 7:                    # unexpected final-price jump adds friction
        h = min(0.99, h + C.SURCHARGE_SENSITIVITY[persona] * surcharge)
    return h


def baseline_would_leave(plan: Plan, step: int) -> bool:
    """Counterfactual: would the user leave at this step with NO coach?
    Path-independent (uses the plan's pre-drawn randomness), so it is the clean
    reference for trigger precision/recall even when the coach kept the user
    alive past where the baseline would have dropped."""
    if step == 1 and plan.oos1:
        return True
    if step == 2 and plan.oos2:
        return True
    if step == 4 and plan.oos4:
        return True
    h = _base_hazard(plan.persona, step, plan.surcharge)
    return plan.friction[step] >= (1.0 - h)


def resolve(plan: Plan, policy: Policy) -> Result:
    persona = plan.persona
    res = Result(persona=persona, outcome="abandoned", final_step=C.STEP_ORDER[0])
    cum = 0.0
    tariff: Optional[str] = None
    provisional = final = delta = None

    for step in C.STEP_ORDER:
        sig = plan.signals[step]
        cum += sig.time_on_step_s
        res.final_step = step

        advisory_click = False
        # ---- forced out-of-scope selections (clean advisor route, not coached) ----
        forced_route = False
        if step == 1 and plan.oos1:
            forced_route = True
        elif step == 2 and plan.oos2:
            forced_route = True
        elif step == 4:
            tariff = plan.tariff
            provisional = C.TARIFF_PRICES[tariff]
            if plan.oos4:
                advisory_click = True
                tariff = "Opt.Plus"          # what they clicked
                provisional = C.TARIFF_PRICES[tariff]
        elif step == 7:
            if provisional is None:
                tariff = tariff or "Optimal"
                provisional = C.TARIFF_PRICES[tariff]
            delta = round(plan.surcharge, 4)
            final = round(provisional * (1 + plan.surcharge), 2)

        obs = Observation(
            persona_hint=None, step=step, step_name=C.STEP_NAMES[step], signals=sig,
            cumulative_time_s=round(cum, 1), tariff_clicked=tariff,
            advisory_click=advisory_click, provisional_price=provisional,
            final_price=final, price_delta_pct=delta,
        )
        interv = policy.act(obs)
        if interv is not None:
            res.interventions.append((step, interv))

        rec = StepRecord(
            step=step, step_name=C.STEP_NAMES[step], signals=sig,
            cumulative_time_s=round(cum, 1), tariff=tariff, advisory_click=advisory_click,
            provisional_price=provisional, final_price=final, price_delta_pct=delta,
            left_here=False, routed=False, intervention=interv,
        )

        # ---- advisory-tariff click: coach may steer back to an online tariff ----
        if advisory_click:
            switched = interv is not None and plan.save_coin[step] < interv.switch_prob
            if switched:
                tariff = "Optimal"
                provisional = C.TARIFF_PRICES[tariff]
                rec.tariff = tariff
                rec.provisional_price = provisional
                rec.advisory_click = False
                advisory_click = False
            else:
                forced_route = True

        if forced_route:
            rec.left_here = True
            rec.routed = True
            rec.forced_oos = True
            res.steps.append(rec)
            res.outcome = "advisor_routed"
            break

        # ---- normal hazard resolution (coach may lower the hazard) ----
        h = _base_hazard(persona, step, plan.surcharge)
        if interv is not None:
            h = max(0.0, min(0.999, h * interv.hazard_multiplier))
        leave = plan.friction[step] >= (1.0 - h)

        if leave:
            routed = plan.route_coin[step] < C.ROUTE_FRACTION[persona][step]
            rec.left_here = True
            rec.routed = routed
            res.steps.append(rec)
            res.outcome = "advisor_routed" if routed else "abandoned"
            break

        res.steps.append(rec)
        if step == C.STEP_ORDER[-1]:
            res.outcome = "converted"

    return res


# --------------------------------------------------------------------------- #
# Calibration check                                                            #
# --------------------------------------------------------------------------- #

def calibration_report(n_per_persona: int = 20000, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    pol = Policy()
    agg = {"reach": {s: 0.0 for s in C.STEP_ORDER},
           "leave": {s: 0.0 for s in C.STEP_ORDER}}
    per_persona = {}
    total_w_conv = 0.0
    for persona, w in C.PERSONA_MIX.items():
        conv = routed = aband = 0
        reach = {s: 0 for s in C.STEP_ORDER}
        leave = {s: 0 for s in C.STEP_ORDER}
        for _ in range(n_per_persona):
            r = resolve(make_plan(rng, persona), pol)
            for rec in r.steps:
                reach[rec.step] += 1
                if rec.left_here:
                    leave[rec.step] += 1
            conv += r.outcome == "converted"
            routed += r.outcome == "advisor_routed"
            aband += r.outcome == "abandoned"
        cr = conv / n_per_persona
        per_persona[persona] = {"conversion": cr, "advisor_routed": routed / n_per_persona,
                                "abandoned": aband / n_per_persona}
        total_w_conv += w * cr
        for s in C.STEP_ORDER:
            agg["reach"][s] += w * reach[s] / n_per_persona
            agg["leave"][s] += w * leave[s] / n_per_persona
    cond_drop = {s: (agg["leave"][s] / agg["reach"][s] if agg["reach"][s] else 0.0)
                 for s in C.STEP_ORDER}
    return {"overall_conversion": total_w_conv, "per_persona": per_persona,
            "conditional_drop": cond_drop}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("-n", type=int, default=20000)
    ap.parse_args()
    rep = calibration_report(n_per_persona=20000)
    print(f"\nOverall online conversion : {rep['overall_conversion']*100:5.2f} %   "
          f"(target {C.TARGET_OVERALL_CONVERSION*100:.1f} %)")
    print("\nConditional drop-off per step (target 66% @4, 78% @7):")
    for s in C.STEP_ORDER:
        tgt = C.CRITICAL_STEPS.get(s)
        tag = f"  <- target {tgt*100:.0f}%" if tgt else ""
        print(f"  step {s:>2} {C.STEP_NAMES[s]:22s} {rep['conditional_drop'][s]*100:5.1f}%{tag}")
    print("\nPer-persona online conversion:")
    for p, d in rep["per_persona"].items():
        print(f"  {p:7s} conv={d['conversion']*100:5.2f}%  "
              f"routed={d['advisor_routed']*100:4.1f}%  aband={d['abandoned']*100:4.1f}%")
