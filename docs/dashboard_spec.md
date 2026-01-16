# Dashboard Spec — Customer Segmentation

## Audience
Marketing, retention, and growth stakeholders who need quick answers:
- Who are our best customers?
- Who is at risk of churning?
- Where should we focus offers and outreach?

## Filters (global)
- **Country** (multi-select)
- **Segment** (multi-select)

## KPI row (top)
- Customers (count)
- Revenue (Monetary sum)
- Avg Recency (days)
- Avg Frequency (invoices)

## Visuals
1. **Segment Distribution** (bar)
   - x: segment_name, y: customers
2. **RFM Scatter** (Recency vs Monetary, size=Frequency)
   - hover: customer_id, segment_name, R/F/M
3. **Monetary by Segment** (box)
   - y: monetary
4. **Monthly Revenue by Segment** (line)
   - x: month, y: revenue, color: segment

## Design notes
- Use consistent formatting: currency for monetary, days for recency
- Prefer hover tooltips over labels to reduce clutter
- Keep the dashboard in a single view with a clean grid layout
