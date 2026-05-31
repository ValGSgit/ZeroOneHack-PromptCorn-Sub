#!/usr/bin/env python3
"""
simulate.py — run cohorts through the calibrated funnel and emit data.

Two uses:

  # 1) Emit the no-coach baseline TRAINING dataset (per-step rows, labelled).
  python simulate.py baseline --n 8000 --seed 11 --out artifacts/baseline_steps.csv

  # 2) Paired baseline-vs-coach cohort on the SAME plans (common random numbers)
  #    -> used by evaluate.py; can also be called directly to dump outcomes.
  python simulate.py compare --n 5000 --seed 99 --model artifacts/coach_model.pkl \
      --out artifacts/compare_outcomes.csv

All randomness is seeded; baseline and coach see identical journeys.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from coach import config as C
from coach.funnel import make_plan, resolve, Policy
from coach.coach import CoachPolicy


# --------------------------------------------------------------------------- #
# Cohort generation (shared by training-data emit and evaluation)             #
# --------------------------------------------------------------------------- #

def make_cohort(n_per_persona: int, seed: int):
    """Return a list of (session_id, persona, Plan) — the shared journey set."""
    rng = np.random.default_rng(seed)
    cohort = []
    for persona in C.PERSONA_MIX:
        for j in range(n_per_persona):
            cohort.append((f"{persona[:1].lower()}{seed}_{j:06d}", persona,
                           make_plan(rng, persona)))
    return cohort


def resolve_cohort(cohort, policy_factory):
    """policy_factory(persona) -> Policy ; returns list of (sid, persona, Result)."""
    out = []
    cache = {}
    for sid, persona, plan in cohort:
        pol = cache.get(persona)
        if pol is None:
            pol = cache[persona] = policy_factory(persona)
        out.append((sid, persona, resolve(plan, pol)))
    return out


def load_model(path: str | None):
    if not path:
        return None
    import joblib
    return joblib.load(path)


# --------------------------------------------------------------------------- #
# Training-data rows (baseline, per step reached)                              #
# --------------------------------------------------------------------------- #

STEP_FIELDS = [
    "session_id", "persona", "segment", "step_id", "step_name",
    "tariff_selected", "advisory_click", "provisional_price", "final_price",
    "price_delta_pct", "time_on_step_s", "cumulative_time_s",
    "n_hesitation_events", "n_back_clicks", "opened_competitor_tab",
    "cum_hesitation_events", "cum_back_clicks",
    "forced_oos", "label", "routed", "journey_outcome", "final_step_reached",
]


def baseline_rows(results):
    rows = []
    for sid, persona, res in results:
        cum_hes = cum_back = 0
        for rec in res.steps:
            row = {
                "session_id": sid, "persona": persona, "segment": C.SEGMENTS[persona],
                "step_id": rec.step, "step_name": rec.step_name,
                "tariff_selected": rec.tariff or "", "advisory_click": int(rec.advisory_click),
                "provisional_price": "" if rec.provisional_price is None else rec.provisional_price,
                "final_price": "" if rec.final_price is None else rec.final_price,
                "price_delta_pct": "" if rec.price_delta_pct is None else rec.price_delta_pct,
                "time_on_step_s": rec.signals.time_on_step_s,
                "cumulative_time_s": rec.cumulative_time_s,
                "n_hesitation_events": rec.signals.n_hesitation_events,
                "n_back_clicks": rec.signals.n_back_clicks,
                "opened_competitor_tab": rec.signals.opened_competitor_tab,
                "cum_hesitation_events": cum_hes, "cum_back_clicks": cum_back,
                "forced_oos": int(rec.forced_oos), "label": int(rec.left_here),
                "routed": int(rec.routed), "journey_outcome": res.outcome,
                "final_step_reached": res.final_step,
            }
            cum_hes += rec.signals.n_hesitation_events
            cum_back += rec.signals.n_back_clicks
            rows.append(row)
    return rows


def summarise(results, label="cohort"):
    from collections import Counter
    oc = Counter(r.outcome for _, _, r in results)
    n = len(results)
    conv = oc.get("converted", 0)
    # mix-weighted overall conversion (cohort is equal-sized per persona)
    by_p = {p: [r for _, pp, r in results if pp == p] for p in C.PERSONA_MIX}
    mixed = sum(C.PERSONA_MIX[p] * sum(r.outcome == "converted" for r in by_p[p]) / len(by_p[p])
                for p in C.PERSONA_MIX if by_p[p])
    print(f"  [{label}] sessions={n:,}  conversion(mix)={mixed*100:5.2f}%  "
          f"converted={conv:,} abandoned={oc.get('abandoned',0):,} "
          f"advisor_routed={oc.get('advisor_routed',0):,}")
    return {"sessions": n, "conversion": mixed, **oc}


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("baseline", help="emit no-coach training dataset")
    b.add_argument("--n", type=int, default=8000, help="journeys per persona")
    b.add_argument("--seed", type=int, default=11)
    b.add_argument("--out", default="artifacts/baseline_steps.csv")

    c = sub.add_parser("compare", help="paired baseline vs coach outcomes")
    c.add_argument("--n", type=int, default=5000)
    c.add_argument("--seed", type=int, default=99)
    c.add_argument("--model", default="artifacts/coach_model.pkl")
    c.add_argument("--out", default="artifacts/compare_outcomes.csv")

    args = ap.parse_args()

    if args.cmd == "baseline":
        cohort = make_cohort(args.n, args.seed)
        results = resolve_cohort(cohort, lambda p: Policy())
        print(f"Baseline cohort ({args.n:,}/persona, seed {args.seed}):")
        summarise(results, "no-coach")
        rows = baseline_rows(results)
        out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=STEP_FIELDS); w.writeheader(); w.writerows(rows)
        n_train = sum(1 for r in rows if not r["forced_oos"])
        print(f"  wrote {len(rows):,} step-rows ({n_train:,} trainable, "
              f"{len(rows)-n_train:,} forced-OOS) -> {out}")

    elif args.cmd == "compare":
        model = load_model(args.model)
        cohort = make_cohort(args.n, args.seed)
        base = resolve_cohort(cohort, lambda p: Policy())
        coach = resolve_cohort(cohort, lambda p: CoachPolicy(p, model=model))
        print(f"Paired cohort ({args.n:,}/persona, seed {args.seed}):")
        summarise(base, "no-coach")
        summarise(coach, "coach   ")
        out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["session_id", "persona", "baseline_outcome", "coach_outcome"])
            for (sid, p, rb), (_, _, rc) in zip(base, coach):
                w.writerow([sid, p, rb.outcome, rc.outcome])
        print(f"  wrote outcomes -> {out}")


if __name__ == "__main__":
    main()
