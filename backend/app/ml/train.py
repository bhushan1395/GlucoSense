"""Train an experimental baseline using MongoDB observations with real reference labels."""
import os, argparse, warnings, json
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd, joblib
from dotenv import load_dotenv
from pymongo import MongoClient
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.model_selection import train_test_split, GroupShuffleSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer

FEATURES=[f"channel_{i}" for i in range(12)]+["led_850_raw","led_940_raw","pulse_bpm","skin_temp_c"]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--min-samples",type=int,default=100)
    parser.add_argument("--test-size",type=float,default=.2)
    args=parser.parse_args()
    load_dotenv()
    uri=os.getenv("MONGODB_URI","")
    if not uri or "YOUR_CLUSTER" in uri: raise SystemExit("Configure MONGODB_URI in backend/.env.")
    client=MongoClient(uri,serverSelectionTimeoutMS=5000)
    db=client[os.getenv("MONGODB_DB","glucosense")]
    docs=list(db.readings.find({"reference_glucose_mg_dl":{"$type":"number"}}))
    if len(docs)<args.min_samples:
        raise SystemExit(f"Only {len(docs)} labeled records; need at least {args.min_samples}. This is a software guardrail, not a clinical sample-size recommendation.")
    rows=[]
    for d in docs:
        ch=d.get("channels") or []
        row={f"channel_{i}":float(ch[i]) if i<len(ch) else np.nan for i in range(12)}
        for k in ("led_850_raw","led_940_raw","pulse_bpm","skin_temp_c"): row[k]=d.get(k,np.nan)
        row["target"]=float(d["reference_glucose_mg_dl"])
        row["participant_code"]=d.get("participant_code")
        rows.append(row)
    df=pd.DataFrame(rows); X=df[FEATURES].replace([np.inf,-np.inf],np.nan); y=df.target
    valid=y.notna() & X.notna().any(axis=1); X=X.loc[valid]; y=y.loc[valid]; df=df.loc[valid]
    groups=df.participant_code.fillna("").astype(str)
    if groups.nunique()>1 and (groups!="").all():
        splitter=GroupShuffleSplit(n_splits=1,test_size=args.test_size,random_state=42)
        train_idx,test_idx=next(splitter.split(X,y,groups)); split_type="participant_group_holdout"
    else:
        warnings.warn("Participant codes missing/not diverse: random holdout may leak repeated-person patterns.")
        train_idx,test_idx=train_test_split(np.arange(len(X)),test_size=args.test_size,random_state=42)
        split_type="random_holdout_not_clinically_validated"
    candidates={"ExtraTrees":ExtraTreesRegressor(n_estimators=300,min_samples_leaf=3,random_state=42,n_jobs=-1),
                "RandomForest":RandomForestRegressor(n_estimators=300,min_samples_leaf=3,random_state=42,n_jobs=-1),
                "HistGradientBoosting":HistGradientBoostingRegressor(max_iter=200,l2_regularization=1.0,random_state=42)}
    reports={}; best=None
    for name,est in candidates.items():
        pipe=Pipeline([("imputer",SimpleImputer(strategy="median")),("model",est)])
        pipe.fit(X.iloc[train_idx],y.iloc[train_idx]); pred=pipe.predict(X.iloc[test_idx])
        m={"MAE_mg_dl":float(mean_absolute_error(y.iloc[test_idx],pred)),
           "RMSE_mg_dl":float(mean_squared_error(y.iloc[test_idx],pred)**.5),
           "R2":float(r2_score(y.iloc[test_idx],pred)),"test_samples":int(len(test_idx))}
        reports[name]=m
        if best is None or m["MAE_mg_dl"]<best[0]: best=(m["MAE_mg_dl"],name,pipe)
    best[2].fit(X,y)
    artifact={"model":best[2],"feature_names":FEATURES,"model_version":"0.1.0",
              "selected_model":best[1],"evaluation":reports,"split_type":split_type,
              "trained_at_utc":datetime.now(timezone.utc).isoformat(),
              "training_samples":int(len(X)),"clinical_validation":False}
    out=Path(os.getenv("MODEL_PATH","artifacts/glucosense_model.joblib"))
    if not out.is_absolute(): out=Path(__file__).resolve().parents[2]/out
    out.parent.mkdir(parents=True,exist_ok=True); joblib.dump(artifact,out)
    db.model_runs.insert_one({"created_at":datetime.now(timezone.utc),"selected_model":best[1],
        "evaluation":reports,"split_type":split_type,"training_samples":int(len(X)),
        "test_samples":int(len(test_idx)),"clinical_validation":False,
        "notice":"Experimental only; metrics do not establish clinical accuracy."})
    print(json.dumps({"artifact":str(out),"selected_model":best[1],"split_type":split_type,
                      "training_samples":len(X),"evaluation":reports,"clinical_validation":False},indent=2))
    client.close()
if __name__=="__main__": main()
