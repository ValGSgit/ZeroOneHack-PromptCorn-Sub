#!/usr/bin/env python3
"""
download_model.py — Pre-fetch the Mistral model on a LOGIN node (which has internet).

Leonardo COMPUTE nodes have no outbound internet, so the model weights must be
downloaded into a shared cache ($HF_HOME, ideally under $PUBLIC) before the sbatch
job runs. Run this once, on the login node, after `huggingface-cli login` (or with
HF_TOKEN exported) if the model is gated.

Usage (login node, venv activated):
    export HF_HOME="$PUBLIC/hf_cache"
    export HF_TOKEN="hf_xxx"            # only if the model is gated
    python download_model.py --model mistralai/Mistral-7B-Instruct-v0.2

It prints the local snapshot path — pass that (or the same HF id with HF_HUB_OFFLINE=1)
to persona_simulator.py --model.
"""

import argparse
import os
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="mistralai/Mistral-7B-Instruct-v0.2",
                    help="HF model id to download.")
    args = ap.parse_args()

    hf_home = os.environ.get("HF_HOME")
    if not hf_home:
        raise SystemExit(
            "ERROR: set HF_HOME first, e.g.  export HF_HOME=\"$PUBLIC/hf_cache\""
        )
    Path(hf_home).mkdir(parents=True, exist_ok=True)

    from huggingface_hub import snapshot_download

    print(f"Downloading {args.model} into {hf_home} ...")
    path = snapshot_download(
        repo_id=args.model,
        token=os.environ.get("HF_TOKEN"),
        # skip the duplicate .bin if safetensors exist (saves space/time)
        ignore_patterns=["*.pth", "*.gguf", "original/*"],
    )
    print("\nDownload complete.")
    print(f"Local snapshot path:\n  {path}")
    print("\nIn the sbatch job you can now use either:")
    print(f'  --model "{args.model}"   (with HF_HUB_OFFLINE=1 + HF_HOME set), or')
    print(f'  --model "{path}"          (explicit local path)')


if __name__ == "__main__":
    main()
