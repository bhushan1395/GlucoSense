
import numpy as np
import pandas as pd

from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.feature_selection import SelectKBest, f_regression
from sklearn.preprocessing import StandardScaler
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.svm import SVR
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

df = pd.read_csv("glucosense_features.csv")
df = df.drop_duplicates(subset=["subject_id"]).copy()

y = pd.to_numeric(df["glucose_mg_dl"], errors="coerce")

X = df.drop(
    columns=["glucose_mg_dl", "glucose_mmol_l", "subject_id", "duration_sec"],
    errors="ignore"
)
X = X.select_dtypes(include=[np.number])
X = X.replace([np.inf, -np.inf], np.nan)

valid = y.notna()
X = X.loc[valid].reset_index(drop=True)
y = y.loc[valid].reset_index(drop=True)
groups = df.loc[valid, "subject_id"].reset_index(drop=True)

models = {
    "Mean Baseline": DummyRegressor(strategy="mean"),
    "Random Forest": RandomForestRegressor(
        n_estimators=300, max_features=0.7,
        min_samples_leaf=3, random_state=42, n_jobs=-1
    ),
    "Extra Trees": ExtraTreesRegressor(
        n_estimators=300, max_features=0.7,
        min_samples_leaf=3, random_state=42, n_jobs=-1
    ),
    "SVR": SVR(kernel="rbf", C=10, epsilon=5),
    "Hist Gradient Boosting": HistGradientBoostingRegressor(
        max_iter=100, max_leaf_nodes=7,
        l2_regularization=5, random_state=42
    )
}

cv = GroupKFold(n_splits=5)
results = []
all_predictions = []

print("Participants:", len(X))
print("Features:", X.shape[1])

for name, model in models.items():
    print(f"\nTraining: {name}")
    predictions = np.zeros(len(y))

    for fold, (train_idx, test_idx) in enumerate(
        cv.split(X, y, groups), start=1
    ):
        steps = [
            ("imputer", SimpleImputer(strategy="median"))
        ]

        if name != "Mean Baseline":
            steps.extend([
                ("select", SelectKBest(f_regression, k=10)),
                ("scaler", StandardScaler())
            ])

        steps.append(("model", model))
        pipeline = Pipeline(steps)

        pipeline.fit(X.iloc[train_idx], y.iloc[train_idx])
        predictions[test_idx] = pipeline.predict(X.iloc[test_idx])

        print(f"Fold {fold}/5 completed")

    mae = mean_absolute_error(y, predictions)
    rmse = np.sqrt(mean_squared_error(y, predictions))
    r2 = r2_score(y, predictions)

    print(f"MAE: {mae:.2f} mg/dL")
    print(f"RMSE: {rmse:.2f} mg/dL")
    print(f"R2: {r2:.4f}")

    results.append({
        "model": name, "MAE": mae, "RMSE": rmse, "R2": r2
    })

    for i in range(len(y)):
        all_predictions.append({
            "model": name,
            "subject_id": groups.iloc[i],
            "actual_glucose_mg_dl": y.iloc[i],
            "predicted_glucose_mg_dl": predictions[i]
        })

result_df = pd.DataFrame(results).sort_values("MAE")
result_df.to_csv("glucosense_model_comparison.csv", index=False)

pd.DataFrame(all_predictions).to_csv(
    "glucosense_all_model_predictions.csv", index=False
)

print("\nFINAL COMPARISON")
print(result_df.to_string(index=False))
print("\nBoth CSV files saved successfully.")
print("Research only. Not clinically validated.")
