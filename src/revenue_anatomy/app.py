import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from .core import revenue_bridge
from .io import ROOT, require, theme


@st.cache_data
def transactions():
    return pd.read_parquet(ROOT / "data/processed/transactions.parquet")


def main():
    theme("Revenue Anatomy", "Traceable commercial metrics, customer exposure, and revenue drivers")
    require(ROOT / "reports/metrics.json", "revenue-anatomy run")
    require(ROOT / "data/processed/transactions.parquet", "revenue-anatomy run")
    st.caption("UCI Online Retail · historical UK retailer · GBP · actual revenue, assumed cost scenarios")
    data = transactions()
    monthly = pd.read_csv(ROOT / "reports/monthly_metrics.csv")
    complete = monthly[monthly.month < data.date.max().strftime("%Y-%m")]
    cols = st.columns(3)
    cols[0].metric("Net classified revenue", f"£{monthly.net_revenue.sum():,.0f}")
    cols[1].metric("Gross product sales", f"£{monthly.gross_product_sales.sum():,.0f}")
    cols[2].metric(
        "Unidentified gross sales",
        f"{monthly.unidentified_gross_sales.sum() / monthly.gross_product_sales.sum():.1%}",
    )
    tabs = st.tabs(["Performance", "Revenue bridge", "Customers", "Products and credits", "Cost scenarios"])
    with tabs[0]:
        st.plotly_chart(
            px.line(complete, x="month", y=["gross_product_sales", "net_revenue"]), width="stretch"
        )
        st.caption(
            "Partial final month excluded from trend. Full source totals remain in the headline metrics."
        )
        st.dataframe(monthly, hide_index=True)
    with tabs[1]:
        periods = complete.month.tolist()
        before = st.selectbox("Earlier month", periods, index=periods.index("2011-10"))
        after = st.selectbox("Later month", periods, index=periods.index("2011-11"))
        bridge, check = revenue_bridge(data, before, after)
        fig = go.Figure(
            go.Waterfall(
                x=[before] + bridge.driver.tolist() + [after],
                measure=["absolute"] + ["relative"] * len(bridge) + ["total"],
                y=[check["opening"]] + bridge.change.tolist() + [0],
            )
        )
        st.plotly_chart(fig, width="stretch")
        st.caption(
            f"Bridge reconciliation difference: £{check['difference']:.8f}. Descriptive volume→mix→price order."
        )
        st.dataframe(bridge, hide_index=True)
    with tabs[2]:
        customers = pd.read_csv(ROOT / "reports/customer_metrics.csv")
        st.dataframe(customers.head(100), hide_index=True)
        cohorts = pd.read_csv(ROOT / "reports/cohort_retention.csv")
        st.plotly_chart(
            px.imshow(
                cohorts.pivot(index="cohort", columns="month", values="retention"),
                color_continuous_scale="Teal",
                title="Observed repeat purchasing by first-observed cohort",
            ),
            width="stretch",
        )
    with tabs[3]:
        products = pd.read_csv(ROOT / "reports/product_metrics.csv")
        minimum = st.number_input("Minimum gross product sales", min_value=0.0, value=1000.0)
        products = products[products.gross_sales >= minimum].copy()
        products["credited_value_ratio"] = products.credited_value / products.gross_sales
        st.dataframe(products.sort_values("credited_value", ascending=False), hide_index=True)
        st.caption(
            "Credits need matching to original orders and reason codes before drawing quality conclusions."
        )
    with tabs[4]:
        cost = st.slider("Assumed product cost / gross sales", 0.2, 0.9, 0.6, 0.01)
        fulfilment = st.slider("Assumed fulfilment / order GBP", 0.0, 10.0, 3.0, 0.5)
        contribution = (
            monthly.net_revenue.sum()
            - monthly.gross_product_sales.sum() * cost
            - monthly.orders.sum() * fulfilment
        )
        st.metric("Hypothetical contribution", f"£{contribution:,.0f}")
        st.caption("Costs are absent from the source. This is a sensitivity scenario, not observed profit.")
    st.download_button(
        "Download Excel management model",
        (ROOT / "reports/commercial_review.xlsx").read_bytes(),
        "commercial_review.xlsx",
    )
    st.download_button(
        "Download management slides",
        (ROOT / "reports/management_review.pptx").read_bytes(),
        "management_review.pptx",
    )
