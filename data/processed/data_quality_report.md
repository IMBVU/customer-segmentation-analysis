# Data Quality Report — Online Retail II

**Raw rows:** 200,000

## Raw missing values
- InvoiceDate missing: 0
- CustomerID missing: 62,054
- UnitPrice missing: 0
- Quantity missing: 0

## Rows removed
- Cancellations (Invoice starts with 'C'): 3,999
- Rows with null critical fields (date/customer/qty/price)
- Rows with non-positive Quantity or UnitPrice

## Final curated datasets
- Clean transactions: 134,104 rows
- RFM customers: 2,504 customers

## Snapshot date
- 2011-02-24
