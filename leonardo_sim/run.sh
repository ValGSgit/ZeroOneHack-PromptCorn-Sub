#!/usr/bin/env bash
#
# run.sh — keyword launcher for the UNIQA persona simulator project.
#
# Two pipelines live in this repo:
#
#   LOCAL (CPU, runs anywhere) — the analytical funnel model:
#       baseline -> train -> evaluate -> compare        (writes to artifacts/)
#
#   CLUSTER (GPU, Leonardo) — the LLM persona journey generator:
#       setup -> download -> submit (sbatch) -> merge   (writes to $PUBLIC/hackathon_data)
#
# Run `./run.sh help` for the full command list. Unknown/extra options after a
# command are passed straight through to the underlying python entrypoint, so
# every flag the tools support is still reachable.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# --- python runner: prefer the local coach venv, then pixi, then system python3 -
export PATH="$HOME/.pixi/bin:$PATH"
if [ -x "$SCRIPT_DIR/.venv_coach/bin/python" ]; then
    PY=("$SCRIPT_DIR/.venv_coach/bin/python")
elif command -v pixi >/dev/null 2>&1; then
    PY=(pixi run python)
else
    PY=(python3)
fi

# --- cluster defaults (match setup_leonardo.sh / run_simulation.sbatch) -------
export PUBLIC="${PUBLIC:-/leonardo/pub/userexternal/$USER}"
export HF_HOME="${HF_HOME:-$PUBLIC/hf_cache}"
MODEL="${MODEL:-${MODEL_PATH:-mistralai/Mistral-7B-Instruct-v0.2}}"
DATA_DIR="${DATA_DIR:-$PUBLIC/hackathon_data}"

# --- colors (off when not a tty) ---------------------------------------------
if [ -t 1 ]; then
    B="\033[1m"; G="\033[32m"; C="\033[36m"; Y="\033[33m"; D="\033[2m"; R="\033[0m"
else
    B=""; G=""; C=""; Y=""; D=""; R=""
fi
say() { printf "${B}> %s${R}\n" "$*"; }

usage() {
    printf "${B}UNIQA persona simulator — runner${R}\n\n"
    printf "${B}USAGE${R}\n"
    printf "    ./run.sh <command> [options]\n"
    printf "    Extra options are forwarded to the underlying tool.\n\n"

    printf "${B}LOCAL PIPELINE${R} ${D}(CPU — analytical funnel model, writes artifacts/)${R}\n"
    printf "    ${G}baseline${R}   Generate no-coach training data    ${D}-> artifacts/baseline_steps.csv${R}\n"
    printf "    ${G}train${R}      Train the Conversion Coach model    ${D}-> artifacts/coach_model.pkl${R}\n"
    printf "    ${G}evaluate${R}   Evaluate coach on held-out cohort   ${D}-> artifacts/eval_*.{json,png}${R}\n"
    printf "    ${G}compare${R}    Paired baseline-vs-coach outcomes   ${D}-> artifacts/compare_outcomes.csv${R}\n"
    printf "    ${G}pipeline${R}   baseline -> train -> evaluate -> compare (full local run)\n"
    printf "    ${G}clean${R}      Remove generated artifacts/ output\n\n"

    printf "${B}CLUSTER PIPELINE${R} ${D}(GPU / Leonardo — LLM persona journeys)${R}\n"
    printf "    ${G}setup${R}      One-shot login-node setup (pixi env + model download)\n"
    printf "    ${G}download${R}   Pre-download the HF model into \$HF_HOME\n"
    printf "    ${G}sim${R}        Run persona_simulator.py directly (needs a GPU node)\n"
    printf "    ${G}submit${R}     sbatch all personas + auto-merge (run_all.sh)\n"
    printf "    ${G}merge${R}      Merge data_*.csv into the master training set\n\n"

    printf "${B}COMMON OPTIONS${R}\n"
    printf "    ${C}baseline${R}   --n 8000  --seed 11   --out artifacts/baseline_steps.csv\n"
    printf "    ${C}train${R}      --data artifacts/baseline_steps.csv  --out-dir artifacts  --seed 0\n"
    printf "    ${C}evaluate${R}   --n 6000  --seed 99   --model artifacts/coach_model.pkl  --out-dir artifacts\n"
    printf "    ${C}compare${R}    --n 5000  --seed 99   --model artifacts/coach_model.pkl  --out artifacts/compare_outcomes.csv\n"
    printf "    ${C}sim${R}        --persona {franz|judith|peter|all}  --per-persona 1000  --seed 1234\n"
    printf "               --model PATH (default \$MODEL)  --output-dir DIR (default \$DATA_DIR)\n"
    printf "               --tensor-parallel-size N  --max-tokens 900  --max-model-len 4096\n"
    printf "    ${C}download${R}   --model PATH  (default \$MODEL)\n"
    printf "    ${C}merge${R}      --input-dir DIR (default \$DATA_DIR)  --output FILE  --pattern 'data_*.csv'\n\n"

    printf "${B}ENV OVERRIDES${R}\n"
    printf "    MODEL=%s\n" "$MODEL"
    printf "    DATA_DIR=%s\n" "$DATA_DIR"
    printf "    PUBLIC=%s  HF_HOME=%s\n\n" "$PUBLIC" "$HF_HOME"

    printf "${B}EXAMPLES${R}\n"
    printf "    ./run.sh pipeline                 ${D}# full local run end-to-end${R}\n"
    printf "    ./run.sh baseline --n 2000        ${D}# quick local dataset${R}\n"
    printf "    ./run.sh evaluate                 ${D}# metrics + plots into artifacts/${R}\n"
    printf "    ./run.sh sim --persona franz --per-persona 20   ${D}# small GPU smoke test${R}\n"
    printf "    N=20 ./run.sh submit              ${D}# sbatch all personas, 20 journeys each${R}\n"
    printf "    ./run.sh merge --input-dir \$PUBLIC/hackathon_data\n"
}

# --- local pipeline ----------------------------------------------------------
cmd_baseline() { say "simulate.py baseline $*"; "${PY[@]}" simulate.py baseline "$@"; }
cmd_train()    { say "train_coach.py $*";       "${PY[@]}" train_coach.py "$@"; }
cmd_evaluate() { say "evaluate.py $*";          "${PY[@]}" evaluate.py "$@"; }
cmd_compare()  { say "simulate.py compare $*";  "${PY[@]}" simulate.py compare "$@"; }
cmd_demo()     { say "demo.py $*";              "${PY[@]}" demo.py "$@"; }

cmd_pipeline() {
    cmd_baseline
    cmd_train
    cmd_evaluate
    cmd_compare
    printf "${G}pipeline complete -> see artifacts/${R}\n"
}

cmd_clean() {
    say "removing generated artifacts"
    rm -f artifacts/baseline_steps.csv artifacts/coach_model.pkl \
          artifacts/compare_outcomes.csv artifacts/eval_*.json artifacts/eval_*.png \
          artifacts/classifier_eval.png artifacts/classifier_metrics.json \
          artifacts/qualitative_trace.txt
    printf "${G}done${R}\n"
}

# --- cluster pipeline --------------------------------------------------------
cmd_setup()    { say "setup_leonardo.sh"; bash setup_leonardo.sh; }
cmd_submit()   { say "run_all.sh $*";     bash run_all.sh "$@"; }
cmd_download() { say "download_model.py"; "${PY[@]}" download_model.py --model "$MODEL" "$@"; }
cmd_merge()    { say "merge_datasets.py"; "${PY[@]}" merge_datasets.py --input-dir "$DATA_DIR" "$@"; }

cmd_sim() {
    # Inject defaults for the two required flags unless the user overrode them.
    local has_model=0 has_out=0 a
    for a in "$@"; do
        [ "$a" = "--model" ] && has_model=1
        [ "$a" = "--output-dir" ] && has_out=1
    done
    local extra=()
    [ "$has_model" -eq 0 ] && extra+=(--model "$MODEL")
    [ "$has_out" -eq 0 ]   && extra+=(--output-dir "$DATA_DIR")
    say "persona_simulator.py ${extra[*]} $*"
    "${PY[@]}" persona_simulator.py "${extra[@]}" "$@"
}

# --- dispatch ----------------------------------------------------------------
cmd="${1:-help}"
[ $# -gt 0 ] && shift || true
case "$cmd" in
    baseline)        cmd_baseline "$@" ;;
    train)           cmd_train "$@" ;;
    evaluate|eval)   cmd_evaluate "$@" ;;
    compare)         cmd_compare "$@" ;;
    demo)            cmd_demo "$@" ;;
    pipeline|all)    cmd_pipeline "$@" ;;
    clean)           cmd_clean "$@" ;;
    setup)           cmd_setup "$@" ;;
    download)        cmd_download "$@" ;;
    sim)             cmd_sim "$@" ;;
    submit)          cmd_submit "$@" ;;
    merge)           cmd_merge "$@" ;;
    help|-h|--help)  usage ;;
    *) printf "${Y}Unknown command: %s${R}\n\n" "$cmd" >&2; usage; exit 2 ;;
esac
