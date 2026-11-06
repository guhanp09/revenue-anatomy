# Revenue Anatomy methodology

Source rows retain unique row IDs. Exact duplicates are flagged and retained, because repeated lines may be legitimate. Missing customer IDs become UNKNOWN without being dropped from company totals. Cancellation-prefixed positive quantities, negative prices and invalid dates are quarantined. Negative quantities are credits; positive-price, positive-quantity merchandise rows are product sales; zero prices and non-product adjustments remain separate. Product-code pattern matching is a transparent heuristic, not a verified product master.

SQL views calculate monthly gross merchandise sales, credits, non-product adjustments, net classified revenue, distinct merchandise invoices and known active customers. Company totals include unidentified customers. Product and customer totals deliberately have different scopes and are labeled. The source total equals classified plus quarantined amounts; monthly classified revenue equals the cleaned ledger.

For shared products, let Q be total units, s product unit shares and p realized average prices. The sequential bridge is volume = (Q1−Q0)Σs0p0; mix = Q1Σ(s1−s0)p0; price = Q1Σs1(p1−p0). New-product sales and lost-product prior sales are separate, as are credits/adjustments. This telescopes exactly. Order matters; realized price changes can reflect discounting and customer mix. There is no causal price-elasticity inference.

Known-customer concentration uses identified gross merchandise sales as its denominator. Cohorts use first observed purchase within the dataset; left-censoring and incomplete follow-up limit lifetime interpretations. The partial final month is excluded from the complete-month trend. Scenario contribution deducts assumed cost ratios and fulfilment per order; it is not observed accounting profit. Obtain real cost and credit reason-code data before pricing or quality decisions.

## Data flow

UCI Excel archive → preserved source parquet → classified transaction ledger → SQLite facts and SQL views → reconciled metrics / exact bridge → workbook, report, presentation and application.
