# GlucoSense Red Research Dashboard

React + Vite dashboard for your ESP32 sensor API. Updated with a red/black theme inspired by the supplied reference screenshots and functional navigation, saved-reading history, CSV export, ESP32 IP settings, and local signal-baseline capture.

## Run on Windows / VS Code
1. Extract `GlucoSense_Red_Theme_Dashboard.zip`.
2. Open the `glucosense-dashboard` folder in VS Code.
3. Open Terminal > New Terminal in that folder.
4. Run:
   ```powershell
   npm install
   npm run dev
   ```
5. Open the local URL printed by Vite, usually `http://localhost:5173`.
6. If needed, open System Settings and enter the IP address shown in Arduino Serial Monitor.

## ESP32 API
The dashboard polls `http://<ESP32-IP>/api/data` once per second. The ESP32 endpoint should return JSON and include `Access-Control-Allow-Origin: *` to allow browser access.

Recognized optional fields:
- `channels`: array of AS7343 raw counts
- `nir`, `vis`: optional mapped spectral values
- `red`, `ir`: MAX30102 raw optical counts
- `objectTempC`, `ambientTempC`: MLX90614 temperatures
- `adcRaw`, `adcVolts`: arrays of ADS1115 readings
- `as7343Ready`, `max30102Ready`, `mlx90614Ready`, `ads1115Ready`: booleans indicating module status

If the ESP32 firmware doesn't send the `*Ready` flags, the UI infers status from available data where possible. For the best module-health status, add explicit readiness flags in the ESP32 JSON response.

## Button behavior
- Sidebar navigation switches between Dashboard, History Log, Spectrometry, Photodiode, Research Notes, and System Settings.
- Save reading stores a local snapshot in this browser's localStorage.
- Export CSV downloads saved readings, or recent live samples if none have been saved.
- Clear history deletes locally saved snapshots.
- Capture baseline stores current raw values locally for comparison only; it is not glucose calibration.
- System Settings applies a new ESP32 IP and reconnects the polling loop.

## Important scientific limitation
This dashboard deliberately does not generate a glucose value, confidence score, or clinical result. Raw AS7343/MAX30102 optical readings are not blood glucose measurements. Any future glucose model requires suitable reference measurements and independent validation before accuracy or clinical claims.
