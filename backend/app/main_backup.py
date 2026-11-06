
import os
import secrets
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Optional

from bson import ObjectId
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Header, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient, DESCENDING

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
# MONGODB CONNECTION
# =========================================================

db = None
client = None

mongo_uri = os.getenv("MONGODB_URI", "").strip()
mongo_db_name = os.getenv("MONGODB_DB", "glucosense").strip()

if not mongo_uri:
    print(f"MongoDB ERROR: MONGODB_URI is missing in {ENV_FILE}")

elif "YOUR_CLUSTER" in mongo_uri:
    print("MongoDB ERROR: Replace the placeholder URI in backend/.env")

else:
    try:
        client = MongoClient(
            mongo_uri,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000
        )

        # Force an actual connection test
        client.admin.command("ping")

        db = client[mongo_db_name]

        # Create indexes
        db.readings.create_index([("timestamp", DESCENDING)])

        db.readings.create_index(
            [("device_id", 1), ("timestamp", DESCENDING)]
        )

        db.model_runs.create_index([("created_at", DESCENDING)])

        print(f"MongoDB connected successfully: {mongo_db_name}")

    except Exception as exc:
        db = None

        if client is not None:
            client.close()
            client = None

        print(
            f"MongoDB connection failed: "
            f"{type(exc).__name__}: {exc}"
        )


# =========================================================
# DATABASE DEPENDENCY
# =========================================================

def get_db():
    if db is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "MongoDB unavailable. Check backend/.env, "
                "Atlas network access, credentials, and backend logs."
            )
        )

    return db


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
    return {
        "status": "ok",
        "database_connected": db is not None,
        "model_available": model_path().exists(),
        "warning": (
            "Experimental prototype only; not for medical use."
        )
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

@app.get("/api/model/status")
def model_status():
    p = model_path()

    return {
        "available": p.exists(),
        "artifact": p.name if p.exists() else None,
        "status": (
            "experimental model available"
            if p.exists()
            else "not trained"
        ),
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
            )
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Prediction failed ({type(exc).__name__}); "
                "check model artifact/features."
            )
        )
