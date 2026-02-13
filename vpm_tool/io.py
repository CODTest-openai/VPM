from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

REQUIRED_COLUMNS = [
    "Business Unit",
    "Year",
    "Month",
    "Product Category",
    "Sku Code",
    "Sku Name",
    "Scenario",
    "Units Sold",
    "Revenue",
]


@dataclass
class LoadedInput:
    clean_df: pd.DataFrame
    exceptions_df: pd.DataFrame


def _normalize_scenario(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.upper()


def validate_columns(df: pd.DataFrame, required_columns: Iterable[str] = REQUIRED_COLUMNS) -> list[str]:
    missing = [c for c in required_columns if c not in df.columns]
    return missing


def add_derived_fields(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["FiscalYear"] = out["Year"].where(out["Month"] >= 3, out["Year"] - 1)
    out["FiscalMonthIndex"] = out["Month"].where(out["Month"] < 3, out["Month"] - 2)
    out.loc[out["Month"] < 3, "FiscalMonthIndex"] = out.loc[out["Month"] < 3, "Month"] + 10
    out["FiscalMonthIndex"] = out["FiscalMonthIndex"].astype(int)
    out["Scenario"] = _normalize_scenario(out["Scenario"])
    out["UnitPrice"] = out["Revenue"] / out["Units Sold"]
    out.loc[out["Units Sold"] == 0, "UnitPrice"] = pd.NA
    return out


def split_exceptions(df: pd.DataFrame) -> LoadedInput:
    out = df.copy()
    reason = pd.Series(pd.NA, index=out.index, dtype="object")
    reason.loc[out["Units Sold"] < 0] = "Units Sold < 0"
    reason.loc[(out["Units Sold"] == 0) & (out["Revenue"] != 0)] = "Units Sold == 0 and Revenue != 0"

    exceptions = out.loc[reason.notna()].copy()
    exceptions["Exception Reason"] = reason.loc[exceptions.index]

    clean = out.loc[reason.isna()].copy()
    return LoadedInput(clean_df=clean, exceptions_df=exceptions)


def load_input_table(path_or_buffer) -> LoadedInput:
    if hasattr(path_or_buffer, "name") and str(path_or_buffer.name).lower().endswith(".xlsx"):
        df = pd.read_excel(path_or_buffer)
    elif isinstance(path_or_buffer, str) and path_or_buffer.lower().endswith(".xlsx"):
        df = pd.read_excel(path_or_buffer)
    else:
        df = pd.read_csv(path_or_buffer)

    missing = validate_columns(df)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    for col in ["Year", "Month", "Units Sold", "Revenue"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if df[["Year", "Month", "Units Sold", "Revenue"]].isna().any().any():
        bad_cols = df[["Year", "Month", "Units Sold", "Revenue"]].columns[
            df[["Year", "Month", "Units Sold", "Revenue"]].isna().any()
        ].tolist()
        raise ValueError(f"Numeric conversion failed for columns: {bad_cols}")

    df["Year"] = df["Year"].astype(int)
    df["Month"] = df["Month"].astype(int)
    df = add_derived_fields(df)
    return split_exceptions(df)
