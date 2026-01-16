#!/usr/bin/env python3
"""Build clean transactions + customer-level RFM table from Online Retail II.

Online Retail II often comes as an Excel workbook with *two sheets* (2009-2010 and 2010-2011),
and column names vary slightly across mirrors. This script handles both.

Usage:
  python etl/build_rfm.py --input data/raw/online_retail_II.xlsx --outdir data/processed

Outputs:
  - transactions_clean.csv
  - customers_rfm.csv
  - data_quality_report.md

Cleaning rules (common industry practice for behavioral segmentation):
  - Drop rows without CustomerID (cannot segment unknown customers)
  - Remove cancellations/returns (Invoice starting with 'C')
  - Remove non-positive Quantity and non-positive UnitPrice
"""

import argparse
import os
from datetime import timedelta

import pandas as pd

REQUIRED_COLS = [
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
]


def _read_any(path: str) -> pd.DataFrame:
    ext = os.path.splitext(path)[1].lower()
    if ext in [".xlsx", ".xls"]:
        # Read all sheets and concatenate (Online Retail II is commonly split by year).
        sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
        df = pd.concat(sheets.values(), ignore_index=True)
        return df
    if ext == ".csv":
        return pd.read_csv(path, encoding_errors="ignore")
    raise ValueError(f"Unsupported file type: {ext}")


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names across dataset variants."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # Case/space-insensitive matching
    lookup = {str(c).strip().lower().replace(" ", "").replace("_", ""): c for c in df.columns}

    def pick(*candidates: str) -> str | None:
        for cand in candidates:
            key = cand.lower().replace(" ", "").replace("_", "")
            if key in lookup:
                return lookup[key]
        return None

    mapping = {}
    mapping["InvoiceNo"] = pick("InvoiceNo", "Invoice", "InvoiceNo.")
    mapping["StockCode"] = pick("StockCode", "Stock Code")
    mapping["Description"] = pick("Description")
    mapping["Quantity"] = pick("Quantity", "Qty")
    mapping["InvoiceDate"] = pick("InvoiceDate", "Invoice Date")
    mapping["UnitPrice"] = pick("UnitPrice", "Price", "Unit Price")
    mapping["CustomerID"] = pick("CustomerID", "Customer ID", "CustomerId")
    mapping["Country"] = pick("Country")

    missing = [k for k, v in mapping.items() if v is None]
    if missing:
        raise ValueError(
            "Dataset missing required columns: " + ", ".join(missing) + "\n" +
            "Found columns: " + ", ".join(df.columns.astype(str))
        )

    df = df.rename(columns={v: k for k, v in mapping.items()})
    return df


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Path to Online Retail II file (.xlsx or .csv)")
    ap.add_argument("--outdir", required=True, help="Output directory")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    df_raw = _read_any(args.input)
    df_raw = _normalize_columns(df_raw)

    # Keep only needed columns
    df = df_raw[REQUIRED_COLS].copy()

    # Type conversions
    df["InvoiceNo"] = df["InvoiceNo"].astype(str)
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
    df["CustomerID"] = pd.to_numeric(df["CustomerID"], errors="coerce")
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
    df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce")

    # Data quality metrics (raw)
    n_rows_raw = len(df)
    null_invoice_date_raw = int(df["InvoiceDate"].isna().sum())
    null_customer_raw = int(df["CustomerID"].isna().sum())
    null_price_raw = int(df["UnitPrice"].isna().sum())
    null_qty_raw = int(df["Quantity"].isna().sum())

    # Identify cancellations/returns
    is_cancel = df["InvoiceNo"].str.startswith("C", na=False)

    # Clean
    df_clean = df.copy()
    df_clean = df_clean.dropna(subset=["InvoiceDate", "CustomerID", "UnitPrice", "Quantity"])
    df_clean = df_clean[~is_cancel]
    df_clean = df_clean[(df_clean["Quantity"] > 0) & (df_clean["UnitPrice"] > 0)]

    # Feature: line revenue
    df_clean["LineTotal"] = df_clean["Quantity"] * df_clean["UnitPrice"]

    # RFM snapshot date = day after max invoice date
    snapshot_date = df_clean["InvoiceDate"].max() + timedelta(days=1)

    rfm = (
        df_clean.groupby("CustomerID")
        .agg(
            recency_days=("InvoiceDate", lambda x: int((snapshot_date - x.max()).days)),
            frequency_invoices=("InvoiceNo", "nunique"),
            monetary_value=("LineTotal", "sum"),
            country=("Country", lambda x: x.mode().iloc[0] if len(x.mode()) else x.iloc[0]),
        )
        .reset_index()
    )

    # Write outputs
    tx_out = os.path.join(args.outdir, "transactions_clean.csv")
    rfm_out = os.path.join(args.outdir, "customers_rfm.csv")
    report_out = os.path.join(args.outdir, "data_quality_report.md")

    df_clean.to_csv(tx_out, index=False)
    rfm.to_csv(rfm_out, index=False)

    # Quality report
    with open(report_out, "w", encoding="utf-8") as f:
        f.write("# Data Quality Report — Online Retail II\n\n")
        f.write(f"**Raw rows:** {n_rows_raw:,}\n\n")
        f.write("## Raw missing values\n")
        f.write(f"- InvoiceDate missing: {null_invoice_date_raw:,}\n")
        f.write(f"- CustomerID missing: {null_customer_raw:,}\n")
        f.write(f"- UnitPrice missing: {null_price_raw:,}\n")
        f.write(f"- Quantity missing: {null_qty_raw:,}\n\n")

        f.write("## Rows removed\n")
        f.write(f"- Cancellations (Invoice starts with 'C'): {int(is_cancel.sum()):,}\n")
        f.write("- Rows with null critical fields (date/customer/qty/price)\n")
        f.write("- Rows with non-positive Quantity or UnitPrice\n\n")

        f.write("## Final curated datasets\n")
        f.write(f"- Clean transactions: {len(df_clean):,} rows\n")
        f.write(f"- RFM customers: {len(rfm):,} customers\n\n")
        f.write("## Snapshot date\n")
        f.write(f"- {snapshot_date.date().isoformat()}\n")

    print("Wrote:")
    print(f"- {tx_out}")
    print(f"- {rfm_out}")
    print(f"- {report_out}")


if __name__ == "__main__":
    main()
