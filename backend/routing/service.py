"""Model Router - Automatically selects the best available model for a task."""
import re
from typing import Optional
from models.runtime import OllamaRuntime


TASK_KEYWORDS = {
    "coding": [
        "code", "program", "function", "class", "debug", "fix bug", "implement",
        "python", "javascript", "typescript", "java", "rust", "sql", "algorithm",
        "refactor", "compile", "syntax", "api", "endpoint", "script",
    ],
    "vision": [
        "image", "picture", "photo", "diagram", "drawing", "chart", "graph",
        "screenshot", "scan", "visual", "look at", "describe this image",
        "engineering drawing", "blueprint", "floor plan",
    ],
    "document_reasoning": [
        "document", "pdf", "report", "summarize", "analyze document",
        "inspection report", "sop", "policy", "manual", "contract",
        "read this", "what does this say", "extract from",
    ],
    "embedding": [
        "embed", "similarity", "search", "find similar", "vector",
    ],
    "general_reasoning": [
        "explain", "what is", "how does", "why", "compare", "think about",
        "reasoning", "logic", "analyze", "evaluate", "opinion",
    ],
    "fast_chat": [
        "hello", "hi", "thanks", "yes", "no", "okay", "help",
        "translate", "define", "spell", "calculate",
    ],
}

MODEL_CAPABILITY_MAP = {
    "qwen3:8b": ["general_reasoning", "coding", "document_reasoning", "fast_chat"],
    # Vision-capable Ollama models, ordered by preference. Using the base
    # name (not "llava:7b") so any pulled tag/quantization of a family
    # matches - e.g. "llava:13b" or "llava:34b" still match "llava".
    "llava": ["vision", "general_reasoning"],
    "bakllava": ["vision", "general_reasoning"],
    "llama3.2-vision": ["vision", "general_reasoning"],
    "qwen2.5vl": ["vision", "general_reasoning", "document_reasoning"],
    "qwen2-vl": ["vision", "general_reasoning"],
    "minicpm-v": ["vision", "general_reasoning"],
    "moondream": ["vision"],
    "nomic-embed-text:latest": ["embedding"],
    "qwen2.5-coder": ["coding", "general_reasoning"],
    "mistral": ["general_reasoning", "document_reasoning", "fast_chat"],
    "llama3": ["general_reasoning", "coding", "document_reasoning"],
}


class ModelRouter:
    """Routes requests to the best available model based on task type."""

    def __init__(self):
        self.runtime = OllamaRuntime()

    def classify_task(self, query: str, attachments: Optional[list] = None) -> str:
        """Classify the task type from user query."""
        query_lower = query.lower()

        if attachments:
            for att in attachments:
                mime = att.get("mime_type", "")
                if mime.startswith("image/"):
                    return "vision"
                if "pdf" in mime or "document" in mime:
                    return "document_reasoning"
                if "audio" in mime:
                    return "audio"

        scores = {}
        for task_type, keywords in TASK_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            if score > 0:
                scores[task_type] = score

        if not scores:
            if len(query.split()) < 5:
                return "fast_chat"
            return "general_reasoning"

        return max(scores, key=scores.get)

    async def get_available_models(self) -> list[dict]:
        """Get models currently available from runtime."""
        return await self.runtime.list_models()

    async def route_request(
        self,
        query: str,
        task_type: Optional[str] = None,
        attachments: Optional[list] = None,
        mode: str = "balanced",
    ) -> dict:
        """Route a request to the best available model."""
        if not task_type:
            task_type = self.classify_task(query, attachments)

        available = await self.get_available_models()
        available_names = [m["name"] for m in available]

        # Find best model for task
        selected = None
        fallback = None
        reason = ""

        for model_name, capabilities in MODEL_CAPABILITY_MAP.items():
            # Check if model is available (partial match for tags)
            matched_available = None
            for avail in available_names:
                if model_name in avail or avail.startswith(model_name):
                    matched_available = avail
                    break

            if matched_available and task_type in capabilities:
                if selected is None:
                    selected = matched_available
                    reason = f"Best match for {task_type}"
                elif fallback is None:
                    fallback = matched_available

        # Default fallbacks
        if not selected:
            if available_names:
                selected = available_names[0]
                reason = "Default fallback (no specialized model found)"
            else:
                return {
                    "model_id": None,
                    "task_type": task_type,
                    "error": "No models available",
                    "reason": "No models detected from runtime",
                }

        if not fallback and available_names:
            fallback = next((m for m in available_names if m != selected), selected)

        return {
            "model_id": selected,
            "task_type": task_type,
            "reason": reason,
            "fallback": fallback,
            "mode": mode,
            "available_count": len(available_names),
        }
