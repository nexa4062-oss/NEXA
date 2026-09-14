"""Shared helper for generating embeddings via whatever local Ollama
embedding model (e.g. nomic-embed-text) is actually installed.

Used at document-indexing time (to embed each chunk) and at query time
(to embed the user's question) so both sides go through the same model
lookup and the same graceful-failure behavior.
"""
from typing import Optional

from routing.service import ModelRouter
from models.runtime import OllamaRuntime

_router = ModelRouter()
_runtime = OllamaRuntime()


async def get_embedding(text: str) -> Optional[list[float]]:
    """Return an embedding vector for `text`, or None if no embedding
    model is currently available locally. Never raises - callers should
    treat None as "fall back to keyword search", not as an error."""
    if not text or not text.strip():
        return None

    try:
        route = await _router.route_request(text, task_type="embedding")
        model_id = route.get("model_id")
        if not model_id:
            return None

        vector = await _runtime.embeddings(model_id, text)
        return vector if vector else None
    except Exception:
        return None
