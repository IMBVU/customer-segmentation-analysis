-- Optional: load curated tables into a SQL database

CREATE TABLE IF NOT EXISTS transactions_clean (
  InvoiceNo TEXT,
  StockCode TEXT,
  Description TEXT,
  Quantity INTEGER,
  InvoiceDate TIMESTAMP,
  UnitPrice NUMERIC,
  CustomerID TEXT,
  Country TEXT,
  TotalPrice NUMERIC
);

CREATE TABLE IF NOT EXISTS customers_rfm_scored (
  CustomerID TEXT PRIMARY KEY,
  Country TEXT,
  Recency INTEGER,
  Frequency INTEGER,
  Monetary NUMERIC,
  cluster INTEGER,
  segment_name TEXT
);
