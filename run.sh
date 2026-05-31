#!/usr/bin/env bash
#
# run.sh — one launcher for the UNIQA Conversion Coach submission.
#
#   ./run.sh app                                 web demo  -> http://localhost:9696
#   ./run.sh demo --compare judith --seed 17     terminal side-by-side (routed -> CONVERTED)
#   ./run.sh demo --auto --seed 42               terminal: all three personas
#   ./run.sh eval [--no-plots]                   3-dimension evaluation
#   ./run.sh calibrate                           verify baseline 5.6% / 66% / 78%
#   ./run.sh train                               retrain the coach classifier
#   ./run.sh setup                               build the venv only
#
# It builds a local .venv with pip wheels — NO conda/pixi solve — so the
# "No candidates for torch" / NFS-cache problems can't happen. Override the
# interpreter with PYTHON=/path/to/python3 ; change the web port with PORT=xxxx.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIM="$ROOT/leonardo_sim"
DEMO="$ROOT/demo"
VENV="$ROOT/.venv"
PYBIN="$VENV/bin/python"

# Pin BLAS/OpenMP threads: keeps numpy/scikit-learn from spawning a CPU storm that
# an HPC login node's resource governor would SIGKILL (and it's plenty fast here).
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-1}"

say(){ printf "\033[1m> %s\033[0m\n" "$*"; }
die(){ printf "\033[31mERROR: %s\033[0m\n" "$*" >&2; exit 1; }

# Find a Python >= 3.10: $PYTHON, then PATH, then Leonardo's `module load python`.
find_python(){
  local c
  if [ -n "${PYTHON:-}" ] && "$PYTHON" -c 'import sys;exit(0 if sys.version_info[:2]>=(3,10) else 1)' 2>/dev/null; then
    echo "$PYTHON"; return 0
  fi
  for c in python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys;exit(0 if sys.version_info[:2]>=(3,10) else 1)' 2>/dev/null; then
      echo "$c"; return 0
    fi
  done
  # Leonardo / HPC: environment modules
  [ -f /etc/profile.d/modules.sh ] && . /etc/profile.d/modules.sh 2>/dev/null || true
  if command -v module >/dev/null 2>&1; then
    module load python/3.11.6 >/dev/null 2>&1 || module load python >/dev/null 2>&1 || true
    for c in python3.12 python3.11 python3.10 python3; do
      if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys;exit(0 if sys.version_info[:2]>=(3,10) else 1)' 2>/dev/null; then
        echo "$c"; return 0
      fi
    done
  fi
  return 1
}

ensure_venv(){
  if [ -x "$PYBIN" ]; then return 0; fi
  local PY; PY="$(find_python)" || die "need Python >= 3.10. Set PYTHON=/path/to/python3 (or 'module load python')."
  say "Creating .venv with $("$PY" --version 2>&1)"
  "$PY" -m venv "$VENV"
  "$PYBIN" -m pip install -q --upgrade pip
  say "Installing dependencies (pip wheels, ~1 min, one time)…"
  "$PYBIN" -m pip install -q \
    fastapi "uvicorn[standard]" pydantic numpy scikit-learn joblib pandas matplotlib
  say "Environment ready (.venv)."
}

usage(){
  cat <<'EOF'
UNIQA Conversion Coach — launcher

  ./run.sh app                              web demo (two showcases)       -> :9696
  ./run.sh demo --compare judith --seed 17  terminal side-by-side (routed -> CONVERTED)
  ./run.sh demo --compare franz  --seed 10  terminal: Franz abandoned -> CONVERTED
  ./run.sh demo --auto --seed 42            terminal: all three personas
  ./run.sh eval [--no-plots]                3-dimension before/after evaluation
  ./run.sh calibrate                        verify the baseline reproduces 5.6% / 66% / 78%
  ./run.sh train                            retrain the coach classifier
  ./run.sh setup                            build the .venv only

  PYTHON=/path/to/python3   pick the interpreter (default: auto / module load)
  PORT=9696                 web app port
EOF
}

cmd="${1:-help}"; shift || true
case "$cmd" in
  setup)            ensure_venv ;;
  app|web|start)    ensure_venv
                    say "Web demo → http://localhost:${PORT:-9696}   (Ctrl+C to stop)"
                    cd "$DEMO"; LEONARDO_SIM="$SIM" PYTHONWARNINGS=ignore exec "$PYBIN" app.py ;;
  demo|terminal)    ensure_venv; cd "$SIM"; exec "$PYBIN" demo.py "$@" ;;
  eval|evaluate)    ensure_venv; cd "$SIM"; exec "$PYBIN" evaluate.py "$@" ;;
  calibrate)        ensure_venv; cd "$SIM"; exec "$PYBIN" -m coach.funnel --calibrate "$@" ;;
  train)            ensure_venv; cd "$SIM"; exec "$PYBIN" train_coach.py "$@" ;;
  help|-h|--help)   usage ;;
  *)                die "unknown command '$cmd' (try ./run.sh help)" ;;
esac
