#!/usr/bin/env python3
"""
persona_simulator.py — LLM-driven UNIQA funnel journey simulator (Leonardo / vLLM).

Runs a free Mistral instruct model as each persona (Franz / Judith / Peter), walks
each simulated user through the 7 in-scope steps of the UNIQA health-insurance
calculator, and records the behavioral signals + abandonment label needed to train
the Conversion Coach's abandonment classifier (e.g. XGBoost).

One LLM call == one full journey (batched by vLLM). Python grounds the numeric
fields (prices, cumulative time), enforces the funnel scope rules, and writes a CSV
whose schema is compatible with the deterministic data_franz.csv generator so all
team CSVs can be merged.

Usage (inside the sbatch job, GPU node):
    python persona_simulator.py --persona franz   --per-persona 1000 \
        --output-dir "$PUBLIC/hackathon_data" --model "$MODEL_PATH"

    python persona_simulator.py --persona all --per-persona 1000 ...

Output: <output-dir>/data_<persona>.csv  (one file per persona)
"""

import argparse
import csv
import json
import random
import re
import sys
import time
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Product / funnel constants  (from uniqa-funnel-doc + Track spec)
# ---------------------------------------------------------------------------

TARIFF_PRICES = {
    "Start":    38.74,
    "Optimal":  68.14,
    "Opt.Plus": 96.66,
    "Premium": 140.16,
}
ADVISORY_TARIFFS = {"Opt.Plus", "Premium"}      # choosing these => advisor route, not conversion
ONLINE_TARIFFS = {"Start", "Optimal"}

# Ordered in-scope steps (matches the funnel doc; 5/8-11 are out-of-scope branches)
STEP_ORDER = [1, 2, 3, 4, 6, 7, 12]
STEP_NAMES = {
    1:  "coverage_selection",
    2:  "for_whom",
    3:  "personal_data",
    4:  "tariff_selection",
    6:  "health_questions",
    7:  "final_price",
    12: "closing",
}

CSV_FIELDS = [
    "session_id", "persona", "segment", "step_id", "step_name",
    "coverage_selection", "for_whom", "tariff_selected", "advisory_tariff_clicked",
    "provisional_price", "final_price", "price_delta_pct",
    "time_on_step_s", "cumulative_time_s",
    "n_hesitation_events", "n_back_clicks", "opened_competitor_tab",
    "coach_intervened", "coach_type",
    "label",
    "journey_outcome", "final_step_reached", "gen_temperature", "scenario", "reasoning",
]

# ---------------------------------------------------------------------------
# Persona system prompts — loaded from the per-persona briefing files
# (franz.md / judith.md / peter.md). Those .md files ARE the single source of
# truth for each character ("Use this profile as a system prompt for persona
# bots"); personas.js is the COACH's config, not the persona simulator's.
# "Good prompts beat complex setups" — the briefings are intentionally rich.
# ---------------------------------------------------------------------------

# persona key -> (briefing file, CSV segment label, display name)
PERSONA_FILES = {
    "franz":  ("franz.md",  "segment_2_online_affine", "Franz"),
    "judith": ("judith.md", "segment_1_rising_hybrid", "Judith"),
    "peter":  ("peter.md",  "segment_3_service_affine", "Peter"),
}

# Realism calibration appended to every persona prompt. The earlier inline
# prompts let the model convert far too often (e.g. Franz ~66% vs the real
# ~5.6%). This footer grounds the bot in the real funnel so the generated
# labels reflect genuine abandonment behaviour — the persona must only complete
# when the journey actually earns it.
REALISM_FOOTER = """

---

BEHAVIOURAL REALISM (CRITICAL — read before you act)
You are a real person, not a helpful assistant. You are NOT trying to finish the
form to be cooperative. In the real UNIQA online funnel:
  - Only about 5-6 in 100 people who start actually complete the purchase online.
  - ~66% leave at the FIRST price screen (step 4).
  - ~78% of those who remain leave at the FINAL price screen (step 7).
So your DEFAULT tendency is to abandon or route to an advisor the moment the
journey hits one of YOUR specific annoyances or pain points described above.
Continue to the next step ONLY when nothing has genuinely bothered you yet.
Reach the final purchase (step 12) ONLY if the whole journey actually satisfied
your needs — which, for someone like you, is the exception, not the rule.
Pick "abandon" or "route_advisor" exactly as your character would: silently and
early if you are the impatient type, after hesitation if you are the careful
type. Do not narrate as an AI. Do not complete the purchase just to be helpful."""


def _load_persona_prompt(md_path: Path) -> str:
    """Turn a persona briefing (.md) into an in-character system prompt.

    Strips the team-facing meta header (title + "> Use this profile…" blockquote)
    and the trailing "## Source" provenance section, then prepends the hard
    in-character directive and appends the realism calibration footer.
    """
    raw = md_path.read_text(encoding="utf-8")

    # drop the trailing "## Source" provenance section (meta, not for the bot)
    src_idx = raw.find("\n## Source")
    if src_idx != -1:
        raw = raw[:src_idx]

    # strip the leading title line and the "> Use this profile…" blockquote / "---"
    body_lines = []
    skipping_header = True
    for line in raw.splitlines():
        s = line.strip()
        if skipping_header:
            if not s or s.startswith("#") or s.startswith(">") or s == "---":
                continue
            skipping_header = False
        body_lines.append(line)
    body = "\n".join(body_lines).strip()

    name = md_path.stem.capitalize()
    header = (f"You ARE {name}. Stay fully in character at all times. "
              f"You are a real human going through an insurance website, NOT an AI "
              f"assistant. Never break character or mention that you are a model.\n\n")
    return header + body + REALISM_FOOTER


def load_personas(persona_dir: Path) -> dict:
    """Build the PERSONAS table by reading each persona's .md briefing."""
    out = {}
    for key, (md_name, segment, display) in PERSONA_FILES.items():
        md_path = persona_dir / md_name
        if not md_path.exists():
            raise FileNotFoundError(
                f"Persona briefing not found: {md_path}. Expected {md_name} next to "
                f"persona_simulator.py (override with --persona-dir).")
        out[key] = {
            "segment": segment,
            "display": display,
            "system": _load_persona_prompt(md_path),
        }
    return out


# Populated in main() from --persona-dir (defaults to this script's directory).
PERSONAS: dict = {}

# Per-persona scenario flavors that diversify journeys and surface edge cases
# (kept persona-consistent; one is attached at random per journey).
SCENARIOS = {
    "franz": [
        "You are in a hurry on your phone during a commute.",
        "You already checked Durchblicker and have a price in mind.",
        "You are mildly annoyed because a competitor's form just wasted your time.",
        "You are relaxed at home in the evening, willing to read a bit more.",
        "A friend told you private insurance is 'actually not that expensive'.",
        "You are skeptical and ready to bail at the first sign of an advisor push.",
    ],
    "judith": [
        "It's late evening after the kids are asleep; you have limited patience.",
        "You want to get a price before mentioning it to your partner/advisor.",
        "A colleague recommended UNIQA and you're giving it a fair look.",
        "You're comparing UNIQA against an offer your advisor already sketched.",
        "You're worried the coverage won't fit your family's stage of life.",
        "You're calm and methodical, reading each tariff carefully.",
    ],
    "peter": [
        "You just got a surprising hospital bill and feel a bit stressed.",
        "A family member nagged you to 'finally sort out insurance'.",
        "You clicked a Google ad on your phone during a work break.",
        "You're tired after a shift and have little patience for forms.",
        "You half-expect to give up and call them instead.",
        "A colleague said UNIQA was fine, so you typed it in, unsure what you need.",
    ],
}

# Final-price surcharge scenarios (risk surcharge applied at step 7).
# (base_pct, weight) — most journeys see a small/no increase; some see a painful jump.
SURCHARGE_SCENARIOS = [(0.0, 0.20), (0.04, 0.34), (0.10, 0.26), (0.18, 0.14), (0.30, 0.06)]


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def build_funnel_brief(surcharge_pct: int, scenario: str) -> str:
    return f"""TODAY'S SITUATION: {scenario}

You are going through UNIQA's ONLINE health-insurance calculator (private Krankenversicherung).
React EXACTLY as you (the persona) would. Move through the steps IN ORDER: 1, 2, 3, 4, 6, 7, 12.

THE STEPS AND THE RULES:
Step 1 — Where do you want coverage? Choose "doctor_visits", "hospital", or "both".
         ONLY "doctor_visits" can be completed online. "hospital" or "both" => you are routed to an advisor (journey ENDS, not an online purchase).
Step 2 — Who is insured? Choose "myself" or "other".
         ONLY "myself" stays online. "other" => routed to an advisor (journey ENDS).
Step 3 — Personal data: date of birth + social-insurance. First time real personal data is asked (a trust barrier).
Step 4 — Tariff selection / FIRST price shown. Four tariffs:
         Start €38.74/mo, Optimal €68.14/mo  -> purchasable ONLINE.
         Opt.Plus €96.66/mo, Premium €140.16/mo -> ADVISORY ONLY (choosing one routes you to an advisor; journey ENDS, not a conversion).
         Pick the tariff you would actually focus on.
Step 6 — Health questions (Gender, First and Last Name, Email, Phone Number, Height in cm, Weight, If they do competitive sports and if they are attending a physician the name of the physician) used to compute your FINAL price.
Step 7 — FINAL price after the health questions. In THIS journey the final price is your chosen tariff's monthly price
         INCREASED BY {surcharge_pct}% (a personal risk surcharge). React to that concrete number.
Step 12 — Closing: personal data, start date, payment, consents, confirmation. Completing this = a SUCCESSFUL ONLINE PURCHASE.

AT EACH STEP, choose ONE action:
 - "continue"      : proceed to the next step
 - "abandon"       : close the tab / give up (journey ENDS here)
 - "route_advisor" : you are sent to (or decide to call) a human advisor / customer service (journey ENDS here; natural at steps 1, 2, 4, or whenever you'd rather have a person)
STOP as soon as you abandon or are routed — produce no further steps.

FILL THESE SIGNALS PER STEP (realistic for you):
 - time_on_step_s    : seconds spent (integer)
 - hesitation_events : times you hesitate / hover / re-read (integer 0-12)
 - back_clicks       : times you navigate backwards (integer 0-4)
 - opened_competitor_tab : 1 if you open another tab to compare, else 0

OUTPUT FORMAT — output ONLY a JSON array, one object per step you actually reach. Example shape:
[{{"step_id":1,"action":"continue","coverage":"doctor_visits","for_whom":null,"tariff":null,"time_on_step_s":7,"hesitation_events":0,"back_clicks":0,"opened_competitor_tab":0,"note":"knew what I wanted"}},
 {{"step_id":2,"action":"continue","coverage":null,"for_whom":"myself","tariff":null,"time_on_step_s":5,"hesitation_events":0,"back_clicks":0,"opened_competitor_tab":0,"note":""}}]
Use null where a field is not relevant to that step. Do NOT write anything before or after the JSON array."""


def build_chat(tokenizer, persona_key: str, surcharge_pct: int, scenario: str) -> str:
    messages = [
        {"role": "system", "content": PERSONAS[persona_key]["system"]},
        {"role": "user",   "content": build_funnel_brief(surcharge_pct, scenario)},
    ]
    # Mistral instruct models have no real system role in their template; fold it in.
    try:
        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    except Exception:
        merged = messages[0]["content"] + "\n\n" + messages[1]["content"]
        return tokenizer.apply_chat_template(
            [{"role": "user", "content": merged}], tokenize=False, add_generation_prompt=True
        )


# ---------------------------------------------------------------------------
# Output parsing + normalization
# ---------------------------------------------------------------------------

def _extract_json_array(text: str):
    """Pull the first top-level JSON array out of the model output."""
    start = text.find("[")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                blob = text[start:i + 1]
                try:
                    return json.loads(blob)
                except json.JSONDecodeError:
                    # tolerate trailing commas
                    cleaned = re.sub(r",\s*([\]}])", r"\1", blob)
                    try:
                        return json.loads(cleaned)
                    except json.JSONDecodeError:
                        return None
    return None


def _norm_tariff(val) -> Optional[str]:
    if not val:
        return None
    s = re.sub(r"[^A-Z]", "", str(val).upper())
    if s.startswith("OPTPLUS") or s == "OPTPLUS":
        return "Opt.Plus"
    if "PREMIUM" in s:
        return "Premium"
    if "OPTIMAL" in s:
        return "Optimal"
    if "START" in s:
        return "Start"
    if "OPT" in s and "PLUS" in s:
        return "Opt.Plus"
    return None


def _norm_coverage(val) -> Optional[str]:
    if not val:
        return None
    s = str(val).lower()
    if "both" in s:
        return "both"
    if "hosp" in s or "krankenhaus" in s or "klinik" in s:
        return "hospital"
    if "doctor" in s or "arzt" in s:
        return "doctor_visits"
    return None


def _norm_forwhom(val) -> Optional[str]:
    if not val:
        return None
    s = str(val).lower()
    if "other" in s or "ander" in s:
        return "other"
    if "my" in s or "self" in s or "mich" in s:
        return "myself"
    return None


def _as_int(val, lo: int, hi: int, default: int = 0) -> int:
    try:
        return max(lo, min(hi, int(round(float(val)))))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Journey assembly — enforce funnel scope rules, ground numeric fields
# ---------------------------------------------------------------------------

def assemble_journey(raw_steps, session_id: str, persona_key: str,
                     surcharge_pct: int, scenario: str, temperature: float) -> list[dict]:
    """Convert parsed model steps into validated CSV rows. Enforces scope rules."""
    persona_disp = PERSONAS[persona_key]["display"]
    segment = PERSONAS[persona_key]["segment"]

    # index model steps by step_id for easy lookup
    by_id = {}
    for st in raw_steps if isinstance(raw_steps, list) else []:
        if isinstance(st, dict) and "step_id" in st:
            try:
                by_id[int(st["step_id"])] = st
            except (TypeError, ValueError):
                continue

    rows: list[dict] = []
    cum_time = 0.0
    coverage = for_whom = tariff = ""
    advisory_clicked = 0
    provisional = final = delta = None
    outcome = "abandoned"
    last_step = None

    for step_id in STEP_ORDER:
        st = by_id.get(step_id, {})
        action = str(st.get("action", "continue")).lower().strip()
        if action not in ("continue", "abandon", "route_advisor"):
            action = "continue"

        time_s = _as_int(st.get("time_on_step_s"), 1, 1200, default=20)
        n_hes = _as_int(st.get("hesitation_events"), 0, 12, default=0)
        n_back = _as_int(st.get("back_clicks"), 0, 4, default=0)
        opened_tab = 1 if _as_int(st.get("opened_competitor_tab"), 0, 1, default=0) == 1 else 0
        note = str(st.get("note", "")).replace("\n", " ").strip()[:300]

        terminal = False
        routed = False

        # ---- step-specific state + scope enforcement ----
        if step_id == 1:
            coverage = _norm_coverage(st.get("coverage")) or "doctor_visits"
            if coverage != "doctor_visits":
                action, terminal, routed = "route_advisor", True, True
            elif action != "continue":
                terminal = True

        elif step_id == 2:
            for_whom = _norm_forwhom(st.get("for_whom")) or "myself"
            if for_whom == "other":
                action, terminal, routed = "route_advisor", True, True
            elif action != "continue":
                terminal = True

        elif step_id == 3:
            if action != "continue":
                terminal = True

        elif step_id == 4:
            tariff = _norm_tariff(st.get("tariff")) or "Optimal"
            provisional = TARIFF_PRICES[tariff]
            if tariff in ADVISORY_TARIFFS:
                advisory_clicked = 1
                action, terminal, routed = "route_advisor", True, True
            else:
                if action != "continue":
                    terminal = True

        elif step_id == 6:
            if action != "continue":
                terminal = True

        elif step_id == 7:
            if provisional is None:                       # safety: tariff somehow missing
                tariff = tariff or "Optimal"
                provisional = TARIFF_PRICES[tariff]
            delta = round(surcharge_pct / 100.0, 4)
            final = round(provisional * (1 + delta), 2)
            if action != "continue":
                terminal = True

        elif step_id == 12:
            if action == "continue":
                outcome = "converted"
            else:
                terminal = True

        cum_time += time_s
        last_step = step_id

        rows.append({
            "session_id":              session_id,
            "persona":                 persona_disp,
            "segment":                 segment,
            "step_id":                 step_id,
            "step_name":               STEP_NAMES[step_id],
            "coverage_selection":      coverage,
            "for_whom":                for_whom,
            "tariff_selected":         tariff,
            "advisory_tariff_clicked": advisory_clicked,
            "provisional_price":       "" if provisional is None else provisional,
            "final_price":             "" if final is None else final,
            "price_delta_pct":         "" if delta is None else delta,
            "time_on_step_s":          time_s,
            "cumulative_time_s":       round(cum_time, 1),
            "n_hesitation_events":     n_hes,
            "n_back_clicks":           n_back,
            "opened_competitor_tab":   opened_tab,
            "coach_intervened":        0,            # baseline (no-coach) dataset
            "coach_type":              "none",
            "label":                   1 if terminal else 0,
            "journey_outcome":         "advisor_routed" if routed else ("converted" if (step_id == 12 and action == "continue") else "abandoned"),
            "final_step_reached":      step_id,
            "gen_temperature":         round(temperature, 3),
            "scenario":                scenario,
            "reasoning":               note,
        })

        if terminal:
            outcome = "advisor_routed" if routed else "abandoned"
            break
    else:
        outcome = "converted"

    # backfill a clean journey-level outcome on every row
    for r in rows:
        r["journey_outcome"] = outcome
        r["final_step_reached"] = last_step
    return rows


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def run_persona(persona_key: str, n: int, llm, tokenizer, SamplingParams,
                rng: random.Random, base_seed: int, temp_lo: float, temp_hi: float,
                max_tokens: int):
    """Generate n journeys for one persona; returns (rows, stats)."""
    prompts, metas, sampling = [], [], []
    for j in range(n):
        surcharge_pct = int(round(
            rng.choices([s[0] for s in SURCHARGE_SCENARIOS],
                        weights=[s[1] for s in SURCHARGE_SCENARIOS])[0] * 100
        ))
        scenario = rng.choice(SCENARIOS[persona_key])
        temperature = round(rng.uniform(temp_lo, temp_hi), 3)
        prompts.append(build_chat(tokenizer, persona_key, surcharge_pct, scenario))
        metas.append((f"{persona_key}_{j+1:05d}", surcharge_pct, scenario, temperature))
        sampling.append(SamplingParams(
            temperature=temperature, top_p=0.95, max_tokens=max_tokens,
            seed=base_seed + j,
        ))

    print(f"  [vLLM] generating {n} journeys for {persona_key} ...", flush=True)
    outputs = llm.generate(prompts, sampling)

    rows, n_parse_fail = [], 0
    counts = {"converted": 0, "abandoned": 0, "advisor_routed": 0}
    for out, (sid, surcharge_pct, scenario, temperature) in zip(outputs, metas):
        text = out.outputs[0].text
        parsed = _extract_json_array(text)
        if not parsed:
            n_parse_fail += 1
            continue
        journey = assemble_journey(parsed, sid, persona_key, surcharge_pct, scenario, temperature)
        if not journey:
            n_parse_fail += 1
            continue
        rows.extend(journey)
        counts[journey[-1]["journey_outcome"]] += 1

    stats = {"requested": n, "parse_fail": n_parse_fail, **counts}
    return rows, stats


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(description="LLM persona journey simulator (vLLM/Mistral).")
    p.add_argument("--persona", default="all",
                   choices=["franz", "judith", "peter", "all"],
                   help="Which persona to simulate (default: all).")
    p.add_argument("--per-persona", type=int, default=1000,
                   help="Journeys per persona (default: 1000).")
    p.add_argument("--model", required=True,
                   help="Model path or HF id (e.g. mistralai/Mistral-7B-Instruct-v0.2 "
                        "or a local snapshot dir under $HF_HOME).")
    p.add_argument("--output-dir", required=True,
                   help="Directory to write data_<persona>.csv (e.g. $PUBLIC/hackathon_data).")
    p.add_argument("--seed", type=int, default=1234, help="Base RNG/sampling seed.")
    p.add_argument("--temp-lo", type=float, default=0.7, help="Min sampling temperature.")
    p.add_argument("--temp-hi", type=float, default=1.05, help="Max sampling temperature.")
    p.add_argument("--max-tokens", type=int, default=900, help="Max new tokens per journey.")
    p.add_argument("--tensor-parallel-size", type=int, default=1,
                   help="Number of GPUs for vLLM tensor parallelism.")
    p.add_argument("--max-model-len", type=int, default=4096, help="vLLM max context length.")
    p.add_argument("--gpu-memory-utilization", type=float, default=0.90)
    p.add_argument("--persona-dir", default=None,
                   help="Directory holding the persona briefings (franz.md / judith.md / "
                        "peter.md). Defaults to this script's directory.")
    args = p.parse_args(argv)

    # Load persona prompts from the .md briefings (single source of truth).
    global PERSONAS
    persona_dir = Path(args.persona_dir) if args.persona_dir else Path(__file__).resolve().parent
    PERSONAS = load_personas(persona_dir)
    print(f"Loaded persona briefings from {persona_dir}: {', '.join(PERSONAS)}", flush=True)

    # Import heavy deps here so --help works without a GPU env.
    from vllm import LLM, SamplingParams
    from transformers import AutoTokenizer

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading model: {args.model}", flush=True)
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    llm = LLM(
        model=args.model,
        tensor_parallel_size=args.tensor_parallel_size,
        max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_memory_utilization,
        dtype="bfloat16",
        seed=args.seed,
    )
    print(f"Model ready in {time.time() - t0:.1f}s", flush=True)

    personas = ["franz", "judith", "peter"] if args.persona == "all" else [args.persona]
    rng = random.Random(args.seed)

    for pk in personas:
        print(f"\n=== Persona: {PERSONAS[pk]['display']} ({PERSONAS[pk]['segment']}) ===", flush=True)
        rows, stats = run_persona(
            pk, args.per_persona, llm, tokenizer, SamplingParams,
            rng, args.seed, args.temp_lo, args.temp_hi, args.max_tokens,
        )
        out_path = out_dir / f"data_{pk}.csv"
        write_csv(out_path, rows)
        n_sessions = stats["converted"] + stats["abandoned"] + stats["advisor_routed"]
        print(f"  Wrote {len(rows):,} rows / {n_sessions:,} valid journeys -> {out_path}", flush=True)
        print(f"  parse_fail={stats['parse_fail']}  "
              f"converted={stats['converted']}  "
              f"abandoned={stats['abandoned']}  "
              f"advisor_routed={stats['advisor_routed']}", flush=True)
        if n_sessions:
            print(f"  conversion rate = {stats['converted'] / n_sessions * 100:.1f}%", flush=True)

    print("\nDone.", flush=True)


if __name__ == "__main__":
    main()
