# UNIQA Conversion Coach — Demo

One FastAPI app with **two showcases** over the real `leonardo_sim` engine:

1. **▶ Live coach** — the 7-step UNIQA private-doctor funnel with the coach
   reacting to behavioural signals (back-clicks, competitor tab, critical steps)
   and an optional Phi-3 chat.
2. **📊 Evidence** — the *real engine*, not a mock:
   - **Side-by-side**: one persona, the **same pre-drawn journey** resolved with
     no coach vs the trained coach (common random numbers) — shows exactly which
     step the intervention flipped, with the coach's trigger reason visible.
   - **Headline evaluation**: the three judged dimensions straight from
     `artifacts/eval_metrics.json` (conversion uplift + drop-off reduction,
     per-persona breakdown, intervention precision/recall/annoyance).

The demo no longer hard-codes the spec numbers: prices, the 50/30/20 traffic mix
and the 66%/78% cliffs all come from `leonardo_sim` (→ `personas.js`), so the
slides can't drift from the engine being judged.

## Run

```bash
# pip route (light — no GPU/torch needed; runs the engine + full evaluation)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py                       # open http://localhost:9696

# or pixi
pixi run start                      # core (doc-grounded chat + full evidence)
pixi run -e slm start               # + Phi-3 conversational coach (heavy)
```

## Connecting to the engine

The app auto-finds `leonardo_sim`. If it lives somewhere non-default, point at it:

```bash
LEONARDO_SIM=/path/to/leonardo_sim python app.py
```

Resolution order: `$LEONARDO_SIM` → `../leonardo_sim` →
`../ZeroOneHack42/leonardo_sim`. Open the **Evidence** tab — the status pill and
banner show where the engine loaded from and whether the trained model is in use.
If the engine can't be imported, the app still runs standalone on spec-accurate
constants (clearly flagged in the UI).

## Optional: Phi-3 chat

```bash
pip install "torch>=2.4" "transformers>=4.46"
HF_HOME=/leonardo/pub/usertrain/a08trc0t/hf_cache PRELOAD_SLM=1 python app.py
# override model (same MIT license):
CHAT_MODEL=microsoft/Phi-3.5-mini-instruct python app.py
```

Without torch the chat falls back to instant doc-grounded replies; everything
else (funnel, signals, side-by-side, evaluation) is unaffected.

## Endpoints

| Route | Purpose |
|---|---|
| `GET /` | the two-showcase UI |
| `GET /status` | engine / trained-model / SLM availability |
| `POST /simulate` | `{persona, seed?}` → paired baseline-vs-coach trace + the flip |
| `GET /eval` | the three-dimension `eval_metrics.json` |
| `POST /chat`, `POST /signal` | live coach panel |

## Files

```
demo/
├── app.py            ← FastAPI + HTML + live coach + evidence endpoints
├── engine.py         ← bridge to leonardo_sim (constants, paired sim, eval, docs)
├── requirements.txt  ← pip deps (torch optional)
├── pixi.toml         ← conda deps (slm feature optional)
└── README.md
```
