import pandas as pd
import numpy as np
from scipy.stats import spearmanr
p = r"C:\Users\DELL\Downloads\non_invasive_glucose_estimator-main\non_invasive_glucose_estimator-main\Hb_PPG_Dataset\subject information.xlsx"
df = pd.read_excel(p)
columns = {
    "Age": "Age (year)",
    "Height": "Height (cm)",
    "Weight": "Weight (kg)",
    "Hemoglobin": "Hemoglobin (g/L)",
    "Glucose": "Blood glucose (mmol/L)",
    "SBP": "SBP (mmHg)",
    "DBP": "DBP (mmHg)",
    "Signal length": "Signal length (second)"
}
for label, col in columns.items():
    df[col] = pd.to_numeric(df[col], errors="coerce")
print("\nMISSING VALUES:")
print(df[list(columns.values())].isna().sum())
results = []
for label, col in columns.items():
    if label == "Glucose":
        continue
    valid = df[[col, columns["Glucose"]]].dropna()
    if len(valid) >= 20 and valid[col].nunique() > 1:
        rho, pval = spearmanr(valid[col], valid[columns["Glucose"]])
        results.append([label, rho, pval, len(valid)])
result = pd.DataFrame(
    results,
    columns=["Variable", "Spearman_Rho", "P_Value", "N"]
)
print("\nUPDATED GLUCOSE CORRELATIONS:")
print(result.round(5).to_string(index=False))
result.to_csv("glucosense_metadata_correlations.csv", index=False)
print("\nSaved: glucosense_metadata_correlations.csv")
