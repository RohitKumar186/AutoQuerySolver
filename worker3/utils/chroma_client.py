"""
utils/chroma_client.py
Single shared ChromaDB client for all nodes.
"""

import logging
import os
import chromadb

log = logging.getLogger("ChromaClient")

CHROMA_PATH     = os.getenv("CHROMA_PATH", "/chroma_data")
COLLECTION_NAME = "doctor_fixes"


def get_collection():
    """
    Creates a fresh client + collection every call.
    Avoids threading issues with shared state.
    """
    try:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        log.info(f"✅ ChromaDB collection ready — {collection.count()} fix(es) stored.")
        return collection
    except Exception as exc:
        log.error(f"❌ ChromaDB init error: {exc}")
        raise