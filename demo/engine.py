#!/usr/bin/env python3
"""
engine.py — bridge from the demo app to the REAL UNIQA Conversion-Coach
implementation in ``leonardo_sim``.

The demo used to carry its own hard-coded copies of the prices, the persona mix,
the funnel cliffs and an ad-hoc risk score. That meant the slides could silently
drift from the engine the submission is actually judged on. This module makes the
real engine the single source of truth:

  * product / funnel constants come from ``coach.config`` + ``coach.persona_config``
    (which themselves derive from ``personas.js`` — survey n=4004 + funnel data),
  * the live side-by-side runs the calibrated funnel under the real ``Policy`` (no
    coach) vs the real ``CoachPolicy`` with the trained classifier brain, on the
    SAME pre-drawn plan (common random numbers — fair, reproducible pairing),
  * the headline evaluation numbers come from the committed
    ``artifacts/eval_metrics.json`` produced by ``evaluate.py``.

Locating the engine
-------------------
The path is resolved from, in order:
  1. ``$LEONARDO_SIM`` (explicit override),
  2. a list of sensible defaults relative to this file
     (``../leonardo_sim``, ``../ZeroOneHack42/leonardo_sim``, …).

If the engine cannot be imported (e.g. numpy/scikit-learn not installed), the
module degrades gracefully: ``AVAILABLE`` is ``False``, spec-accurate fallback
constants are still exported, and the app keeps running in standalone mode.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

# --------------------------------------------------------------------------- #
# Locate leonardo_sim                                                          #
# --------------------------------------------------------------------------- #

_HERE = Path(__file__).resolve().parent


def _candidate_paths() -> List[Path]:
    env = os.environ.get("LEONARDO_SIM")
    cands: List[Path] = []
    if env:
        cands.append(Path(env).expanduser())
    # Common layouts relative to demo/ (sibling, or nested second clone).
    cands += [
        _HERE.parent / "leonardo_sim",
        _HERE.parent / "ZeroOneHack42" / "leonardo_sim",
        _HERE.parent.parent / "ZeroOneHack42" / "leonardo_sim",
        _HERE.parent.parent / "leonardo_sim",
    ]
    return cands


def _resolve_sim_dir() -> Optional[Path]:
    for c in _candidate_paths():
        try:
            if (c / "coach" / "config.py").is_file():
                return c.resolve()
        except OSError:
            continue
    return None


SIM_DIR: Optional[Path] = _resolve_sim_dir()

# --------------------------------------------------------------------------- #
# Try to import the real engine                                               #
# --------------------------------------------------------------------------- #

AVAILABLE = False
STATUS = "not initialised"
MODEL = None
MODEL_STATUS = "not loaded"

# Spec-accurate fallbacks (used only if the engine is unavailable). These match
# personas.js / the Track spec so the UI is never wrong, just not "live".
TARIFF_PRICES: Dict[str, float] = {
    "Start": 38.74, "Optimal": 68.14, "Opt.Plus": 96.66, "Premium": 140.16,
}
ONLINE_TARIFFS = ("Start", "Optimal")
ADVISORY_TARIFFS = ("Opt.Plus", "Premium")
STEP_ORDER = [1, 2, 3, 4, 6, 7, 12]
STEP_NAMES = {
    1: "coverage_selection", 2: "for_whom", 3: "personal_data",
    4: "tariff_initial_price", 6: "health_questions", 7: "final_price",
    12: "closing",
}
PERSONA_MIX = {"Franz": 0.50, "Judith": 0.30, "Peter": 0.20}
CRITICAL_STEPS = {4: 0.66, 7: 0.78}
TARGET_OVERALL_CONVERSION = 0.056
PRIMARY_DROPOFF_STEP = {"Franz": 7, "Judith": 4, "Peter": 3}
ADVISOR_FRIENDLY = {"Franz": False, "Judith": True, "Peter": True}
BEST_INTERVENTIONS: Dict[str, List[str]] = {"Franz": [], "Judith": [], "Peter": []}
LIKELY_SIGNALS: Dict[str, List[str]] = {"Franz": [], "Judith": [], "Peter": []}

# Engine handles (populated on success)
_C = _PC = _funnel = None
_make_plan = _resolve = _Policy = _CoachPolicy = None
_np = None


def _try_import() -> None:
    global AVAILABLE, STATUS, MODEL, MODEL_STATUS
    global _C, _PC, _funnel, _make_plan, _resolve, _Policy, _CoachPolicy, _np
    global TARIFF_PRICES, ONLINE_TARIFFS, ADVISORY_TARIFFS, STEP_ORDER, STEP_NAMES
    global PERSONA_MIX, CRITICAL_STEPS, TARGET_OVERALL_CONVERSION
    global PRIMARY_DROPOFF_STEP, ADVISOR_FRIENDLY, BEST_INTERVENTIONS, LIKELY_SIGNALS

    if SIM_DIR is None:
        STATUS = ("leonardo_sim not found — set $LEONARDO_SIM or place it at "
                  "../leonardo_sim. Running in standalone (spec-constant) mode.")
        return

    if str(SIM_DIR) not in sys.path:
        sys.path.insert(0, str(SIM_DIR))

    try:
        import numpy as np
        from coach import config as C
        from coach import persona_config as PC
        from coach import funnel as funnel_mod
        from coach.funnel import make_plan, resolve, Policy
        from coach.coach import CoachPolicy
    except Exception as e:  # noqa: BLE001 - we want to degrade, not crash
        STATUS = f"engine import failed ({type(e).__name__}: {e}). Standalone mode."
        return

    _np = np
    _C, _PC, _funnel = C, PC, funnel_mod
    _make_plan, _resolve, _Policy, _CoachPolicy = make_plan, resolve, Policy, CoachPolicy

    # Adopt the engine's authoritative constants.
    TARIFF_PRICES = dict(C.TARIFF_PRICES)
    ONLINE_TARIFFS = tuple(C.ONLINE_TARIFFS)
    ADVISORY_TARIFFS = tuple(C.ADVISORY_TARIFFS)
    STEP_ORDER = list(C.STEP_ORDER)
    STEP_NAMES = dict(C.STEP_NAMES)
    PERSONA_MIX = dict(C.PERSONA_MIX)
    CRITICAL_STEPS = dict(C.CRITICAL_STEPS)
    TARGET_OVERALL_CONVERSION = float(C.TARGET_OVERALL_CONVERSION)
    PRIMARY_DROPOFF_STEP = dict(PC.PRIMARY_DROPOFF_STEP)
    ADVISOR_FRIENDLY = dict(PC.ADVISOR_FRIENDLY)
    BEST_INTERVENTIONS = {k: list(v) for k, v in PC.BEST_INTERVENTIONS.items()}
    LIKELY_SIGNALS = {k: list(v) for k, v in PC.LIKELY_SIGNALS.items()}

    # Load the trained classifier brain (optional — coach falls back to a
    # transparent heuristic if absent, so this never blocks the demo).
    model_path = SIM_DIR / "artifacts" / "coach_model.pkl"
    try:
        import joblib
        MODEL = joblib.load(model_path)
        MODEL_STATUS = f"loaded {type(MODEL).__name__} from {model_path.name}"
    except Exception as e:  # noqa: BLE001
        MODEL = None
        MODEL_STATUS = (f"trained model not loaded ({type(e).__name__}); "
                        f"coach uses heuristic risk")

    AVAILABLE = True
    STATUS = f"engine loaded from {SIM_DIR}"


_try_import()


# --------------------------------------------------------------------------- #
# Persona display names (Franz / Judith / Peter)                              #
# --------------------------------------------------------------------------- #

PERSONAS = list(PERSONA_MIX.keys())
PERSONA_PRIOR = dict(PERSONA_MIX)        # belief prior == real traffic mix


# --------------------------------------------------------------------------- #
# Grounding docs for the SLM system prompt (fixes the undefined-name bug and  #
# grounds replies in the real persona briefings + engine constants).          #
# --------------------------------------------------------------------------- #

def _read(path: Path, limit: int = 4000) -> str:
    try:
        return path.read_text(encoding="utf-8")[:limit]
    except OSError:
        return ""


def _build_docs():
    funnel_doc = (
        "UNIQA online private-doctor funnel (steps 1,2,3,4,6,7,12). Real baseline: "
        f"~{TARGET_OVERALL_CONVERSION*100:.1f}% overall online conversion. Conditional "
        f"drop-offs: step 4 initial price ~{int(CRITICAL_STEPS.get(4, 0.66)*100)}%, "
        f"step 7 final price ~{int(CRITICAL_STEPS.get(7, 0.78)*100)}%. Hospital path / "
        "'other persons' / Opt.Plus / Premium are OUT of scope -> clean advisor route "
        "(a correct exit, not a conversion). Step 5 (hospital add-ons) is never reached "
        "on the in-scope private-doctor path."
    )
    product_doc = (
        "Online-purchasable tariffs (the only conversion targets): "
        f"Start €{TARIFF_PRICES.get('Start', 38.74):.2f}/mo (GP, specialists, medications, "
        f"basic diagnostics); Optimal €{TARIFF_PRICES.get('Optimal', 68.14):.2f}/mo "
        "(adds therapies, medical aids, refractive eye surgery). Advisory-only (NOT online): "
        f"Opt.Plus €{TARIFF_PRICES.get('Opt.Plus', 96.66):.2f}, "
        f"Premium €{TARIFF_PRICES.get('Premium', 140.16):.2f}."
    )
    persona_docs: Dict[str, str] = {}
    name_to_file = {"Franz": "franz.md", "Judith": "judith.md", "Peter": "peter.md"}
    for name, fname in name_to_file.items():
        text = _read(SIM_DIR / fname) if SIM_DIR else ""
        if not text:
            text = _PERSONA_FALLBACK.get(name, "")
        persona_docs[name] = text
    return funnel_doc, product_doc, persona_docs


_PERSONA_FALLBACK = {
    "Franz": ("Franz Huber, Segment 2 (Online Affine). Digital-first, no patience for "
              "friction; wants fast, transparent online purchase. Drops at the FINAL "
              "price surprise. NEVER push an advisor (he closes the tab). Data/price "
              "reframing and market comparison work."),
    "Judith": ("Judith Berger, Segment 1 (Rising Hybrid). Researches online but wants a "
               "trusted person before committing. Drops at the INITIAL price. Term "
               "explanations, transparency and reassurance keep her online; an advisor "
               "handoff is acceptable."),
    "Peter": ("Peter Wagner, Segment 3 (Service Affine). Wants to be told what to pick. "
              "Overwhelmed EARLY. A single clear recommendation / simplification works; "
              "piling on more info backfires (paralysis). A warm proactive callback is "
              "genuinely welcome."),
}

FUNNEL_DOC, PRODUCT_DOC, PERSONA_DOCS = _build_docs()


# --------------------------------------------------------------------------- #
# Paired baseline-vs-coach simulation (the "which step flipped" showcase)     #
# --------------------------------------------------------------------------- #

def _parse_intervention(iv) -> Optional[dict]:
    if iv is None:
        return None
    msg = iv.message or ""
    trigger = ""
    text = msg
    if msg.startswith("[") and "] " in msg:
        trigger, text = msg[1:].split("] ", 1)
    return {
        "name": iv.name,
        "category": iv.category,
        "trigger": trigger,            # e.g. "rule:final_price_jump | seg=online | best"
        "message": text,
        "hazard_multiplier": round(float(iv.hazard_multiplier), 3),
        "switch_prob": round(float(iv.switch_prob), 3),
    }


def _serialize_result(res) -> dict:
    steps = []
    for rec in res.steps:
        s = rec.signals
        steps.append({
            "step": rec.step,
            "step_name": rec.step_name,
            "dwell_s": int(s.time_on_step_s),
            "hesitation": int(s.n_hesitation_events),
            "back_clicks": int(s.n_back_clicks),
            "competitor_tab": int(s.opened_competitor_tab),
            "tariff": rec.tariff,
            "advisory_click": bool(rec.advisory_click),
            "provisional_price": rec.provisional_price,
            "final_price": rec.final_price,
            "price_delta_pct": rec.price_delta_pct,
            "left_here": bool(rec.left_here),
            "routed": bool(rec.routed),
            "forced_oos": bool(rec.forced_oos),
            "intervention": _parse_intervention(rec.intervention),
        })
    return {"outcome": res.outcome, "final_step": res.final_step, "steps": steps}


def run_paired(persona: str, seed: int) -> dict:
    """Run ONE journey twice on the same pre-drawn plan: no-coach baseline vs
    trained coach. Returns the full step-by-step trace of both plus the flip."""
    if not AVAILABLE:
        raise RuntimeError("engine unavailable: " + STATUS)
    if persona not in PERSONA_MIX:
        raise ValueError(f"unknown persona {persona!r}; expected one of {list(PERSONA_MIX)}")

    rng = _np.random.default_rng(int(seed))
    plan = _make_plan(rng, persona)
    base = _resolve(plan, _Policy())
    coach = _resolve(plan, _CoachPolicy(persona, model=MODEL))

    base_s = _serialize_result(base)
    coach_s = _serialize_result(coach)
    intervened = [st["step"] for st in coach_s["steps"] if st["intervention"]]
    flipped = base.outcome != "converted" and coach.outcome == "converted"
    return {
        "persona": persona,
        "seed": int(seed),
        "model": MODEL is not None,
        "baseline": base_s,
        "coach": coach_s,
        "flip": {
            "baseline_outcome": base.outcome,
            "coach_outcome": coach.outcome,
            "flipped": flipped,
            "baseline_left_step": None if base.outcome == "converted" else base.final_step,
            "intervened_steps": intervened,
        },
    }


def find_flip(persona: str, start_seed: int = 0, limit: int = 400) -> Optional[int]:
    """Return the first seed >= start_seed where the coach turns a baseline
    non-conversion into a conversion (a compelling, honest default for the demo)."""
    if not AVAILABLE:
        return None
    for seed in range(int(start_seed), int(start_seed) + int(limit)):
        r = run_paired(persona, seed)
        if r["flip"]["flipped"]:
            return seed
    return None


# Per-persona default seeds that produce a clean baseline->coach flip. Computed
# lazily and cached so the "both showcases" UI opens on a winning example.
_DEFAULT_FLIP_SEED: Dict[str, Optional[int]] = {}


def default_flip(persona: str) -> dict:
    if persona not in _DEFAULT_FLIP_SEED:
        _DEFAULT_FLIP_SEED[persona] = find_flip(persona, start_seed=1, limit=300)
    seed = _DEFAULT_FLIP_SEED[persona]
    if seed is None:                       # fall back to a deterministic seed
        seed = 1
    return run_paired(persona, seed)


# --------------------------------------------------------------------------- #
# Headline evaluation (the three judged dimensions)                           #
# --------------------------------------------------------------------------- #

def eval_metrics() -> Optional[dict]:
    """The committed three-dimension evaluation (artifacts/eval_metrics.json)."""
    if SIM_DIR is None:
        return None
    path = SIM_DIR / "artifacts" / "eval_metrics.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return None


def qualitative_trace() -> str:
    if SIM_DIR is None:
        return ""
    return _read(SIM_DIR / "artifacts" / "qualitative_trace.txt", limit=8000)


def expected_surcharge() -> float:
    """The mean step-7 risk surcharge (provisional -> final price), weighted over
    the engine's SURCHARGE_SCENARIOS. Used so the live calculator's final price is
    a real engine number, not a magic +10%."""
    if _C is not None and hasattr(_C, "SURCHARGE_SCENARIOS"):
        try:
            return float(sum(frac * w for frac, w in _C.SURCHARGE_SCENARIOS))
        except Exception:  # noqa: BLE001
            pass
    # Fallback = mean of the documented scenarios (0/4/10/18/30% @ .20/.34/.26/.14/.06).
    return 0.0828


def ui_config() -> dict:
    """Everything the front-end needs to render real numbers (no client-side
    hard-coding): tariffs, belief prior, the conditional drop cliffs, the typical
    surcharge and the baseline conversion — all from the engine."""
    return {
        "tariffs": {
            "Start": TARIFF_PRICES.get("Start", 38.74),
            "Optimal": TARIFF_PRICES.get("Optimal", 68.14),
            "OptPlus": TARIFF_PRICES.get("Opt.Plus", TARIFF_PRICES.get("OptPlus", 96.66)),
            "Premium": TARIFF_PRICES.get("Premium", 140.16),
        },
        "prior": dict(PERSONA_PRIOR),
        "critical": {str(k): v for k, v in CRITICAL_STEPS.items()},
        "surcharge": round(expected_surcharge(), 4),
        "target_conversion": TARGET_OVERALL_CONVERSION,
        "available": AVAILABLE,
    }


def status() -> dict:
    return {
        "available": AVAILABLE,
        "status": STATUS,
        "sim_dir": str(SIM_DIR) if SIM_DIR else None,
        "model_status": MODEL_STATUS,
        "personas": PERSONAS,
        "tariffs": TARIFF_PRICES,
        "persona_mix": PERSONA_MIX,
        "critical_steps": {str(k): v for k, v in CRITICAL_STEPS.items()},
        "target_conversion": TARGET_OVERALL_CONVERSION,
        "primary_dropoff_step": PRIMARY_DROPOFF_STEP,
        "advisor_friendly": ADVISOR_FRIENDLY,
        "has_eval_metrics": eval_metrics() is not None,
    }


if __name__ == "__main__":   # quick self-test: `python engine.py`
    import pprint
    pprint.pprint(status())
    if AVAILABLE:
        for p in PERSONAS:
            r = default_flip(p)
            print(f"\n{p}: seed={r['seed']} baseline={r['flip']['baseline_outcome']} "
                  f"-> coach={r['flip']['coach_outcome']} "
                  f"(flipped={r['flip']['flipped']}, fired at {r['flip']['intervened_steps']})")
