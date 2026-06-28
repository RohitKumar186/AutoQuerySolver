"""
worker6/api/routes.py
REST endpoints exposed by Worker 6.

GET /audit          → last 100 audit rows
GET /audit/{id}     → single row by id
GET /stats          → aggregate stats
GET /report         → full human-readable report
GET /memory         → ChromaDB memory count
"""

import logging
from fastapi import APIRouter, HTTPException

log = logging.getLogger("Routes")


def build_router(audit_writer, memory_writer, report_builder) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/audit")
    def get_audit(limit: int = 100):
        """Return the most recent audit log rows."""
        try:
            rows = audit_writer.fetch_recent(limit=min(limit, 500))
            return {"count": len(rows), "rows": rows}
        except Exception as exc:
            log.error(f"GET /audit error: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

    @router.get("/stats")
    def get_stats():
        """Return aggregate statistics from the audit table."""
        try:
            stats = audit_writer.fetch_stats()
            return stats
        except Exception as exc:
            log.error(f"GET /stats error: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

    @router.get("/report")
    def get_report():
        """Return a full human-readable report with narrative."""
        try:
            stats       = audit_writer.fetch_stats()
            recent_rows = audit_writer.fetch_recent(limit=100)
            report      = report_builder.build(stats, recent_rows)
            return report
        except Exception as exc:
            log.error(f"GET /report error: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

    @router.get("/memory")
    def get_memory():
        """Return ChromaDB memory bank size."""
        try:
            count = memory_writer.count()
            return {"memory_entries": count, "collection": "doctor_fixes"}
        except Exception as exc:
            log.error(f"GET /memory error: {exc}")
            raise HTTPException(status_code=500, detail=str(exc))

    return router