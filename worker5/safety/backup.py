"""
safety/backup.py
Worker 5 — Pre-execution mysqldump backup.

Runs mysqldump via subprocess BEFORE writing any fix to the database.
Saves backup to /backups/backup_YYYYMMDD_HHMMSS.sql

Like taking a photo of the database before surgery.
If something goes catastrophically wrong, Rohit can restore from this file.

Usage:
    from safety.backup import run_backup
    success = run_backup()
"""

import logging
import os
import subprocess
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("Backup")

DB_HOST     = os.getenv("DB_HOST",     "watchman_mysql")
DB_PORT     = os.getenv("DB_PORT",     "3306")
DB_NAME     = os.getenv("DB_NAME",     "autoquery_db")
DB_USER     = os.getenv("DB_USER",     "solver_admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

BACKUP_DIR  = os.getenv("BACKUP_DIR",  "/backups")


def run_backup() -> dict:
    """
    Runs mysqldump and saves output to /backups/backup_YYYYMMDD_HHMMSS.sql

    Returns:
    {
        "success":   True | False,
        "filepath":  "/backups/backup_20260622_143000.sql",
        "size_kb":   42,
        "reason":    "OK" | "error message"
    }
    """
    # ── Make sure backup directory exists ─────────────────────────────────────
    os.makedirs(BACKUP_DIR, exist_ok=True)

    timestamp   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"backup_{timestamp}.sql")

    log.info(f"  📸 Starting mysqldump → {backup_file}")

    # ── Build the mysqldump command ────────────────────────────────────────────
    # subprocess runs this as if you typed it in a terminal:
    # mysqldump -h watchman_mysql -P 3306 -u solver_admin -psecret autoquery_db > backup.sql
    cmd = [
        "mysqldump",
        f"-h{DB_HOST}",
        f"-P{DB_PORT}",
        f"-u{DB_USER}",
        f"-p{DB_PASSWORD}",
        "--ssl-mode=DISABLED",          # no space between -p and password
        "--single-transaction",        # consistent snapshot without locking tables
        "--routines",                  # include stored procedures
        "--triggers",                  # include triggers
        DB_NAME,
    ]

    try:
        with open(backup_file, "w") as out_file:
            result = subprocess.run(
                cmd,
                stdout=out_file,       # write dump output directly to file
                stderr=subprocess.PIPE,
                timeout=120,           # max 2 minutes for backup
            )

        if result.returncode != 0:
            error_msg = result.stderr.decode("utf-8", errors="replace").strip()
            # mysqldump prints password warning to stderr — not a real error
            if "Using a password on the command line" in error_msg:
                log.warning("  ⚠️  mysqldump password warning (safe to ignore)")
            else:
                log.error(f"  ❌ mysqldump failed: {error_msg}")
                return {
                    "success":  False,
                    "filepath": backup_file,
                    "size_kb":  0,
                    "reason":   error_msg,
                }

        # ── Check backup file size ─────────────────────────────────────
        size_bytes = os.path.getsize(backup_file)
        size_kb    = round(size_bytes / 1024, 1)

        if size_bytes < 100:
            log.warning(f"  ⚠️  Backup file suspiciously small ({size_kb} KB) — may be empty.")

        log.info(f"  ✅ Backup complete — {backup_file} ({size_kb} KB)")
        return {
            "success":  True,
            "filepath": backup_file,
            "size_kb":  size_kb,
            "reason":   "OK",
        }

    except subprocess.TimeoutExpired:
        log.error("  ❌ mysqldump timed out after 120 seconds.")
        return {
            "success":  False,
            "filepath": backup_file,
            "size_kb":  0,
            "reason":   "mysqldump timed out",
        }
    except FileNotFoundError:
        log.error("  ❌ mysqldump not found — is it installed in the container?")
        return {
            "success":  False,
            "filepath": backup_file,
            "size_kb":  0,
            "reason":   "mysqldump binary not found",
        }
    except Exception as exc:
        log.error(f"  ❌ Backup error: {exc}", exc_info=True)
        return {
            "success":  False,
            "filepath": backup_file,
            "size_kb":  0,
            "reason":   str(exc),
        }


def clean_old_backups(keep_last: int = 10):
    """
    Deletes oldest backup files, keeping only the last N.
    Prevents /backups from filling up disk over time.
    """
    try:
        files = sorted([
            os.path.join(BACKUP_DIR, f)
            for f in os.listdir(BACKUP_DIR)
            if f.startswith("backup_") and f.endswith(".sql")
        ])

        to_delete = files[:-keep_last] if len(files) > keep_last else []

        for f in to_delete:
            os.remove(f)
            log.info(f"  🗑️  Deleted old backup: {f}")

        if to_delete:
            log.info(f"  🧹 Cleaned {len(to_delete)} old backup(s), kept last {keep_last}.")

    except Exception as exc:
        log.warning(f"  ⚠️  Backup cleanup error: {exc}")