"""VPM tie-out checks.

Primary execution mode:
    python tests/test_vpm_tieout.py

Also compatible with pytest discovery.
"""

from __future__ import annotations

import sys


def _require_runtime_dependencies() -> None:
    try:
        import pandas  # noqa: F401
        import numpy  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        if "pytest" in sys.modules:
            import pytest

            pytest.skip(
                "Missing runtime dependencies. Install requirements first: pip install -r requirements.txt",
                allow_module_level=False,
            )
        raise RuntimeError(
            "Missing runtime dependencies. Install requirements first: pip install -r requirements.txt"
        ) from exc


def _load_modules():
    from vpm_tool.io import load_input_table
    from vpm_tool.vpm import run_vpm_analysis

    return load_input_table, run_vpm_analysis


def _assert_tie_out(df, tol=1e-6):
    assert not df.empty
    assert (df["TieOutDiff"].abs() <= tol).all()


def test_monthly_vs_ly_tie_out():
    _require_runtime_dependencies()
    load_input_table, run_vpm_analysis = _load_modules()
    loaded = load_input_table("data/sample_main.csv")
    result = run_vpm_analysis(
        clean_df=loaded.clean_df,
        exceptions_df=loaded.exceptions_df,
        business_unit="North",
        compare_mode="vs LY",
        fiscal_year=2026,
        period_mode="Single",
        single_month=1,
    )
    _assert_tie_out(result.category_vpm)


def test_fytd_vs_bud_tie_out():
    _require_runtime_dependencies()
    load_input_table, run_vpm_analysis = _load_modules()
    loaded = load_input_table("data/sample_main.csv")
    result = run_vpm_analysis(
        clean_df=loaded.clean_df,
        exceptions_df=loaded.exceptions_df,
        business_unit="North",
        compare_mode="vs BUD",
        fiscal_year=2026,
        period_mode="FYTD",
        end_month=5,
    )
    _assert_tie_out(result.category_vpm)


def test_exception_rows_excluded_and_logged():
    _require_runtime_dependencies()
    load_input_table, _ = _load_modules()
    loaded = load_input_table("data/sample_with_exceptions.csv")
    assert len(loaded.exceptions_df) == 2
    reasons = set(loaded.exceptions_df["Exception Reason"].tolist())
    assert "Units Sold < 0" in reasons
    assert "Units Sold == 0 and Revenue != 0" in reasons


def main() -> int:
    _require_runtime_dependencies()
    tests = [
        test_monthly_vs_ly_tie_out,
        test_fytd_vs_bud_tie_out,
        test_exception_rows_excluded_and_logged,
    ]
    for test in tests:
        test()
        print(f"PASS: {test.__name__}")
    print("All VPM tie-out checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
