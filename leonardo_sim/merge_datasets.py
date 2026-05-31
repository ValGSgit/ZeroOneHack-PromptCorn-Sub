#!/usr/bin/env python3
"""
merge_datasets.py — Step 3 of the team plan: merge every CSV in the shared folder
into one master training dataset for the Conversion Coach classifier.

Usage:
    python merge_datasets.py --input-dir "$PUBLIC/hackathon_data" \
        --output "$PUBLIC/hackathon_data/master_training_dataset.csv"
"""

import argparse
import glob
from pathlib import Path

import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-dir", required=True, help="Folder containing data_*.csv files.")
    ap.add_argument("--output", default="master_training_dataset.csv")
    ap.add_argument("--pattern", default="data_*.csv",
                    help="Glob pattern of files to merge (default: data_*.csv).")
    args = ap.parse_args()

    files = sorted(glob.glob(str(Path(args.input_dir) / args.pattern)))
    # never merge the master back into itself
    files = [f for f in files if Path(f).name != Path(args.output).name]
    if not files:
        raise SystemExit(f"No files matching {args.pattern} in {args.input_dir}")

    print("Merging:")
    frames = []
    for f in files:
        df = pd.read_csv(f)
        print(f"  {Path(f).name:30s} {len(df):>8,} rows  "
              f"({df['session_id'].nunique():,} sessions)")
        frames.append(df)

    master = pd.concat(frames, ignore_index=True)
    master.to_csv(args.output, index=False)

    print(f"\nSuccessfully merged {len(master):,} rows "
          f"({master['session_id'].nunique():,} journeys) -> {args.output}")
    if "persona" in master.columns:
        print("\nPer-persona journey counts:")
        per = master.groupby("persona")["session_id"].nunique()
        for name, cnt in per.items():
            print(f"  {name:10s} {cnt:,}")
    if "journey_outcome" in master.columns:
        print("\nOutcome distribution (per journey):")
        terminal = master.sort_values("step_id").groupby("session_id").tail(1)
        print(terminal["journey_outcome"].value_counts().to_string())


if __name__ == "__main__":
    main()
