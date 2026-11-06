
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"

for path in DATA_DIR.iterdir():
    if path.suffix.lower() not in {".csv", ".xlsx", ".xls"}:
        continue

    df = (
        pd.read_csv(path)
        if path.suffix.lower() == ".csv"
        else pd.read_excel(path)
    )

    print(f"\nFILE: {path.name}")
    print("Rows:", len(df))
    print("\nSource distribution:")
    print(
        df["source"].value_counts(dropna=False).to_string()
        if "source" in df.columns
        else "No source column"
    )

    for col in [
        "nir", "vis", "red", "ir",
        "objectTempC", "ambientTempC"
    ]:
        if col in df.columns:
            values = pd.to_numeric(df[col], errors="coerce")
            print(
                f"{col}: min={values.min()}, "
                f"max={values.max()}, "
                f"unique={values.nunique()}, "
                f"zeros={(values == 0).sum()}"
            )

    print("\nSample records:")
    print(df.head(3).to_string(index=False))
