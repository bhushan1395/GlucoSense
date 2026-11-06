
import numpy as np
import pandas as pd

from pathlib import Path
from scipy.signal import butter, sosfiltfilt, find_peaks, welch
from scipy.stats import skew, kurtosis

# ==========================================
# GLUCOSENSE - Hb-PPG FEATURE EXTRACTION
# ==========================================

BASE = Path(
    r"C:\Users\DELL\Downloads\non_invasive_glucose_estimator-main"
    r"\non_invasive_glucose_estimator-main\Hb_PPG_Dataset"
)

DATA_DIR = BASE / "data_csv"
EXCEL_FILE = BASE / "subject information.xlsx"

OUTPUT = Path("glucosense_features.csv")

FS = 200
CHANNELS = ["660nm", "730nm", "850nm", "940nm"]


def extract_channel_features(signal, name):

    x = np.asarray(signal, dtype=np.float64)
    x = x[np.isfinite(x)]

    if len(x) < FS * 4:
        raise ValueError("Signal too short")

    # Raw optical signal
    raw_mean = np.mean(x)
    raw_std = np.std(x)

    if raw_mean == 0 or raw_std == 0:
        raise ValueError("Invalid or constant signal")

    # Remove DC baseline
    ac = x - raw_mean

    # Bandpass filter: 0.5 to 8 Hz
    sos = butter(
        3,
        [0.5, 8.0],
        btype="bandpass",
        fs=FS,
        output="sos"
    )

    filtered = sosfiltfilt(sos, ac)

    features = {
        f"{name}_raw_mean": raw_mean,
        f"{name}_raw_std": raw_std,
        f"{name}_raw_range": np.ptp(x),

        f"{name}_ac_std": np.std(filtered),
        f"{name}_ac_rms": np.sqrt(np.mean(filtered ** 2)),
        f"{name}_ac_iqr": (
            np.percentile(filtered, 75)
            - np.percentile(filtered, 25)
        ),

        f"{name}_skew": skew(filtered),
        f"{name}_kurtosis": kurtosis(filtered),

        f"{name}_ac_dc_ratio": (
            np.std(filtered) / abs(raw_mean)
        )
    }

    # PPG pulse detection
    distance = int(FS * 60 / 180)

    peaks, _ = find_peaks(
        filtered,
        distance=distance,
        prominence=0.2 * np.std(filtered)
    )

    duration = len(filtered) / FS

    features[f"{name}_peak_count"] = len(peaks)

    features[f"{name}_peak_rate_bpm"] = (
        len(peaks) / duration * 60
    )

    if len(peaks) >= 3:

        intervals = np.diff(peaks) / FS

        features[f"{name}_ibi_mean"] = np.mean(intervals)
        features[f"{name}_ibi_std"] = np.std(intervals)

    else:

        features[f"{name}_ibi_mean"] = np.nan
        features[f"{name}_ibi_std"] = np.nan

    # Frequency-domain feature
    frequencies, power = welch(
        filtered,
        fs=FS,
        nperseg=min(len(filtered), 1024)
    )

    features[f"{name}_dominant_freq"] = frequencies[
        np.argmax(power)
    ]

    features[f"{name}_band_power"] = np.trapz(
        power, frequencies
    )

    return features


def main():

    if not DATA_DIR.exists():
        raise FileNotFoundError(DATA_DIR)

    if not EXCEL_FILE.exists():
        raise FileNotFoundError(EXCEL_FILE)

    metadata = pd.read_excel(EXCEL_FILE)

    metadata["ID"] = pd.to_numeric(
        metadata["ID"], errors="coerce"
    )

    metadata["Blood glucose (mmol/L)"] = pd.to_numeric(
        metadata["Blood glucose (mmol/L)"],
        errors="coerce"
    )

    # Only participants with reference glucose
    metadata = metadata.dropna(
        subset=["ID", "Blood glucose (mmol/L)"]
    ).copy()

    metadata["ID"] = metadata["ID"].astype(int)

    metadata = metadata.drop_duplicates(
        subset=["ID"]
    )

    records = []
    skipped = []

    for _, participant in metadata.iterrows():

        subject_id = int(participant["ID"])

        file = DATA_DIR / f"{subject_id}.csv"

        if not file.exists():
            skipped.append((subject_id, "CSV missing"))
            continue

        try:

            df = pd.read_csv(file)

            if not all(c in df.columns for c in CHANNELS):
                raise ValueError("Unexpected CSV columns")

            if df[CHANNELS].isnull().any().any():
                raise ValueError("Missing signal values")

            features = {}

            # Extract all four wavelength features
            for channel in CHANNELS:

                features.update(
                    extract_channel_features(
                        df[channel].values,
                        channel
                    )
                )

            # Cross-wavelength optical ratios
            features["ratio_660_940"] = (
                features["660nm_raw_mean"]
                / features["940nm_raw_mean"]
            )

            features["ratio_730_850"] = (
                features["730nm_raw_mean"]
                / features["850nm_raw_mean"]
            )

            features["subject_id"] = subject_id

            glucose = float(
                participant["Blood glucose (mmol/L)"]
            )

            features["glucose_mmol_l"] = glucose
            features["glucose_mg_dl"] = glucose * 18.018

            features["signal_duration_sec"] = (
                len(df) / FS
            )

            records.append(features)

        except Exception as error:

            skipped.append((subject_id, str(error)))

    if not records:
        raise RuntimeError("No valid records extracted")

    result = pd.DataFrame(records)

    result = result.replace(
        [np.inf, -np.inf], np.nan
    )

    result.to_csv(OUTPUT, index=False)

    print("\n========== GLUCOSENSE FEATURES ==========")

    print("Valid participants:", len(result))
    print("Skipped participants:", len(skipped))
    print("Feature count:", len(result.columns) - 4)

    print("\nGlucose statistics (mg/dL):")
    print(result["glucose_mg_dl"].describe())

    print("\nMissing feature values:")
    print(result.isna().sum()[result.isna().sum() > 0])

    print("\nSaved:", OUTPUT.resolve())

    if skipped:
        print("\nSkipped records:")
        for item in skipped:
            print(item)


if __name__ == "__main__":
    main()
