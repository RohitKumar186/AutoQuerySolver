"""
issues/search.py
Step 2 — Search ChromaDB for the 3 most similar past fixes.
"""

import logging
from utils.chroma_client import get_collection

log = logging.getLogger("SearchNode")

TOP_K = 3


def search_node(state: dict) -> dict:
    embedding = state.get("embedding", [])
    record    = state.get("record", {})

    if not embedding:
        log.warning("  ⚠️  No embedding — skipping ChromaDB search.")
        return {**state, "similar": []}

    try:
        collection = get_collection()
        count = collection.count()

        if count == 0:
            log.info("  📭 ChromaDB empty — no past fixes.")
            return {**state, "similar": []}

        n = min(TOP_K, count)
        results = collection.query(
            query_embeddings=[embedding],
            n_results=n,
            include=["metadatas", "distances"],
        )

        similar = []
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for meta, dist in zip(metadatas, distances):
            similarity_score = round(1 - dist, 3)
            similar.append({
                "original":    meta.get("original"),
                "issues":      meta.get("issues"),
                "fixed":       meta.get("fixed"),
                "explanation": meta.get("explanation"),
                "confidence":  meta.get("confidence"),
                "similarity":  similarity_score,
            })
            log.info(f"  🔍 Similar fix — similarity={similarity_score}")

        log.info(f"  📚 Found {len(similar)} similar past fix(es).")
        return {**state, "similar": similar}

    except Exception as exc:
        log.error(f"  ❌ ChromaDB search error: {exc}")
        return {**state, "similar": []}