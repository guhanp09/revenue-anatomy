# Data dictionary and provenance

Chen, D. (2015), Online Retail, UCI dataset 352, DOI 10.24432/C5BW33, CC BY 4.0. All 541,909 rows from a UK-based non-store retailer, December 2010–December 2011. Prices are GBP. Product costs, payment collections, marketing spending, true acquisition dates and causal elasticities are unavailable. Cost scenarios are explicitly assumed.

| Derived field | Meaning |
| --- | --- |
| row_id | Stable row number within source snapshot |
| invoice, product | Preserved string source identifiers |
| customer | Customer ID, with UNKNOWN for missing IDs |
| date, month | Transaction timestamp and calendar month |
| quantity, unit_price, amount | Units, GBP/unit, quantity × unit_price |
| duplicate_flag | Member of an exact source-duplicate group; row retained |
| is_product | Product-code-pattern heuristic |
| classification | product_sale, credit, adjustment, zero_price or quarantine |

Company totals include unknown customers and non-product adjustments. Known-customer
concentration has an identified-gross-sales denominator. Product totals are merchandise
only. Source rows with negative prices are quarantined rather than normalized into sales.
The SQLite views live in sql/metrics.sql. Cost ratios and fulfilment costs are separate
assumptions; there are no observed cost, collection or marketing fields.
