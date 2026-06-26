"""
db/connection.py
SQLAlchemy engine factory for Worker 5.
Creates a single shared engine using .env credentials.
All DB operations in worker5 import from here.
"""

import os
import logging
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("DBConnection")

DB_HOST     = os.getenv("DB_HOST",     "watchman_mysql")
DB_PORT     = os.getenv("DB_PORT",     "3306")
DB_NAME     = os.getenv("DB_NAME",     "autoquery_db")
DB_USER     = os.getenv("DB_USER",     "solver_admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# mysql+pymysql://user:password@host:port/dbname
DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

_engine = None


def get_engine():
    """
    Returns a shared SQLAlchemy engine.
    Creates it once, reuses it on every subsequent call.
    Like a single road between Python and MySQL —
    no need to build a new road every time.
    """
    global _engine
    if _engine is None:
        try:
            _engine = create_engine(
                DATABASE_URL,
                pool_pre_ping=True,      # auto-reconnect if connection drops
                pool_size=5,             # max 5 connections in pool
                max_overflow=2,          # allow 2 extra in emergencies
                echo=False,              # set True to log every SQL statement
            )
            # Test the connection immediately
            with _engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            log.info(f"✅ DB engine ready — {DB_HOST}:{DB_PORT}/{DB_NAME}")
        except Exception as exc:
            log.error(f"❌ DB connection failed: {exc}")
            raise
    return _engine