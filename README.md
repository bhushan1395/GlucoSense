# GlucoSense – Non-Invasive Glucose Monitoring System

<p align="center">
  <strong>An Experimental IoT and Machine Learning Research Prototype</strong>
</p>

GlucoSense is an experimental non-invasive glucose monitoring research project that explores the use of optical sensing, physiological signals, IoT hardware, and Machine Learning for glucose estimation.

The system integrates an ESP32-based sensor platform with a full-stack web application, cloud database, and an experimental ML pipeline to collect, process, visualize, and analyze sensor readings.

> **Disclaimer:** GlucoSense is an experimental research prototype, not a clinically validated medical device. Its estimated glucose values must not be used for diagnosis, treatment, insulin dosing, or medical decisions.

## Key Features

- ESP32-based sensor data acquisition.
- Multispectral optical sensing using AS7343.
- NIR sensing experiments using 850 nm and 940 nm LEDs.
- PPG signal acquisition using MAX30102.
- Temperature monitoring using MLX90614.
- Real-time sensor telemetry and visualization.
- FastAPI-based backend services.
- MongoDB Atlas database integration.
- Experimental Machine Learning regression pipeline.
- Interactive React dashboard.
- Historical sensor reading management.

## Hardware Components

| Component | Purpose |
|---|---|
| ESP32 DevKit V1 | Main microcontroller |
| AS7343 | Multispectral optical sensing |
| MAX30102 | PPG and pulse signal acquisition |
| MLX90614 | Infrared temperature measurement |
| ADS1115 | 16-bit ADC |
| SSD1306 OLED | Sensor status and readings display |
| 850 nm / 940 nm LEDs | Near-infrared illumination |

## Technology Stack

**Embedded Systems**
- ESP32
- Arduino IDE
- I2C communication
- Sensor interfacing

**Backend**
- Python
- FastAPI
- Pydantic
- REST APIs

**Database**
- MongoDB Atlas
- PyMongo

**Frontend**
- React
- Vite
- JavaScript / TypeScript
- Recharts

**Machine Learning**
- Python
- NumPy
- Pandas
- Scikit-learn
- Joblib

## System Architecture

```text
       OPTICAL AND PHYSIOLOGICAL SENSORS
                      |
                      v
                  ESP32
                      |
                      v
              Wi-Fi Communication
                      |
                      v
             FASTAPI BACKEND
                      |
             +--------+--------+
             |                 |
             v                 v
       MONGODB ATLAS      ML PIPELINE
             |                 |
             v                 v
       Reading Storage   Experimental Model
             |                 |
             +--------+--------+
                      |
                      v
              REACT DASHBOARD
                      |
                      v
          Visualization and Analysis
```

## Machine Learning Pipeline

The GlucoSense ML module explores regression-based glucose estimation using optical and physiological sensor features.

The experimental pipeline includes:

1. Sensor data collection.
2. Data preprocessing and cleaning.
3. Signal quality assessment.
4. Feature extraction.
5. Model training and evaluation.
6. Model artifact storage.
7. Backend model integration.
8. Dashboard visualization.

The trained model artifact is stored in:

```text
backend/
└── artifacts/
    └── glucosense_model.joblib
```

Model performance and generalization require independent validation using appropriately collected reference glucose measurements. The prototype does not establish clinical accuracy.

## Project Structure

```text
GlucoSense/
│
├── backend/
│   ├── app/
│   │   └── ml/
│   ├── artifacts/
│   │   └── glucosense_model.joblib
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   ├── package.json
│   └── .env.example
│
├── firmware/
│   └── GlucoSense_ESP32.ino
│
├── README.md
└── .gitignore
```

## Installation and Setup

### 1. Clone the Repository

```bash
git clone https://github.com/bhushan1395/GlucoSense.git
cd GlucoSense
```

### 2. Backend Setup

```bash
cd backend

python -m venv .venv
```

Activate the environment on Windows:

```powershell
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create your environment file:

```powershell
Copy-Item .env.example .env
```

Configure your MongoDB URI and other required environment variables in `.env`.

Start the backend:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API health check:

```text
http://127.0.0.1:8000/health
```

Interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

### 3. Frontend Setup

Open another terminal:

```bash
cd frontend
npm install
```

Create the frontend environment file if required:

```powershell
Copy-Item .env.example .env
```

Start the development server:

```bash
npm run dev
```

Open the local URL displayed by Vite.

### 4. ESP32 Firmware Setup

1. Open `firmware/GlucoSense_ESP32.ino` in Arduino IDE.
2. Install the required sensor libraries.
3. Configure Wi-Fi credentials and device API key locally.
4. Select ESP32 DevKit V1 and the correct COM port.
5. Compile and upload the firmware.
6. Check sensor communication using Serial Monitor.

## API and Database

The FastAPI backend provides REST endpoints for sensor telemetry, database interaction, and model-related operations.

MongoDB Atlas is used for storing sensor readings and associated project data.

The API documentation is available through FastAPI Swagger UI at `/docs` when the backend is running.

## Future Scope

- Improve sensor calibration and signal quality.
- Collect larger datasets with reliable reference glucose labels.
- Conduct independent model validation.
- Explore additional regression algorithms.
- Improve optical sensor placement and hardware integration.
- Optimize real-time data processing.
- Evaluate performance across different users and conditions.

## Research and Safety Disclaimer

GlucoSense is developed for educational and research purposes.

It is not a certified or clinically validated glucose monitoring device. Optical and physiological sensor readings do not directly measure blood glucose. Experimental predictions must not replace standard glucose measurement devices or professional medical advice.

## Author

**Bhushan Bhatkar**

Electronics and Telecommunication Engineering

GitHub: https://github.com/bhushan1395

LinkedIn: https://www.linkedin.com/in/bhushan-bhatkar/

---

**Project:** GlucoSense – Non-Invasive Glucose Monitoring System

**Category:** IoT | Embedded Systems | Full Stack Development | Machine Learning
