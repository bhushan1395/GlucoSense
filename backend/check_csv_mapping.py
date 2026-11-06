
import pandas as pd
from pathlib import Path

# Dataset location
DATA_DIR = Path(
    r"C:\Users\DELL\Downloads\non_invasive_glucose_estimator-main"
    r"\non_invasive_glucose_estimator-main"
    r"\Hb_PPG_Dataset\data_csv"
)

LABEL_FILE = Path("labelled_participants.csv")

if not DATA_DIR.exists():
    raise FileNotFoundError(f"CSV folder not found: {DATA_DIR}")

if not LABEL_FILE.exists():
    raise FileNotFoundError("labelled_participants.csv not found")

labels = pd.read_csv(LABEL_FILE)

# Get CSV filenames
csv_files = list(DATA_DIR.glob("*.csv"))

csv_ids = set()

for file in csv_files:
    try:
        csv_ids.add(int(file.stem))
    except ValueError:
        print("Non-numeric filename:", file.name)

label_ids = set(labels["ID"].astype(int))

matched = label_ids.intersection(csv_ids)
missing = label_ids - csv_ids

print("\n========== CSV MAPPING REPORT ==========")
print("Total CSV files:", len(csv_files))
print("Labelled participants:", len(label_ids))
print("Matched participants:", len(matched))
print("Missing signal files:", len(missing))

print("\nMissing IDs:", sorted(missing)[:30])

# Inspect one matched signal file
if matched:
    sample_id = sorted(matched)[0]
    sample_file = DATA_DIR / f"{sample_id}.csv"

    signal = pd.read_csv(sample_file)

    print("\n========== SAMPLE SIGNAL ==========")
    print("File:", sample_file.name)
    print("Shape:", signal.shape)
    print("Columns:", signal.columns.tolist())
    print("\nFirst five rows:")
    print(signal.head())

print("\nMapping inspection completed.")
