"""
worker6/api/app.py
FastAPI application — exposes audit log, reports, and stats via REST.
Runs on port 8770 inside Docker.
"""

import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import build_router

log = logging.getLogger("APIApp")


def build_app(audit_writer, memory_writer, report_builder) -> FastAPI:
    app = FastAPI(
        title="AutoQuerySolver — Audit API",
        description="Worker 6 audit log, reports, and memory stats.",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    router = build_router(audit_writer, memory_writer, report_builder)
    app.include_router(router)

    @app.get("/health")
    def health():
        return {"status": "ok", "worker": "6"}

    return app


def run_api(audit_writer, memory_writer, report_builder, host: str, port: int):
    app = build_app(audit_writer, memory_writer, report_builder)
    log.info(f"🌐 FastAPI starting on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")