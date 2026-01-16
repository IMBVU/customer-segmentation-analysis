# Customer Segmentation Analysis (Online Retail II)

## Business goal
Segment customers based on purchase behavior to enable targeted retention, win-back, and upsell campaigns.

## Dataset
- **Online Retail II** (Excel workbook): `data/raw/online_retail_II.xlsx`
- This repo also includes a **quick-run sample extract** (200k rows) to let you view the interactive dashboard fast: `data/raw/online_retail_sample.csv`

## What you get
- Production-style **ETL** (schema normalization + cleaning + data quality report)
- **RFM feature engineering** (Recency, Frequency, Monetary)
- **KMeans clustering**
- Human-readable **segment names** per cluster
- An **interactive dashboard** (Dash) with filters + charts

## Project structure
```
customer-segmentation-analysis/
  data/
    raw/
      online_retail_II.xlsx
      online_retail_sample.csv
    processed/
  etl/build_rfm.py
  model/train_cluster_model.py
  dash_app/app.py
  docs/
  requirements.txt
  run_pipeline.sh
```

## Quickstart (recommended)
This uses the included sample extract so it runs quickly.

```bash
pip install -r requirements.txt
python etl/build_rfm.py --input data/raw/online_retail_sample.csv --outdir data/processed
python model/train_cluster_model.py --rfm data/processed/customers_rfm.csv --outdir data/processed
python dash_app/app.py
```
Open: http://127.0.0.1:8050

## Full dataset run (slower)
Running the entire Excel workbook can take longer because it has ~1M rows.

```bash
./run_pipeline.sh data/raw/online_retail_II.xlsx data/processed
python dash_app/app.py
```

## Dashboard features
- Filters: Country, Segment
- KPIs: Customers, Revenue (Monetary), Avg Recency, Avg Frequency
- Charts: Segment distribution, RFM scatter, Monetary by Segment, Monthly revenue by segment

## Notes on cleaning
- Removes rows without CustomerID
- Removes non-positive Quantity/UnitPrice and cancellations (Invoice numbers starting with "C")

---

### Suggested portfolio description (350 chars)
Customer segmentation on Online Retail II transactions using RFM features + KMeans. Includes production-style ETL, model training, segment profiling, and an interactive dashboard with country/segment filters to explore revenue and customer behavior patterns.
# Customer-Segmentation-Analysis
