"""
issues/embed.py
Step 1 — Convert the bad record + issues into a vector.
Focuses on issue patterns (field names + issue types) rather than raw values,
so similar types of problems cluster together in ChromaDB.
"""

import json
import logging
import hashlib
import math
from collections import Counter

log = logging.getLogger("EmbedNode")

VECTOR_SIZE = 384


def _ngrams(text: str, n: int) -> list:
    text = text.lower()
    return [text[i:i+n] for i in range(len(text) - n + 1)]


def _get_embedding(text: str, weight: float = 1.0, vec: list = None) -> list:
    if vec is None:
        vec = [0.0] * VECTOR_SIZE
    grams = _ngrams(text, 3) + _ngrams(text, 2)
    counts = Counter(grams)
    for gram, count in counts.items():
        idx = int(hashlib.md5(gram.encode()).hexdigest(), 16) % VECTOR_SIZE
        vec[idx] += count * weight
    return vec


def embed_node(state: dict) -> dict:
    record = state.get("record", {})
    issues = state.get("issues", [])

    log.info(f"  🔢 Generating embedding for record id={record.get('id', '?')}")

    try:
        vec = [0.0] * VECTOR_SIZE

        for issue in issues:
            _get_embedding(issue, weight=5.0, vec=vec)

        for key in record.keys():
            _get_embedding(key, weight=2.0, vec=vec)

        _get_embedding(json.dumps(record), weight=1.0, vec=vec)

        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        embedding = [x / norm for x in vec]

        log.info(f"  🔢 Embedding generated — {len(embedding)} dimensions (issue-weighted).")
        return {**state, "embedding": embedding}

    except Exception as exc:
        log.error(f"  ❌ Embedding error: {exc}")
        return {**state, "embedding": []}
