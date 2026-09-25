# Decisions

Answers to questions raised during profiling or review, so they are not asked again.
Newest at the bottom. If a decision is reversed, add a new decision that says so.

### 2026-09-25 - As-of date for maturity bucketing uses the file's Reporting Date, not calendar today
- **Decision:** When a snapshot file's single Reporting Date is earlier than the current calendar date, maturity horizons (e.g. "next 7/30/90/365 days") are measured from the file's Reporting Date, not from today. Confirmed with the user for IAM_Deal_Inventory_DUMMY_2026-08-01.xlsx (Reporting Date 2026-08-01, run on 2026-09-25).
- **Applies to:** ['money_market', 'dated snapshot files with a single Reporting Date']
- **Confirmed:** user, 2026-09-25

### 2026-09-25 - "Maturing in next N days" means cumulative windows, not exclusive buckets
- **Decision:** When a question asks for the total amount maturing in the next 7, 30, 90 and 365 days, each number is the cumulative total from the as-of date out to that horizon (so 30d includes everything in 7d, 90d includes everything in 30d, etc.), not a partition into non-overlapping buckets. A separate by-year or by-tenor-bucket table is used when a true partition is wanted. Confirmed with the user for deal_inventory_overview.
- **Applies to:** ['money_market', 'any maturity/aging report phrased as "next N days"']
- **Confirmed:** user, 2026-09-25

