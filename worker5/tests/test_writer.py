"""
tests/test_writer.py
pytest tests for db/writer.py

Tests:
  1. Missing record_id → returns ERROR
  2. Missing fixed_record → returns ERROR
  3. Valid payload shape → returns SUCCESS or ROLLED_BACK (depends on DB)
  4. Payload with unknown record_id → returns ROLLED_BACK (0 rows updated)

Run with:
  pytest worker5/tests/test_writer.py -v
"""

import pytest
from unittest.mock import patch, MagicMock


# ── Test 1: Missing record_id ──────────────────────────────────────────────────
def test_missing_record_id():
    from db.writer import apply_fix

    result = apply_fix({
        "fixed_record": {"name": "Rohit Singh"},
        # record_id intentionally missing
    })

    assert result["status"]   == "ERROR"
    assert result["verified"] == False
    assert "missing" in result["reason"].lower() or result["reason"] != ""


# ── Test 2: Missing fixed_record ───────────────────────────────────────────────
def test_missing_fixed_record():
    from db.writer import apply_fix

    result = apply_fix({
        "record_id": 5,
        # fixed_record intentionally missing
    })

    assert result["status"]   == "ERROR"
    assert result["verified"] == False


# ── Test 3: Empty fixed_record dict ────────────────────────────────────────────
def test_empty_fixed_record():
    from db.writer import apply_fix

    result = apply_fix({
        "record_id":    5,
        "fixed_record": {},   # empty — nothing to fix
    })

    assert result["status"]   == "ERROR"
    assert result["verified"] == False


# ── Test 4: Valid payload — mock DB success ────────────────────────────────────
def test_success_with_mock_db():
    """
    Mocks the SQLAlchemy engine so we don't need a real DB.
    Simulates: UPDATE succeeds, read-back matches.
    """
    from db.writer import apply_fix

    # Create mock objects to simulate SQLAlchemy behavior
    mock_conn   = MagicMock()
    mock_engine = MagicMock()

    # Simulate UPDATE returning 1 row affected
    mock_execute_update = MagicMock()
    mock_execute_update.rowcount = 1

    # Simulate SELECT returning ("Rohit Singh", "UNKNOWN")
    mock_row = ("Rohit Singh", "UNKNOWN")

    # Make conn.execute return different things for different calls:
    # 1st call = SAVEPOINT, 2nd = UPDATE, 3rd = SELECT, 4th = RELEASE SAVEPOINT
    mock_conn.execute.side_effect = [
        MagicMock(),                          # SAVEPOINT
        mock_execute_update,                  # UPDATE → 1 row
        MagicMock(fetchone=lambda: mock_row), # SELECT → row matches
        MagicMock(),                          # RELEASE SAVEPOINT
    ]

    mock_engine.begin.return_value.__enter__ = lambda s: mock_conn
    mock_engine.begin.return_value.__exit__  = MagicMock(return_value=False)

    with patch("db.writer.get_engine", return_value=mock_engine):
        result = apply_fix({
            "record_id":    1,
            "table":        "customers",
            "fixed_record": {"name": "Rohit Singh", "phone": "UNKNOWN"},
            "explanation":  "Fixed typo in name",
        })

    assert result["status"]   == "SUCCESS"
    assert result["verified"] == True
    assert result["record_id"] == 1


# ── Test 5: Read-back mismatch → ROLLBACK ─────────────────────────────────────
def test_rollback_on_mismatch():
    """
    Simulates: UPDATE succeeds but read-back returns different value.
    Expected: ROLLED_BACK.
    """
    from db.writer import apply_fix

    mock_conn   = MagicMock()
    mock_engine = MagicMock()

    mock_execute_update      = MagicMock()
    mock_execute_update.rowcount = 1

    # Read-back returns WRONG value — mismatch
    wrong_row = ("Wrong Name", "UNKNOWN")

    mock_conn.execute.side_effect = [
        MagicMock(),                               # SAVEPOINT
        mock_execute_update,                       # UPDATE → 1 row
        MagicMock(fetchone=lambda: wrong_row),     # SELECT → MISMATCH
        MagicMock(),                               # ROLLBACK TO SAVEPOINT
    ]

    mock_engine.begin.return_value.__enter__ = lambda s: mock_conn
    mock_engine.begin.return_value.__exit__  = MagicMock(return_value=False)

    with patch("db.writer.get_engine", return_value=mock_engine):
        result = apply_fix({
            "record_id":    5,
            "table":        "customers",
            "fixed_record": {"name": "Rohit Singh", "phone": "UNKNOWN"},
            "explanation":  "Fixed typo in name",
        })

    assert result["status"]   == "ROLLED_BACK"
    assert result["verified"] == False
    assert "mismatch" in result["reason"].lower()


# ── Test 6: Zero rows updated → ROLLBACK ──────────────────────────────────────
def test_rollback_on_zero_rows():
    """
    Simulates: record_id does not exist in DB → UPDATE affects 0 rows.
    Expected: ROLLED_BACK with helpful reason.
    """
    from db.writer import apply_fix

    mock_conn   = MagicMock()
    mock_engine = MagicMock()

    mock_execute_update          = MagicMock()
    mock_execute_update.rowcount = 0    # ← 0 rows affected

    mock_conn.execute.side_effect = [
        MagicMock(),          # SAVEPOINT
        mock_execute_update,  # UPDATE → 0 rows
        MagicMock(),          # ROLLBACK TO SAVEPOINT
    ]

    mock_engine.begin.return_value.__enter__ = lambda s: mock_conn
    mock_engine.begin.return_value.__exit__  = MagicMock(return_value=False)

    with patch("db.writer.get_engine", return_value=mock_engine):
        result = apply_fix({
            "record_id":    9999,   # non-existent id
            "table":        "customers",
            "fixed_record": {"name": "Someone"},
            "explanation":  "Test",
        })

    assert result["status"]   == "ROLLED_BACK"
    assert result["verified"] == False