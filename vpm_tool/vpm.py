from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

CompareMode = Literal["vs LY", "vs BUD"]
PeriodMode = Literal["Single", "Range", "FYTD"]


@dataclass
class VPMResult:
    category_vpm: pd.DataFrame
    sku_vpm: pd.DataFrame
    bridge_category: pd.DataFrame
    current_rows: int
    base_rows: int


def _period_window(period_mode: PeriodMode, single: int | None = None, start: int | None = None, end: int | None = None):
    if period_mode == "Single":
        if single is None:
            raise ValueError("single month index is required for Single mode")
        return single, single
    if period_mode == "Range":
        if start is None or end is None:
            raise ValueError("start and end are required for Range mode")
        if start > end:
            raise ValueError("Range start must be <= end")
        return start, end
    if period_mode == "FYTD":
        if end is None:
            raise ValueError("end month index is required for FYTD mode")
        return 1, end
    raise ValueError(f"Unsupported period mode: {period_mode}")


def _safe_div(numerator, denominator):
    if denominator is None or denominator == 0:
        return np.nan
    return numerator / denominator


def _build_period_data(
    clean_df: pd.DataFrame,
    business_unit: str,
    compare_mode: CompareMode,
    fiscal_year: int,
    period_mode: PeriodMode,
    single: int | None = None,
    start: int | None = None,
    end: int | None = None,
):
    start_idx, end_idx = _period_window(period_mode, single, start, end)
    in_window = clean_df["FiscalMonthIndex"].between(start_idx, end_idx)
    bu = clean_df["Business Unit"] == business_unit

    current = clean_df.loc[
        bu
        & (clean_df["Scenario"] == "ACT")
        & (clean_df["FiscalYear"] == fiscal_year)
        & in_window
    ].copy()

    if compare_mode == "vs LY":
        base = clean_df.loc[
            bu
            & (clean_df["Scenario"] == "ACT")
            & (clean_df["FiscalYear"] == fiscal_year - 1)
            & in_window
        ].copy()
    else:
        base = clean_df.loc[
            bu
            & (clean_df["Scenario"] == "BUD")
            & (clean_df["FiscalYear"] == fiscal_year)
            & in_window
        ].copy()

    return current, base, start_idx, end_idx


def run_vpm_analysis(
    clean_df: pd.DataFrame,
    exceptions_df: pd.DataFrame,
    business_unit: str,
    compare_mode: CompareMode,
    fiscal_year: int,
    period_mode: PeriodMode,
    single_month: int | None = None,
    start_month: int | None = None,
    end_month: int | None = None,
) -> VPMResult:
    current, base, _, _ = _build_period_data(
        clean_df,
        business_unit,
        compare_mode,
        fiscal_year,
        period_mode,
        single=single_month,
        start=start_month,
        end=end_month,
    )

    keys = ["Business Unit", "Product Category", "Sku Code", "Sku Name"]

    g0 = (
        base.groupby(keys, dropna=False, as_index=False)
        .agg(U0=("Units Sold", "sum"), R0=("Revenue", "sum"))
    )
    g1 = (
        current.groupby(keys, dropna=False, as_index=False)
        .agg(U1=("Units Sold", "sum"), R1=("Revenue", "sum"))
    )

    sku = pd.merge(g0, g1, on=keys, how="outer").fillna({"U0": 0.0, "R0": 0.0, "U1": 0.0, "R1": 0.0})
    sku["P0"] = sku.apply(lambda r: _safe_div(r["R0"], r["U0"]), axis=1)
    sku["P1"] = sku.apply(lambda r: _safe_div(r["R1"], r["U1"]), axis=1)

    sku["Bucket"] = np.select(
        [
            (sku["U0"] > 0) & (sku["U1"] > 0),
            (sku["U0"] <= 0) & (sku["U1"] > 0),
            (sku["U0"] > 0) & (sku["U1"] <= 0),
        ],
        ["Common", "New", "Lost"],
        default="Other",
    )

    sku["VOL"] = np.where(sku["Bucket"] == "Common", (sku["U1"] - sku["U0"]) * sku["P0"], 0.0)
    sku["PRI"] = np.where(sku["Bucket"] == "Common", sku["U1"] * (sku["P1"] - sku["P0"]), 0.0)
    sku["NEW"] = np.where(sku["Bucket"] == "New", sku["R1"], 0.0)
    sku["LST"] = np.where(sku["Bucket"] == "Lost", -sku["R0"], 0.0)
    sku["MIX"] = 0.0

    common = sku.loc[sku["Bucket"] == "Common"].copy()
    if not common.empty:
        common_totals = (
            common.groupby(["Business Unit", "Product Category"], as_index=False)
            .agg(U0_cat=("U0", "sum"), U1_cat=("U1", "sum"), R0_cat=("R0", "sum"))
        )
        common = common.merge(common_totals, on=["Business Unit", "Product Category"], how="left")
        common["P0_cat"] = common.apply(lambda r: _safe_div(r["R0_cat"], r["U0_cat"]), axis=1)
        common["S0"] = common.apply(lambda r: _safe_div(r["U0"], r["U0_cat"]), axis=1)
        common["S1"] = common.apply(lambda r: _safe_div(r["U1"], r["U1_cat"]), axis=1)
        common["MIX"] = (common["S1"] - common["S0"]) * common["U1_cat"] * (common["P0"] - common["P0_cat"])
        sku = sku.drop(columns=["MIX"]).merge(common[keys + ["MIX"]], on=keys, how="left")
        sku["MIX"] = sku["MIX"].fillna(0.0)

    sku["DeltaR"] = sku["R1"] - sku["R0"]

    cat = (
        sku.groupby(["Business Unit", "Product Category"], as_index=False)
        .agg(
            R0=("R0", "sum"),
            R1=("R1", "sum"),
            VOL=("VOL", "sum"),
            PRI=("PRI", "sum"),
            MIX=("MIX", "sum"),
            NEW=("NEW", "sum"),
            LST=("LST", "sum"),
            CommonSKUs=("Bucket", lambda s: int((s == "Common").sum())),
            NewSKUs=("Bucket", lambda s: int((s == "New").sum())),
            LostSKUs=("Bucket", lambda s: int((s == "Lost").sum())),
        )
    )
    cat["DeltaR"] = cat["R1"] - cat["R0"]
    cat["CalcDelta"] = cat[["VOL", "PRI", "MIX", "NEW", "LST"]].sum(axis=1)
    cat["TieOutDiff"] = cat["DeltaR"] - cat["CalcDelta"]
    cat["%DeltaR"] = np.where(cat["R0"] != 0, cat["DeltaR"] / cat["R0"], np.nan)

    if len(exceptions_df) > 0:
        exc_counts = (
            exceptions_df.loc[exceptions_df["Business Unit"] == business_unit]
            .groupby("Product Category")
            .size()
            .rename("#ExceptionRows")
            .reset_index()
        )
    else:
        exc_counts = pd.DataFrame(columns=["Product Category", "#ExceptionRows"])

    cat = cat.merge(exc_counts, on="Product Category", how="left")
    cat["#ExceptionRows"] = cat["#ExceptionRows"].fillna(0).astype(int)
    cat = cat.rename(columns={"CommonSKUs": "#CommonSKUs", "NewSKUs": "#NewSKUs", "LostSKUs": "#LostSKUs"})

    bridge = cat.melt(
        id_vars=["Business Unit", "Product Category"],
        value_vars=["VOL", "PRI", "MIX", "NEW", "LST"],
        var_name="Component",
        value_name="Value",
    )
    bridge["Component"] = bridge["Component"].replace(
        {"VOL": "Volume", "PRI": "Price", "MIX": "Mix", "NEW": "New", "LST": "Lost"}
    )

    sku_cols = keys + ["Bucket", "U0", "R0", "P0", "U1", "R1", "P1", "DeltaR", "VOL", "PRI", "MIX", "NEW", "LST"]
    cat_cols = [
        "Business Unit",
        "Product Category",
        "R0",
        "R1",
        "DeltaR",
        "VOL",
        "PRI",
        "MIX",
        "NEW",
        "LST",
        "%DeltaR",
        "#CommonSKUs",
        "#NewSKUs",
        "#LostSKUs",
        "#ExceptionRows",
        "TieOutDiff",
    ]

    return VPMResult(
        category_vpm=cat[cat_cols].sort_values("DeltaR", ascending=False).reset_index(drop=True),
        sku_vpm=sku[sku_cols].sort_values("DeltaR", ascending=False).reset_index(drop=True),
        bridge_category=bridge.sort_values(["Product Category", "Component"]).reset_index(drop=True),
        current_rows=len(current),
        base_rows=len(base),
    )
