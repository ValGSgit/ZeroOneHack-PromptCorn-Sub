#!/usr/bin/env python3
"""
evaluate.py — the before/after evaluation (spec §7, three dimensions).

Runs a HELD-OUT cohort (a seed disjoint from training) through the funnel twice
on identical plans (common random numbers): once with no coach, once with the
trained coach. Produces:

  Dimension 1  Conversion uplift + per-step drop-off reduction
  Dimension 2  Per-persona conversion (does it work for all three segments?)
  Dimension 3  Intervention quality: trigger precision / recall / annoyance rate

Outputs: artifacts/eval_metrics.json, artifacts/eval_dropoff.png,
artifacts/eval_conversion.png, artifacts/eval_intervention_quality.png, and a
qualitative before/after trace printed to stdout + artifacts/qualitative_trace.txt

  python evaluate.py --n 6000 --seed 99 --model artifacts/coach_model.pkl
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from coach import config as C
from coach.funnel import resolve, Policy, baseline_would_leave
from coach.coach import CoachPolicy
from simulate import make_cohort, load_model


def conditional_dropoff(results_by_plan):
    """Aggregate conditional drop per step, persona-mix weighted."""
    reach = {p: {s: 0 for s in C.STEP_ORDER} for p in C.PERSONA_MIX}
    leave = {p: {s: 0 for s in C.STEP_ORDER} for p in C.PERSONA_MIX}
    n = {p: 0 for p in C.PERSONA_MIX}
    for persona, res in results_by_plan:
        n[persona] += 1
        for rec in res.steps:
            reach[persona][rec.step] += 1
            if rec.left_here:
                leave[persona][rec.step] += 1
    drop = {}
    for s in C.STEP_ORDER:
        num = den = 0.0
        for p, w in C.PERSONA_MIX.items():
            if reach[p][s]:
                num += w * leave[p][s] / n[p]
                den += w * reach[p][s] / n[p]
        drop[s] = (num / den) if den else 0.0
    return drop


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6000, help="held-out journeys per persona")
    ap.add_argument("--seed", type=int, default=99)
    ap.add_argument("--model", default="artifacts/coach_model.pkl")
    ap.add_argument("--out-dir", default="artifacts")
    ap.add_argument("--no-plots", action="store_true",
                    help="Skip matplotlib plots (useful on memory-constrained nodes).")
    args = ap.parse_args()

    if not args.no_plots:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    model = load_model(args.model)
    cohort = make_cohort(args.n, args.seed)

    base_policy = Policy()
    coaches = {p: CoachPolicy(p, model=model) for p in C.PERSONA_MIX}

    base, coach = [], []
    interventions = []        # (persona, step, iv, counterfactual_leave, coachable)
    for sid, persona, plan in cohort:
        rb = resolve(plan, base_policy)
        rc = resolve(plan, coaches[persona])
        base.append((persona, rb)); coach.append((persona, rc))
        for step, iv in rc.interventions:
            coachable = not (step == 1 and plan.oos1) and not (step == 2 and plan.oos2)
            interventions.append((persona, step, iv, baseline_would_leave(plan, step), coachable))

    # ---- per-persona conversion (used to build the mix-weighted overall) ----
    # The cohort is equal-sized per persona for clean per-segment stats, so the
    # headline "overall" must be re-weighted to the 50/30/20 traffic mix to mean
    # the real funnel number.
    def persona_conv(results, p):
        rs = [r for pp, r in results if pp == p]
        return sum(r.outcome == "converted" for r in rs) / len(rs)

    per_persona = {p: {"baseline": persona_conv(base, p), "coach": persona_conv(coach, p)}
                   for p in C.PERSONA_MIX}
    base_cr = sum(C.PERSONA_MIX[p] * per_persona[p]["baseline"] for p in C.PERSONA_MIX)
    coach_cr = sum(C.PERSONA_MIX[p] * per_persona[p]["coach"] for p in C.PERSONA_MIX)

    def routed_share(results):
        rs_by_p = {p: [r for pp, r in results if pp == p] for p in C.PERSONA_MIX}
        return sum(C.PERSONA_MIX[p] * sum(r.outcome == "advisor_routed" for r in rs_by_p[p])
                   / len(rs_by_p[p]) for p in C.PERSONA_MIX)
    base_routed, coach_routed = routed_share(base), routed_share(coach)
    drop_b = conditional_dropoff(base); drop_c = conditional_dropoff(coach)

    print("\n" + "=" * 64)
    print("DIMENSION 1 — Conversion uplift")
    print("=" * 64)
    print(f"  overall online conversion : {base_cr*100:5.2f}%  ->  {coach_cr*100:5.2f}%   "
          f"(+{(coach_cr-base_cr)*100:.2f} pts, x{coach_cr/base_cr:.2f})   [50/30/20 mix-weighted]")
    print(f"  advisor-routed share      : {base_routed*100:5.2f}%  ->  {coach_routed*100:5.2f}%")
    print("\n  conditional drop-off per step (baseline -> coach):")
    for s in C.STEP_ORDER:
        tag = "  <= critical" if s in C.CRITICAL_STEPS else ""
        print(f"    step {s:>2} {C.STEP_NAMES[s]:22s} {drop_b[s]*100:5.1f}% -> {drop_c[s]*100:5.1f}%{tag}")

    # ---- Dimension 2: per persona ----
    print("\n" + "=" * 64)
    print("DIMENSION 2 — Persona differentiation")
    print("=" * 64)
    for p in C.PERSONA_MIX:
        bcr, ccr = per_persona[p]["baseline"], per_persona[p]["coach"]
        print(f"  {p:7s} (mix {C.PERSONA_MIX[p]*100:.0f}%) conversion "
              f"{bcr*100:5.2f}% -> {ccr*100:5.2f}%   (+{(ccr-bcr)*100:.2f} pts, x{ccr/bcr:.2f})")

    # ---- Dimension 3: intervention quality ----
    # A "coaching" fire excludes the two hard out-of-scope routes (hospital /
    # other persons), which are clean handoffs the coach must do, not coaching.
    coachable_fires = [i for i in interventions if i[4]]
    tp = sum(1 for i in coachable_fires if i[3])   # fired AND user would really leave
    fp = len(coachable_fires) - tp                 # fired but user would have stayed
    # Recall denominator: would-leave events at coachable steps the coach actually
    # reached (was present to intervene). Reuse the already-resolved coach runs.
    wl_events = wl_caught = 0
    for (sid, persona, plan), (_, rc) in zip(cohort, coach):
        fired_steps = {step for step, _ in rc.interventions
                       if not (step == 1 and plan.oos1) and not (step == 2 and plan.oos2)}
        reached_steps = {rec.step for rec in rc.steps}
        for s in C.STEP_ORDER:
            coachable = not (s == 1 and plan.oos1) and not (s == 2 and plan.oos2)
            if coachable and s in reached_steps and baseline_would_leave(plan, s):
                wl_events += 1
                if s in fired_steps:
                    wl_caught += 1
    precision = tp / max(1, tp + fp)
    recall = wl_caught / max(1, wl_events)
    annoyance = fp / max(1, len(coachable_fires))
    print("\n" + "=" * 64)
    print("DIMENSION 3 — Intervention quality")
    print("=" * 64)
    print(f"  coaching interventions fired : {len(coachable_fires):,}")
    print(f"  trigger precision            : {precision*100:5.1f}%  (fired on a real would-leave)")
    print(f"  trigger recall               : {recall*100:5.1f}%  (of would-leave events caught)")
    print(f"  annoyance rate               : {annoyance*100:5.1f}%  (fired when user would have stayed)")
    mix = Counter(iv.name for _, _, iv, _, c in coachable_fires)
    print("  intervention mix:")
    for name, cnt in mix.most_common():
        print(f"    {name:28s} {cnt:6,}  ({cnt/len(coachable_fires)*100:4.1f}%)")

    # ---- plots ----
    import numpy as np
    if not args.no_plots:
        steps = C.STEP_ORDER; xlab = [f"{s}\n{C.STEP_NAMES[s][:10]}" for s in steps]
        x = np.arange(len(steps)); w = 0.38
        fig, axp = plt.subplots(figsize=(11, 5))
        axp.bar(x - w/2, [drop_b[s]*100 for s in steps], w, label="no coach", color="#c0392b")
        axp.bar(x + w/2, [drop_c[s]*100 for s in steps], w, label="with coach", color="#27ae60")
        for s, tgt in C.CRITICAL_STEPS.items():
            axp.axhline(tgt*100, ls=":", c="gray", lw=.8)
        axp.set(xticks=x, xticklabels=xlab, ylabel="conditional drop-off %",
                title="Drop-off per step — baseline vs coach (dotted = real UNIQA target)")
        axp.legend(); fig.tight_layout(); fig.savefig(out / "eval_dropoff.png", dpi=110); plt.close(fig)

        fig, axc = plt.subplots(figsize=(8, 5))
        names = list(per_persona) + ["OVERALL"]
        bvals = [per_persona[p]["baseline"]*100 for p in per_persona] + [base_cr*100]
        cvals = [per_persona[p]["coach"]*100 for p in per_persona] + [coach_cr*100]
        xx = np.arange(len(names))
        axc.bar(xx - w/2, bvals, w, label="no coach", color="#c0392b")
        axc.bar(xx + w/2, cvals, w, label="with coach", color="#27ae60")
        for i, (b, c) in enumerate(zip(bvals, cvals)):
            axc.text(i + w/2, c + .1, f"x{c/b:.1f}", ha="center", fontsize=9)
        axc.set(xticks=xx, xticklabels=names, ylabel="online conversion %",
                title="Conversion by persona — baseline vs coach"); axc.legend()
        fig.tight_layout(); fig.savefig(out / "eval_conversion.png", dpi=110); plt.close(fig)

        fig, axq = plt.subplots(figsize=(7, 5))
        axq.bar(["precision", "recall", "1 − annoyance"],
                [precision*100, recall*100, (1-annoyance)*100], color="#2980b9")
        axq.set(ylim=(0, 100), ylabel="%", title="Intervention quality")
        for i, v in enumerate([precision, recall, 1-annoyance]):
            axq.text(i, v*100 + 1, f"{v*100:.0f}%", ha="center")
        fig.tight_layout(); fig.savefig(out / "eval_intervention_quality.png", dpi=110); plt.close(fig)
        print(f"Saved plots -> {out}/")

    # ---- qualitative before/after trace (one saved journey per persona) ----
    lines = []
    for target in C.PERSONA_MIX:
        for (sid, persona, plan) in cohort:
            if persona != target:
                continue
            rb = resolve(plan, base_policy); rc = resolve(plan, coaches[persona])
            if rb.outcome != "converted" and rc.outcome == "converted":
                lines.append(f"\n=== {persona} — baseline={rb.outcome.upper()} | coach=CONVERTED ===")
                ivs = dict(rc.interventions)
                for rec in rc.steps:
                    s = rec.step
                    msg = f"  step {s:>2} {rec.step_name:20s} dwell={rec.signals.time_on_step_s:>3}s "\
                          f"hes={rec.signals.n_hesitation_events} back={rec.signals.n_back_clicks} "\
                          f"tab={rec.signals.opened_competitor_tab}"
                    if rec.final_price:
                        msg += f" final=€{rec.final_price}"
                    lines.append(msg)
                    if s in ivs:
                        lines.append(f"        ↳ COACH [{ivs[s].category}/{ivs[s].name}] {ivs[s].message}")
                break
    trace = "\n".join(lines)
    print("\n" + "=" * 64 + "\nQUALITATIVE BEFORE/AFTER TRACES\n" + "=" * 64 + trace)
    (out / "qualitative_trace.txt").write_text(trace)

    metrics = {
        "held_out": {"n_per_persona": args.n, "seed": args.seed},
        "dimension1_conversion": {"baseline": base_cr, "coach": coach_cr,
                                  "uplift_pts": coach_cr - base_cr,
                                  "multiplier": coach_cr / base_cr,
                                  "dropoff_baseline": drop_b, "dropoff_coach": drop_c},
        "dimension2_per_persona": per_persona,
        "dimension3_intervention_quality": {
            "fired": len(coachable_fires), "precision": precision, "recall": recall,
            "annoyance_rate": annoyance, "mix": dict(mix)},
    }
    (out / "eval_metrics.json").write_text(json.dumps(metrics, indent=2, default=float))
    print(f"\nSaved metrics -> {out}/eval_metrics.json")


if __name__ == "__main__":
    main()
