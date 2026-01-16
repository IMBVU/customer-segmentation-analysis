#!/usr/bin/env bash
set -euo pipefail

python etl/build_rfm.py --input data/raw/online_retail_II.xlsx --outdir data/processed
python model/train_cluster_model.py --rfm data/processed/customers_rfm.csv --outdir data/processed

echo "Done. To view the dashboard: python dash_app/app.py"
