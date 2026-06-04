"""
Worker 2 — The Inspector (Anomaly Detection Agent)
Consumes CDC events from Kafka and runs:
  - Rule-based checks  (regex, Pandera, Great Expectations)
  - AI-powered checks  (Gemini API)  <- only fires if all basic checks pass
  - Duplicate detection (FuzzyWuzzy / Soundex)

Also broadcasts every event to the dashboard via WebSocket on port 8765.
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

from checks.rule_based  import RuleBasedChecker
from checks.ai_checker  import AIChecker
from checks.duplicate   import DuplicateChecker

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("InspectorAgent")

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
KAFKA_TOPIC  = os.getenv("KAFKA_TOPIC",  "dbserver1.autoquery.customers")
KAFKA_GROUP  = os.getenv("KAFKA_GROUP",  "inspector-group")
WS_HOST      = os.getenv("WS_HOST", "0.0.0.0")
WS_PORT      = int(os.getenv("WS_PORT", "8765"))

# ── WebSocket state ────────────────────────────────────────────────────────────
_ws_clients: set = set()
_ws_loop: asyncio.AbstractEventLoop | None = None


async def _ws_handler(websocket):
    """Register a new dashboard client."""
    _ws_clients.add(websocket)
    log.info(f"🖥  Dashboard connected ({len(_ws_clients)} client(s))")
    try:
        await websocket.wait_closed()
    finally:
        _ws_clients.discard(websocket)
        log.info(f"🖥  Dashboard disconnected ({len(_ws_clients)} client(s))")


def _broadcast(payload: dict):
    """Thread-safe: push a JSON event to all connected dashboard clients."""
    if not _ws_clients or _ws_loop is None:
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
    """Run the WebSocket server in its own thread + event loop."""
    global _ws_loop
    _ws_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_ws_loop)

    async def _serve():
        async with websockets.serve(_ws_handler, WS_HOST, WS_PORT):
            log.info(f"🌐 WebSocket server listening on ws://{WS_HOST}:{WS_PORT}")
            await asyncio.Future()   # run forever

    _ws_loop.run_until_complete(_serve())


# ── CDC parsing ────────────────────────────────────────────────────────────────
def parse_event(raw_value: bytes) -> dict | None:
    """Extract the 'after' payload from a Debezium CDC envelope."""
    try:
        msg     = json.loads(raw_value)
        payload = msg.get("payload", msg)
        after   = payload.get("after")
        op      = payload.get("op", "?")   # c=create u=update d=delete r=read
        return {"op": op, "record": after} if after else None
    except (json.JSONDecodeError, AttributeError):
        return None


# ── Main loop ──────────────────────────────────────────────────────────────────
def run():
    # Start WS server in background thread
    ws_thread = threading.Thread(target=_start_ws_server, daemon=True)
    ws_thread.start()

    log.info("🔍 Inspector Agent starting — connecting to Kafka …")

    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        group_id=KAFKA_GROUP,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: v,
    )

    rule_checker = RuleBasedChecker()
    ai_checker   = AIChecker()
    dup_checker  = DuplicateChecker()

    log.info(f"✅ Listening on topic: {KAFKA_TOPIC}")

    for msg in consumer:
        event = parse_event(msg.value)
        if not event:
            continue

        op     = event["op"]
        record = event["record"]
        log.info(f"📥 Event [{op.upper()}] — {record}")

        issues     = []
        ai_checked = False
        ai_issues  = []

        # ── 1. Rule-based checks ───────────────────────────────────────
        rule_issues = rule_checker.check(record)
        if rule_issues:
            issues.extend(rule_issues)
            log.warning(f"  ⚠️  Rule issues: {rule_issues}")

        # ── 2. Duplicate detection ─────────────────────────────────────
        dup_issues = dup_checker.check(record)
        if dup_issues:
            issues.extend(dup_issues)
            log.warning(f"  🔁 Dup issues: {dup_issues}")

        # ── 3. AI check — only if basic checks passed ──────────────────
        if not issues:
            ai_checked = True
            ai_issues  = ai_checker.check(record)
            if ai_issues:
                issues.extend(ai_issues)
                log.warning(f"  🤖 AI issues : {ai_issues}")
        else:
            log.info(
                f"  ⏭️  Skipping AI check — "
                f"{len(issues)} basic issue(s) already detected."
            )

        # ── Summary ───────────────────────────────────────────────────
        if issues:
            log.error(f"❌ ANOMALY DETECTED — {len(issues)} issue(s): {issues}")
        else:
            log.info("  ✅ Record looks clean.")

        # ── Broadcast to dashboard ─────────────────────────────────────
        _broadcast({
            "op":         op,
            "record":     record,
            "issues":     issues,
            "ai_checked": ai_checked,
            "ai_issues":  ai_issues,
            "ts":         datetime.now(timezone.utc).strftime("%H:%M:%S"),
        })


if __name__ == "__main__":
    run()