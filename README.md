# GlucoSense
### Experimental Non-Invasive Glucose Monitoring Research Prototype

GlucoSense is an experimental research prototype exploring optical and physiological signals for non-invasive glucose estimation. The software stack includes a React + Vite dashboard, a FastAPI backend, MongoDB persistence, and an ML model artifact.

> **Research and safety notice:** GlucoSense is not a medical device. It has not been clinically validated and must not be used for diagnosis, treatment decisions, insulin dosing, or replacing a certified glucose meter. Optical sensor readings are not direct blood-glucose measurements.

## Repository structure

```text
GlucoSense/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── schemas.py
│   │   └── ml/
│   │       └── train.py
│   ├── artifacts/
│   │   └── glucosense_model.joblib
│   ├── requirements.txt
│   └── .env.example
├── firmware/
│   └── GlucoSense_ESP32.ino
├── frontend/
│   ├── src/
│   ├── package.json
│   └── .env.example
├── README.md
└── .gitignore
```

**Firmware:** `firmware/GlucoSense_ESP32.ino` contains the supplied ESP32 integrated firmware. Before flashing, replace `YOUR_WIFI_SSID`, `YOUR_WIFI_PASSWORD`, and `YOUR_DEVICE_API_KEY` with your local values. Keep real credentials out of GitHub.

## Technology stack

- **Frontend:** React, Vite, JavaScript, Recharts
- **Backend:** Python, FastAPI, Pydantic
- **Database:** MongoDB Atlas / PyMongo
- **Machine learning:** scikit-learn, NumPy, pandas, joblib
- **Embedded hardware (project design):** ESP32 with optical/physiological sensor modules

## Hardware and sensing concept

The project design uses multispectral/NIR optical sensing and physiological signals. The earlier hardware configuration includes an ESP32, AS7343 spectral sensor, MAX30102 pulse oximetry/PPG sensor, MLX90614 infrared temperature sensor, ADS1115 ADC, and SSD1306 OLED. Confirm actual wiring and firmware against your final hardware before reproducing the build.

## ESP32 firmware setup

1. Open `firmware/GlucoSense_ESP32.ino` in Arduino IDE.
2. Install the libraries required by the sketch (including the Adafruit sensor/display libraries, SparkFun MAX3010x library, and ArduinoJson).
3. Replace the Wi-Fi and device-key placeholders locally.
4. Select the correct ESP32 board and port, then compile and upload.
5. Confirm the I2C devices and sensor readings using Serial Monitor.

The firmware uses the ESP32 I2C bus on SDA GPIO21 and SCL GPIO22. Check the pin assignments and sensor addresses in the source comments against your actual wiring. Never commit your personal Wi-Fi password or device API key.

## Backend setup (Windows PowerShell)

1. Install Python 3.10+.
2. Open a terminal in the `backend` directory.
3. Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

4. Edit `backend/.env` with your own MongoDB connection details and a newly generated device API key. Never commit `.env`.
5. Start the API:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Check:
- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

## Frontend setup

Open a second terminal in the `frontend` directory:

```powershell
npm install
Copy-Item .env.example .env
npm run dev
```

Open the local URL printed by Vite (usually `http://localhost:5173`).

For a deployed backend, set `VITE_BACKEND_URL` in the frontend environment and configure the backend `CORS_ORIGINS` accordingly.

## ML model

The repository includes the supplied `backend/artifacts/glucosense_model.joblib` artifact. The training script is in `backend/app/ml/train.py`.

Model training expects suitable readings with reference glucose labels in MongoDB. The script includes a minimum-sample guardrail and records evaluation metadata. Do not interpret software evaluation metrics as evidence of clinical accuracy. Training data and participant-level records are intentionally not included in this public repository.

## Security

- Keep `backend/.env` and `frontend/.env` private.
- Never commit MongoDB URIs, passwords, Wi-Fi credentials, device API keys, access tokens, or participant-level datasets.
- Use a new, unique device API key for your own deployment.
- If a credential was ever committed to a public repository, rotate it immediately; deleting the file in a later commit does not remove it from Git history.

## Current limitations

- This repository is a software research prototype, not a certified medical product.
- Clinical validation and independent testing are not established.
- Firmware source is not included in this archive.
- Participant-level datasets and raw reading exports are intentionally excluded from this public-ready package.

## License

No license is included. Add a license only after confirming that you own or have permission to license all source code, datasets, model artifacts, and third-party assets in this repository.
