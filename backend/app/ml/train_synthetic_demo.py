"""Create a clearly synthetic demo-only GlucoSense artifact. Not for medical use."""
from pathlib import Path
import numpy as np, joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer

FEATURES=[f'channel_{i}' for i in range(12)]+['led_850_raw','led_940_raw','pulse_bpm','skin_temp_c']
rng=np.random.default_rng(2026)
n=6000
# Artificial sensor vectors and an arbitrary smooth target relationship for UI/API testing only.
X=rng.uniform(100,30000,size=(n,12))
X[:,3]=rng.uniform(100,20000,n); X[:,4]=rng.uniform(100,20000,n)
extra=np.column_stack([rng.uniform(100,30000,n),rng.uniform(100,30000,n),rng.normal(75,12,n),rng.normal(33,2,n)])
X=np.column_stack([X,extra])
# Synthetic target: deliberately generated, not derived from human glucose measurements.
z=(X[:,12]/30000)*0.35+(X[:,13]/30000)*0.25+(X[:,3]/30000)*0.2+(X[:,4]/30000)*0.2
noise=rng.normal(0,0.025,n)
y=np.clip(75+z*80+noise*20,70,180)
pipe=Pipeline([('imputer',SimpleImputer(strategy='median')),('model',RandomForestRegressor(n_estimators=120,min_samples_leaf=2,random_state=42,n_jobs=-1))])
pipe.fit(X,y)
artifact={'model':pipe,'feature_names':FEATURES,'model_version':'demo-synthetic-1.0','selected_model':'RandomForestRegressor','synthetic_demo':True,'clinical_validation':False,'training_samples':n,'notice':'Synthetic demonstration only. Not trained on real paired sensor/reference glucose data; not for medical use.'}
out=Path(__file__).resolve().parents[2]/'artifacts'/'glucosense_model.joblib'
out.parent.mkdir(parents=True,exist_ok=True); joblib.dump(artifact,out)
print(f'Created {out} ({n} synthetic rows)')
