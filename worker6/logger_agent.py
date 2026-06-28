"""
Worker 6 — The Logger / Auditor
Consumes CDC events from Kafka (same topic, new consumer group).
For every fix event:
  1. Writes an append-only row to audit_log (MySQL)
  2. Updates ChromaDB memory so Worker 3 learns from confirmed fixes
  3. Builds a report payload and broadcasts it to the dashboard (WebSocket)

Also runs a FastAPI server on port 8770 for audit REST queries.

Pipeline (LangGraph):
  ingest → audit → memory → reporter → broadcast
"""

import asyncio
import json
import logging
import os
import threading
from datetime import datetime, timezone

import websockets
from kafka import KafkaConsumer
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("LoggerAgent")

from config import (
    KAFKA_BROKER, KAFKA_TOPIC, KAFKA_GROUP,
    WS_HOST, WS_PORT, API_HOST, API_PORT,
)
from models.db_setup      import setup_db
from services.audit_writer import AuditWriter
from services.memory_writer import MemoryWriter
from services.report_builder import ReportBuilder
from pipeline              import build_pipeline
from api.app               import run_api

# ── WebSocket state ────────────────────────────────────────────────────────────
_ws_clients: set = set()
_ws_loop = None


async def _ws_handler(websocket):
    _ws_clients.add(websocket)
    log.info(f"🖥  Dashboard connected ({len(_ws_clients)} client(s))")
    try:
        await websocket.wait_closed()
    finally:
        _ws_clients.discard(websocket)
        log.info(f"🖥  Dashboard disconnected ({len(_ws_clients)} client(s))")


def broadcast(payload: dict):
    """Thread-safe push to all connected dashboard clients."""
    if not _ws_clients or _ws_loop is None:
        return
    msg = json.dumps(payload, default=str)
    asyncio.run_coroutine_threadsafe(_do_broadcast(msg), _ws_loop)


async def _do_broadcast(msg: str):
    if not _ws_clients:
        return
    await asyncio.gather(
        *[ws.send(msg) for ws in list(_ws_clients)],
        return_exceptions=True,
    )


def _start_ws_server():
    global _ws_loop
    _ws_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_ws_loop)

    async def _serve():
        async with websockets.serve(_ws_handler, WS_HOST, WS_PORT):
            log.info(f"🌐 Logger WebSocket on ws://{WS_HOST}:{WS_PORT}")
            await asyncio.Future()

    _ws_loop.run_until_complete(_serve())


# ── CDC event parsing ──────────────────────────────────────────────────────────
def parse_event(raw_value: bytes) -> dict | None:
    """
    Parse a raw Debezium CDC message from Kafka.
    Returns a normalised dict or None if the message is unusable.

    Worker 6 reads the same raw Debezium topic as Workers 2 and 3.
    It does NOT receive Worker 5's execution results directly — Worker 5
    writes to MySQL, and Debezium captures that write as a new CDC event.

    So Worker 6 sees the final corrected record as a Debezium UPDATE event.
    The 'before' contains the bad data, the 'after' contains the fix.
    """
    try:
        msg     = json.loads(raw_value)
        payload = msg.get("payload", msg)
        op      = payload.get("op", "?")
        after   = payload.get("after")
        before  = payload.get("before")

        if not after:
            return None

        # For UPDATE events (op="u"), before=original bad record, after=fixed record
        # For INSERT events (op="c"), this is a new record (could be clean or anomaly)
        return {
            "op":     op,
            "after":  after,
            "before": before,
            # Worker 5 stores these in the record itself for traceability
            "issues":      after.get("_issues"),
            "fixed":       after,
            "original":    before or after,
            "confidence":  after.get("_confidence"),
            "fix_valid":   after.get("_fix_valid"),
            "approved_by": after.get("_approved_by"),
            "explanation": after.get("_explanation"),
            "worker":      "worker5",
            "record_id":   after.get("id"),
            "ts":          datetime.now(timezone.utc).strftime("%H:%M:%S"),
        }
    except (json.JSONDecodeError, AttributeError):
        return None


# ── Main ───────────────────────────────────────────────────────────────────────
def run():
    # ── Setup DB ───────────────────────────────────────────────────────────────
    log.info("📋 Logger Agent starting — setting up database …")
    engine = setup_db()

    # ── Init services ──────────────────────────────────────────────────────────
    audit_writer  = AuditWriter(engine)
    memory_writer = MemoryWriter()
    report_builder = ReportBuilder()

    # ── Build LangGraph pipeline ───────────────────────────────────────────────
    pipeline = build_pipeline(
        audit_writer=audit_writer,
        memory_writer=memory_writer,
        report_builder=report_builder,
        broadcast_fn=broadcast,
    )

    # ── Start WebSocket server (background thread) ─────────────────────────────
    ws_thread = threading.Thread(target=_start_ws_server, daemon=True)
    ws_thread.start()

    # ── Start FastAPI server (background thread) ───────────────────────────────
    api_thread = threading.Thread(
        target=run_api,
        args=(audit_writer, memory_writer, report_builder, API_HOST, API_PORT),
        daemon=True,
    )
    api_thread.start()
    log.info(f"🌐 FastAPI audit API on http://{API_HOST}:{API_PORT}")

    # ── Kafka consumer loop ────────────────────────────────────────────────────
    log.info(f"📋 Connecting to Kafka — topic={KAFKA_TOPIC} group={KAFKA_GROUP}")

    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        group_id=KAFKA_GROUP,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: v,
    )

    log.info("✅ Logger Agent ready — listening for events …")

    for msg in consumer:
        event = parse_event(msg.value)
        if not event:
            continue

        log.info(
            f"📥 Logger received [{event['op'].upper()}] — "
            f"record_id={event.get('record_id')}"
        )

        try:
            result = pipeline.invoke({
                "raw_event":         event,
                "op":                "",
                "record_id":         None,
                "original":          {},
                "fixed":             {},
                "before":            None,
                "issues":            [],
                "confidence":        None,
                "fix_valid":         False,
                "approved_by":       None,
                "explanation":       "",
                "worker":            "worker5",
                "ts":                "",
                "is_fix_event":      False,
                "skipped":           False,
                "audit_id":          None,
                "audit_row":         None,
                "memory_written":    False,
                "dashboard_payload": None,
                "full_report":       None,
            })

            if result.get("skipped"):
                log.info("  ⏭️  Event skipped — no action needed.")
            else:
                log.info(
                    f"  ✅ Pipeline complete — "
                    f"audit_id={result.get('audit_id')} "
                    f"memory={result.get('memory_written')}"
                )

        except Exception as exc:
            log.error(f"  ❌ Pipeline error: {exc}", exc_info=True)


if __name__ == "__main__":
    run()