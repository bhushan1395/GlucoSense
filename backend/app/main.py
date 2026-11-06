
import os
import secrets
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Optional
import csv
import io
import statistics
import math
from fastapi.responses import StreamingResponse

from bson import ObjectId
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient, DESCENDING
from urllib.parse import quote_plus, urlsplit, urlunsplit

from .schemas import ReadingIn, ReferenceIn


# =========================================================
# ENVIRONMENT CONFIGURATION
# =========================================================

BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"

load_dotenv(ENV_FILE, override=True)

app = FastAPI(
    title="GlucoSense API",
    version="0.1.0",
    description="Experimental research prototype; not for medical use."
)


# =========================================================
# CORS CONFIGURATION
# =========================================================

origins = [
    x.strip()
    for x in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if x.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"]
)


# =========================================================
# MONGODB CONNECTION (LAZY + AUTO-RECONNECT)
# =========================================================

db = None
client = None
mongo_db_name = os.getenv("MONGODB_DB", "glucosense").strip() or "glucosense"


def _get_mongodb_uri():
    """
    Prefer separate credentials when supplied. This avoids URI parsing errors
    when a MongoDB password contains characters such as @, :, /, # or %.
    Existing MONGODB_URI configuration remains supported unchanged.
    """
    load_dotenv(ENV_FILE, override=True)

    username = os.getenv("MONGODB_USERNAME", "").strip()
    password = os.getenv("MONGODB_PASSWORD", "")
    cluster_host = os.getenv("MONGODB_CLUSTER_HOST", "").strip()

    if username and password and cluster_host:
        encoded_user = quote_plus(username)
        encoded_password = quote_plus(password)
        return (
            f"mongodb+srv://{encoded_user}:{encoded_password}@{cluster_host}/"
            "?retryWrites=true&w=majority&appName=GlucoSense"
        )

    uri = os.getenv("MONGODB_URI", "").strip()
    if not uri or "<db_password>" in uri or "YOUR_CLUSTER" in uri:
        raise RuntimeError(
            "MongoDB configuration missing. Set MONGODB_URI, or set "
            "MONGODB_USERNAME, MONGODB_PASSWORD and MONGODB_CLUSTER_HOST "
            "in backend/.env."
        )
    return uri


def connect_mongodb():
    """Connect on demand and retry after transient Atlas/network failures."""
    global client, db, mongo_db_name

    load_dotenv(ENV_FILE, override=True)
    mongo_db_name = os.getenv("MONGODB_DB", "glucosense").strip() or "glucosense"
    mongo_uri = _get_mongodb_uri()

    if client is not None and db is not None:
        try:
            client.admin.command("ping")
            return db
        except Exception:
            try:
                client.close()
            except Exception:
                pass
            client = None
            db = None

    last_error = None
    for attempt in range(1, 3):
        candidate = None
        try:
            candidate = MongoClient(
                mongo_uri,
                serverSelectionTimeoutMS=8000,
                connectTimeoutMS=8000,
                socketTimeoutMS=10000,
                retryReads=True,
                retryWrites=True,
                appName="GlucoSense-FastAPI"
            )
            candidate.admin.command("ping")
            database = candidate[mongo_db_name]

            database.readings.create_index([("timestamp", DESCENDING)])
            database.readings.create_index([("device_id", 1), ("timestamp", DESCENDING)])
            database.model_runs.create_index([("created_at", DESCENDING)])
            database.calibrations.create_index([("device_id", 1), ("created_at", DESCENDING)])
            database.research_sessions.create_index([("device_id", 1), ("started_at", DESCENDING)])

            client = candidate
            db = database
            print(f"MongoDB connected successfully; database selected: {mongo_db_name}")
            return db
        except Exception as exc:
            last_error = exc
            if candidate is not None:
                try:
                    candidate.close()
                except Exception:
                    pass

    # Do not print the URI or credentials in logs.
    print(f"MongoDB connection failed ({type(last_error).__name__}): {last_error}")
    raise RuntimeError(
        "MongoDB Atlas connection failed. Verify the Atlas database username/password, "
        "cluster hostname, database user authentication database, and IP access list. "
        "The existing database and collections are not modified by this failure."
    )


def get_db():
    """Reconnect per request rather than leaving db=None after a startup failure."""
    try:
        return connect_mongodb()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"MongoDB unavailable ({type(exc).__name__}). Check backend console; existing data is not deleted."
        )


@app.on_event("startup")
def startup_mongodb_check():
    # FastAPI still starts if Atlas is offline; database routes retry later.
    try:
        connect_mongodb()
    except Exception as exc:
        print(f"Startup: MongoDB not ready; will retry on API requests ({type(exc).__name__}).")


# =========================================================
# DEVICE AUTHENTICATION
# =========================================================

def verify_device(
    x_device_key: Optional[str] = Header(default=None)
):
    expected = os.getenv("DEVICE_API_KEY", "")

    if (
        not expected
        or expected == "replace-with-a-long-random-secret"
    ):
        raise HTTPException(
            status_code=503,
            detail="Set a strong DEVICE_API_KEY in backend/.env."
        )

    if not x_device_key or not secrets.compare_digest(
        x_device_key, expected
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid device API key."
        )


# =========================================================
# SERIALIZATION
# =========================================================

def serialise(doc):
    if doc is None:
        return None

    doc["_id"] = str(doc["_id"])

    for key in (
        "timestamp",
        "created_at",
        "reference_measured_at",
        "reference_added_at"
    ):
        if isinstance(doc.get(key), datetime):
            doc[key] = doc[key].isoformat()

    # Do not expose participant codes in API responses
    doc.pop("participant_code", None)

    return doc


# =========================================================
# MODEL PATH
# =========================================================

def model_path():
    p = Path(
        os.getenv(
            "MODEL_PATH",
            "artifacts/glucosense_model.joblib"
        )
    )

    return (
        p if p.is_absolute()
        else BACKEND_DIR / p
    )


# =========================================================
# TIMESTAMPS
# =========================================================

def add_timestamps(doc):
    """Store UTC timestamps and additional IST ISO strings."""

    ist = ZoneInfo("Asia/Kolkata")

    timestamp = doc.get("timestamp")

    if timestamp is None:
        timestamp = datetime.now(timezone.utc)

    elif timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    else:
        timestamp = timestamp.astimezone(timezone.utc)

    created_at = datetime.now(timezone.utc)

    doc["timestamp"] = timestamp
    doc["created_at"] = created_at

    doc["timestamp_ist"] = timestamp.astimezone(ist).isoformat()
    doc["created_at_ist"] = created_at.astimezone(ist).isoformat()


# =========================================================
# SAVE READING
# =========================================================

def save_reading(payload, database, source):
    doc = payload.model_dump()

    if doc.get("reference_glucose_mg_dl") is not None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Attach reference labels through the reference endpoint "
                "after a real reference measurement."
            )
        )

    add_timestamps(doc)
    doc["source"] = source

    # Attach transparent engineering quality flags at ingestion time.
    # The helper is defined in the additive research section below.
    quality = assess_reading_quality(doc)
    doc["signal_quality"] = quality["label"]
    doc.setdefault("metadata", {})["quality_assessment"] = quality

    result = database.readings.insert_one(doc)

    saved_doc = database.readings.find_one(
        {"_id": result.inserted_id}
    )

    return serialise(saved_doc)


# =========================================================
# ROOT AND HEALTH
# =========================================================

@app.get("/")
def root():
    return {
        "service": "GlucoSense API",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
def health():
    database_connected = False
    if client is not None:
        try:
            client.admin.command("ping")
            database_connected = True
        except Exception:
            database_connected = False

    return {
        "status": "ok",
        "database_connected": database_connected,
        "model_available": model_path().exists(),
        "warning": "Experimental prototype only; not for medical use."
    }


# =========================================================
# READINGS API
# =========================================================

@app.get("/api/readings")
def get_readings(
    limit: int = Query(100, ge=1, le=500),
    database=Depends(get_db)
):
    return [
        serialise(x)
        for x in database.readings.find(
            {},
            {"participant_code": 0}
        ).sort("timestamp", DESCENDING).limit(limit)
    ]


@app.get("/api/readings/latest")
def get_latest(database=Depends(get_db)):
    doc = database.readings.find_one(
        {},
        {"participant_code": 0},
        sort=[("timestamp", DESCENDING)]
    )

    return serialise(doc) if doc else None


@app.post(
    "/api/readings",
    dependencies=[Depends(verify_device)]
)
def create_reading(
    payload: ReadingIn,
    database=Depends(get_db)
):
    return save_reading(payload, database, "device")


@app.post("/api/readings/dashboard")
def create_dashboard_reading(
    payload: ReadingIn,
    database=Depends(get_db)
):
    """Save a user-requested dashboard snapshot."""
    return save_reading(payload, database, "dashboard")


# =========================================================
# REFERENCE GLUCOSE API
# =========================================================

@app.post(
    "/api/readings/{reading_id}/reference",
    dependencies=[Depends(verify_device)]
)
def add_reference(
    reading_id: str,
    payload: ReferenceIn,
    database=Depends(get_db)
):
    try:
        oid = ObjectId(reading_id)

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid reading ID."
        )

    if not database.readings.find_one({"_id": oid}):
        raise HTTPException(
            status_code=404,
            detail="Reading not found."
        )

    database.readings.update_one(
        {"_id": oid},
        {
            "$set": {
                "reference_glucose_mg_dl":
                    payload.reference_glucose_mg_dl,
                "reference_method": payload.reference_method,
                "reference_measured_at": payload.measured_at,
                "reference_notes": payload.notes,
                "reference_added_at": datetime.now(timezone.utc)
            }
        }
    )

    return {
        "ok": True,
        "message": (
            "Reference label attached. Verify timing/session "
            "quality before training."
        )
    }


# =========================================================
# MODEL STATUS AND METRICS
# =========================================================

def _artifact_is_synthetic(path):
    try:
        import joblib
        return bool(joblib.load(path).get("synthetic_demo", False))
    except Exception:
        return False


@app.get("/api/model/status")
def model_status():
    p = model_path()

    return {
        "available": p.exists(),
        "artifact": p.name if p.exists() else None,
        "status": (
            "synthetic demo model available" if p.exists() and _artifact_is_synthetic(p)
            else "experimental model available" if p.exists()
            else "not trained"
        ),
        "synthetic_demo": _artifact_is_synthetic(p) if p.exists() else False,
        "notice": (
            "Artifact availability does not imply clinical validation."
        )
    }


@app.get("/api/model/metrics")
def model_metrics(database=Depends(get_db)):
    doc = database.model_runs.find_one(
        {},
        sort=[("created_at", DESCENDING)]
    )

    return serialise(doc) if doc else None


# =========================================================
# EXPERIMENTAL PREDICTION
# =========================================================

@app.post("/api/predict")
def predict(payload: ReadingIn):
    p = model_path()

    if not p.exists():
        return {
            "prediction_available": False,
            "reason": "No trained model artifact found.",
            "experimental": True,
            "medical_use": False
        }

    try:
        import joblib
        import pandas as pd

        artifact = joblib.load(p)
        row = {}

        for i in range(12):
            row[f"channel_{i}"] = (
                payload.channels[i]
                if i < len(payload.channels)
                else None
            )

        for key in (
            "led_850_raw",
            "led_940_raw",
            "pulse_bpm",
            "skin_temp_c"
        ):
            row[key] = getattr(payload, key)

        X = pd.DataFrame(
            [[row.get(k) for k in artifact["feature_names"]]],
            columns=artifact["feature_names"]
        )

        pred = float(artifact["model"].predict(X)[0])

        if not 20 <= pred <= 700:
            return {
                "prediction_available": False,
                "reason": (
                    "Prediction outside configured bounds; withheld."
                ),
                "experimental": True,
                "medical_use": False
            }

        return {
            "prediction_available": True,
            "estimated_glucose_mg_dl": round(pred, 1),
            "experimental": True,
            "medical_use": False,
            "notice": (
                "Research estimate only. Not a glucose measurement "
                "and not for clinical decisions."
            ),
            "model_version": artifact.get(
                "model_version", "unknown"
            ),
            "synthetic_demo": bool(artifact.get("synthetic_demo", False)),
            "prediction_type": "SYNTHETIC DEMO - NOT A REAL GLUCOSE ESTIMATE" if artifact.get("synthetic_demo", False) else "experimental research estimate"
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Prediction failed ({type(exc).__name__}); "
                "check model artifact/features."
            )
        )


# =========================================================
# GLUCOSENSE RESEARCH PIPELINE (ADDITIVE; EXISTING ROUTES KEPT)
# =========================================================

def assess_reading_quality(doc):
    """Snapshot-level optical checks only; not a clinical or motion-quality score."""
    values = [float(x) for x in (doc.get("channels") or [])]
    flags = []
    if len(values) < 12:
        flags.append("fewer_than_12_channels")
    if not values or all(v == 0 for v in values):
        flags.append("all_channels_zero")
    if values and any(v >= 65000 for v in values):
        flags.append("possible_sensor_saturation")
    if values and max(values) - min(values) <= 1:
        flags.append("channels_nearly_identical")
    for key in ("led_850_raw", "led_940_raw"):
        value = doc.get(key)
        if value is None:
            flags.append(f"{key}_missing")
        elif not isinstance(value, (int, float)) or value < 0:
            flags.append(f"{key}_invalid")

    # This score is a transparent engineering heuristic, not a validated metric.
    score = 100
    score -= 20 if "fewer_than_12_channels" in flags else 0
    score -= 35 if "all_channels_zero" in flags else 0
    score -= 25 if "possible_sensor_saturation" in flags else 0
    score -= 10 if "channels_nearly_identical" in flags else 0
    score -= 5 if "led_850_raw_missing" in flags else 0
    score -= 5 if "led_940_raw_missing" in flags else 0
    score = max(0, score)
    label = "good" if score >= 85 else "fair" if score >= 65 else "poor"
    return {
        "score": score,
        "label": label,
        "flags": flags,
        "method": "snapshot_heuristic_v1",
        "limitations": [
            "No temporal waveform or motion assessment from a single snapshot",
            "Not a glucose accuracy metric",
            "Not clinically validated"
        ]
    }


def _numeric(values):
    return [float(v) for v in values if isinstance(v, (int, float)) and math.isfinite(float(v))]


def _mean(values):
    vals = _numeric(values)
    return float(sum(vals) / len(vals)) if vals else None


def build_research_features(readings):
    """One aggregate feature row per session (or per reading if session_id is absent)."""
    groups = {}
    for doc in readings:
        key = doc.get("session_id") or f"reading:{doc.get('_id')}"
        groups.setdefault(key, []).append(doc)

    output = []
    for session_id, docs in groups.items():
        docs = sorted(docs, key=lambda d: d.get("timestamp") or datetime.min.replace(tzinfo=timezone.utc))
        channel_count = max([len(d.get("channels") or []) for d in docs] or [0])
        row = {
            "session_id": session_id,
            "device_id": docs[-1].get("device_id"),
            "n_readings": len(docs),
            "quality_good_fraction": (
                sum(1 for d in docs if d.get("signal_quality") == "good") / len(docs)
                if docs else None
            ),
            "led_850_mean": _mean([d.get("led_850_raw") for d in docs]),
            "led_940_mean": _mean([d.get("led_940_raw") for d in docs]),
            "pulse_bpm_mean": _mean([d.get("pulse_bpm") for d in docs]),
            "skin_temp_c_mean": _mean([d.get("skin_temp_c") for d in docs]),
            "object_temp_c_mean": _mean([d.get("object_temp_c") for d in docs]),
            "ambient_temp_c_mean": _mean([d.get("ambient_temp_c") for d in docs]),
            "reference_glucose_mg_dl": next(
                (d.get("reference_glucose_mg_dl") for d in docs
                 if d.get("reference_glucose_mg_dl") is not None), None
            ),
            "label_source": next(
                (d.get("reference_method") for d in docs if d.get("reference_method")), None
            )
        }
        for i in range(channel_count):
            vals = _numeric([
                (d.get("channels") or [])[i]
                for d in docs if len(d.get("channels") or []) > i
            ])
            row[f"channel_{i+1}_mean"] = _mean(vals)
            row[f"channel_{i+1}_std"] = (
                float(statistics.pstdev(vals)) if len(vals) > 1 else 0.0 if vals else None
            )
        if row["led_940_mean"] not in (None, 0) and row["led_850_mean"] is not None:
            row["led_850_940_ratio"] = row["led_850_mean"] / row["led_940_mean"]
        else:
            row["led_850_940_ratio"] = None
        output.append(row)
    return output


@app.post("/api/research/sessions/start", dependencies=[Depends(verify_device)])
def start_research_session(payload: dict, database=Depends(get_db)):
    device_id = str(payload.get("device_id", "")).strip()
    session_id = str(payload.get("session_id", "")).strip()
    if not device_id or not session_id:
        raise HTTPException(status_code=422, detail="device_id and session_id are required.")
    now = datetime.now(timezone.utc)
    doc = {
        "device_id": device_id,
        "session_id": session_id,
        "started_at": now,
        "status": "active",
        "metadata": payload.get("metadata", {}),
        "notice": "Research data only; not a glucose measurement."
    }
    database.research_sessions.update_one(
        {"device_id": device_id, "session_id": session_id},
        {"$setOnInsert": doc},
        upsert=True
    )
    return {"ok": True, "device_id": device_id, "session_id": session_id, "status": "active"}


@app.post("/api/research/sessions/{session_id}/stop", dependencies=[Depends(verify_device)])
def stop_research_session(session_id: str, payload: dict, database=Depends(get_db)):
    device_id = str(payload.get("device_id", "")).strip()
    result = database.research_sessions.update_one(
        {"device_id": device_id, "session_id": session_id, "status": "active"},
        {"$set": {"status": "completed", "ended_at": datetime.now(timezone.utc)}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Active session not found.")
    return {"ok": True, "status": "completed"}


@app.get("/api/research/sessions")
def list_research_sessions(
    device_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    database=Depends(get_db)
):
    query = {"device_id": device_id} if device_id else {}
    docs = database.research_sessions.find(query).sort("started_at", DESCENDING).limit(limit)
    return [serialise(x) for x in docs]


@app.get("/api/research/quality")
def research_quality(
    device_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    database=Depends(get_db)
):
    query = {"device_id": device_id} if device_id else {}
    docs = list(database.readings.find(query).sort("timestamp", DESCENDING).limit(limit))
    assessments = [assess_reading_quality(d) for d in docs]
    counts = {"good": 0, "fair": 0, "poor": 0}
    for item in assessments:
        counts[item["label"]] += 1
    return {
        "count": len(assessments),
        "quality_counts": counts,
        "latest": assessments[0] if assessments else None,
        "notice": "Engineering snapshot checks only; not a clinical or glucose-quality score."
    }


@app.post("/api/calibration/baseline", dependencies=[Depends(verify_device)])
def capture_optical_baseline(payload: dict, database=Depends(get_db)):
    """Capture an optical baseline from recent readings; this is NOT glucose calibration."""
    device_id = str(payload.get("device_id", "")).strip()
    session_id = payload.get("session_id")
    sample_count = int(payload.get("sample_count", 10))
    if not device_id:
        raise HTTPException(status_code=422, detail="device_id is required.")
    if sample_count < 3 or sample_count > 100:
        raise HTTPException(status_code=422, detail="sample_count must be between 3 and 100.")

    query = {"device_id": device_id}
    if session_id:
        query["session_id"] = session_id
    docs = list(database.readings.find(query).sort("timestamp", DESCENDING).limit(sample_count))
    docs = [d for d in docs if len(d.get("channels") or []) >= 12]
    if len(docs) < 3:
        raise HTTPException(status_code=400, detail="At least 3 valid readings are required.")

    channel_means = []
    for i in range(12):
        channel_means.append(_mean([(d.get("channels") or [])[i] for d in docs]))
    baseline = {
        "device_id": device_id,
        "session_id": session_id,
        "created_at": datetime.now(timezone.utc),
        "sample_count": len(docs),
        "channels_mean": channel_means,
        "led_850_mean": _mean([d.get("led_850_raw") for d in docs]),
        "led_940_mean": _mean([d.get("led_940_raw") for d in docs]),
        "calibration_type": "optical_baseline_only",
        "glucose_calibration": False,
        "notice": "Baseline normalization only. No reference glucose was measured."
    }
    result = database.calibrations.insert_one(baseline)
    baseline["_id"] = str(result.inserted_id)
    baseline["created_at"] = baseline["created_at"].isoformat()
    return baseline


@app.get("/api/calibration/latest")
def latest_optical_baseline(device_id: str, database=Depends(get_db)):
    doc = database.calibrations.find_one(
        {"device_id": device_id}, sort=[("created_at", DESCENDING)]
    )
    return serialise(doc) if doc else None


@app.get("/api/research/features")
def get_research_features(
    device_id: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = Query(5000, ge=1, le=20000),
    database=Depends(get_db)
):
    query = {}
    if device_id:
        query["device_id"] = device_id
    if session_id:
        query["session_id"] = session_id
    docs = list(database.readings.find(query).sort("timestamp", DESCENDING).limit(limit))
    features = build_research_features(docs)
    return {
        "count": len(features),
        "features": features,
        "notice": "Descriptive research features only. No glucose estimate is produced."
    }


@app.get("/api/research/export.csv")
def export_research_csv(
    device_id: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = Query(5000, ge=1, le=20000),
    database=Depends(get_db)
):
    query = {}
    if device_id:
        query["device_id"] = device_id
    if session_id:
        query["session_id"] = session_id
    docs = list(database.readings.find(query).sort("timestamp", DESCENDING).limit(limit))
    rows = build_research_features(docs)
    if not rows:
        raise HTTPException(status_code=404, detail="No research readings found.")
    buffer = io.StringIO()
    fieldnames = sorted({key for row in rows for key in row.keys()})
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=glucosense_research_features.csv"}
    )


@app.get("/api/research/notice")
def research_notice():
    return {
        "data_type": "experimental optical telemetry",
        "glucose_measurement": False,
        "clinical_validation": False,
        "reference_glucometer_available": False,
        "message": "Do not use this prototype for diagnosis, treatment, medication, or glucose decisions."
    }
