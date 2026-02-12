from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from vpm_tool import export_results, load_input_table, run_vpm_analysis

st.set_page_config(page_title="VPM Analyzer", layout="wide")
st.title("VPM (Volume-Price-Mix) Analysis Tool")

if "loaded" not in st.session_state:
    st.session_state.loaded = None

uploaded = st.file_uploader("Upload source file (CSV or XLSX)", type=["csv", "xlsx"])

if uploaded is not None:
    try:
        loaded = load_input_table(uploaded)
        st.session_state.loaded = loaded
        st.success("File loaded and validated.")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Load failed: {exc}")

if st.session_state.loaded is not None:
    loaded = st.session_state.loaded
    clean_df = loaded.clean_df
    exceptions_df = loaded.exceptions_df

    st.subheader("Dataset summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows (clean)", f"{len(clean_df):,}")
    c2.metric("Rows excluded", f"{len(exceptions_df):,}")
    c3.metric("Business Units", clean_df["Business Unit"].nunique())
    c4.metric("Scenarios", ", ".join(sorted(clean_df["Scenario"].dropna().unique().tolist())))
    ym_min = clean_df[["Year", "Month"]].sort_values(["Year", "Month"]).head(1).iloc[0]
    ym_max = clean_df[["Year", "Month"]].sort_values(["Year", "Month"]).tail(1).iloc[0]
    st.caption(f"Year-Month range: {int(ym_min['Year'])}-{int(ym_min['Month']):02d} to {int(ym_max['Year'])}-{int(ym_max['Month']):02d}")

    st.subheader("Filters")
    col1, col2, col3, col4, col5 = st.columns(5)
    bu = col1.selectbox("Business Unit", sorted(clean_df["Business Unit"].unique().tolist()))
    compare_mode = col2.selectbox("Compare mode", ["vs LY", "vs BUD"])
    period_mode = col3.selectbox("Period mode", ["Single", "Range", "FYTD"])
    fy = col4.selectbox("Fiscal Year", sorted(clean_df["FiscalYear"].unique().tolist()))

    single_month = start_month = end_month = None
    months = list(range(1, 13))
    if period_mode == "Single":
        single_month = col5.selectbox("FiscalMonthIndex", months, index=0)
    elif period_mode == "Range":
        start_month, end_month = st.select_slider(
            "Fiscal month index range", options=months, value=(1, 12)
        )
    else:
        end_month = col5.selectbox("FYTD end FiscalMonthIndex", months, index=11)

    run_clicked = st.button("Run VPM Analysis", type="primary")

    if run_clicked:
        result = run_vpm_analysis(
            clean_df=clean_df,
            exceptions_df=exceptions_df,
            business_unit=bu,
            compare_mode=compare_mode,
            fiscal_year=int(fy),
            period_mode=period_mode,
            single_month=single_month,
            start_month=start_month,
            end_month=end_month,
        )
        st.session_state.result = result
        st.session_state.params = {
            "Business Unit": bu,
            "Compare mode": compare_mode,
            "Period mode": period_mode,
            "FiscalYear": fy,
            "Single Month": single_month,
            "Range Start": start_month,
            "Range End": end_month,
            "Generated": datetime.now().isoformat(timespec="seconds"),
        }

    if "result" in st.session_state:
        result = st.session_state.result
        st.subheader("Category_VPM")
        st.dataframe(result.category_vpm, use_container_width=True)

        tie_out_warning = result.category_vpm["TieOutDiff"].abs().max()
        if tie_out_warning > 1e-6:
            st.warning(f"Tie-out has differences up to {tie_out_warning:.6f}")
        else:
            st.success("Category tie-out check passed.")

        st.subheader("SKU Drilldown")
        categories = ["All"] + sorted(result.sku_vpm["Product Category"].unique().tolist())
        d1, d2, d3 = st.columns(3)
        selected_category = d1.selectbox("Category", categories)
        bucket_filter = d2.multiselect("Bucket", ["Common", "New", "Lost", "Other"], default=["Common", "New", "Lost"])
        top_n = d3.number_input("Top N by |DeltaR| (0=all)", min_value=0, value=20, step=5)

        sku_df = result.sku_vpm.copy()
        if selected_category != "All":
            sku_df = sku_df[sku_df["Product Category"] == selected_category]
        if bucket_filter:
            sku_df = sku_df[sku_df["Bucket"].isin(bucket_filter)]
        if top_n > 0:
            sku_df = sku_df.reindex(sku_df["DeltaR"].abs().sort_values(ascending=False).index).head(int(top_n))

        st.dataframe(sku_df.sort_values("DeltaR", ascending=False), use_container_width=True)

        st.subheader("Export")
        output_dir = Path("exports")
        if st.button("Export bridge-ready Excel"):
            path = export_results(
                output_dir=output_dir,
                result=result,
                exceptions_df=exceptions_df,
                parameters=st.session_state.get("params", {}),
            )
            st.success(f"Export saved to {path}")

        if len(exceptions_df) > 0:
            with st.expander("Exceptions preview"):
                st.dataframe(exceptions_df.head(100), use_container_width=True)
