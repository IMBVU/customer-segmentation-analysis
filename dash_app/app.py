from __future__ import annotations

from pathlib import Path
import pandas as pd
from dash import Dash, dcc, html, Input, Output
import plotly.express as px

# -----------------------------
# Paths
# -----------------------------
HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent  # dash_app/ -> project root
PROCESSED = PROJECT_ROOT / "data" / "processed"

RFM_PATHS = [
    PROCESSED / "customers_rfm_scored.csv",
    PROCESSED / "customers_rfm.csv",
]
TXN_PATHS = [
    PROCESSED / "transactions_clean.csv",
    PROCESSED / "transactions_cleaned.csv",
    PROCESSED / "transactions.csv",
]


def _first_existing(paths: list[Path]) -> Path:
    for p in paths:
        if p.exists():
            return p
    raise FileNotFoundError(f"None of these files exist: {[str(p) for p in paths]}")


def _normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    return df


def _coalesce_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Return the first column name in df that matches any candidate (case/space-insensitive)."""
    cols_norm = {c.lower().replace(" ", "").replace("_", ""): c for c in df.columns}
    for cand in candidates:
        key = cand.lower().replace(" ", "").replace("_", "")
        if key in cols_norm:
            return cols_norm[key]
    return None


def _load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    rfm_path = _first_existing(RFM_PATHS)
    txn_path = _first_existing(TXN_PATHS)

    rfm = _normalize_cols(pd.read_csv(rfm_path))
    txn = _normalize_cols(pd.read_csv(txn_path))

    # ---- Normalize RFM column names ----
    # Customer id
    rfm_cust = _coalesce_column(rfm, ["CustomerID", "Customer ID", "customer_id"])
    if not rfm_cust:
        raise KeyError(f"RFM file missing customer id. Found columns: {list(rfm.columns)}")
    if rfm_cust != "CustomerID":
        rfm = rfm.rename(columns={rfm_cust: "CustomerID"})

    # Segment name
    seg_col = _coalesce_column(rfm, ["segment_name", "Segment", "SegmentName", "segment"])
    if seg_col and seg_col != "segment_name":
        rfm = rfm.rename(columns={seg_col: "segment_name"})
    if "segment_name" not in rfm.columns:
        # If your modeling step didn't label segments, at least show cluster.
        cl = _coalesce_column(rfm, ["cluster", "Cluster", "label"])
        if cl and cl != "cluster":
            rfm = rfm.rename(columns={cl: "cluster"})
        if "cluster" in rfm.columns:
            rfm["segment_name"] = "Cluster " + rfm["cluster"].astype(str)
        else:
            rfm["segment_name"] = "All Customers"

    # Recency / Frequency / Monetary
    rec = _coalesce_column(rfm, ["RecencyDays", "Recency", "Recency_Days", "recency_days"])
    freq = _coalesce_column(rfm, ["Frequency", "Freq"])
    mon = _coalesce_column(rfm, ["Monetary", "MonetaryValue", "Revenue", "Spend"])

    if rec and rec != "RecencyDays":
        rfm = rfm.rename(columns={rec: "RecencyDays"})
    if freq and freq != "Frequency":
        rfm = rfm.rename(columns={freq: "Frequency"})
    if mon and mon != "Monetary":
        rfm = rfm.rename(columns={mon: "Monetary"})

    required_rfm = ["CustomerID", "RecencyDays", "Frequency", "Monetary", "segment_name"]
    missing = [c for c in required_rfm if c not in rfm.columns]
    if missing:
        raise KeyError(f"Missing RFM columns: {missing}. Found: {list(rfm.columns)}")

    for c in ["RecencyDays", "Frequency", "Monetary"]:
        rfm[c] = pd.to_numeric(rfm[c], errors="coerce")

    # ---- Normalize Transactions columns ----
    txn_cust = _coalesce_column(txn, ["CustomerID", "Customer ID", "customer_id"])
    if not txn_cust:
        raise KeyError(f"Transactions file missing customer id. Found columns: {list(txn.columns)}")
    if txn_cust != "CustomerID":
        txn = txn.rename(columns={txn_cust: "CustomerID"})

    inv_date = _coalesce_column(txn, ["InvoiceDate", "Invoice Date", "invoice_date", "Order Date", "OrderDate"])
    if not inv_date:
        raise KeyError(f"Transactions file missing InvoiceDate/OrderDate. Found columns: {list(txn.columns)}")
    if inv_date != "InvoiceDate":
        txn = txn.rename(columns={inv_date: "InvoiceDate"})

    txn["InvoiceDate"] = pd.to_datetime(txn["InvoiceDate"], errors="coerce")
    txn = txn.dropna(subset=["InvoiceDate"]).copy()

    # Country (optional filter)
    country = _coalesce_column(txn, ["Country", "country"])
    if country and country != "Country":
        txn = txn.rename(columns={country: "Country"})
    if "Country" not in txn.columns:
        txn["Country"] = "All"

    # Revenue: TotalPrice = Quantity * UnitPrice (or fallback to existing Sales/Revenue)
    if "TotalPrice" not in txn.columns:
        qty = _coalesce_column(txn, ["Quantity", "qty"])
        unit = _coalesce_column(txn, ["UnitPrice", "Unit Price", "unit_price"])
        sales = _coalesce_column(txn, ["Sales", "Revenue", "Amount", "Total"])

        if qty and unit:
            txn["TotalPrice"] = pd.to_numeric(txn[qty], errors="coerce") * pd.to_numeric(txn[unit], errors="coerce")
        elif sales:
            txn["TotalPrice"] = pd.to_numeric(txn[sales], errors="coerce")
        else:
            raise KeyError(f"Couldn't create TotalPrice. Found columns: {list(txn.columns)}")

    txn["TotalPrice"] = pd.to_numeric(txn["TotalPrice"], errors="coerce").fillna(0)

    # Attach segment_name to transactions
    txn = txn.merge(rfm[["CustomerID", "segment_name"]], on="CustomerID", how="left")
    txn["segment_name"] = txn["segment_name"].fillna("Unknown")

    return rfm, txn


rfm, txn = _load_data()

# Precompute month
txn["Month"] = txn["InvoiceDate"].dt.to_period("M").dt.to_timestamp()

# -----------------------------
# App
# -----------------------------
app = Dash(__name__)
app.title = "Customer Segmentation Dashboard"

countries = ["All"] + sorted(txn["Country"].dropna().unique().tolist())
segments = ["All"] + sorted(rfm["segment_name"].dropna().unique().tolist())


def _filter(country: str, segment: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    t = txn.copy()
    r = rfm.copy()

    if country != "All":
        t = t[t["Country"] == country]

    if segment != "All":
        r = r[r["segment_name"] == segment]
        t = t[t["segment_name"] == segment]

    return r, t


def _kpi(value: str, subtitle: str) -> html.Div:
    return html.Div(
        [
            html.Div(value, style={"fontSize": "24px", "fontWeight": "700"}),
            html.Div(subtitle, style={"fontSize": "12px", "opacity": 0.7}),
        ],
        style={
            "padding": "12px 14px",
            "border": "1px solid rgba(0,0,0,0.08)",
            "borderRadius": "14px",
            "background": "white",
            "boxShadow": "0 2px 12px rgba(0,0,0,0.04)",
        },
    )


app.layout = html.Div(
    [
        html.Div(
            [
                html.H1("Customer Segmentation Dashboard", style={"margin": "0 0 6px 0"}),
                html.Div(
                    "RFM segmentation using Online Retail transactions. Filter by country and segment to explore behavior and revenue trends.",
                    style={"opacity": 0.8},
                ),
            ],
            style={"marginBottom": "14px"},
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.Div("Filters", style={"fontWeight": "700", "marginBottom": "8px"}),
                        html.Label("Country", style={"fontSize": "12px", "opacity": 0.75}),
                        dcc.Dropdown(countries, "All", id="country", clearable=False),
                        html.Label("Segment", style={"fontSize": "12px", "opacity": 0.75, "marginTop": "10px", "display": "block"}),
                        dcc.Dropdown(segments, "All", id="segment", clearable=False),
                    ],
                    style={
                        "padding": "14px",
                        "border": "1px solid rgba(0,0,0,0.08)",
                        "borderRadius": "14px",
                        "background": "white",
                        "boxShadow": "0 2px 12px rgba(0,0,0,0.04)",
                    },
                ),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Div(id="kpis", style={"display": "grid", "gridTemplateColumns": "repeat(4, 1fr)", "gap": "12px"}),
                            ]
                        ),
                        html.Div([dcc.Graph(id="seg_dist")], style={"marginTop": "12px"}),
                        html.Div(
                            [
                                html.Div([dcc.Graph(id="rfm_scatter")], style={"flex": "1", "minWidth": "380px"}),
                                html.Div([dcc.Graph(id="monetary_by_seg")], style={"flex": "1", "minWidth": "380px"}),
                            ],
                            style={"display": "flex", "gap": "12px", "marginTop": "12px", "flexWrap": "wrap"},
                        ),
                        html.Div([dcc.Graph(id="monthly")], style={"marginTop": "12px"}),
                    ]
                ),
            ],
            style={"display": "grid", "gridTemplateColumns": "320px 1fr", "gap": "12px"},
        ),
        html.Div(
            "Tip: Segments come from your clustering output. If you re-train, re-run ETL/model scripts and refresh this dashboard.",
            style={"opacity": 0.65, "marginTop": "10px", "fontSize": "12px"},
        ),
    ],
    style={"maxWidth": "1200px", "margin": "18px auto", "padding": "0 14px", "fontFamily": "Arial"},
)


@app.callback(
    Output("kpis", "children"),
    Output("seg_dist", "figure"),
    Output("rfm_scatter", "figure"),
    Output("monetary_by_seg", "figure"),
    Output("monthly", "figure"),
    Input("country", "value"),
    Input("segment", "value"),
)
def update(country: str, segment: str):
    r, t = _filter(country, segment)

    customers = int(r["CustomerID"].nunique())
    revenue = float(t["TotalPrice"].sum())
    avg_rec = float(r["RecencyDays"].mean()) if len(r) else 0.0
    avg_freq = float(r["Frequency"].mean()) if len(r) else 0.0

    kpis = [
        _kpi(f"{customers:,}", "Customers"),
        _kpi(f"${revenue:,.0f}", "Revenue"),
        _kpi(f"{avg_rec:,.1f}", "Avg Recency (days)"),
        _kpi(f"{avg_freq:,.2f}", "Avg Frequency"),
    ]

    seg_dist = r.groupby("segment_name", as_index=False).agg(Customers=("CustomerID", "nunique"))
    fig_seg = px.bar(seg_dist.sort_values("Customers", ascending=False), x="segment_name", y="Customers", title="Customers by Segment")
    fig_seg.update_layout(xaxis_title="Segment", yaxis_title="Customers", margin=dict(l=20, r=20, t=50, b=20))

    fig_scatter = px.scatter(
        r,
        x="RecencyDays",
        y="Monetary",
        color="segment_name",
        hover_data=["CustomerID", "Frequency"],
        title="RFM: Recency vs Monetary",
    )
    fig_scatter.update_layout(margin=dict(l=20, r=20, t=50, b=20))

    mon_seg = r.groupby("segment_name", as_index=False).agg(AvgMonetary=("Monetary", "mean"), Customers=("CustomerID", "nunique"))
    fig_mon = px.bar(mon_seg.sort_values("AvgMonetary", ascending=False), x="segment_name", y="AvgMonetary", title="Average Monetary Value by Segment")
    fig_mon.update_layout(xaxis_title="Segment", yaxis_title="Avg Monetary", margin=dict(l=20, r=20, t=50, b=20))

    monthly = t.groupby(["Month", "segment_name"], as_index=False)["TotalPrice"].sum()
    fig_month = px.line(monthly, x="Month", y="TotalPrice", color="segment_name", title="Monthly Revenue by Segment")
    fig_month.update_layout(xaxis_title="Month", yaxis_title="Revenue", margin=dict(l=20, r=20, t=50, b=20))

    return kpis, fig_seg, fig_scatter, fig_mon, fig_month


if __name__ == "__main__":
    # Dash 2.16+ prefers app.run()
    app.run(debug=True, host="127.0.0.1", port=8050)
