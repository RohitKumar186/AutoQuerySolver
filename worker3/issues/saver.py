"""
issues/saver.py
Step 5 — Save fix to ChromaDB + broadcast to dashboard.
"""

import json
import logging
from datetime import datetime, timezone

log = logging.getLogger("SaverNode")


def build_saver_node(broadcast_fn):

    def saver_node(state: dict) -> dict:
        log.info("  💉 Saver node started.")
        record    = state.get("record", {})
        issues    = state.get("issues", [])
        fix       = state.get("fix")
        fix_valid = state.get("fix_valid", False)
        op        = state.get("op", "?")
        embedding = state.get("embedding", [])
        ts        = state.get("ts", datetime.now(timezone.utc).strftime("%H:%M:%S"))

        if not fix:
            log.warning("  ⚠️  No fix to save.")
            return state

        fixed_record = fix.get("fixed_record", {})
        explanation  = fix.get("explanation", "")
        confidence   = fix.get("confidence", 0.0)

        # ── Save to ChromaDB ──────────────────────────────────────────
        if not embedding:
            log.warning("  ⚠️  No embedding available — skipping ChromaDB save (Gemini API key not set).")
        else:
            try:
                from utils.chroma_client import get_collection
                collection = get_collection()

                fix_id   = f"fix_{record.get('id', 'unknown')}_{ts.replace(':', '')}"
                document = f"Record: {json.dumps(record)} | Issues: {json.dumps(issues)}"
                metadata = {
                    "original":    json.dumps(record),
                    "issues":      json.dumps(issues),
                    "fixed":       json.dumps(fixed_record),
                    "explanation": explanation,
                    "confidence":  str(confidence),
                    "fix_valid":   str(fix_valid),
                    "op":          op,
                    "ts":          ts,
                }

                collection.upsert(
                    ids=[fix_id],
                    embeddings=[embedding],
                    metadatas=[metadata],
                    documents=[document],
                )
                log.info(f"  💾 Fix saved to ChromaDB — id={fix_id} total={collection.count()}")

            except Exception as exc:
                log.error(f"  ❌ ChromaDB save error: {exc}", exc_info=True)

        # ── Broadcast to dashboard ────────────────────────────────────
        try:
            broadcast_fn({
                "type":         "fix",
                "op":           op,
                "original":     record,
                "issues":       issues,
                "fixed":        {**record, **fixed_record},
                "fixed_fields": fixed_record,
                "explanation":  explanation,
                "confidence":   confidence,
                "fix_valid":    fix_valid,
                "ts":           ts,
            })
            log.info(f"  📡 Fix broadcasted — valid={fix_valid} confidence={confidence}")
        except Exception as exc:
            log.error(f"  ❌ Broadcast error: {exc}", exc_info=True)

        log.info("  ✅ Saver node complete.")
        return state

    return saver_node