#!/usr/bin/env python3
"""Train a customer segmentation model (KMeans) on RFM features.

Default behavior: train a 4-cluster KMeans model on log-scaled RFM features.

Why this file exists in the repo:
- Shows feature engineering (RFM)
- Shows simple, explainable segmentation (KMeans)
- Produces a scored customer table for BI tools + dashboards

Inputs:
  data/processed/customers_rfm.csv  (output of etl/build_rfm.py)

Outputs:
  data/processed/customers_rfm_scored.csv (includes cluster + segment_name)
  model/kmeans_model.pkl
  model/model_report.md

Usage:
  python model/train_cluster_model.py --rfm data/processed/customers_rfm.csv --outdir data/processed --k 4
"""

from __future__ import annotations

import os
# Make runs stable in constrained environments (avoid hanging due to BLAS thread oversubscription)
for _k in ["OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"]:
    os.environ.setdefault(_k, "1")

import argparse
from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler


@dataclass
class ModelArtifacts:
    k: int
    silhouette: float


def _normalize_columns(rfm: pd.DataFrame) -> pd.DataFrame:
    rfm = rfm.copy()
    # Handle common column name variants from different mirrors of Online Retail II
    ren = {}
    if "recency_days" in rfm.columns:
        ren["recency_days"] = "Recency"
    if "frequency_invoices" in rfm.columns:
        ren["frequency_invoices"] = "Frequency"
    if "monetary_value" in rfm.columns:
        ren["monetary_value"] = "Monetary"
    if "customer_id" in rfm.columns and "CustomerID" not in rfm.columns:
        ren["customer_id"] = "CustomerID"
    rfm = rfm.rename(columns=ren)

    required = ["CustomerID", "Recency", "Frequency", "Monetary"]
    missing = [c for c in required if c not in rfm.columns]
    if missing:
        raise ValueError(f"RFM file missing required columns: {missing}. Found: {list(rfm.columns)}")
    return rfm


def _segment_names_by_cluster(rfm_scored: pd.DataFrame) -> dict[int, str]:
    """Assign friendly names based on cluster-level medians.

    Heuristic:
      - High monetary + high frequency + low recency => Champions
      - High monetary/frequency but higher recency => Loyal (Needs Re-engagement)
      - Low monetary/frequency + low recency => New / Promising
      - Low monetary/frequency + high recency => At Risk / Lost
    """
    grp = rfm_scored.groupby("cluster").agg(
        Recency=("Recency", "median"),
        Frequency=("Frequency", "median"),
        Monetary=("Monetary", "median"),
        Customers=("CustomerID", "count"),
    )

    # Rank clusters by Monetary & Frequency (higher is better), and Recency (lower is better)
    grp["mon_rank"] = grp["Monetary"].rank(ascending=False, method="dense")
    grp["freq_rank"] = grp["Frequency"].rank(ascending=False, method="dense")
    grp["rec_rank"] = grp["Recency"].rank(ascending=True, method="dense")

    names: dict[int, str] = {}
    for cl, row in grp.iterrows():
        strong = (row["mon_rank"] <= 2) and (row["freq_rank"] <= 2)
        recent = (row["rec_rank"] <= 2)

        if strong and recent:
            names[int(cl)] = "Champions"
        elif strong and not recent:
            names[int(cl)] = "Loyal (Re-engage)"
        elif (not strong) and recent:
            names[int(cl)] = "New / Promising"
        else:
            names[int(cl)] = "At Risk / Lost"

    # Ensure uniqueness if heuristics collide
    seen = {}
    for cl, nm in list(names.items()):
        if nm in seen:
            names[cl] = f"{nm} ({cl})"
        else:
            seen[nm] = cl

    return names


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rfm", required=True, help="Path to customers_rfm.csv")
    ap.add_argument("--outdir", required=True, help="Output directory (processed)")
    ap.add_argument("--k", type=int, default=4, help="Number of clusters")
    ap.add_argument("--auto_k", action="store_true", help="Search k=2..10 via silhouette and pick best")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    os.makedirs("model", exist_ok=True)

    rfm = pd.read_csv(args.rfm)
    rfm = _normalize_columns(rfm)

    # Features (log-scaled to reduce skew)
    X = np.column_stack([
        np.log1p(rfm["Recency"].values),
        np.log1p(rfm["Frequency"].values),
        np.log1p(rfm["Monetary"].values),
    ])
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)

    best_k = args.k
    best_score = -1.0

    if args.auto_k:
        for k in range(2, 11):
            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = km.fit_predict(Xs)
            score = silhouette_score(Xs, labels)
            if score > best_score:
                best_score = score
                best_k = k
    else:
        km = KMeans(n_clusters=best_k, random_state=42, n_init=10)
        labels = km.fit_predict(Xs)
        best_score = float(silhouette_score(Xs, labels))

    # Fit final model
    km = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    labels = km.fit_predict(Xs)

    rfm_scored = rfm.copy()
    rfm_scored["cluster"] = labels.astype(int)

    name_map = _segment_names_by_cluster(rfm_scored)
    rfm_scored["segment_name"] = rfm_scored["cluster"].map(name_map)

    scored_path = os.path.join(args.outdir, "customers_rfm_scored.csv")
    rfm_scored.to_csv(scored_path, index=False)

    joblib.dump({"kmeans": km, "scaler": scaler, "segment_name_map": name_map}, "model/kmeans_model.pkl")

    report = os.path.join("model", "model_report.md")
    with open(report, "w", encoding="utf-8") as f:
        f.write("# Customer Segmentation Model Report\n\n")
        f.write(f"- Customers: {len(rfm_scored):,}\n")
        f.write(f"- Clusters (k): {best_k}\n")
        f.write(f"- Silhouette score: {best_score:.3f}\n\n")
        f.write("## Segment sizes\n\n")
        f.write(rfm_scored["segment_name"].value_counts().to_frame("customers").to_markdown())
        f.write("\n\n")
        f.write("## Cluster medians (R/F/M)\n\n")
        f.write(
            rfm_scored.groupby(["segment_name", "cluster"])[["Recency", "Frequency", "Monetary"]]
            .median().round(2).to_markdown()
        )
        f.write("\n")

    print("Wrote:")
    print(f"- {scored_path}")
    print("- model/kmeans_model.pkl")
    print(f"- {report}")


if __name__ == "__main__":
    main()
