"""Turn every sheet of LedgerForge_Dataset.xlsx into data/<sheet>.csv (skip if you already have the CSVs).
Usage: python -m scripts.export_csvs path\to\LedgerForge_Dataset.xlsx"""
import sys
from pathlib import Path
import pandas as pd

xlsx = sys.argv[1]
Path("data").mkdir(exist_ok=True)
for name, df in pd.read_excel(xlsx, sheet_name=None).items():
    if name not in ("README", "Sheet1", "data_dictionary"):
        df.to_csv(f"data/{name}.csv", index=False)
        print(name, len(df))
