---
title: Smart Health
emoji: 🏥
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
app_port: 7860
---

# Smart Health — AI-Driven District Health Centre & Supply Chain Management

A real-time monitoring and resource management platform for district-level primary health centres (PHCs) and community health centres (CHCs).


---

## Folder Structure
```text
smart-health/
├── backend/
│   ├── app/
│   │   ├── api/             # API routing files (M3, M4, M5, M6, M7)
│   │   │   ├── __init__.py
│   │   │   ├── attendance.py
│   │   │   ├── beds.py
│   │   │   ├── centres.py
│   │   │   ├── flags.py
│   │   │   ├── footfall.py
│   │   │   ├── forecasting_api.py
│   │   │   ├── reports.py
│   │   │   ├── schemas.py
│   │   │   ├── stock.py
│   │   │   └── transfers.py
│   │   ├── models/          # SQLAlchemy database models (M1)
│   │   │   ├── __init__.py
│   │   │   ├── database.py
│   │   │   └── models.py
│   │   ├── services/        # Analytical Layers
│   │   │   ├── anomaly.py       # M4 Anomaly Layer
│   │   │   ├── forecasting.py   # M5 Forecasting Engine
│   │   │   ├── optimizer.py     # M6 Redistribution Optimizer
│   │   │   ├── flagging.py      # M7 Underperformance Flagging
│   │   │   └── models/          # Trained Model Files (.joblib)
│   │   └── main.py          # FastAPI app entrypoint
│   └── scripts/
│       ├── generate_synthetic_data.py   # M2 Synthetic Data Generator
│       ├── verify_seeded_data.py        # M2 Verification script
│       ├── test_api.py                  # M3 API verification tests
│       ├── test_anomaly.py              # M4 Anomaly Layer tests
│       ├── test_forecasting.py          # M5 Forecasting Engine tests
│       ├── test_optimizer.py            # M6 Redistribution Optimizer tests
│       └── test_flagging.py             # M7 Underperformance Flagging tests
├── requirements.txt         # Project-wide Python requirements
└── .env.example             # Template for configuration environment variables
```

---

## Setup & Running Locally

### 1. Prerequisites
- Python 3.13+ installed

### 2. Installation
From the `smart-health` folder:
```bash
pip install -r requirements.txt
```

### 3. Configuration
Copy the environment variables template and configure your parameters:
```bash
cp .env.example .env
```
*(For local SQLite development, the default parameters will work out of the box).*

### 4. Seeding Synthetic Data (M2)
To recreate the SQLite database and seed 90 days of realistic daily operations logs, run:
```bash
python backend/scripts/generate_synthetic_data.py
```
This generates 10 distinct health centres, 5 drugs, and 90 days of daily historical operations logs, injecting specific silent reporting and high consumption anomalies.

### 5. Verifying the Seeded Data
To check the data metrics and confirm that all anomalies have been injected correctly, run:
```bash
python backend/scripts/verify_seeded_data.py
```

### 6. Running the Core FastAPI Server (M3)
Navigate to the `backend` folder and run uvicorn:
```bash
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 7. Verifying the API CRUD (M3)
While the FastAPI server is running, execute the verification script from the `smart-health` folder:
```bash
python backend/scripts/test_api.py
```

### 8. Verifying the Data Trust & Anomaly Layer (M4)
Run the anomaly verification script to trigger scans and confirm that Wada PHC (silent centre) and Murbad PHC (consumption mismatch) are flagged:
```bash
python backend/scripts/test_anomaly.py
```

### 9. Verifying the Forecasting Engine (M5)
Run the forecasting verification script to trigger model training and verify rollout simulations with confidence intervals:
```bash
python backend/scripts/test_forecasting.py
```

### 10. Verifying the Redistribution Optimizer (M6)
Run the optimizer verification script to trigger optimization and verify transfer plan recommendations and execution:
```bash
python backend/scripts/test_optimizer.py
```

### 11. Verifying the Underperformance Flagging (M7)
Run the flagging verification script to trigger the peer-adequacy analysis and verify that Tokawade PHC gets flagged correctly for doctor absenteeism, bed overcrowding, and chronic stockouts:
```bash
python backend/scripts/test_flagging.py
```

### 12. Running the Frontend Dashboard (M9)
Navigate to the `frontend` folder and start the local Python-based web server:
```bash
cd frontend
python serve.py
```
Open your browser and navigate to `http://localhost:3000` to view the dashboard interface.

---

## Showcase Features
This platform includes special interactive showcase features designed for demonstration:
1. **Interactive Showcase Transfer Recommendations**: Multiple realistic scenarios (such as ORS reallocation during monsoon diarrheal spike, Insulin transfer due to cold-chain failure) are displayed under the **Transfer Recommendations** section. You can click **Approve** on any recommendation to see it statefully transition on the UI.
2. **Tertiary Referral & General Hospitals Bed Availability Tracker**: A dedicated dashboard panel displaying live bed capacity (ICU, Ventilator, Oxygen, General) for major district hospitals (SCB Medical College, AIIMS Bhubaneswar, City Hospital, Capital Hospital).
3. **Interactive Patient Referral Simulation**: You can select a bed type from the dropdown on any referral hospital card and click **Refer Patient**. This sends a live request to the FastAPI backend, reserving the bed, decrementing availability, and updating the dashboard live with a success toast notification.

