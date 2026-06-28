"""
worker6/services/memory_writer.py
Feeds confirmed fix pairs into ChromaDB so Worker 3 gets smarter over time.

Uses the same n-gram hash embedding strategy as Worker 3 (pure Python,
no external embedding model dependencies).
"""

import json
import logging

import chromadb

from config import CHROMA_PATH, CHROMA_COLLECTION

log = logging.getLogger("MemoryWriter")


# ── Pure-Python n-gram hash embedding (mirrors Worker 3) ──────────────────────
def _ngram_hash_embedding(text: str, n: int = 3, dim: int = 256) -> list[float]:
    """
    Convert text into a fixed-size float vector using character n-gram hashing.
    Identical implementation to Worker 3 so vectors are comparable.
    """
    text  = text.lower().strip()
    vec   = [0.0] * dim
    total = 0

    for i in range(len(text) - n + 1):
        gram  = text[i:i + n]
        h     = hash(gram) % dim
        vec[h] += 1.0
        total  += 1

    if total > 0:
        vec = [v / total for v in vec]

    return vec


def _build_document(original: dict, issues: list, fixed: dict) -> str:
    return (
        f"Record: {json.dumps(original)} | "
        f"Issues: {json.dumps(issues)} | "
        f"Fixed: {json.dumps(fixed)}"
    )


# ── MemoryWriter ───────────────────────────────────────────────────────────────
class MemoryWriter:
    def __init__(self):
        self._client     = None
        self._collection = None
        self._init()

    def _init(self):
        try:
            self._client     = chromadb.PersistentClient(path=CHROMA_PATH)
            self._collection = self._client.get_or_create_collection(
                name=CHROMA_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
            log.info(
                f"✅ ChromaDB ready — "
                f"{self._collection.count()} fix(es) in memory."
            )
        except Exception as exc:
            log.error(f"❌ ChromaDB init error: {exc}", exc_info=True)

    def write(self, event: dict) -> bool:
        """
        Upsert one confirmed fix into ChromaDB.
        Returns True on success.

        Only writes if fix_valid=True or confidence >= 0.7
        (low-confidence fixes would pollute the memory bank).
        """
        if self._collection is None:
            log.warning("  ⚠️  ChromaDB not available — memory write skipped.")
            return False

        fix_valid  = event.get("fix_valid", False)
        confidence = event.get("confidence") or 0.0
        if not fix_valid and confidence < 0.7:
            log.info(
                f"  ⏭️  Memory write skipped — "
                f"fix_valid={fix_valid} confidence={confidence}"
            )
            return False

        original    = event.get("original") or {}
        fixed       = event.get("fixed") or {}
        issues      = event.get("issues") or []
        explanation = event.get("explanation", "")
        record_id   = event.get("record_id", "unknown")
        ts          = event.get("ts", "")

        doc_text  = _build_document(original, issues, fixed)
        embedding = _ngram_hash_embedding(doc_text)
        fix_id    = f"w6_fix_{record_id}_{ts.replace(':', '')}"

        metadata = {
            "original":    json.dumps(original),
            "issues":      json.dumps(issues),
            "fixed":       json.dumps(fixed),
            "explanation": explanation,
            "confidence":  str(confidence),
            "fix_valid":   str(fix_valid),
            "source":      "worker6",
        }

        try:
            self._collection.upsert(
                ids=[fix_id],
                embeddings=[embedding],
                metadatas=[metadata],
                documents=[doc_text],
            )
            log.info(
                f"  🧠 Memory updated — fix_id={fix_id} "
                f"total={self._collection.count()}"
            )
            return True
        except Exception as exc:
            log.error(f"  ❌ Memory write error: {exc}", exc_info=True)
            return False

    def count(self) -> int:
        if self._collection is None:
            return 0
        try:
            return self._collection.count()
        except Exception:
            return 0