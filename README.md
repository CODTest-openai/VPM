# Local VPM (Volume-Price-Mix) Analysis Tool

Streamlit-based local tool for FMCG revenue management that computes Volume/Price/Mix decomposition with fiscal year support (FY starts in March), category outputs, SKU drilldown, and Excel export.

## Features
- Upload one long-format CSV/XLSX table with ACT/BUD data.
- Fiscal logic:
  - `FiscalYear = Year if Month >= 3 else Year - 1`
  - `FiscalMonthIndex = Month - 2 if Month >= 3 else Month + 10`
- Compare modes:
  - ACT vs LY
  - ACT vs BUD
- Period modes:
  - Single month
  - Range
  - FYTD (start fixed at fiscal month index 1)
- VPM decomposition:
  - SKU-level base/current aggregation
  - Bucketization: Common / New / Lost
  - Category-level MIX via share-shift on Common SKUs only
- Exception policy (excluded + logged):
  - `Units Sold < 0`
  - `Units Sold == 0 and Revenue != 0`
- Excel export with bridge-ready sheets.

## Project structure

```text
.
├── app.py
├── requirements.txt
├── README.md
├── data/
│   ├── sample_main.csv
│   └── sample_with_exceptions.csv
├── tests/
│   └── test_vpm_tieout.py
├── exports/
└── vpm_tool/
    ├── __init__.py
    ├── io.py
    ├── vpm.py
    └── export.py
```

## Input data contract
Required columns:
- Business Unit
- Year
- Month
- Product Category
- Sku Code
- Sku Name
- Scenario (ACT or BUD)
- Units Sold
- Revenue

## Run on Windows (exact steps)
1. Open **PowerShell** in the repo folder.
2. Create venv:
   ```powershell
   py -m venv .venv
   ```
3. Activate venv:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```
4. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
5. Start app:
   ```powershell
   streamlit run app.py
   ```
6. In the app:
   - Upload `data/sample_main.csv` or your own file.
   - Set filters and run analysis.
   - Click **Export bridge-ready Excel**.

## Export location
Exports are written to:
- `exports/vpm_export_YYYYMMDD_HHMMSS.xlsx`

Sheets in export:
1. `Parameters`
2. `Category_VPM`
3. `SKU_VPM` (all categories)
4. `Bridge_Category`
5. `Exceptions`

## Run tests
From repo root:
```bash
pytest -q
```

Tests include tie-out assertions for:
- Monthly vs LY (`FY=2026`, fiscal month index `1`)
- FYTD vs BUD (`FY=2026`, end fiscal month index `5`)
- Exception row detection and logging
