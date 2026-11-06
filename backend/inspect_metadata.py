
import pandas as pd
from pathlib import Path

file_path = Path(
    r"C:\Users\DELL\Downloads\non_invasive_glucose_estimator-main"
    r"\non_invasive_glucose_estimator-main"
    r"\Hb_PPG_Dataset\subject information.xlsx"
)

print("Loading GlucoSense research dataset...")

if not file_path.exists():
    raise FileNotFoundError(f"Excel file not found: {file_path}")

df = pd.read_excel(file_path)

print("\n========== DATASET INFORMATION ==========")

print("Total participants:", len(df))
print("\nColumns:")
print(df.columns.tolist())

glucose_col = "Blood glucose (mmol/L)"

df[glucose_col] = pd.to_numeric(
    df[glucose_col], errors="coerce"
)

labelled = df.dropna(subset=[glucose_col]).copy()
unlabelled = df[df[glucose_col].isna()].copy()

labelled["glucose_mg_dl"] = (
    labelled[glucose_col] * 18.018
)

print("\n========== LABEL SUMMARY ==========")

print("Labelled participants:", len(labelled))
print("Unlabelled participants:", len(unlabelled))

print("\n========== GLUCOSE STATISTICS ==========")

print(labelled[glucose_col].describe())

print("\n========== PARTICIPANT DATA ==========")

print(
    labelled[
        ["ID", glucose_col, "glucose_mg_dl"]
    ].to_string(index=False)
)

output = Path("labelled_participants.csv")

labelled.to_csv(output, index=False)

print("\nSaved:", output.resolve())
print("\nInspection completed successfully!")
