#!/bin/bash
#SBATCH --job-name=uniqa_sim
#SBATCH --account=EUHPC_D30_031
#SBATCH --partition=boost_usr_prod       # A100 64GB "Booster" partition
#SBATCH --qos=normal                     # use boost_qos_dbg for <=30min test runs
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --gres=gpu:1                      # 1x A100 is plenty for Mistral-7B
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=01:00:00
#SBATCH --output=logs/sim_%x_%j.out
#SBATCH --error=logs/sim_%x_%j.err
#
# Usage:
#   sbatch run_simulation.sbatch franz      # one persona
#   sbatch run_simulation.sbatch all        # all three personas in one job
#
# Split across 4 nodes per the team plan by submitting 4 jobs:
#   sbatch run_simulation.sbatch franz
#   sbatch run_simulation.sbatch judith
#   sbatch run_simulation.sbatch peter
#   sbatch run_simulation.sbatch all        # (4th node = mixed/edge-case pass)

set -euo pipefail

PERSONA="${1:-all}"

# ---- paths (EDIT these two if your layout differs) -----------------------
export PUBLIC="${PUBLIC:-/leonardo/pub/userexternal/$USER}"   # the shared team area
SHARED_DATA="${OUTDIR:-$PUBLIC/hackathon_data}"               # where CSVs land (override with OUTDIR=)
VENV="$PUBLIC/uniqa_venv"                                     # shared virtualenv
export HF_HOME="$PUBLIC/hf_cache"                             # pre-downloaded weights
MODEL="HuggingFaceH4/zephyr-7b-beta"                    # or a local snapshot path

# ---- offline: compute nodes have no internet, weights are pre-cached -----
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
export TOKENIZERS_PARALLELISM=false

mkdir -p logs "$SHARED_DATA"

# ---- environment ----------------------------------------------------------
# If you use the module system instead of a venv, replace the next lines, e.g.:
#   module load profile/deeplrn cuda/12.1 python/3.11.6
source "$VENV/bin/activate"

echo "Job $SLURM_JOB_ID on $(hostname)"
echo "Persona     : $PERSONA"
echo "Model       : $MODEL"
echo "Output dir  : $SHARED_DATA"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true

# ---- run ------------------------------------------------------------------
# The base seed is offset per persona so the 4 nodes never produce identical data.
case "$PERSONA" in
  franz)  SEED=1001 ;;
  judith) SEED=2002 ;;
  peter)  SEED=3003 ;;
  all)    SEED=9009 ;;
  *)      SEED=4242 ;;
esac

# Journeys per persona — override with `N=20 sbatch ...` for a quick smoke test.
PER_PERSONA="${N:-1000}"
echo "Per-persona  : $PER_PERSONA"

# Persona briefings (franz.md / judith.md / peter.md) live next to the script.
srun python persona_simulator.py \
    --persona "$PERSONA" \
    --per-persona "$PER_PERSONA" \
    --model "$MODEL" \
    --output-dir "$SHARED_DATA" \
    --persona-dir "$SLURM_SUBMIT_DIR" \
    --seed "$SEED" \
    --temp-lo 0.7 --temp-hi 1.05 \
    --tensor-parallel-size 1 \
    --max-model-len 8192

echo "Finished persona=$PERSONA -> $SHARED_DATA"
ls -lh "$SHARED_DATA"
