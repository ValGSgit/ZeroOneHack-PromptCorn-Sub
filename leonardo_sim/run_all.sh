#!/bin/bash
# Fire-and-forget UNIQA Conversion Coach pipeline on Leonardo:
#
#   [GPU] sim franz ─┐
#   [GPU] sim judith ┼─(afterok)→ [CPU] merge ─(afterok)→ [CPU] train + evaluate
#   [GPU] sim peter ─┘
#
# Submit all jobs with dependencies, then walk away — the master dataset, the
# trained coach model, and the evaluation plots all appear automatically.
#
#   bash run_all.sh                 # default: 5000 journeys/persona (~1-2h on A100)
#   N=1000 bash run_all.sh          # quick full run (~15 min)
#   N=20   bash run_all.sh          # tiny smoke test
#   N=8000 TIME=03:00:00 bash run_all.sh   # bigger run, longer walltime
#
# Knobs (env vars):
#   N      journeys per persona            (default 5000)
#   TIME   walltime per GPU sim job        (default 02:00:00)
#   QOS    queue for the GPU sims          (default normal; use boost_qos_dbg for <=30m tests)
set -euo pipefail

cd "$(dirname "$0")"
export N="${N:-5000}"
TIME="${TIME:-02:00:00}"
QOS="${QOS:-normal}"

echo ">> Submitting GPU simulation jobs"
echo "   N=$N journeys/persona  walltime=$TIME  qos=$QOS"
SB=(sbatch --parsable --qos="$QOS" --time="$TIME")
j1=$("${SB[@]}" run_simulation.sbatch franz)
j2=$("${SB[@]}" run_simulation.sbatch judith)
j3=$("${SB[@]}" run_simulation.sbatch peter)
echo "   franz=$j1  judith=$j2  peter=$j3"

# Merge runs only if all three sims finish successfully (afterok).
jm=$(sbatch --parsable --dependency=afterok:$j1:$j2:$j3 merge.sbatch)
echo ">> Merge job $jm queued (runs after all sims succeed)."

# Train + evaluate the coach once the master dataset exists.
jt=$(sbatch --parsable --dependency=afterok:$jm train_eval.sbatch)
echo ">> Train+evaluate job $jt queued (runs after merge succeeds)."

echo ""
squeue --me
echo ""
echo "When the whole chain finishes you'll have:"
echo "  \$PUBLIC/hackathon_data/master_training_dataset.csv   (merged GPU journeys)"
echo "  artifacts/coach_model.pkl                            (trained coach brain)"
echo "  artifacts/classifier_eval.png  artifacts/eval_*.png  (metrics + plots)"
echo ""
echo "Track progress:  squeue --me   |   tail -f logs/sim_uniqa_sim_${j1}.out"
