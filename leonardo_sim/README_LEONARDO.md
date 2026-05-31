# UNIQA Persona Simulation on Leonardo — Run Guide

Generate LLM-driven persona journeys (Franz / Judith / Peter) through the UNIQA
health-insurance funnel and produce a merged CSV to train the Conversion Coach's
abandonment classifier (XGBoost). Uses a **free Mistral instruct model** served with
**vLLM** on a single A100.

```
leonardo_sim/
├── persona_simulator.py   # main: LLM persona journeys -> data_<persona>.csv
├── download_model.py      # pre-cache the model on the login node (compute = offline)
├── run_simulation.sbatch  # SLURM launcher for the boost_usr_prod (A100) partition
├── merge_datasets.py      # Step 3: merge every data_*.csv -> master_training_dataset.csv
├── requirements.txt
└── README_LEONARDO.md     # this file
```

Each journey is **one LLM call** (vLLM batches thousands at once). The model role-plays
the persona and emits a per-step JSON trace; Python enforces the funnel **scope rules**
(hospital / "other persons" / Opt.Plus / Premium → advisor route = clean exit, not a
conversion), grounds the prices, and writes the label (`1` = abandoned/routed at this
step, `0` = continued). This is the **no-coach baseline** dataset — exactly what you
want to train a "user is about to abandon" predictor.

---

## 0. One person creates the shared folder

Per the plan, use `$PUBLIC` so all four teammates write to the same place:

```bash
echo "$PUBLIC"                      # confirm your public area path
mkdir -p "$PUBLIC/hackathon_data"
chmod -R g+rwX "$PUBLIC"            # let teammates read/write
```

Everyone points `--output-dir` at `$PUBLIC/hackathon_data`.

> If `$PUBLIC` is unset, it's typically `/leonardo/pub/userexternal/$USER`. Check the
> welcome MOTD ("A new personal area $PUBLIC is available…") for your exact path.

---

## 1. One-time setup on a LOGIN node (has internet)

```bash
# copy this folder to Leonardo, e.g. into $PUBLIC so everyone shares it
cd "$PUBLIC"
# (scp/rsync the leonardo_sim/ folder here from your laptop)
cd leonardo_sim

# strip Windows line endings if you edited on Windows
sed -i 's/\r$//' run_simulation.sbatch

# shared virtualenv under $PUBLIC
module load python/3.11.6 2>/dev/null || module load python    # name varies; `module avail python`
python -m venv "$PUBLIC/uniqa_venv"
source "$PUBLIC/uniqa_venv/bin/activate"
pip install --upgrade pip
pip install -r requirements.txt
```

### Pre-download the model (compute nodes can't reach the internet)

```bash
export HF_HOME="$PUBLIC/hf_cache"
export HF_TOKEN="hf_xxx"     # ONLY if the model is gated; Mistral-7B-Instruct-v0.2 needs
                             # you to accept its license once on huggingface.co, then a token
python download_model.py --model mistralai/Mistral-7B-Instruct-v0.2
```

This caches the weights under `$PUBLIC/hf_cache`. The compute job runs with
`HF_HUB_OFFLINE=1`, so it loads from this cache — no internet needed at run time.

> **Truly ungated alternative** (no license click / token): pass
> `--model teknium/OpenHermes-2.5-Mistral-7B` here and in the sbatch `MODEL=...`. It's a
> Mistral-7B fine-tune and works with the same chat template.

---

## 2. Edit the sbatch header

Open `run_simulation.sbatch` and set:

- `--account=CHANGE_ME_ACCOUNT` → your project account (run `saldo -b` to list yours).
- Confirm the `PUBLIC`, `VENV`, `HF_HOME`, `MODEL` paths near the top match step 1.

Defaults already target Leonardo's A100 partition: `boost_usr_prod`, `--gres=gpu:1`,
1 hour wall time. For a quick smoke test use `--qos=boost_qos_dbg` and a low
`--per-persona` (see below).

---

## 3. Generate the data (the "divide" — 4 nodes)

Submit one job per persona so the four of you run in parallel and never overlap
(seeds are offset per persona inside the sbatch):

```bash
cd "$PUBLIC/leonardo_sim"
sbatch run_simulation.sbatch franz      # teammate 1  -> data_franz.csv
sbatch run_simulation.sbatch judith     # teammate 2  -> data_judith.csv
sbatch run_simulation.sbatch peter      # teammate 3  -> data_peter.csv
sbatch run_simulation.sbatch all        # teammate 4  -> all three (mixed/edge pass, seed 9009)
```

Each `franz/judith/peter` job writes 1,000 journeys (~5–8k rows) into
`$PUBLIC/hackathon_data/`. Mistral-7B on one A100 finishes 1,000 journeys in a few
minutes.

Monitor:
```bash
squeue --me
tail -f logs/sim_uniqa_sim_<jobid>.out
```

### Quick smoke test first (recommended)
```bash
# 1-min sanity check on 20 journeys before spending the real run
sbatch --qos=boost_qos_dbg --time=00:20:00 run_simulation.sbatch franz
# ...or override count by editing --per-persona 20 in the sbatch temporarily
```

---

## 4. Merge (the "conquer")

Once the jobs finish, one person merges everything (login node is fine — it's just pandas):

```bash
source "$PUBLIC/uniqa_venv/bin/activate"
python merge_datasets.py \
    --input-dir "$PUBLIC/hackathon_data" \
    --output    "$PUBLIC/hackathon_data/master_training_dataset.csv"
```

Prints per-persona counts and the converted / abandoned / advisor_routed split.

---

## 5. Hand off to the coach trainer (Step 4)

`master_training_dataset.csv` columns (one row per step reached per journey):

| column | meaning |
|---|---|
| `session_id`, `persona`, `segment` | journey identity |
| `step_id`, `step_name` | funnel step (1,2,3,4,6,7,12) |
| `coverage_selection`, `for_whom`, `tariff_selected`, `advisory_tariff_clicked` | choices made |
| `provisional_price`, `final_price`, `price_delta_pct` | first vs. final price + surcharge |
| `time_on_step_s`, `cumulative_time_s` | timing signals |
| `n_hesitation_events`, `n_back_clicks`, `opened_competitor_tab` | hesitation / comparison signals |
| `coach_intervened`, `coach_type` | always `0` / `none` here (baseline set) |
| **`label`** | **target: `1` = abandoned/routed at this step, else `0`** |
| `journey_outcome`, `final_step_reached` | `converted` / `abandoned` / `advisor_routed` |
| `gen_temperature`, `scenario`, `reasoning` | generation metadata + the model's rationale |

The teammate loads this and trains XGBoost to predict `label` from the behavioral
features — that's the "Coach's brain" (abandonment predictor). Drop `reasoning`,
`scenario`, ids, and any leakage columns (`journey_outcome`, `final_step_reached`)
from the feature matrix.

> Schema is a superset of the deterministic `data_franz.csv` generator
> (`../simulate_franz.py`), so you can `pd.concat` that file in too — pandas fills the
> extra columns with NaN.

---

## Tuning knobs

| Flag (persona_simulator.py) | Default | Notes |
|---|---|---|
| `--per-persona` | 1000 | journeys per persona |
| `--temp-lo` / `--temp-hi` | 0.7 / 1.05 | per-journey temperature is sampled in this range — widen `--temp-hi` (e.g. 1.2) for more edge cases (the teammate-4 "mixed" pass) |
| `--seed` | from sbatch | offset per persona so nodes don't duplicate |
| `--tensor-parallel-size` | 1 | set to 2–4 to shard a bigger model across GPUs (request matching `--gres=gpu:N`) |
| `--max-model-len` | 4096 | plenty for one journey |

## Troubleshooting

- **`OSError: ... not found` / tries to reach huggingface.co on the compute node** →
  weights weren't pre-downloaded into `$HF_HOME`, or `HF_HOME` differs between the
  download step and the sbatch. Re-run `download_model.py` with the same `HF_HOME`.
- **Gated repo / 401** → accept the model license on huggingface.co and export a valid
  `HF_TOKEN` before `download_model.py`, or switch to the ungated OpenHermes model.
- **CUDA OOM at load** → lower `--gpu-memory-utilization` (e.g. 0.85) or `--max-model-len`.
- **High `parse_fail` count** → lower `--temp-hi` toward 0.9; the JSON parser is tolerant
  but very high temperatures occasionally break structure. Failed journeys are skipped,
  not written.
- **`sbatch: error: invalid account`** → fix `--account` (run `saldo -b`).
