# Modeling notes

## Features
- Recency: days since last purchase (lower is better)
- Frequency: distinct invoices (higher is better)
- Monetary: total spend (higher is better)

## Algorithm
KMeans with robust preprocessing:
- log1p transform Monetary & Frequency
- StandardScaler

## Cluster selection
- Silhouette score for k in [2..10]
- Fallback to k=4 if silhouette is not computable

## Segment naming
Each cluster is ranked by average RFM (higher score = better):
- Champions
- Loyal
- Potential
- At Risk
- Hibernating

(Exact labels depend on k and cluster ranking.)
