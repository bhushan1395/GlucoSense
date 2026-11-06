import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold, GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.feature_selection import VarianceThreshold, SelectKBest, f_regression
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
# Load dataset from current backend folder
df = pd.read_csv("glucosense_features.csv")
TARGET = "glucose_mg_dl"
GROUP = "subject_id"
if TARGET not in df.columns or GROUP not in df.columns:
    raise ValueError(f"Missing required columns: {df.columns.tolist()}")
df = df.drop_duplicates(subset=[GROUP]).copy()
y = pd.to_numeric(df[TARGET], errors="coerce")
X = df.drop(
    columns=[TARGET, "glucose_mmol_l", GROUP, "duration_sec"],
    errors="ignore"
)
X = X.select_dtypes(include=[np.number])
X = X.replace([np.inf, -np.inf], np.nan)
valid = y.notna()
X = X.loc[valid].reset_index(drop=True)
y = y.loc[valid].reset_index(drop=True)
groups = df.loc[valid, GROUP].reset_index(drop=True)
print("\n========== DATASET ==========")
print("Participants:", len(X))
print("Features:", X.shape[1])
if len(X) < 20:
    raise ValueError("Not enough participants for cross-validation")
outer_cv = GroupKFold(n_splits=5)
predictions = np.zeros(len(y))
baseline_predictions = np.zeros(len(y))
pipeline = Pipeline([
    ("imputer", SimpleImputer(strategy="median")),
    ("variance", VarianceThreshold()),
    ("select", SelectKBest(score_func=f_regression)),
    ("scaler", StandardScaler()),
    ("model", Ridge())
])
parameters = {
    "select__k": [5, 10, 15, "all"],
    "model__alpha": [0.1, 1, 10, 100]
}
for fold, (train_idx, test_idx) in enumerate(
    outer_cv.split(X, y, groups), start=1
):
    X_train = X.iloc[train_idx]
    X_test = X.iloc[test_idx]
    y_train = y.iloc[train_idx]
    y_test = y.iloc[test_idx]
    train_groups = groups.iloc[train_idx]
    baseline = DummyRegressor(strategy="mean")
    baseline.fit(X_train, y_train)
    baseline_predictions[test_idx] = baseline.predict(X_test)
    inner_cv = GroupKFold(n_splits=4)
    search = GridSearchCV(
        pipeline,
        parameters,
        scoring="neg_mean_absolute_error",
        cv=inner_cv,
        n_jobs=-1
    )
    search.fit(X_train, y_train, groups=train_groups)
    predictions[test_idx] = search.predict(X_test)
    print(f"Fold {fold}/5 completed")
    print("Best parameters:", search.best_params_)
def evaluate(name, actual, predicted):
    mae = mean_absolute_error(actual, predicted)
    rmse = np.sqrt(mean_squared_error(actual, predicted))
    r2 = r2_score(actual, predicted)
    print(f"\n{name}")
    print(f"MAE:  {mae:.2f} mg/dL")
    print(f"RMSE: {rmse:.2f} mg/dL")
    print(f"R2:   {r2:.4f}")
    return {
        "model": name,
        "MAE": mae,
        "RMSE": rmse,
        "R2": r2
    }
print("\n========== MODEL RESULTS ==========")
results = [
    evaluate("Mean Baseline", y, baseline_predictions),
    evaluate("Ridge Regression", y, predictions)
]
pd.DataFrame(results).to_csv(
    "glucosense_model_evaluation.csv", index=False
)
pd.DataFrame({
    "subject_id": groups,
    "actual_glucose_mg_dl": y,
    "predicted_glucose_mg_dl": predictions
}).to_csv("glucosense_oof_predictions.csv", index=False)
print("\nFiles saved successfully:")
print("1. glucosense_model_evaluation.csv")
print("2. glucosense_oof_predictions.csv")
print("\nResearch-only evaluation. Not clinically validated.")
