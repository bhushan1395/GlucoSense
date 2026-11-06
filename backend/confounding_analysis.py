import pandas as pd
import numpy as np
from scipy.stats import spearmanr
from pathlib import Path
excel = Path(
    r"C:\Users\DELL\Downloads\non_invasive_glucose_estimator-main\non_invasive_glucose_estimator-main\Hb_PPG_Dataset\subject information.xlsx"
)
df = pd.read_excel(excel)
print("\nAVAILABLE COLUMNS:")
print(df.columns.tolist())
glucose_col = "Blood glucose (mmol/L)"
if glucose_col not in df.columns:
    raise ValueError("Glucose column not found. Check AVAILABLE COLUMNS above.")
df[glucose_col] = pd.to_numeric(df[glucose_col], errors="coerce")
print("\nCONFOUNDING ANALYSIS")
print("Total labelled participants:", df[glucose_col].notna().sum())
results = []
for col in df.select_dtypes(include=np.number).columns:
    if col == glucose_col:
        continue
    valid = df[[col, glucose_col]].replace(
        [np.inf, -np.inf], np.nan
    ).dropna()
    if len(valid) >= 20 and valid[col].nunique() > 1:
        rho, p = spearmanr(valid[col], valid[glucose_col])
        results.append({
            "variable": col,
            "spearman_rho": rho,
            "p_value": p,
            "sample_count": len(valid)
        })
result = pd.DataFrame(results)
if not result.empty:
    result["abs_rho"] = result["spearman_rho"].abs()
    result = result.sort_values("abs_rho", ascending=False)
    print("\nVARIABLES ASSOCIATED WITH GLUCOSE:")
    print(result.drop(columns="abs_rho").round(5).to_string(index=False))
    result.to_csv("glucosense_confounding_analysis.csv", index=False)
    print("\nSaved: glucosense_confounding_analysis.csv")
print("\nGLUCOSE DISTRIBUTION (mg/dL):")
print((df[glucose_col] * 18.018).describe().round(2))
