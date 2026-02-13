from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from .vpm import VPMResult


def export_results(
    output_dir: str | Path,
    result: VPMResult,
    exceptions_df: pd.DataFrame,
    parameters: dict,
    filename: str | None = None,
) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_name = filename or f"vpm_export_{stamp}.xlsx"
    path = output_dir / out_name

    params_df = pd.DataFrame(
        [{"Parameter": k, "Value": v} for k, v in {**parameters, "timestamp": stamp, "excluded_rows": len(exceptions_df)}.items()]
    )

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        params_df.to_excel(writer, index=False, sheet_name="Parameters")
        result.category_vpm.to_excel(writer, index=False, sheet_name="Category_VPM")
        result.sku_vpm.to_excel(writer, index=False, sheet_name="SKU_VPM")
        result.bridge_category.to_excel(writer, index=False, sheet_name="Bridge_Category")
        exceptions_df.to_excel(writer, index=False, sheet_name="Exceptions")

    return path
