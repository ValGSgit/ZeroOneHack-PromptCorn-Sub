#!/usr/bin/env python3
"""
train_coach.py — train the abandonment classifier (the Conversion Coach's "brain").

Input  : a no-coach baseline step-dataset from `simulate.py baseline`
         (or the LLM-generated master_training_dataset.csv — same feature names).
Target : `label` = 1 if the user abandoned/routed AT this step, else 0.
Output : artifacts/coach_model.pkl + evaluation plots + metrics.json

We train on GENUINE abandonment risk only: forced out-of-scope routes
(hospital / other-persons / advisory-tariff click) are dropped, because the coach
handles those with deterministic routing rules, not the risk model. No leakage:
only signals observable at the moment of the step feed the model.

  python train_coach.py --data artifacts/baseline_steps.csv --out-dir artifacts
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from coach.features import FEATURE_COLUMNS


def load_xy(path: str):
    df = pd.read_csv(path)
    # accept either our baseline schema or the LLM master schema
    if "forced_oos" in df.columns:
        df = df[df["forced_oos"] == 0].copy()
    if "advisory_click" not in df.columns and "advisory_tariff_clicked" in df.columns:
        df = df.rename(columns={"advisory_tariff_clicked": "advisory_click"})
    # derive cumulative features if absent (LLM CSV doesn't carry them)
    for col, src in (("cum_hesitation_events", "n_hesitation_events"),
                     ("cum_back_clicks", "n_back_clicks")):
        if col not in df.columns:
            df[col] = (df.sort_values(["session_id", "step_id"])
                         .groupby("session_id")[src].cumsum().reindex(df.index).fillna(0))
    if "step" not in df.columns:
        df["step"] = df["step_id"]
    df["is_price_step"] = df["step"].isin([4, 7]).astype(float)
    for c in ("provisional_price", "price_delta_pct"):
        df[c] = pd.to_numeric(df.get(c), errors="coerce").fillna(0.0)
    df["advisory_click"] = pd.to_numeric(df.get("advisory_click", 0), errors="coerce").fillna(0)
    X = df[FEATURE_COLUMNS].astype(float).values
    y = df["label"].astype(int).values
    return X, y, df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="artifacts/baseline_steps.csv")
    ap.add_argument("--out-dir", default="artifacts")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import (roc_auc_score, average_precision_score,
                                 precision_recall_curve, roc_curve, brier_score_loss,
                                 classification_report)
    from sklearn.calibration import calibration_curve
    from sklearn.inspection import permutation_importance
    import joblib
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    X, y, df = load_xy(args.data)
    print(f"Loaded {len(y):,} trainable step-rows  | positive (abandon) rate = {y.mean()*100:.1f}%")

    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25,
                                          random_state=args.seed, stratify=y)
    clf = HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.06, max_depth=4,
        l2_regularization=1.0, early_stopping=True, random_state=args.seed)
    clf.fit(Xtr, ytr)

    p = clf.predict_proba(Xte)[:, 1]
    auc = roc_auc_score(yte, p)
    ap_ = average_precision_score(yte, p)
    brier = brier_score_loss(yte, p)
    print(f"\nHeld-out  ROC-AUC={auc:.3f}  PR-AUC={ap_:.3f}  Brier={brier:.3f}")
    print(classification_report(yte, (p >= 0.5).astype(int),
                                target_names=["continue", "abandon"], digits=3))

    # ---- plots: ROC, PR, calibration, feature importance ----
    fig, ax = plt.subplots(2, 2, figsize=(12, 9))
    fpr, tpr, _ = roc_curve(yte, p)
    ax[0, 0].plot(fpr, tpr, label=f"AUC={auc:.3f}"); ax[0, 0].plot([0, 1], [0, 1], "k--", lw=.7)
    ax[0, 0].set(title="ROC", xlabel="FPR", ylabel="TPR"); ax[0, 0].legend()

    pr, rc, _ = precision_recall_curve(yte, p)
    ax[0, 1].plot(rc, pr, label=f"PR-AUC={ap_:.3f}")
    ax[0, 1].axhline(yte.mean(), ls="--", c="gray", lw=.7, label=f"base={yte.mean():.2f}")
    ax[0, 1].set(title="Precision-Recall", xlabel="Recall", ylabel="Precision"); ax[0, 1].legend()

    frac, mean_pred = calibration_curve(yte, p, n_bins=10, strategy="quantile")
    ax[1, 0].plot(mean_pred, frac, "o-"); ax[1, 0].plot([0, 1], [0, 1], "k--", lw=.7)
    ax[1, 0].set(title=f"Calibration (Brier={brier:.3f})",
                 xlabel="Predicted risk", ylabel="Observed abandon rate")

    imp = permutation_importance(clf, Xte, yte, n_repeats=8, random_state=args.seed,
                                 scoring="roc_auc")
    order = np.argsort(imp.importances_mean)
    ax[1, 1].barh([FEATURE_COLUMNS[i] for i in order], imp.importances_mean[order])
    ax[1, 1].set(title="Permutation importance (Δ ROC-AUC)")
    fig.tight_layout(); fig.savefig(out / "classifier_eval.png", dpi=110); plt.close(fig)

    joblib.dump(clf, out / "coach_model.pkl")
    metrics = {"n_rows": int(len(y)), "positive_rate": float(y.mean()),
               "roc_auc": float(auc), "pr_auc": float(ap_), "brier": float(brier),
               "feature_importance": {FEATURE_COLUMNS[i]: float(imp.importances_mean[i])
                                      for i in range(len(FEATURE_COLUMNS))}}
    (out / "classifier_metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"\nSaved model -> {out/'coach_model.pkl'}")
    print(f"Saved plots -> {out/'classifier_eval.png'}")
    print(f"Top features: " + ", ".join(
        f"{FEATURE_COLUMNS[i]}({imp.importances_mean[i]:.3f})" for i in order[::-1][:4]))


if __name__ == "__main__":
    main()
