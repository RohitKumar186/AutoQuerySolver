"""
Worker 3 — The Doctor (Correction Agent)
"""

import json
import logging
import os
import threading
import asyncio
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

import websockets
from kafka import KafkaConsumer
from dotenv import load_dotenv

from graph.pipeline import build_pipeline

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("DoctorAgent")

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC  = os.getenv("KAFKA_TOPIC",  "dbserver1.autoquery_db.customers")
KAFKA_GROUP  = os.getenv("KAFKA_GROUP",  "doctor-group")
WS_HOST      = os.getenv("WS_HOST",  "0.0.0.0")
WS_PORT      = int(os.getenv("WS_PORT", "8766"))
HTTP_PORT    = int(os.getenv("HTTP_PORT", "8767"))

DB_HOST = os.getenv("DB_HOST", "watchman_mysql")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "solver_admin")
DB_PASS = os.getenv("DB_PASSWORD", "secure_agent_password_2026")
DB_NAME = os.getenv("DB_NAME", "autoquery_db")

# ── In-memory table snapshot ────────────────────────────────────────────────────
# Stores every row we've seen via Kafka, keyed by id
_table_snapshot: dict = {}
_table_lock = threading.Lock()

# ── WebSocket state ─────────────────────────────────────────────────────────────
_ws_clients: set = set()
_ws_loop = None


async def _ws_handler(websocket):
    _ws_clients.add(websocket)
    log.info(f"🖥  Dashboard connected ({len(_ws_clients)} client(s))")
    # Send current snapshot immediately on connect
    with _table_lock:
        snapshot = list(_table_snapshot.values())
    try:
        await websocket.send(json.dumps({"type": "snapshot", "rows": snapshot}))
    except Exception:
        pass
    try:
        await websocket.wait_closed()
    finally:
        _ws_clients.discard(websocket)


def broadcast(payload: dict):
    if _ws_loop is None:
        return
    msg = json.dumps(payload)
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
            log.info(f"🌐 Doctor WebSocket listening on ws://{WS_HOST}:{WS_PORT}")
            await asyncio.Future()

    _ws_loop.run_until_complete(_serve())


# ── HTTP API — serves /table for dashboard ──────────────────────────────────────
class TableHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silence HTTP logs

    def do_GET(self):
        if self.path == "/table" or self.path == "/table/":
            with _table_lock:
                rows = list(_table_snapshot.values())
            rows.sort(key=lambda r: r.get("id", 0))
            body = json.dumps({"rows": rows}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()


def _start_http_server():
    server = HTTPServer(("0.0.0.0", HTTP_PORT), TableHandler)
    log.info(f"🌐 HTTP API listening on http://0.0.0.0:{HTTP_PORT}/table")
    server.serve_forever()


# ── CDC parsing ─────────────────────────────────────────────────────────────────
def parse_event(raw_value: bytes) -> dict | None:
    try:
        msg     = json.loads(raw_value)
        payload = msg.get("payload", msg)
        after   = payload.get("after")
        op      = payload.get("op", "?")
        before  = payload.get("before")
        return {"op": op, "record": after, "before": before} if after else None
    except (json.JSONDecodeError, AttributeError):
        return None


def _update_snapshot(op: str, record: dict, fixed_record: dict = None, fix_valid: bool = False):
    """Keep in-memory table snapshot up to date."""
    if not record:
        return
    rid = record.get("id")
    if not rid:
        return

    with _table_lock:
        if op == "d":
            _table_snapshot.pop(rid, None)
        else:
            merged = dict(record)
            status = "clean"
            if fixed_record:
                merged.update(fixed_record)
                status = "fixed" if fix_valid else "partial"
            elif rid in _table_snapshot:
                status = _table_snapshot[rid].get("status", "clean")
            _table_snapshot[rid] = {**merged, "status": status}


# ── Main loop ────────────────────────────────────────────────────────────────────
def run():
    # Start WebSocket server
    threading.Thread(target=_start_ws_server, daemon=True).start()
    # Start HTTP API server
    threading.Thread(target=_start_http_server, daemon=True).start()

    log.info("🩺 Doctor Agent starting — connecting to Kafka …")

    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        group_id=KAFKA_GROUP,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: v,
    )

    pipeline = build_pipeline(broadcast_fn=broadcast)
    log.info(f"✅ Doctor listening on topic: {KAFKA_TOPIC}")

    for msg in consumer:
        event = parse_event(msg.value)
        if not event:
            continue

        op     = event["op"]
        record = event["record"]

        log.info(f"📥 Doctor received [{op.upper()}] — {record}")

        # Add to snapshot as clean first
        _update_snapshot(op, record)

        # Broadcast raw row event to dashboard
        broadcast({
            "type":   "row",
            "op":     op,
            "record": record,
            "status": "clean",
            "ts":     datetime.now(timezone.utc).strftime("%H:%M:%S"),
        })

        try:
            result = pipeline.invoke({
                "op":        op,
                "record":    record,
                "before":    event.get("before"),
                "issues":    [],
                "embedding": [],
                "similar":   [],
                "fix":       None,
                "fix_valid": False,
                "ts":        datetime.now(timezone.utc).strftime("%H:%M:%S"),
            })

            if result.get("skipped"):
                log.info("  ⏭️  Record is clean — Doctor has nothing to fix.")
            else:
                fix       = result.get("fix") or {}
                fix_valid = result.get("fix_valid", False)
                fixed_record = fix.get("fixed_record", {})

                # Update snapshot with fixed data
                _update_snapshot(op, record, fixed_record, fix_valid)

                if fix_valid:
                    log.info(f"  ✅ Fix applied: {fix}")
                else:
                    log.warning("  ⚠️  Fix generated but failed validation.")

        except Exception as exc:
            log.error(f"  ❌ Pipeline error: {exc}", exc_info=True)


if __name__ == "__main__":
    run()