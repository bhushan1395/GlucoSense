import numpy as np
import pandas as pd
from pathlib import Path
from scipy.signal import butter, sosfiltfilt, find_peaks
DATA_DIR = Path(
    r"C:\Users\DELL\Downloads\non_invasive_glucose_estimator-main\non_invasive_glucose_estimator-main\Hb_PPG_Dataset\data_csv"
)
FS = 200
CHANNEL = "940nm"
sos = butter(
    3, [0.5, 8],
    btype="bandpass",
    fs=FS,
    output="sos"
)
results = []
for file in sorted(DATA_DIR.glob("*.csv")):
    try:
        sid = int(file.stem)
        x = pd.read_csv(file)[CHANNEL].to_numpy(dtype=float)
        if len(x) < FS * 10 or not np.isfinite(x).all():
            continue
        raw_std = np.std(x)
        raw_range = np.ptp(x)
        filtered = sosfiltfilt(sos, x - np.mean(x))
        peaks, _ = find_peaks(
            filtered,
            distance=int(FS * 60 / 180),
            prominence=0.2 * np.std(filtered)
        )
        bpm = len(peaks) / (len(x) / FS) * 60
        # Compare slow baseline variation with pulse signal
        slow_sos = butter(
            2, 0.5,
            btype="lowpass",
            fs=FS,
            output="sos"
        )
        baseline = sosfiltfilt(slow_sos, x)
        baseline_std = np.std(baseline)
        results.append({
            "subject_id": sid,
            "raw_std": raw_std,
            "raw_range": raw_range,
            "filtered_std": np.std(filtered),
            "pulse_count": len(peaks),
            "estimated_bpm": bpm,
            "baseline_std": baseline_std,
            "duration_sec": len(x) / FS
        })
    except Exception as e:
        print("Skipped:", file.name, str(e))
df = pd.DataFrame(results)
df.to_csv("glucosense_signal_quality.csv", index=False)
print("\nSIGNAL QUALITY ANALYSIS")
print("Participants:", len(df))
print("\nSUMMARY:")
print(df.describe().round(2).to_string())
print("\nLOWEST 10 FILTERED AMPLITUDE:")
print(df.nsmallest(10, "filtered_std").to_string(index=False))
print("\nHIGHEST 10 RAW RANGE:")
print(df.nlargest(10, "raw_range").to_string(index=False))
print("\nSaved: glucosense_signal_quality.csv")
print("Research signal diagnostics only.")
