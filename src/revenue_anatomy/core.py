"""Transaction classification and an exact sequential revenue bridge."""

import numpy as np
import pandas as pd


def clean(raw):
    data = raw.copy()
    data["row_id"] = np.arange(len(data))
    data["duplicate_flag"] = raw.duplicated(keep=False)
    data["invoice"] = data.InvoiceNo.astype(str).str.upper().str.strip()
    data["product"] = data.StockCode.astype(str).str.upper().str.strip()
    data["customer"] = data.CustomerID.map(lambda x: str(int(x)) if pd.notna(x) else "UNKNOWN")
    data["date"] = pd.to_datetime(data.InvoiceDate)
    data["country"] = data.Country.fillna("UNKNOWN").astype(str)
    data["description"] = data.Description.fillna("Unknown description")
    data["quantity"] = pd.to_numeric(data.Quantity)
    data["unit_price"] = pd.to_numeric(data.UnitPrice)
    data["amount"] = data.quantity * data.unit_price
    data["is_product"] = data["product"].str.fullmatch(r"\d{5}[A-Z]?")
    cancellation = data.invoice.str.startswith("C")
    invalid = data.unit_price.lt(0) | (cancellation & data.quantity.gt(0)) | data.date.isna()
    data["classification"] = np.select(
        [
            invalid,
            data.quantity.lt(0),
            data.is_product & data.quantity.gt(0) & data.unit_price.gt(0),
            data.is_product & data.unit_price.eq(0),
        ],
        ["quarantine", "credit", "product_sale", "zero_price"],
        default="adjustment",
    )
    # Credits retain their product/non-product status for separate bridge terms.
    data["month"] = data.date.dt.to_period("M").astype(str)
    return data


def revenue_bridge(data, before, after):
    def period(month):
        d = data[(data.month == month) & (data.classification != "quarantine")]
        sales = (
            d[d.classification == "product_sale"]
            .groupby("product")
            .agg(quantity=("quantity", "sum"), revenue=("amount", "sum"))
        )
        return d, sales

    a, x = period(before)
    b, y = period(after)
    shared = x.index.intersection(y.index)
    new, lost = y.index.difference(x.index), x.index.difference(y.index)
    rows = []
    q0, q1 = x.loc[shared, "quantity"], y.loc[shared, "quantity"]
    volume = mix = price = 0.0
    if len(shared):
        p0 = x.loc[shared, "revenue"] / q0
        p1 = y.loc[shared, "revenue"] / q1
        s0, s1 = q0 / q0.sum(), q1 / q1.sum()
        volume = float((q1.sum() - q0.sum()) * (s0 * p0).sum())
        mix = float(q1.sum() * ((s1 - s0) * p0).sum())
        price = float((q1 * (p1 - p0)).sum())
    for driver, value in [
        ("Volume, shared products", volume),
        ("Mix, shared products", mix),
        ("Price, shared products", price),
        ("New products", float(y.loc[new, "revenue"].sum())),
        ("Discontinued products", -float(x.loc[lost, "revenue"].sum())),
    ]:
        rows.append(dict(driver=driver, change=value))
    for kind in ["credit", "adjustment", "zero_price"]:
        rows.append(
            dict(
                driver=kind,
                change=float(
                    b.loc[b.classification == kind, "amount"].sum()
                    - a.loc[a.classification == kind, "amount"].sum()
                ),
            )
        )
    opening, closing = float(a.amount.sum()), float(b.amount.sum())
    result = pd.DataFrame(rows)
    difference = closing - opening - result.change.sum()
    if abs(difference) > max(0.01, abs(closing) * 1e-10):
        raise ValueError(f"Revenue bridge does not reconcile: {difference}")
    return result, dict(
        before=before, after=after, opening=opening, closing=closing, difference=float(difference)
    )


def customer_cohorts(data):
    sales = data[(data.classification == "product_sale") & (data.customer != "UNKNOWN")].copy()
    first = sales.groupby("customer").month.min()
    sales["cohort"] = sales.customer.map(first)
    counts = sales.groupby(["cohort", "month"]).customer.nunique().rename("active_customers").reset_index()
    initial = counts[counts.cohort == counts.month].set_index("cohort").active_customers
    counts["cohort_customers"] = counts.cohort.map(initial)
    counts["retention"] = counts.active_customers / counts.cohort_customers
    return counts
