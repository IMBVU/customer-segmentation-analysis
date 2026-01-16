#!/usr/bin/env bash
set -euo pipefail

INPUT=${1:-data/raw/online_retail_II.xlsx}
OUTDIR=${2:-data/processed}

mkdir -p "$OUTDIR"

# If input is Excel, stream-convert to CSV first (faster + lighter for repeated runs)
EXT="${INPUT##*.}"
COMBINED_CSV="data/raw/online_retail_II_combined.csv"
if [[ "${EXT,,}" == "xlsx" || "${EXT,,}" == "xls" ]]; then
  echo "Converting Excel to CSV (streaming)..."
  python etl/convert_xlsx_to_csv.py --input "$INPUT" --output "$COMBINED_CSV"
  INPUT="$COMBINED_CSV"
fi

echo "Building RFM tables..."
python etl/build_rfm.py --input "$INPUT" --outdir "$OUTDIR"

echo "Training clustering model + scoring customers..."
python model/train_cluster_model.py --rfm "$OUTDIR/customers_rfm.csv" --outdir "$OUTDIR"

echo "\nPipeline complete. Run dashboard with:"
echo "  python dash_app/app.py"
