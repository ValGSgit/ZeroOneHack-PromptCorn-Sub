"""
persona_config.py — loads personas.js and exposes it as the COACH's config.

personas.js is the authoritative UNIQA segmentation config (survey n=4004 +
funnel analysis). The persona *simulator* characters live in the .md briefings;
this module is the other half — the structured facts the COACH uses to GUIDE and
PROCESS people:

  * who the segments are (display name <-> segment label, traffic mix)
  * the real funnel baselines (overall conversion, the 66%/78% price cliffs)
  * each segment's PRIMARY DROP-OFF step + likely behavioural signals
    -> the coach lowers its firing threshold where a segment is known to bail
  * each segment's BEST coach interventions (mapped to our canonical names)
    -> the coach prefers the documented-effective nudge for the inferred segment
  * the intervention taxonomy (categories -> intervention ids)

Everything is derived from personas.js so there is a single source of truth; the
numeric hazards/efficacies that need tuning stay in config.py / response_model.py.
"""

from __future__ import annotations

import json
from pathlib import Path

PERSONAS_JSON_PATH = Path(__file__).resolve().parent.parent / "personas.js"

RAW = json.loads(PERSONAS_JSON_PATH.read_text(encoding="utf-8"))
SHARED = RAW["shared_context"]
_PERSONAS = RAW["personas"]

# --------------------------------------------------------------------------- #
# segment <-> display-name mapping (derived from the archetype names)          #
# --------------------------------------------------------------------------- #

def _display(seg_key: str) -> str:
    return _PERSONAS[seg_key]["persona_archetype"]["name"].split()[0]

def _segment_label(seg_key: str) -> str:
    """e.g. 'segment_2' + 'Online Affine' -> 'segment_2_online_affine'."""
    short = _PERSONAS[seg_key]["name_short"].lower().replace(" ", "_")
    return f"{seg_key}_{short}"

# Keep the funnel/training order: Franz, Judith, Peter (segment_2, 1, 3).
_ORDER = ["segment_2", "segment_1", "segment_3"]
DISPLAY_NAMES = [_display(s) for s in _ORDER]                  # ["Franz","Judith","Peter"]
SEGMENT_OF = {_display(s): _segment_label(s) for s in _ORDER}  # display -> "segment_x_label"
_SEG_KEY_OF = {_display(s): s for s in _ORDER}                 # display -> "segment_x"

ARCHETYPE = {_display(s): _PERSONAS[s]["persona_archetype"] for s in _ORDER}

# --------------------------------------------------------------------------- #
# Funnel baselines (the real numbers the coach is judged against)              #
# --------------------------------------------------------------------------- #

_traffic = SHARED["online_funnel_traffic_share"]
# segment_1/2/3 share -> display-keyed mix, preserving Franz/Judith/Peter order
PERSONA_MIX = {_display(s): float(_traffic[s]) for s in _ORDER}

_baseline = SHARED["current_online_conversion_baseline"]
TARGET_OVERALL_CONVERSION = float(_baseline["rate"])

# Map the funnel doc's step *names* to our numeric step ids.
_DROP_NAME_TO_STEP = {
    "initial_price_display": 4,
    "additional_coverage_selection": 5,      # out-of-scope hospital path
    "final_price_after_health_questions": 7,
    "earlier_steps_or_initial_price": 3,     # early overwhelm (Peter)
}

# The in-scope graded cliffs: {step_id: conditional drop rate}.
CRITICAL_STEPS = {
    _DROP_NAME_TO_STEP[d["step"]]: float(d["rate"])
    for d in _baseline["drop_offs"]
    if _DROP_NAME_TO_STEP.get(d["step"]) in (4, 7)
}

# --------------------------------------------------------------------------- #
# Per-segment funnel-behaviour hypotheses (guide WHEN/WHERE the coach acts)    #
# --------------------------------------------------------------------------- #

def _hyp(display: str) -> dict:
    return _PERSONAS[_SEG_KEY_OF[display]]["online_funnel_behavior_hypotheses"]

PRIMARY_DROPOFF_STEP = {
    d: _DROP_NAME_TO_STEP.get(_hyp(d)["primary_drop_off_step"], 4) for d in DISPLAY_NAMES
}
LIKELY_SIGNALS = {d: list(_hyp(d).get("behavioral_signals_likely", [])) for d in DISPLAY_NAMES}

# --------------------------------------------------------------------------- #
# Intervention taxonomy + per-segment best interventions                      #
# --------------------------------------------------------------------------- #

INTERVENTION_TAXONOMY = RAW["intervention_taxonomy_suggestions"]["categories"]

# Map the free-text best_coach_interventions in personas.js to the canonical
# intervention names the coach/response_model actually use. Keyword -> name.
_INTERVENTION_KEYWORDS = [
    ("market comparison",        "market_comparison_signal"),
    ("comparison",               "market_comparison_signal"),
    ("reframe price",            "psychological_price_reframe"),
    ("psycholog",                "psychological_price_reframe"),
    ("value justification",      "value_justification"),
    ("final price diverges",     "value_justification"),
    ("lower-priced tariff",      "suggest_cheaper_tariff"),
    ("cheaper",                  "suggest_cheaper_tariff"),
    ("term explanation",         "term_glossary"),
    ("glossary",                 "term_glossary"),
    ("pause-and-resume",         "save_progress_resume_later"),
    ("save progress",            "save_progress_resume_later"),
    ("advisor booking",          "advisor_booking_proactive"),
    ("customer service handoff", "advisor_booking_proactive"),
    ("phone callback",           "advisor_booking_proactive"),
    ("simplify form",            "simplify_recommendation"),
    ("simplif",                  "simplify_recommendation"),
    ("overwhelm",                "simplify_recommendation"),
]


def _map_interventions(texts: list[str]) -> list[str]:
    out: list[str] = []
    for t in texts:
        tl = t.lower()
        for kw, name in _INTERVENTION_KEYWORDS:
            if kw in tl and name not in out:
                out.append(name)
                break
    return out


BEST_INTERVENTIONS = {
    d: _map_interventions(_hyp(d).get("best_coach_interventions", [])) for d in DISPLAY_NAMES
}

# Segments where pushing an advisor handoff is the RIGHT move (vs a backfire).
# Derived from the hypotheses text: Franz explicitly dislikes advisor pushes.
ADVISOR_FRIENDLY = {
    d: not any("avoid pushing" in t.lower() or "dislikes" in t.lower()
               for t in _hyp(d).get("best_coach_interventions", []))
    for d in DISPLAY_NAMES
}


if __name__ == "__main__":   # quick audit: `python -m coach.persona_config`
    print(f"source: {PERSONAS_JSON_PATH.name}  (v{RAW.get('version')})")
    print(f"PERSONA_MIX            : {PERSONA_MIX}")
    print(f"SEGMENT_OF             : {SEGMENT_OF}")
    print(f"TARGET_OVERALL_CONV    : {TARGET_OVERALL_CONVERSION}")
    print(f"CRITICAL_STEPS         : {CRITICAL_STEPS}")
    print(f"PRIMARY_DROPOFF_STEP   : {PRIMARY_DROPOFF_STEP}")
    print(f"ADVISOR_FRIENDLY       : {ADVISOR_FRIENDLY}")
    print("BEST_INTERVENTIONS:")
    for d, names in BEST_INTERVENTIONS.items():
        print(f"  {d:7s} -> {names}")
    print(f"taxonomy categories    : {list(INTERVENTION_TAXONOMY)}")
