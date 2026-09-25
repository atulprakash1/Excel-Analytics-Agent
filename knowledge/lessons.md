# Lessons learned

Mistakes or near-misses caught in review, turned into rules every agent follows.
Lessons that apply to a whole Treasury area can later move into its domain pack.

### Large-notional outliers in a deal blotter are usually real deals, not data errors
- **What happened:** profile_excel.py flagged 90 "extreme outlier" values in Notional in CCY for IAM_Deal_Inventory_DUMMY_2026-08-01.xlsx (up to EUR 834M against a mean of EUR 39M). These were confirmed with the user as legitimate large money-market deals, not entry errors, and were kept in scope for every total.
- **Rule:** For deal-level notional/principal columns in a money-market blotter, treat the profiler's statistical outlier flag as a prompt to ask the user, not as a signal to exclude or cap the value. Only drop or adjust a flagged value if the user confirms it is wrong.
- **Applies to:** ['money_market', 'notional/principal measures on deal-level extracts']
- **Confirmed:** user, 2026-09-25

