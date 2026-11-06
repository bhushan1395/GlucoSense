
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def main():
    if not DATA_DIR.exists():
        print(f"Data folder not found: {DATA_DIR}")
        print("Create backend/data and put your CSV or Excel file inside.")
        return

    files = [
        p for p in DATA_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not files:
        print("No CSV or Excel file found in backend/data.")
        return

    for path in files:
        print("\n" + "=" * 65)
        print(f"FILE: {path.name}")
        print("=" * 65)

        try:
            if path.suffix.lower() == ".csv":
                df = pd.read_csv(path)
            else:
                df = pd.read_excel(path)

            print(f"\nRows: {len(df)}")
            print(f"Columns: {len(df.columns)}")

            print("\nColumn names and data types:")
            print(df.dtypes.to_string())

            print("\nFirst 5 rows:")
            print(df.head().to_string())

            print("\nMissing values per column:")
            print(df.isna().sum().to_string())

            print("\nDuplicate rows:", int(df.duplicated().sum()))

            numeric = df.select_dtypes(include="number")

            if not numeric.empty:
                print("\nNumeric summary:")
                print(numeric.describe().round(3).to_string())

            print("\nPotential source/label columns:")
            for col in df.columns:
                name = str(col).lower()
                if any(term in name for term in [
                    "source", "device", "subject", "session",
                    "glucose", "timestamp", "time", "label", "target"
                ]):
                    print(f"  {col}: {df[col].head(5).tolist()}")

            print("\nAudit completed. No data was modified.")

        except Exception as exc:
            print(f"Could not inspect {path.name}: {exc}")


if __name__ == "__main__":
    main()
