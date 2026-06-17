"""
approval/api.py
FastAPI — approve/reject endpoints for the manager approval UI.
Also serves a WebSocket so the React frontend gets live fix updates.

Endpoints:
    GET  /pending              — list all fixes waiting for approval
    GET  /fix/{fix_id}         — get one fix by id
    POST /approve/{fix_id}     — approve a fix (moves to approved queue)
    POST /reject/{fix_id}      — reject a fix  (moves to rejected queue)
    GET  /stats                — queue depth stats
    WS   /ws                   — live updates pushed to approval UI
"""

import asyncio
import json
import logging
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

log = logging.getLogger("ApprovalAPI")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Watchman Checker — Approval API",
    description="Human-in-the-loop approval interface for Worker 4",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Lazy imports (avoid circular) ─────────────────────────────────────────────
_queue    = None
_notifier = None
_applier  = None


def init_api(queue, notifier, applier):
    """Called from checker_agent.py after all components are ready."""
    global _queue, _notifier, _applier
    _queue    = queue
    _notifier = notifier
    _applier  = applier
    log.info("✅ ApprovalAPI initialised.")


# ── WebSocket manager ─────────────────────────────────────────────────────────
_ws_clients: set = set()


async def broadcast_ws(payload: dict):
    """Push a live update to all connected approval UI clients."""
    if not _ws_clients:
        return
    msg = json.dumps(payload)
    await asyncio.gather(
        *[ws.send_text(msg) for ws in list(_ws_clients)],
        return_exceptions=True,
    )


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.add(websocket)
    log.info(f"🖥  Approval UI connected ({len(_ws_clients)} client(s))")
    try:
        while True:
            await websocket.receive_text()   # keep-alive; UI can send pings
    except WebSocketDisconnect:
        _ws_clients.discard(websocket)
        log.info(f"🖥  Approval UI disconnected ({len(_ws_clients)} client(s))")


# ── Request / Response models ─────────────────────────────────────────────────
class RejectRequest(BaseModel):
    reason: Optional[str] = "No reason provided"
    rejected_by: Optional[str] = "manager"


class ApproveRequest(BaseModel):
    approved_by: Optional[str] = "manager"


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "watchman-checker"}


@app.get("/stats")
def stats():
    if not _queue:
        raise HTTPException(503, "Queue not initialised")
    return {
        "pending":  _queue.pending_count(),
        "redis_ok": _queue.available,
    }


@app.get("/pending")
def list_pending():
    """Return all fixes currently waiting for human approval."""
    if not _queue:
        raise HTTPException(503, "Queue not initialised")
    fixes = _queue.list_pending()
    return {"count": len(fixes), "fixes": fixes}


@app.get("/fix/{fix_id}")
def get_fix(fix_id: str):
    """Get the full payload for a specific fix."""
    if not _queue:
        raise HTTPException(503, "Queue not initialised")
    fix = _queue.get_fix(fix_id)
    if not fix:
        raise HTTPException(404, f"fix_id '{fix_id}' not found")
    return fix


@app.post("/approve/{fix_id}")
async def approve_fix(fix_id: str, body: ApproveRequest = ApproveRequest()):
    """
    Approve a fix.
    1. Moves fix to approved queue
    2. Triggers applier.py to write to MySQL immediately
    3. Broadcasts update to approval UI via WebSocket
    4. Sends "applied" notification
    """
    if not _queue:
        raise HTTPException(503, "Queue not initialised")

    fix = _queue.get_fix(fix_id)
    if not fix:
        raise HTTPException(404, f"fix_id '{fix_id}' not found")

    # Move to approved
    ok = _queue.push_approved(fix_id, approved_by=body.approved_by)
    if not ok:
        raise HTTPException(500, "Failed to move fix to approved queue")

    # Apply to MySQL immediately
    apply_result = {"applied": False, "error": None}
    if _applier:
        try:
            applied = _applier.apply(fix)
            apply_result["applied"] = applied
            if applied and _notifier:
                record_id = fix.get("original", {}).get("id", "?")
                _notifier.notify_applied(fix_id, record_id)
        except Exception as exc:
            apply_result["error"] = str(exc)
            log.error(f"❌ Apply failed after approval: {exc}")

    # Push live update to approval UI
    await broadcast_ws({
        "event":    "approved",
        "fix_id":   fix_id,
        "by":       body.approved_by,
        "applied":  apply_result["applied"],
    })

    log.info(f"✅ fix_id={fix_id} approved by {body.approved_by} — applied={apply_result['applied']}")
    return {
        "status":  "approved",
        "fix_id":  fix_id,
        "applied": apply_result,
    }


@app.post("/reject/{fix_id}")
async def reject_fix(fix_id: str, body: RejectRequest = RejectRequest()):
    """
    Reject a fix.
    1. Moves fix to rejected queue
    2. Sends rejection notification
    3. Broadcasts update to approval UI
    """
    if not _queue:
        raise HTTPException(503, "Queue not initialised")

    fix = _queue.get_fix(fix_id)
    if not fix:
        raise HTTPException(404, f"fix_id '{fix_id}' not found")

    ok = _queue.push_rejected(fix_id, rejected_by=body.rejected_by, reason=body.reason)
    if not ok:
        raise HTTPException(500, "Failed to move fix to rejected queue")

    if _notifier:
        _notifier.notify_rejected(fix_id, reason=body.reason)

    await broadcast_ws({
        "event":   "rejected",
        "fix_id":  fix_id,
        "by":      body.rejected_by,
        "reason":  body.reason,
    })

    log.info(f"❌ fix_id={fix_id} rejected by {body.rejected_by} — reason: {body.reason}")
    return {
        "status":  "rejected",
        "fix_id":  fix_id,
        "reason":  body.reason,
    }