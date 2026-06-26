"""
tests/test_backup.py
pytest tests for safety/backup.py

Tests:
  1. mysqldump not found → returns failure dict cleanly
  2. mysqldump succeeds → returns success dict with filepath
  3. clean_old_backups deletes excess files correctly

Run with:
  pytest worker5/tests/test_backup.py -v
"""

import os
import pytest
from unittest.mock import patch, MagicMock


# ── Test 1: mysqldump binary not found ────────────────────────────────────────
def test_backup_mysqldump_not_found(tmp_path):
    """
    If mysqldump is not installed in the container,
    backup should return failure cleanly — not crash.
    """
    from safety.backup import run_backup

    with patch("safety.backup.BACKUP_DIR", str(tmp_path)):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = run_backup()

    assert result["success"]  == False
    assert result["size_kb"]  == 0
    assert "not found" in result["reason"].lower()


# ── Test 2: mysqldump succeeds ─────────────────────────────────────────────────
def test_backup_success(tmp_path):
    """
    Simulates a successful mysqldump run.
    Backup file should be created with content.
    """
    from safety.backup import run_backup

    def fake_subprocess_run(cmd, stdout, stderr, timeout):
        # Write fake SQL content to the output file
        stdout.write("-- MySQL dump\nCREATE TABLE customers (...);\n")
        mock_result         = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr  = b""
        return mock_result

    with patch("safety.backup.BACKUP_DIR", str(tmp_path)):
        with patch("subprocess.run", side_effect=fake_subprocess_run):
            result = run_backup()

    assert result["success"]            == True
    assert result["reason"]             == "OK"
    assert result["filepath"].endswith(".sql")
    assert os.path.exists(result["filepath"])


# ── Test 3: mysqldump returns non-zero exit code ───────────────────────────────
def test_backup_nonzero_exit(tmp_path):
    """
    If mysqldump exits with error code, backup should return failure.
    """
    from safety.backup import run_backup

    mock_result            = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr     = b"Access denied for user"

    with patch("safety.backup.BACKUP_DIR", str(tmp_path)):
        with patch("subprocess.run", return_value=mock_result):
            result = run_backup()

    assert result["success"] == False
    assert "Access denied" in result["reason"]


# ── Test 4: clean_old_backups keeps only last N files ─────────────────────────
def test_clean_old_backups(tmp_path):
    """
    Creates 15 fake backup files, runs clean with keep_last=10.
    Should delete 5 oldest files.
    """
    from safety.backup import clean_old_backups

    # Create 15 fake backup files
    for i in range(15):
        filepath = tmp_path / f"backup_2026060{i:02d}_120000.sql"
        filepath.write_text("-- fake backup")

    with patch("safety.backup.BACKUP_DIR", str(tmp_path)):
        clean_old_backups(keep_last=10)

    remaining = [
        f for f in os.listdir(tmp_path)
        if f.startswith("backup_") and f.endswith(".sql")
    ]

    assert len(remaining) == 10


# ── Test 5: clean_old_backups does nothing if fewer than N files ───────────────
def test_clean_old_backups_no_deletion(tmp_path):
    """
    If fewer than keep_last files exist, nothing should be deleted.
    """
    from safety.backup import clean_old_backups

    for i in range(3):
        filepath = tmp_path / f"backup_20260601_1200{i:02d}.sql"
        filepath.write_text("-- fake backup")

    with patch("safety.backup.BACKUP_DIR", str(tmp_path)):
        clean_old_backups(keep_last=10)

    remaining = [
        f for f in os.listdir(tmp_path)
        if f.startswith("backup_") and f.endswith(".sql")
    ]

    assert len(remaining) == 3