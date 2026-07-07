import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

# Load environment variables safely (prevent upward traversal finding invalid UTF-16 files)
models_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(models_dir, "..", ".."))
project_dir = os.path.abspath(os.path.join(backend_dir, ".."))
dotenv_path = os.path.join(project_dir, ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path=dotenv_path)
else:
    # Set to a non-existent local path to prevent upward search
    load_dotenv(dotenv_path=os.path.join(project_dir, "nonexistent.env"))

# Default to SQLite for local development if DATABASE_URL is not set
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # database.py is in backend/app/models/database.py
    # We want to put smart_health.db in backend/smart_health.db
    models_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.abspath(os.path.join(models_dir, "..", ".."))
    db_path = os.path.join(backend_dir, "smart_health.db")
    DATABASE_URL = f"sqlite:///{db_path}"

# Adjust connect_args for SQLite and create directories if needed
connect_args = {}
if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    # Check if there is a relative/absolute folder path
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    connect_args["check_same_thread"] = False
elif DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args)


# Enable foreign key support in SQLite
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
