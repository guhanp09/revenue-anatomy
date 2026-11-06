import numpy as np
import pandas as pd

from revenue_anatomy.core import clean, revenue_bridge


def test_bridge_handles_new_discontinued_and_credit():
    d = pd.DataFrame(
        [
            ["2025-01", "A", "product_sale", 10, 100],
            ["2025-01", "B", "product_sale", 5, 100],
            ["2025-01", "gone", "product_sale", 1, 50],
            ["2025-01", "A", "credit", -1, -10],
            ["2025-02", "A", "product_sale", 15, 180],
            ["2025-02", "B", "product_sale", 3, 75],
            ["2025-02", "new", "product_sale", 2, 80],
            ["2025-02", "A", "credit", -1, -12],
        ],
        columns=["month", "product", "classification", "quantity", "amount"],
    )
    bridge, metrics = revenue_bridge(d, "2025-01", "2025-02")
    assert abs(metrics["difference"]) < 1e-9
    assert np.isclose(bridge.change.sum(), 83)
    assert bridge.set_index("driver").loc["Discontinued products", "change"] == -50


def test_unknown_customer_preserved_and_duplicate_flagged():
    row = dict(
        InvoiceNo="1",
        StockCode="12345A",
        CustomerID=np.nan,
        InvoiceDate="2025-01-01",
        Country="UK",
        Description=None,
        Quantity=2,
        UnitPrice=3,
    )
    d = clean(pd.DataFrame([row, row]))
    assert d.amount.sum() == 12
    assert d.duplicate_flag.all()
    assert (d.customer == "UNKNOWN").all()
    assert d.is_product.all()


def test_credit_and_negative_price_classification():
    base = dict(StockCode="12345", CustomerID=1, InvoiceDate="2025-01-01", Country="UK", Description="A")
    d = clean(
        pd.DataFrame(
            [
                dict(base, InvoiceNo="C1", Quantity=-1, UnitPrice=3),
                dict(base, InvoiceNo="2", Quantity=1, UnitPrice=-3),
            ]
        )
    )
    assert d.classification.tolist() == ["credit", "quarantine"]


def test_bridge_without_any_shared_products():
    d = pd.DataFrame(
        [
            ["2025-01", "A", "product_sale", 2, 30.0],
            ["2025-02", "B", "product_sale", 3, 45.0],
        ],
        columns=["month", "product", "classification", "quantity", "amount"],
    )
    bridge, check = revenue_bridge(d, "2025-01", "2025-02")
    assert abs(check["difference"]) < 1e-9
    assert np.isclose(bridge.change.sum(), 15.0)
