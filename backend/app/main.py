from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

# Load environment variables safely (prevent upward traversal finding invalid UTF-16 files)
main_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(main_dir, ".."))
project_dir = os.path.abspath(os.path.join(backend_dir, ".."))
dotenv_path = os.path.join(project_dir, ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    load_dotenv(dotenv_path=os.path.join(project_dir, "nonexistent.env"))

from app.api import centres, stock, footfall, beds, attendance, transfers, flags, reports, anomaly_api, forecasting_api, intake

app = FastAPI(
    title="Smart Health API",
    description="Real-time district health centre and supply chain management system API.",
    version="1.0.0"
)

# Configure CORS for dashboard integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers under /api prefix
app.include_router(centres.router, prefix="/api")
app.include_router(stock.router, prefix="/api")
app.include_router(footfall.router, prefix="/api")
app.include_router(beds.router, prefix="/api")
app.include_router(attendance.router, prefix="/api")
app.include_router(transfers.router, prefix="/api")
app.include_router(flags.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(anomaly_api.router, prefix="/api")
app.include_router(forecasting_api.router, prefix="/api")
app.include_router(intake.router, prefix="/api")

@app.on_event("startup")
def startup_event():
    import subprocess
    import sys
    from app.models import SessionLocal
    from app.models.models import Centre
    from app.services.forecasting import load_models, retrain_models

    # 1. Self-seed / setup tables if database is empty or tables don't exist
    db = SessionLocal()
    run_seeding = False
    try:
        if db.query(Centre).count() == 0:
            run_seeding = True
    except Exception:
        # Tables don't exist yet
        run_seeding = True
    finally:
        db.close()

    if run_seeding:
        print("Database tables missing or empty. Running auto-seeding...")
        try:
            main_dir = os.path.dirname(os.path.abspath(__file__))
            backend_dir = os.path.abspath(os.path.join(main_dir, ".."))
            script_path = os.path.join(backend_dir, "scripts", "generate_synthetic_data.py")
            subprocess.run([sys.executable, script_path], check=True)
            print("Auto-seeding completed successfully.")
        except Exception as e:
            print(f"Failed to run auto-seeding script: {e}")

    # 2. Check and retrain ML models if needed
    ff, _, _, _ = load_models()
    if ff is None:
        print("Pre-trained models not found. Running auto-retrain on startup...")
        db = SessionLocal()
        try:
            retrain_models(db)
        except Exception as e:
            print(f"Failed to auto-train models on startup: {e}")
        finally:
            db.close()


@app.get("/")
def read_root():
    return {
        "status": "online",
        "system": "Smart Health Platform",
        "description": "AI-driven health centre & supply chain management core services active."
    }
