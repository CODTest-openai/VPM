import pytest

pytest.importorskip("pandas")
pytest.importorskip("numpy")

from vpm_tool.io import load_input_table
from vpm_tool.vpm import run_vpm_analysis


def _assert_tie_out(df, tol=1e-6):
    assert not df.empty
    assert (df["TieOutDiff"].abs() <= tol).all()


def test_monthly_vs_ly_tie_out():
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
    loaded = load_input_table("data/sample_with_exceptions.csv")
    assert len(loaded.exceptions_df) == 2
    reasons = set(loaded.exceptions_df["Exception Reason"].tolist())
    assert "Units Sold < 0" in reasons
    assert "Units Sold == 0 and Revenue != 0" in reasons
