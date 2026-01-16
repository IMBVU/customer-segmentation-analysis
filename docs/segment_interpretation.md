# Segment Interpretation (How to Explain This in Interviews)

This project uses RFM (Recency, Frequency, Monetary) to describe customer purchase behavior:
- **Recency**: days since last purchase (lower is better)
- **Frequency**: number of distinct invoices (higher is better)
- **Monetary**: total spend (higher is better)

## Cluster → Segment names
After clustering, each cluster is profiled using median R, F, M values and translated into a human-readable segment:

- **Champions**: very recent, high frequency, high spend
- **Loyal**: frequent purchasers with solid spend
- **Big Spenders**: high spend but not necessarily frequent
- **New / Promising**: recent but low frequency/spend so far
- **At Risk**: not recent; prior value may exist but engagement dropped
- **Hibernating**: long time since purchase and low engagement

## Recommended actions
- Champions: VIP perks, early access, referral asks
- Loyal: bundles, subscription offers, cross-sell
- Big Spenders: concierge outreach, premium recommendations
- New/Promising: onboarding sequence, second-purchase incentives
- At Risk: win-back offers, personalized emails
- Hibernating: low-cost reactivation campaigns, suppress from costly channels
