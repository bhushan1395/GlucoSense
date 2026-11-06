import pandas as pd
import numpy as np
from scipy.stats import rankdata, t
excel = r"C:\Users\DELL\Downloads\non_invasive_glucose_estimator-main\non_invasive_glucose_estimator-main\Hb_PPG_Dataset\subject information.xlsx"
meta = pd.read_excel(excel)
quality = pd.read_csv("glucosense_signal_quality_detailed.csv")
meta["ID"] = pd.to_numeric(meta["ID"], errors="coerce")
meta["Blood glucose (mmol/L)"] = pd.to_numeric(
    meta["Blood glucose (mmol/L)"], errors="coerce"
)
for col in [
    "Age (year)", "SBP (mmHg)", "DBP (mmHg)",
    "Signal length (second)", "Height (cm)", "Weight (kg)"
]:
    meta[col] = pd.to_numeric(meta[col], errors="coerce")
df = meta.merge(
    quality,
    left_on="ID",
    right_on="subject_id",
    how="inner"
)
df["glucose_mg_dl"] = df["Blood glucose (mmol/L)"] * 18.018
metrics = [
    "filtered_std",
    "ac_dc_ratio",
    "pulse_interval_cv",
    "baseline_drift_std",
    "pulse_count"
]
def adjusted_spearman(data, feature, target, covariates):
    cols = [feature, target] + covariates
    d = data[cols].replace([np.inf, -np.inf], np.nan).dropna()
    n = len(d)
    k = len(covariates)
    if n <= k + 3:
        return n, np.nan, np.nan
    # Rank-transform feature, target and confounders
    x = rankdata(d[feature])
    y = rankdata(d[target])
    Z = np.column_stack([
        np.ones(n)
    ] + [rankdata(d[c]) for c in covariates])
    rx = x - Z @ np.linalg.lstsq(Z, x, rcond=None)[0]
    ry = y - Z @ np.linalg.lstsq(Z, y, rcond=None)[0]
    r = np.corrcoef(rx, ry)[0, 1]
    dfree = n - k - 2
    if not np.isfinite(r) or abs(r) >= 1:
        return n, r, np.nan
    statistic = r * np.sqrt(dfree / (1 - r**2))
    pvalue = 2 * t.sf(abs(statistic), dfree)
    return n, r, pvalue
adjustments = {
    "Age + BP + Signal length": [
        "Age (year)", "SBP (mmHg)",
        "DBP (mmHg)", "Signal length (second)"
    ],
    "Age + BP + Height + Weight": [
        "Age (year)", "SBP (mmHg)",
        "DBP (mmHg)", "Height (cm)", "Weight (kg)"
    ]
}
rows = []
for label, covars in adjustments.items():
    for feature in metrics:
        n, rho, pvalue = adjusted_spearman(
            df, feature, "glucose_mg_dl", covars
        )
        rows.append({
            "adjustment": label,
            "signal_metric": feature,
            "N": n,
            "adjusted_partial_spearman": rho,
            "p_value": pvalue
        })
result = pd.DataFrame(rows)
print("\nADJUSTED SIGNAL-GLUCOSE ANALYSIS")
print(result.round(5).to_string(index=False))
result.to_csv(
    "glucosense_adjusted_correlations.csv",
    index=False
)
print("\nSaved: glucosense_adjusted_correlations.csv")
print("Exploratory analysis only; not clinical validation.")
