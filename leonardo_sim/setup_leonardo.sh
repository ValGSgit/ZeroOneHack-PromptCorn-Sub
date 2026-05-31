#!/bin/bash
# One-shot setup on a Leonardo LOGIN node (has internet). Idempotent — safe to re-run.
#   1) installs pixi if missing
#   2) resolves + installs the locked environment from pixi.toml
#   3) pre-downloads the model into the shared cache (compute nodes are offline)
#
# Usage:
#   cd <this folder>
#   bash setup_leonardo.sh
set -euo pipefail

cd "$(dirname "$0")"

# ---- 1. pixi ----------------------------------------------------------------
if [ ! -x "$HOME/.pixi/bin/pixi" ] && ! command -v pixi >/dev/null 2>&1; then
    echo ">> Installing pixi ..."
    curl -fsSL https://pixi.sh/install.sh | bash
fi
export PATH="$HOME/.pixi/bin:$PATH"
echo ">> pixi $(pixi --version)"

# ---- 2. environment (creates .pixi/envs + pixi.lock) ------------------------
echo ">> Resolving + installing the environment (this downloads torch/vllm, ~3 GB) ..."
pixi install

# ---- 3. model weights into the shared cache --------------------------------
export PUBLIC="${PUBLIC:-/leonardo/pub/userexternal/$USER}"
export HF_HOME="${HF_HOME:-$PUBLIC/hf_cache}"
mkdir -p "$HF_HOME" "$PUBLIC/hackathon_data"
echo ">> Downloading model into HF_HOME=$HF_HOME ..."
pixi run download-model

echo ""
echo ">> Setup complete."
echo "   HF_HOME      = $HF_HOME"
echo "   Shared data  = $PUBLIC/hackathon_data"
echo "   Next: sbatch run_simulation.sbatch all     (or: bash run_all.sh)"
