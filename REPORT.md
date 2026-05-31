# PromptCorn — UNIQA Conversion Coach

Honest evaluation, assumptions, and disclosures for the Insurance / UNIQA track.
All numbers below are produced by `leonardo_sim/evaluate.py` and written to
`leonardo_sim/artifacts/eval_metrics.json`; they refresh on every run and are
**not** hard-coded into the demo.

---

Team
- Valentino Garcia Susini
- Erik Seferi
- Dinmukhamed Zhakhan
- Benjamin Szilas

---
## 1. Results — the three judged dimensions

Held-out cohort: **300 journeys per persona, seed 99** (disjoint from the
training seed), identical journeys resolved with vs without the coach (common
random numbers), re-weighted to the **50/30/20** traffic mix.

### Dimension 1 — conversion uplift + drop-off reduction
| | baseline | coach | |
|---|---|---|---|
| Overall online conversion | **4.8%** | **17.3%** | ×3.6 (+12.5 pts) |
| Conditional drop @ step 4 (initial price) | 67.3% | 46.4% | −20.9 pts |
| Conditional drop @ step 7 (final price) | 80.4% | 55.1% | −25.3 pts |

### Dimension 2 — per-persona (works for all three segments)
| segment (mix) | baseline | coach | multiplier |
|---|---|---|---|
| Franz — Online Affine (50%) | 6.3% | 21.3% | ×3.4 |
| Judith — Rising Hybrid (30%) | 3.0% | 14.3% | ×4.8 |
| Peter — Service Affine (20%) | 3.7% | 11.7% | ×3.2 |

### Dimension 3 — intervention quality
- Coaching interventions fired: **1,051**
- Trigger **precision 72.1%** (fired on a real would-leave moment)
- Trigger **recall 86.3%** (of would-leave moments caught)
- **Annoyance 27.9%** (fired when the user would have stayed anyway)
- Mix: simplify_recommendation 44%, term_glossary 18%, suggest_online_tariff 12%,
  market_comparison 12%, value_justification 7%, reassurance 7%.

---

## 2. Baseline calibration (probed first — everything depends on it)

`python -m coach.funnel --calibrate` (20,000 journeys/persona) reproduces UNIQA's
real funnel:

| metric | target | reproduced |
|---|---|---|
| Overall online conversion | ~5.6% | **5.2%** |
| Conditional drop @ step 4 | 66% | **65.4%** |
| Conditional drop @ step 7 | 78% | **78.7%** |
| Drop @ step 5 (hospital add-ons) | — | **0%** (never reached in scope) |

Drops are applied **conditionally on the cohort that reached each step**, not
against the original 1,000. Survival math holds: 1,000 → ~340 (after the 66%
step-4 cliff) → ~57 (after the 78% step-7 cliff) ≈ the ~5.6% baseline.

> The held-out overall baseline (4.8%) is slightly below the large-sample
> calibration (5.2%) because it is a 900-journey sample at the 50/30/20 mix; the
> coach uplift is measured on the *same* sample, so the comparison is fair.

---

## 3. Scope correctness (hard boundary)

In scope: private-doctor tariffs, "myself only", and the two online-purchasable
tariffs **Start (€38.74)** and **Optimal (€68.14)**.

- Hospital path, "other persons", and **Opt.Plus (€96.66) / Premium (€140.16)**
  selections force a **clean advisor route** in `coach/funnel.py` — counted as
  `advisor_routed`, **never as an online conversion**. The coach does not attempt
  to "coach" these; it routes them. Advisor-routed share is reported separately.
- **Step 5 (hospital add-ons) is never reached** on the in-scope private-doctor
  path (`STEP_ORDER = [1,2,3,4,6,7,12]`), so the 24% step-5 cliff does not apply
  to these personas — confirmed 0% in calibration.
- All calculator steps are still collected; the coach never deletes a step.

A clean advisor handoff is treated as a **correct exit**, not a conversion win.

---

## 4. The conversion-definition conflict (disclosed, not silently resolved)

There is a genuine contradiction in the brief:

- **Contract spec** (`Track_..._EN.md`, §7): conversion = **online purchase only**,
  for all three personas.
- **Persona matrix** (`personas_comparison_matrix.md`): Judith's advisor handoff
  and Peter's service contact **also** count as success.

**Our resolution:** we use the **contract definition as the headline number**
(online conversion only — what all the tables above report). The engine *also*
tracks `advisor_routed` separately, so the "handoffs counted" view is available
without changing the headline. We did not silently pick the more favourable
definition. (Counting clean advisor routes as success would raise the reported
numbers further, especially for Judith/Peter — which is exactly why we keep them
out of the headline.)

---

## 5. Persona differentiation

The three personas drop at **different** steps and respond to **different**
interventions (`coach/config.py` `BASE_HAZARD`, `coach/persona_config.py`
`PRIMARY_DROPOFF_STEP`):

| | primary drop-off | what the coach must NOT do | why |
|---|---|---|---|
| Franz | final price (step 7) | push an advisor | he closes the tab (`response_model`: advisor push = ×1.25 = backfire) |
| Judith | initial price (step 4) | suggest an advisor reflexively | term/price reassurance keeps her online |
| Peter | early (steps 1/3) | pile on more information | more info → paralysis (market_comparison = ×1.15 = backfire) |

Because efficacies are resolved against the **true** persona, a mis-targeted
intervention earns no uplift (or backfires), so per-segment targeting beats a
single unified nudge by construction. A head-to-head unified-vs-per-segment
ablation is the most useful next addition (see §8).

---

## 6. Reproducibility

- **Identical seeds**, baseline vs coach: both resolve the *same* `Plan` objects
  (common random numbers) — see `simulate.make_cohort` / `evaluate.py`.
- Training data: `simulate.py baseline` (seed 11) → `artifacts/baseline_steps.csv`
  (~110k labelled step-rows). Evaluation: **seed 99, disjoint** from training.
- Re-run end to end on CPU in ~1 min: `./run.sh pipeline`.
- Classifier: `HistGradientBoostingClassifier`, ROC-AUC ≈ 0.975, PR-AUC ≈ 0.93,
  Brier ≈ 0.043 (`artifacts/classifier_metrics.json`).

---

## 7. Synthetic assumptions (documented, as the brief endorses)

- **Per-step hazards** (`BASE_HAZARD`) are tuned so the no-coach baseline matches
  UNIQA's published 66% / 78% / 5.6%; shapes encode each archetype.
- **Response efficacies** (`response_model.py`) are synthetic, derived from each
  persona's `best_coach_interventions` in `personas.js`, including the documented
  **backfires** (Franz ↔ advisor push, Peter ↔ more information).
- **Final-price surcharge** is sampled from documented scenarios
  (`SURCHARGE_SCENARIOS`: 0/4/10/18/30% at weights .20/.34/.26/.14/.06; expected
  ≈ 8.3%). The brief notes the price delta is undocumented; this is our stated
  assumption. The live demo's final price uses this **expected** surcharge,
  labelled as "typical", not a magic number.
- **LLM persona data** grounds signal *ranges*; the trained classifier learns from
  the calibrated funnel's labelled rows.

---

## 8. Limitations & threats to validity

- **Synthetic data.** No real UNIQA clickstream; behaviour is simulated. The
  funnel is calibrated to the published aggregates, not fit to per-user data.
- **Smoke-test-sized LLM run.** The GPU persona generation was run at small scale
  to validate the pipeline; the headline numbers come from the analytical funnel,
  not the LLM sample.
- **Single eval configuration** (n=300/persona, one held-out seed). Confidence
  intervals across seeds are not yet reported.
- **No unified-policy ablation** numbers yet — differentiation is argued from the
  mechanism (backfires) rather than a measured A/B.
- The classifier can learn the funnel's own signal model; on real data the brain
  would need re-training (the architecture supports it: `./run.sh train`).

---

## 9. Demo disclosures (what is real vs. illustrative)

The `demo/` app has two tabs and is explicit about which is which:

- **📊 Evidence tab — real engine.** The side-by-side baseline-vs-coach run calls
  the actual `coach/funnel.py` + `coach/coach.py` with the trained
  `coach_model.pkl` on identical seeds; the three-dimension numbers are read from
  `artifacts/eval_metrics.json`. Nothing here is mocked. A status banner shows
  where the engine loaded from and whether the trained model is in use.
- **▶ Live coach tab — interactive.** For responsiveness, the live click-through
  uses a transparent heuristic risk score and doc-grounded reply templates (or an
  optional Phi-3 chat if `torch` is installed). It is an interaction *feel*, not
  the evaluation. **All product numbers it displays** (prices, the 66% drop
  label, the typical surcharge, the segment prior) are injected from the engine —
  there are no hard-coded values in the page.
- The optional Phi-3 SLM is **not** required; without it the coach replies are
  instant and doc-grounded. The coach's decision logic is independent of any LLM
  call (not an LLM wrapper).

---

## 10. Submission hygiene

- **MIT licensed** (`LICENSE`), public repo, README + REPORT + requirements present.
- Runs from a clean checkout with the documented commands.
- **No API keys or tokens** in the repository or its git history.
