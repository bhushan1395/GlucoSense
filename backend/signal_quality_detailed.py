import numpy as np
import pandas as pd
from pathlib import Path
from scipy.signal import butter, sosfiltfilt, find_peaks
DATA_DIR = Path(
    r"C:\Users\DELL\Downloads\non_invasive_glucose_estimator-main\non_invasive_glucose_estimator-main\Hb_PPG_Dataset\data_csv"
)
FS = 200
results = []
pulse_filter = butter(
    3, [0.5, 8], btype="bandpass",
    fs=FS, output="sos"
)
baseline_filter = butter(
    2, 0.5, btype="lowpass",
    fs=FS, output="sos"
)
for file in sorted(DATA_DIR.glob("*.csv")):
    try:
        sid = int(file.stem)
        x = pd.read_csv(file)["940nm"].to_numpy(dtype=float)
        if len(x) < FS * 10 or not np.isfinite(x).all():
            continue
        filtered = sosfiltfilt(
            pulse_filter, x - np.mean(x)
        )
        baseline = sosfiltfilt(baseline_filter, x)
        baseline_drift = baseline - np.mean(baseline)
        peaks, _ = find_peaks(
            filtered,
            distance=int(FS * 60 / 180),
            prominence=0.2 * np.std(filtered)
        )
        intervals = np.diff(peaks) / FS
        if len(intervals) >= 3 and np.mean(intervals) > 0:
            interval_cv = np.std(intervals) / np.mean(intervals)
        else:
            interval_cv = np.nan
        raw_mean = abs(np.mean(x))
        ac_dc = np.std(filtered) / raw_mean if raw_mean > 0 else np.nan
        results.append({
            "subject_id": sid,
            "filtered_std": np.std(filtered),
            "ac_dc_ratio": ac_dc,
            "pulse_interval_cv": interval_cv,
            "baseline_drift_std": np.std(baseline_drift),
            "pulse_count": len(peaks)
        })
    except Exception as e:
        print("Skipped:", file.name, str(e))
df = pd.DataFrame(results)
df.to_csv("glucosense_signal_quality_detailed.csv", index=False)
print("\nDETAILED SIGNAL QUALITY")
print("Participants:", len(df))
print("\nSUMMARY:")
print(df.describe().round(4).to_string())
print("\nHIGHEST PULSE INTERVAL VARIABILITY:")
print(df.nlargest(10, "pulse_interval_cv").to_string(index=False))
print("\nLOWEST AC/DC RATIO:")
print(df.nsmallest(10, "ac_dc_ratio").to_string(index=False))
print("\nSaved: glucosense_signal_quality_detailed.csv")
