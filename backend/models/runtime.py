"""Model Runtime abstraction layer.

ModelRuntime
 ├── OllamaRuntime (primary)
 └── FutureLocalRuntime (extensible)
"""
import httpx
import json
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional
from config import get_settings

settings = get_settings()


class ModelRuntime(ABC):
    """Abstract base class for local model runtimes."""

    @abstractmethod
    async def list_models(self) -> list[dict]:
        """List all available models."""
        pass

    @abstractmethod
    async def generate(self, model_id: str, prompt: str, **kwargs) -> str:
        """Generate a complete response."""
        pass

    @abstractmethod
    async def generate_stream(self, model_id: str, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """Generate a streaming response."""
        pass

    @abstractmethod
    async def health_check(self) -> dict:
        """Check runtime health."""
        pass

    @abstractmethod
    async def model_info(self, model_id: str) -> Optional[dict]:
        """Get detailed model information."""
        pass

    @abstractmethod
    async def pull_model(self, model_id: str) -> AsyncGenerator[dict, None]:
        """Pull/download a model."""
        pass

    @abstractmethod
    async def embeddings(self, model_id: str, text: str) -> list[float]:
        """Generate embeddings."""
        pass


class OllamaRuntime(ModelRuntime):
    """Ollama local model runtime adapter."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.OLLAMA_URL
        self.timeout = settings.OLLAMA_TIMEOUT

    async def list_models(self) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10, connect=3)) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                models = []
                for m in data.get("models", []):
                    models.append({
                        "name": m.get("name", ""),
                        "model": m.get("model", m.get("name", "")),
                        "size": m.get("size", 0),
                        "digest": m.get("digest", ""),
                        "modified_at": m.get("modified_at", ""),
                        "details": m.get("details", {}),
                    })
                return models
        except Exception as e:
            return []

    async def generate(self, model_id: str, prompt: str, **kwargs) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "model": model_id,
                    "prompt": prompt,
                    "stream": False,
                    **kwargs,
                }
                resp = await client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                return resp.json().get("response", "")
        except httpx.TimeoutException:
            return "Error: Model generation timed out. Please try again."
        except Exception as e:
            return f"Error: Failed to generate response: {str(e)}"

    async def generate_stream(self, model_id: str, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "model": model_id,
                    "prompt": prompt,
                    "stream": True,
                    **kwargs,
                }
                async with client.stream("POST", f"{self.base_url}/api/generate", json=payload) as resp:
                    # Unlike generate(), this never called raise_for_status() or
                    # checked for an "error" field in the stream - so an Ollama-side
                    # failure (bad/oversized model, OOM, model not found, etc, same
                    # as the 500 the Model Control "Test Model" button surfaces)
                    # silently produced zero tokens: the UI showed an empty reply
                    # with just the "via <model> | <task>" footer and no error at
                    # all. Surfacing it as visible "Error: ..." text (matching the
                    # error style generate() already uses) fixes that.
                    if resp.status_code >= 400:
                        body = await resp.aread()
                        try:
                            detail = json.loads(body).get("error", body.decode(errors="replace"))
                        except Exception:
                            detail = body.decode(errors="replace")
                        yield f"Error: Ollama returned {resp.status_code}: {detail}"
                        return

                    async for line in resp.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            if data.get("error"):
                                yield f"Error: {data['error']}"
                                return
                            token = data.get("response", "")
                            if token:
                                yield token
                            if data.get("done", False):
                                break
        except httpx.TimeoutException:
            yield "Error: Model generation timed out. Please try again."
        except Exception as e:
            yield f"Error: {str(e)}"

    async def chat(self, model_id: str, messages: list[dict], **kwargs) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "model": model_id,
                    "messages": messages,
                    "stream": False,
                    **kwargs,
                }
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                return resp.json().get("message", {}).get("content", "")
        except Exception as e:
            return f"Error: {str(e)}"

    async def chat_stream(self, model_id: str, messages: list[dict], **kwargs) -> AsyncGenerator[str, None]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "model": model_id,
                    "messages": messages,
                    "stream": True,
                    **kwargs,
                }
                async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                    async for line in resp.aiter_lines():
                        if line:
                            import json
                            try:
                                data = json.loads(line)
                                token = data.get("message", {}).get("content", "")
                                if token:
                                    yield token
                                if data.get("done", False):
                                    break
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            yield f"Error: {str(e)}"

    async def health_check(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    return {
                        "status": "healthy",
                        "runtime": "ollama",
                        "url": self.base_url,
                        "model_count": len(models),
                    }
                return {"status": "unhealthy", "runtime": "ollama", "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"status": "unavailable", "runtime": "ollama", "error": str(e)}

    async def model_info(self, model_id: str) -> Optional[dict]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(f"{self.base_url}/api/show", json={"name": model_id})
                if resp.status_code == 200:
                    return resp.json()
                return None
        except Exception:
            return None

    async def pull_model(self, model_id: str) -> AsyncGenerator[dict, None]:
        try:
            async with httpx.AsyncClient(timeout=3600) as client:
                async with client.stream("POST", f"{self.base_url}/api/pull",
                                         json={"name": model_id, "stream": True}) as resp:
                    async for line in resp.aiter_lines():
                        if line:
                            import json
                            try:
                                yield json.loads(line)
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            yield {"status": f"Error: {str(e)}"}

    async def embeddings(self, model_id: str, text: str) -> list[float]:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": model_id, "prompt": text}
                )
                resp.raise_for_status()
                return resp.json().get("embedding", [])
        except Exception:
            return []


class RuntimeManager:
    """Manages available model runtimes."""

    def __init__(self):
        self.runtimes: dict[str, ModelRuntime] = {
            "ollama": OllamaRuntime(),
        }

    def get_runtime(self, name: str) -> Optional[ModelRuntime]:
        return self.runtimes.get(name)

    def register_runtime(self, name: str, runtime: ModelRuntime):
        self.runtimes[name] = runtime

    async def health_check_all(self) -> dict:
        results = {}
        for name, runtime in self.runtimes.items():
            results[name] = await runtime.health_check()
        return results
