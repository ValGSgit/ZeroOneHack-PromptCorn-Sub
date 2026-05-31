#!/bin/bash
#SBATCH --job-name=uniqa_traineval
#SBATCH --partition=lrd_all_serial        # CPU/serial — no GPU needed for the coach brain
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=00:30:00
#SBATCH --output=logs/traineval_%j.out
#SBATCH --error=logs/traineval_%j.err
#
# Trains the Conversion Coach's abandonment classifier on the merged GPU dataset,
# then evaluates the coach (before/after, 3 dimensions) on the calibrated funnel.
# Usually chained automatically after the merge job by run_all.sh; can also run
# standalone:  sbatch train_eval.sbatch
#
# CPU-only and fast (a few minutes). The GPU work is the persona data generation;
# this is the "coach's brain" fit + evaluation.

set -euo pipefail
cd "$(dirname "$0")"

export PUBLIC="${PUBLIC:-/leonardo/pub/userexternal/$USER}"
DATA="${DATA:-$PUBLIC/hackathon_data/master_training_dataset.csv}"
PY=".venv_coach/bin/python"

mkdir -p logs artifacts

echo "Training coach on: $DATA"
$PY train_coach.py --data "$DATA" --out-dir artifacts

echo ""
echo "Evaluating coach (held-out funnel cohort)..."
$PY evaluate.py --model artifacts/coach_model.pkl --out-dir artifacts --n 6000 --seed 99

echo ""
echo "Done. Artifacts in artifacts/:"
ls -lh artifacts/
