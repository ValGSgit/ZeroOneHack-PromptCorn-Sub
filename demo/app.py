#!/usr/bin/env python3
"""
UNIQA Conversion Coach – FastAPI + SLM + modern UI.
Run with: pixi run start
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

# Bridge to the REAL leonardo_sim implementation (single source of truth for
# prices / personas / funnel cliffs + the live paired baseline-vs-coach run).
import engine

# torch / transformers power the optional Phi-3 chat. They are heavy and only
# needed for the conversational panel — import them lazily so the demo (and the
# whole engine/evaluation showcase) still runs on a plain CPU node without them.
try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    _TORCH_AVAILABLE = True
except Exception:  # noqa: BLE001 - degrade to doc-grounded replies, never crash
    torch = None
    AutoModelForCausalLM = AutoTokenizer = None
    _TORCH_AVAILABLE = False

# ----------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("uniqa-coach")
logging.getLogger("transformers").setLevel(logging.ERROR)

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
class Config:
    MODEL_ID = os.environ.get("CHAT_MODEL", "microsoft/Phi-3-mini-4k-instruct")
    HF_HOME = os.environ.get("HF_HOME", str(Path.home() / ".cache" / "huggingface"))
    PRELOAD_SLM = os.environ.get("PRELOAD_SLM", "").lower() in ("1", "true", "yes")
    HOST = os.environ.get("HOST", "127.0.0.1")
    PORT = int(os.environ.get("PORT", "9696"))
    MAX_HISTORY = 16
    SLM_MAX_NEW_TOKENS = 150
    SLM_MAX_PROMPT_LEN = 2048

# ----------------------------------------------------------------------
# Product constants — sourced from the real engine (engine.py -> coach.config
# -> personas.js) so the demo can never drift from the judged numbers. Falls
# back to spec-accurate literals if leonardo_sim is unavailable.
# ----------------------------------------------------------------------
# Keep the demo's compact JS-friendly keys (OptPlus) but take the VALUES from the
# engine, which uses the spec spelling "Opt.Plus".
_EP = engine.TARIFF_PRICES
TARIFFS = {
    "Start": _EP.get("Start", 38.74),
    "Optimal": _EP.get("Optimal", 68.14),
    "OptPlus": _EP.get("Opt.Plus", _EP.get("OptPlus", 96.66)),
    "Premium": _EP.get("Premium", 140.16),
}
ONLINE_TARIFFS = tuple(engine.ONLINE_TARIFFS)
STEPS = list(engine.STEP_ORDER)
# Human-friendly step labels for the chat copy (engine uses snake_case ids).
STEP_NAMES = {
    1: "coverage",
    2: "who",
    3: "personal data",
    4: "tariff / first price",
    6: "health questions",
    7: "final price",
    12: "checkout",
}

# Grounding docs for the SLM system prompt. These were referenced but never
# defined before (a guaranteed NameError the moment the model loaded); they now
# come from the real persona briefings + engine constants.
FUNNEL_DOC = engine.FUNNEL_DOC
PRODUCT_DOC = engine.PRODUCT_DOC
PERSONA_DOCS = engine.PERSONA_DOCS

# ----------------------------------------------------------------------
# Intent detection
# ----------------------------------------------------------------------
_INTENT_RULES = [
    ("frustration", {"wtf", "ugh", "damn", "hate", "huh", "sucks", "argh"},
     ["this sucks", "makes no sense", "waste of time"]),
    ("wants_human", {"advisor", "phone", "agent", "human", "someone", "callback"},
     ["call me", "speak to", "real person", "can't you help", "need help", "please help"]),
    ("price_jump", {"increased", "surcharge", "changed"},
     ["went up", "higher than", "price changed", "why is it more", "more than the estimate"]),
    ("price_high", {"expensive", "pricey", "afford", "costly"},
     ["too much", "too expensive", "a lot", "bit steep", "a month is"]),
    ("advisory_tariff", {"premium"}, ["opt.plus", "opt plus", "advisory required", "advisory only"]),
    ("comparing", {"compare", "durchblicker", "check24", "generali", "helvetia"},
     ["other insurer", "better deal", "somewhere else", "shopping around"]),
    # Understanding the CHOICES on a step (hospital vs doctor, myself vs others,
    # Start vs Optimal, "what's the difference …"). Must be matched BEFORE the
    # generic glossary ("unfamiliar"), otherwise "what is the difference between
    # hospital and doctor visits" wrongly triggers the eye-surgery glossary.
    ("explain_options", {"difference", "differences", "hospital", "outpatient",
                         "inpatient", "ambulant"},
     ["difference between", "what's the difference", "what is the difference",
      "whats the difference", " vs ", "versus", "hospital stay", "hospital stays",
      "doctor visit", "doctor visits", "myself or", "other persons",
      "which of these", "compare these", "start or optimal", "optimal or start"]),
    ("step_explain", {"explain"}, ["what is this step", "what does this step", "what do i do",
                                   "where am i", "what's going on", "not sure what to do"]),
    ("unfamiliar", {"refractive", "heilbehelfe", "jargon", "means"},
     ["what is ", "what's a ", "what does ", "what are ", "don't understand", "what's covered"]),
    ("overwhelmed", {"complicated", "confused", "overwhelmed", "lost"},
     ["too many", "don't know", "no idea", "this is a lot", "too complex"]),
    ("trust", {"secure", "safe", "scam", "legit", "privacy"},
     ["is it safe", "my data", "can i trust", "not a scam"]),
    ("leaving", {"leave", "quit", "bye", "exit", "later"},
     ["give up", "forget it", "not now", "come back later", "changed my mind"]),
    ("recommend", {"recommend", "suggest", "best"},
     ["which one", "which plan", "what should i", "best for me", "help me choose", "just pick"]),
    ("options", {"options", "plan", "plans", "tariff", "tariffs", "choices"},
     ["show me", "what do you have", "what are my options", "what can i get"]),
    ("price_info", {"price", "prices", "cost", "costs"},
     ["how much", "what's the price", "per month", "monthly cost"]),
    ("greeting", {"hi", "hello", "hey", "start"}, ["good morning", "need insurance", "looking for"]),
    ("ready", {"ok", "okay", "yes", "sure", "next", "continue", "proceed"},
     ["sounds good", "let's do", "go ahead"]),
]

def detect_intent(text: str) -> Optional[str]:
    t = text.lower().strip()
    words = set(re.findall(r"[a-z']+", t))
    for intent, triggers, phrases in _INTENT_RULES:
        if words & triggers or any(p in t for p in phrases):
            return intent
    return None

# ----------------------------------------------------------------------
# Bayesian belief update
# ----------------------------------------------------------------------
# Persona order + belief prior come from the engine (the real 50/30/20 traffic mix).
PERSONAS = list(engine.PERSONAS)
PRIOR = dict(engine.PERSONA_PRIOR)
_EVIDENCE = {
    "price_high": (1.5, 0.5, 0.1), "price_jump": (2.0, 1.0, 0.1),
    "price_info": (1.0, 0.4, 0.1), "comparing": (2.5, 0.2, 0.0),
    "advisory_tariff": (0.8, 0.8, 0.1), "step_explain": (0.0, 0.8, 1.8),
    "explain_options": (0.2, 1.0, 1.4),
    "unfamiliar": (0.0, 2.0, 0.8), "overwhelmed": (0.0, 0.2, 2.8),
    "wants_human": (0.0, 0.3, 2.5), "recommend": (0.1, 0.5, 2.2),
    "trust": (0.2, 1.8, 0.4), "leaving": (0.6, 0.6, 0.4),
    "frustration": (0.3, 0.1, 1.5), "ready": (1.8, 0.4, 0.1),
}

def update_belief(belief: Dict[str, float], intent: Optional[str]) -> Dict[str, float]:
    ev = _EVIDENCE.get(intent, (0.3, 0.3, 0.3))
    log_odds = {}
    for p, w in zip(PERSONAS, ev):
        b = max(min(belief.get(p, 0.5), 0.999), 0.001)
        log_odds[p] = math.log(b / (1 - b)) + w * 0.4
    raw = {p: 1 / (1 + math.exp(-log_odds[p])) for p in PERSONAS}
    total = sum(raw.values())
    return {p: raw[p] / total for p in PERSONAS}

def top_segment(belief: Dict[str, float]) -> str:
    return max(belief, key=belief.get)

def safe_belief(data: any) -> Dict[str, float]:
    if isinstance(data, dict):
        try:
            return {p: min(max(float(data[p]), 0.0), 1.0) for p in PERSONAS}
        except (KeyError, TypeError, ValueError):
            pass
    return dict(PRIOR)

# ----------------------------------------------------------------------
# Risk scoring
# ----------------------------------------------------------------------
def score_risk(step: int, back_clicks: int, competitor_tab: bool, intent: Optional[str]) -> float:
    base = {4: 0.35, 7: 0.55}.get(step, 0.10)
    risk = base + back_clicks * 0.12 + (0.15 if competitor_tab else 0)
    if intent in ("leaving", "price_high", "price_jump", "overwhelmed"):
        risk += 0.20
    if intent in ("frustration", "advisory_tariff"):
        risk += 0.10
    return min(0.98, risk)

# ----------------------------------------------------------------------
# Doc‑grounded reply (fallback) – step‑aware
# ----------------------------------------------------------------------
def explain_options(text: str, step: int) -> Optional[str]:
    """Answer 'what's the difference between …' for the actual on-screen choices.
    Returns None to fall back to the generic step-options explanation."""
    t = (text or "").lower()
    mentions_cover = ("hospital" in t or "doctor" in t or "outpatient" in t
                      or "inpatient" in t or "ambulant" in t)
    mentions_who = ("myself" in t or "other person" in t or "others" in t
                    or "family" in t or "partner" in t or "children" in t)
    mentions_tariff = ("start" in t or "optimal" in t or "opt.plus" in t
                       or "opt plus" in t or "premium" in t)
    if mentions_cover or step == 1:
        return ("'Doctor visits' = private OUTPATIENT cover — GP, specialists, diagnostics, "
                "telemedicine — and is fully purchasable online. 'Hospital stays' = INPATIENT "
                "cover (private room, elective surgery) and needs an advisor call, so it's "
                "outside this online flow. To finish online, choose Doctor visits.")
    if mentions_who or step == 2:
        return ("'Myself only' keeps everything online and instant. 'Other persons' "
                "(partner / children) needs an advisor because family policies require extra "
                "checks. For an online purchase, pick 'Myself only'.")
    if mentions_tariff or step == 4:
        return (f"Start (€{TARIFFS['Start']:.2f}/mo) covers GP, specialists, medications and basic "
                f"diagnostics. Optimal (€{TARIFFS['Optimal']:.2f}/mo) adds therapies, medical aids "
                f"and refractive eye surgery. Both buy online; Opt.Plus (€{TARIFFS['OptPlus']:.2f}) "
                f"and Premium (€{TARIFFS['Premium']:.2f}) need an advisor.")
    return None


def doc_reply(intent: Optional[str], step: int, tariff: str, belief: Dict, top_seg: str,
              text: str = "") -> str:
    price = TARIFFS.get(tariff, 68.14)
    per_day = price / 30.0
    advisor_ok = top_seg in ("Judith", "Peter")

    # "What's the difference between these choices?" — answer the specific
    # comparison if we can, else fall through to the step-options explanation.
    if intent == "explain_options":
        specific = explain_options(text, step)
        if specific:
            return specific

    # Step‑specific options explanation
    if intent in ("options", "explain_options"):
        if step == 1:
            return ("On this step you have two options: 'Doctor visits' (fully online, covers GP, specialists, diagnostics) "
                    "or 'Hospital stays' (requires an advisor call, adds private room and elective surgery).")
        if step == 2:
            return ("Option 'Myself' keeps the application fully online. Option 'Other persons' (partner/children) "
                    "requires an advisor conversation because family policies need additional checks.")
        if step == 3:
            return ("Step 3 asks for your date of birth and social insurance number – these are needed to calculate "
                    "your personalised provisional premium. No other options here.")
        if step == 4:
            return (f"Two plans you can buy online today: Start (€{TARIFFS['Start']:.2f}/mo) covers essentials; "
                    f"Optimal (€{TARIFFS['Optimal']:.2f}/mo) adds therapies, medical aids, and eye surgery. "
                    f"Opt.Plus and Premium require an advisor call.")
        if step == 6:
            return ("The health questions are 'Yes/No' about chronic conditions, regular medication, and recent surgery. "
                    "Your answers adjust the final price but are always confidential.")
        if step == 7:
            return ("Step 7 shows your final personalised price. There are no further options here – you can go to checkout "
                    "or ask about adjusting coverage (which would require changing tariff in step 4).")
        if step == 12:
            return ("Checkout options: you can review your details, choose payment method (SEPA or credit card), "
                    "and confirm. Nothing is charged until you click Confirm.")
        return f"You're on step {step}. Ask me about the choices on this screen."

    # Other intents
    step_info = {
        1: "Step 1: choose 'Doctor visits' to stay fully online. 'Hospital stays' routes to an advisor.",
        2: "Step 2: 'Myself only' keeps you online. 'Other persons' routes to an advisor.",
        3: "Step 3 collects your date of birth and social insurance number for a personalised estimate.",
        4: f"Step 4: first price display. Start (€{TARIFFS['Start']:.2f}/mo) covers essentials; Optimal (€{TARIFFS['Optimal']:.2f}/mo) adds therapies and aids.",
        6: "Step 6: health questions to compute your final price. Answers are confidential.",
        7: "Step 7: your final price after the health assessment. A small surcharge is normal.",
        12: "Step 12: final checkout. Nothing is charged until you confirm.",
    }

    if intent == "greeting":
        return ("Hi! I'm your conversion coach — I help you finish online without the back-and-forth. "
                f"You're on the {STEP_NAMES.get(step, 'current')} step. Ask me about the options, the price, "
                "or what to pick.")

    if intent in ("step_explain", None):
        return step_info.get(step, f"You're on step {step}. Ask me anything.")

    if intent == "unfamiliar":
        return ("Glossary: 'Refractive eye surgery' = laser vision correction (Optimal+). "
                "'Medical aids' = hearing aids, orthotics (Optimal+). "
                "'Therapeutic treatments' = physio, speech therapy (Optimal+). "
                "What specific term would you like me to explain?")

    if intent == "price_jump":
        return (f"The step‑4 price is a provisional estimate. Step‑7 is your final risk‑adjusted premium — "
                f"a small surcharge is standard. You can still complete online at €{price:.2f}/mo.")

    if intent == "price_high":
        cheaper = (f"Start at €{TARIFFS['Start']:.2f}/mo covers the essentials if budget is the main factor."
                   if tariff != "Start" else "That is already the lowest online tariff.")
        return (f"€{price:.2f}/mo works out to €{per_day:.2f}/day for private‑doctor cover. {cheaper}")

    if intent in ("recommend", "overwhelmed"):
        if top_seg == "Peter":
            return (f"My recommendation: Optimal (€{TARIFFS['Optimal']:.2f}/mo) — the solid all‑rounder for most "
                    "people. Fully online, no advisor call needed. Or I can arrange a quick callback.")
        return (f"Optimal (€{TARIFFS['Optimal']:.2f}/mo) is the most popular online choice. "
                f"If budget is tight, Start (€{TARIFFS['Start']:.2f}) covers your most‑used doctors.")

    if intent == "wants_human":
        if advisor_ok:
            return "I can arrange a callback — an advisor finishes this with you in about 5 minutes. Want me to set that up?"
        return "I can save your progress so you can finish online whenever suits you. Want the resume link?"

    if intent == "comparing":
        return (f"Optimal at €{TARIFFS['Optimal']:.2f}/mo is well‑positioned against comparable private‑doctor tariffs. "
                f"Happy to show you the line‑item breakdown.")

    if intent == "advisory_tariff":
        return (f"Opt.Plus and Premium need an advisor call by regulation — not online purchasable. "
                f"Optimal (€{TARIFFS['Optimal']:.2f}/mo) covers most of the same and completes fully online today.")

    if intent == "trust":
        return ("Your data is encrypted, GDPR‑compliant, and nothing is charged until final confirmation. "
                "You can review every detail before committing.")

    if intent == "leaving":
        return "I can save exactly where you are so you pick up later with no re‑typing. Or tell me what's blocking you."

    if intent == "price_info":
        return (f"Online: Start €{TARIFFS['Start']:.2f}/mo · Optimal €{TARIFFS['Optimal']:.2f}/mo. "
                f"You're looking at {tariff} (≈€{per_day:.2f}/day). Want me to break down what's covered?")

    return step_info.get(step, "Ask me about the options, the price, or anything that's unclear.")

# ----------------------------------------------------------------------
# Coach DECISION layer — map a detected signal to the real intervention the
# coach would fire (same taxonomy as leonardo_sim), respecting each segment's
# "must NOT". This is what makes the live panel *the coach*, with visible
# reasoning, rather than a generic chatbot. Phi-3 (if present) only rephrases.
# ----------------------------------------------------------------------
_SIGNAL_TO_INTERVENTION = {
    "price_high":      ("suggest_cheaper_tariff",     "reassurance"),
    "price_jump":      ("value_justification",        "reassurance"),
    "price_info":      ("value_justification",        "explanation"),
    "comparing":       ("market_comparison_signal",   "reassurance"),
    "advisory_tariff": ("suggest_online_tariff",      "alternative_offering"),
    "explain_options": ("term_glossary",              "explanation"),
    "unfamiliar":      ("term_glossary",              "explanation"),
    "overwhelmed":     ("simplify_recommendation",    "personalization"),
    "recommend":       ("simplify_recommendation",    "personalization"),
    "wants_human":     ("advisor_booking_proactive",  "handoff"),
    "trust":           ("reassurance_transparency",   "reassurance"),
    "leaving":         ("save_progress_resume_later", "retention"),
    "frustration":     ("reassurance_transparency",   "reassurance"),
    "step_explain":    ("term_glossary",              "explanation"),
    "options":         ("term_glossary",              "explanation"),
    "greeting":        ("welcome",                    "informational"),
    "ready":           ("encourage_continue",         "informational"),
}

def coach_decision(intent: Optional[str], top_seg: str) -> Dict[str, str]:
    """The coach's decision trace for one turn: detected signal, inferred
    segment, and the intervention it picks (respecting per-segment 'must NOT')."""
    name, cat = _SIGNAL_TO_INTERVENTION.get(intent or "", ("clarify_intent", "informational"))
    # Never push an advisor on a segment that dislikes it (Franz). Fall back to a
    # self-service nudge — exactly what the real coach does.
    if name == "advisor_booking_proactive" and not engine.ADVISOR_FRIENDLY.get(top_seg, True):
        name, cat = "save_progress_resume_later", "retention"
    return {
        "signal": intent or "open_message",
        "segment": top_seg,
        "intervention": name,
        "category": cat,
        # is this one of the segment's *documented* best interventions?
        "documented_best": name in engine.BEST_INTERVENTIONS.get(top_seg, []),
    }

def vary_reply(state, reply: str) -> str:
    """Avoid the coach repeating itself verbatim turn after turn."""
    recent = getattr(state, "recent_replies", [])
    if reply in recent:
        nudges = [
            " Anything specific you'd like me to clarify?",
            " Want me to break that down further?",
            " Happy to go deeper on any part.",
            " Let me know what would help most.",
        ]
        reply = reply.rstrip() + nudges[len(recent) % len(nudges)]
    recent.append(reply)
    state.recent_replies = recent[-5:]
    return reply

# ----------------------------------------------------------------------
# SLM (Phi‑3) loader & generation (non‑blocking)
# ----------------------------------------------------------------------
_slm_tokenizer: Optional[AutoTokenizer] = None
_slm_model: Optional[AutoModelForCausalLM] = None
_slm_load_lock = asyncio.Lock()
_slm_loading = False

async def ensure_slm_loaded() -> bool:
    global _slm_model, _slm_tokenizer, _slm_loading
    if not _TORCH_AVAILABLE:
        return False
    if _slm_model is not None:
        return True
    if _slm_loading:
        return False
    async with _slm_load_lock:
        if _slm_model is not None:
            return True
        if _slm_loading:
            return False
        _slm_loading = True
    try:
        logger.info(f"Loading SLM {Config.MODEL_ID} from cache {Config.HF_HOME} ...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        tokenizer = AutoTokenizer.from_pretrained(
            Config.MODEL_ID, cache_dir=Config.HF_HOME, trust_remote_code=False
        )
        model = AutoModelForCausalLM.from_pretrained(
            Config.MODEL_ID,
            torch_dtype=torch.bfloat16,
            attn_implementation="eager",
            cache_dir=Config.HF_HOME,
            trust_remote_code=False,
        ).to(device)
        model.eval()
        _slm_tokenizer, _slm_model = tokenizer, model
        gb = sum(p.numel() * 2 for p in model.parameters()) / 1e9
        logger.info(f"SLM ready — {gb:.1f} GB bf16 on {device}")
        return True
    except Exception as e:
        logger.error(f"SLM load failed: {e!r}")
        return False
    finally:
        _slm_loading = False

def build_system_prompt(step: int, tariff: str, belief: Dict[str, float], top_seg: str) -> str:
    price = TARIFFS.get(tariff, 68.14)
    belief_str = "  ".join(f"{k}:{v*100:.0f}%" for k, v in belief.items())

    step_options = {
        1: "Options: 'Doctor visits' (online) or 'Hospital stays' (advisor).",
        2: "Options: 'Myself' (online) or 'Other persons' (advisor).",
        3: "Options: enter date of birth and social insurance number.",
        4: (f"Options: Start (€{TARIFFS['Start']:.2f}/mo, online), Optimal (€{TARIFFS['Optimal']:.2f}/mo, online), "
            f"Opt.Plus (€{TARIFFS['OptPlus']:.2f}/mo, advisor), Premium (€{TARIFFS['Premium']:.2f}/mo, advisor)."),
        6: "Options: answer health questions (Yes/No).",
        7: "Options: view final price, then proceed to checkout.",
        12: "Options: fill in name, email, payment method, then confirm.",
    }
    opt_text = step_options.get(step, "Options depend on the current step.")

    return (
        "You are the UNIQA Conversion Coach — a helpful AI assistant inside Austria's "
        "online private-doctor health insurance calculator. Help visitors complete a purchase.\n\n"
        "Rules: Reply in 2–3 SHORT sentences. No bullet lists. Never reveal profiling.\n"
        f"Adapt tone: Franz-like=crisp/data, never push advisor. "
        f"Judith-like=warm/reassuring, advisor ok. Peter-like=simple/one-action, offer callback.\n\n"
        f"Online tariffs (only these purchasable online):\n"
        f"  Start  €{TARIFFS['Start']:.2f}/mo — GP, specialists, medications, basic diagnostics\n"
        f"  Optimal €{TARIFFS['Optimal']:.2f}/mo — Start + therapies, medical aids, eye surgery\n"
        f"  Opt.Plus €{TARIFFS['OptPlus']:.2f} / Premium €{TARIFFS['Premium']:.2f} — advisor call required\n\n"
        f"Current: step {step} ({STEP_NAMES.get(step,'?')}) · tariff {tariff} €{price:.2f}/mo\n"
        f"Step options: {opt_text}\n"
        f"Segment belief (do not reveal): {belief_str} → {top_seg}\n\n"
        f"Funnel facts:\n{FUNNEL_DOC[:600]}\n\n"
        f"Product reference:\n{PRODUCT_DOC[:500]}\n\n"
        f"User archetype ({top_seg}):\n{PERSONA_DOCS.get(top_seg, '')[:300]}"
    )

async def generate_slm_reply(messages: List[Dict[str, str]]) -> str:
    if not _slm_model:
        return ""
    try:
        def _sync_generate():
            prompt = _slm_tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
            inputs = _slm_tokenizer(
                prompt, return_tensors="pt", truncation=True,
                max_length=Config.SLM_MAX_PROMPT_LEN
            ).to(_slm_model.device)
            with torch.no_grad():
                outputs = _slm_model.generate(
                    **inputs,
                    max_new_tokens=Config.SLM_MAX_NEW_TOKENS,
                    # Sample (not greedy) + repetition penalty so the coach phrases
                    # each reply differently instead of repeating canned sentences.
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9,
                    repetition_penalty=1.3,
                    no_repeat_ngram_size=3,
                    pad_token_id=(_slm_tokenizer.pad_token_id or _slm_tokenizer.eos_token_id),
                )
            raw = _slm_tokenizer.decode(
                outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True
            )
            for stop in ("<|end|>", "<|user|>", "<|endoftext|>", "</s>"):
                raw = raw.split(stop)[0]
            parts = re.split(r"(?<=[.!?])\s+", raw.strip())
            return " ".join(parts[:3]).strip()
        reply = await asyncio.to_thread(_sync_generate)
        return reply
    except Exception as e:
        logger.error(f"SLM generation failed: {e!r}")
        return ""

# ----------------------------------------------------------------------
# Session state
# ----------------------------------------------------------------------
class SessionState:
    def __init__(self, session_id: str):
        self.id = session_id
        self.step = 4
        self.tariff = "Optimal"
        self.belief = dict(PRIOR)
        self.history: List[Dict[str, str]] = []
        self.back_clicks = 0
        self.competitor_tab = False
        self.recent_replies: List[str] = []
        self.created_at = datetime.utcnow()

_sessions: Dict[str, SessionState] = {}

def get_session(session_id: str) -> SessionState:
    if session_id not in _sessions:
        _sessions[session_id] = SessionState(session_id)
    return _sessions[session_id]

# ----------------------------------------------------------------------
# Pydantic models
# ----------------------------------------------------------------------
class SignalRequest(BaseModel):
    action: str
    step: int = 4
    tariff: Optional[str] = None
    intent: Optional[str] = None
    value: Optional[str] = None

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed = {"next", "back", "tab", "tariff", "trigger"}
        if v not in allowed:
            raise ValueError(f"action must be one of {allowed}")
        return v

class ChatRequest(BaseModel):
    message: str
    step: int = 4
    tariff: str = "Optimal"
    belief: Optional[Dict[str, float]] = None

class ChatResponse(BaseModel):
    reply: str
    intent: Optional[str]
    belief: Dict[str, float]
    top_seg: str
    risk: float
    reasoning: Optional[Dict[str, object]] = None
    source: str = "coach"   # "coach" (rule-based) or "coach+phi3" (phrased by SLM)

class SignalResponse(BaseModel):
    belief: Dict[str, float]
    top_seg: str
    risk: float
    coach_message: str
    intent: Optional[str]
    reasoning: Optional[Dict[str, object]] = None
    source: str = "coach"

class SimulateRequest(BaseModel):
    persona: str = "Franz"
    seed: Optional[int] = None

    @field_validator("persona")
    @classmethod
    def validate_persona(cls, v: str) -> str:
        if v not in engine.PERSONAS:
            raise ValueError(f"persona must be one of {engine.PERSONAS}")
        return v

# ----------------------------------------------------------------------
# FastAPI app
# ----------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    if Config.PRELOAD_SLM:
        logger.info("Preloading SLM during startup...")
        await ensure_slm_loaded()
    yield
    logger.info("Shutting down...")

app = FastAPI(title="UNIQA Conversion Coach", lifespan=lifespan)

def get_session_id(request: Request) -> str:
    session_id = request.cookies.get("coach_session")
    if not session_id:
        session_id = str(uuid.uuid4())
    return session_id

# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def index():
    import json
    # Inject the real engine numbers so the page renders zero hard-coded values.
    html = HTML_TEMPLATE.replace("__UNIQA_CFG__", json.dumps(engine.ui_config()))
    return HTMLResponse(content=html)

@app.post("/signal", response_model=SignalResponse)
async def handle_signal(request: Request, data: SignalRequest):
    session_id = get_session_id(request)
    state = get_session(session_id)

    state.step = data.step
    if data.action == "back":
        state.back_clicks += 1
    elif data.action == "tab":
        state.competitor_tab = True
    elif data.action == "tariff" and data.value:
        state.tariff = data.value
    elif data.action in ("next", "trigger"):
        state.back_clicks = 0
        state.competitor_tab = False

    intent = data.intent
    if data.action in ("back", "tab", "trigger") and not intent:
        if data.action == "tab":
            intent = "comparing"
        elif data.action == "back" and state.back_clicks >= 2:
            intent = "overwhelmed"

    if intent:
        state.belief = update_belief(state.belief, intent)
    top_seg = top_segment(state.belief)
    risk = score_risk(state.step, state.back_clicks, state.competitor_tab, intent)

    coach_msg = ""
    decision = None
    source = "coach"
    if risk > 0.35:
        decision = coach_decision(intent, top_seg)
        coach_msg = doc_reply(intent, state.step, state.tariff, state.belief, top_seg)
        if _slm_model:
            sys_p = build_system_prompt(state.step, state.tariff, state.belief, top_seg)
            user_content = f"[signal:{data.action}] {coach_msg}"
            slm_reply = await generate_slm_reply([
                {"role": "system", "content": sys_p},
                {"role": "user", "content": user_content}
            ])
            if slm_reply:
                coach_msg = slm_reply
                source = "coach+phi3"
        coach_msg = vary_reply(state, coach_msg)

    response = SignalResponse(
        belief=state.belief,
        top_seg=top_seg,
        risk=risk,
        coach_message=coach_msg,
        intent=intent,
        reasoning=decision,
        source=source,
    )
    resp = JSONResponse(content=response.model_dump())
    if not request.cookies.get("coach_session"):
        resp.set_cookie(key="coach_session", value=session_id, httponly=True, max_age=3600*24)
    return resp

@app.post("/chat", response_model=ChatResponse)
async def chat(request: Request, data: ChatRequest):
    session_id = get_session_id(request)
    state = get_session(session_id)

    state.step = data.step
    state.tariff = data.tariff

    intent = detect_intent(data.message)
    belief = safe_belief(data.belief if data.belief is not None else state.belief)
    belief = update_belief(belief, intent)
    state.belief = belief
    top_seg = top_segment(belief)
    risk = score_risk(state.step, state.back_clicks, state.competitor_tab, intent)

    # The COACH decides what to do (detection signal -> segment -> intervention);
    # doc_reply renders it. Phi-3, if present, only rephrases — it never decides.
    decision = coach_decision(intent, top_seg)
    reply = doc_reply(intent, state.step, state.tariff, belief, top_seg, text=data.message)
    source = "coach"

    if _slm_model:
        state.history.append({"role": "user", "content": data.message})
        sys_p = build_system_prompt(state.step, state.tariff, belief, top_seg)
        messages = [{"role": "system", "content": sys_p}] + state.history[-Config.MAX_HISTORY:]
        slm_reply = await generate_slm_reply(messages)
        if slm_reply:
            reply = slm_reply
            source = "coach+phi3"
            state.history.append({"role": "assistant", "content": reply})
        if len(state.history) > Config.MAX_HISTORY * 2:
            state.history = state.history[-Config.MAX_HISTORY * 2:]
    else:
        asyncio.create_task(ensure_slm_loaded())

    reply = vary_reply(state, reply)
    response = ChatResponse(
        reply=reply,
        intent=intent,
        belief=belief,
        top_seg=top_seg,
        risk=risk,
        reasoning=decision,
        source=source,
    )
    resp = JSONResponse(content=response.model_dump())
    if not request.cookies.get("coach_session"):
        resp.set_cookie(key="coach_session", value=session_id, httponly=True, max_age=3600*24)
    return resp

# ----------------------------------------------------------------------
# Evidence endpoints — backed by the REAL leonardo_sim engine
# ----------------------------------------------------------------------
@app.get("/status")
async def status():
    """Engine + model + SLM availability (honest disclosure for the demo)."""
    s = engine.status()
    s["slm"] = {
        "torch_available": _TORCH_AVAILABLE,
        "model_id": Config.MODEL_ID if _TORCH_AVAILABLE else None,
        "loaded": _slm_model is not None,
    }
    return JSONResponse(content=s)

@app.get("/eval")
async def eval_metrics():
    """The committed three-dimension evaluation (artifacts/eval_metrics.json)."""
    m = engine.eval_metrics()
    if m is None:
        return JSONResponse(content={"available": False,
                                     "reason": "eval_metrics.json not found — run evaluate.py"})
    return JSONResponse(content={"available": True, "metrics": m})

@app.post("/simulate")
async def simulate(data: SimulateRequest):
    """Run ONE journey twice on the SAME pre-drawn plan (common random numbers):
    no-coach baseline vs the trained coach. Returns both step-by-step traces and
    the flip — the side-by-side 'which step the intervention saved' showcase."""
    if not engine.AVAILABLE:
        return JSONResponse(status_code=503,
                            content={"available": False, "reason": engine.STATUS})

    def _run():
        if data.seed is None:
            return engine.default_flip(data.persona)
        return engine.run_paired(data.persona, int(data.seed))

    try:
        result = await asyncio.to_thread(_run)
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=500,
                            content={"available": False, "reason": f"{type(e).__name__}: {e}"})
    result["available"] = True
    return JSONResponse(content=result)

# ----------------------------------------------------------------------
# HTML Template (polished UI)
# ----------------------------------------------------------------------
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
<title>UNIQA Health Insurance – AI Coach</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, sans-serif;
    background: linear-gradient(135deg, #f5f7fc 0%, #eef2f8 100%);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
}
.container {
    max-width: 1400px;
    width: 100%;
    background: #fff;
    border-radius: 32px;
    box-shadow: 0 25px 50px -12px rgba(0,0,0,0.25);
    overflow: hidden;
    display: flex;
    flex-wrap: wrap;
}
.calculator {
    flex: 1.2;
    min-width: 380px;
    background: #ffffff;
    border-right: 1px solid #e9edf2;
    display: flex;
    flex-direction: column;
}
.chat {
    flex: 1;
    min-width: 360px;
    background: #fafcff;
    display: flex;
    flex-direction: column;
}
.calc-header {
    background: #002b5c;
    color: white;
    padding: 20px 28px;
    display: flex;
    align-items: center;
    gap: 12px;
}
.calc-header h1 { font-size: 1.5rem; font-weight: 600; letter-spacing: -0.3px; }
.progress-bar { height: 6px; background: #e2e8f0; }
.progress-fill { height: 6px; background: #00b4d8; transition: width 0.3s ease; width: 0%; }
.step-content { flex: 1; padding: 28px; overflow-y: auto; }
.step-num { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; color: #5b6e8c; margin-bottom: 8px; }
.step-title { font-size: 1.75rem; font-weight: 700; color: #0a2540; margin-bottom: 24px; }
.option-card {
    border: 2px solid #e2e8f0;
    border-radius: 20px;
    padding: 18px;
    margin-bottom: 16px;
    cursor: pointer;
    transition: all 0.2s;
}
.option-card:hover { border-color: #00b4d8; background: #f0f9ff; transform: translateY(-2px); }
.option-card.selected { border-color: #002b5c; background: #eef4ff; }
.option-card h3 { font-size: 1.1rem; font-weight: 600; margin-bottom: 6px; }
.option-card p { font-size: 0.85rem; color: #4a5b7a; }
.badge {
    display: inline-block;
    font-size: 0.7rem;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 30px;
    margin-top: 8px;
}
.badge.online { background: #dcfce7; color: #166534; }
.badge.advisory { background: #fef9c3; color: #854d0e; }
.tariff-price { font-size: 1.5rem; font-weight: 700; color: #002b5c; margin-top: 10px; }
input, select {
    width: 100%;
    padding: 12px 16px;
    border: 1.5px solid #cbd5e1;
    border-radius: 16px;
    font-size: 0.9rem;
    margin-top: 6px;
    transition: 0.2s;
}
input:focus, select:focus { border-color: #00b4d8; outline: none; }
label { font-weight: 500; color: #1e2a44; margin-top: 16px; display: block; }
.health-row { display: flex; gap: 12px; margin-top: 12px; }
.health-btn {
    flex: 1;
    padding: 10px;
    border: 2px solid #e2e8f0;
    border-radius: 40px;
    background: white;
    cursor: pointer;
    font-weight: 500;
}
.health-btn.yes { background: #fef2f2; border-color: #ef4444; color: #b91c1c; }
.health-btn.no { background: #f0fdf4; border-color: #22c55e; color: #15803d; }
.final-price-box {
    background: #eef4ff;
    border-radius: 24px;
    padding: 24px;
    text-align: center;
    margin: 20px 0;
}
.final-price-box .amount { font-size: 2.5rem; font-weight: 800; color: #002b5c; }
.price-change {
    background: #fff7ed;
    border-left: 4px solid #f97316;
    padding: 12px 16px;
    border-radius: 16px;
    font-size: 0.85rem;
    margin-bottom: 20px;
}
.calc-footer {
    padding: 20px 28px;
    border-top: 1px solid #e9edf2;
    display: flex;
    flex-direction: column;
    gap: 12px;
}
.btn-primary {
    background: #002b5c;
    color: white;
    border: none;
    border-radius: 40px;
    padding: 14px;
    font-weight: 600;
    font-size: 1rem;
    cursor: pointer;
    transition: 0.2s;
}
.btn-primary:hover { background: #003f7f; }
.sim-btns { display: flex; gap: 12px; }
.sim-btn {
    flex: 1;
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 40px;
    padding: 8px;
    font-size: 0.8rem;
    cursor: pointer;
}
.chat-header {
    background: #00b4d8;
    color: white;
    padding: 20px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.chat-header h2 { font-size: 1.2rem; font-weight: 600; }
.model-badge {
    background: rgba(255,255,255,0.2);
    padding: 4px 12px;
    border-radius: 40px;
    font-size: 0.7rem;
}
.risk-strip {
    background: white;
    padding: 12px 20px;
    border-bottom: 1px solid #e9edf2;
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 0.8rem;
}
.risk-bar { flex: 1; height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden; }
.risk-fill { height: 6px; background: #22c55e; transition: width 0.3s, background 0.3s; }
.profile-bar {
    background: white;
    padding: 12px 20px;
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
    border-bottom: 1px solid #e9edf2;
    font-size: 0.75rem;
}
.seg-pill { display: flex; align-items: center; gap: 6px; }
.seg-track { width: 60px; height: 5px; background: #e2e8f0; border-radius: 3px; }
.seg-fill { height: 5px; border-radius: 3px; }
.seg-f { background: #002b5c; }
.seg-j { background: #00b4d8; }
.seg-p { background: #7c3aed; }
.messages {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}
.msg {
    max-width: 85%;
    padding: 10px 16px;
    border-radius: 20px;
    font-size: 0.9rem;
    line-height: 1.4;
}
.msg.user {
    background: #002b5c;
    color: white;
    align-self: flex-end;
    border-bottom-right-radius: 4px;
}
.msg.coach {
    background: white;
    border: 1px solid #e2e8f0;
    align-self: flex-start;
    border-bottom-left-radius: 4px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
.msg.system {
    background: #fef9c3;
    color: #854d0e;
    align-self: center;
    font-size: 0.8rem;
}
.typing {
    display: none;
    padding: 8px 16px;
    background: white;
    border-radius: 20px;
    align-self: flex-start;
    font-size: 0.8rem;
    color: #5b6e8c;
}
.input-row {
    padding: 16px 20px;
    background: white;
    border-top: 1px solid #e9edf2;
    display: flex;
    gap: 12px;
}
.input-row input {
    flex: 1;
    margin: 0;
    border-radius: 40px;
}
.input-row button {
    background: #00b4d8;
    border: none;
    border-radius: 40px;
    padding: 0 20px;
    font-weight: 600;
    cursor: pointer;
    color: white;
}
@media (max-width: 800px) {
    .container { flex-direction: column; }
    .calculator { border-right: none; border-bottom: 1px solid #e9edf2; }
}
/* ---- top nav / tabs + evidence (second showcase) ---- */
.topnav{max-width:1400px;margin:0 auto 14px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;width:100%}
.tab-btn{background:#fff;border:1.5px solid #cbd5e1;border-radius:40px;padding:9px 18px;font-weight:600;font-size:.9rem;cursor:pointer;color:#0a2540}
.tab-btn.active{background:#002b5c;color:#fff;border-color:#002b5c}
.status-pill{margin-left:auto;font-size:.72rem;display:flex;gap:8px;align-items:center;background:#fff;border:1px solid #e2e8f0;border-radius:40px;padding:6px 14px}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block}
.dot.ok{background:#22c55e}.dot.warn{background:#f59e0b}.dot.off{background:#94a3b8}
.evidence{max-width:1400px;width:100%;margin:0 auto;background:#fff;border-radius:28px;box-shadow:0 25px 50px -12px rgba(0,0,0,.18);padding:26px 30px}
.evidence h2{font-size:1.3rem;color:#0a2540;margin:18px 0 4px}
.evidence .sub{color:#5b6e8c;font-size:.85rem;margin-bottom:16px}
.evidence code{background:#f1f5f9;border-radius:6px;padding:1px 6px;font-size:.85em}
.ev-controls{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:16px}
.persona-btn{border:2px solid #e2e8f0;border-radius:40px;padding:8px 16px;background:#fff;cursor:pointer;font-weight:600;font-size:.85rem}
.persona-btn.active{border-color:#00b4d8;background:#f0f9ff}
.seed-in{width:140px;padding:9px 12px;border:1.5px solid #cbd5e1;border-radius:12px;font-size:.85rem}
.sbs{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.col{border:1px solid #e9edf2;border-radius:18px;overflow:hidden}
.col h3{padding:12px 16px;font-size:.95rem;color:#fff}
.col.base h3{background:#c0392b}.col.coach h3{background:#27ae60}
.srow{padding:10px 14px;border-bottom:1px solid #eef2f7;font-size:.82rem}
.srow .sig{color:#5b6e8c;font-size:.72rem;margin-top:3px}
.srow.left{background:#fff5f5}
.srow .iv{margin-top:7px;background:#ecfdf5;border-left:3px solid #27ae60;border-radius:8px;padding:7px 9px;font-size:.8rem}
.srow .iv .trig{font-family:ui-monospace,monospace;font-size:.66rem;color:#0e7490;display:block;margin-bottom:3px}
.outcome{display:inline-block;font-weight:700;font-size:.72rem;padding:3px 10px;border-radius:30px;text-transform:capitalize}
.outcome.converted{background:#dcfce7;color:#166534}
.outcome.abandoned{background:#fee2e2;color:#991b1b}
.outcome.advisor_routed{background:#fef9c3;color:#854d0e}
.flipline{margin:0 0 18px;padding:12px 16px;border-radius:14px;background:#eef4ff;font-size:.9rem;line-height:1.5}
.evdim{margin-top:24px}
.evdim h3{font-size:1rem;color:#0a2540;margin-bottom:10px}
.barrow{display:flex;align-items:center;gap:10px;margin-bottom:7px;font-size:.78rem}
.barrow .lab{width:160px;flex-shrink:0}
.bar{flex:1;height:18px;background:#eef2f7;border-radius:9px;overflow:hidden}
.bar > span{display:block;height:100%}
.bg-base{background:#c0392b}.bg-coach{background:#27ae60}
.metric-cards{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:8px}
.mcard{flex:1;min-width:150px;background:#f8fafc;border:1px solid #e9edf2;border-radius:16px;padding:14px}
.mcard .v{font-size:1.5rem;font-weight:800;color:#002b5c}
.mcard .k{font-size:.7rem;color:#5b6e8c;text-transform:uppercase;letter-spacing:.5px;margin-top:2px}
@media (max-width:800px){.sbs{grid-template-columns:1fr}}

/* ====================================================================== */
/*  Cohesive redesign layer (v2) — design tokens + restyle                */
/* ====================================================================== */
:root{
  --navy:#0a2540; --navy2:#002b5c; --cyan:#00b4d8; --cyan-d:#0093b4;
  --ink:#0f2138; --muted:#64748b; --line:#e6ebf2; --bg:#eef2f8;
  --ok:#16a34a; --warn:#f59e0b; --bad:#dc2626;
  --r-lg:22px; --r-md:16px; --r-sm:11px;
  --shadow:0 10px 30px -12px rgba(13,38,76,.22);
  --shadow-lg:0 24px 60px -20px rgba(13,38,76,.30);
}
body{
  background:radial-gradient(1200px 600px at 10% -10%, #eaf6fb 0%, transparent 60%),
             radial-gradient(1000px 500px at 110% 0%, #eef1fb 0%, transparent 55%),
             linear-gradient(180deg,#f3f6fb 0%, #e9eef6 100%);
  display:block; padding:18px 18px 8px; color:var(--ink);
}
/* --- app bar --- */
.appbar{max-width:1400px;margin:0 auto 16px;background:#fff;border:1px solid var(--line);
  border-radius:var(--r-lg);box-shadow:var(--shadow);padding:14px 20px;display:flex;
  align-items:center;gap:18px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:13px;min-width:0}
.brand-mark{width:42px;height:42px;border-radius:13px;flex:none;display:grid;place-items:center;
  background:linear-gradient(135deg,var(--navy2),var(--cyan));color:#fff;font-weight:800;font-size:1.3rem;
  box-shadow:0 6px 16px -6px rgba(0,148,180,.6)}
.brand-title{font-weight:800;font-size:1.12rem;color:var(--navy);letter-spacing:-.2px;line-height:1.1}
.brand-sub{font-size:.74rem;color:var(--muted);margin-top:2px}
.tabs{display:flex;gap:8px;margin-left:8px}
.tab-btn{background:#f1f5fb;border:1.5px solid transparent;border-radius:40px;padding:9px 18px;
  font-weight:600;font-size:.88rem;cursor:pointer;color:var(--navy);transition:.18s}
.tab-btn:hover{background:#e7eefb}
.tab-btn.active{background:var(--navy2);color:#fff;box-shadow:0 8px 18px -8px rgba(0,43,92,.6)}
.status-pill{margin-left:auto;font-size:.72rem;color:var(--muted);display:flex;gap:9px;align-items:center;
  background:#f7f9fc;border:1px solid var(--line);border-radius:40px;padding:7px 14px}
.dot{width:9px;height:9px;border-radius:50%}
.dot.ok{background:var(--ok);box-shadow:0 0 0 3px rgba(22,163,74,.15)}
.dot.warn{background:var(--warn);box-shadow:0 0 0 3px rgba(245,158,11,.15)}
.dot.off{background:#94a3b8}
/* --- shells --- */
.container{max-width:1400px;margin:0 auto 14px;border-radius:var(--r-lg);box-shadow:var(--shadow-lg);
  border:1px solid var(--line)}
.calculator{border-right:1px solid var(--line)}
.calc-header{background:linear-gradient(120deg,var(--navy) 0%,var(--navy2) 60%,#063e7e 100%)}
.calc-header h1{font-weight:800;letter-spacing:-.4px}
.progress-fill{background:linear-gradient(90deg,var(--cyan),#3ddc97)}
.step-title{letter-spacing:-.5px}
.option-card{border-radius:var(--r-md);border:2px solid var(--line);transition:.18s}
.option-card:hover{border-color:var(--cyan);background:#f3fbfe;box-shadow:0 10px 24px -16px rgba(0,148,180,.7)}
.option-card.selected{border-color:var(--navy2);background:#eef4ff}
.badge.online{background:#dcfce7;color:#15803d}
.badge.advisory{background:#fef3c7;color:#92400e}
.btn-primary{background:linear-gradient(120deg,var(--navy2),#0e4f93);border-radius:40px;
  box-shadow:0 12px 24px -12px rgba(0,43,92,.7);letter-spacing:.2px}
.btn-primary:hover{filter:brightness(1.08)}
.sim-btn{border-radius:40px;transition:.15s}
.sim-btn:hover{border-color:var(--cyan);color:var(--cyan-d);background:#f3fbfe}
/* --- chat / coach --- */
.chat{background:linear-gradient(180deg,#fbfdff,#f5f8fd)}
.chat-header{background:linear-gradient(120deg,var(--cyan),var(--cyan-d));align-items:flex-start}
.chat-header h2{font-weight:700;font-size:1.12rem}
.chat-sub{font-size:.68rem;color:rgba(255,255,255,.9);margin-top:3px;font-weight:500}
.model-badge{background:rgba(255,255,255,.22);font-weight:700;align-self:center}
.risk-strip{gap:10px}
.risk-lab{font-weight:600;color:var(--muted);white-space:nowrap}
.risk-bar{height:8px;border-radius:5px;background:#e8edf4}
.risk-fill{height:8px;border-radius:5px;transition:width .4s ease,background .4s}
.risk-pct{font-weight:800;color:var(--navy);min-width:34px;text-align:right}
.profile-bar{gap:16px;align-items:center}
.seg-pill{font-weight:600;color:#41506a}
.seg-track{width:64px;height:6px;border-radius:4px}
.seg-fill{height:6px;border-radius:4px;transition:width .4s}
.messages{gap:14px;padding:18px 18px 8px}
.msg{max-width:88%;border-radius:16px;font-size:.9rem;line-height:1.45;box-shadow:0 2px 6px -3px rgba(13,38,76,.15)}
.msg.user{background:linear-gradient(120deg,var(--navy2),#0e4f93);border-bottom-right-radius:5px}
.msg.coach{background:#fff;border:1px solid var(--line);border-bottom-left-radius:5px}
.msg.system{background:#fff7d6;color:#7c5e10;border:1px solid #fde68a;border-radius:14px;font-weight:600}
/* visible coach reasoning chip */
.reason-chip{margin-top:9px;padding:7px 9px;background:#f3f8ff;border:1px solid #e2ecfb;border-radius:10px;
  font-size:.68rem;color:#43597c;display:flex;flex-wrap:wrap;align-items:center;gap:5px;line-height:1.5}
.reason-chip.muted{color:#8aa;background:#f8fafc;border-color:#eef2f7}
.reason-chip .rlab{text-transform:uppercase;letter-spacing:.4px;font-size:.6rem;color:#90a0b8;font-weight:700}
.reason-chip .rval{font-weight:600;color:#33465f}
.reason-chip .rarr{color:#b6c2d4;font-weight:700}
.reason-chip .rint{color:#0e7490;background:#e0f5fb;padding:1px 7px;border-radius:20px;font-size:.7rem}
.reason-chip .rbest{color:#15803d;background:#dcfce7;padding:1px 7px;border-radius:20px;font-weight:700}
.reason-chip .rphi{color:#7c3aed;background:#f3e8ff;padding:1px 7px;border-radius:20px}
.input-row input{border:1.5px solid var(--line)}
.input-row input:focus{border-color:var(--cyan)}
.input-row button{background:linear-gradient(120deg,var(--cyan),var(--cyan-d));font-weight:700}
/* --- evidence cohesion --- */
.evidence{border:1px solid var(--line);box-shadow:var(--shadow-lg);border-radius:var(--r-lg)}
.col{border-radius:var(--r-md)}
.mcard{border-radius:14px}
.mcard .v{color:var(--navy)}
/* --- footer --- */
.appfoot{max-width:1400px;margin:6px auto 10px;padding:12px 20px;display:flex;flex-wrap:wrap;gap:10px;
  align-items:center;justify-content:center;font-size:.78rem;color:var(--muted)}
.appfoot b{color:var(--navy)}
.appfoot .dotsep{color:#cbd5e1}
@media (max-width:820px){.appbar{gap:10px}.brand-sub{display:none}.status-pill{margin-left:0}}
</style>
</head>
<body>
<header class="appbar">
    <div class="brand">
        <div class="brand-mark">U</div>
        <div class="brand-text">
            <div class="brand-title">UNIQA Conversion Coach</div>
            <div class="brand-sub">detects abandonment → fires a per-segment intervention → more online conversions</div>
        </div>
    </div>
    <nav class="tabs">
        <button class="tab-btn active" id="tabLive" onclick="showView('live')">▶ Live coach</button>
        <button class="tab-btn" id="tabEvidence" onclick="showView('evidence')">📊 Evidence &amp; results</button>
    </nav>
    <div class="status-pill" id="statusPill"><span class="dot off"></span><span>checking engine…</span></div>
</header>
<div id="liveView">
<div class="container">
    <div class="calculator">
        <div class="calc-header"><h1>🏥 UNIQA Health</h1></div>
        <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
        <div class="step-content">
            <div class="step-num" id="stepNum">Step 1 of 7</div>
            <div class="step-title" id="stepTitle">Where do you want coverage?</div>
            <div id="stepBody"></div>
        </div>
        <div class="calc-footer">
            <button class="btn-primary" id="continueBtn">Continue →</button>
            <div class="sim-btns">
                <button class="sim-btn" id="backSimBtn">← Back click</button>
                <button class="sim-btn" id="tabSimBtn">⎋ Competitor tab</button>
            </div>
        </div>
    </div>
    <div class="chat">
        <div class="chat-header">
            <div>
                <h2>💬 AI Conversion Coach</h2>
                <div class="chat-sub">rule-based detection + decision · Phi-3 only phrases it</div>
            </div>
            <div class="model-badge" id="modelBadge">coach engine</div>
        </div>
        <div class="risk-strip">
            <span class="risk-lab">Abandonment risk</span>
            <div class="risk-bar"><div class="risk-fill" id="riskFill"></div></div>
            <span id="riskPct" class="risk-pct">5%</span>
        </div>
        <div class="profile-bar" id="profileBar">
            <!-- dynamic personas -->
        </div>
        <div class="messages" id="messages"></div>
        <div class="typing" id="typingIndicator">Coach is thinking…</div>
        <div class="input-row">
            <input type="text" id="chatInput" placeholder="Ask about options, price, or what to do…" onkeydown="if(event.key==='Enter') sendMessage()">
            <button id="sendBtn">Ask</button>
        </div>
    </div>
</div>
</div><!-- /liveView -->

<div id="evidenceView" style="display:none">
  <div class="evidence">
    <div id="evStatus" class="flipline" style="background:#f1f5f9">Loading engine status…</div>

    <h2>Side-by-side · which step the coach saved</h2>
    <div class="sub">Same persona, the <b>same pre-drawn journey</b> (common random numbers) resolved twice — no coach vs the trained coach. This is the real <code>leonardo_sim</code> calibrated funnel + classifier brain, not a scripted mock.</div>
    <div class="ev-controls">
      <span style="font-weight:600">Segment:</span>
      <button class="persona-btn active" data-p="Franz" onclick="pickPersona('Franz')">Franz · final-price</button>
      <button class="persona-btn" data-p="Judith" onclick="pickPersona('Judith')">Judith · initial-price</button>
      <button class="persona-btn" data-p="Peter" onclick="pickPersona('Peter')">Peter · early overwhelm</button>
      <input class="seed-in" id="seedInput" type="number" placeholder="seed (blank = winning)">
      <button class="btn-primary" style="padding:9px 18px" onclick="runSim()">Run side-by-side</button>
    </div>
    <div id="flipSummary"></div>
    <div class="sbs">
      <div class="col base"><h3>① Baseline — no coach</h3><div id="baseSteps"></div></div>
      <div class="col coach"><h3>② With coach</h3><div id="coachSteps"></div></div>
    </div>

    <div class="evdim">
      <h2>Headline evaluation · the three judged dimensions</h2>
      <div class="sub">Held-out cohort (seed disjoint from training), identical journeys baseline vs coach — straight from <code>artifacts/eval_metrics.json</code>.</div>
      <div id="evalBody">Loading evaluation…</div>
    </div>
  </div>
</div>
<footer class="appfoot">
    <span><b>~5.6%</b> baseline → <b id="footConv">~17%</b> with coach</span>
    <span class="dotsep">•</span>
    <span>traffic mix <b>50/30/20</b> (Franz/Judith/Peter)</span>
    <span class="dotsep">•</span>
    <span>identical seeds · not an LLM wrapper</span>
    <span class="dotsep">•</span>
    <span>MIT · Zero One Hack_01</span>
</footer>
<script>
// Real engine numbers injected server-side (engine.ui_config) — no hard-coding.
const CFG = __UNIQA_CFG__;
const STEPS = [
    { id:1,  title:"Where do you want coverage?", body: () => `<div class="option-card" onclick="selectOption('coverage','doctor_visits',event)"><h3>🩺 Doctor visits</h3><p>Private GP, specialists, diagnostics, telemedicine</p><span class="badge online">✓ Purchasable online</span></div><div class="option-card" onclick="selectOption('coverage','hospital',event)"><h3>🏥 Hospital stays</h3><p>Private room, elective surgery scheduling</p><span class="badge advisory">Advisory required</span></div>` },
    { id:2,  title:"Who should be insured?", body: () => `<div class="option-card" onclick="selectOption('who','myself',event)"><h3>👤 Myself</h3><p>Complete online right now</p><span class="badge online">✓ Online path</span></div><div class="option-card" onclick="selectOption('who','other',event)"><h3>👨‍👩‍👧 Other persons</h3><p>Partner, children – advisor needed</p><span class="badge advisory">Advisory required</span></div>` },
    { id:3,  title:"Your personal details", body: () => `<p style="margin-bottom:16px">We need these two fields to calculate your provisional premium. Nothing is charged yet.</p><label>Date of birth</label><input type="date" id="dob"><label>Social insurance number</label><input type="text" id="svnr" placeholder="e.g. 1234 010180">` },
    { id:4,  title:"Choose your tariff", body: () => `<p>⚠ ${(CFG.critical['4']*100).toFixed(0)}% of users drop off here. Coach can help.</p><div class="option-card" onclick="selectTariff('Start',event)"><h3>Start</h3><p>GP, specialists, medications, basic diagnostics</p><div class="tariff-price">€${CFG.tariffs.Start.toFixed(2)}<span style="font-size:0.9rem">/mo</span></div><span class="badge online">✓ Buy online</span></div><div class="option-card" onclick="selectTariff('Optimal',event)"><h3>Optimal <span style="font-size:0.8rem">most popular</span></h3><p>+ therapies, medical aids, eye surgery</p><div class="tariff-price">€${CFG.tariffs.Optimal.toFixed(2)}<span style="font-size:0.9rem">/mo</span></div><span class="badge online">✓ Buy online</span></div><div class="option-card" onclick="selectTariff('OptPlus',event)"><h3>Optimal Plus</h3><p>Broader cover, advisor required</p><div class="tariff-price">€${CFG.tariffs.OptPlus.toFixed(2)}<span style="font-size:0.9rem">/mo</span></div><span class="badge advisory">Advisory required</span></div><div class="option-card" onclick="selectTariff('Premium',event)"><h3>Premium</h3><p>Comprehensive cover, advisor required</p><div class="tariff-price">€${CFG.tariffs.Premium.toFixed(2)}<span style="font-size:0.9rem">/mo</span></div><span class="badge advisory">Advisory required</span></div>` },
    { id:6,  title:"Health questions", body: () => `<p>Your answers are confidential and affect the final price.</p><label>Chronic conditions?</label><div class="health-row"><button class="health-btn" onclick="healthAnswer(1,'yes')">Yes</button><button class="health-btn" onclick="healthAnswer(1,'no')">No</button></div><label>Prescription medication?</label><div class="health-row"><button class="health-btn" onclick="healthAnswer(2,'yes')">Yes</button><button class="health-btn" onclick="healthAnswer(2,'no')">No</button></div><label>Surgery in last 5 years?</label><div class="health-row"><button class="health-btn" onclick="healthAnswer(3,'yes')">Yes</button><button class="health-btn" onclick="healthAnswer(3,'no')">No</button></div>` },
    { id:7,  title:"Your final price", body: () => { const base = tariffPrices[state.tariff]||CFG.tariffs.Optimal; const sc = CFG.surcharge; const final = (base*(1+sc)).toFixed(2); return `<div class="price-change">⚠ Your final price is slightly higher than the initial estimate – standard for all insurers.</div><div class="final-price-box"><div>Final monthly premium</div><div class="amount">€${final}</div><div class="note">${state.tariff} tariff · personalised</div></div><p>Initial estimate: €${base.toFixed(2)}/mo · +${(sc*100).toFixed(1)}% typical risk surcharge</p>`; } },
    { id:12, title:"Almost done!", body: () => `<p>Review and confirm. Nothing is charged until you click Confirm.</p><label>Full name</label><input type="text" placeholder="Max Mustermann"><label>Email</label><input type="text" placeholder="you@example.com"><label>Start date</label><input type="date"><label>Payment method</label><select><option>SEPA Direct Debit</option><option>Credit card</option></select><div style="margin-top:16px;background:#eef4ff;border-radius:16px;padding:12px;">✓ Your policy will be active immediately after confirmation.</div>` }
];
const tariffPrices = CFG.tariffs;
let state = { stepIdx:0, tariff:'Optimal', selections:{}, belief: Object.assign({}, CFG.prior) };
let risk = 0.05;

function renderStep() {
    const step = STEPS[state.stepIdx];
    document.getElementById('stepNum').innerText = `Step ${state.stepIdx+1} of ${STEPS.length}`;
    document.getElementById('stepTitle').innerText = step.title;
    document.getElementById('stepBody').innerHTML = step.body();
    const progress = ((state.stepIdx+1)/STEPS.length)*100;
    document.getElementById('progressFill').style.width = progress+'%';
    document.getElementById('continueBtn').innerText = state.stepIdx === STEPS.length-1 ? '✓ Confirm purchase' : 'Continue →';
    if (step.id === 4) triggerCoach('step_explain', 'You reached the tariff selection – the most important step.');
    if (step.id === 7) triggerCoach('price_jump', 'Final price shown – coach intervenes on this drop-off.');
}
function selectOption(key, val, ev) {
    state.selections[key] = val;
    document.querySelectorAll('.option-card').forEach(c=>c.classList.remove('selected'));
    ev.currentTarget.classList.add('selected');
    if (val==='hospital'||val==='other') addMessage('coach', `That path requires a short advisor call – I'll help route you.`, 'out-of-scope');
}
function selectTariff(t, ev) {
    state.tariff = t;
    document.querySelectorAll('.option-card').forEach(c=>c.classList.remove('selected'));
    ev.currentTarget.classList.add('selected');
    fetch('/signal', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'tariff', value:t, step:STEPS[state.stepIdx].id})});
    if (t==='OptPlus'||t==='Premium') addMessage('coach', `${t==='OptPlus'?'Optimal Plus':'Premium'} needs an advisor call by regulation. Optimal (€${CFG.tariffs.Optimal.toFixed(2)}/mo) covers most and is fully online.`, 'advisory_tariff');
}
function healthAnswer(q, ans) { /* visual feedback only */ }
function nextStep() {
    if (state.stepIdx >= STEPS.length-1) {
        addMessage('system', '🎉 Purchase confirmed! Your UNIQA policy is now active.');
        document.getElementById('continueBtn').disabled = true;
        return;
    }
    fetch('/signal', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'next', step:STEPS[state.stepIdx].id})});
    state.stepIdx++;
    renderStep();
}
function simBack() { fetch('/signal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'back', step:STEPS[state.stepIdx].id})}).then(r=>r.json()).then(updateUI); }
function simTab() { fetch('/signal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'tab', step:STEPS[state.stepIdx].id})}).then(r=>r.json()).then(updateUI); }
function updateUI(d) {
    if (!d) return;
    if (d.belief) {
        state.belief = d.belief;
        const barDiv = document.getElementById('profileBar');
        barDiv.innerHTML = ['Franz','Judith','Peter'].map(p => {
            const pct = Math.round(d.belief[p]*100);
            const key = p[0].toLowerCase();
            return `<div class="seg-pill"><span>${p}</span><div class="seg-track"><div class="seg-fill seg-${key}" style="width:${pct}%"></div></div><span>${pct}%</span></div>`;
        }).join('') + `<span style="margin-left:auto; font-weight:600;">${d.top_seg || ''}</span>`;
    }
    if (d.risk !== undefined) {
        risk = d.risk;
        const r = Math.round(risk*100);
        document.getElementById('riskFill').style.width = r+'%';
        document.getElementById('riskFill').style.background = r>65?'#ef4444':r>35?'#f97316':'#22c55e';
        document.getElementById('riskPct').innerText = r+'%';
    }
    if (d.coach_message) {
        if (d.reasoning) d.reasoning.source = d.source;
        addMessage('coach', d.coach_message, d.reasoning || d.intent || '');
    }
}
function triggerCoach(intent, reason) {
    fetch('/signal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'trigger', step:STEPS[state.stepIdx].id, intent, tariff:state.tariff})}).then(r=>r.json()).then(updateUI);
}
function addMessage(role, text, reasoning='') {
    const msgs = document.getElementById('messages');
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    const body = document.createElement('div');
    body.textContent = text;
    div.appendChild(body);
    if (reasoning && role === 'coach') {
        if (typeof reasoning === 'object') div.appendChild(renderReasoning(reasoning));
        else { const t = document.createElement('div'); t.className = 'reason-chip muted'; t.textContent = reasoning; div.appendChild(t); }
    }
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
}
// Visible coach reasoning: detected signal → inferred segment → chosen intervention.
function renderReasoning(r) {
    const chip = document.createElement('div');
    chip.className = 'reason-chip';
    const best = r.documented_best ? `<span class="rbest">★ best for ${r.segment}</span>` : '';
    const phi = r.source === 'coach+phi3' ? `<span class="rphi">Phi-3 phrasing</span>` : '';
    chip.innerHTML =
        `<span class="rlab">signal</span><span class="rval">${r.signal}</span>` +
        `<span class="rarr">→</span><span class="rlab">segment</span><span class="rval">${r.segment}</span>` +
        `<span class="rarr">→</span><span class="rlab">intervention</span><b class="rint">${r.intervention}</b>` +
        best + phi;
    return chip;
}
async function sendMessage() {
    const inp = document.getElementById('chatInput');
    const msg = inp.value.trim();
    if (!msg) return;
    inp.value = '';
    addMessage('user', msg);
    document.getElementById('typingIndicator').style.display = 'flex';
    const resp = await fetch('/chat', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message: msg, step: STEPS[state.stepIdx].id, tariff: state.tariff, belief: state.belief})});
    const d = await resp.json();
    document.getElementById('typingIndicator').style.display = 'none';
    if (d.reasoning) d.reasoning.source = d.source;
    addMessage('coach', d.reply, d.reasoning || d.intent || '');
    updateUI(d);
}
document.getElementById('continueBtn').onclick = nextStep;
document.getElementById('backSimBtn').onclick = simBack;
document.getElementById('tabSimBtn').onclick = simTab;
document.getElementById('sendBtn').onclick = sendMessage;
renderStep();
addMessage('coach', "Hi! I'm your conversion coach. Pick a coverage type to begin, or ask me anything — try “what’s the difference between hospital and doctor visits?” or “which plan should I pick?”", {signal:'open_message', segment:'—', intervention:'welcome', documented_best:false});

// ====================================================================
// Evidence showcase — driven by the real leonardo_sim engine
// ====================================================================
let selectedPersona = 'Franz';
let evidenceLoaded = false;

function showView(v){
    const live = v === 'live';
    document.getElementById('liveView').style.display = live ? 'block' : 'none';
    document.getElementById('evidenceView').style.display = live ? 'none' : 'block';
    document.getElementById('tabLive').classList.toggle('active', live);
    document.getElementById('tabEvidence').classList.toggle('active', !live);
    if (!live && !evidenceLoaded){ evidenceLoaded = true; loadEval(); runSim(); }
}

function renderStatus(s){
    const slm = s.slm || {};
    const engDot = s.available ? 'ok' : 'off';
    const slmDot = slm.loaded ? 'ok' : (slm.torch_available ? 'warn' : 'off');
    document.getElementById('statusPill').innerHTML =
        `<span class="dot ${engDot}"></span><span>engine ${s.available ? 'live' : 'standalone'}</span>` +
        `<span class="dot ${slmDot}"></span><span>Phi-3 ${slm.loaded ? 'on' : (slm.torch_available ? 'warming' : 'off')}</span>`;
    const mb = document.getElementById('modelBadge');
    if (mb) mb.textContent = slm.loaded ? 'coach + Phi-3' : 'coach engine';
    const fc = document.getElementById('footConv');
    const evs = document.getElementById('evStatus');
    if (evs){
        evs.innerHTML = s.available
            ? `✓ Real engine loaded from <code>${s.sim_dir}</code><br>${s.model_status} · personas ${s.personas.join(' / ')} · traffic mix ` +
              Object.entries(s.persona_mix).map(([k,v]) => `${k} ${Math.round(v*100)}%`).join(' / ') + '.'
            : `⚠ Engine not loaded (${s.status}). Showing spec constants only — set $LEONARDO_SIM to wire the real implementation.`;
    }
}
async function loadStatus(){
    try { renderStatus(await (await fetch('/status')).json()); }
    catch(e){ document.getElementById('statusPill').innerHTML = '<span class="dot off"></span><span>status error</span>'; }
}

function pickPersona(p){
    selectedPersona = p;
    document.querySelectorAll('.persona-btn').forEach(b => b.classList.toggle('active', b.dataset.p === p));
    document.getElementById('seedInput').value = '';
    runSim();
}

async function runSim(){
    const seedRaw = document.getElementById('seedInput').value.trim();
    const body = { persona: selectedPersona };
    if (seedRaw !== '') body.seed = parseInt(seedRaw, 10);
    document.getElementById('flipSummary').innerHTML = '<div class="flipline">Running the paired simulation…</div>';
    document.getElementById('baseSteps').innerHTML = '';
    document.getElementById('coachSteps').innerHTML = '';
    try {
        const d = await (await fetch('/simulate', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)})).json();
        if (!d.available){ document.getElementById('flipSummary').innerHTML = `<div class="flipline">Engine unavailable: ${d.reason}</div>`; return; }
        renderSim(d);
    } catch(e){
        document.getElementById('flipSummary').innerHTML = `<div class="flipline">Request failed: ${e}</div>`;
    }
}

function renderSim(d){
    const f = d.flip;
    const brain = d.model ? 'trained classifier' : 'heuristic risk';
    let verb;
    if (f.flipped) verb = `turned a baseline <b>${f.baseline_outcome.replace('_',' ')}</b> (left at step ${f.baseline_left_step}) into a <b>CONVERSION</b>`;
    else verb = `baseline <b>${f.baseline_outcome.replace('_',' ')}</b> → coach <b>${f.coach_outcome.replace('_',' ')}</b>`;
    document.getElementById('flipSummary').innerHTML =
        `<div class="flipline"><b>${d.persona}</b> · seed ${d.seed} · ${brain} — the coach ${verb}. ` +
        `Interventions fired at step(s) ${f.intervened_steps.join(', ') || '—'}.</div>`;
    document.getElementById('baseSteps').innerHTML = renderCol(d.baseline);
    document.getElementById('coachSteps').innerHTML = renderCol(d.coach);
}

function renderCol(res){
    let h = `<div style="padding:9px 14px;border-bottom:1px solid #eef2f7">` +
            `<span class="outcome ${res.outcome}">${res.outcome.replace('_',' ')}</span> · reached step ${res.final_step}</div>`;
    for (const st of res.steps){
        h += `<div class="srow${st.left_here ? ' left' : ''}">`;
        h += `<b>Step ${st.step}</b> ${st.step_name}`;
        if (st.final_price) h += ` · final €${st.final_price}`;
        else if (st.provisional_price) h += ` · €${st.provisional_price}`;
        h += `<div class="sig">dwell ${st.dwell_s}s · hesitation ${st.hesitation} · back ${st.back_clicks} · competitor-tab ${st.competitor_tab}` +
             `${st.advisory_click ? ' · ⚠ advisory-tariff click' : ''}${st.price_delta_pct ? ' · price +' + Math.round(st.price_delta_pct*100) + '%' : ''}</div>`;
        if (st.left_here) h += `<div class="sig" style="color:#b91c1c;font-weight:700">✦ left here (${st.routed ? 'advisor route' : 'abandoned'}${st.forced_oos ? ', out-of-scope' : ''})</div>`;
        if (st.intervention){
            const iv = st.intervention;
            h += `<div class="iv"><span class="trig">▸ ${iv.trigger || 'coach fired'} · ${iv.category}/${iv.name}</span>${iv.message}</div>`;
        }
        h += `</div>`;
    }
    return h;
}

const pct = x => (x*100).toFixed(1) + '%';
const bar = (val, max, cls) => `<div class="bar"><span class="${cls}" style="width:${Math.min(100, val/max*100)}%"></span></div>`;

async function loadEval(){
    try {
        const d = await (await fetch('/eval')).json();
        if (!d.available){ document.getElementById('evalBody').innerHTML = `<div class="sub">Evaluation not available: ${d.reason}</div>`; return; }
        renderEval(d.metrics);
    } catch(e){ document.getElementById('evalBody').innerHTML = `<div class="sub">Could not load evaluation: ${e}</div>`; }
}

function renderEval(m){
    const d1 = m.dimension1_conversion, d2 = m.dimension2_per_persona, d3 = m.dimension3_intervention_quality;
    let h = `<div class="metric-cards">` +
        `<div class="mcard"><div class="v">${pct(d1.baseline)} → ${pct(d1.coach)}</div><div class="k">overall conversion · 50/30/20</div></div>` +
        `<div class="mcard"><div class="v">×${d1.multiplier.toFixed(2)}</div><div class="k">uplift · +${(d1.uplift_pts*100).toFixed(1)} pts</div></div>` +
        `<div class="mcard"><div class="v">${pct(d3.precision)}</div><div class="k">trigger precision</div></div>` +
        `<div class="mcard"><div class="v">${pct(d3.recall)}</div><div class="k">trigger recall</div></div>` +
        `<div class="mcard"><div class="v">${pct(d3.annoyance_rate)}</div><div class="k">annoyance rate</div></div>` +
        `</div>`;

    h += `<div class="evdim"><h3>Dimension 1 — drop-off cut at the two price cliffs</h3>`;
    [4,7].forEach(s => {
        const b = d1.dropoff_baseline[s], c = d1.dropoff_coach[s];
        h += `<div class="barrow"><div class="lab">step ${s} · no coach</div>${bar(b,1,'bg-base')}<span>${pct(b)}</span></div>`;
        h += `<div class="barrow"><div class="lab">step ${s} · coach</div>${bar(c,1,'bg-coach')}<span>${pct(c)}</span></div>`;
    });
    h += `<div class="sub">Real UNIQA targets the baseline reproduces: step 4 ≈ 66%, step 7 ≈ 78%.</div></div>`;

    h += `<div class="evdim"><h3>Dimension 2 — lifts all three segments</h3>`;
    Object.keys(d2).forEach(p => {
        const b = d2[p].baseline, c = d2[p].coach;
        h += `<div class="barrow"><div class="lab">${p} · no coach</div>${bar(b,0.25,'bg-base')}<span>${pct(b)}</span></div>`;
        h += `<div class="barrow"><div class="lab">${p} · coach</div>${bar(c,0.25,'bg-coach')}<span>${pct(c)} (×${(c/b).toFixed(1)})</span></div>`;
    });
    h += `</div>`;

    const mix = d3.mix, tot = Object.values(mix).reduce((a,b)=>a+b,0);
    h += `<div class="evdim"><h3>Dimension 3 — intervention mix · ${d3.fired.toLocaleString()} coaching fires</h3>`;
    Object.entries(mix).sort((a,b)=>b[1]-a[1]).forEach(([k,v]) => {
        h += `<div class="barrow"><div class="lab">${k}</div>${bar(v,tot,'bg-coach')}<span>${v} (${Math.round(v/tot*100)}%)</span></div>`;
    });
    h += `</div>`;
    document.getElementById('evalBody').innerHTML = h;
}

loadStatus();
</script>
</body>
</html>
"""

# ----------------------------------------------------------------------
# Run
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting UNIQA Conversion Coach on {Config.HOST}:{Config.PORT}")
    uvicorn.run(app, host=Config.HOST, port=Config.PORT)