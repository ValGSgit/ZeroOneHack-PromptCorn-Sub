#!/usr/bin/env python3
"""
demo.py — interactive roleplay demo for the UNIQA Conversion Coach.

You step through the funnel AS the persona. At each step the coach shows you
what it detects and what intervention it would fire. You decide whether to
continue, abandon, or call an advisor — or let the persona decide automatically.

Usage:
    python demo.py                        # pick persona interactively
    python demo.py --persona franz        # jump straight in
    python demo.py --persona judith --no-coach   # see baseline (no coach)
    python demo.py --auto --seed 42       # auto-run all three, show traces
    python demo.py --compare judith --seed 17    # Judith: advisor_routed → CONVERTED
    python demo.py --compare franz --seed 10     # Franz:  abandoned → CONVERTED
    python demo.py --compare peter --seed 5      # Peter:  advisor_routed → CONVERTED

Via run.sh:
    ./run.sh demo --compare judith --seed 17
    ./run.sh demo --auto --seed 17
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from typing import Optional

import numpy as np

from coach import config as C
from coach.funnel import make_plan, resolve, Policy, Plan, Result
from coach.coach import CoachPolicy


# ---------------------------------------------------------------------------
# Terminal colours (fall back gracefully when not a tty)
# ---------------------------------------------------------------------------

if sys.stdout.isatty():
    _B  = "\033[1m"
    _D  = "\033[2m"
    _R  = "\033[0m"
    _G  = "\033[32m"
    _Y  = "\033[33m"
    _C  = "\033[36m"
    _M  = "\033[35m"
    _RE = "\033[31m"
else:
    _B = _D = _R = _G = _Y = _C = _M = _RE = ""


def _hdr(text: str, char: str = "─") -> str:
    w = min(70, 70)
    pad = max(0, w - len(text) - 2)
    return f"{_B}{char * 2} {text} {char * (pad)}{_R}"


def _step_bar(step: int, total_steps: int = 7) -> str:
    idx = C.STEP_ORDER.index(step) + 1
    filled = "█" * idx
    empty  = "░" * (total_steps - idx)
    return f"{_G}{filled}{_D}{empty}{_R} {idx}/{total_steps}"


# ---------------------------------------------------------------------------
# Rich trace printer (used by --auto and --compare)
# ---------------------------------------------------------------------------

def print_trace(result: Result, persona: str, label: str = "") -> None:
    outcome_colour = _G if result.outcome == "converted" else (_Y if "routed" in result.outcome else _RE)
    header = f"{persona}"
    if label:
        header += f" [{label}]"
    print(f"\n{_hdr(header)}")
    iv_map = {step: iv for step, iv in result.interventions}
    for rec in result.steps:
        sig = rec.signals
        sig_parts = []
        if sig.time_on_step_s >= 40:
            sig_parts.append(f"dwell {sig.time_on_step_s}s ⚠")
        else:
            sig_parts.append(f"dwell {sig.time_on_step_s}s")
        if sig.n_hesitation_events:
            sig_parts.append(f"hes={sig.n_hesitation_events}")
        if sig.n_back_clicks:
            sig_parts.append(f"back={sig.n_back_clicks}")
        if sig.opened_competitor_tab:
            sig_parts.append(f"{_Y}competitor-tab{_R}")
        sig_str = "  ".join(sig_parts)

        price_str = ""
        if rec.final_price:
            price_str = f"  {_C}€{rec.final_price:.2f}/mo{_R}"
        elif rec.provisional_price:
            price_str = f"  {_C}€{rec.provisional_price:.2f}/mo{_R}"

        left_marker = f"  {_RE}✗ LEFT HERE{_R}" if rec.left_here else ""
        print(f"  step {rec.step:>2}  {rec.step_name:<22}  {sig_str}{price_str}{left_marker}")

        if rec.step in iv_map:
            iv = iv_map[rec.step]
            hm_str = f"{iv.hazard_multiplier:.2f}×hazard"
            cat_tag = f"{_M}[{iv.category}/{iv.name}]{_R}"
            print(f"         {_G}↳ COACH{_R} {cat_tag}  {_D}{hm_str}{_R}")
            # strip the internal [rule|seg] prefix for cleaner display
            msg = iv.message
            if msg.startswith("["):
                end = msg.find("] ")
                prefix = msg[1:end]
                msg = msg[end + 2:]
                print(f"           {_D}trigger: {prefix}{_R}")
            print(f"           \"{_B}{msg}{_R}\"")

    print(f"  {_B}outcome:{_R} {outcome_colour}{result.outcome.upper()}{_R}")


# ---------------------------------------------------------------------------
# Interactive single-journey mode
# ---------------------------------------------------------------------------

PERSONA_BLURBS = {
    "Franz":  "Franz — digital-first, analytical, hates advisor detours. Drops at FINAL price if it surprises him.",
    "Judith": "Judith — researches online, commits via advisor. Drops at INITIAL price from sticker shock.",
    "Peter":  "Peter — service-oriented, easily overwhelmed. Drops early from complexity, welcomes a callback.",
}

STEP_FLAVOUR = {
    1:  "Where do you want coverage?  (doctor_visits ✓ | hospital → advisor route)",
    2:  "Who is insured?  (myself ✓ | other persons → advisor route)",
    3:  "Personal data — date of birth + social insurance number.  Trust barrier.",
    4:  "Tariff selection + FIRST price shown.  The 66% drop-off cliff.",
    6:  "Health questions — detailed risk screening for final premium calculation.",
    7:  "FINAL price after health answers.  The 78% drop-off cliff.",
    12: "Checkout — payment details + confirmation.  Completing this = CONVERTED.",
}


def _risk_bar(risk: float, width: int = 20) -> str:
    filled = int(round(risk * width))
    colour = _RE if risk > 0.6 else (_Y if risk > 0.35 else _G)
    return f"{colour}{'█' * filled}{'░' * (width - filled)}{_R} {risk:.0%}"


def _ask(prompt: str, choices: list[str], default: str = "") -> str:
    choices_str = "/".join(
        f"{_B}{c.upper()}{_R}" if c == default else c for c in choices
    )
    while True:
        raw = input(f"{prompt} [{choices_str}]: ").strip().lower()
        if not raw and default:
            return default
        if raw in choices:
            return raw
        print(f"  Please enter one of: {', '.join(choices)}")


def run_interactive(persona: str, seed: int, coach_on: bool, model=None) -> None:
    rng = np.random.default_rng(seed)
    plan = make_plan(rng, persona)

    print(f"\n{_hdr(f'UNIQA Conversion Coach  —  Interactive Demo', '═')}")
    print(f"  {_B}Persona:{_R} {persona}   {_D}{PERSONA_BLURBS[persona]}{_R}")
    print(f"  {_B}Seed:{_R}    {seed}   "
          f"{'  ' + _G + 'Coach: ON' + _R if coach_on else _D + 'Coach: OFF' + _R}")
    if plan.oos1:
        print(f"  {_Y}Note: this seed's persona selected hospital coverage at step 1 "
              f"(out-of-scope → advisor route).{_R}")
    if plan.oos4:
        print(f"  {_Y}Note: this seed's persona clicked Opt.Plus/Premium at step 4 "
              f"(advisor-only tariff).{_R}")
    print(f"  {_D}Surcharge scenario: +{plan.surcharge*100:.0f}% at final price{_R}")

    coach = CoachPolicy(persona, model=model) if coach_on else None

    cum_time = 0.0
    cum_hes  = 0
    cum_back = 0
    tariff: Optional[str] = None
    provisional = final = delta = None

    for step in C.STEP_ORDER:
        sig = plan.signals[step]
        cum_time += sig.time_on_step_s
        cum_hes  += sig.n_hesitation_events
        cum_back += sig.n_back_clicks

        print(f"\n{_hdr(f'Step {step}  —  {C.STEP_NAMES[step]}')}")
        print(f"  {_D}{STEP_FLAVOUR.get(step, '')}{_R}")
        print(f"  Progress: {_step_bar(step)}")

        # ---- price display ----
        if step == 4:
            tariff = plan.tariff if not plan.oos4 else "Opt.Plus"
            provisional = C.TARIFF_PRICES[tariff]
            print(f"\n  {_B}Tariffs shown:{_R}")
            for t, p in C.TARIFF_PRICES.items():
                online = t in C.ONLINE_TARIFFS
                marker = f"{_G}✓ online{_R}" if online else f"{_Y}advisory only{_R}"
                chosen = " ← persona focuses here" if t == tariff else ""
                print(f"    {t:8s} €{p:.2f}/mo  {marker}{_D}{chosen}{_R}")
            print(f"\n  {_B}Initial price (Optimal headline):{_R} €{C.TARIFF_PRICES['Optimal']:.2f}/mo")

        if step == 7:
            if provisional is None:
                tariff = tariff or "Optimal"
                provisional = C.TARIFF_PRICES[tariff]
            delta = plan.surcharge
            final = round(provisional * (1 + delta), 2)
            delta_eur = final - provisional
            arrow = f"{_RE}▲ +€{delta_eur:.2f} (+{delta*100:.0f}%){_R}" if delta > 0 else f"{_G}no change{_R}"
            print(f"\n  {_B}Provisional price:{_R} €{provisional:.2f}/mo")
            print(f"  {_B}Final price:{_R}       €{final:.2f}/mo   {arrow}")

        # ---- behavioural signals ----
        print(f"\n  {_B}Behavioural signals this step:{_R}")
        print(f"    dwell:            {sig.time_on_step_s}s"
              + (f"  {_Y}⚠ long{_R}" if sig.time_on_step_s >= 40 else ""))
        print(f"    hesitation:       {sig.n_hesitation_events}"
              + (f"  {_Y}⚠ high{_R}" if sig.n_hesitation_events >= 4 else ""))
        print(f"    back-clicks:      {sig.n_back_clicks}"
              + (f"  {_RE}⚠⚠ alarming{_R}" if sig.n_back_clicks >= 2 else ""))
        if sig.opened_competitor_tab:
            print(f"    competitor tab:   {_Y}YES — opened another tab to compare{_R}")
        print(f"    cumulative time:  {cum_time:.0f}s")

        # ---- forced out-of-scope ----
        forced_oos = (
            (step == 1 and plan.oos1) or
            (step == 2 and plan.oos2) or
            (step == 4 and plan.oos4)
        )
        if forced_oos and step == 4 and plan.oos4 and coach_on and coach:
            # advisory-click intervention may redirect
            from coach.funnel import Observation
            obs = Observation(
                persona_hint=None, step=step, step_name=C.STEP_NAMES[step], signals=sig,
                cumulative_time_s=round(cum_time, 1), tariff_clicked=tariff,
                advisory_click=True, provisional_price=provisional, final_price=final,
                price_delta_pct=delta,
            )
            iv = coach.act(obs)
            if iv:
                print(f"\n  {_G}╔══ COACH INTERVENES ══╗{_R}")
                print(f"  {_G}║{_R} Type:    {_M}{iv.category} / {iv.name}{_R}")
                print(f"  {_G}║{_R} Effect:  hazard ×{iv.hazard_multiplier:.2f}  switch-prob {iv.switch_prob:.0%}")
                print(f"  {_G}║{_R} Message: \"{_B}{iv.message}{_R}\"")
                print(f"  {_G}╚══════════════════════╝{_R}")
                if plan.save_coin[step] < iv.switch_prob:
                    print(f"\n  {_G}→ Persona accepts the steer and switches to Optimal online.{_R}")
                    tariff = "Optimal"
                    provisional = C.TARIFF_PRICES[tariff]
                    forced_oos = False

        if forced_oos:
            oos_reason = {
                1: "hospital/both selected → out of scope",
                2: "'other persons' selected → out of scope",
                4: "Opt.Plus/Premium selected → advisory only",
            }[step]
            print(f"\n  {_Y}⇢ ROUTED TO ADVISOR  ({oos_reason}){_R}")
            print(f"\n{_hdr('Journey ended — ADVISOR_ROUTED', '═')}")
            return

        # ---- coach evaluation ----
        iv = None
        if coach_on and coach:
            from coach.funnel import Observation
            obs = Observation(
                persona_hint=None, step=step, step_name=C.STEP_NAMES[step], signals=sig,
                cumulative_time_s=round(cum_time, 1), tariff_clicked=tariff,
                advisory_click=False, provisional_price=provisional, final_price=final,
                price_delta_pct=delta,
            )
            iv = coach.act(obs)

            # show risk score
            risk = coach._risk(obs)
            rule = coach._hard_rule(obs)
            seg  = coach._infer_segment(obs)
            thr  = coach.thresholds.get(step, 0.55)
            print(f"\n  {_B}Coach detection:{_R}")
            print(f"    risk score:   {_risk_bar(risk)}")
            print(f"    threshold:    {thr:.0%}")
            print(f"    hard rule:    {_Y + rule + _R if rule else _D + 'none' + _R}")
            print(f"    inferred seg: {_C}{seg}{_R}")

            if iv:
                msg_display = iv.message
                if msg_display.startswith("["):
                    end = msg_display.find("] ")
                    prefix = msg_display[1:end]
                    msg_display = msg_display[end + 2:]
                    trigger_display = prefix
                else:
                    trigger_display = f"risk={risk:.2f}"
                print(f"\n  {_G}╔══ COACH INTERVENES ══╗{_R}")
                print(f"  {_G}║{_R} Trigger: {_D}{trigger_display}{_R}")
                print(f"  {_G}║{_R} Type:    {_M}{iv.category} / {iv.name}{_R}")
                print(f"  {_G}║{_R} Effect:  hazard ×{iv.hazard_multiplier:.2f}"
                      f"  annoyance risk {(1-iv.hazard_multiplier)*100:.0f}pp reduction")
                print(f"  {_G}║{_R} Message: \"{_B}{msg_display}{_R}\"")
                print(f"  {_G}╚══════════════════════╝{_R}")
            else:
                print(f"    {_D}→ no intervention fired at this step{_R}")

        # ---- persona's baseline decision ----
        h = C.BASE_HAZARD[persona][step]
        if step == 7:
            h = min(0.99, h + C.SURCHARGE_SENSITIVITY[persona] * (delta or 0))
        would_leave_base = plan.friction[step] >= (1 - h)

        if iv:
            h_coached = max(0.0, min(0.999, h * iv.hazard_multiplier))
            would_leave_coached = plan.friction[step] >= (1 - h_coached)
        else:
            would_leave_coached = would_leave_base

        effective_leave = would_leave_coached if coach_on else would_leave_base

        # ---- user prompt ----
        print(f"\n  {_B}Persona's simulated state:{_R}")
        print(f"    friction score:  {plan.friction[step]:.2f}   "
              f"(leave threshold: {1-(h_coached if coach_on and iv else h):.2f})")
        if would_leave_base and not (coach_on and iv and not would_leave_coached):
            print(f"    {_RE}⚠ WITHOUT coach: persona would LEAVE here{_R}")
        if coach_on and iv and would_leave_base and not would_leave_coached:
            print(f"    {_G}✓ Coach reduced hazard enough to keep the persona going{_R}")

        choices = ["continue", "abandon", "advisor", "auto"]
        print(f"\n  {_D}Your turn: play the persona.{_R}")
        print(f"  {_D}  continue = proceed to next step{_R}")
        print(f"  {_D}  abandon  = close the tab{_R}")
        print(f"  {_D}  advisor  = call/route to an advisor{_R}")
        print(f"  {_D}  auto     = let the simulation decide (based on friction score){_R}")
        default = "auto"
        action = _ask("  Your action", choices, default)

        if action == "auto":
            if effective_leave:
                is_routed = plan.route_coin[step] < C.ROUTE_FRACTION[persona][step]
                action = "advisor" if is_routed else "abandon"
                print(f"    {_D}→ auto: {action}{_R}")
            else:
                action = "continue"
                print(f"    {_D}→ auto: continue{_R}")

        if action == "abandon":
            print(f"\n{_hdr('Journey ended — ABANDONED', '═')}")
            print(f"  Persona left at step {step} ({C.STEP_NAMES[step]}).")
            return

        if action == "advisor":
            print(f"\n{_hdr('Journey ended — ADVISOR_ROUTED', '═')}")
            print(f"  Routed to advisor at step {step}.")
            return

    # reached step 12 and continued
    print(f"\n{_hdr('Journey ended — CONVERTED  🎉', '═')}")
    if final:
        print(f"  Online purchase complete. Monthly premium: €{final:.2f}  (tariff: {tariff})")
    else:
        print(f"  Online purchase complete. Tariff: {tariff or 'Optimal'}")


# ---------------------------------------------------------------------------
# Side-by-side compare mode
# ---------------------------------------------------------------------------

def run_compare(persona: str, seed: int, model=None) -> None:
    rng_b = np.random.default_rng(seed)
    plan = make_plan(rng_b, persona)

    coaches = {persona: CoachPolicy(persona, model=model)}

    rb = resolve(plan, Policy())
    rc = resolve(plan, coaches[persona])

    print(f"\n{_hdr(f'COMPARE  —  {persona}  seed={seed}', '═')}")
    print_trace(rb, persona, "no coach")
    print_trace(rc, persona, "with coach")

    flipped = rb.outcome != "converted" and rc.outcome == "converted"
    if flipped:
        print(f"\n  {_G}{_B}→ Coach flipped this run: {rb.outcome} → CONVERTED{_R}")
    elif rb.outcome == rc.outcome:
        print(f"\n  {_D}→ Same outcome both runs: {rb.outcome}{_R}")
    else:
        print(f"\n  {_Y}→ Different outcome: {rb.outcome} → {rc.outcome}{_R}")


# ---------------------------------------------------------------------------
# Auto-run all three personas (non-interactive)
# ---------------------------------------------------------------------------

def run_auto_all(seed: int, model=None) -> None:
    print(f"\n{_hdr('AUTO  —  all three personas  seed=' + str(seed), '═')}")
    rng = np.random.default_rng(seed)
    for persona in C.PERSONA_MIX:
        plan = make_plan(rng, persona)
        coach = CoachPolicy(persona, model=model)
        rb = resolve(plan, Policy())
        rc = resolve(plan, coach)
        print_trace(rb, persona, "no coach")
        print_trace(rc, persona, "with coach")
        flipped = rb.outcome != "converted" and rc.outcome == "converted"
        tag = f"{_G}FLIPPED{_R}" if flipped else f"{_D}same{_R}"
        print(f"  [{tag}]  {rb.outcome} → {rc.outcome}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--persona", choices=["franz", "judith", "peter", "all"],
                    default=None, help="Persona to simulate.")
    ap.add_argument("--seed", type=int, default=None,
                    help="RNG seed (default: random).")
    ap.add_argument("--no-coach", action="store_true",
                    help="Disable the coach (baseline run).")
    ap.add_argument("--auto", action="store_true",
                    help="Non-interactive: auto-resolve every step and print trace.")
    ap.add_argument("--compare", metavar="PERSONA",
                    choices=["franz", "judith", "peter"],
                    help="Side-by-side baseline vs coach for one persona.")
    ap.add_argument("--model", default="artifacts/coach_model.pkl",
                    help="Path to trained coach model (default: artifacts/coach_model.pkl).")
    args = ap.parse_args()

    # load trained model
    model = None
    try:
        import joblib
        model = joblib.load(args.model)
        print(f"{_D}Loaded model: {args.model}{_R}")
    except Exception as e:
        print(f"{_Y}Warning: could not load model ({e}). Using heuristic fallback.{_R}")

    seed = args.seed if args.seed is not None else random.randint(0, 99999)

    # ---- compare mode ----
    if args.compare:
        run_compare(args.compare.capitalize(), seed, model)
        return

    # ---- all + auto ----
    if args.persona == "all" or args.auto:
        run_auto_all(seed, model)
        return

    # ---- interactive ----
    persona = args.persona
    if persona is None:
        print(f"\n{_B}Choose a persona:{_R}")
        for key, blurb in PERSONA_BLURBS.items():
            print(f"  {_B}{key.lower()[0]}{_R} / {key.lower():7s} — {blurb}")
        choice = _ask("\nPersona", ["franz", "judith", "peter", "f", "j", "p"], "franz")
        persona = {"f": "franz", "j": "judith", "p": "peter"}.get(choice, choice)

    persona_cap = persona.capitalize()
    if seed is None:
        seed = random.randint(0, 99999)
        print(f"  Using random seed {seed}  (pass --seed {seed} to replay this exact run)")

    run_interactive(persona_cap, seed, coach_on=not args.no_coach, model=model)

    print(f"\n{_D}Run again:{_R}")
    print(f"  python demo.py --persona {persona} --seed {seed}")
    print(f"  python demo.py --compare {persona} --seed {seed}")
    print(f"  python demo.py --persona {persona} --seed {seed} --no-coach")


if __name__ == "__main__":
    main()
