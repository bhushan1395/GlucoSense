import numpy as np
import pandas as pd
from sklearn.model_selection import RepeatedKFold
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
excel = r"C:\Users\DELL\Downloads\non_invasive_glucose_estimator-main\non_invasive_glucose_estimator-main\Hb_PPG_Dataset\subject information.xlsx"
meta = pd.read_excel(excel)
quality = pd.read_csv("glucosense_signal_quality_detailed.csv")
meta["ID"] = pd.to_numeric(meta["ID"], errors="coerce")
meta["Blood glucose (mmol/L)"] = pd.to_numeric(
    meta["Blood glucose (mmol/L)"], errors="coerce"
)
df = meta.merge(
    quality,
    left_on="ID",
    right_on="subject_id",
    how="inner"
)
features = [
    "filtered_std",
    "ac_dc_ratio",
    "pulse_interval_cv",
    "baseline_drift_std",
    "pulse_count"
]
df["target"] = df["Blood glucose (mmol/L)"] * 18.018
df = df.replace([np.inf, -np.inf], np.nan)
df = df.dropna(subset=["target"]).reset_index(drop=True)
X = df[features]
y = df["target"].to_numpy()
model = make_pipeline(
    SimpleImputer(strategy="median"),
    StandardScaler(),
    Ridge(alpha=10)
)
cv = RepeatedKFold(n_splits=5, n_repeats=10, random_state=42)
pred_sum = np.zeros(len(df))
counts = np.zeros(len(df))
for train, test in cv.split(X):
    model.fit(X.iloc[train], y[train])
    pred_sum[test] += model.predict(X.iloc[test])
    counts[test] += 1
pred = pred_sum / counts
print("\nOPTICAL ONLY MODEL")
print("Participants:", len(df))
print("MAE:", round(mean_absolute_error(y, pred), 3), "mg/dL")
print("RMSE:", round(np.sqrt(mean_squared_error(y, pred)), 3), "mg/dL")
print("R2:", round(r2_score(y, pred), 4))
pd.DataFrame({
    "actual_glucose": y,
    "predicted_glucose": pred
}).to_csv("glucosense_optical_only_predictions.csv", index=False)
print("\nSaved: glucosense_optical_only_predictions.csv")
print("Research only. Not clinically validated.")
