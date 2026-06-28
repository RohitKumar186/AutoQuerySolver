"""
worker6/config.py
All environment variables and shared constants for Worker 6.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Kafka ──────────────────────────────────────────────────────────────────────
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC  = os.getenv("KAFKA_TOPIC",  "dbserver1.autoquery_db.customers")
KAFKA_GROUP  = os.getenv("KAFKA_GROUP",  "logger-group")

# ── MySQL (audit table) ────────────────────────────────────────────────────────
DB_HOST     = os.getenv("DB_HOST",     "localhost")
DB_PORT     = os.getenv("DB_PORT",     "3306")
DB_USER     = os.getenv("DB_USER",     "solver_admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME     = os.getenv("DB_NAME",     "autoquery_db")

DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# ── ChromaDB ───────────────────────────────────────────────────────────────────
CHROMA_PATH       = os.getenv("CHROMA_PATH", "/chroma_data")
CHROMA_COLLECTION = "doctor_fixes"

# ── WebSocket ──────────────────────────────────────────────────────────────────
WS_HOST = os.getenv("WS_HOST", "0.0.0.0")
WS_PORT = int(os.getenv("WS_PORT", "8769"))

# ── FastAPI ────────────────────────────────────────────────────────────────────
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8770"))