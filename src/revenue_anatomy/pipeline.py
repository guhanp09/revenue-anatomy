import io
import sqlite3
import zipfile

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import xlsxwriter
from pptx import Presentation
from pptx.util import Inches, Pt

from .core import clean, customer_cohorts, revenue_bridge
from .io import ROOT, chart, dump, fetch, report

SOURCE = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"


def prepare(refresh=False):
    path = fetch(SOURCE, ROOT / "data/raw/online_retail.zip", refresh)
    cache = ROOT / "data/raw/source.parquet"
    if not cache.exists() or refresh:
        with zipfile.ZipFile(path) as archive:
            name = next(n for n in archive.namelist() if n.endswith(".xlsx"))
            frame = pd.read_excel(io.BytesIO(archive.read(name)))
        # Mixed Excel identifiers are deliberately preserved as strings for stable parquet storage.
        frame["InvoiceNo"] = frame.InvoiceNo.astype(str)
        frame["StockCode"] = frame.StockCode.astype(str)
        frame["Description"] = frame.Description.astype("string")
        frame.to_parquet(cache, index=False)
    else:
        frame = pd.read_parquet(cache)
    data = clean(frame)
    out = ROOT / "data/processed"
    out.mkdir(parents=True, exist_ok=True)
    data.to_parquet(out / "transactions.parquet", index=False)
    dump(
        ROOT / "data/provenance.json",
        dict(
            source=SOURCE,
            dataset="UCI Online Retail, dataset 352",
            citation="Chen, D. (2015), DOI:10.24432/C5BW33",
            license="CC BY 4.0",
            geography="UK-based non-store retailer; international customers",
            currency="GBP",
            observed="invoice transactions, prices, quantities, product IDs, customer IDs, countries",
            unavailable="product costs, collections, marketing spend, true acquisition dates, causal price elasticities",
        ),
    )
    return data


def write_workbook(monthly, products, customers, bridge, reconciliation, scenarios):
    with xlsxwriter.Workbook(ROOT / "reports/commercial_review.xlsx") as book:
        header = book.add_format({"bold": True, "bg_color": "#17324d", "font_color": "white"})
        money = book.add_format({"num_format": "£#,##0.00;[Red](£#,##0.00)"})
        for name, frame in [
            ("Monthly inputs", monthly),
            ("Products", products),
            ("Customers", customers),
            ("Bridge inputs", bridge),
            ("Cost scenarios", scenarios),
        ]:
            sheet = book.add_worksheet(name)
            for col, name_col in enumerate(frame.columns):
                sheet.write(0, col, name_col, header)
            for rownum, row in enumerate(frame.itertuples(index=False, name=None), 1):
                sheet.write_row(rownum, 0, [None if pd.isna(v) else v for v in row])
            sheet.autofilter(0, 0, len(frame), len(frame.columns) - 1)
            sheet.set_column(0, len(frame.columns) - 1, 23)
            sheet.freeze_panes(1, 1)
        drivers = book.add_worksheet("Assumptions")
        drivers.write_row(0, 0, ["Driver", "Editable value", "Status"], header)
        for rownum, row in enumerate(
            [
                ("Revenue multiplier", 1, "Scenario"),
                ("Cost ratio", 0.6, "ASSUMED; not in source data"),
                ("Fulfilment per order GBP", 3, "ASSUMED; not in source data"),
            ],
            1,
        ):
            drivers.write_row(rownum, 0, row)
        drivers.set_column(0, 2, 30)
        summary = book.add_worksheet("Management model")
        summary.write_row(
            0,
            0,
            [
                "Month",
                "Gross sales",
                "Credits",
                "Adjustments",
                "Net revenue",
                "Orders",
                "Average gross order",
                "Scenario contribution",
            ],
            header,
        )
        for i, r in enumerate(monthly.itertuples(), 1):
            n = i + 1
            summary.write(i, 0, r.month)
            summary.write_formula(
                i, 1, f"='Monthly inputs'!B{n}*Assumptions!$B$2", money, r.gross_product_sales
            )
            summary.write_formula(i, 2, f"='Monthly inputs'!C{n}*Assumptions!$B$2", money, r.credits)
            summary.write_formula(i, 3, f"='Monthly inputs'!D{n}*Assumptions!$B$2", money, r.adjustments)
            summary.write_formula(i, 4, f"=SUM(B{n}:D{n})", money, r.net_revenue)
            summary.write_formula(i, 5, f"='Monthly inputs'!F{n}", None, r.orders)
            summary.write_formula(
                i, 6, f"=IFERROR(B{n}/F{n},0)", money, r.gross_product_sales / r.orders if r.orders else 0
            )
            contribution = r.net_revenue - r.gross_product_sales * 0.6 - r.orders * 3
            summary.write_formula(
                i, 7, f"=E{n}-B{n}*Assumptions!$B$3-F{n}*Assumptions!$B$4", money, contribution
            )
        summary.set_column(0, 7, 23)
        summary.freeze_panes(1, 1)
        chart_obj = book.add_chart({"type": "line"})
        chart_obj.add_series(
            {
                "name": "Net revenue",
                "categories": ["Management model", 1, 0, len(monthly), 0],
                "values": ["Management model", 1, 4, len(monthly), 4],
            }
        )
        summary.insert_chart("J2", chart_obj)
        controls = book.add_worksheet("Controls")
        controls.write_row(0, 0, ["Check", "Difference; must be zero"], header)
        controls.write(1, 0, "Ledger less monthly totals")
        controls.write_number(1, 1, reconciliation["monthly_vs_ledger_difference"], money)
        controls.write(2, 0, "Bridge less net movement")
        controls.write_formula(
            2,
            1,
            f"={reconciliation['bridge']['closing']:.12f}-{reconciliation['bridge']['opening']:.12f}-SUM('Bridge inputs'!B2:B{len(bridge) + 1})",
            money,
            reconciliation["bridge"]["difference"],
        )
        controls.write(4, 0, "Margin figures are scenario estimates, not observed profit")
        controls.set_column(0, 0, 60)


def presentation(metrics, recommendations):
    deck = Presentation()
    deck.slide_width, deck.slide_height = Inches(13.333), Inches(7.5)
    slides = [
        (
            "Revenue Anatomy",
            "Transaction-level commercial review\nPublic historical UK retail data · GBP\n"
            + f"Net classified revenue: £{metrics['net_revenue']:,.0f}",
        ),
        (
            "Can we trust the numbers?",
            f"{metrics['source_rows']:,} source rows; duplicates retained and flagged.\nUnknown-customer sales remain in company totals.\nQuarantined rows and non-product adjustments are reported separately.\nLedger and monthly totals reconcile.",
        ),
        (
            "What changed?",
            f"{metrics['bridge']['before']} → {metrics['bridge']['after']}\nNet change: £{metrics['bridge']['closing'] - metrics['bridge']['opening']:,.0f}\nBridge reconciles price, volume, mix, new/discontinued products and credits.\nDecomposition is descriptive and order-dependent.",
        ),
        (
            "Customer and product exposure",
            f"Top ten known customers: {metrics['top10_known_customer_share']:.1%} of known-customer gross sales.\nUnknown customer gross-sales share: {metrics['unknown_customer_gross_share']:.1%}.\nCohort retention is within-dataset repeat activity, not lifetime retention.",
        ),
        ("Decisions and next evidence", "\n\n".join(recommendations)),
    ]
    for title, body in slides:
        slide = deck.slides.add_slide(deck.slide_layouts[5])
        slide.shapes.title.text = title
        box = slide.shapes.add_textbox(Inches(0.7), Inches(1.6), Inches(11.9), Inches(5.2))
        tf = box.text_frame
        tf.word_wrap = True
        for i, line in enumerate(body.split("\n")):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = line
            p.font.size = Pt(23)
    deck.save(ROOT / "reports/management_review.pptx")


def run(refresh=False, before="2011-10", after="2011-11"):
    data = prepare(refresh)
    fields = [
        "row_id",
        "invoice",
        "product",
        "customer",
        "date",
        "country",
        "quantity",
        "unit_price",
        "amount",
        "is_product",
        "classification",
        "month",
        "duplicate_flag",
    ]
    database = ROOT / "data/processed/revenue.sqlite"
    with sqlite3.connect(database) as con:
        data[fields].to_sql("fact_transactions", con, if_exists="replace", index=False, chunksize=10000)
        data[["product", "description"]].drop_duplicates("product", keep="last").to_sql(
            "dim_product", con, if_exists="replace", index=False
        )
        data[["customer", "country"]].drop_duplicates(["customer", "country"]).to_sql(
            "dim_customer_country", con, if_exists="replace", index=False
        )
        con.executescript((ROOT / "sql/metrics.sql").read_text())
        monthly = pd.read_sql_query("SELECT * FROM monthly_metrics ORDER BY month", con)
        customers = pd.read_sql_query("SELECT * FROM customer_metrics ORDER BY gross_sales DESC", con)
        products = pd.read_sql_query("SELECT * FROM product_metrics ORDER BY gross_sales DESC", con)
    valid = data[data.classification != "quarantine"]
    reconciliation = dict(
        source_amount=float(data.amount.sum()),
        classified_amount=float(valid.amount.sum()),
        quarantined_amount=float(data.loc[data.classification == "quarantine", "amount"].sum()),
        monthly_vs_ledger_difference=float(monthly.net_revenue.sum() - valid.amount.sum()),
        duplicates_policy="retained and flagged, not presumed erroneous",
    )
    if abs(reconciliation["monthly_vs_ledger_difference"]) > 0.01:
        raise ValueError("SQL monthly metrics fail ledger reconciliation")
    bridge, detail = revenue_bridge(data, before, after)
    reconciliation["bridge"] = detail
    cohort = customer_cohorts(data)
    for name, frame in [
        ("monthly_metrics", monthly),
        ("customer_metrics", customers),
        ("product_metrics", products),
        ("revenue_bridge", bridge),
        ("cohort_retention", cohort),
    ]:
        frame.to_csv(ROOT / f"reports/{name}.csv", index=False)
    gross = float(valid.loc[valid.classification == "product_sale", "amount"].sum())
    unknown = float(
        valid.loc[(valid.classification == "product_sale") & (valid.customer == "UNKNOWN"), "amount"].sum()
    )
    complete = monthly[monthly.month < data.date.max().strftime("%Y-%m")]
    metric = dict(
        source_rows=len(data),
        duplicate_flagged_rows=int(data.duplicate_flag.sum()),
        missing_customer_rows=int((data.customer == "UNKNOWN").sum()),
        quarantine_rows=int((data.classification == "quarantine").sum()),
        classification_counts=data.classification.value_counts().to_dict(),
        gross_product_sales=gross,
        net_revenue=float(valid.amount.sum()),
        unknown_customer_gross_share=unknown / gross,
        top10_known_customer_share=float(customers.head(10).gross_sales.sum() / customers.gross_sales.sum()),
        bridge=detail,
        partial_final_month=data.date.max().strftime("%Y-%m"),
        reconciliation=reconciliation,
    )
    scenarios = pd.DataFrame(
        [
            dict(
                assumed_cost_ratio=c,
                assumed_fulfilment_per_order=f,
                scenario_contribution=float(valid.amount.sum() - gross * c - monthly.orders.sum() * f),
            )
            for c in [0.45, 0.6, 0.75]
            for f in [1, 3, 5]
        ]
    )
    scenarios.to_csv(ROOT / "reports/cost_scenarios.csv", index=False)
    dump(ROOT / "reports/reconciliation.json", reconciliation)
    write_workbook(monthly, products, customers, bridge, reconciliation, scenarios)
    recommendations = [
        f"Commercial lead: review the top ten known accounts ({metric['top10_known_customer_share']:.1%} of identified gross sales); track concentration monthly. Unknown IDs prevent a complete customer view.",
        "Operations lead: investigate the largest credited product values and match credits to original orders before attributing them to product quality; track credited value and reason codes.",
        "Finance lead: obtain actual landed product and fulfilment costs before recommending price changes; use the separate cost scenarios to identify conclusions sensitive to margin assumptions.",
    ]
    presentation(metric, recommendations)
    chart(
        px.line(
            complete,
            x="month",
            y=["gross_product_sales", "net_revenue"],
            title="Sales and net revenue — complete calendar months",
        ),
        "monthly_revenue",
    )
    waterfall = go.Figure(
        go.Waterfall(
            x=[before] + bridge.driver.tolist() + [after],
            measure=["absolute"] + ["relative"] * len(bridge) + ["total"],
            y=[detail["opening"]] + bridge.change.tolist() + [0],
        )
    )
    waterfall.update_layout(title="Exact sequential revenue bridge — GBP")
    chart(waterfall, "revenue_bridge")
    report(
        "Revenue Anatomy",
        f"""# Commercial performance review

Source: Chen, D. (2015), UCI Online Retail, DOI 10.24432/C5BW33, CC BY 4.0. Historical UK-based online retailer with international customers. Amounts are GBP. Data contain transactions, not product costs or collections.

The {len(data):,} source rows include {metric["duplicate_flagged_rows"]:,} rows belonging to exact-duplicate groups. They are retained and flagged because repeated invoice lines may be legitimate. Missing customer IDs remain in company totals. Quarantined rows ({metric["quarantine_rows"]}) include negative prices and contradictory cancellation signs; their amount is separately reconciled. Non-product charges and adjustments remain distinct from merchandise sales.

Net classified revenue is GBP {metric["net_revenue"]:,.2f}. SQL monthly totals differ from the classified ledger by GBP {reconciliation["monthly_vs_ledger_difference"]:.8f}. Unknown customer IDs account for {metric["unknown_customer_gross_share"]:.1%} of gross product sales. The top ten known customers contribute {metric["top10_known_customer_share"]:.1%} of identified gross sales; this is not their share of all revenue.

The bridge from {before} to {after} explains GBP {detail["closing"] - detail["opening"]:,.2f} of net movement with a reconciliation difference of GBP {detail["difference"]:.8f}. Shared-product gross sales are decomposed in the documented volume→mix→price order; new/discontinued products, credits and non-product adjustments are separate. Average realized prices reflect discounts and customer mix as well as possible list-price changes. No causal elasticity is inferred.

The final observed month ({metric["partial_final_month"]}) is partial and is excluded from the complete-month trend chart. Cohorts describe observed repeat purchasing, with left-censoring at dataset start and incomplete follow-up for recent cohorts. Seasonality and the short observation window constrain growth conclusions.

"""
        + "\n\n".join(recommendations)
        + "\n\nThe formula-driven Excel model separates observed revenue from assumed costs. Cost scenarios are hypothetical contributions, not observed profit. The accompanying five-slide presentation contains evidence, decisions and limitations.",
        metric,
    )
    return metric
