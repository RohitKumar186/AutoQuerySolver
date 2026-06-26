"""
Worker 5 — The Executor (Execution Agent)
The ONLY worker that writes to the live MySQL database.

Flow:
  1. Poll Redis queue for approved fixes from Worker 4
  2. Run mysqldump backup before each batch
  3. Apply fix via SQLAlchemy transaction with SAVEPOINT
  4. Read-back SELECT verification
  5. COMMIT on success, ROLLBACK on failure
  6. Broadcast result to dashboard (WebSocket port 8768)

This is the most careful worker in the system.
Every write is wrapped in a safety net.
"""

import asyncio
import json
import logging
import os
import threading
from datetime import datetime, timezone

import websockets
from dotenv import load_dotenv

from db.writer           import apply_fix
from redis_queue.redis_consumer import get_redis_client, consume_one, queue_length
from safety.backup       import run_backup, clean_old_backups

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
log = logging.getLogger("ExecutorAgent")

# ── Config ─────────────────────────────────────────────────────────────────────
WS_HOST        = os.getenv("WS_HOST",  "0.0.0.0")
WS_PORT        = int(os.getenv("WS_PORT", "8768"))   # Worker 2=8765, 3=8766, 4=8767
BACKUP_EVERY_N = int(os.getenv("BACKUP_EVERY_N", "10"))  # backup before every 10 fixes

# ── WebSocket state ────────────────────────────────────────────────────────────
_ws_clients: set = set()
_ws_loop         = None


async def _ws_handler(websocket):
    """Register a new dashboard client."""
    _ws_clients.add(websocket)
    log.info(f"🖥  Dashboard connected ({len(_ws_clients)} client(s))")
    try:
        await websocket.wait_closed()
    finally:
        _ws_clients.discard(websocket)
        log.info(f"🖥  Dashboard disconnected ({len(_ws_clients)} client(s))")


def broadcast(payload: dict):
    """Thread-safe: push a JSON event to all connected dashboard clients."""
    if not _ws_clients or _ws_loop is None:
        log.debug("No dashboard clients — skipping broadcast.")
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
            log.info(f"🌐 Executor WebSocket listening on ws://{WS_HOST}:{WS_PORT}")
            await asyncio.Future()   # run forever

    _ws_loop.run_until_complete(_serve())


# ── Main loop ──────────────────────────────────────────────────────────────────
def run():
    # ── Start WebSocket server in background thread ────────────────────────────
    ws_thread = threading.Thread(target=_start_ws_server, daemon=True)
    ws_thread.start()

    log.info("⚡ Executor Agent starting — connecting to Redis …")

    redis_client   = get_redis_client()
    fixes_executed = 0      # counter — used to decide when to take a backup
    last_backup    = None   # filepath of most recent backup

    log.info(f"✅ Executor ready — polling Redis queue '{os.getenv('REDIS_HOST', 'redis')}:approved_fixes'")
    log.info(f"   Backup every {BACKUP_EVERY_N} fix(es) | WebSocket on port {WS_PORT}")

    while True:
        try:
            # ── Poll Redis for next approved fix ──────────────────────
            pending = queue_length(redis_client)
            if pending > 0:
                log.info(f"  📋 {pending} fix(es) waiting in queue.")

            fix_payload = consume_one(redis_client)

            if fix_payload is None:
                # Timeout — nothing in queue, loop again
                continue

            record_id = fix_payload.get("record_id", "?")
            log.info(f"🔧 Processing fix for record id={record_id} ...")

            # ── Run backup before every Nth fix ───────────────────────
            if fixes_executed % BACKUP_EVERY_N == 0:
                log.info(f"  📸 Backup triggered (every {BACKUP_EVERY_N} fixes) ...")
                backup_result = run_backup()
                last_backup   = backup_result.get("filepath")

                if not backup_result["success"]:
                    log.error(
                        f"  ❌ Backup FAILED — {backup_result['reason']} "
                        f"— proceeding anyway (fix will still be applied)"
                    )
                else:
                    # Clean old backups to save disk space
                    clean_old_backups(keep_last=10)

                # Broadcast backup event to dashboard
                broadcast({
                    "type":      "backup",
                    "success":   backup_result["success"],
                    "filepath":  backup_result.get("filepath"),
                    "size_kb":   backup_result.get("size_kb", 0),
                    "ts":        datetime.now(timezone.utc).strftime("%H:%M:%S"),
                })

            # ── Apply the fix to MySQL ─────────────────────────────────
            result = apply_fix(fix_payload)
            fixes_executed += 1

            status    = result["status"]
            verified  = result["verified"]
            applied   = result["applied"]
            reason    = result["reason"]
            ts        = result["ts"]

            if status == "SUCCESS":
                log.info(
                    f"  ✅ Fix SUCCESS — id={record_id} "
                    f"fields={list(applied.keys())} verified={verified}"
                )
            elif status == "ROLLED_BACK":
                log.warning(
                    f"  ⚠️  Fix ROLLED BACK — id={record_id} reason='{reason}'"
                )
            else:
                log.error(
                    f"  ❌ Fix ERROR — id={record_id} reason='{reason}'"
                )

            # ── Broadcast execution result to dashboard ────────────────
            broadcast({
                "type":        "execution",
                "record_id":   record_id,
                "status":      status,
                "applied":     applied,
                "original":    fix_payload.get("original", {}),
                "fixed_fields":applied,
                "verified":    verified,
                "confidence":  fix_payload.get("confidence"),
                "approved_by": fix_payload.get("approved_by"),
                "explanation": fix_payload.get("explanation", ""),
                "reason":      reason,
                "last_backup": last_backup,
                "ts":          ts,
            })

        except KeyboardInterrupt:
            log.info("🛑 Executor shutting down.")
            break
        except Exception as exc:
            log.error(f"❌ Unexpected executor error: {exc}", exc_info=True)
            # Don't crash the loop — log and continue
            continue


if __name__ == "__main__":
    run()