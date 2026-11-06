import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import RepeatedKFold
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
excel = Path(
    r"C:\Users\DELL\Downloads\non_invasive_glucose_estimator-main\non_invasive_glucose_estimator-main\Hb_PPG_Dataset\subject information.xlsx"
)
meta = pd.read_excel(excel)
quality = pd.read_csv("glucosense_signal_quality_detailed.csv")
meta["ID"] = pd.to_numeric(meta["ID"], errors="coerce")
meta["Blood glucose (mmol/L)"] = pd.to_numeric(
    meta["Blood glucose (mmol/L)"], errors="coerce"
)
covariates = [
    "Age (year)",
    "SBP (mmHg)",
    "DBP (mmHg)",
    "Hemoglobin (g/L)",
    "Signal length (second)"
]
optical = [
    "filtered_std",
    "ac_dc_ratio",
    "pulse_interval_cv",
    "baseline_drift_std",
    "pulse_count"
]
for col in covariates:
    meta[col] = pd.to_numeric(meta[col], errors="coerce")
df = meta.merge(
    quality,
    left_on="ID",
    right_on="subject_id",
    how="inner"
)
df["target"] = df["Blood glucose (mmol/L)"] * 18.018
# Same participants for all model comparisons
df = df.replace([np.inf, -np.inf], np.nan)
df = df.dropna(subset=["target"] + covariates).reset_index(drop=True)
X_meta = df[covariates]
X_combined = df[covariates + optical]
y = df["target"].to_numpy()
print("\nINCREMENTAL OPTICAL VALUE TEST")
print("Participants:", len(df))
print("Metadata predictors:", covariates)
print("Optical predictors:", optical)
models = {
    "Mean Baseline": None,
    "Metadata Only": make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        Ridge(alpha=10)
    ),
    "Metadata + Optical": make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        Ridge(alpha=10)
    )
}
cv = RepeatedKFold(
    n_splits=5,
    n_repeats=10,
    random_state=42
)
predictions = {
    name: np.zeros(len(df))
    for name in models
}
counts = np.zeros(len(df))
for train_idx, test_idx in cv.split(X_meta):
    counts[test_idx] += 1
    train_mean = y[train_idx].mean()
    predictions["Mean Baseline"][test_idx] += train_mean
    models["Metadata Only"].fit(
        X_meta.iloc[train_idx], y[train_idx]
    )
    predictions["Metadata Only"][test_idx] += (
        models["Metadata Only"].predict(X_meta.iloc[test_idx])
    )
    models["Metadata + Optical"].fit(
        X_combined.iloc[train_idx], y[train_idx]
    )
    predictions["Metadata + Optical"][test_idx] += (
        models["Metadata + Optical"].predict(X_combined.iloc[test_idx])
    )
rows = []
for name, pred_sum in predictions.items():
    pred = pred_sum / counts
    rows.append({
        "model": name,
        "MAE_mg_dl": mean_absolute_error(y, pred),
        "RMSE_mg_dl": np.sqrt(mean_squared_error(y, pred)),
        "R2": r2_score(y, pred)
    })
results = pd.DataFrame(rows)
print("\nCROSS-VALIDATION RESULTS:")
print(results.round(4).to_string(index=False))
results.to_csv(
    "glucosense_incremental_value_results.csv",
    index=False
)
print("\nSaved: glucosense_incremental_value_results.csv")
print("Repeated 5-fold CV, 10 repeats.")
print("Research-only; not clinically validated.")
