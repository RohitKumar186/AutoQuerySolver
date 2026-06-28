"""
worker6/models/db_setup.py
Creates all tables on startup. Safe to call multiple times (CREATE IF NOT EXISTS).
"""

import logging
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from config import DATABASE_URL
from models.audit_log import Base

log = logging.getLogger("DBSetup")


def get_engine(retries: int = 10, delay: int = 5):
    """
    Create SQLAlchemy engine with retry loop.
    MySQL may still be initialising when this container starts.
    """
    for attempt in range(1, retries + 1):
        try:
            engine = create_engine(
                DATABASE_URL,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            log.info(f"✅ MySQL connected on attempt {attempt}.")
            return engine
        except OperationalError as exc:
            log.warning(
                f"  ⏳ MySQL not ready (attempt {attempt}/{retries}): {exc}. "
                f"Retrying in {delay}s …"
            )
            time.sleep(delay)

    raise RuntimeError("❌ Could not connect to MySQL after multiple retries.")


def create_tables(engine):
    """Create audit_log (and any future tables) if they don't exist."""
    Base.metadata.create_all(engine)
    log.info("✅ audit_log table ready.")


def setup_db():
    engine = get_engine()
    create_tables(engine)
    return engine