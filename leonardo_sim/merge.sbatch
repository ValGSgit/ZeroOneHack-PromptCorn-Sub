#!/bin/bash
#SBATCH --job-name=uniqa_merge
#SBATCH --partition=lrd_all_serial        # CPU/serial partition (no GPU, no reservation needed)
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=00:20:00
#SBATCH --output=logs/merge_%j.out
#SBATCH --error=logs/merge_%j.err
#
# Merges every data_*.csv in the shared folder into master_training_dataset.csv.
# Usually launched automatically by run_all.sh (after the sim jobs finish), but can
# also be submitted standalone:  sbatch merge.sbatch

set -euo pipefail

export PUBLIC="${PUBLIC:-/leonardo/pub/userexternal/$USER}"

PIXI="$HOME/.pixi/bin/pixi"
MANIFEST="$(cd "$(dirname "$0")" && pwd)/pixi.toml"

mkdir -p logs
$PIXI run --as-is --manifest-path "$MANIFEST" python3 merge_datasets.py \
    --input-dir "$PUBLIC/hackathon_data" \
    --output    "$PUBLIC/hackathon_data/master_training_dataset.csv"
