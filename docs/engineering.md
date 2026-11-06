# Engineering notes

Source rows retain identifiers and duplicate flags. Missing customer IDs remain in company
totals, while contradictory transaction records are quarantined and reconciled separately.
Merchandise sales, credits, non-product adjustments and zero-price rows have explicit scopes.

SQL views calculate monthly, customer and product metrics from the classified ledger. The
volume-mix-price bridge includes separate new/discontinued product and credit movements;
it must reconcile exactly to the total classified revenue change.

Fixtures cover credits, missing customer IDs, duplicate preservation and periods without
shared products. Generated workbooks contain editable scenario assumptions and reconciliation
controls. Cost sensitivities are kept separate from observed revenue because the source has
no product-cost or collection records.

Tested dependency versions are recorded in constraints.txt and environment.json.
